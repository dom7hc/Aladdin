"""LLM agents (DeepSeek): contract tests with a fake client — never network."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents import llm
from app.agents.base import ReviewResult
from app.agents.llm import (
    ClaudeClient,
    DeepSeekClient,
    FallbackClient,
    LlmArchitectAgent,
    LlmDeveloperAgent,
    LLMError,
    LlmRequirementAgent,
    LlmReviewerAgent,
    LlmTesterAgent,
    _extract_json,
    build_llm_agents,
)
from app.agents.stubs import (
    QUESTION_PER_FIELD,
    StubDeveloperAgent,
    StubRequirementAgent,
)
from app.schemas.project import empty_requirements
from app.workspace import workspace as ws


class FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = SimpleNamespace(content=content)
        self.finish_reason = finish_reason


class FakeResponse:
    def __init__(self, content, finish_reason="stop"):
        self.choices = [FakeChoice(content, finish_reason)]


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            return FakeResponse(*item)
        return FakeResponse(item)


class FakeClient:
    def __init__(self, *responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(list(responses)))


@pytest.fixture()
def llm_workspace(tmp_path: Path, monkeypatch) -> str:
    """Hermetic generated workspace under tmp_path."""
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path / "generated"))
    return "abcdef0123456789abcdef01"


def _scaffold_frontend(project_id: str) -> None:
    """Files an LLM developer run must add on top of the template."""
    ws.write_file(project_id, "frontend/index.html", "<!doctype html>\n")
    ws.write_file(project_id, "frontend/src/main.tsx", "import App from './App'\n")


def test_deepseek_client_returns_content_and_sends_model():
    client = DeepSeekClient(client=FakeClient("hi"))
    assert asyncio.run(client.complete("sys", "user")) == "hi"
    call = client._client.chat.completions.calls[0]
    assert call["model"] == client.model
    assert call["messages"][0]["role"] == "system"
    assert call["stream"] is False


def test_deepseek_client_wraps_errors_as_llm_error():
    client = DeepSeekClient(client=FakeClient(RuntimeError("boom")))
    with pytest.raises(LLMError, match="LLM request failed"):
        asyncio.run(client.complete("sys", "user"))


def test_extract_json_tolerates_fences_prose_and_nested_strings():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('Sure: {"a": "{\\"b\\": 1}"} done') == {"a": '{"b": 1}'}
    with pytest.raises(LLMError):
        _extract_json("no json here")
    with pytest.raises(LLMError):
        _extract_json('{"open": ')


def test_extract_json_tolerates_raw_newlines_in_strings():
    raw = '{"files": [{"path": "a.py", "content": "line1\nline2\ttab"}]}'
    assert _extract_json(raw)["files"][0]["content"] == "line1\nline2\ttab"


def test_deepseek_client_reports_truncation():
    client = DeepSeekClient(client=FakeClient(("partial json {", "length")))
    with pytest.raises(LLMError, match="truncated"):
        asyncio.run(client.complete("sys", "user"))


def test_deepseek_client_disables_thinking_by_default():
    client = DeepSeekClient(client=FakeClient("ok"))
    asyncio.run(client.complete("sys", "user"))
    call = client._client.chat.completions.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in call


def test_deepseek_client_enables_thinking_with_effort():
    client = DeepSeekClient(client=FakeClient("ok"), thinking="enabled", reasoning_effort="low")
    asyncio.run(client.complete("sys", "user"))
    call = client._client.chat.completions.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}
    assert call["reasoning_effort"] == "low"


def test_deepseek_client_sends_reasoning_effort():
    client = DeepSeekClient(client=FakeClient("ok"), thinking="enabled", reasoning_effort="high")
    asyncio.run(client.complete("sys", "user"))
    assert client._client.chat.completions.calls[0]["reasoning_effort"] == "high"


def test_deepseek_client_omits_thinking_field_for_foundry():
    client = DeepSeekClient(client=FakeClient("ok"), thinking="omit", reasoning_effort="low")
    asyncio.run(client.complete("sys", "user"))
    call = client._client.chat.completions.calls[0]
    assert "extra_body" not in call
    assert "reasoning_effort" not in call


def test_deepseek_client_omits_reasoning_effort_when_off():
    client = DeepSeekClient(client=FakeClient("ok"), thinking="enabled", reasoning_effort="off")
    asyncio.run(client.complete("sys", "user"))
    assert "reasoning_effort" not in client._client.chat.completions.calls[0]


async def test_requirement_agent_fills_missing_only_and_stays_deterministic():
    client = FakeClient(
        json.dumps(
            {
                "requirements": {
                    "targetUsers": ["Accountants"],
                    "features": ["upload", "review"],
                    "idea": "hijack attempt",
                },
                "reply": "What inputs does it receive?",
            }
        )
    )
    turn = await LlmRequirementAgent(DeepSeekClient(client=client)).run(
        empty_requirements("Invoice AI"), [], "For accountants; upload and review invoices"
    )
    assert turn.requirements["targetUsers"] == ["Accountants"]
    assert turn.requirements["features"] == ["upload", "review"]
    assert "idea" not in turn.requirements or turn.requirements["idea"] != "hijack attempt"
    assert turn.ready is False
    assert turn.missing_fields  # more fields still missing
    assert turn.assistant_message == "What inputs does it receive?"


async def test_requirement_agent_reports_ready_and_fallback_reply():
    client = FakeClient(json.dumps({"requirements": {}, "reply": "  "}))
    complete: dict[str, Any] = {
        "problem": "p",
        "targetUsers": ["u"],
        "mainWorkflow": ["w"],
        "features": ["x"],
        "inputs": ["x"],
        "outputs": ["x"],
        "successCriteria": ["x"],
    }
    turn = await LlmRequirementAgent(DeepSeekClient(client=client)).run(complete, [], "that is all")
    assert turn.ready is True
    assert turn.missing_fields == []
    assert turn.assistant_message.startswith("I have enough information")


async def test_requirement_agent_rejects_payload_without_requirements():
    client = FakeClient(json.dumps({"reply": "hi"}))
    with pytest.raises(LLMError, match="requirements"):
        await LlmRequirementAgent(DeepSeekClient(client=client)).run(
            empty_requirements("x"), [], "y"
        )


async def test_autofill_fills_missing_fields_from_the_model():
    client = FakeClient(
        json.dumps(
            {
                "targetUsers": ["Accountants"],
                "mainWorkflow": ["Upload", "Review", "Export"],
                "features": ["Upload invoices"],
                "inputs": ["PDF invoices"],
                "outputs": ["Dashboard"],
                "successCriteria": ["Faster reviews"],
            }
        )
    )
    turn = await LlmRequirementAgent(DeepSeekClient(client=client)).autofill(
        empty_requirements("Invoice AI"), []
    )
    assert turn.ready is True
    assert turn.missing_fields == []
    assert turn.requirements["targetUsers"] == ["Accountants"]


async def test_autofill_falls_back_to_defaults_when_the_llm_fails():
    client = FakeClient(RuntimeError("boom"))
    turn = await LlmRequirementAgent(DeepSeekClient(client=client)).autofill(
        empty_requirements("Invoice AI"), []
    )
    assert turn.ready is True
    assert turn.requirements["mainWorkflow"]  # deterministic best-practice defaults


async def test_stub_autofill_fills_every_missing_field():
    turn = await StubRequirementAgent().autofill(empty_requirements("x"), [])
    assert turn.ready is True
    assert turn.missing_fields == []


VALID_SPEC = {
    "title": "Orders",
    "layout": "kpi-overview",
    "widgets": [
        {"kind": "stat", "endpoint": "/api/metrics", "label": "Orders", "field": "total"},
        {
            "kind": "line",
            "endpoint": "/api/series",
            "title": "Orders over time",
            "xField": "day",
            "series": [{"label": "Orders", "field": "value"}],
        },
    ],
}


def _without_look(spec: dict) -> dict:
    """The spec as the model wrote it: the architect adds the look itself."""
    return {k: v for k, v in spec.items() if k != "designSystem"}


async def test_architect_agent_returns_a_valid_dashboard_spec():
    agent = LlmArchitectAgent(DeepSeekClient(client=FakeClient(json.dumps(VALID_SPEC))))
    spec = await agent.run(empty_requirements("x"))
    # The model chose no look, so the design brief's first picks fill it in.
    design_system = spec.pop("designSystem")
    assert spec == VALID_SPEC
    assert set(design_system) == {"palette", "fonts", "style"}


async def test_architect_sends_the_design_brief_and_fills_the_look_from_it():
    """ui-ux-pro-max's rules for the industry reach the model, and an invented
    id is replaced by the brief's pick rather than the platform default."""
    client = FakeClient(
        json.dumps({**VALID_SPEC, "designSystem": {"palette": "neon", "style": "flat-design"}})
    )
    agent = LlmArchitectAgent(DeepSeekClient(client=client))
    requirements = {**empty_requirements("x"), "problem": "Attrition and headcount by team"}
    spec = await agent.run(requirements)

    sent = json.loads(client.chat.completions.calls[0]["messages"][1]["content"])
    assert sent["designBrief"]["category"] == "Job Board/Recruitment"
    assert sent["designBrief"]["avoid"]
    assert spec["designSystem"]["style"] == "flat-design"
    assert spec["designSystem"]["palette"] == "job-board-recruitment"


