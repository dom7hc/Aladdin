"""API routes for projects (Backend Plan §6)."""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import config
from app.agents.base import (
    ArchitectAgent,
    DeveloperAgent,
    RequirementAgent,
    ReviewerAgent,
    TesterAgent,
)
from app.agents.llm import LlmRequirementAgent, build_llm_agents
from app.agents.stubs import (
    StubArchitectAgent,
    StubDeveloperAgent,
    StubRequirementAgent,
    StubReviewerAgent,
    StubTesterAgent,
)
from app.repositories.project_repository import ProjectNotFoundError
from app.schemas.project import (
    ArtifactResponse,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    FinalizeResponse,
    GenerateResponse,
    PreviewResponse,
    ProjectCreate,
    ProjectResponse,
    RequirementStateResponse,
    StatusResponse,
)
from app.services.generation_service import PocGenerationService
from app.services.preview_service import PreviewNotReadyError, PreviewService
from app.services.project_service import InvalidTransitionError, ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.db


def _requirement_agent() -> RequirementAgent:
    if config.LLM_ENABLED:
        return LlmRequirementAgent()
    return StubRequirementAgent()


def get_project_service(db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> ProjectService:
    return ProjectService(db, requirement_agent=_requirement_agent())


def get_generation_service(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> PocGenerationService:
    if config.LLM_ENABLED:
        architect, developer, reviewer, tester = build_llm_agents()
    else:
        architect: ArchitectAgent = StubArchitectAgent()
        developer: DeveloperAgent = StubDeveloperAgent()
        reviewer: ReviewerAgent = StubReviewerAgent()
        tester: TesterAgent = StubTesterAgent()
    return PocGenerationService(db, architect, developer, reviewer, tester)


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    payload: ProjectCreate,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    return await service.create(payload.idea)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> list[ProjectResponse]:
    return await service.list_projects()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    return await _guard(project_id, service.get(project_id))


@router.post("/{project_id}/chat", response_model=ChatResponse)
async def chat(
    project_id: str,
    payload: ChatRequest,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ChatResponse:
    return await _guard(project_id, service.chat(project_id, payload.message))


@router.get("/{project_id}/chat", response_model=list[ChatMessageResponse])
async def chat_history(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> list[ChatMessageResponse]:
    return await _guard(project_id, service.chat_history(project_id))


@router.get("/{project_id}/requirements", response_model=RequirementStateResponse)
async def get_requirements(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> RequirementStateResponse:
    return await _guard(project_id, service.requirements(project_id))


@router.post("/{project_id}/requirements/finalize", response_model=FinalizeResponse)
async def finalize_requirements(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> FinalizeResponse:
    result = await _guard(project_id, service.finalize(project_id))
    return FinalizeResponse(status=result["status"], artifact_count=result["artifactCount"])


@router.post("/{project_id}/generate", response_model=GenerateResponse, status_code=202)
async def generate(
    project_id: str,
    background: BackgroundTasks,
    service: Annotated[ProjectService, Depends(get_project_service)],
    generation: Annotated[PocGenerationService, Depends(get_generation_service)],
) -> GenerateResponse:
    project = await _guard(project_id, service.get(project_id))
    if project.status not in {"REQUIREMENT_READY", "FAILED"}:
        raise HTTPException(
            status_code=409,
            detail=(f"Project is {project.status}; generate requires REQUIREMENT_READY or FAILED."),
        )
    # The site is open, so refuse a burst rather than letting it exhaust the
    # VM and the LLM budget. Told plainly, since the user can simply retry.
    in_flight = await service.generations_in_flight()
    if in_flight >= config.MAX_CONCURRENT_GENERATIONS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"{in_flight} projects are generating right now, which is the limit. "
                "Try again in a minute."
            ),
        )
    if project.status == "FAILED":
        await _guard(project_id, service.reset_for_retry(project_id))
    background.add_task(generation.generate, project_id)
    return GenerateResponse(project_id=project_id, status="STARTED")


@router.get("/{project_id}/status", response_model=StatusResponse)
async def status(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> Any:
    return await _guard(project_id, service.status(project_id))


@router.get("/{project_id}/artifacts", response_model=list[ArtifactResponse])
async def artifacts(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> list[ArtifactResponse]:
    items = await _guard(project_id, service.artifacts(project_id))
    return [ArtifactResponse.model_validate(item) for item in items]


@router.get("/{project_id}/source")
async def source(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> Response:
    data = await _guard(project_id, service.source_zip(project_id))
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project_id}.zip"'},
    )


@router.get("/{project_id}/deck")
async def deck(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> Response:
    """A .pptx presenting the dashboard, for the user to show to their own team."""
    data = await _guard(project_id, service.deck_pptx(project_id))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{project_id}.pptx"'},
    )


def get_preview_service(db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> PreviewService:
    return PreviewService(db)


@router.post("/{project_id}/preview", response_model=PreviewResponse, status_code=202)
async def start_preview(
    project_id: str,
    background: BackgroundTasks,
    preview: Annotated[PreviewService, Depends(get_preview_service)],
) -> PreviewResponse:
    """Build the generated PoC into images and run it as a local Docker stack."""
    try:
        state = await preview.start(project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except PreviewNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    background.add_task(preview.run_build, project_id)
    return PreviewResponse.model_validate(state)


@router.get("/{project_id}/preview", response_model=PreviewResponse)
async def get_preview(
    project_id: str,
    preview: Annotated[PreviewService, Depends(get_preview_service)],
) -> PreviewResponse:
    try:
        state = await preview.get_state(project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    return PreviewResponse.model_validate(state)


@router.delete("/{project_id}/preview", response_model=PreviewResponse)
async def stop_preview(
    project_id: str,
    preview: Annotated[PreviewService, Depends(get_preview_service)],
) -> PreviewResponse:
    try:
        state = await preview.stop(project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    return PreviewResponse.model_validate(state)


async def _guard(project_id: str, awaitable: Any) -> Any:
    """Map domain errors to HTTP statuses in one place."""
    try:
        return await awaitable
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
