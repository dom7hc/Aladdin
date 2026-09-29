"""Isolated per-project workspaces on disk.

generated/{project-id}/
├── requirements.md
├── architecture.md
└── source/          (copied from templates/default-poc)
"""

import shutil
import zipfile
from io import BytesIO
from pathlib import Path

from app.config import GENERATED_DIR, TEMPLATES_DIR
from app.repositories.project_repository import ProjectNotFoundError

_SAFE_ID = set("abcdefABCDEF0123456789")


def workspace_dir(project_id: str) -> Path:
    if not project_id or len(project_id) != 24 or not set(project_id) <= _SAFE_ID:
        raise ProjectNotFoundError(project_id)
    path = Path(GENERATED_DIR) / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def source_dir(project_id: str) -> Path:
    return workspace_dir(project_id) / "source"


def copy_template(project_id: str, template_name: str = "default-poc") -> Path:
    template = Path(TEMPLATES_DIR) / template_name
    if not template.is_dir():
        raise FileNotFoundError(f"Template not found: {template}")
    destination = source_dir(project_id)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(template, destination)
    return destination


def write_file(project_id: str, relative_path: str, content: str) -> Path:
    path = source_dir(project_id) / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def read_file(project_id: str, relative_path: str) -> str:
    path = source_dir(project_id) / relative_path
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    return path.read_text(encoding="utf-8")


def list_files(project_id: str) -> list[str]:
    source = source_dir(project_id)
    if not source.is_dir():
        return []
    return sorted(
        str(p.relative_to(source)).replace("\\", "/") for p in source.rglob("*") if p.is_file()
    )


def zip_source(project_id: str) -> bytes:
    source = source_dir(project_id)
    files = [p for p in source.rglob("*") if p.is_file()] if source.is_dir() else []
    # The build/test runner's compileall step leaves __pycache__ behind; those
    # artifacts are not source and must not ship in the export.
    files = [p for p in files if "__pycache__" not in p.parts and p.suffix != ".pyc"]
    if not files:
        raise FileNotFoundError(f"No generated source for project {project_id}")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, file_path.relative_to(source))
    return buffer.getvalue()