async def test_architect_agent_rejects_a_non_dashboard_spec():
    """An unknown layout must fail the run, not render an empty page. The model
    gets one correction re-ask (which also fails here), then the run dies."""
    bad = {**VALID_SPEC, "layout": "chatbot"}
    agent = LlmArchitectAgent(DeepSeekClient(client=FakeClient(json.dumps(bad), json.dumps(bad))))
    with pytest.raises(LLMError, match="layout"):
        await agent.run(empty_requirements("x"))


async def test_architect_agent_honours_the_users_theme():
    """The theme the user picked wins over whatever the model chose."""
    agent = LlmArchitectAgent(
        DeepSeekClient(client=FakeClient(json.dumps({**VALID_SPEC, "theme": "rose"})))
    )
    spec = await agent.run({**empty_requirements("x"), "theme": "teal"})
    assert spec["theme"] == "teal"


async def test_architect_reasks_once_on_invalid_json():
    """Observed live: a transient JSON slip at the developer step failed the
    whole project; the model gets one correction attempt, then fail fast."""
    client = FakeClient(
        '{"title": "Orders", "layout": "kpi-overview", "widgets": [', json.dumps(VALID_SPEC)
    )
    spec = await LlmArchitectAgent(DeepSeekClient(client=client)).run(empty_requirements("x"))
    assert _without_look(spec) == VALID_SPEC
    assert len(client.chat.completions.calls) == 2
    retry = client.chat.completions.calls[1]["messages"][1]["content"]
    assert "not valid JSON" in retry


