"""LLM-backed agents (DeepSeek, OpenAI-compatible API).

Drop-in replacements for the deterministic stubs behind the same interfaces in
``app.agents.base`` — orchestration, endpoints and contracts are unchanged.
Every agent validates the model output deterministically and raises
``LLMError`` (fail fast) on API, parsing or validation failures; the
generation service turns that into the usual FAILED project state.

The build/test execution stays deterministic (AI Developer Plan §8): the LLM
tester runs the same runner battery as the stub and only uses the model to
turn raw command output into a structured diagnosis.
"""

import json
import logging
from typing import Any

from app import config
from app.agents.base import (
    ArchitectAgent,
    DeveloperAgent,
    RequirementAgent,
    RequirementTurn,
    ReviewerAgent,
    ReviewIssue,
    ReviewResult,
    TesterAgent,
    TestResult,
)
from app.generation import runner
from app.schemas.project import LIST_FIELDS, completion_of, missing_fields
from app.workspace import workspace as ws

logger = logging.getLogger(__name__)

MAX_GENERATED_FILES = 10
MAX_FILE_CHARS = 64_000
MAX_DIAGNOSIS_CHARS = 2_000
# Files every generated PoC must keep regardless of what the model produces:
# a runnable FastAPI app and a runnable React entry (index.html + main.tsx
# mount App.tsx; the template only ships a placeholder package.json).
MINIMAL_FILES = {
    "backend/main.py",
    "frontend/package.json",
    "frontend/index.html",
    "frontend/src/main.tsx",
}


class LLMError(Exception):
    """Raised when the LLM API call fails or its output cannot be trusted."""


class DeepSeekClient:
    """Thin async wrapper over the OpenAI-compatible DeepSeek endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
        thinking: str | None = None,
        client: Any = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else config.LLM_API_KEY
        self.base_url = base_url if base_url is not None else config.LLM_BASE_URL
        self.model = model if model is not None else config.LLM_MODEL
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else config.LLM_TIMEOUT_SECONDS
        )
        self.max_tokens = max_tokens if max_tokens is not None else config.LLM_MAX_TOKENS
        self.reasoning_effort = (
            reasoning_effort if reasoning_effort is not None else config.LLM_REASONING_EFFORT
        )
        self.thinking = thinking if thinking is not None else config.LLM_THINKING
        self._client = client
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
                raise LLMError(
                    "The openai package is required for LLM agents; install it with pip."
                ) from exc
            self._client = AsyncOpenAI(
                api_key=self.api_key, base_url=self.base_url, timeout=self.timeout_seconds
            )

    async def complete(self, system: str, user: str) -> str:
        """One chat completion; returns the assistant message content."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if self.thinking == "enabled":
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            if self.reasoning_effort != "off":
                kwargs["reasoning_effort"] = self.reasoning_effort
        else:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        try:
            choice = response.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMError("LLM response had no message content") from exc
        if getattr(choice, "finish_reason", None) == "length":
            raise LLMError(
                f"LLM output was truncated at max_tokens={self.max_tokens}; "
                "increase LLM_MAX_TOKENS or reduce the requested output"
            )
        if not content or not content.strip():
            raise LLMError("LLM returned an empty message")
        return content


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object in the model output (tolerates code fences)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        cleaned = cleaned.removeprefix("json")
    start = cleaned.find("{")
    if start == -1:
        raise LLMError("LLM output contained no JSON object")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : index + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    # Models embedding code in JSON strings often emit raw
                    # newlines/tabs; strict=False accepts control characters.
                    try:
                        parsed = json.loads(candidate, strict=False)
                    except json.JSONDecodeError as exc:
                        raise LLMError(f"LLM output was not valid JSON: {exc}") from exc
                if not isinstance(parsed, dict):
                    raise LLMError("LLM JSON was not an object")
                return parsed
    raise LLMError("LLM JSON object was not closed")


_REQUIREMENT_SYSTEM = (
    "You are the requirements analyst of an AI PoC builder. Extract project "
    "requirements from the conversation so far. Answer with STRICT JSON only, no "
    'prose: {"requirements": {<field>: <value>...}, "reply": "<your next '
    'message to the user>"}. Field types: "problem" is a string; '
    '"targetUsers", "mainWorkflow", "features", "inputs", "outputs", '
    '"constraints" and "successCriteria" are arrays of short strings. '
    "Include a field only if the conversation states it; never invent facts. In "
    '"reply", ask about the most important missing field, or confirm the '
    "requirements are complete."
)


