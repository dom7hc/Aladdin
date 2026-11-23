"""Full generation pipeline with stub agents: state machine, artifacts, workspace, ZIP."""

import importlib.util
import json

import pytest
from fastapi.testclient import TestClient

from app.agents.llm import LlmArchitectAgent, LlmDeveloperAgent, LlmTesterAgent
from app.agents.stubs import (
    DEVELOPER_FILES,
    REVIEW_PASS,
    StubArchitectAgent,
    StubDeveloperAgent,
    StubReviewerAgent,
    StubTesterAgent,
)
from app.catalogue import SCENARIOS
from app.generation.samples import sample_for
from app.generation.spec import spec_endpoints, validate_spec
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import empty_requirements
from app.services.generation_service import PocGenerationService
from app.workspace import workspace as ws
from tests.conftest import answer_all_questions


def run_pipeline(client, project_id) -> dict:
    answer_all_questions(client, project_id)
    finalized = client.post(f"/api/projects/{project_id}/requirements/finalize")
    assert finalized.status_code == 200
    started = client.post(f"/api/projects/{project_id}/generate")
    assert started.status_code == 202
    status = client.get(f"/api/projects/{project_id}/status").json()
    assert status["status"] == "READY", status
    return status


def test_generate_guard_requires_finalized(client, project_id):
    response = client.post(f"/api/projects/{project_id}/generate")
    assert response.status_code == 409


def test_full_pipeline_reaches_ready(client, project_id):
    status = run_pipeline(client, project_id)
    assert status["completion"] == 100
    assert status["currentStep"] is None
    assert all(state == "COMPLETED" for state in status["steps"].values())


def test_pipeline_persists_artifacts(client, project_id):
    run_pipeline(client, project_id)
    artifacts = client.get(f"/api/projects/{project_id}/artifacts").json()
    types = {a["type"] for a in artifacts}
    assert {
        "REQUIREMENTS_JSON",
        "REQUIREMENTS_MD",
        "ARCHITECTURE_JSON",
        "ARCHITECTURE_MD",
        "REVIEW_RESULT",
        "TEST_RESULT",
    } <= types
    requirements_md = next(a for a in artifacts if a["type"] == "REQUIREMENTS_MD")
    assert requirements_md["content"].startswith("# ")
    assert "## Problem" in requirements_md["content"]


def test_pipeline_generates_workspace_and_zip(client, project_id):
    run_pipeline(client, project_id)
    response = client.get(f"/api/projects/{project_id}/source")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content[:2] == b"PK"  # valid ZIP magic
    assert b"item.py" in response.content  # developer stub output included


def test_source_before_generation_is_conflict(client, project_id):
    response = client.get(f"/api/projects/{project_id}/source")
    assert response.status_code == 409


def _read_endpoints(project_id, spec):
    source = ws.source_dir(project_id) / "backend/main.py"
    module_spec = importlib.util.spec_from_file_location(f"poc_{project_id}", source)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    with TestClient(module.app) as generated:
        result = {}
        for path in spec_endpoints(spec):
            response = generated.get(path)
            assert response.status_code == 200, path
            result[path] = response.json()
        return result


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
async def test_all_starter_stub_preparation_contracts(db, tmp_path, monkeypatch, scenario):
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path))
    from app.generation.prepare import prepare_inputs, write_dashboard

    requirements, data = prepare_inputs({"scenarioId": scenario.id}, None)
    fixture = sample_for(scenario.id)
    assert data["rows"] == fixture["rows"]
    architecture = await StubArchitectAgent().run(requirements)
    pid = await ProjectRepository(db).create("T", "T", requirements, 100)
    ws.copy_template(pid)
    write_dashboard(pid, requirements, architecture, data)
    await StubDeveloperAgent().run(pid, requirements, architecture)
    spec = json.loads(ws.read_file(pid, "frontend/src/dashboard.config.json"))
    assert validate_spec(spec) == []
    assert spec["provenance"] == fixture["provenance"]
    assert _read_endpoints(pid, spec) == fixture["payloads"]
    assert "Sample data" in ws.read_file(pid, "frontend/src/kit/render.tsx")


