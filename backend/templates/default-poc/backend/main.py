"""Default PoC template backend. The Developer Agent replaces these endpoints.

The two /api routes below match frontend/src/dashboard.config.json, so the
template renders a working dashboard before any generation happens. The
generator overwrites both this file and the spec together, keeping them in
step — app/generation/contract.py fails the run if they drift.
"""

from fastapi import FastAPI

app = FastAPI(title="Generated PoC")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metrics")
async def metrics() -> dict[str, object]:
    return {"total": 1280, "change": 4.2, "trend": [980, 1020, 1105, 1090, 1180, 1280]}


@app.get("/api/series")
async def series() -> list[dict[str, object]]:
    return [
        {"label": "Mon", "value": 180},
        {"label": "Tue", "value": 205},
        {"label": "Wed", "value": 246},
        {"label": "Thu", "value": 231},
        {"label": "Fri", "value": 268},
        {"label": "Sat", "value": 150},
    ]