class LlmRequirementAgent(RequirementAgent):
    """LLM extracts requirement fields; readiness stays deterministic."""

    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self.client = client or DeepSeekClient()

    async def run(
        self, requirements: dict[str, Any], chat: list[dict[str, Any]], message: str
    ) -> RequirementTurn:
        transcript = "\n".join(
            f"{entry.get('role', 'user')}: {entry.get('content', '')}" for entry in chat
        )
        current = json.dumps(requirements, ensure_ascii=False)
        payload = _extract_json(
            await self.client.complete(
                _REQUIREMENT_SYSTEM,
                (
                    f"Known requirements so far (JSON): {current}\n\nConversation:\n{transcript}\n\n"
                    f"New user message: {message}"
                ),
            )
        )
        extracted = payload.get("requirements")
        if not isinstance(extracted, dict):
            raise LLMError("LLM requirements payload lacked a 'requirements' object")
        content = {**requirements}
        for field in extracted:
            if field not in missing_fields(content):
                continue  # only fill missing fields, never overwrite answers
            value = extracted[field]
            if field in LIST_FIELDS:
                if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
                    content[field] = value
            elif isinstance(value, str) and value.strip():
                content[field] = value.strip()
        remaining = missing_fields(content)
        reply = payload.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            reply = (
                "I have enough information to prepare the PoC specification."
                if not remaining
                else f"Could you tell me more about: {remaining[0]}?"
            )
        return RequirementTurn(
            assistant_message=reply.strip(),
            requirements=content,
            completion=completion_of(content),
            missing_fields=remaining,
            ready=not remaining,
        )


class LlmArchitectAgent(ArchitectAgent):
    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self.client = client or DeepSeekClient()

    async def run(self, requirements: dict[str, Any]) -> dict[str, Any]:
        payload = _extract_json(
            await self.client.complete(
                "You are a software architect for small AI PoCs (FastAPI + React + "
                "MongoDB). Given requirements JSON, answer with STRICT JSON only: "
                '{"pages": [{"name", "purpose"}], "apis": [{"method", '
                '"path"}], "entities": [{"name", "fields"}], "services": '
                '[string], "aiCapabilities": [string]}. Keep it minimal but complete.',
                json.dumps(requirements, ensure_ascii=False),
            )
        )
        for key in ("pages", "apis", "entities", "services", "aiCapabilities"):
            if not isinstance(payload.get(key), list):
                raise LLMError(f"LLM architecture JSON lacked array field '{key}'")
        return payload


def _safe_generated_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path or ".." in path:
        return False
    root = path.split("/", 1)[0]
    return root in {"backend", "frontend"} or path == "README.md"


class LlmDeveloperAgent(DeveloperAgent):
    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self.client = client or DeepSeekClient()

    async def run(
        self,
        project_id: str,
        requirements: dict[str, Any],
        architecture: dict[str, Any],
        feedback: list[str] | None = None,
    ) -> list[str]:
        payload = _extract_json(
            await self.client.complete(
                "You are the code generator of an AI PoC builder. Given requirements "
                'and architecture JSON, output STRICT JSON only: {"files": '
                '[{"path": "...", "content": "..."}]}. Rules: paths are '
                "workspace-relative under backend/ or frontend/ (or README.md); the "
                "backend is FastAPI and MUST define backend/main.py with a GET /health "
                "route, and backend/requirements.txt MUST list fastapi and "
                "uvicorn[standard]; the frontend is React and MUST include "
                'frontend/package.json with a "build" script plus react, '
                "react-dom, vite, @vitejs/plugin-react and typescript in its "
                "dependencies/devDependencies, frontend/index.html and "
                "frontend/src/main.tsx mounting frontend/src/App.tsx; at most "
                f"{MAX_GENERATED_FILES} files and at most 120 lines per file; write "
                "tersely, no markdown fences inside content, no comments beyond "
                "one line where essential, no TODO placeholders, and emit valid "
                "JSON (escape newlines inside strings).",
                json.dumps(
                    {
                        "requirements": requirements,
                        "architecture": architecture,
                        "repairFeedback": feedback or [],
                    },
                    ensure_ascii=False,
                ),
            )
        )
        files = payload.get("files")
        if not isinstance(files, list) or not files:
            raise LLMError("LLM developer output lacked a non-empty 'files' array")
        written: list[str] = []
        for entry in files:
            if not isinstance(entry, dict):
                raise LLMError("LLM developer files contained a non-object entry")
            path, content = entry.get("path"), entry.get("content")
            if not isinstance(path, str) or not _safe_generated_path(path):
                raise LLMError(f"LLM developer produced an unsafe path: {path!r}")
            if not isinstance(content, str) or not content.strip():
                raise LLMError(f"LLM developer produced empty content for {path}")
            if len(content) > MAX_FILE_CHARS:
                raise LLMError(f"LLM developer file {path} exceeded the size limit")
            ws.write_file(project_id, path, content)
            written.append(path)
        if len(written) > MAX_GENERATED_FILES:
            raise LLMError("LLM developer exceeded the file count limit")
        missing = MINIMAL_FILES - set(ws.list_files(project_id))
        if missing:
            raise LLMError(
                f"LLM developer output lacks required files: {', '.join(sorted(missing))}"
            )
        return written


_REVIEW_SYSTEM = (
    "You are a strict code reviewer for a generated PoC. Given requirements, "
    "architecture and the list of generated files, answer with STRICT JSON only: "
    '{"status": "PASS"|"FAIL", "issues": [{"id": "REV-001", '
    '"severity": "HIGH"|"MEDIUM"|"LOW", "file": "...", "problem": '
    '"...", "recommendation": "..."}]}. Fail only for real coverage gaps '
    "between architecture and files (missing pages, APIs, entities or services)."
)


