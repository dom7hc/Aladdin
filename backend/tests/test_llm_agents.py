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
    DeepSeekClient,
    LlmArchitectAgent,
    LlmDeveloperAgent,
    LLMError,
    LlmRequirementAgent,
    LlmReviewerAgent,
    LlmTesterAgent,
    _extract_json,
    build_llm_agents,
)
from app.agents.stubs import StubDeveloperAgent
from app.schemas.project import empty_requirements
from app.workspace import workspace as ws


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item))])


class FakeClient:
    def __init__(self, *responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(list(responses)))


@pytest.fixture()
def llm_workspace(tmp_path: Path, monkeypatch) -> str:
    """Hermetic generated workspace under tmp_path."""
    monkeypatch.setattr(ws, "GENERATED_DIR", str(tmp_path / "generated"))
    return "abcdef0123456789abcdef01"


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


async def test_architect_agent_validates_shape():
    good = {
        "pages": [{"name": "Home", "purpose": "main"}],
        "apis": [{"method": "GET", "path": "/api/items"}],
        "entities": [{"name": "Item", "fields": ["id"]}],
        "services": ["ItemService"],
        "aiCapabilities": [],
    }
    agent = LlmArchitectAgent(DeepSeekClient(client=FakeClient(json.dumps(good))))
    assert await agent.run(empty_requirements("x")) == good

    bad = {**good, "services": None}
    agent = LlmArchitectAgent(DeepSeekClient(client=FakeClient(json.dumps(bad))))
    with pytest.raises(LLMError, match="services"):
        await agent.run(empty_requirements("x"))


async def test_developer_agent_writes_files(llm_workspace: str):
    files = [
        {"path": "backend/main.py", "content": "from fastapi import FastAPI\napp = FastAPI()\n"},
        {"path": "frontend/package.json", "content": '{"name": "poc"}'},
        {"path": "frontend/src/App.tsx", "content": "export default () => null\n"},
    ]
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
    written = await agent.run(llm_workspace, {}, {})
    assert written == ["backend/main.py", "frontend/package.json", "frontend/src/App.tsx"]
    assert ws.read_file(llm_workspace, "backend/main.py").startswith("from fastapi")


async def test_developer_agent_rejects_unsafe_paths(llm_workspace: str):
    files = [
        {"path": "backend/main.py", "content": "x"},
        {"path": "frontend/package.json", "content": "x"},
        {"path": "../escape.py", "content": "x"},
    ]
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
    with pytest.raises(LLMError, match="unsafe path"):
        await agent.run(llm_workspace, {}, {})


async def test_developer_agent_requires_minimal_files(llm_workspace: str):
    files = [{"path": "frontend/src/App.tsx", "content": "x"}]
    agent = LlmDeveloperAgent(DeepSeekClient(client=FakeClient(json.dumps({"files": files}))))
    with pytest.raises(LLMError, match="backend/main.py"):
        await agent.run(llm_workspace, {}, {})


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
    client = FakeClient()  # empty: any LLM call would raise IndexError
    result = await LlmTesterAgent(DeepSeekClient(client=client)).run(llm_workspace)
    assert result.status == "PASSED"
    assert client.chat.completions.calls == []


async def test_tester_agent_uses_llm_diagnosis_on_failure(llm_workspace: str):
    ws.copy_template(llm_workspace)
    await StubDeveloperAgent().run(llm_workspace, {}, {})
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
    architect, developer, reviewer, tester = build_llm_agents()
    assert isinstance(architect, LlmArchitectAgent)
    assert isinstance(developer, LlmDeveloperAgent)
    assert isinstance(reviewer, LlmReviewerAgent)
    assert isinstance(tester, LlmTesterAgent)
