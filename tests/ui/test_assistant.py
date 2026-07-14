"""
Tests for the embedded AI assistant: gating, tool registry, agent loop, and
session tools (ui/assistant_core.py, ui/assistant_tools.py, ui/Assistant.py).

The agent loop is tested against a duck-typed fake client, so no anthropic
SDK or API key is required.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import json
from types import SimpleNamespace

import pytest

import assistant_core as core
import assistant_tools as atools


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OWL_ASSISTANT", raising=False)
    assert core.assistant_enabled() is False


def test_enabled_with_env(monkeypatch):
    monkeypatch.setenv("OWL_ASSISTANT", "1")
    assert core.assistant_enabled() is True


def test_model_override(monkeypatch):
    assert core.assistant_model() == core.DEFAULT_MODEL
    monkeypatch.setenv("OWL_ASSISTANT_MODEL", "claude-haiku-4-5")
    assert core.assistant_model() == "claude-haiku-4-5"


def test_client_kwargs_default_empty(monkeypatch):
    monkeypatch.delenv("OWL_ASSISTANT_BASE_URL", raising=False)
    monkeypatch.delenv("OWL_ASSISTANT_API_KEY", raising=False)
    # Empty → the SDK's own resolution chain (ANTHROPIC_* vars, ant profile) applies.
    assert core.client_kwargs() == {}


def test_client_kwargs_owl_scoped_overrides(monkeypatch):
    monkeypatch.setenv("OWL_ASSISTANT_BASE_URL", "http://localhost:4000")
    monkeypatch.setenv("OWL_ASSISTANT_API_KEY", "sk-test")
    assert core.client_kwargs() == {"base_url": "http://localhost:4000", "api_key": "sk-test"}


def test_page_hidden_when_disabled(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.delenv("OWL_ASSISTANT", raising=False)
    at = AppTest.from_file("ui/Assistant.py", default_timeout=30)
    at.run()
    assert not at.exception
    assert any("disabled" in str(i.value) for i in at.info)
    assert len(at.chat_input) == 0  # page stops before the chat UI


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


def test_stateless_tool_schemas_match_whitelist():
    schemas = core.stateless_tool_schemas()
    names = {s["name"] for s in schemas}
    assert names == set(core.STATELESS_TOOLS)
    for s in schemas:
        assert s["description"]
        assert s["input_schema"]["type"] == "object"


def test_stateless_whitelist_covers_all_mcp_tools():
    # The chat page exposes the full MCP registry (phase-3b decision). This guards
    # against forgetting to whitelist a newly added MCP tool: if the sets diverge
    # intentionally some day, update this test with the reason.
    from owlplanner.assistant.tools import MCP_TOOLS

    assert set(core.STATELESS_TOOLS) == {t.__name__ for t in MCP_TOOLS}


def test_all_tool_schemas_include_session_tools():
    names = {s["name"] for s in atools.all_tool_schemas()}
    assert {"get_current_case", "list_open_cases", "get_current_case_results"} <= names


def test_call_stateless_tool_rejects_non_whitelisted():
    with pytest.raises(ValueError):
        core.call_stateless_tool("delete_all_cases", {})


def test_call_stateless_tool_executes():
    out = core.call_stateless_tool("list_contribution_limits", {"birth_years": [1965]})
    data = json.loads(out)
    assert "persons" in data


# ---------------------------------------------------------------------------
# Agent loop (duck-typed fake client)
# ---------------------------------------------------------------------------


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_block(name, args, tid="tu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=args, id=tid)


class FakeClient:
    """Yields scripted responses; records the kwargs of each create() call."""

    def __init__(self, responses, reject_thinking=False):
        self._responses = list(responses)
        self.calls = []
        self.reject_thinking = reject_thinking

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.reject_thinking and "thinking" in kwargs:
            raise RuntimeError("this endpoint does not support the thinking parameter")
        return self._responses.pop(0)


def test_agent_turn_with_tool_call():
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[_tool_block("echo", {"x": 1})]),
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("All done.")]),
    ]
    client = FakeClient(responses)
    executed = []

    def execute(name, args):
        executed.append((name, args))
        return "tool says hi"

    seen = []
    messages = [{"role": "user", "content": "hello"}]
    text = core.run_agent_turn(
        client, "m", "sys", messages, [], execute, on_tool=seen.append
    )

    assert text == "All done."
    assert executed == [("echo", {"x": 1})]
    assert seen == ["echo"]
    # History: user, assistant(tool_use), user(tool_result), assistant(text).
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    result_msg = messages[2]["content"]
    assert result_msg[0]["type"] == "tool_result"
    assert result_msg[0]["tool_use_id"] == "tu_1"
    assert result_msg[0]["content"] == "tool says hi"


def test_agent_turn_tool_error_reported_not_raised():
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[_tool_block("boom", {})]),
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("Recovered.")]),
    ]
    client = FakeClient(responses)

    def execute(name, args):
        raise ValueError("bad input")

    messages = [{"role": "user", "content": "go"}]
    text = core.run_agent_turn(client, "m", "sys", messages, [], execute)
    assert text == "Recovered."
    assert messages[2]["content"][0]["is_error"] is True


def test_agent_turn_drops_thinking_on_rejection():
    responses = [
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("ok")]),
    ]
    client = FakeClient(responses, reject_thinking=True)
    messages = [{"role": "user", "content": "hi"}]
    text = core.run_agent_turn(client, "m", "sys", messages, [], lambda n, a: "")
    assert text == "ok"
    # Second call succeeded without the thinking parameter.
    assert "thinking" not in client.calls[-1]


def test_agent_turn_refusal():
    client = FakeClient([SimpleNamespace(stop_reason="refusal", content=[])])
    text = core.run_agent_turn(client, "m", "sys", [{"role": "user", "content": "x"}], [], None)
    assert "can't help" in text


@pytest.mark.toml
def test_agent_turn_scripted_llm_real_tools():
    """Fake only the LLM; the tool dispatch and solver run for real."""
    params = {
        "names": ["Pat"],
        "birth_dates": ["1960-07-01"],
        "life_expectancy": [88],
        "taxable": [200_000],
        "tax_deferred": [800_000],
        "roth": [100_000],
        "ss_monthly_pias": [2500],
        "ss_ages": [67],
        "state": "TX",
        "rate_method": "conservative",
    }
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[_tool_block("run_from_params", params)]),
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("Solved your plan.")]),
    ]
    client = FakeClient(responses)
    messages = [{"role": "user", "content": "run my numbers"}]
    text = core.run_agent_turn(client, "m", "sys", messages, [], atools.execute_tool)

    assert text == "Solved your plan."
    result = json.loads(messages[2]["content"][0]["content"])
    assert result["status"] == "solved"
    assert result["spending_year1_nominal"] > 0
    assert "assumed_defaults" in result


# ---------------------------------------------------------------------------
# Session tools (kz monkeypatched)
# ---------------------------------------------------------------------------


def test_get_current_case_no_case(monkeypatch):
    monkeypatch.setattr(atools.kz, "has_current_case", lambda: False)
    data = json.loads(atools.get_current_case())
    assert "error" in data


def test_list_open_cases(monkeypatch):
    monkeypatch.setattr(atools.kz, "onlyCaseNames", lambda: ["alpha", "beta"])
    monkeypatch.setattr(atools.kz, "has_current_case", lambda: True)
    monkeypatch.setattr(atools.kz, "currentCaseName", lambda: "beta")
    data = json.loads(atools.list_open_cases())
    assert data == {"open_cases": ["alpha", "beta"], "active_case": "beta"}


def test_get_current_case_results_no_case(monkeypatch):
    monkeypatch.setattr(atools.kz, "has_current_case", lambda: False)
    data = json.loads(atools.get_current_case_results())
    assert "error" in data


def test_get_current_case_results_unsolved(monkeypatch):
    monkeypatch.setattr(atools.kz, "has_current_case", lambda: True)
    monkeypatch.setattr(atools.kz, "currentCaseDic", lambda: {"caseStatus": "new", "plan": None})
    data = json.loads(atools.get_current_case_results())
    assert "not been solved" in data["error"]


@pytest.mark.toml
def test_get_current_case_results_solved(monkeypatch):
    from owlplanner.assistant.tools import _build_plan_from_params

    plan = _build_plan_from_params(
        names=["Pat"],
        birth_dates=["1960-07-01"],
        life_expectancy=[88],
        state="TX",
        taxable=[200_000],
        tax_deferred=[800_000],
        roth=[100_000],
        hsa=None,
        cost_basis=None,
        ss_monthly_pias=[2500],
        ss_ages=[67],
        pension_monthly_amounts=None,
        pension_ages=None,
        rate_method="conservative",
    )
    plan.solve("maxSpending", {"units": "1"})
    assert plan.caseStatus == "solved"

    monkeypatch.setattr(atools.kz, "has_current_case", lambda: True)
    monkeypatch.setattr(atools.kz, "currentCaseName", lambda: "pat")
    monkeypatch.setattr(atools.kz, "currentCaseDic", lambda: {"caseStatus": "solved", "plan": plan})
    data = json.loads(atools.get_current_case_results())
    assert data["case_name"] == "pat"
    assert data["status"] == "solved"
    assert data["spending_year1_nominal"] > 0
    assert len(data["by_year"]) == plan.N_n


def test_get_current_case_with_invalid_config(monkeypatch):
    monkeypatch.setattr(atools.kz, "has_current_case", lambda: True)
    monkeypatch.setattr(atools.kz, "currentCaseName", lambda: "draft")
    monkeypatch.setattr(atools.kz, "currentCaseDic", lambda: {"caseStatus": "new"})
    data = json.loads(atools.get_current_case())
    assert data["case_name"] == "draft"
    assert data["status"] == "new"
    # An incomplete case reports a config error instead of raising.
    assert "config" in data or "config_error" in data


# ---------------------------------------------------------------------------
# Greeting and starter prompts
# ---------------------------------------------------------------------------


def test_greeting_no_case(monkeypatch):
    monkeypatch.setattr(atools.kz, "has_current_case", lambda: False)
    assert "from scratch" in atools.greeting()
    starters = atools.starter_prompts()
    assert starters[0].startswith("Help me build")


def test_greeting_solved_case(monkeypatch):
    monkeypatch.setattr(atools.kz, "has_current_case", lambda: True)
    monkeypatch.setattr(atools.kz, "currentCaseName", lambda: "jack+jill")
    monkeypatch.setattr(atools.kz, "currentCaseDic", lambda: {"caseStatus": "solved"})
    g = atools.greeting()
    assert "jack+jill" in g and "solved" in g
    starters = atools.starter_prompts()
    assert any("worth in dollars" in s for s in starters)
    assert any("probability of success" in s for s in starters)


def test_greeting_unsolved_case(monkeypatch):
    monkeypatch.setattr(atools.kz, "has_current_case", lambda: True)
    monkeypatch.setattr(atools.kz, "currentCaseName", lambda: "draft")
    monkeypatch.setattr(atools.kz, "currentCaseDic", lambda: {"caseStatus": "new"})
    g = atools.greeting()
    assert "draft" in g and "Run it" in g
