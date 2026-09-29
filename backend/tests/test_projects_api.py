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
