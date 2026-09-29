"""Full generation pipeline with stub agents: state machine, artifacts, workspace, ZIP."""

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