async def test_architect_reasks_once_on_an_invalid_spec():
    bad = {**VALID_SPEC, "widgets": [{"kind": "stat", "label": "x"}]}  # endpoint+field missing
    client = FakeClient(json.dumps(bad), json.dumps(VALID_SPEC))
    spec = await LlmArchitectAgent(DeepSeekClient(client=client)).run(empty_requirements("x"))
    assert _without_look(spec) == VALID_SPEC
    assert len(client.chat.completions.calls) == 2
    retry = client.chat.completions.calls[1]["messages"][1]["content"]
    assert "'endpoint'" in retry  # the problem is named to the model


async def test_architect_fails_after_the_second_invalid_spec():
    bad = {**VALID_SPEC, "widgets": [{"kind": "stat", "label": "x"}]}
    client = FakeClient(json.dumps(bad), json.dumps(bad))
    with pytest.raises(LLMError, match="dashboard spec is invalid"):
        await LlmArchitectAgent(DeepSeekClient(client=client)).run(empty_requirements("x"))
    assert len(client.chat.completions.calls) == 2  # bounded: never more than one re-ask


async def test_truncation_is_not_reasked():
    client = FakeClient(("partial {", "length"), json.dumps(VALID_SPEC))
    with pytest.raises(LLMError, match="truncated"):
        await LlmArchitectAgent(DeepSeekClient(client=client)).run(empty_requirements("x"))
    assert len(client.chat.completions.calls) == 1


