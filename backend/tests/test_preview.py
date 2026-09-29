"""Preview deployment (local Docker): hermetic contract tests — no daemon."""

from pathlib import Path

import pytest

from app.preview import builder
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import empty_requirements
from app.services.preview_service import PreviewNotReadyError, PreviewService
from app.workspace import workspace as ws

PROJECT_ID = "abcdef0123456789abcdef01"


@pytest.fixture()
def preview_ws(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path / "generated"))
    return ws.source_dir(PROJECT_ID)


def test_workspace_ships_preview_deploy_files():
    """Every generated workspace must be self-hostable via its deploy/ dir."""
    ws.copy_template(PROJECT_ID)
    deploy = ws.source_dir(PROJECT_ID) / "deploy"
    assert (deploy / "compose.yml").is_file()
    assert (deploy / "backend.Dockerfile").is_file()
    assert (deploy / "frontend.Dockerfile").is_file()


def test_workspace_ships_fallback_vite_entry_point():
    """The platform must be able to supply the frontend build entry.

    Vite resolves the build from index.html. When it is absent no dist/ is
    emitted and the preview image fails at COPY with "stat app/dist: file
    does not exist" — observed in production before these files existed.

    These are fallbacks, not overrides: frontend.Dockerfile only copies them
    in when the generated app has none. They carry content the model owns —
    the page title and the stylesheet import — so overwriting a model-authored
    entry produced an unstyled page.
    """
    ws.copy_template(PROJECT_ID)
    canonical = ws.source_dir(PROJECT_ID) / "deploy" / "frontend"
    assert (canonical / "index.html").is_file()
    assert (canonical / "src" / "main.tsx").is_file()
    assert (canonical / "vite.config.ts").is_file()
    assert 'src="/src/main.tsx"' in (canonical / "index.html").read_text(encoding="utf-8")


def test_pick_slot_returns_free_slot():
    slot = builder.pick_slot()
    assert 1 <= slot <= builder.config.PREVIEW_SLOTS


def test_pick_slot_skips_occupied():
    assert builder.pick_slot({1, 2}) == 3
    occupied = set(range(1, builder.config.PREVIEW_SLOTS + 1))
    with pytest.raises(builder.PreviewError, match="preview slots are in use"):
        builder.pick_slot(occupied)


def test_slot_port_and_public_url_stay_in_step(monkeypatch):
    """Slot N must land on loopback 8200+N and be served on 9000+N.

    These two bases are what the Caddyfile site blocks assume; if they drift,
    previews resolve to the wrong container or to nothing.
    """
    monkeypatch.setattr(builder.config, "PREVIEW_PORT_BASE", 8200)
    monkeypatch.setattr(builder.config, "PREVIEW_PUBLIC_PORT_BASE", 9000)
    monkeypatch.setattr(builder.config, "PUBLIC_BASE_URL", "https://example.test")
    assert builder.slot_port(3) == 8203
    assert builder.public_url(3) == "https://example.test:9003/"


def test_public_url_never_advertises_localhost(monkeypatch):
    """A preview URL must be reachable from a browser, not just from the host."""
    monkeypatch.setattr(builder.config, "PUBLIC_BASE_URL", "https://example.test")
    assert "localhost" not in builder.public_url(1)


def test_compose_file_missing_raises(preview_ws: Path):
    with pytest.raises(builder.PreviewError, match="deploy/compose.yml"):
        builder.compose_file(preview_ws)


def test_stack_up_reports_failure(tmp_path: Path, monkeypatch):
    def fake_run(args, timeout):
        from subprocess import CompletedProcess

        return CompletedProcess(args, 1, stdout="", stderr="build failed: no such file")

    monkeypatch.setattr(builder, "_run", fake_run)
    ws.copy_template(PROJECT_ID)
    with pytest.raises(builder.PreviewError, match="build failed"):
        builder.stack_up(ws.source_dir(PROJECT_ID), PROJECT_ID, 8200)


def test_stack_up_writes_env_and_succeeds(tmp_path: Path, monkeypatch):
    captured = {}

    def fake_run(args, timeout):
        captured["args"] = args
        from subprocess import CompletedProcess

        return CompletedProcess(args, 0, stdout="Started", stderr="")

    monkeypatch.setattr(builder, "_run", fake_run)
    ws.copy_template(PROJECT_ID)
    source = ws.source_dir(PROJECT_ID)
    builder.stack_up(source, PROJECT_ID, 8217)
    args = captured["args"]
    assert "aladdin-poc-abcdef01" in args  # compose project name from id prefix
    assert any(arg.endswith(str(Path("deploy") / "compose.yml")) for arg in args)
    assert "POC_PORT=8217" in (source / "deploy" / ".preview.env").read_text()


async def test_start_requires_ready_project(db):
    service = PreviewService(db)
    repo = ProjectRepository(db)
    project_id = await repo.create("T", "T", empty_requirements("p"), 14)
    with pytest.raises(PreviewNotReadyError, match="REQUIREMENT_COLLECTION"):
        await service.start(project_id)


async def test_start_rejects_without_docker(db, monkeypatch):
    repo = ProjectRepository(db)
    project_id = await repo.create("T", "T", empty_requirements("p"), 100)
    await repo.update_fields(project_id, {"status": "READY"})
    monkeypatch.setattr(builder, "docker_available", lambda: False)
    service = PreviewService(db)
    with pytest.raises(PreviewNotReadyError, match="Docker is not available"):
        await service.start(project_id)


