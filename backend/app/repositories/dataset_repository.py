"""MongoDB access for uploaded datasets, one per project.

Kept out of the project document on purpose: up to MAX_ROWS rows would bloat
every project read, and the requirement chat rewrites the requirements, which
must never be able to drop the user's data. Keyed by the project id as _id, so
a re-upload replaces the previous file.
"""

from dataclasses import asdict
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.ingest.spreadsheet import Column, Dataset
from app.schemas.project import utcnow


class DatasetRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["datasets"]

    async def save(self, project_id: str, dataset: Dataset) -> None:
        doc = {
            "_id": project_id,
            "filename": dataset.filename,
            "columns": [asdict(column) for column in dataset.columns],
            "rows": dataset.rows,
            "row_count": dataset.row_count,
            "truncated": dataset.truncated,
            "notes": dataset.notes,
            "uploaded_at": utcnow(),
        }
        await self.collection.replace_one({"_id": project_id}, doc, upsert=True)

    async def get(self, project_id: str) -> Dataset | None:
        doc = await self.collection.find_one({"_id": project_id})
        return _to_dataset(doc) if doc else None

    async def delete(self, project_id: str) -> bool:
        result = await self.collection.delete_one({"_id": project_id})
        return result.deleted_count > 0


def _to_dataset(doc: dict[str, Any]) -> Dataset:
    return Dataset(
        filename=doc["filename"],
        columns=[Column(**column) for column in doc["columns"]],
        rows=doc["rows"],
        row_count=doc["row_count"],
        truncated=doc.get("truncated", False),
        notes=doc.get("notes", []),
    )
