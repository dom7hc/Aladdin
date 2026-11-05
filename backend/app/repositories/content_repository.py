"""MongoDB access for editable site content.

`scenarios` holds the business cases, keyed by a readable slug as _id. It is
seeded once from the built-in set in app/catalogue.py; a marker document
records that, so deleting every case does not bring the built-ins back on the
next start. `site_content` holds the home page texts as one document.
"""

import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app import catalogue
from app.catalogue import SCENARIOS, Scenario
from app.schemas.content import HOME_DEFAULTS, ScenarioInput
from app.schemas.project import utcnow

_SEED_MARKER = "seed:scenarios"
_HOME_ID = "home"


class ScenarioNotFoundError(Exception):
    pass


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "case"


def _builtin_doc(scenario: Scenario, order: int) -> dict[str, Any]:
    now = utcnow()
    return {
        "_id": scenario.id,
        "title": scenario.title,
        "audience": scenario.audience,
        "problem": scenario.problem,
        "layout": scenario.layout,
        "highlights": list(scenario.highlights),
        "prompt": scenario.prompt,
        "enabled": True,
        "order": order,
        "builtin": True,
        "created_at": now,
        "updated_at": now,
    }


def to_response(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["_id"],
        "title": doc["title"],
        "audience": doc["audience"],
        "problem": doc["problem"],
        "layout": doc.get("layout", "kpi-overview"),
        "highlights": doc.get("highlights", []),
        "prompt": doc["prompt"],
        "enabled": doc.get("enabled", True),
        "order": doc.get("order", 0),
        "builtin": doc.get("builtin", False),
    }


def _to_scenario(doc: dict[str, Any]) -> Scenario:
    return Scenario(
        id=doc["_id"],
        title=doc["title"],
        audience=doc["audience"],
        problem=doc["problem"],
        layout=doc.get("layout", "kpi-overview"),
        highlights=tuple(doc.get("highlights", [])),
        prompt=doc["prompt"],
    )


class ContentRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.scenarios = db["scenarios"]
        self.site = db["site_content"]

    # --- Business cases ----------------------------------------------------

    async def ensure_seeded(self) -> None:
        if await self.site.find_one({"_id": _SEED_MARKER}):
            return
        for order, scenario in enumerate(SCENARIOS):
            # Upsert by id: two requests racing to seed write the same rows.
            await self.scenarios.replace_one(
                {"_id": scenario.id}, _builtin_doc(scenario, order), upsert=True
            )
        await self.site.replace_one(
            {"_id": _SEED_MARKER}, {"_id": _SEED_MARKER, "at": utcnow()}, upsert=True
        )

    async def list_scenarios(self, *, include_hidden: bool = False) -> list[dict[str, Any]]:
        await self.ensure_seeded()
        query = {} if include_hidden else {"enabled": True}
        docs = await self.scenarios.find(query).sort([("order", 1), ("title", 1)]).to_list(None)
        return docs

    async def refresh_catalogue(self) -> None:
        """Point the agents and the public list at what is stored now."""
        docs = await self.list_scenarios()
        catalogue.set_current([_to_scenario(doc) for doc in docs])

    async def create(self, data: ScenarioInput) -> dict[str, Any]:
        await self.ensure_seeded()
        base = _slug(data.title)
        scenario_id, suffix = base, 2
        while await self.scenarios.find_one({"_id": scenario_id}, {"_id": 1}):
            scenario_id, suffix = f"{base}-{suffix}", suffix + 1
        last = await self.scenarios.find_one({}, sort=[("order", -1)])
        now = utcnow()
        doc = {
            "_id": scenario_id,
            **data.model_dump(),
            "order": (last["order"] + 1) if last else 0,
            "builtin": False,
            "created_at": now,
            "updated_at": now,
        }
        await self.scenarios.insert_one(doc)
        return doc

    async def update(self, scenario_id: str, data: ScenarioInput) -> dict[str, Any]:
        await self.ensure_seeded()
        result = await self.scenarios.update_one(
            {"_id": scenario_id}, {"$set": {**data.model_dump(), "updated_at": utcnow()}}
        )
        if result.matched_count == 0:
            raise ScenarioNotFoundError(scenario_id)
        return await self.scenarios.find_one({"_id": scenario_id})

    async def delete(self, scenario_id: str) -> None:
        await self.ensure_seeded()
        result = await self.scenarios.delete_one({"_id": scenario_id})
        if result.deleted_count == 0:
            raise ScenarioNotFoundError(scenario_id)

    async def reorder(self, ids: list[str]) -> None:
        """Put the given cases first, in that order; any not named follow."""
        await self.ensure_seeded()
        existing = {doc["_id"] for doc in await self.scenarios.find({}, {"_id": 1}).to_list(None)}
        unknown = [i for i in ids if i not in existing]
        if unknown:
            raise ScenarioNotFoundError(", ".join(unknown))
        rest = [doc["_id"] for doc in await self.list_scenarios(include_hidden=True)]
        ordered = list(dict.fromkeys([*ids, *rest]))
        for order, scenario_id in enumerate(ordered):
            await self.scenarios.update_one({"_id": scenario_id}, {"$set": {"order": order}})

    async def reset_scenarios(self) -> None:
        """Back to the built-in set: every edit and added case is dropped."""
        await self.scenarios.delete_many({})
        await self.site.delete_one({"_id": _SEED_MARKER})
        await self.ensure_seeded()

    # --- Home page texts ---------------------------------------------------

    async def get_home(self) -> dict[str, str]:
        doc = await self.site.find_one({"_id": _HOME_ID}) or {}
        return {key: doc.get(key) or default for key, default in HOME_DEFAULTS.items()}

    async def save_home(self, values: dict[str, str]) -> dict[str, str]:
        # Blank means "use the default", so clearing a field is how to undo it.
        stored = {k: v.strip() for k, v in values.items() if k in HOME_DEFAULTS and v.strip()}
        await self.site.replace_one(
            {"_id": _HOME_ID}, {"_id": _HOME_ID, **stored, "updated_at": utcnow()}, upsert=True
        )
        return await self.get_home()

    async def reset_home(self) -> dict[str, str]:
        await self.site.delete_one({"_id": _HOME_ID})
        return await self.get_home()
