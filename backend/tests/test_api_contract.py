"""API-contract functional check (Plan Ã‚Â§8): hermetic regex-based tests."""

from pathlib import Path

from app.generation.contract import check_api_contract


def make_source(tmp_path: Path, backend: str, frontend: str) -> Path:
    source = tmp_path / "source"
    (source / "backend").mkdir(parents=True)
    (source / "frontend" / "src").mkdir(parents=True)
    (source / "backend" / "main.py").write_text(backend, encoding="utf-8")
    (source / "frontend" / "src" / "api.ts").write_text(frontend, encoding="utf-8")
    return source


def test_contract_passes_when_frontend_calls_are_covered(tmp_path: Path):
    source = make_source(
        tmp_path,
        backend=(
            '@app.get("/health")\n@app.get("/api/tasks")\n@app.post("/api/tasks/{task_id}")\n'
        ),
        frontend=(
            "const list = fetch('/api/tasks')\n"
            "const save = fetch(`/api/tasks/${id}`, { method: 'POST' })\n"
        ),
    )
    result = check_api_contract(source)
    assert result["exitCode"] == 0
    assert "contract OK" in result["stdout"]


def test_contract_fails_on_missing_backend_route(tmp_path: Path):
    source = make_source(
        tmp_path,
        backend='@app.get("/api/tasks")\n',
        frontend=("fetch('/api/tasks')\nfetch('/api/users', { method: 'POST' })\n"),
    )
    result = check_api_contract(source)
    assert result["exitCode"] == 1
    assert "/api/users" in result["stdout"]
    assert "MISSING IN BACKEND" in result["stdout"]


def test_contract_normalizes_path_params(tmp_path: Path):
    source = make_source(
        tmp_path,
        backend='@app.delete("/api/items/{item_id}")\n',
        frontend="fetch(`/api/items/${itemId}`, { method: 'DELETE' })\n",
    )
    result = check_api_contract(source)
    assert result["exitCode"] == 0


def test_contract_fails_when_backend_has_no_api_routes(tmp_path: Path):
    source = make_source(
        tmp_path, backend='@app.get("/health")\n', frontend="fetch('/api/tasks')\n"
    )
    result = check_api_contract(source)
    assert result["exitCode"] == 1


VALID_MAIN = (
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n\n"
    '@app.get("/health")\n'
    "def health():\n"
    '    return {"status": "ok"}\n'
)


async def test_battery_includes_api_contract_step(tmp_path: Path):
    from app.generation import runner

    source = tmp_path / "source"
    (source / "backend").mkdir(parents=True)
    (source / "frontend").mkdir(parents=True)
    (source / "backend" / "main.py").write_text(VALID_MAIN, encoding="utf-8")
    steps = await runner.run_test_battery(str(source), run_pytest=False)
    by_step = {step["step"]: step for step in steps}
    assert by_step["apiContract"]["status"] == "PASSED"


async def test_battery_fails_on_contract_mismatch(tmp_path: Path, monkeypatch):
    from app.generation import runner

    source = tmp_path / "source"
    (source / "backend").mkdir(parents=True)
    (source / "frontend" / "src").mkdir(parents=True)
    (source / "backend" / "main.py").write_text(VALID_MAIN, encoding="utf-8")
    (source / "frontend" / "src" / "api.ts").write_text("fetch('/api/missing')\n", encoding="utf-8")

    # Keep the battery hermetic: skip pip/pytest/npm, only exercise the contract step.
    steps = await runner.run_test_battery(
        str(source), run_pip_install=False, run_pytest=False, run_npm_build=False
    )
    failed = next(step for step in steps if step["status"] == "FAILED")
    assert failed["step"] == "apiContract"
    assert failed["category"] == "API_CONTRACT"
    assert "/api/missing" in (failed["result"]["stdout"] or "")
    # The battery stops at the first failure: no later steps are recorded.
    assert steps[-1]["step"] == "apiContract"


def _write_spec(source: Path, spec: dict) -> None:
    import json

    (source / "frontend" / "src" / "dashboard.config.json").write_text(
        json.dumps(spec), encoding="utf-8"
    )


EDITABLE_TABLE_SPEC = {
    "title": "Onboarding",
    "layout": "records-workspace",
    "widgets": [
        {
            "kind": "table",
            "title": "Outstanding steps",
            "endpoint": "/api/joiners",
            "editable": True,
            "columns": [{"label": "ID", "field": "id"}, {"label": "Name", "field": "name"}],
        }
    ],
}


def test_spec_demands_crud_routes_for_editable_tables(tmp_path: Path):
    source = make_source(
        tmp_path,
        backend='@app.get("/api/joiners")\n',  # reads only — CRUD missing
        frontend="",
    )
    _write_spec(source, EDITABLE_TABLE_SPEC)
    result = check_api_contract(source)
    assert result["exitCode"] == 1
    assert "POST /api/joiners" in result["stdout"]
    assert "PUT /api/joiners/{param}" in result["stdout"]
    assert "DELETE /api/joiners/{param}" in result["stdout"]


def test_spec_crud_routes_satisfied_by_full_backend(tmp_path: Path):
    source = make_source(
        tmp_path,
        backend=(
            '@app.get("/api/joiners")\n@app.post("/api/joiners")\n'
            '@app.put("/api/joiners/{joiner_id}")\n@app.delete("/api/joiners/{joiner_id}")\n'
        ),
        frontend="",
    )
    _write_spec(source, EDITABLE_TABLE_SPEC)
    result = check_api_contract(source)
    assert result["exitCode"] == 0
    assert "mutating" in result["stdout"]


def test_contract_is_method_aware(tmp_path: Path):
    """A POST call must not pass on the strength of a GET route (this passed
    under the old path-only matcher and 405'd at runtime)."""
    source = make_source(
        tmp_path,
        backend='@app.get("/api/tasks")\n',
        frontend="fetch('/api/tasks', { method: 'POST' })\n",
    )
    result = check_api_contract(source)
    assert result["exitCode"] == 1
    assert "POST /api/tasks" in result["stdout"]


def test_read_only_spec_stays_get_only(tmp_path: Path):
    spec = {
        "title": "Orders",
        "layout": "kpi-overview",
        "widgets": [
            {"kind": "stat", "label": "Orders", "field": "total", "endpoint": "/api/metrics"}
        ],
    }
    source = make_source(tmp_path, backend='@app.get("/api/metrics")\n', frontend="")
    _write_spec(source, spec)
    result = check_api_contract(source)
    assert result["exitCode"] == 0
    assert "0 mutating" in result["stdout"]
