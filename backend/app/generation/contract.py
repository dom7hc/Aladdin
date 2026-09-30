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
import re
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


def check_api_contract(source_dir: Path) -> dict[str, Any]:
    """Return a normalized battery step result for the frontend/backend contract."""
    started = time.monotonic()
    backend_dir = source_dir / "backend"
    frontend_dir = source_dir / "frontend"

    provided: set[tuple[str, str]] = set()
    for py_file in backend_dir.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for method, route in _BACKEND_ROUTE.findall(text):
            if route.startswith("/api"):
                provided.add((method.upper(), _normalize(route)))

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
        f"backend /api routes: {len(provided)}",
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
