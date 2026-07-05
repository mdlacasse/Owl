"""
Tests for the MCP server surface: tool registration, the owl_intake prompt,
and the intake-checklist / modeling-capabilities resources.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio

from owlplanner.cli.cmd_serve import mcp
from owlplanner.assistant.intake import INTAKE_PROMPT, modeling_capabilities_text
from owlplanner.assistant.tools import MCP_TOOLS


def _run(coro):
    return asyncio.run(coro)


def test_all_tools_registered():
    tools = _run(mcp.list_tools())
    assert len(tools) == len(MCP_TOOLS) == 16
    names = {t.name for t in tools}
    assert {"run_from_params", "save_case", "compare_to_baseline", "explain_results"} <= names


def test_owl_intake_prompt_registered():
    prompts = _run(mcp.list_prompts())
    assert [p.name for p in prompts] == ["owl_intake"]


def test_owl_intake_prompt_content():
    result = _run(mcp.get_prompt("owl_intake"))
    text = result.messages[0].content.text
    assert text == INTAKE_PROMPT
    # The three-tier structure and the key must-ask items are present.
    assert "Tier 1" in text and "Tier 2" in text and "Tier 3" in text
    for item in ("State of residence", "Social Security", "SLCSP", "assumed_defaults"):
        assert item in text
    # Unit conventions that commonly trip up LLM callers.
    assert "$/month" in text
    assert "net of the retirement contributions" in text


def test_intake_checklist_resource():
    contents = _run(mcp.read_resource("owl://intake-checklist"))
    assert contents[0].content == INTAKE_PROMPT


def test_modeling_capabilities_resource():
    contents = _run(mcp.read_resource("owl://modeling-capabilities"))
    text = contents[0].content
    assert text == modeling_capabilities_text()
    # Running from the repo, the real document should be found and substantial.
    assert "Modeling Capabilities" in text
    assert "Roth" in text and "Medicare" in text
    assert len(text) > 10_000


def test_resources_listed():
    resources = _run(mcp.list_resources())
    uris = {str(r.uri) for r in resources}
    assert {"owl://intake-checklist", "owl://modeling-capabilities"} <= uris
