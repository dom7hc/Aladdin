"""Deterministic API-contract check between the generated frontend and backend.

AI Developer Plan §8 functional check: "Are expected API routes available?".
The developer agent writes both sides in one shot, so nothing stops the model
from calling an endpoint it never implemented (observed: `POST /api/users`
against a backend without it). This checker scans the generated sources and
fails the tester battery when the frontend calls an /api path the backend
does not define, giving the repair loop actionable feedback.
"""

import re
from pathlib import Path
from typing import Any

# @app.get("/api/...") or @router.post('/api/...')
_BACKEND_ROUTE = re.compile(r"@\w+\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]")
# fetch("/api/..."), fetch(`/api/.../${id}`) and axios-style literals
_FRONTEND_CALL = re.compile(r"[`'\"](\/api\/[A-Za-z0-9_\-./${}]*)[`'\"]")

_PARAMS = re.compile(r"\$\{[^}]+\}")
_ROUTE_PARAM = re.compile(r"\{[^}]+\}")


def _normalize(path: str) -> str:
    # ${itemId} (frontend template literal) and {item_id} (FastAPI route)
    # both collapse to {param} so path shapes compare equal.
    path = _ROUTE_PARAM.sub("{param}", _PARAMS.sub("{param}", path))
    return path.rstrip("/") or "/"


def check_api_contract(source_dir: Path) -> dict[str, Any]:
    """Return a normalized battery step result for the frontend/backend contract."""
    import time

    started = time.monotonic()
    backend_dir = source_dir / "backend"
    frontend_dir = source_dir / "frontend"

    backend_routes: set[str] = set()
    for py_file in backend_dir.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for _, route in _BACKEND_ROUTE.findall(text):
            if route.startswith("/api"):
                backend_routes.add(_normalize(route))

    frontend_calls: set[str] = set()
    for ext in ("*.ts", "*.tsx"):
        for src_file in frontend_dir.rglob(ext):
            try:
                text = src_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for call in _FRONTEND_CALL.findall(text):
                frontend_calls.add(_normalize(call))

    missing = sorted(frontend_calls - backend_routes)
    lines = [
        f"frontend api calls: {len(frontend_calls)}",
        f"backend /api routes: {len(backend_routes)}",
    ]
    if missing:
        lines.append("MISSING IN BACKEND:")
        lines.extend(f"  - {call}" for call in missing)
        summary = "\n".join(lines)
        exit_code = 1
    else:
        lines.append("contract OK: every frontend /api call has a backend route")
        summary = "\n".join(lines)
        exit_code = 0
    return {
        "command": "api-contract-check",
        "exitCode": exit_code,
        "stdout": summary,
        "stderr": "",
        "durationMs": int((time.monotonic() - started) * 1000),
    }
