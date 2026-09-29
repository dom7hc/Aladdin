"""Preview lifecycle: build + run a generated PoC as a local Docker stack.

State is persisted on the project document (`preview: {...}`) so the UI can
poll `GET /api/projects/{id}/preview` while the build runs in the background,
mirroring the generation flow.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app import config
from app.preview import builder
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import utcnow

logger = logging.getLogger(__name__)


class PreviewNotReadyError(Exception):
    """The project cannot start a preview right now."""


def _default_state() -> dict[str, Any]:
    return {
        "status": "none",
        "slot": None,
        "port": None,
        "url": None,
        "message": None,
        "updatedAt": None,
        "expiresAt": None,
    }


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
        # Reject before spending minutes on a build that has nowhere to land.
        if len(await self._occupied_slots()) >= config.PREVIEW_SLOTS:
            raise PreviewNotReadyError(
                f"All {config.PREVIEW_SLOTS} preview slots are in use; "
                "stop a running preview and try again"
            )
        return await self._save_state(project_id, status="building")

    async def _occupied_slots(self) -> set[int]:
        """Slots held by previews that are currently running or building."""
        cursor = self.repo.collection.find(
            {"preview.status": {"$in": ["running", "building"]}, "preview.slot": {"$ne": None}},
            {"preview.slot": 1},
        )
        return {doc["preview"]["slot"] async for doc in cursor}

    async def run_build(self, project_id: str) -> None:
        """Background task: build, start and health-check the preview stack."""
        try:
            occupied = await self._occupied_slots()
            slot = await builder.build_and_start(project_id, occupied)
        except (builder.PreviewError, OSError) as exc:
            logger.warning("Preview build failed for %s: %s", project_id, exc)
            await self._save_state(project_id, status="failed", message=str(exc)[:1500])
            return
        expires = utcnow() + timedelta(seconds=config.PREVIEW_TTL_SECONDS)
        await self._save_state(
            project_id,
            status="running",
            slot=slot,
            port=builder.slot_port(slot),
            url=builder.public_url(slot),
            message="PoC preview is live",
            expiresAt=expires.isoformat(),
        )

    async def reap_expired(self) -> int:
        """Stop previews past their TTL. Returns how many were stopped.

        Previews are ephemeral; without this they accumulate until the VM
        fills and deployments start failing.
        """
        now = utcnow()
        cursor = self.repo.collection.find(
            {"preview.status": "running", "preview.expiresAt": {"$ne": None}},
            {"preview.expiresAt": 1},
        )
        expired: list[str] = []
        async for doc in cursor:
            raw = doc["preview"]["expiresAt"]
            try:
                if datetime.fromisoformat(raw) <= now:
                    expired.append(str(doc["_id"]))
            except (TypeError, ValueError):
                logger.warning("Unparseable preview expiresAt on %s: %r", doc["_id"], raw)

        for project_id in expired:
            try:
                await self.stop(project_id)
                logger.info("Reaped expired preview for %s", project_id)
            except Exception:
                logger.exception("Could not reap preview for %s", project_id)
        return len(expired)

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