async def test_developer_reasks_once_on_invalid_json(llm_workspace: str):
    files = [{"path": "backend/main.py", "content": "app = 1\n"}]
    client = FakeClient('{"files": [broken', json.dumps({"files": files}))
    written = await LlmDeveloperAgent(DeepSeekClient(client=client)).run(
        llm_workspace, {}, VALID_SPEC
    )
    assert "backend/main.py" in written
    assert len(client.chat.completions.calls) == 2


async def test_developer_agent_writes_backend_and_the_platform_writes_the_spec(llm_workspace: str):
    files = [
        {"path": "backend/main.py", "content": "from fastapi import FastAPI\napp = FastAPI()\n"},
        {"path": "backend/requirements.txt", "content": "fastapi\n"},
    ]
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
    written = await agent.run(llm_workspace, {}, VALID_SPEC)

    assert ws.read_file(llm_workspace, "backend/main.py").startswith("from fastapi")
    # The spec is ours, not the model's: it must match the architecture exactly,
    # plus the design system as resolved (defaults here, since none was chosen).
    assert llm.DASHBOARD_SPEC_PATH in written
    spec = json.loads(ws.read_file(llm_workspace, llm.DASHBOARD_SPEC_PATH))
    design_system = spec.pop("designSystem")
    assert spec == VALID_SPEC
    assert design_system == {
        "palette": "saas-general",
        "fonts": "modern-professional",
        "style": "soft-ui-evolution",
    }


async def test_developer_resolves_the_chosen_look_into_the_spec(llm_workspace: str):
    """A known style is kept; an invented one falls back rather than failing."""
    files = [{"path": "backend/main.py", "content": "app = None\n"}]
    for chosen, expected in (
        ("glassmorphism", "glassmorphism"),
        ("neon-vapor", "soft-ui-evolution"),
    ):
        architecture = {**VALID_SPEC, "designSystem": {"style": chosen}}
        agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
        await agent.run(llm_workspace, {}, architecture)
        spec = json.loads(ws.read_file(llm_workspace, llm.DASHBOARD_SPEC_PATH))
        assert spec["designSystem"]["style"] == expected


async def test_developer_agent_accepts_empty_package_markers(llm_workspace: str):
    """Observed live: models emit empty __init__.py package markers, which is
    valid Python — that exact case FAILED two production runs."""
    files = [
        {"path": "backend/main.py", "content": "from fastapi import FastAPI\napp = FastAPI()\n"},
        {"path": "backend/requirements.txt", "content": "fastapi\n"},
        {"path": "backend/__init__.py", "content": ""},
        {"path": "backend/tests/__init__.py", "content": ""},
    ]
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
    written = await agent.run(llm_workspace, {}, VALID_SPEC)
    assert "backend/tests/__init__.py" in written
    assert ws.read_file(llm_workspace, "backend/tests/__init__.py") == ""

    # The guard stays for real code files.
    empty_main = [{"path": "backend/main.py", "content": ""}]
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": empty_main}))))
    with pytest.raises(LLMError, match="empty content"):
        await agent.run(llm_workspace, {}, VALID_SPEC)


async def test_developer_agent_rejects_every_frontend_path(llm_workspace: str):
    """The design system is platform-owned; a model bringing its own CSS fails."""
    for path in ("frontend/src/App.tsx", "frontend/src/kit/theme.css", "frontend/package.json"):
        files = [{"path": "backend/main.py", "content": "x"}, {"path": path, "content": "x"}]
        agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
        with pytest.raises(LLMError, match="unsafe path"):
            await agent.run(llm_workspace, {}, VALID_SPEC)


