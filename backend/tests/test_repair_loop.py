"""Repair loop: bounded retries, persisted attempt count, FAILED terminal state."""

import pytest

from app.agents.base import ReviewIssue, ReviewResult
from app.agents.stubs import (
    StubArchitectAgent,
    StubDeveloperAgent,
    StubReviewerAgent,
    StubTesterAgent,
)
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import empty_requirements
from app.services.generation_service import PocGenerationService

HIGH_ISSUE = [
    ReviewIssue(
        "REV-001", "HIGH", "backend/models/item.py", "Expected file missing.", "Regenerate it."
    )
]


class FlakyReviewer(StubReviewerAgent):
    """Fails the first review as if a generated file were missing, passes afterwards."""

    def __init__(self):
        self.calls = 0

    async def run(self, requirements, architecture, files):
        self.calls += 1
        if self.calls == 1:
            return ReviewResult(status="FAIL", issues=HIGH_ISSUE)
        return await super().run(requirements, architecture, files)


class AlwaysFailReviewer(StubReviewerAgent):
    async def run(self, requirements, architecture, files):
        return ReviewResult(status="FAIL", issues=HIGH_ISSUE)


@pytest.fixture()
async def project_id(db) -> str:
    repo = ProjectRepository(db)
    return await repo.create("T", "T", empty_requirements("p"), 14)


async def get_project(db, project_id: str) -> dict:
    return await ProjectRepository(db).get(project_id)


async def test_reviewer_repair_loop_recovers(db, project_id):
    service = PocGenerationService(
        db, StubArchitectAgent(), StubDeveloperAgent(), FlakyReviewer(), StubTesterAgent()
    )
    await service.generate(project_id)

    project = await get_project(db, project_id)
    assert project["status"] == "READY"
    assert project["repair_attempts"] == 1
    assert all(state == "COMPLETED" for state in project["steps"].values())


async def test_reviewer_max_attempts_marks_failed(db, project_id):
    service = PocGenerationService(
        db, StubArchitectAgent(), StubDeveloperAgent(), AlwaysFailReviewer(), StubTesterAgent()
    )
    await service.generate(project_id)

    project = await get_project(db, project_id)
    assert project["status"] == "FAILED"
    assert project["repair_attempts"] == 3
    assert "Review still failing" in project["error"]
    assert project["steps"]["reviewer"] == "FAILED"
