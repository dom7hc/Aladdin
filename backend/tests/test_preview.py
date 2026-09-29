"""Preview deployment (local Docker): hermetic contract tests — no daemon."""

from pathlib import Path

import pytest

from app.preview import builder
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import empty_requirements
from app.services.preview_service import PreviewNotReadyError, PreviewService
from app.workspace import workspace as ws

PROJECT_ID = "abcdef0123456789abcdef01"


@pytest.fixture()
def preview_ws(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path / "generated"))
    return ws.source_dir(PROJECT_ID)


def test_workspace_ships_preview_deploy_files():
    """Every generated workspace must be self-hostable via its deploy/ dir."""
    ws.copy_template(PROJECT_ID)
    deploy = ws.source_dir(PROJECT_ID) / "deploy"
    assert (deploy / "compose.yml").is_file()
    assert (deploy / "backend.Dockerfile").is_file()
    assert (deploy / "frontend.Dockerfile").is_file()


def test_pick_port_returns_free_port():
    port = builder.pick_port()
    assert (
        builder.config.PREVIEW_PORT_BASE
        <= port
        < builder.config.PREVIEW_PORT_BASE + builder.config.PREVIEW_PORT_RANGE
    )


def test_compose_file_missing_raises(preview_ws: Path):
    with pytest.raises(builder.PreviewError, match="deploy/compose.yml"):
        builder.compose_file(preview_ws)


def test_stack_up_reports_failure(tmp_path: Path, monkeypatch):
    def fake_run(args, timeout):
        from subprocess import CompletedProcess

        return CompletedProcess(args, 1, stdout="", stderr="build failed: no such file")

    monkeypatch.setattr(builder, "_run", fake_run)
    ws.copy_template(PROJECT_ID)
    with pytest.raises(builder.PreviewError, match="build failed"):
        builder.stack_up(ws.source_dir(PROJECT_ID), PROJECT_ID, 8200)


def test_stack_up_writes_env_and_succeeds(tmp_path: Path, monkeypatch):
    captured = {}

    def fake_run(args, timeout):
        captured["args"] = args
        from subprocess import CompletedProcess

        return CompletedProcess(args, 0, stdout="Started", stderr="")

    monkeypatch.setattr(builder, "_run", fake_run)
    ws.copy_template(PROJECT_ID)
    source = ws.source_dir(PROJECT_ID)
    builder.stack_up(source, PROJECT_ID, 8217)
    args = captured["args"]
    assert "aladdin-poc-abcdef01" in args  # compose project name from id prefix
    assert any(arg.endswith(str(Path("deploy") / "compose.yml")) for arg in args)
    assert "POC_PORT=8217" in (source / "deploy" / ".preview.env").read_text()


async def test_start_requires_ready_project(db):
    service = PreviewService(db)
    repo = ProjectRepository(db)
    project_id = await repo.create("T", "T", empty_requirements("p"), 14)
    with pytest.raises(PreviewNotReadyError, match="REQUIREMENT_COLLECTION"):
        await service.start(project_id)


async def test_start_rejects_without_docker(db, monkeypatch):
    repo = ProjectRepository(db)
    project_id = await repo.create("T", "T", empty_requirements("p"), 100)
    await repo.update_fields(project_id, {"status": "READY"})
    monkeypatch.setattr(builder, "docker_available", lambda: False)
    service = PreviewService(db)
    with pytest.raises(PreviewNotReadyError, match="Docker is not available"):
        await service.start(project_id)


async def test_start_and_failed_build_flow(db, monkeypatch):
    repo = ProjectRepository(db)
    project_id = await repo.create("T", "T", empty_requirements("p"), 100)
    await repo.update_fields(project_id, {"status": "READY"})
    monkeypatch.setattr(builder, "docker_available", lambda: True)

    async def explode(pid):
        raise builder.PreviewError("docker build exploded")

    monkeypatch.setattr(builder, "build_and_start", explode)
    service = PreviewService(db)
    state = await service.start(project_id)
    assert state["status"] == "building"
    await service.run_build(project_id)
    failed = await service.get_state(project_id)
    assert failed["status"] == "failed"
    assert "docker build exploded" in failed["message"]


async def test_successful_build_flow_records_port(db, monkeypatch):
    repo = ProjectRepository(db)
    project_id = await repo.create("T", "T", empty_requirements("p"), 100)
    await repo.update_fields(project_id, {"status": "READY"})
    monkeypatch.setattr(builder, "docker_available", lambda: True)

    async def fake_build(pid):
        return 8207

    monkeypatch.setattr(builder, "build_and_start", fake_build)
    service = PreviewService(db)
    await service.start(project_id)
    await service.run_build(project_id)
    running = await service.get_state(project_id)
    assert running["status"] == "running"
    assert running["port"] == 8207
    assert running["url"] == "http://localhost:8207"
    # stop tears down and resets state
    monkeypatch.setattr(builder, "stack_down", lambda pid, source_dir: None)
    stopped = await service.stop(project_id)
    assert stopped["status"] == "none"
    assert stopped["port"] is None


def test_wait_healthy_true_and_false(monkeypatch):
    import urllib.error

    def ok(url, timeout):
        from contextlib import contextmanager

        @contextmanager
        def resp():
            from types import SimpleNamespace

            yield SimpleNamespace(status=200)

        return resp()  # urllib.request.urlopen returns a context manager

    monkeypatch.setattr(builder.urllib.request, "urlopen", ok)
    monkeypatch.setattr(builder.config, "PREVIEW_HEALTH_TIMEOUT_SECONDS", 1)
    assert builder.wait_healthy(8200) is True

    def boom(url, timeout):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(builder.urllib.request, "urlopen", boom)
    assert builder.wait_healthy(8200) is False
