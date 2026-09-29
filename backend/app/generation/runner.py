"""Build/test command runner: captures stdout, stderr, exit code and duration.

Implements the deterministic battery from Backend Plan §10: pip install,
compileall and pytest for the generated backend, npm install/build for the
generated frontend. Real agent integrations reuse this instead of running
their own commands.
"""

import asyncio
import importlib.util
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from app.generation.contract import check_api_contract

COMMAND_TIMEOUT_SECONDS = 300
# Command output is embedded in TEST_RESULT artifacts, so it is capped to keep
# project documents bounded (npm builds can be extremely verbose).
MAX_OUTPUT_CHARS = 20_000


def _cap(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated {len(text) - MAX_OUTPUT_CHARS} characters]"


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
        "stdout": _cap(stdout.decode(errors="replace")),
        "stderr": _cap(stderr.decode(errors="replace")),
        "durationMs": int((time.monotonic() - started) * 1000),
    }


def tool_available(name: str) -> str | None:
    """Resolved executable path for a build tool, or None when not installed."""
    return shutil.which(name)


def pytest_available() -> bool:
    return importlib.util.find_spec("pytest") is not None


async def pip_install(backend_dir: str) -> dict[str, Any]:
    return await run_command(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=backend_dir
    )


async def compile_python(source_dir: str) -> dict[str, Any]:
    """Deterministic syntax check of generated backend code."""
    return await run_command([sys.executable, "-m", "compileall", "-q", "."], cwd=source_dir)


async def pytest_backend(backend_dir: str) -> dict[str, Any]:
    """Run the generated backend's pytest suite with this interpreter."""
    return await run_command(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "."], cwd=backend_dir
    )


def _npm_path() -> str:
    npm = tool_available("npm")
    if npm is None:
        raise RuntimeError("npm is not available on PATH")
    return npm


async def npm_install(frontend_dir: str) -> dict[str, Any]:
    return await run_command([_npm_path(), "install", "--no-audit", "--no-fund"], cwd=frontend_dir)


async def npm_build(frontend_dir: str) -> dict[str, Any]:
    return await run_command([_npm_path(), "run", "build"], cwd=frontend_dir)


CATEGORY_BY_STEP = {
    "pipInstall": "DEPENDENCY_INSTALL",
    "compile": "COMPILE_ERROR",
    "pytest": "TEST_FAILURE",
    "apiContract": "API_CONTRACT",
    "npmInstall": "BUILD_ERROR",
    "npmBuild": "BUILD_ERROR",
}


def _step(step: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "step": step,
        "status": "PASSED" if result["exitCode"] == 0 else "FAILED",
        "reason": None,
        "category": None if result["exitCode"] == 0 else CATEGORY_BY_STEP[step],
        "result": result,
    }


def _skipped(step: str, reason: str) -> dict[str, Any]:
    return {"step": step, "status": "SKIPPED", "reason": reason, "category": None, "result": None}


def _failed(step: str, reason: str, category: str) -> dict[str, Any]:
    return {
        "step": step,
        "status": "FAILED",
        "reason": reason,
        "category": category,
        "result": None,
    }


async def run_test_battery(
    source_dir: str,
    *,
    run_pip_install: bool = False,
    run_pytest: bool = True,
    run_npm_build: bool = False,
) -> list[dict[str, Any]]:
    """Run the §10 battery in order and return one record per step.

    Records stop at the first failure. Enabled-but-missing npm fails with
    TOOL_UNAVAILABLE; a missing pytest only skips (the deployment image does
    not ship it, so pytest stays a best-effort check).
    """
    backend_dir = os.path.join(source_dir, "backend")
    frontend_dir = os.path.join(source_dir, "frontend")
    steps: list[dict[str, Any]] = []

    if run_pip_install:
        record = _step("pipInstall", await pip_install(backend_dir))
        steps.append(record)
        if record["status"] == "FAILED":
            return steps
    else:
        steps.append(_skipped("pipInstall", "pip install disabled (TESTER_RUN_PIP_INSTALL=false)"))

    record = _step("compile", await compile_python(backend_dir))
    steps.append(record)
    if record["status"] == "FAILED":
        return steps

    if run_pytest:
        if pytest_available():
            record = _step("pytest", await pytest_backend(backend_dir))
            steps.append(record)
            if record["status"] == "FAILED":
                return steps
        else:
            steps.append(_skipped("pytest", "pytest is not installed in this environment"))
    else:
        steps.append(_skipped("pytest", "pytest check disabled (TESTER_RUN_PYTEST=false)"))

    # Functional check (Plan §8): every /api path the generated frontend calls
    # must exist in the generated backend, otherwise the PoC 404s at runtime.
    source = Path(source_dir)
    record = _step("apiContract", check_api_contract(source))
    steps.append(record)
    if record["status"] == "FAILED":
        return steps

    if run_npm_build:
        if tool_available("npm") is None:
            steps.append(
                _failed(
                    "npmInstall",
                    "npm is not available on PATH but TESTER_RUN_NPM_BUILD=true",
                    "TOOL_UNAVAILABLE",
                )
            )
            return steps
        record = _step("npmInstall", await npm_install(frontend_dir))
        steps.append(record)
        if record["status"] == "FAILED":
            return steps
        steps.append(_step("npmBuild", await npm_build(frontend_dir)))
    else:
        steps.append(_skipped("npmInstall", "frontend build disabled (TESTER_RUN_NPM_BUILD=false)"))
        steps.append(_skipped("npmBuild", "frontend build disabled (TESTER_RUN_NPM_BUILD=false)"))
    return steps
