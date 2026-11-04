"""Deterministic API-contract check between the generated frontend and backend.

AI Developer Plan §8 functional check: "Are expected API routes available?".
Two sources of required calls, both paired with their HTTP method:

- ``dashboard.config.json`` (platform-written from the validated spec): a GET
  per widget endpoint, plus POST/PUT/DELETE for every editable table. The kit
  reads endpoints from the spec at runtime, so without this the reads would
  never be checked at all.
- ``fetch`` calls with /api literals in frontend source — a safety net for any
  call written outside the kit.

The developer agent writes both sides in one shot, so nothing stops the model
from promising an endpoint it never implemented (observed: `POST /api/users`
against a backend without it). This checker fails the tester battery with
actionable feedback for the repair loop. Method-aware since the editable-table
feature: a GET route no longer satisfies a POST call.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# @app.get("/api/...") or @router.post('/api/...')
_BACKEND_ROUTE = re.compile(r"@\w+\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]")
# fetch("/api/...") and fetch(`/api/.../${id}`, { method: "POST", ... }).
_FRONTEND_CALL = re.compile(r"fetch\(\s*[`'\"](\/api\/[A-Za-z0-9_\-./${}]*)[`'\"]\s*\)")
_FRONTEND_METHOD_CALL = re.compile(
    r"fetch\(\s*[`'\"](\/api\/[A-Za-z0-9_\-./${}]*)[`'\"]\s*,\s*\{(?P<options>[^}]*)\}",
    re.DOTALL,
)
_METHOD_IN_OPTIONS = re.compile(r"method:\s*['\"](\w+)['\"]")

# The spec the platform writes; the kit's runtime reads come from here.
_SPEC_PATH = Path("src") / "dashboard.config.json"

_PARAMS = re.compile(r"\$\{[^}]+\}")
_ROUTE_PARAM = re.compile(r"\{[^}]+\}")


def _normalize(path: str) -> str:
    # ${itemId} (frontend template literal) and {item_id} (FastAPI route)
    # both collapse to {param} so path shapes compare equal.
    path = _ROUTE_PARAM.sub("{param}", _PARAMS.sub("{param}", path))
    return path.rstrip("/") or "/"


def _spec_calls(spec: dict[str, Any]) -> set[tuple[str, str]]:
    """(METHOD, path) pairs the dashboard itself must be able to call."""
    calls: set[tuple[str, str]] = set()
    widgets = spec.get("widgets")
    if not isinstance(widgets, list):
        return calls
    for widget in widgets:
        if not isinstance(widget, dict):
            continue
        endpoint = widget.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint.startswith("/api"):
            continue
        calls.add(("GET", _normalize(endpoint)))
        if widget.get("kind") == "table" and widget.get("editable"):
            base = _normalize(endpoint)
            calls.add(("POST", base))
            calls.add(("PUT", f"{base}/{{param}}"))
            calls.add(("DELETE", f"{base}/{{param}}"))
    return calls


# Run in a child process from the generated backend's directory: imports main,
# runs its startup (where some apps include their routers), and prints the
# routes FastAPI actually serves. A missing third-party module is reported
# apart from every other error, which is a genuinely broken backend.
_ROUTE_PROBE = """
import json, sys, traceback
sys.path.insert(0, ".")
try:
    import main
    app = main.app
    try:
        from fastapi.testclient import TestClient
        with TestClient(app):
            pass
    except ModuleNotFoundError as exc:
        if exc.name not in ("httpx", "fastapi"):
            raise
    # The OpenAPI schema, not app.routes: newer FastAPI keeps include_router()
    # results as lazy wrappers in app.routes, while the schema is public API
    # and lists every served path and method. Plain routes are added for any
    # declared with include_in_schema=False.
    verbs = {"get", "post", "put", "patch", "delete"}
    routes = [
        [method.upper(), path]
        for path, operations in app.openapi().get("paths", {}).items()
        for method in operations
        if method in verbs
    ]
    routes += [
        [method, route.path]
        for route in app.routes
        if isinstance(getattr(route, "path", None), str)
        for method in (getattr(route, "methods", None) or ())
    ]
    print(json.dumps({"ok": True, "routes": routes}))
except ModuleNotFoundError as exc:
    print(json.dumps({"ok": False, "missingModule": exc.name, "error": str(exc)}))
except BaseException:
    detail = traceback.format_exc(limit=4)[-1500:]
    print(json.dumps({"ok": False, "missingModule": None, "error": detail}))
