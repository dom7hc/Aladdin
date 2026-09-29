"""Project use-cases: create, chat, finalize, status, artifacts, source export."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.base import RequirementAgent
from app.agents.stubs import QUESTION_PER_FIELD
from app.generation import renderer
from app.repositories.message_repository import MessageRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import (
    ChatMessageResponse,
    ChatResponse,
    ProjectResponse,
    RequirementStateResponse,
    completion_of,
    dumps_json,
    missing_fields,
)
from app.services.generation_service import completion_from_steps
from app.workspace import workspace as ws


class InvalidTransitionError(Exception):
    """409: operation not allowed in the project's current state."""


class ProjectService:
    def __init__(self, db: AsyncIOMotorDatabase, requirement_agent: RequirementAgent) -> None:
        self.repo = ProjectRepository(db)
        self.messages = MessageRepository(db)
        self.requirement_agent = requirement_agent

    async def create(self, idea: str) -> ProjectResponse:
        requirements = {"problem": idea.strip()}
        # The idea is the initial problem statement; first chat question targets the next field.
        requirements.update(
            {
                f: []
                for f in [
                    "targetUsers",
                    "mainWorkflow",
                    "features",
                    "inputs",
                    "outputs",
                    "constraints",
                    "successCriteria",
                ]
            }
        )
        name = idea.strip()[:60]
        project_id = await self.repo.create(
            name, idea.strip(), requirements, completion_of(requirements)
        )
        await self.messages.insert(project_id, "assistant", QUESTION_PER_FIELD["targetUsers"])
        return await self.get(project_id)

    async def get(self, project_id: str) -> ProjectResponse:
        project = await self.repo.get_or_raise(project_id)
        return ProjectResponse.model_validate(ProjectRepository.serialize(project))

    async def list_projects(self, limit: int = 20) -> list[ProjectResponse]:
        projects = await self.repo.list_recent(limit)
        return [
            ProjectResponse.model_validate(ProjectRepository.serialize(project))
            for project in projects
        ]

    async def chat(self, project_id: str, message: str) -> ChatResponse:
        project = await self.repo.get_or_raise(project_id)
        if project["status"] != "REQUIREMENT_COLLECTION":
            raise InvalidTransitionError("Requirements are already finalized for this project.")
        content: dict[str, Any] = project["requirements"]["content"]

        await self.messages.insert(project_id, "user", message)
        recent = await self.messages.recent(project_id)
        turn = await self.requirement_agent.run(content, recent[:-1], message)
        await self.repo.update_requirements(project_id, turn.requirements, turn.completion)
        await self.messages.insert(project_id, "assistant", turn.assistant_message)
        return ChatResponse(
            message=turn.assistant_message,
            requirements=turn.requirements,
            completion=turn.completion,
            missing_fields=turn.missing_fields,
            ready=turn.ready,
        )

    async def chat_history(self, project_id: str) -> list[ChatMessageResponse]:
        await self.repo.get_or_raise(project_id)
        docs = await self.messages.history(project_id)
        return [
            ChatMessageResponse(
                id=str(doc["_id"]),
                project_id=doc["project_id"],
                role=doc["role"],
                content=doc["content"],
                created_at=doc["created_at"],
            )
            for doc in docs
        ]

    async def requirements(self, project_id: str) -> RequirementStateResponse:
        project = await self.repo.get_or_raise(project_id)
        content = project["requirements"]["content"]
        missing = missing_fields(content)
        return RequirementStateResponse(
            requirements=content,
            completion=completion_of(content),
            missing_fields=missing,
            ready=not missing,
        )

    async def finalize(self, project_id: str) -> dict[str, Any]:
        project = await self.repo.get_or_raise(project_id)
        if project["status"] != "REQUIREMENT_COLLECTION":
            raise InvalidTransitionError("Requirements can only be finalized once.")
        content = project["requirements"]["content"]
        missing = missing_fields(content)
        if missing:
            raise InvalidTransitionError(f"Requirements incomplete, missing: {', '.join(missing)}")

        md = renderer.render_requirements_md(project["name"], content)
        await self.repo.push_artifact(project_id, "REQUIREMENTS_JSON", dumps_json(content))
        await self.repo.push_artifact(project_id, "REQUIREMENTS_MD", md)
        steps = {**project["steps"], "requirements": "COMPLETED"}
        await self.repo.update_fields(project_id, {"status": "REQUIREMENT_READY", "steps": steps})
        return {"status": "REQUIREMENT_READY", "artifactCount": 2}

    async def status(self, project_id: str) -> dict[str, Any]:
        project = await self.repo.get_or_raise(project_id)
        steps: dict[str, str] = project["steps"]
        if project["status"] == "READY":
            completion = 100
        elif project["status"] == "REQUIREMENT_COLLECTION":
            completion = project["completion"]
        else:
            completion = completion_from_steps(steps)
        return {
            "status": project["status"],
            "currentStep": project.get("current_step"),
            "completion": completion,
            "steps": steps,
            "message": project.get("error"),
        }

    async def reset_for_retry(self, project_id: str) -> None:
        """Clear a failed run so the pipeline can start again from scratch."""
        project = await self.repo.get_or_raise(project_id)
        steps = {key: "PENDING" for key in project["steps"]}
        await self.repo.update_fields(
            project_id,
            {
                "status": "REQUIREMENT_READY",
                "current_step": None,
                "completion": 100,
                "steps": steps,
                "repair_attempts": 0,
                "error": None,
            },
        )

    async def artifacts(self, project_id: str) -> list[dict[str, Any]]:
        project = await self.repo.get_or_raise(project_id)
        return [
            {
                "type": artifact["type"],
                "version": artifact["version"],
                "created_at": artifact["created_at"],
                "content": artifact["content"],
            }
            for artifact in project.get("artifacts", [])
        ]

    async def source_zip(self, project_id: str) -> bytes:
        await self.repo.get_or_raise(project_id)
        try:
            return ws.zip_source(project_id)
        except FileNotFoundError as exc:
            raise InvalidTransitionError("Source is not generated yet.") from exc
