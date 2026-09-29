"""Preview lifecycle: build + run a generated PoC as a local Docker stack.

State is persisted on the project document (`preview: {...}`) so the UI can
poll `GET /api/projects/{id}/preview` while the build runs in the background,
mirroring the generation flow.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.preview import builder
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import utcnow

logger = logging.getLogger(__name__)


class PreviewNotReadyError(Exception):
    """The project cannot start a preview right now."""


def _default_state() -> dict[str, Any]:
    return {"status": "none", "port": None, "url": None, "message": None, "updatedAt": None}


class PreviewService:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.repo = ProjectRepository(db)

    async def _load(self, project_id: str) -> dict[str, Any]:
        return await self.repo.get_or_raise(project_id)

    async def _save_state(self, project_id: str, **fields: Any) -> dict[str, Any]:
        state = {**_default_state(), **fields, "updatedAt": utcnow().isoformat()}
        await self.repo.update_fields(project_id, {"preview": state})
        return state

    async def get_state(self, project_id: str) -> dict[str, Any]:
        project = await self._load(project_id)
        return project.get("preview") or _default_state()

    async def start(self, project_id: str) -> dict[str, Any]:
        """Validate and mark the preview as building (fast path, no Docker work)."""
        project = await self._load(project_id)
        if project.get("status") != "READY":
            raise PreviewNotReadyError(
                f"Project is {project.get('status')}; preview requires a READY project"
            )
        current = project.get("preview") or {}
        if current.get("status") == "building":
            raise PreviewNotReadyError("A preview build is already running")
        if not await asyncio.to_thread(builder.docker_available):
            raise PreviewNotReadyError(
                "Docker is not available to this backend; preview deployment "
                "needs a mounted Docker socket (supported on the local stack)"
            )
        return await self._save_state(project_id, status="building")

    async def _occupied_ports(self) -> set[int]:
        """Ports published by previews that are currently running."""
        cursor = self.repo.collection.find(
            {"preview.status": "running", "preview.port": {"$ne": None}},
            {"preview.port": 1},
        )
        return {doc["preview"]["port"] async for doc in cursor}

    async def run_build(self, project_id: str) -> None:
        """Background task: build, start and health-check the preview stack."""
        try:
            occupied = await self._occupied_ports()
            port = await builder.build_and_start(project_id, occupied)
        except (builder.PreviewError, OSError) as exc:
            logger.warning("Preview build failed for %s: %s", project_id, exc)
            await self._save_state(project_id, status="failed", message=str(exc)[:1500])
            return
        await self._save_state(
            project_id,
            status="running",
            port=port,
            url=f"http://localhost:{port}",
            message="PoC preview is live",
        )

    async def stop(self, project_id: str) -> dict[str, Any]:
        await self._load(project_id)
        from app.workspace import workspace as ws

        source_dir: Path = ws.source_dir(project_id)
        try:
            await asyncio.to_thread(builder.stack_down, project_id, source_dir)
        except builder.PreviewError as exc:
            logger.warning("Preview teardown issue for %s: %s", project_id, exc)
        return await self._save_state(
            project_id, status="none", port=None, url=None, message="Preview stopped"
        )
