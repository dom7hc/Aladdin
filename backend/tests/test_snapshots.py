"""Generated API capture runs in an isolated, bounded child, never a preview."""

import time

import pytest

from app.generation import snapshot
from app.generation.samples import sample_for


def app_dir(tmp_path, source):
    backend = tmp_path / "source/backend"
    (backend / "data").mkdir(parents=True)
    (backend / "data/dataset.json").write_text('{"rows": [{"value": 7}]}')
    (backend / "main.py").write_text(source, encoding="utf-8")
    return tmp_path / "source"


SOURCE = """
import json, os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
@asynccontextmanager
async def lifespan(app):
    app.state.ready = True
    yield
    Path("closed").write_text("yes")
app = FastAPI(lifespan=lifespan)
@app.get("/api/metrics")
def metrics():
    assert app.state.ready
    assert "DEEPSEEK_API_KEY" not in os.environ
    assert "POC_DB" not in os.environ
    return {"value": json.loads(Path("data/dataset.json").read_text())["rows"][0]["value"]}
"""


def simple_spec():
    spec = sample_for("sales-pipeline")["spec"]
    spec["widgets"] = [
        {
            "id": "metric",
            "kind": "stat",
            "label": "Value",
            "field": "value",
            "endpoint": "/api/metrics",
        }
    ]
    spec["hero"] = dict(spec["widgets"][0])
    return spec


def test_lifespan_deduplication_environment_and_no_db(tmp_path, monkeypatch):
    source = app_dir(tmp_path, SOURCE)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-not-a-secret")
    result = snapshot.capture(source, simple_spec())
    assert result["endpoints"] == {"/api/metrics": {"value": 7}}
    assert (source / "backend/closed").read_text() == "yes"
    assert not list(tmp_path.rglob("*.db"))
    assert not list(tmp_path.glob(".capture-*"))


@pytest.mark.parametrize("path", ["https://host/api/a", "/api/../secret", "/api/a?q=x"])
def test_unsafe_paths_rejected_before_import(tmp_path, path):
    spec = simple_spec()
    spec["hero"]["endpoint"] = path
    with pytest.raises(snapshot.CaptureError):
        snapshot.capture(app_dir(tmp_path, "raise RuntimeError('must not run')"), spec)


@pytest.mark.parametrize(
    "body",
    [
        "return float('nan')",
        "return 'not an object'",
        "return {'x': 'x' * 600000}",
        "raise RuntimeError('secret detail must not escape')",
    ],
)
def test_invalid_or_oversized_payload_is_bounded_nonsecret(tmp_path, body):
    source = app_dir(
        tmp_path,
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/api/metrics')\ndef metrics():\n    " + body,
    )
    with pytest.raises(snapshot.CaptureError) as exc:
        snapshot.capture(source, simple_spec())
    assert "secret detail" not in str(exc.value)
    assert not list(tmp_path.glob(".capture-*"))


def test_timeout_reaps_and_cleans(tmp_path):
    source = app_dir(tmp_path, "import time\ntime.sleep(60)")
    start = time.monotonic()
    with pytest.raises(snapshot.CaptureError, match="timed out"):
        snapshot.capture(source, simple_spec(), timeout=0.2)
    assert time.monotonic() - start < 5
    assert not list(tmp_path.glob(".capture-*"))


def test_editable_fresh_db_seeded_by_generated_lifespan_and_removed(tmp_path):
    source = app_dir(
        tmp_path,
        """
import os, sqlite3, json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
@asynccontextmanager
async def lifespan(app):
    db = sqlite3.connect(os.environ["POC_DB"])
    db.execute("create table records(value)")
    rows = json.loads(Path("data/dataset.json").read_text())["rows"]
    db.executemany("insert into records values (?)", [(r["value"],) for r in rows])
    db.commit()
    app.state.db = db
    yield
    db.close()
app = FastAPI(lifespan=lifespan)
@app.get("/api/metrics")
async def metrics():
    return [{"value": r[0]} for r in app.state.db.execute("select value from records")]
""",
    )
    spec = simple_spec()
    spec["hero"] = None
    spec["widgets"] = [
        {
            "id": "records",
            "kind": "table",
            "title": "Records",
            "endpoint": "/api/metrics",
            "editable": True,
            "columns": [{"field": "id", "label": "ID"}],
        }
    ]
    assert snapshot.capture(source, spec)["endpoints"]["/api/metrics"] == [{"value": 7}]
    assert not list(tmp_path.rglob("*.db"))


def test_missing_dependency_is_unavailable(tmp_path, monkeypatch):
    source = app_dir(tmp_path, SOURCE)
    monkeypatch.setattr(snapshot, "DEPENDENCIES", ("definitely_absent_capture_dependency",))
    with pytest.raises(snapshot.CaptureError, match="dependency"):
        snapshot.capture(source, simple_spec())


def test_unique_get_only(tmp_path):
    source = app_dir(
        tmp_path,
        """
from fastapi import FastAPI
app = FastAPI()
count = 0
@app.get("/api/metrics")
def metrics():
    global count
    count += 1
    return {"value": count}
""",
    )
    assert snapshot.capture(source, simple_spec())["endpoints"] == {"/api/metrics": {"value": 1}}
