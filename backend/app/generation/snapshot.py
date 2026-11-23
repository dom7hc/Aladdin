"""Bounded initial API capture. Process isolation is NOT a security sandbox.

The generated app owns aggregation and any DB seeding, always into a throwaway POC_DB.
Its lifespan reads the existing dataset; no second aggregation implementation.
"""

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

MAX_PAYLOAD_BYTES = 512_000
MAX_TOTAL_BYTES = 2_000_000
DEPENDENCIES = ("fastapi", "httpx")


class CaptureError(Exception):
    """Safe, bounded diagnostic; never expose child output or exception text."""


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def content_hash(value) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def capture(source: Path, spec: dict, *, timeout: float = 10) -> dict:
    # Import only on the parent path: the child runs this file with -I and does
    # not import platform modules (or inherit PYTHONPATH/LLM/DB credentials).
    from app.generation.spec import normalize_spec, spec_endpoints, validate_spec

    try:
        spec = normalize_spec(spec)
        if validate_spec(spec):
            raise ValueError()
        paths = sorted(spec_endpoints(spec))
        if not paths or len(paths) > 22:
            raise ValueError()
    except (TypeError, ValueError, KeyError):
        raise CaptureError("Presentation capture has an invalid dashboard spec.") from None
    if any(importlib.util.find_spec(name) is None for name in DEPENDENCIES):
        raise CaptureError("Presentation capture dependency unavailable.")
    backend = source.resolve() / "backend"
    if not (backend / "main.py").is_file() or not (backend / "data/dataset.json").is_file():
        raise CaptureError("Presentation capture source or dataset missing.")
    # Explicit allowlist rather than trying to enumerate all possible secrets.
    env = {
        key: os.environ[key]
        for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LANG", "LC_ALL")
        if key in os.environ
    }
    env["PYTHONIOENCODING"] = "utf-8"
    with tempfile.TemporaryDirectory(prefix=".capture-", dir=source.parent) as temp:
        directory = Path(temp)
        request = directory / "request.json"
        output = directory / "output.json"
        request.write_bytes(canonical_bytes(paths))
        # Always a fresh absent path inside the owned temp dir. Generated apps
        # open their DB at import with a default such as /data/poc.db, which
        # the platform user cannot create on the server (capture then failed
        # for every dashboard without an editable table). Apps that seed from
        # the dataset do so on startup; the preview database is never touched.
        env["POC_DB"] = str(directory / "capture.db")
        try:
            process = subprocess.Popen(
                [sys.executable, "-I", str(Path(__file__).resolve()), str(request), str(output)],
                cwd=backend,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=os.name != "nt",
            )
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                            timeout=3,
                        )
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                finally:
                    process.kill()
                    process.wait()
                raise CaptureError("Presentation capture timed out.") from None
            if code != 0 or not output.is_file():
                raise CaptureError("Presentation capture failed or returned invalid payloads.")
            if output.stat().st_size > MAX_TOTAL_BYTES:
                raise CaptureError("Presentation capture exceeded payload limit.")
            endpoints = json.loads(output.read_bytes())
            if set(endpoints) != set(paths):
                raise CaptureError("Presentation capture has incomplete endpoints.")
        except OSError:
            raise CaptureError("Presentation capture process unavailable.") from None
    return {
        "schemaVersion": 1,
        "specHash": content_hash(spec),
        "capturedAt": datetime.now(UTC).isoformat(),
        "scope": "Initial generation snapshot; default filters (all records)",
        "provenance": spec["provenance"],
        "endpoints": endpoints,
    }


def _child(request: str, output: str) -> None:
    from fastapi.testclient import TestClient

    sys.path.insert(0, str(Path.cwd()))
    module_spec = importlib.util.spec_from_file_location("_captured_app", Path.cwd() / "main.py")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    paths = json.loads(Path(request).read_bytes())
    endpoints = {}
    # Context manager is essential for startup/shutdown and dataset/DB seeding.
    with TestClient(module.app) as client:
        for path in paths:
            response = client.get(path, follow_redirects=False)
            if response.status_code != 200 or len(response.content) > MAX_PAYLOAD_BYTES:
                raise ValueError("invalid response")
            payload = response.json()
            if not isinstance(payload, (dict, list)):
                raise TypeError("invalid payload shape")
            canonical_bytes(payload)  # reject NaN/Infinity, including nested values
            endpoints[path] = payload
            if len(canonical_bytes(endpoints)) > MAX_TOTAL_BYTES:
                raise ValueError("payload limit")
    Path(output).write_bytes(canonical_bytes(endpoints))


if __name__ == "__main__":
    _child(*sys.argv[1:])
