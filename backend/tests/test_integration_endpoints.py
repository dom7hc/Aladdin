"""Endpoints added for frontend integration: project list, chat history, retry."""

from tests.conftest import answer_all_questions


def test_list_projects_empty(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == []


def test_list_projects_returns_newest_first(client, project_id):
    client.post("/api/projects", json={"idea": "Second idea"})
    response = client.get("/api/projects")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    # newest (Second idea) first
    assert body[0]["name"] == "Second idea"
    assert any(item["id"] == project_id for item in body)


def test_list_projects_shape(client, project_id):
    body = client.get("/api/projects").json()
    project = body[0]
    assert set(project) == {
        "id",
        "name",
        "description",
        "status",
        "completion",
        "createdAt",
        "updatedAt",
    }


def test_chat_history_returns_greeting(client, project_id):
    response = client.get(f"/api/projects/{project_id}/chat")
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 1
    assert messages[0]["role"] == "assistant"
    assert set(messages[0]) == {"id", "projectId", "role", "content", "createdAt"}
    assert messages[0]["projectId"] == project_id


def test_chat_history_is_chronological(client, project_id):
    client.post(f"/api/projects/{project_id}/chat", json={"message": "Finance team"})
    client.post(f"/api/projects/{project_id}/chat", json={"message": "Upload then review"})
    messages = client.get(f"/api/projects/{project_id}/chat").json()
    assert [m["role"] for m in messages] == [
        "assistant",
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[-2]["content"] == "Upload then review"


def test_chat_history_unknown_project_returns_404(client):
    assert client.get("/api/projects/000000000000000000000000/chat").status_code == 404


async def test_generate_from_failed_allows_retry(client, db, project_id):
    from app.repositories.project_repository import ProjectRepository

    answer_all_questions(client, project_id)
    client.post(f"/api/projects/{project_id}/requirements/finalize")

    # Simulate a failed run by setting the project status/error directly.
    repo = ProjectRepository(db)
    await repo.update_fields(project_id, {"status": "FAILED", "error": "boom"})

    status = client.get(f"/api/projects/{project_id}/status").json()
    assert status["status"] == "FAILED"
    assert status["message"] == "boom"

    retry = client.post(f"/api/projects/{project_id}/generate")
    assert retry.status_code == 202
    assert retry.json()["status"] == "STARTED"


def test_generate_rejects_wrong_state(client, project_id):
    response = client.post(f"/api/projects/{project_id}/generate")
    assert response.status_code == 409
