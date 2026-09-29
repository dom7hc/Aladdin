"""MongoDB access for the projects collection (embedded requirements + artifacts)."""

from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.project import utcnow


class ProjectNotFoundError(Exception):
    pass


class ProjectRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["projects"]

    @staticmethod
    def parse_id(project_id: str) -> ObjectId:
        try:
            return ObjectId(project_id)
        except (InvalidId, TypeError) as exc:
            raise ProjectNotFoundError(project_id) from exc

    async def create(
        self, name: str, description: str, requirements: dict[str, Any], completion: int
    ) -> str:
        now = utcnow()
        doc = {
            "name": name,
            "description": description,
            "status": "REQUIREMENT_COLLECTION",
            "current_step": None,
            "completion": completion,
            "requirements": {"content": requirements, "completion": completion, "updated_at": now},
            "artifacts": [],
            "steps": {
                "requirements": "PENDING",
                "architect": "PENDING",
                "developer": "PENDING",
                "reviewer": "PENDING",
                "tester": "PENDING",
            },
            "repair_attempts": 0,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def get(self, project_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": self.parse_id(project_id)})

    async def get_or_raise(self, project_id: str) -> dict[str, Any]:
        project = await self.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    async def update_fields(self, project_id: str, fields: dict[str, Any]) -> None:
        fields = {**fields, "updated_at": utcnow()}
        await self.collection.update_one({"_id": self.parse_id(project_id)}, {"$set": fields})

    async def update_requirements(
        self, project_id: str, content: dict[str, Any], completion: int
    ) -> None:
        await self.update_fields(
            project_id,
            {
                "requirements": {
                    "content": content,
                    "completion": completion,
                    "updated_at": utcnow(),
                },
                "completion": completion,
            },
        )

    async def push_artifact(self, project_id: str, artifact_type: str, content: str) -> int:
        project = await self.get_or_raise(project_id)
        version = sum(1 for a in project.get("artifacts", []) if a["type"] == artifact_type) + 1
        artifact = {
            "type": artifact_type,
            "content": content,
            "version": version,
            "created_at": utcnow(),
        }
        await self.collection.update_one(
            {"_id": self.parse_id(project_id)},
            {"$push": {"artifacts": artifact}, "$set": {"updated_at": utcnow()}},
        )
        return version

    @staticmethod
    def serialize(project: dict[str, Any]) -> dict[str, Any]:
        """Mongo document -> API-shaped dict (id as string, datetimes ISO)."""
        return {
            "id": str(project["_id"]),
            "name": project["name"],
            "description": project["description"],
            "status": project["status"],
            "completion": project["completion"],
            "created_at": _iso(project["created_at"]),
            "updated_at": _iso(project["updated_at"]),
        }


def _iso(value: datetime | str) -> str:
    if isinstance(value, str):
        return value
    return value.isoformat()
