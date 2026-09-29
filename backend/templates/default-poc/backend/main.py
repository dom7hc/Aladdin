"""Default PoC template backend. The Developer Agent fills/extends this code."""

from fastapi import FastAPI

app = FastAPI(title="Generated PoC")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