async def test_developer_agent_rejects_unsafe_paths(llm_workspace: str):
    files = [
        {"path": "backend/main.py", "content": "x"},
        {"path": "frontend/package.json", "content": "x"},
        {"path": "../escape.py", "content": "x"},
    ]
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
    with pytest.raises(LLMError, match="unsafe path"):
        await agent.run(llm_workspace, {}, VALID_SPEC)
    assert ws.list_files(llm_workspace) == []  # nothing written on failure


async def test_developer_agent_truncates_overflow_keeping_required(llm_workspace: str):
    files: list[dict[str, str]] = [
        {"path": f"backend/extra_{i}.py", "content": "x"} for i in range(14)
    ]
    files.insert(0, {"path": "backend/main.py", "content": "app = 1\n"})
    files.append({"path": "backend/requirements.txt", "content": "fastapi\n"})
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
    written = await agent.run(llm_workspace, {}, VALID_SPEC)
    # The platform writes the spec and the design tokens on top of the model's
    # budgeted files.
    assert len(written) == llm.MAX_GENERATED_FILES + 2
    for required in (
        "backend/main.py",
        "backend/requirements.txt",
        llm.DASHBOARD_SPEC_PATH,
        llm.DESIGN_CSS_PATH,
    ):
        assert required in written


async def test_developer_agent_requires_minimal_files(llm_workspace: str):
    files = [{"path": "backend/helpers.py", "content": "x"}]
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
    with pytest.raises(LLMError, match="backend/main.py"):
        await agent.run(llm_workspace, {}, VALID_SPEC)


async def test_reviewer_agent_maps_pass_and_clamps_severity():
    payload = {
        "status": "PASS",
        "issues": [{"id": "REV-001", "severity": "EXTREME", "file": "a", "problem": "p"}],
    }
    result = await LlmReviewerAgent(DeepSeekClient(client=FakeClient(json.dumps(payload)))).run(
        {}, {}, ["backend/main.py"]
    )
    assert isinstance(result, ReviewResult)
    assert result.status == "PASS"
    assert result.issues[0].severity == "MEDIUM"


async def test_reviewer_agent_rejects_unknown_status():
    client = FakeClient(json.dumps({"status": "MAYBE", "issues": []}))
    with pytest.raises(LLMError, match="PASS/FAIL"):
        await LlmReviewerAgent(DeepSeekClient(client=client)).run({}, {}, [])


async def test_tester_agent_passes_without_llm_call(llm_workspace: str):
    ws.copy_template(llm_workspace)
    await StubDeveloperAgent().run(llm_workspace, {}, {})
    _scaffold_frontend(llm_workspace)
    client = FakeClient()  # empty: any LLM call would raise IndexError
    result = await LlmTesterAgent(DeepSeekClient(client=client)).run(llm_workspace)
    assert result.status == "PASSED"
    assert client.chat.completions.calls == []


async def test_tester_agent_uses_llm_diagnosis_on_failure(llm_workspace: str):
    ws.copy_template(llm_workspace)
    await StubDeveloperAgent().run(llm_workspace, {}, {})
    _scaffold_frontend(llm_workspace)
    ws.write_file(llm_workspace, "backend/broken.py", "def oops(:\n")
    diagnosis = json.dumps(
        {"summary": "Syntax error in broken.py", "suggestedFix": "Fix the function signature"}
    )
    result = await LlmTesterAgent(DeepSeekClient(client=FakeClient(diagnosis))).run(llm_workspace)
    assert result.status == "FAILED"
    assert result.category == "COMPILE_ERROR"
    assert result.summary == "Syntax error in broken.py"
    assert result.suggested_fix == "Fix the function signature"
    assert result.commands


