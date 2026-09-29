"""Build/test runner battery (Backend Plan §10).

The tester must validate more than compileall: pytest on the generated backend
and an opt-in npm install/build on the generated frontend, each captured as a
normalized command result and aggregated into ordered step records.
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

from app.agents.stubs import StubDeveloperAgent, StubTesterAgent
from app.config import TEMPLATES_DIR
from app.generation import runner
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import empty_requirements
from app.workspace import workspace as ws

STEP_KEYS = {"step", "status", "reason", "category", "result"}


@pytest.fixture()
def template_source(tmp_path: Path) -> Path:
    destination = tmp_path / "source"
    shutil.copytree(Path(TEMPLATES_DIR) / "default-poc", destination)
    return destination


@pytest.fixture()
async def prepared_workspace(db) -> str:
    """A project with the template copied, as the generation service would leave it."""
    project_id = await ProjectRepository(db).create("T", "T", empty_requirements("p"), 14)
    ws.copy_template(project_id)
    return project_id


async def test_run_command_captures_all_fields():
    result = await runner.run_command([sys.executable, "-c", "print('out-line')"], cwd=".")
    assert result["exitCode"] == 0
    assert "out-line" in result["stdout"]
    assert " -c " in result["command"]
    assert result["durationMs"] >= 0
    assert result["stderr"] == ""


async def test_run_command_reports_failure():
    result = await runner.run_command([sys.executable, "-c", "raise SystemExit(3)"], cwd=".")
    assert result["exitCode"] == 3


async def test_pytest_backend_passes_on_fresh_template(template_source: Path):
    result = await runner.pytest_backend(str(template_source / "backend"))
    assert result["exitCode"] == 0, result
    assert "1 passed" in result["stdout"]


async def test_pytest_backend_fails_on_failing_test(template_source: Path):
    broken = template_source / "backend" / "tests" / "test_broken.py"
    broken.write_text("def test_broken():\n    assert False\n", encoding="utf-8")
    result = await runner.pytest_backend(str(template_source / "backend"))
    assert result["exitCode"] != 0
    assert "1 failed" in result["stdout"]


async def test_battery_default_runs_compile_and_records_skips(template_source: Path):
    steps = await runner.run_test_battery(str(template_source))
    by_step = {step["step"]: step for step in steps}
    assert by_step["compile"]["status"] == "PASSED"
    assert by_step["pytest"]["status"] in {"PASSED", "SKIPPED"}
    assert by_step["pipInstall"]["status"] == "SKIPPED"
    assert by_step["npmInstall"]["status"] == "SKIPPED"
    assert by_step["npmBuild"]["status"] == "SKIPPED"
    assert all(set(step) == STEP_KEYS for step in steps)
    assert all(step["reason"] for step in steps if step["status"] == "SKIPPED")


async def test_battery_stops_after_compile_failure(template_source: Path):
    (template_source / "backend" / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    steps = await runner.run_test_battery(str(template_source))
    statuses = [(step["step"], step["status"]) for step in steps]
    assert ("compile", "FAILED") in statuses
    assert all(status == "SKIPPED" for name, status in statuses if name in {"pytest", "npmBuild"})


async def test_battery_records_tool_unavailable_when_npm_enabled(
    template_source: Path, monkeypatch
):
    monkeypatch.setattr(runner, "tool_available", lambda name: None)
    steps = await runner.run_test_battery(str(template_source), run_npm_build=True)
    failed = next(step for step in steps if step["status"] == "FAILED")
    assert failed["category"] == "TOOL_UNAVAILABLE"
    assert "npm" in failed["reason"]


async def test_battery_runs_npm_steps_when_enabled(template_source: Path, monkeypatch):
    async def fake_npm_install(frontend_dir: str):
        return {
            "command": "npm install",
            "exitCode": 0,
            "stdout": "",
            "stderr": "",
            "durationMs": 1,
        }

    async def fake_npm_build(frontend_dir: str):
        return {
            "command": "npm run build",
            "exitCode": 0,
            "stdout": "built",
            "stderr": "",
            "durationMs": 1,
        }

    monkeypatch.setattr(runner, "tool_available", lambda name: "npm")
    monkeypatch.setattr(runner, "npm_install", fake_npm_install)
    monkeypatch.setattr(runner, "npm_build", fake_npm_build)
    steps = await runner.run_test_battery(str(template_source), run_npm_build=True)
    by_step = {step["step"]: step for step in steps}
    assert by_step["npmInstall"]["status"] == "PASSED"
    assert by_step["npmBuild"]["status"] == "PASSED"


async def test_battery_npm_build_failure_maps_to_build_error(template_source: Path, monkeypatch):
    async def failing_npm_build(frontend_dir: str):
        return {
            "command": "npm run build",
            "exitCode": 1,
            "stdout": "",
            "stderr": "tsc error",
            "durationMs": 1,
        }

    monkeypatch.setattr(runner, "tool_available", lambda name: "npm")
    monkeypatch.setattr(runner, "npm_install", _fake_npm_install_ok)
    monkeypatch.setattr(runner, "npm_build", failing_npm_build)
    steps = await runner.run_test_battery(str(template_source), run_npm_build=True)
    failed = next(step for step in steps if step["status"] == "FAILED")
    assert failed["step"] == "npmBuild"
    assert failed["category"] == "BUILD_ERROR"
    assert "tsc error" in (failed["result"]["stderr"] or "")


async def _fake_npm_install_ok(frontend_dir: str):
    return {"command": "npm install", "exitCode": 0, "stdout": "", "stderr": "", "durationMs": 1}


async def test_tester_passes_with_command_reports(prepared_workspace: str):
    await StubDeveloperAgent().run(prepared_workspace, {}, {})
    result = await StubTesterAgent().run(prepared_workspace)
    assert result.status == "PASSED"
    assert "compiles" in result.summary
    statuses = {step["step"]: step["status"] for step in result.commands}
    assert statuses["compile"] == "PASSED"
    assert statuses["npmInstall"] == "SKIPPED"


async def test_tester_maps_compile_error(prepared_workspace: str):
    await StubDeveloperAgent().run(prepared_workspace, {}, {})
    ws.write_file(prepared_workspace, "backend/broken.py", "def oops(:\n")
    result = await StubTesterAgent().run(prepared_workspace)
    assert result.status == "FAILED"
    assert result.category == "COMPILE_ERROR"
    assert any(step["step"] == "compile" and step["status"] == "FAILED" for step in result.commands)


async def test_tester_maps_pytest_failure(prepared_workspace: str):
    await StubDeveloperAgent().run(prepared_workspace, {}, {})
    ws.write_file(
        prepared_workspace,
        "backend/tests/test_broken.py",
        "def test_broken():\n    assert False\n",
    )
    result = await StubTesterAgent().run(prepared_workspace)
    assert result.status == "FAILED"
    assert result.category == "TEST_FAILURE"
    assert "failed" in result.summary


async def test_tester_default_battery_never_invokes_npm(prepared_workspace: str, monkeypatch):
    """Hermetic default: with npm disabled the tester must not invoke npm at all."""

    async def explode(*args, **kwargs):
        raise AssertionError("npm must not run while TESTER_RUN_NPM_BUILD is false")

    monkeypatch.setattr(runner, "npm_install", explode)
    monkeypatch.setattr(runner, "npm_build", explode)
    await StubDeveloperAgent().run(prepared_workspace, {}, {})
    result = await StubTesterAgent().run(prepared_workspace)
    assert result.status == "PASSED"
    assert all(step["status"] != "FAILED" for step in result.commands)


def test_pipeline_test_result_artifact_includes_command_reports(client, project_id):
    from tests.conftest import answer_all_questions

    answer_all_questions(client, project_id)
    assert client.post(f"/api/projects/{project_id}/requirements/finalize").status_code == 200
    assert client.post(f"/api/projects/{project_id}/generate").status_code == 202
    assert client.get(f"/api/projects/{project_id}/status").json()["status"] == "READY"

    artifacts = client.get(f"/api/projects/{project_id}/artifacts").json()
    artifact = next(a for a in artifacts if a["type"] == "TEST_RESULT")
    payload = json.loads(artifact["content"])
    assert payload["status"] == "PASSED"
    steps = {step["step"]: step["status"] for step in payload["commands"]}
    assert steps["compile"] == "PASSED"
    assert steps["pipInstall"] == "SKIPPED"
    assert steps["npmBuild"] == "SKIPPED"
