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

# Phrased for a dashboard, because that is the only thing this product builds.
# Asking "what should users be able to do?" invited answers about assistants and
# editors that we then could not build.
QUESTION_PER_FIELD = {
    "targetUsers": "Whose job should this dashboard make easier?",
    "mainWorkflow": "What do they do today to get this information?",
    "features": "What should the dashboard show them?",
    "inputs": "What data would it read — which records or fields?",
    "outputs": "Which figures and lists should appear on screen?",
    "successCriteria": "What decision should they be able to make at a glance?",
}

# Best-practice defaults for the "Autofill remaining" button. Aladdin renders a
# dashboard PoC, so the defaults describe the workflow every generated PoC
# supports; the LLM agent personalizes the same fields from the idea and falls
# back to these when the API is unavailable.
AUTOFILL_DEFAULTS = {
    "targetUsers": [
        "Team leads and managers",
        "Operations staff",
        "Business stakeholders",
    ],
    "mainWorkflow": [
        "Open the dashboard",
        "Filter and explore the latest data",
        "Act on the reported results",
    ],
    "features": [
        "KPI overview with charts",
        "Filterable record tables",
        "Realistic seeded sample data",
    ],
    "inputs": ["Records entered through forms", "Uploaded or imported data"],
    "outputs": [
        "Interactive dashboard with KPIs, trends and breakdowns",
        "Exportable reports",
    ],
    "successCriteria": [
        "The dashboard loads populated with sample data",
        "Every widget renders from a working API endpoint",
    ],
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
    "API_CONTRACT": "Implement every /api route the generated frontend calls in backend/main.py (or remove the calls).",
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

    async def autofill(
        self, requirements: dict[str, Any], chat: list[dict[str, Any]]
    ) -> RequirementTurn:
        content = {**requirements}
        for field, value in AUTOFILL_DEFAULTS.items():
            if field in missing_fields(content):
                content[field] = list(value)
        remaining = missing_fields(content)
        filled = len(AUTOFILL_DEFAULTS) - len([f for f in AUTOFILL_DEFAULTS if f in remaining])
        return RequirementTurn(
            assistant_message=(
                f"I filled {filled} remaining section(s) with Alladin best-practice "
                "defaults — review them in the summary and adjust anything you like."
                if not remaining
                else "I could not complete every section automatically; "
                + QUESTION_PER_FIELD.get(remaining[0], "")
            ),
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
