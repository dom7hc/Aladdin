"""Requirement chat, completion, finalize and state guards (Backend Plan §6)."""

from tests.conftest import answer_all_questions


def test_chat_updates_requirements_and_completion(client, project_id):
    first = client.post(
        f"/api/projects/{project_id}/chat", json={"message": "Finance employees"}
    ).json()
    assert first["requirements"]["targetUsers"] == ["Finance employees"]
    assert first["ready"] is False
    assert "targetUsers" not in first["missingFields"]
    assert first["completion"] > 14

    second = client.post(
        f"/api/projects/{project_id}/chat", json={"message": "Upload and review invoices"}
    ).json()
    assert second["requirements"]["mainWorkflow"] == ["Upload and review invoices"]
    assert second["completion"] > first["completion"]


def test_chat_rejects_blank_message(client, project_id):
    assert client.post(f"/api/projects/{project_id}/chat", json={"message": ""}).status_code == 422


def test_chat_on_unknown_project_returns_404(client):
    assert (
        client.post(
            "/api/projects/000000000000000000000000/chat", json={"message": "hi"}
        ).status_code
        == 404
    )


def test_finalize_requires_complete_requirements(client, project_id):
    response = client.post(f"/api/projects/{project_id}/requirements/finalize")
    assert response.status_code == 409
    assert "missing" in response.json()["detail"]


def test_finalize_then_chat_is_rejected(client, project_id):
    answer_all_questions(client, project_id)
    finalized = client.post(f"/api/projects/{project_id}/requirements/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "REQUIREMENT_READY"

    blocked = client.post(f"/api/projects/{project_id}/chat", json={"message": "one more thing"})
    assert blocked.status_code == 409

    twice = client.post(f"/api/projects/{project_id}/requirements/finalize")
    assert twice.status_code == 409


def test_requirements_state_endpoint(client, project_id):
    state = client.get(f"/api/projects/{project_id}/requirements").json()
    assert state["requirements"]["problem"].startswith("I want an AI application")
    assert len(state["missingFields"]) == 6
    assert state["ready"] is False
