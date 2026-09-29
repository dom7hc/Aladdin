"""Build/test command runner: captures stdout, stderr, exit code and duration.

Used by the Tester side of the pipeline (Backend Plan §10). Real agent
integrations reuse this against npm/pytest inside generated projects.
"""

import asyncio
import sys
import time
from typing import Any

COMMAND_TIMEOUT_SECONDS = 300


async def run_command(args: list[str], cwd: str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=COMMAND_TIMEOUT_SECONDS
        )
    except TimeoutError:
        return {
            "command": " ".join(args),
            "exitCode": None,
            "stdout": "",
            "stderr": f"Command timed out after {COMMAND_TIMEOUT_SECONDS}s",
            "durationMs": int((time.monotonic() - started) * 1000),
        }
    return {
        "command": " ".join(args),
        "exitCode": process.returncode,
        "stdout": stdout.decode(errors="replace"),
        "stderr": stderr.decode(errors="replace"),
        "durationMs": int((time.monotonic() - started) * 1000),
    }


async def compile_python(source_dir: str) -> dict[str, Any]:
    """Deterministic syntax check of generated backend code."""
    return await run_command([sys.executable, "-m", "compileall", "-q", "."], cwd=source_dir)