class LlmReviewerAgent(ReviewerAgent):
    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self.client = client or DeepSeekClient()

    async def run(
        self, requirements: dict[str, Any], architecture: dict[str, Any], files: list[str]
    ) -> ReviewResult:
        payload = _extract_json(
            await self.client.complete(
                _REVIEW_SYSTEM,
                json.dumps(
                    {"requirements": requirements, "architecture": architecture, "files": files},
                    ensure_ascii=False,
                ),
            )
        )
        status = payload.get("status")
        if status not in {"PASS", "FAIL"}:
            raise LLMError("LLM review JSON had no PASS/FAIL status")
        issues: list[ReviewIssue] = []
        for index, entry in enumerate(payload.get("issues") or []):
            if not isinstance(entry, dict):
                raise LLMError("LLM review issues contained a non-object entry")
            raw_severity = entry.get("severity")
            severity = raw_severity if raw_severity in {"HIGH", "MEDIUM", "LOW"} else "MEDIUM"
            issues.append(
                ReviewIssue(
                    id=str(entry.get("id") or f"REV-{index + 1:03d}"),
                    severity=severity,
                    file=str(entry.get("file") or ""),
                    problem=str(entry.get("problem") or ""),
                    recommendation=str(entry.get("recommendation") or ""),
                )
            )
        return ReviewResult(status=status, issues=issues)


_DIAGNOSIS_SYSTEM = (
    "You are a build/test diagnostician for a generated PoC. Given the failed "
    "build/test step records (command, exit code, stdout, stderr), answer with "
    'STRICT JSON only: {"summary": "<what broke, <= 300 chars>", '
    '"suggestedFix": "<concrete next fix instruction for the code '
    'generator, <= 300 chars>"}. Base everything on the evidence; no guesses.'
)


class LlmTesterAgent(TesterAgent):
    """Deterministic battery + LLM diagnosis of failures (Plan §8 flow)."""

    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self.client = client or DeepSeekClient()

    async def run(self, project_id: str) -> TestResult:
        files = set(ws.list_files(project_id))
        missing = sorted(MINIMAL_FILES - files)
        if missing:
            return TestResult(
                status="FAILED",
                category="MISSING_FILES",
                files=missing,
                summary=f"Missing generated files: {', '.join(missing)}",
                suggested_fix="Re-run the developer step.",
            )
        steps = await runner.run_test_battery(
            str(ws.source_dir(project_id)),
            run_pip_install=config.TESTER_RUN_PIP_INSTALL,
            run_pytest=config.TESTER_RUN_PYTEST,
            run_npm_build=config.TESTER_RUN_NPM_BUILD,
        )
        failure = next((step for step in steps if step["status"] == "FAILED"), None)
        if failure is None:
            return TestResult(
                status="PASSED",
                category=None,
                files=[],
                summary="Build and test battery passed.",
                commands=steps,
            )
        result = await self._diagnose(failure)
        return TestResult(
            status="FAILED",
            category=failure.get("category") or "BUILD_ERROR",
            files=[],
            summary=result["summary"],
            suggested_fix=result["suggestedFix"],
            commands=steps,
        )

    async def _diagnose(self, failure: dict[str, Any]) -> dict[str, str]:
        """LLM diagnosis of the failed step; falls back to raw evidence."""
        fallback_detail = (failure.get("result") or {}).get("stderr") or (
            failure.get("reason") or "build/test step failed"
        )
        fallback = {
            "summary": fallback_detail[:MAX_DIAGNOSIS_CHARS],
            "suggestedFix": "Inspect the failing command output and fix the generated code.",
        }
        try:
            payload = _extract_json(
                await self.client.complete(
                    _DIAGNOSIS_SYSTEM,
                    json.dumps(failure, ensure_ascii=False)[: MAX_DIAGNOSIS_CHARS * 8],
                )
            )
        except LLMError:
            logger.warning("LLM diagnosis failed; using raw test output", exc_info=True)
            return fallback
        summary = payload.get("summary")
        fix = payload.get("suggestedFix")
        if not isinstance(summary, str) or not summary.strip():
            return fallback
        return {
            "summary": summary.strip()[:MAX_DIAGNOSIS_CHARS],
            "suggestedFix": (
                fix.strip() if isinstance(fix, str) and fix.strip() else fallback["suggestedFix"]
            ),
        }


def build_llm_agents() -> tuple[
    LlmArchitectAgent, LlmDeveloperAgent, LlmReviewerAgent, LlmTesterAgent
]:
    """Fail fast at wiring time when LLM mode is on without credentials."""
    if not config.LLM_API_KEY:
        raise RuntimeError("LLM_ENABLED=true requires LLM_API_KEY in the environment")
    client = DeepSeekClient()
    return (
        LlmArchitectAgent(client),
        LlmDeveloperAgent(client),
        LlmReviewerAgent(client),
        LlmTesterAgent(client),
    )
