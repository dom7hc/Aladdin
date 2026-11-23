"""Canonical source is the platform frontend; generated mirror never drifts."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "frontend/src/dashboard-kit"
MIRROR = ROOT / "backend/templates/default-poc/frontend/src/kit"
SHARED = (
    "types.ts",
    "normalize.ts",
    "format.ts",
    "snapshot.ts",
    "insights.ts",
    "charts.tsx",
    "export.css",
)


def test_template_mirror_is_byte_identical():
    for name in SHARED:
        assert (CORE / name).read_bytes() == (MIRROR / name).read_bytes(), name


def test_typescript_core_harness():
    node = shutil.which("node")
    if not node:
        pytest.fail("Node required for shared TypeScript development checks")
    result = subprocess.run(
        [node, "--test", str(CORE / "core.test.mjs")],
        cwd=ROOT / "frontend",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_template_build_is_real_and_fonts_are_offline_safe():
    import json

    from app.design.systems import design_css, resolve

    package = json.loads((MIRROR.parents[1] / "package.json").read_text())
    assert package["scripts"]["build"] == "vite build"
    assert "vite" in package["devDependencies"]
    css = design_css(resolve(None, None))
    assert "@import" not in css
    assert "fonts.googleapis" not in css
    assert "system-ui" in css