"""

PROBE_TIMEOUT_SECONDS = 30


def _mounted_routes(backend_dir: Path) -> tuple[set[tuple[str, str]] | None, str | None]:
    """Routes the app really serves, or (None, why) when they cannot be known.

    A static scan finds route decorators in source text, which is not the same
    thing: observed, a generated backend declared its table routes on an
    APIRouter mounted only from a module nothing imported, so the scan passed
    and the dashboard's table 404'd. Starting the app is the only way to see.

    Returns (routes, None) when the app started; (set(), why) when it is
    broken; (None, why) when a third-party module is missing here, which is
    not the generated code's fault, so the caller falls back to the scan.
    """
    if not (backend_dir / "main.py").is_file():
        return None, "backend/main.py missing"
    with tempfile.TemporaryDirectory() as scratch:
        # The app may create its database on import; keep that out of /data.
        env = {**os.environ, "POC_DB": str(Path(scratch) / "probe.db")}
        try:
            result = subprocess.run(
                [sys.executable, "-c", _ROUTE_PROBE],
                cwd=backend_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
                # The probe reports failures as JSON on stdout; exit code unused.
                check=False,
            )
        except subprocess.TimeoutExpired:
            return set(), f"the app did not finish starting within {PROBE_TIMEOUT_SECONDS}s"
    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    if not lines:
        return set(), f"the app could not be started:\n{result.stderr[-1500:]}"
    report = json.loads(lines[-1])
    if report.get("ok"):
        routes = {(method.upper(), _normalize(path)) for method, path in report["routes"]}
        return {(m, p) for m, p in routes if p.startswith("/api")}, None
    missing_module = report.get("missingModule")
    if missing_module and not (backend_dir / f"{missing_module}.py").exists():
        return None, f"third-party module {missing_module!r} not installed here"
    return set(), f"the app crashed while starting:\n{report.get('error', '')}"


def check_api_contract(source_dir: Path, *, probe: bool = True) -> dict[str, Any]:
    """Return a normalized battery step result for the frontend/backend contract.

    ``probe=False`` skips starting the app and uses the static scan alone; only
    unit tests of the scan's matching rules want that.
    """
    started = time.monotonic()
    backend_dir = source_dir / "backend"
    frontend_dir = source_dir / "frontend"

    mounted, probe_note = _mounted_routes(backend_dir) if probe else (None, "probe disabled")
    if mounted is not None and probe_note:
        # The app did not start, so every call would fail. Say why first, so
        # the repair loop fixes the crash rather than chasing routes.
        return {
            "command": "api-contract-check",
            "exitCode": 1,
            "stdout": f"BACKEND DOES NOT START: {probe_note}",
            "stderr": "",
            "durationMs": int((time.monotonic() - started) * 1000),
        }

    provided: set[tuple[str, str]] = set()
    for py_file in [] if mounted is not None else backend_dir.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for method, route in _BACKEND_ROUTE.findall(text):
            if route.startswith("/api"):
                provided.add((method.upper(), _normalize(route)))
    if mounted is not None:
        provided = mounted

    required: set[tuple[str, str]] = set()
    for ext in ("*.ts", "*.tsx"):
        for src_file in frontend_dir.rglob(ext):
            try:
                text = src_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for call in _FRONTEND_CALL.findall(text):
                required.add(("GET", _normalize(call)))
            for path, options in _FRONTEND_METHOD_CALL.findall(text):
                method = _METHOD_IN_OPTIONS.search(options)
                required.add(((method.group(1).upper() if method else "GET"), _normalize(path)))

    spec_file = frontend_dir / _SPEC_PATH
    spec_calls: set[tuple[str, str]] = set()
    if spec_file.exists():
        try:
            spec = json.loads(spec_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            spec = None
        if isinstance(spec, dict):
            spec_calls = _spec_calls(spec)
            required |= spec_calls

    missing = sorted(required - provided, key=lambda pair: (pair[1], pair[0]))
    mutating = sum(1 for method, _ in required if method != "GET")
    lines = [
        f"frontend api calls: {len(required) - len(spec_calls)}",
        f"dashboard spec calls: {len(spec_calls)} ({mutating} mutating)",
        f"backend /api routes: {len(provided)}"
        + (" (served by the app)" if mounted is not None else f" (static scan: {probe_note})"),
    ]
    if missing:
        lines.append("MISSING IN BACKEND:")
        lines.extend(f"  - {method} {path}" for method, path in missing)
        summary = "\n".join(lines)
        exit_code = 1
    else:
        lines.append("contract OK: every required call has a backend route")
        summary = "\n".join(lines)
        exit_code = 0
    return {
        "command": "api-contract-check",
        "exitCode": exit_code,
        "stdout": summary,
        "stderr": "",
        "durationMs": int((time.monotonic() - started) * 1000),
    }