async def test_tester_agent_falls_back_to_raw_output_when_diagnosis_fails(
    llm_workspace: str,
):
    ws.copy_template(llm_workspace)
    await StubDeveloperAgent().run(llm_workspace, {}, {})
    _scaffold_frontend(llm_workspace)
    ws.write_file(llm_workspace, "backend/broken.py", "def oops(:\n")
    result = await LlmTesterAgent(DeepSeekClient(client=FakeClient("not json"))).run(llm_workspace)
    assert result.status == "FAILED"
    assert result.summary  # raw evidence, not the unparseable model reply
    assert "not json" not in result.summary


async def test_tester_agent_missing_minimal_files(llm_workspace: str):
    result = await LlmTesterAgent(DeepSeekClient(client=FakeClient())).run(llm_workspace)
    assert result.status == "FAILED"
    assert result.category == "MISSING_FILES"
    assert "backend/main.py" in result.files


def test_build_llm_agents_requires_api_key(monkeypatch):
    monkeypatch.setattr(llm.config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm.config, "LLM_API_KEY", "")
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        build_llm_agents()


def test_build_llm_agents_returns_llm_types(monkeypatch):
    monkeypatch.setattr(llm.config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm.config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(llm.config, "CLAUDE_FOUNDRY_RESOURCE", "")
    architect, developer, reviewer, tester = build_llm_agents()
    assert isinstance(architect, LlmArchitectAgent)
    assert isinstance(architect.client, DeepSeekClient)
    assert isinstance(developer, LlmDeveloperAgent)
    assert isinstance(reviewer, LlmReviewerAgent)
    assert isinstance(tester, LlmTesterAgent)


def test_build_llm_agents_gives_only_the_architect_claude(monkeypatch):
    monkeypatch.setattr(llm.config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm.config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(llm.config, "CLAUDE_API_KEY", "test-key")
    monkeypatch.setattr(llm.config, "CLAUDE_FOUNDRY_RESOURCE", "test-resource")
    architect, developer, reviewer, tester = build_llm_agents()
    assert isinstance(architect.client, FallbackClient)
    assert isinstance(architect.client.primary, ClaudeClient)
    assert isinstance(architect.client.secondary, DeepSeekClient)
    for agent in (developer, reviewer, tester):
        assert isinstance(agent.client, DeepSeekClient)


class FakeAnthropicMessages:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _claude_response(text, stop_reason="end_turn", category=None):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category) if category else None,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
    )


def _claude(*responses) -> ClaudeClient:
    return ClaudeClient(
        client=SimpleNamespace(messages=FakeAnthropicMessages(*responses)), model="claude-test"
    )


async def test_claude_client_returns_text_and_sends_adaptive_thinking():
    client = _claude(_claude_response('{"ok": true}'))
    assert await client.complete("sys", "user") == '{"ok": true}'
    call = client._client.messages.calls[0]
    assert call["model"] == "claude-test"
    assert call["system"] == "sys"
    assert call["messages"] == [{"role": "user", "content": "user"}]
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": client.effort}


@pytest.mark.parametrize(
    ("response", "match"),
    [
        (_claude_response("", stop_reason="refusal", category="cyber"), "declined"),
        (_claude_response("{", stop_reason="max_tokens"), "truncated"),
        (_claude_response("   "), "empty"),
        (RuntimeError("boom"), "Claude request failed"),
    ],
)
async def test_claude_client_raises_llm_error(response, match):
    with pytest.raises(LLMError, match=match):
        await _claude(response).complete("sys", "user")


async def test_fallback_client_uses_secondary_when_primary_fails():
    secondary = DeepSeekClient(client=FakeClient("from deepseek"))
    fallback = FallbackClient(_claude(RuntimeError("quota")), secondary)
    assert await fallback.complete("sys", "user") == "from deepseek"


async def test_architect_designs_with_claude():
    agent = LlmArchitectAgent(_claude(_claude_response(json.dumps(VALID_SPEC))))
    assert _without_look(await agent.run(empty_requirements("x"))) == VALID_SPEC


