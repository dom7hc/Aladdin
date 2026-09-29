"""Shared fixtures: FastAPI app backed by mongomock-motor (no real MongoDB needed)."""

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.main import create_app


@pytest.fixture()
def db():
    return AsyncMongoMockClient()["aladdin_test"]


@pytest.fixture()
def client(db):
    # Context manager form: TestClient only runs the lifespan (which sets app.state.db) inside `with`.
    with TestClient(create_app(db=db)) as test_client:
        yield test_client


@pytest.fixture()
def project_id(client: TestClient) -> str:
    response = client.post(
        "/api/projects", json={"idea": "I want an AI application that analyzes invoices."}
    )
    assert response.status_code == 201
    return response.json()["id"]


def answer_all_questions(client: TestClient, project_id: str) -> None:
    """Drive the stub requirement agent until ready (6 answers, problem is pre-filled)."""
    for i in range(6):
        response = client.post(
            f"/api/projects/{project_id}/chat", json={"message": f"answer {i + 1}"}
        )
        assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["missingFields"] == []
