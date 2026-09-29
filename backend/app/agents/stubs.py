"""Deterministic placeholder agents.

They make the full pipeline runnable end-to-end without LLM keys, so the
backend contract, orchestration, repair loop and workspaces are testable.
Real agents (AI Developer Plan) drop in behind the same interfaces.
"""

from typing import Any

from app import config
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

SUGGESTED_FIX_BY_STEP = {
    "DEPENDENCY_INSTALL": "Re-run pip install for the generated backend and inspect requirements.txt.",
    "COMPILE_ERROR": "Fix Python syntax errors in generated backend.",
    "TEST_FAILURE": "Fix the failing tests in the generated backend.",
    "BUILD_ERROR": "Fix the frontend build errors reported by npm.",
    "TOOL_UNAVAILABLE": "Install the missing tool or disable the optional check.",
}


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
        steps = await runner.run_test_battery(
            str(ws.source_dir(project_id)),
            run_pip_install=config.TESTER_RUN_PIP_INSTALL,
            run_pytest=config.TESTER_RUN_PYTEST,
            run_npm_build=config.TESTER_RUN_NPM_BUILD,
        )
        return _test_result_from_steps(steps)


def _test_result_from_steps(steps: list[dict[str, Any]]) -> TestResult:
    failure = next((step for step in steps if step["status"] == "FAILED"), None)
    if failure is not None:
        result = failure.get("result") or {}
        detail = (
            result.get("stderr")
            or result.get("stdout")
            or failure.get("reason")
            or "build/test step failed"
        )
        category = failure["category"]
        return TestResult(
            status="FAILED",
            category=category,
            files=[],
            summary=detail[:2000],
            suggested_fix=SUGGESTED_FIX_BY_STEP[category],
            commands=steps,
        )
    passed = "Template files present, backend compiles"
    if any(step["step"] == "pytest" and step["status"] == "PASSED" for step in steps):
        passed += " and generated tests pass"
    return TestResult(
        status="PASSED", category=None, files=[], summary=passed + ".", commands=steps
    )
