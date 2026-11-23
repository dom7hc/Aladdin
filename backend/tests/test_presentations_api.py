"""Read stored input only: never execute generated code or start previews on GET."""

import json

import pytest

from app.agents.stubs import StubRequirementAgent
from app.generation.snapshot import content_hash
from app.presentation import service
from app.repositories.project_repository import ProjectRepository
from app.services.project_service import ProjectService
from app.workspace import workspace as ws
from tests.test_generation_pipeline import run_pipeline


def test_unknown_not_ready_legacy(client, project_id, tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path))
    assert (
        client.get("/api/projects/000000000000000000000000/presentation-input").status_code == 404
    )
    response = client.get(f"/api/projects/{project_id}/presentation-input")
    assert response.status_code == 409
    assert response.json()["detail"]
    assert not (tmp_path / project_id).exists()  # GET does not create workspace


def test_available_get_is_stored_only(client, project_id, tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path))
    run_pipeline(client, project_id)
    directory = tmp_path / project_id / "presentation"
    expected = json.loads((directory / "input.json").read_bytes())
    # Removing generated code proves GET has no execution/preview dependency.
    (tmp_path / project_id / "source/backend/main.py").unlink()
    response = client.get(f"/api/projects/{project_id}/presentation-input")
    assert response.status_code == 200
    assert response.json() == expected
    assert client.get(f"/api/projects/{project_id}").json()["presentation"]["status"] == "available"
    assert client.get(f"/api/projects/{project_id}/status").json()["presentation"]["inputHash"] == (
        content_hash(expected)
    )
    (directory / "input.json").write_text('{"tampered": true}')
    assert client.get(f"/api/projects/{project_id}/presentation-input").status_code == 409


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {"status": "unavailable", "reason": "Presentation capture timed out."},
        {"status": "available", "inputHash": "a" * 64, "schemaVersion": 1},
    ],
)
async def test_ready_without_workspace_is_conflict(
    db, client, project_id, tmp_path, monkeypatch, metadata
):
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path))
    await ProjectRepository(db).update_fields(
        project_id, {"status": "READY", "presentation": metadata}
    )
    result = client.get(f"/api/projects/{project_id}/presentation-input")
    assert result.status_code == 409
    assert not (tmp_path / project_id).exists()


async def test_retry_invalidates_metadata_and_files(db, client, project_id, tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path))
    run_pipeline(client, project_id)
    await ProjectRepository(db).update_fields(project_id, {"status": "FAILED"})
    await ProjectService(db, StubRequirementAgent()).reset_for_retry(project_id)
    assert not (tmp_path / project_id / "presentation").exists()
    project = await ProjectRepository(db).get_or_raise(project_id)
    assert project["presentation"]["status"] == "unavailable"


def test_atomic_publish_failure_exposes_neither_file(client, project_id, tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path))

    def fail(*args):
        raise OSError("test disk error")

    monkeypatch.setattr(service.os, "replace", fail)
    run_pipeline(client, project_id)
    response = client.get(f"/api/projects/{project_id}/presentation-input")
    assert response.status_code == 409
    assert not (tmp_path / project_id / "presentation").exists()
    assert not list((tmp_path / project_id).glob(".presentation-*"))
