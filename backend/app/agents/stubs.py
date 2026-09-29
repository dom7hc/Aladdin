"""Deterministic placeholder agents.

They make the full pipeline runnable end-to-end without LLM keys, so the
backend contract, orchestration, repair loop and workspaces are testable.
Real agents (AI Developer Plan) drop in behind the same interfaces.
"""

from typing import Any

from app.agents.base import (
    ArchitectAgent,
    DeveloperAgent,
    RequirementAgent,
    RequirementTurn,
    ReviewerAgent,
    ReviewIssue,
    ReviewResult,
    TesterAgent,
    TestResult,
)
from app.generation import runner
from app.schemas.project import (
    LIST_FIELDS,
    completion_of,
    missing_fields,
)
from app.workspace import workspace as ws

QUESTION_PER_FIELD = {
    "targetUsers": "Who will mainly use this application?",
    "mainWorkflow": "What is the main workflow users follow?",
    "features": "What should users be able to do?",
    "inputs": "What inputs does the application receive?",
    "outputs": "What outputs should it produce?",
    "successCriteria": "What does success look like?",
}

# Fixed fill order: each user message fills the first missing required field.
FILL_ORDER = [f for f in QUESTION_PER_FIELD]

DEVELOPER_FILES = {
    "backend/models/item.py",
    "backend/services/item_service.py",
    "backend/api/items.py",
    "frontend/src/api/itemApi.ts",
}

REVIEW_PASS = ReviewResult(status="PASS", issues=[])


class StubRequirementAgent(RequirementAgent):
    async def run(
        self, requirements: dict[str, Any], chat: list[dict[str, Any]], message: str
    ) -> RequirementTurn:
        content = {**requirements}
        missing = missing_fields(content)
        value = message.strip()
        if missing and value:
            target = missing[0]
            content[target] = [value] if target in LIST_FIELDS else value
        remaining = missing_fields(content)
        if remaining:
            reply = QUESTION_PER_FIELD.get(remaining[0], f"Tell me more about: {remaining[0]}.")
        else:
            reply = "I have enough information to prepare the PoC specification."
        return RequirementTurn(
            assistant_message=reply,
            requirements=content,
            completion=completion_of(content),
            missing_fields=remaining,
            ready=not remaining,
        )


class StubArchitectAgent(ArchitectAgent):
    async def run(self, requirements: dict[str, Any]) -> dict[str, Any]:
        return {
            "pages": [{"name": "HomePage", "purpose": "Main page of the PoC"}],
            "apis": [{"method": "GET", "path": "/api/items"}],
            "entities": [{"name": "Item", "fields": ["id", "name"]}],
            "services": ["ItemService"],
            "aiCapabilities": [],
        }


class StubDeveloperAgent(DeveloperAgent):
    async def run(
        self,
        project_id: str,
        requirements: dict[str, Any],
        architecture: dict[str, Any],
        feedback: list[str] | None = None,
    ) -> list[str]:
        written = []
        for relative_path in sorted(DEVELOPER_FILES):
            content = f'"""Generated for project {project_id}."""\n'
            ws.write_file(project_id, relative_path, content)
            written.append(relative_path)
        return written


class StubReviewerAgent(ReviewerAgent):
    async def run(
        self, requirements: dict[str, Any], architecture: dict[str, Any], files: list[str]
    ) -> ReviewResult:
        missing = sorted(DEVELOPER_FILES - set(files))
        if missing:
            return ReviewResult(
                status="FAIL",
                issues=[
                    ReviewIssue(
                        id=f"REV-{i + 1:03d}",
                        severity="HIGH",
                        file=path,
                        problem="Expected generated file is missing.",
                        recommendation="Regenerate the file.",
                    )
                    for i, path in enumerate(missing)
                ],
            )
        return REVIEW_PASS


class StubTesterAgent(TesterAgent):
    async def run(self, project_id: str) -> TestResult:
        existing = set(ws.list_files(project_id))
        missing = sorted(DEVELOPER_FILES - existing)
        if missing:
            return TestResult(
                status="FAILED",
                category="MISSING_FILES",
                files=missing,
                summary=f"Missing generated files: {', '.join(missing)}",
                suggested_fix="Re-run the developer step.",
            )
        result = await runner.compile_python(str(ws.source_dir(project_id) / "backend"))
        if result["exitCode"] != 0:
            return TestResult(
                status="FAILED",
                category="COMPILE_ERROR",
                files=[],
                summary=result["stderr"] or "compileall failed",
                suggested_fix="Fix Python syntax errors in generated backend.",
            )
        return TestResult(
            status="PASSED",
            category=None,
            files=[],
            summary="Template files present and backend compiles.",
        )
