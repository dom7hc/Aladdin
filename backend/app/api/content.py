"""Editable site content: business cases and home page texts.

Reads are public: the home page needs them. Writes need the shared admin key in
the X-Admin-Key header (config.ADMIN_KEY), because the site has no accounts and
is reachable by anyone with the URL.
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import config
from app.repositories.content_repository import (
    ContentRepository,
    ScenarioNotFoundError,
    to_response,
)
from app.schemas.content import HomeContent, ScenarioInput, ScenarioOrder, ScenarioResponse

router = APIRouter(prefix="/api/content", tags=["content"])


def get_repository(request: Request) -> ContentRepository:
    db: AsyncIOMotorDatabase = request.app.state.db
    return ContentRepository(db)


Repository = Annotated[ContentRepository, Depends(get_repository)]


def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    if not config.ADMIN_KEY:
        raise HTTPException(
            status_code=403,
            detail="Content editing is switched off: the server has no ADMIN_KEY set.",
        )
    # Constant-time compare: the key is the only thing guarding the page.
    if not x_admin_key or not hmac.compare_digest(x_admin_key, config.ADMIN_KEY):
        raise HTTPException(status_code=401, detail="Wrong or missing admin key.")


Admin = Depends(require_admin)


def _not_found(error: ScenarioNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Business case not found: {error}")


# --- Business cases ---------------------------------------------------------


@router.get("/scenarios", response_model=list[ScenarioResponse], response_model_by_alias=True)
async def list_scenarios(repo: Repository, all: bool = False) -> list[dict]:
    """Enabled cases in display order; ?all=true adds hidden ones for the editor."""
    docs = await repo.list_scenarios(include_hidden=all)
    return [to_response(doc) for doc in docs]


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    response_model_by_alias=True,
    status_code=201,
    dependencies=[Admin],
)
async def create_scenario(payload: ScenarioInput, repo: Repository) -> dict:
    doc = await repo.create(payload)
    await repo.refresh_catalogue()
    return to_response(doc)


@router.put(
    "/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
    response_model_by_alias=True,
    dependencies=[Admin],
)
async def update_scenario(scenario_id: str, payload: ScenarioInput, repo: Repository) -> dict:
    try:
        doc = await repo.update(scenario_id, payload)
    except ScenarioNotFoundError as error:
        raise _not_found(error) from error
    await repo.refresh_catalogue()
    return to_response(doc)


@router.delete("/scenarios/{scenario_id}", status_code=204, dependencies=[Admin])
async def delete_scenario(scenario_id: str, repo: Repository) -> Response:
    try:
        await repo.delete(scenario_id)
    except ScenarioNotFoundError as error:
        raise _not_found(error) from error
    await repo.refresh_catalogue()
    return Response(status_code=204)


@router.put(
    "/scenario-order",
    response_model=list[ScenarioResponse],
    response_model_by_alias=True,
    dependencies=[Admin],
)
async def reorder_scenarios(payload: ScenarioOrder, repo: Repository) -> list[dict]:
    try:
        await repo.reorder(payload.ids)
    except ScenarioNotFoundError as error:
        raise _not_found(error) from error
    await repo.refresh_catalogue()
    return [to_response(doc) for doc in await repo.list_scenarios(include_hidden=True)]


@router.post(
    "/scenarios/reset",
    response_model=list[ScenarioResponse],
    response_model_by_alias=True,
    dependencies=[Admin],
)
async def reset_scenarios(repo: Repository) -> list[dict]:
    await repo.reset_scenarios()
    await repo.refresh_catalogue()
    return [to_response(doc) for doc in await repo.list_scenarios(include_hidden=True)]


# --- Home page texts --------------------------------------------------------


@router.get("/home", response_model=HomeContent, response_model_by_alias=True)
async def get_home(repo: Repository) -> dict:
    return await repo.get_home()


@router.put("/home", response_model=HomeContent, response_model_by_alias=True, dependencies=[Admin])
async def save_home(payload: HomeContent, repo: Repository) -> dict:
    return await repo.save_home(payload.model_dump())


@router.delete(
    "/home", response_model=HomeContent, response_model_by_alias=True, dependencies=[Admin]
)
async def reset_home(repo: Repository) -> dict:
    return await repo.reset_home()
