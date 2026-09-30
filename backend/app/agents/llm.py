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
from app.agents.stubs import QUESTION_PER_FIELD
from app.generation import runner
from app.generation.spec import (
    LAYOUTS,
    MAX_SERIES,
    MAX_WIDGETS,
    THEMES,
    prune_filters,
    validate_spec,
)
from app.schemas.project import LIST_FIELDS, completion_of, missing_fields
from app.workspace import workspace as ws

logger = logging.getLogger(__name__)

MAX_GENERATED_FILES = 14
MAX_FILE_CHARS = 64_000
MAX_DIAGNOSIS_CHARS = 2_000

# The only frontend file the generator writes; everything visual is
# platform-owned in the template's frontend/src/kit/.
DASHBOARD_SPEC_PATH = "frontend/src/dashboard.config.json"

# Files every generated PoC must have. The frontend entry, package.json and the
# design system all come from the template now, and the platform writes the
# spec, so the generator owes only a runnable FastAPI app.
MINIMAL_FILES = {"backend/main.py"}


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
    "Include a field only if the conversation states it; never invent facts. The "
    'user message lists which fields are still missing: in "reply", ask about '
    "the FIRST one listed, and never say the requirements are complete while any "
    "field is still missing."
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
        # Name the outstanding fields explicitly. Left to judge "the most
        # important missing field" on its own, the model skipped `features`
        # entirely and then declared the requirements complete.
        still_missing = ", ".join(missing_fields(requirements)) or "nothing"
        payload = _extract_json(
            await self.client.complete(
                _REQUIREMENT_SYSTEM,
                (
                    f"Known requirements so far (JSON): {current}\n"
                    f"Still missing, in priority order: {still_missing}\n\n"
                    f"Conversation:\n{transcript}\n\n"
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
                else _question_for(remaining[0])
            )
        elif remaining:
            # Readiness is deterministic, but the model would answer "the
            # requirements are complete" while a field was still empty. The user
            # was then told they were finished while Generate stayed blocked,
            # with nothing left to answer.
            #
            # A reply that asks something is left alone even if it is about a
            # different missing field — it still moves the user forward. Only a
            # reply that asks nothing, or claims to be done, gets the question.
            reply = reply.strip()
            lowered = reply.lower()
            claims_done = any(
                phrase in lowered
                for phrase in ("requirements are complete", "have enough", "nothing missing")
            )
            if claims_done or "?" not in reply:
                question = _question_for(remaining[0])
                if question.rstrip("?").lower() not in lowered:
                    reply = f"{reply}\n\n{question}"
        return RequirementTurn(
            assistant_message=reply.strip(),
            requirements=content,
            completion=completion_of(content),
            missing_fields=remaining,
            ready=not remaining,
        )


_ARCHITECT_SYSTEM = (
    "You design DASHBOARDS, and nothing else. Whatever the requirements "
    "describe, express it as a dashboard that reports on it: numbers, trends, "
    "breakdowns, records, status. Never propose chat interfaces, assistants, "
    "wizards or content editors.\n"
    "Given requirements JSON, answer with STRICT JSON only — the dashboard "
    'spec: {"title", "subtitle", "layout", "widgets": [...], "filters": [...]}.\n'
    f"'layout' is exactly one of {sorted(LAYOUTS)}: kpi-overview for headline "
    "numbers over time, analytics-breakdown to compare a trend against "
    "categories, operations-monitor for health and alerts, records-workspace "
    "for browsing and filtering records.\n"
    'Every widget has "kind" and "endpoint" (a path under /api/). By kind: '
    '"stat" needs label and field, plus optional deltaField and trendField; '
    '"line" needs title, xField and series[{label, field}]; "bar" needs title, '
    'categoryField and series[{label, field}]; "table" needs title and '
    'columns[{label, field}]; "status" needs title, labelField and levelField '
    "(values good|warning|serious|critical).\n"
    f"At most {MAX_WIDGETS} widgets and {MAX_SERIES} series per chart. Choose "
    "the form by the data's job: a single headline number is a stat, change "
    "over time is a line, comparison across categories is a bar. Never two "
    "measures of different scale in one chart — use two charts."
)


class LlmArchitectAgent(ArchitectAgent):
    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self.client = client or DeepSeekClient()

    async def run(self, requirements: dict[str, Any]) -> dict[str, Any]:
        payload = _extract_json(
            await self.client.complete(
                _ARCHITECT_SYSTEM, json.dumps(requirements, ensure_ascii=False)
            )
        )
        # Filters are optional; a malformed one is dropped rather than failing
        # the run, since the dashboard is complete without it.
        dropped = prune_filters(payload)
        if dropped:
            logger.info("Dropped %d unusable filter(s) from the dashboard spec", dropped)
        errors = validate_spec(payload)
        if errors:
            raise LLMError("LLM dashboard spec is invalid: " + "; ".join(errors[:6]))
        # Carried through so the generated dashboard opens on the theme the user
        # picked, whatever the model put in the spec.
        if requirements.get("theme") in THEMES:
            payload["theme"] = requirements["theme"]
        return payload


def _question_for(field: str) -> str:
    """The question that unblocks a missing requirement field."""
    return QUESTION_PER_FIELD.get(field, f"Could you tell me about {field}?")


def _safe_generated_path(path: str) -> bool:
    """Where the generator may write.

    The frontend is platform-owned: only the dashboard spec is writable, so the
    design system in frontend/src/kit/ cannot be overwritten by a model that
    decides to bring its own CSS.
    """
    if not path or path.startswith("/") or "\\" in path or ".." in path:
        return False
    if path == "README.md":
        return True
    # The spec is written by the platform from the validated architecture, not
    # by the model, so even that path is closed.
    return path.split("/", 1)[0] == "backend"


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
                "You are the code generator of an AI dashboard builder. Given "
                "requirements and a dashboard spec, output STRICT JSON only: "
                '{"files": [{"path": "...", "content": "..."}]}.\n'
                "YOU DO NOT WRITE ANY UI. The dashboard is rendered by the "
                "platform's own component kit from the spec, which the platform "
                "writes — do not output it. Write only:\n"
                "backend/ — a FastAPI app. backend/main.py MUST define GET "
                "/health, and MUST implement every /api endpoint named by a "
                "widget's 'endpoint', returning exactly the fields that widget "
                "reads. backend/requirements.txt MUST list fastapi and "
                "uvicorn[standard].\n"
                "Endpoint payload shapes: a 'stat' endpoint returns one object "
                "with its field, deltaField and trendField (trend is an array of "
                "numbers); 'line', 'bar', 'table' and 'status' endpoints return "
                "an ARRAY of objects whose keys are exactly the fields the widget "
                "names. Seed 6-12 rows of realistic sample data in code so the "
                "dashboard is populated on first load with no database.\n"
                "Never write any frontend file — no CSS, no components, no "
                "index.html. The whole frontend is platform-owned and any "
                "frontend path is rejected.\n"
                f"At most {MAX_GENERATED_FILES} files, 120 lines per file, write "
                "tersely, no markdown fences inside content, no TODO "
                "placeholders, and emit valid JSON (escape newlines in strings).",
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
        # Validate everything BEFORE writing anything: a failure must never
        # leave a half-written workspace behind.
        validated: list[tuple[str, str]] = []
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
            validated.append((path, content))
        if len(validated) > MAX_GENERATED_FILES:
            # Models are bad at counting: keep required files plus the first
            # entries within budget instead of failing the whole pipeline.
            # The reviewer sees the trimmed coverage and the repair loop can
            # ask the developer to converge.
            prioritized = [
                v for v in validated if v[0] in MINIMAL_FILES or v[0] == "backend/requirements.txt"
            ]
            rest = [v for v in validated if v not in prioritized]
            dropped = validated[MAX_GENERATED_FILES:]
            logger.warning(
                "LLM developer produced %d files; keeping %d, dropping: %s",
                len(validated),
                MAX_GENERATED_FILES,
                ", ".join(path for path, _ in dropped) or "none",
            )
            validated = (prioritized + rest)[:MAX_GENERATED_FILES]
        written: list[str] = []
        for path, content in validated:
            ws.write_file(project_id, path, content)
            written.append(path)

        # The spec comes from the validated architecture, not from the model.
        # Writing it here means the rendered dashboard always matches what the
        # architect designed, with no chance of a transcription slip.
        ws.write_file(
            project_id,
            DASHBOARD_SPEC_PATH,
            json.dumps(architecture, ensure_ascii=False, indent=2) + "\n",
        )
        written.append(DASHBOARD_SPEC_PATH)

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
