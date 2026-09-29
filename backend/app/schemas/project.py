"""Request/response schemas and the requirement domain model.

API JSON uses camelCase (frontend contract); Python uses snake_case.
"""

import json
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


NonEmptyText = Annotated[str, AfterValidator(_reject_blank)]

# Fixed field order drives the stub agent, completion score and missing-field report.
REQUIREMENT_FIELDS = [
    "problem",
    "targetUsers",
    "mainWorkflow",
    "features",
    "inputs",
    "outputs",
    "constraints",
    "successCriteria",
]

# Fields required before requirements are ready (constraints is optional).
REQUIRED_FIELDS = [f for f in REQUIREMENT_FIELDS if f != "constraints"]

LIST_FIELDS = {f for f in REQUIREMENT_FIELDS if f != "problem"}


def utcnow() -> datetime:
    return datetime.now(UTC)


def empty_requirements(problem: str = "") -> dict[str, Any]:
    return {
        "problem": problem,
        "targetUsers": [],
        "mainWorkflow": [],
        "features": [],
        "inputs": [],
        "outputs": [],
        "constraints": [],
        "successCriteria": [],
    }


def _filled(content: dict[str, Any], field: str) -> bool:
    value = content.get(field)
    if isinstance(value, list):
        return len(value) > 0
    return bool(value and str(value).strip())


def missing_fields(content: dict[str, Any]) -> list[str]:
    return [f for f in REQUIRED_FIELDS if not _filled(content, f)]


def completion_of(content: dict[str, Any]) -> int:
    filled = sum(1 for f in REQUIRED_FIELDS if _filled(content, f))
    return round(filled / len(REQUIRED_FIELDS) * 100)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ProjectCreate(BaseModel):
    idea: NonEmptyText = Field(max_length=4000)


class RequirementData(CamelModel):
    problem: str = ""
    target_users: list[str] = []
    main_workflow: list[str] = []
    features: list[str] = []
    inputs: list[str] = []
    outputs: list[str] = []
    constraints: list[str] = []
    success_criteria: list[str] = []

    @classmethod
    def from_doc(cls, content: dict[str, Any]) -> "RequirementData":
        return cls.model_validate(content)


class RequirementStateResponse(CamelModel):
    requirements: RequirementData
    completion: int
    missing_fields: list[str]
    ready: bool


class ChatRequest(BaseModel):
    message: NonEmptyText = Field(max_length=4000)


class ChatResponse(RequirementStateResponse):
    message: str


class ProjectResponse(CamelModel):
    id: str
    name: str
    description: str
    status: str
    completion: int
    created_at: datetime
    updated_at: datetime


class StatusResponse(CamelModel):
    status: str
    current_step: str | None
    completion: int
    steps: dict[str, str]


class FinalizeResponse(CamelModel):
    status: str
    artifact_count: int


class GenerateResponse(CamelModel):
    project_id: str
    status: str


class ArtifactResponse(CamelModel):
    type: str
    version: int
    created_at: datetime
    content: str | None = None


def dumps_json(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)