FIVE = [
    "hiring-pipeline",
    "sales-pipeline",
    "budget-vs-actual",
    "production-quality",
    "energy-usage",
]


@pytest.mark.parametrize("starter", FIVE)
@pytest.mark.parametrize("mode", ["stub", "llm-double"])
async def test_no_upload_pipeline_ready_both_agent_modes(db, tmp_path, monkeypatch, starter, mode):
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path))
    from app.generation.prepare import stub_backend_source

    requirements = {**empty_requirements("sample test"), "scenarioId": starter}
    pid = await ProjectRepository(db).create("Sample", "Sample", requirements, 100)
    fixture = sample_for(starter)
    calls = []

    class Double:
        async def complete(self, system, user):
            request = json.loads(user)
            calls.append(request)
            if "architecture" not in request:
                return json.dumps(fixture["spec"])
            backend = stub_backend_source(request["requirements"])
            return json.dumps(
                {
                    "files": [
                        {"path": "backend/main.py", "content": backend},
                        *[
                            {"path": p, "content": "# double compatibility module\n"}
                            for p in DEVELOPER_FILES
                            if p.startswith("backend/")
                        ],
                        # Malicious/accidental data echo must not replace protected rows.
                        {"path": "backend/data/dataset.json", "content": '{"rows": []}'},
                    ]
                }
            )

    architect = StubArchitectAgent() if mode == "stub" else LlmArchitectAgent(Double())
    developer = StubDeveloperAgent() if mode == "stub" else LlmDeveloperAgent(Double())

    class BackendReviewer(StubReviewerAgent):
        async def run(self, requirements, architecture, files):
            assert "backend/main.py" in files
            return REVIEW_PASS

    reviewer = StubReviewerAgent() if mode == "stub" else BackendReviewer()
    tester = StubTesterAgent() if mode == "stub" else LlmTesterAgent(Double())
    await PocGenerationService(db, architect, developer, reviewer, tester).generate(pid)
    project = await ProjectRepository(db).get_or_raise(pid)
    assert project["status"] == "READY", project.get("error")
    spec = json.loads(ws.read_file(pid, "frontend/src/dashboard.config.json"))
    assert spec["provenance"]["kind"] == "sample"
    assert json.loads(ws.read_file(pid, "backend/data/dataset.json"))["rows"] == fixture["rows"]
    assert _read_endpoints(pid, spec) == fixture["payloads"]
    presentation = project["presentation"]
    assert presentation["status"] == "available", presentation
    bundle = json.loads((ws.workspace_dir(pid) / "presentation/input.json").read_bytes())
    assert bundle["snapshot"]["endpoints"] == _read_endpoints(pid, spec)
    assert bundle["spec"] == spec
    assert bundle["snapshot"]["provenance"]["kind"] == "sample"
    assert bundle["copy"]["problem"] == "sample test"
    assert bundle["theme"]["css"]
    from app.presentation.service import read_input

    assert read_input(pid, presentation) == bundle
    if mode == "llm-double":
        assert len(calls) == 2
        assert calls[0]["dataset"] == calls[1]["requirements"]["dataset"]
        assert calls[1]["requirements"]["sample"]["metric"] == fixture["metric"]


@pytest.mark.parametrize("reason", ["failed", "timed out", "dependency unavailable"])
async def test_capture_failure_still_ready_and_invalidates_old(db, tmp_path, monkeypatch, reason):
    from app.generation import snapshot

    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path))
    pid = await ProjectRepository(db).create("Test", "Test", empty_requirements("test"), 100)
    stale = ws.workspace_dir(pid) / "presentation"
    stale.mkdir()
    (stale / "input.json").write_text('{"stale": true}')

    def fail(*args, **kwargs):
        raise snapshot.CaptureError(f"Presentation capture {reason}.")

    monkeypatch.setattr(snapshot, "capture", fail)
    await PocGenerationService(
        db, StubArchitectAgent(), StubDeveloperAgent(), StubReviewerAgent(), StubTesterAgent()
    ).generate(pid)
    project = await ProjectRepository(db).get_or_raise(pid)
    assert project["status"] == "READY"
    assert project["presentation"] == {
        "status": "unavailable",
        "reason": f"Presentation capture {reason}.",
    }
    assert not stale.exists()
