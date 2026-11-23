"""Execute the shared TypeScript presentation code: slide order, number parity
with the dashboard's own computation, escaping and the no-network CSP."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shared_presentation():
    result = subprocess.run(
        [
            shutil.which("node"),
            "--import",
            "./scripts/register-ts-tests.mjs",
            "--test",
            "src/dashboard-kit/presentation.test.mjs",
            "src/presentation/openInNewTab.test.mjs",
        ],
        cwd=ROOT / "frontend",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