async def test_requirement_agent_never_claims_complete_while_blocked():
    """A user must never be told they are finished while Generate is blocked.

    Observed in production: the model answered "The requirements are complete"
    with `features` still empty, so the project sat at 86% and the user had
    nothing left to answer. Readiness is deterministic, so the reply must
    always end on the question that unblocks it.
    """
    filled = empty_requirements("HR assistant")
    filled.update(
        targetUsers=["HR staff"],
        mainWorkflow=["Ask a question", "Get an answer"],
        inputs=["A question"],
        outputs=["An answer"],
        successCriteria=["Answers are grounded"],
    )
    client = FakeClient(
        json.dumps(
            {"requirements": {}, "reply": "Thanks for confirming. The requirements are complete."}
        )
    )
    turn = await LlmRequirementAgent(DeepSeekClient(client=client)).run(filled, [], "nothing")

    assert turn.ready is False
    assert turn.missing_fields == ["features"]
    # The model's own words are kept, but the blocking question is appended.
    assert "The requirements are complete." in turn.assistant_message
    assert QUESTION_PER_FIELD["features"] in turn.assistant_message


async def test_requirement_agent_does_not_duplicate_a_question_it_already_asked():
    filled = empty_requirements("HR assistant")
    filled.update(
        targetUsers=["HR staff"],
        mainWorkflow=["Ask", "Answer"],
        inputs=["A question"],
        outputs=["An answer"],
        successCriteria=["Grounded"],
    )
    client = FakeClient(json.dumps({"requirements": {}, "reply": QUESTION_PER_FIELD["features"]}))
    turn = await LlmRequirementAgent(DeepSeekClient(client=client)).run(filled, [], "go on")
    assert turn.assistant_message.count(QUESTION_PER_FIELD["features"]) == 1


async def test_developer_never_overwrites_the_uploaded_data(llm_workspace: str):
    """The platform writes the user's rows; a model echoing the file is ignored."""
    ws.write_file(llm_workspace, llm.DATASET_PATH, '{"rows": ["real"]}')
    files = [
        {"path": "backend/main.py", "content": "app = None\n"},
        {"path": llm.DATASET_PATH, "content": '{"rows": ["invented"]}'},
    ]
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
    written = await agent.run(llm_workspace, {}, VALID_SPEC)
    assert llm.DATASET_PATH not in written
    assert json.loads(ws.read_file(llm_workspace, llm.DATASET_PATH)) == {"rows": ["real"]}


async def test_repair_sends_the_current_backend_and_keeps_omitted_files(llm_workspace: str):
    """A blind repair rewrote main.py from memory and lost seven endpoints."""
    ws.write_file(llm_workspace, "backend/main.py", "app = 'first draft'\n")
    ws.write_file(llm_workspace, "backend/crud.py", "router = 'kept'\n")
    ws.write_file(llm_workspace, llm.DATASET_PATH, '{"rows": []}')
    fixed = [{"path": "backend/main.py", "content": "app = 'fixed'\n"}]
    client = FakeClient(json.dumps({"files": fixed}))
    agent = LlmDeveloperAgent(DeepSeekClient(client=client))
    await agent.run(llm_workspace, {}, VALID_SPEC, ["GET /api/orders missing"])

    sent = json.loads(client.chat.completions.calls[0]["messages"][1]["content"])
    assert sent["currentFiles"]["backend/crud.py"] == "router = 'kept'\n"
    assert llm.DATASET_PATH not in sent["currentFiles"], "the rows are not code"
    assert ws.read_file(llm_workspace, "backend/main.py") == "app = 'fixed'\n"
    assert ws.read_file(llm_workspace, "backend/crud.py") == "router = 'kept'\n"


async def test_first_draft_sends_no_current_files(llm_workspace: str):
    client = FakeClient(json.dumps({"files": [{"path": "backend/main.py", "content": "a\n"}]}))
    await LlmDeveloperAgent(DeepSeekClient(client=client)).run(llm_workspace, {}, VALID_SPEC)
    sent = json.loads(client.chat.completions.calls[0]["messages"][1]["content"])
    assert "currentFiles" not in sent
