"""QA gap coverage: requirement state, chat persistence, determinism, workspace, 404s."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.agents.stubs import StubDeveloperAgent, StubTesterAgent
from app.config import GENERATED_DIR
from app.main import create_app
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import empty_requirements
from app.workspace import workspace as ws
from tests.conftest import answer_all_questions

UNKNOWN_ID = "000000000000000000000000"
MALFORMED_ID = "not-an-id"


def run_full_pipeline(client: TestClient, project_id: str) -> None:
    answer_all_questions(client, project_id)
    finalized = client.post(f"/api/projects/{project_id}/requirements/finalize")
    assert finalized.status_code == 200
    started = client.post(f"/api/projects/{project_id}/generate")
    assert started.status_code == 202
    status = client.get(f"/api/projects/{project_id}/status").json()
    assert status["status"] == "READY", status


def test_qa_requirements_state_shape(client, project_id):
    state = client.get(f"/api/projects/{project_id}/requirements").json()
    assert state["completion"] == 14
    assert state["missingFields"] == [
        "targetUsers",
        "mainWorkflow",
        "features",
        "inputs",
        "outputs",
        "successCriteria",
    ]
    assert state["ready"] is False


async def test_qa_chat_persists_messages(db, client, project_id):
    response = client.post(
        f"/api/projects/{project_id}/chat", json={"message": "Finance employees"}
    )
    assert response.status_code == 200

    docs = [doc async for doc in db["messages"].find({"project_id": project_id}).sort("_id", 1)]
    assert [doc["role"] for doc in docs] == ["assistant", "user", "assistant"]
    assert docs[1]["content"] == "Finance employees"


def test_qa_requirements_md_deterministic(client, project_id):
    answer_all_questions(client, project_id)
    first_finalize = client.post(f"/api/projects/{project_id}/requirements/finalize")
    assert first_finalize.status_code == 200

    created = client.post(
        "/api/projects", json={"idea": "I want an AI application that analyzes invoices."}
    )
    assert created.status_code == 201
    second_id = created.json()["id"]
    answer_all_questions(client, second_id)
    second_finalize = client.post(f"/api/projects/{second_id}/requirements/finalize")
    assert second_finalize.status_code == 200

    def requirements_md(pid: str) -> str:
        artifacts = client.get(f"/api/projects/{pid}/artifacts").json()
        artifact = next(a for a in artifacts if a["type"] == "REQUIREMENTS_MD")
        return artifact["content"]

    first_md = requirements_md(project_id)
    second_md = requirements_md(second_id)
    assert first_md == second_md
    assert first_md.startswith("# I want an AI application")


def test_qa_workspace_layout_on_disk(client, project_id):
    run_full_pipeline(client, project_id)
    root = Path(GENERATED_DIR) / project_id
    assert (root / "requirements.md").is_file()
    assert (root / "architecture.md").is_file()
    assert (root / "source" / "backend" / "main.py").is_file()
    assert (root / "source" / "backend" / "models" / "item.py").is_file()


def test_qa_test_result_artifact_passed(client, project_id):
    run_full_pipeline(client, project_id)
    artifacts = client.get(f"/api/projects/{project_id}/artifacts").json()
    artifact = next(a for a in artifacts if a["type"] == "TEST_RESULT")
    assert set(artifact) == {"type", "version", "createdAt", "content"}
    result = json.loads(artifact["content"])
    assert result["status"] == "PASSED"
    assert "compiles" in result["summary"]


async def test_qa_tester_flags_broken_backend(db):
    repository = ProjectRepository(db)
    project_id = await repository.create("QA", "QA", empty_requirements("qa"), 14)
    ws.copy_template(project_id)
    await StubDeveloperAgent().run(project_id, {}, {})
    ws.write_file(project_id, "backend/broken.py", "def oops(:\n")

    result = await StubTesterAgent().run(project_id)
    assert result.status == "FAILED"
    assert result.category == "COMPILE_ERROR"


ROUTE_SPECS = [
    ("get", "/api/projects/{id}/requirements", False),
    ("post", "/api/projects/{id}/chat", True),
    ("post", "/api/projects/{id}/requirements/finalize", False),
    ("get", "/api/projects/{id}/status", False),
    ("get", "/api/projects/{id}/artifacts", False),
    ("get", "/api/projects/{id}/source", False),
]


@pytest.mark.parametrize(("method", "path_template", "needs_body"), ROUTE_SPECS)
def test_qa_404_matrix(client, method, path_template, needs_body):
    for project_id in (UNKNOWN_ID, MALFORMED_ID):
        kwargs = {"json": {"message": "hi"}} if needs_body else {}
        response = getattr(client, method)(path_template.format(id=project_id), **kwargs)
        assert response.status_code == 404, (method, path_template, project_id)


@pytest.mark.parametrize("project_id", [UNKNOWN_ID, MALFORMED_ID])
@pytest.mark.xfail(
    reason=(
        "QA-DEF-1 candidate: generate route resolves project outside _guard; "
        "unknown/malformed id likely 500 instead of 404"
    ),
    strict=False,
)
def test_qa_generate_unknown_id_returns_404(project_id):
    with TestClient(
        create_app(db=AsyncMongoMockClient()["aladdin_qa"]), raise_server_exceptions=False
    ) as client:
        response = client.post(f"/api/projects/{project_id}/generate")
    assert response.status_code == 404
