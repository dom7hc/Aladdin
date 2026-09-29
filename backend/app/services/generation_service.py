"""Generation pipeline: Architect -> Developer -> Reviewer -> Tester.

Simple state machine per Backend Plan §8/§9, with a bounded repair loop
(MAX_REPAIR_ATTEMPTS) whose counter is persisted on the project document.
"""

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.base import ArchitectAgent, DeveloperAgent, ReviewerAgent, TesterAgent
from app.config import MAX_REPAIR_ATTEMPTS
from app.generation import renderer
from app.repositories.project_repository import ProjectNotFoundError, ProjectRepository
from app.schemas.project import dumps_json
from app.workspace import workspace as ws

logger = logging.getLogger(__name__)

STEP_KEYS = ["requirements", "architect", "developer", "reviewer", "tester"]


class PocGenerationService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        architect: ArchitectAgent,
        developer: DeveloperAgent,
        reviewer: ReviewerAgent,
        tester: TesterAgent,
    ) -> None:
        self.repo = ProjectRepository(db)
        self.architect = architect
        self.developer = developer
        self.reviewer = reviewer
        self.tester = tester

    async def generate(self, project_id: str) -> None:
        try:
            await self._run(project_id)
        except Exception as exc:
            logger.exception("Generation failed for project %s", project_id)
            await self._fail(project_id, str(exc))

    async def _run(self, project_id: str) -> None:
        project = await self.repo.get_or_raise(project_id)
        requirements: dict[str, Any] = project["requirements"]["content"]

        # Architect
        await self._transition(project_id, "architect", "ARCHITECTING")
        architecture = await self.architect.run(requirements)
        await self.repo.push_artifact(project_id, "ARCHITECTURE_JSON", dumps_json(architecture))
        await self.repo.push_artifact(
            project_id, "ARCHITECTURE_MD", renderer.render_architecture_md(architecture)
        )
        ws.workspace_dir(project_id).joinpath("architecture.md").write_text(
            renderer.render_architecture_md(architecture), encoding="utf-8"
        )
        await self._transition(project_id, "developer", "ARCHITECTURE_READY")

        # Developer + workspace
        ws.copy_template(project_id)
        ws.workspace_dir(project_id).joinpath("requirements.md").write_text(
            renderer.render_requirements_md(project["name"], requirements), encoding="utf-8"
        )
        await self._transition(project_id, "developer", "GENERATING")
        await self.developer.run(project_id, requirements, architecture)

        # Review loop
        await self._transition(project_id, "reviewer", "REVIEWING")
        review = await self._review_with_repair(project_id, requirements, architecture)
        if review.status != "PASS":
            await self._fail(
                project_id, f"Review still failing after {MAX_REPAIR_ATTEMPTS} repair attempts."
            )
            return
        await self.repo.push_artifact(
            project_id, "REVIEW_RESULT", dumps_json({"status": review.status, "issues": []})
        )

        # Test loop
        await self._transition(project_id, "tester", "TESTING")
        test = await self._test_with_repair(project_id, requirements, architecture)
        if test.status != "PASSED":
            await self._fail(
                project_id, f"Tests still failing after {MAX_REPAIR_ATTEMPTS} repair attempts."
            )
            return
        await self.repo.push_artifact(
            project_id, "TEST_RESULT", dumps_json({"status": test.status, "summary": test.summary})
        )

        await self._set_step(project_id, "tester", "COMPLETED")
        await self.repo.update_fields(
            project_id, {"status": "READY", "current_step": None, "completion": 100}
        )

    async def _review_with_repair(
        self, project_id: str, requirements: dict[str, Any], architecture: dict[str, Any]
    ):
        attempts = 0
        while True:
            files = ws.list_files(project_id)
            review = await self.reviewer.run(requirements, architecture, files)
            if review.status == "PASS":
                return review
            if attempts >= MAX_REPAIR_ATTEMPTS:
                return review
            attempts += 1
            await self.repo.update_fields(project_id, {"repair_attempts": attempts})
            feedback = [
                f"{issue.file}: {issue.problem} {issue.recommendation}" for issue in review.issues
            ]
            await self.developer.run(project_id, requirements, architecture, feedback)

    async def _test_with_repair(
        self, project_id: str, requirements: dict[str, Any], architecture: dict[str, Any]
    ):
        attempts = 0
        while True:
            test = await self.tester.run(project_id)
            if test.status == "PASSED":
                return test
            if attempts >= MAX_REPAIR_ATTEMPTS:
                return test
            attempts += 1
            await self.repo.update_fields(project_id, {"repair_attempts": attempts})
            feedback = [f"{test.category}: {test.summary} {test.suggested_fix or ''}".strip()]
            await self.developer.run(project_id, requirements, architecture, feedback)

    async def _transition(self, project_id: str, step: str, status: str) -> None:
        steps = {
            key: ("COMPLETED" if STEP_KEYS.index(key) < STEP_KEYS.index(step) else "PENDING")
            for key in STEP_KEYS
        }
        steps[step] = "RUNNING"
        await self.repo.update_fields(
            project_id, {"status": status, "current_step": step, "steps": steps}
        )

    async def _set_step(self, project_id: str, step: str, state: str) -> None:
        project = await self.repo.get_or_raise(project_id)
        steps = {**project["steps"], step: state}
        await self.repo.update_fields(project_id, {"steps": steps})

    async def _fail(self, project_id: str, error: str) -> None:
        project = await self.repo.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        steps = {**project["steps"]}
        current = project.get("current_step")
        if current in steps:
            steps[current] = "FAILED"
        await self.repo.update_fields(
            project_id, {"status": "FAILED", "steps": steps, "error": error[:2000]}
        )


def completion_from_steps(steps: dict[str, str]) -> int:
    completed = sum(1 for key in STEP_KEYS if steps.get(key) == "COMPLETED")
    return min(100, completed * 20)
