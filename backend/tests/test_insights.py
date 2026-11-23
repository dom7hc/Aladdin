"""Execute the actual shared TypeScript fact code, not a Python reimplementation."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shared_insights_edge_cases():
    result = subprocess.run(
        [
            shutil.which("node"),
            "--import",
            "./scripts/register-ts-tests.mjs",
            "--test",
            "src/dashboard-kit/insights.test.mjs",
            "src/dashboard-kit/charts.test.mjs",
        ],
        cwd=ROOT / "frontend",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
