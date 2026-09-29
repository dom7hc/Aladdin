"""MongoDB access for the messages collection (append-only chat history)."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.project import utcnow


class MessageRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["messages"]

    async def insert(self, project_id: str, role: str, content: str) -> dict[str, Any]:
        doc = {"project_id": project_id, "role": role, "content": content, "created_at": utcnow()}
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def recent(self, project_id: str, limit: int = 20) -> list[dict[str, Any]]:
        cursor = self.collection.find({"project_id": project_id}).sort("_id", -1).limit(limit)
        return list(await cursor.to_list(length=limit))[::-1]

    async def history(self, project_id: str) -> list[dict[str, Any]]:
        """Full chat history in chronological order."""
        cursor = self.collection.find({"project_id": project_id}).sort("_id", 1)
        return list(await cursor.to_list(length=None))