async def test_start_and_failed_build_flow(db, monkeypatch):
    repo = ProjectRepository(db)
    project_id = await repo.create("T", "T", empty_requirements("p"), 100)
    await repo.update_fields(project_id, {"status": "READY"})
    monkeypatch.setattr(builder, "docker_available", lambda: True)

    async def explode(pid, occupied):
        raise builder.PreviewError("docker build exploded")

    monkeypatch.setattr(builder, "build_and_start", explode)
    service = PreviewService(db)
    state = await service.start(project_id)
    assert state["status"] == "building"
    await service.run_build(project_id)
    failed = await service.get_state(project_id)
    assert failed["status"] == "failed"
    assert "docker build exploded" in failed["message"]


async def test_successful_build_flow_records_slot(db, monkeypatch):
    repo = ProjectRepository(db)
    project_id = await repo.create("T", "T", empty_requirements("p"), 100)
    await repo.update_fields(project_id, {"status": "READY"})
    monkeypatch.setattr(builder, "docker_available", lambda: True)

    async def fake_build(pid, occupied):
        return 7

    monkeypatch.setattr(builder, "build_and_start", fake_build)
    monkeypatch.setattr(builder.config, "PREVIEW_PORT_BASE", 8200)
    monkeypatch.setattr(builder.config, "PREVIEW_PUBLIC_PORT_BASE", 9000)
    monkeypatch.setattr(builder.config, "PUBLIC_BASE_URL", "https://example.test")
    service = PreviewService(db)
    await service.start(project_id)
    await service.run_build(project_id)
    running = await service.get_state(project_id)
    assert running["status"] == "running"
    assert running["slot"] == 7
    assert running["port"] == 8207
    assert running["url"] == "https://example.test:9007/"
    assert running["expiresAt"] is not None
    # stop tears down and resets state
    monkeypatch.setattr(builder, "stack_down", lambda pid, source_dir: None)
    stopped = await service.stop(project_id)
    assert stopped["status"] == "none"
    assert stopped["port"] is None
    assert stopped["slot"] is None


def test_wait_healthy_probes_the_poc_network(monkeypatch):
    """The probe must run on the PoC's own network, not the published port.

    The stack binds its host port to loopback so only the reverse proxy can
    reach it, which is unreachable from this container.
    """
    from subprocess import CompletedProcess

    captured = {}

    def ok(args, timeout):
        captured["args"] = args
        return CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(builder, "_run", ok)
    monkeypatch.setattr(builder.config, "PREVIEW_HEALTH_TIMEOUT_SECONDS", 1)
    assert builder.wait_healthy(PROJECT_ID) is True

    args = captured["args"]
    assert f"{builder.project_name(PROJECT_ID)}_default" in args
    assert "http://poc-frontend:80/health" in args
    # Probing a host port would mean the preview was never actually verified.
    assert not any("127.0.0.1" in str(a) or "host.docker.internal" in str(a) for a in args)


def test_wait_healthy_false_when_probe_never_succeeds(monkeypatch):
    from subprocess import CompletedProcess

    monkeypatch.setattr(
        builder,
        "_run",
        lambda args, timeout: CompletedProcess(args, 1, stdout="", stderr="refused"),
    )
    monkeypatch.setattr(builder.config, "PREVIEW_HEALTH_TIMEOUT_SECONDS", 1)
    assert builder.wait_healthy(PROJECT_ID) is False


async def test_start_rejects_when_all_slots_busy(db, monkeypatch):
    """A build that has nowhere to land must be refused before it starts.

    Otherwise the user waits minutes for a compose build that cannot be
    published, and the machine does the work anyway.
    """
    repo = ProjectRepository(db)
    monkeypatch.setattr(builder, "docker_available", lambda: True)
    monkeypatch.setattr(builder.config, "PREVIEW_SLOTS", 2)

    for slot in (1, 2):
        busy = await repo.create("busy", "busy", empty_requirements("p"), 100)
        await repo.update_fields(
            busy, {"status": "READY", "preview": {"status": "running", "slot": slot}}
        )

    project_id = await repo.create("T", "T", empty_requirements("p"), 100)
    await repo.update_fields(project_id, {"status": "READY"})
    service = PreviewService(db)
    with pytest.raises(PreviewNotReadyError, match="preview slots are in use"):
        await service.start(project_id)


async def test_reaper_stops_expired_previews_only(db, monkeypatch):
    """Expired previews are torn down; live ones are left alone."""
    from datetime import timedelta

    from app.schemas.project import utcnow

    repo = ProjectRepository(db)
    monkeypatch.setattr(builder, "stack_down", lambda pid, source_dir: None)

    stale = await repo.create("stale", "stale", empty_requirements("p"), 100)
    await repo.update_fields(
        stale,
        {
            "status": "READY",
            "preview": {
                "status": "running",
                "slot": 1,
                "expiresAt": (utcnow() - timedelta(minutes=5)).isoformat(),
            },
        },
    )
    fresh = await repo.create("fresh", "fresh", empty_requirements("p"), 100)
    await repo.update_fields(
        fresh,
        {
            "status": "READY",
            "preview": {
                "status": "running",
                "slot": 2,
                "expiresAt": (utcnow() + timedelta(minutes=30)).isoformat(),
            },
        },
    )

    service = PreviewService(db)
    assert await service.reap_expired() == 1
    assert (await service.get_state(stale))["status"] == "none"
    assert (await service.get_state(fresh))["status"] == "running"
