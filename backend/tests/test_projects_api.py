"""Project creation and retrieval (Backend Plan §6 core APIs)."""


def test_create_project_returns_collection_state(client):
    response = client.post("/api/projects", json={"idea": "Analyze invoices for anomalies"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "REQUIREMENT_COLLECTION"
    assert body["name"] == "Analyze invoices for anomalies"
    assert body["completion"] == 14  # problem pre-filled: 1/7 required fields


def test_create_project_rejects_blank_idea(client):
    response = client.post("/api/projects", json={"idea": ""})
    assert response.status_code == 422


def test_get_project(client, project_id):
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["id"] == project_id


def test_get_unknown_project_returns_404(client):
    assert client.get("/api/projects/000000000000000000000000").status_code == 404


def test_get_malformed_id_returns_404(client):
    assert client.get("/api/projects/not-an-id").status_code == 404


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_explicit_scenario_survives_create_autofill_and_get(client):
    response = client.post(
        "/api/projects", json={"idea": "Hiring", "scenarioId": "hiring-pipeline"}
    )
    assert response.status_code == 201
    project = response.json()
    assert project["scenarioId"] == "hiring-pipeline"
    assert client.get(f"/api/projects/{project['id']}").json()["scenarioId"] == "hiring-pipeline"
    state = client.post(f"/api/projects/{project['id']}/requirements/autofill").json()
    assert state["requirements"]["scenarioId"] == "hiring-pipeline"
    assert state["ready"]


def test_custom_scenario_and_legacy_free_text_are_supported(client):
    custom = client.post("/api/projects", json={"idea": "Custom", "scenarioId": "custom-role"})
    assert custom.status_code == 201
    assert custom.json()["scenarioId"] == "custom-role"
    assert client.post("/api/projects", json={"idea": "Free text"}).json()["scenarioId"] is None
    for bad in ("../x", "", "a" * 65, 123):
        assert (
            client.post("/api/projects", json={"idea": "x", "scenarioId": bad}).status_code == 422
        )


def test_mock_scenario_contract():
    import shutil
    import subprocess
    from pathlib import Path

    result = subprocess.run(
        [
            shutil.which("node"),
            "--import",
            "./scripts/register-ts-tests.mjs",
            "--test",
            "src/mocks/scenario.test.mjs",
        ],
        cwd=Path(__file__).resolve().parents[2] / "frontend",
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_delete_project_removes_it_and_its_chat(client, db, project_id):
    client.post(f"/api/projects/{project_id}/chat", json={"message": "Finance team"})
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert project_id not in [p["id"] for p in client.get("/api/projects").json()]


def test_delete_unknown_project_returns_404(client):
    assert client.delete("/api/projects/000000000000000000000000").status_code == 404


async def test_delete_refused_while_generating(client, db, project_id):
    from app.repositories.project_repository import ProjectRepository

    await ProjectRepository(db).update_fields(project_id, {"status": "GENERATING"})
    assert client.delete(f"/api/projects/{project_id}").status_code == 409
    assert client.get(f"/api/projects/{project_id}").status_code == 200
