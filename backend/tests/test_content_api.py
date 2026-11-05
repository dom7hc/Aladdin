"""Editable business cases and home page texts (app/api/content.py)."""

import pytest
from fastapi.testclient import TestClient

from app import catalogue, config

KEY = "test-admin-key"
ADMIN = {"X-Admin-Key": KEY}

NEW_CASE = {
    "title": "Plant OEE watch",
    "audience": "Plant manager",
    "problem": "Downtime is only visible at the weekly review.",
    "layout": "kpi-overview",
    "highlights": ["OEE per line, every shift", "Top downtime reasons"],
    "prompt": "An OEE dashboard: availability, performance and quality per line.",
}


@pytest.fixture(autouse=True)
def admin_key(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_KEY", KEY)


def test_built_in_cases_are_seeded_once(client: TestClient):
    cases = client.get("/api/content/scenarios").json()
    assert len(cases) == 20
    assert cases[0]["id"] == catalogue.SCENARIOS[0].id
    assert all(case["builtin"] for case in cases)
    # The old endpoint reads the same stored set.
    assert [c["id"] for c in client.get("/api/projects/scenarios").json()] == [
        c["id"] for c in cases
    ]


def test_deleting_every_case_does_not_reseed(client: TestClient):
    for case in client.get("/api/content/scenarios").json():
        assert (
            client.delete(f"/api/content/scenarios/{case['id']}", headers=ADMIN).status_code == 204
        )
    assert client.get("/api/content/scenarios").json() == []


def test_create_edit_and_delete_a_case(client: TestClient):
    created = client.post("/api/content/scenarios", json=NEW_CASE, headers=ADMIN)
    assert created.status_code == 201
    body = created.json()
    assert body["id"] == "plant-oee-watch"
    assert body["order"] == 20
    assert body["builtin"] is False

    edited = client.put(
        f"/api/content/scenarios/{body['id']}",
        json={**NEW_CASE, "audience": "Plant and shift managers"},
        headers=ADMIN,
    )
    assert edited.json()["audience"] == "Plant and shift managers"

    # A second case with the same title gets its own id.
    again = client.post("/api/content/scenarios", json=NEW_CASE, headers=ADMIN).json()
    assert again["id"] == "plant-oee-watch-2"

    assert client.delete(f"/api/content/scenarios/{body['id']}", headers=ADMIN).status_code == 204
    assert (
        client.put(f"/api/content/scenarios/{body['id']}", json=NEW_CASE, headers=ADMIN).status_code
        == 404
    )


def test_edits_reach_the_agents_prompt(client: TestClient):
    """The requirement chat steers toward the cases as edited, not the built-ins."""
    client.post("/api/content/scenarios", json=NEW_CASE, headers=ADMIN)
    assert "Plant OEE watch (Plant manager)" in catalogue.prompt_guidance()


def test_hidden_cases_leave_the_home_page_but_stay_editable(client: TestClient):
    first = client.get("/api/content/scenarios").json()[0]
    client.put(
        f"/api/content/scenarios/{first['id']}",
        json={**{k: first[k] for k in NEW_CASE}, "enabled": False},
        headers=ADMIN,
    )
    public = [c["id"] for c in client.get("/api/content/scenarios").json()]
    everything = [c["id"] for c in client.get("/api/content/scenarios?all=true").json()]
    assert first["id"] not in public
    assert first["id"] in everything
    assert first["title"] not in catalogue.prompt_guidance()


def test_reorder_puts_named_cases_first(client: TestClient):
    ids = [c["id"] for c in client.get("/api/content/scenarios").json()]
    reordered = client.put(
        "/api/content/scenario-order", json={"ids": [ids[3], ids[0]]}, headers=ADMIN
    ).json()
    assert [c["id"] for c in reordered[:3]] == [ids[3], ids[0], ids[1]]
    assert len(reordered) == 20

    missing = client.put("/api/content/scenario-order", json={"ids": ["nope"]}, headers=ADMIN)
    assert missing.status_code == 404


def test_reset_restores_the_built_ins(client: TestClient):
    client.post("/api/content/scenarios", json=NEW_CASE, headers=ADMIN)
    first = client.get("/api/content/scenarios").json()[0]
    client.delete(f"/api/content/scenarios/{first['id']}", headers=ADMIN)
    restored = client.post("/api/content/scenarios/reset", headers=ADMIN).json()
    assert [c["id"] for c in restored] == [s.id for s in catalogue.SCENARIOS]


def test_invalid_case_is_rejected(client: TestClient):
    response = client.post(
        "/api/content/scenarios", json={**NEW_CASE, "title": "  "}, headers=ADMIN
    )
    assert response.status_code == 422
    response = client.post(
        "/api/content/scenarios", json={**NEW_CASE, "layout": "chatbot"}, headers=ADMIN
    )
    assert response.status_code == 422


def test_home_texts_default_save_and_reset(client: TestClient):
    home = client.get("/api/content/home").json()
    assert home["titleHighlight"] == "working dashboard"
    assert home["projectsTitle"] == "Recent Projects"

    saved = client.put(
        "/api/content/home",
        json={**home, "title": "Turn your Excel into a", "badge": ""},
        headers=ADMIN,
    ).json()
    assert saved["title"] == "Turn your Excel into a"
    # Blank falls back to the default rather than showing nothing.
    assert saved["badge"] == "Make your wish come true"
    assert client.get("/api/content/home").json()["title"] == "Turn your Excel into a"

    reset = client.delete("/api/content/home", headers=ADMIN).json()
    assert reset["title"] == "Turn your idea into a"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/content/scenarios"),
        ("put", "/api/content/scenarios/cv-fit"),
        ("delete", "/api/content/scenarios/cv-fit"),
        ("put", "/api/content/scenario-order"),
        ("post", "/api/content/scenarios/reset"),
        ("put", "/api/content/home"),
        ("delete", "/api/content/home"),
    ],
)
def test_every_write_needs_the_admin_key(client: TestClient, method: str, path: str):
    body = {"json": NEW_CASE} if method in ("post", "put") else {}
    assert getattr(client, method)(path, **body).status_code == 401
    wrong = getattr(client, method)(path, headers={"X-Admin-Key": "guess"}, **body)
    assert wrong.status_code == 401


def test_editing_is_off_when_the_server_has_no_key(client: TestClient, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_KEY", "")
    response = client.put("/api/content/home", json={}, headers={"X-Admin-Key": ""})
    assert response.status_code == 403
    # Reading still works: the home page needs it.
    assert client.get("/api/content/home").status_code == 200
