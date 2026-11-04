"""Uploading a user's file and building the dashboard on it."""

import json

from app.agents.llm import DATASET_PATH
from app.agents.stubs import (
    StubArchitectAgent,
    StubDeveloperAgent,
    StubReviewerAgent,
    StubTesterAgent,
)
from app.ingest import spreadsheet
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import empty_requirements
from app.services.generation_service import PocGenerationService
from app.workspace import workspace as ws

CSV = b"Month,Region,Revenue\n2026-01-01,North,1200\n2026-02-01,South,950.5\n"


def _upload(client, project_id, name="sales.csv", data=CSV):
    return client.post(f"/api/projects/{project_id}/dataset", files={"file": (name, data)})


def test_upload_returns_what_was_understood(client, project_id):
    response = _upload(client, project_id)
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "sales.csv"
    assert (body["rowCount"], body["usedRows"], body["truncated"]) == (2, 2, False)
    assert body["columns"] == [
        {"key": "month", "label": "Month", "type": "date"},
        {"key": "region", "label": "Region", "type": "text"},
        {"key": "revenue", "label": "Revenue", "type": "number"},
    ]
    assert body["preview"][1] == {"month": "2026-02-01", "region": "South", "revenue": 950.5}


def test_get_replace_and_delete(client, project_id):
    assert client.get(f"/api/projects/{project_id}/dataset").status_code == 404
    _upload(client, project_id)
    _upload(client, project_id, "other.csv", b"a\n1\n")
    got = client.get(f"/api/projects/{project_id}/dataset").json()
    assert got["filename"] == "other.csv", "a re-upload replaces the earlier file"
    assert client.delete(f"/api/projects/{project_id}/dataset").status_code == 204
    assert client.get(f"/api/projects/{project_id}/dataset").status_code == 404


def test_unusable_file_is_refused_with_its_reason(client, project_id):
    response = _upload(client, project_id, "virus.csv", b"MZ\x90\x00" + b"\x00" * 64)
    assert response.status_code == 415
    assert "CSV" in response.json()["detail"]


def test_unknown_project_is_404(client):
    assert _upload(client, "0" * 24).status_code == 404


async def test_upload_is_refused_while_generating(client, db, project_id):
    await ProjectRepository(db).update_fields(project_id, {"status": "GENERATING"})
    assert _upload(client, project_id).status_code == 409


class RecordingArchitect(StubArchitectAgent):
    async def run(self, requirements):
        self.seen = requirements
        return await super().run(requirements)


async def test_generation_designs_on_the_upload_and_ships_its_rows(db, tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path / "generated"))
    project_id = await ProjectRepository(db).create("T", "T", empty_requirements("p"), 14)
    await DatasetRepository(db).save(project_id, spreadsheet.parse("sales.csv", CSV))
    architect = RecordingArchitect()
    service = PocGenerationService(
        db, architect, StubDeveloperAgent(), StubReviewerAgent(), StubTesterAgent()
    )
    await service.generate(project_id)

    # The architect designs around columns that exist...
    dataset = architect.seen["dataset"]
    assert [c["key"] for c in dataset["columns"]] == ["month", "region", "revenue"]
    assert dataset["rowCount"] == 2
    # ...the generated backend gets every row...
    shipped = json.loads(ws.read_file(project_id, DATASET_PATH))
    assert len(shipped["rows"]) == 2 and shipped["columns"][2]["type"] == "number"
    # ...and the stored requirements are untouched by it.
    project = await ProjectRepository(db).get(project_id)
    assert "dataset" not in project["requirements"]["content"]
    assert project["status"] == "READY"
