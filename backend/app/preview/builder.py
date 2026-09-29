"""Preview deployment of a generated PoC on the host Docker daemon.

The generated workspace ships a `deploy/` directory (Dockerfiles + compose
file) from the platform template, so every PoC is self-hostable: the builder
runs `docker compose up -d --build` against the workspace and returns the slot
it was published on.

Requires the Docker socket to be mounted, which deploy/compose.yml does for
both the local and deployed stacks. That is root-equivalent on the host, so the
site sits behind the access gate in deploy/caddy/Caddyfile.
"""

import asyncio
import logging
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from app import config

logger = logging.getLogger(__name__)

COMPOSE_TIMEOUT_SECONDS = 900


class PreviewError(Exception):
    """Raised when a preview stack cannot be built, started or verified."""


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def docker_available() -> bool:
    """True when a Docker daemon answers through the available client."""
    try:
        return _run(["docker", "version", "--format", "{{.Server.Version}}"], 15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def slot_port(slot: int) -> int:
    """Loopback port a preview slot publishes on."""
    return config.PREVIEW_PORT_BASE + slot


def public_url(slot: int) -> str:
    """Browser-reachable URL for a preview slot.

    One port per slot, not one path per slot: generated frontends call
    absolute /api/... paths (see app/generation/contract.py), so a shared path
    prefix would send those calls to this platform's API instead of the PoC's.
    A distinct origin per preview keeps absolute paths inside that preview.
    """
    host = config.PUBLIC_BASE_URL.rstrip("/")
    return f"{host}:{config.PREVIEW_PUBLIC_PORT_BASE + slot}/"


def pick_slot(occupied: set[int] | None = None) -> int:
    """Lowest free preview slot.

    ``occupied`` lists slots already held by running previews: on Windows a
    plain bind-probe can succeed against a 0.0.0.0 listener, so the DB-known
    slots must be excluded before probing.
    """
    taken = occupied or set()
    for slot in range(1, config.PREVIEW_SLOTS + 1):
        if slot in taken:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", slot_port(slot)))
            except OSError:
                continue
        return slot
    raise PreviewError(
        f"All {config.PREVIEW_SLOTS} preview slots are in use; stop a running preview and try again"
    )


def project_name(project_id: str) -> str:
    """Compose project name for a PoC preview stack."""
    return f"aladdin-poc-{project_id[:8]}"


def compose_file(source_dir: Path) -> Path:
    path = source_dir / "deploy" / "compose.yml"
    if not path.is_file():
        raise PreviewError(
            "Generated workspace has no deploy/compose.yml; re-run generation "
            "with a template that ships the preview stack"
        )
    return path


def stack_up(source_dir: Path, project_id: str, port: int) -> dict[str, Any]:
    """Build and start the PoC preview stack; returns normalized command output."""
    compose_path = compose_file(source_dir)
    args = [
        "docker",
        "compose",
        "-p",
        project_name(project_id),
        "--env-file",
        _write_env(source_dir, port),
        "-f",
        str(compose_path),
        "up",
        "-d",
        "--build",
        "--remove-orphans",
    ]
    try:
        result = _run(args, COMPOSE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise PreviewError(f"Preview build timed out after {COMPOSE_TIMEOUT_SECONDS}s") from exc
    if result.returncode != 0:
        raise PreviewError(_tail(result.stderr or result.stdout or "docker compose failed"))
    return {
        "command": " ".join(args[:2] + ["up -d --build"]),
        "exitCode": 0,
        "stdout": _trim(result.stdout),
        "stderr": _trim(result.stderr),
        "durationMs": None,
    }


def stack_down(project_id: str, source_dir: Path | None = None) -> None:
    """Stop and remove the PoC preview stack (and its volumes)."""
    args = ["docker", "compose", "-p", project_name(project_id)]
    if source_dir is not None and compose_file(source_dir).is_file():
        args += [
            "--env-file",
            _write_env(source_dir, 0),
            "-f",
            str(source_dir / "deploy" / "compose.yml"),
        ]
    args += ["down", "-v", "--remove-orphans"]
    try:
        result = _run(args, 120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise PreviewError(f"Failed to stop preview stack: {exc}") from exc
    if result.returncode != 0:
        raise PreviewError(_trim(result.stderr or "docker compose down failed"))


def wait_healthy(project_id: str) -> bool:
    """Poll the PoC's own /health until it answers or time runs out.

    Probed from a throwaway container on the PoC's compose network rather than
    through the published host port. The stack binds its port to 127.0.0.1 so
    that only the reverse proxy can reach it, and a loopback-bound host port is
    not reachable from this container on Linux (nor portably on Docker
    Desktop). The PoC network is, and it answers the same nginx that the proxy
    will forward to.
    """
    network = f"{project_name(project_id)}_default"
    url = "http://poc-frontend:80/health"
    deadline = time.monotonic() + config.PREVIEW_HEALTH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            probe = _run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    network,
                    config.PREVIEW_PROBE_IMAGE,
                    "wget",
                    "--quiet",
                    "--tries=1",
                    "--output-document=/dev/null",
                    url,
                ],
                30,
            )
            if probe.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            pass
        time.sleep(3)
    return False


def _write_env(source_dir: Path, port: int) -> str:
    env_path = source_dir / "deploy" / ".preview.env"
    env_path.write_text(f"POC_PORT={port}\n", encoding="utf-8")
    return str(env_path)


def _trim(text: str, limit: int = 4_000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n... [truncated]"


def _tail(text: str, limit: int = 1_500) -> str:
    """Keep the END of build output: that is where the actual error lives."""
    text = text.strip()
    return text if len(text) <= limit else "... [truncated]\n" + text[-limit:]


async def build_and_start(project_id: str, occupied: set[int] | None = None) -> int:
    """Async orchestration used by the preview service. Returns the slot."""
    if not await asyncio.to_thread(docker_available):
        raise PreviewError(
            "Docker is not available to this backend; preview requires a mounted Docker socket"
        )
    from app.workspace import workspace as ws

    source_dir = Path(ws.source_dir(project_id))
    if not (source_dir / "backend" / "main.py").is_file():
        raise PreviewError("Generated workspace is empty; run generate first")
    slot = await asyncio.to_thread(pick_slot, occupied)
    port = slot_port(slot)
    await asyncio.to_thread(stack_up, source_dir, project_id, port)
    healthy = await asyncio.to_thread(wait_healthy, project_id)
    if not healthy:
        # Leaving a half-started stack behind would hold the slot forever.
        try:
            await asyncio.to_thread(stack_down, project_id, source_dir)
        except PreviewError:
            logger.warning("Could not tear down unhealthy preview for %s", project_id)
        raise PreviewError(f"Preview containers started on slot {slot} but /health never answered")
    return slot
