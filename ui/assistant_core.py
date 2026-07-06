"""
Core logic for the embedded AI assistant (Assistant page).

Streamlit-free: gating, tool-schema assembly, and the tool-use agent loop.
The chat page (Assistant.py) provides the UI; assistant_tools.py provides the
session-aware tools. Solver tools are reused in-process from the FastMCP
registry in owlplanner.cli.cmd_serve — same implementations the MCP server
exposes, called directly without any stdio transport.

The assistant is opt-in and intended for self-hosted or Docker deployments:
it activates only when OWL_ASSISTANT=1 is set in the environment, so the
hosted Streamlit app never exposes it. Conversations are sent to the
configured LLM provider (Anthropic API by default; OWL_ASSISTANT_BASE_URL /
OWL_ASSISTANT_API_KEY point the assistant — and only the assistant — at a
gateway, proxy, or other Anthropic-compatible endpoint; the SDK's global
ANTHROPIC_* variables are also honored).

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import asyncio
import json
import os

DEFAULT_MODEL = "claude-opus-4-8"
MAX_ITERATIONS = 12  # tool-use round trips per user turn

# Stateless solver tools reused from the MCP registry. The file-path tools
# (list_cases, explain_case, run_case, compare_cases) are included: the chat
# runs on the same machine as the case files on a self-hosted install, and
# they close the loop with save_case (save a scenario, reload it later).
STATELESS_TOOLS = (
    "run_from_params",
    "compare_to_baseline",
    "explain_results",
    "run_stochastic",
    "run_longevity_stochastic",
    "run_historical",
    "run_monte_carlo",
    "save_case",
    "list_cases",
    "explain_case",
    "run_case",
    "compare_cases",
    "convert_ss_benefit",
    "list_contribution_limits",
    "list_rate_models",
    "list_mortality_tables",
)


def assistant_enabled() -> bool:
    """The page exists only when explicitly enabled — never on the hosted app."""
    return os.environ.get("OWL_ASSISTANT", "") == "1"


def assistant_model() -> str:
    return os.environ.get("OWL_ASSISTANT_MODEL", DEFAULT_MODEL)


def client_kwargs() -> dict:
    """
    Owl-scoped client overrides: OWL_ASSISTANT_BASE_URL / OWL_ASSISTANT_API_KEY.

    Unlike the SDK's own ANTHROPIC_BASE_URL / ANTHROPIC_API_KEY (which remain
    honored through the SDK's normal resolution chain), these apply only to the
    Owl assistant — pointing it at a local proxy does not redirect other
    Anthropic-SDK programs (e.g. Claude Code) running in the same environment.
    """
    kwargs = {}
    base_url = os.environ.get("OWL_ASSISTANT_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    api_key = os.environ.get("OWL_ASSISTANT_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key
    return kwargs


def stateless_tool_schemas() -> list[dict]:
    """Anthropic-format tool schemas for the whitelisted MCP solver tools."""
    from owlplanner.cli.cmd_serve import mcp

    tools = asyncio.run(mcp.list_tools())
    return [
        {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
        for t in tools
        if t.name in STATELESS_TOOLS
    ]


def call_stateless_tool(name: str, args: dict) -> str:
    """Execute a whitelisted MCP tool in-process and return its text result."""
    if name not in STATELESS_TOOLS:
        raise ValueError(f"Unknown tool '{name}'.")
    from owlplanner.cli.cmd_serve import mcp

    result = asyncio.run(mcp.call_tool(name, args or {}))
    content = result[0] if isinstance(result, tuple) else result
    return "".join(getattr(block, "text", "") for block in content)


def build_system_prompt() -> str:
    from owlplanner.assistant.intake import INTAKE_PROMPT

    return (
        "You are the AI assistant built into Owl (Optimal Wealth Lab), a US retirement "
        "planning optimizer, embedded as a page of its web interface. The user has the "
        "Owl app open next to this chat and may have already built one or more cases in "
        "it.\n\n"
        "When the user refers to 'my case', 'my plan', or their current numbers, call "
        "get_current_case first — it returns the configuration of the case currently "
        "open in the app (and key results when it has been solved). For the detailed "
        "year-by-year solution the app is displaying, call get_current_case_results "
        "instead of re-solving. Use those values verbatim as inputs to the solver "
        "tools; never invent or round balances, ages, or benefits. To explore "
        "variants, translate the case configuration into the flat parameters of "
        "run_from_params / compare_to_baseline / explain_results. "
        "Chat tools cannot modify the case open in the app; to hand a scenario back to "
        "the user, offer save_case, which writes a TOML case file they can load from "
        "the app's Create Case page — and which you can rediscover and re-run later "
        "with list_cases / run_case / compare_cases (use absolute paths).\n\n"
        "Conventions: balances are in full dollars; Social Security and pensions are "
        "$/month (Social Security as the PIA at full retirement age — use "
        "convert_ss_benefit when the user quotes an actual check amount); wages, "
        "contributions, and expenses are $/year; wages must be net of the retirement "
        "contributions listed separately. Solve responses include an assumed_defaults "
        "list — relay material assumptions and ask for true values when they matter. "
        "Solves take seconds; frontier and Monte Carlo tools solve many scenarios and "
        "can take a minute or more, so mention that before launching them.\n\n"
        "Keep responses conversational and concise; lead with the numbers that answer "
        "the question, in today's dollars unless asked otherwise. Owl is an educational "
        "and research tool: results are not financial, tax, or investment advice, and "
        "it is good practice to remind the user of that when decisions are at stake.\n\n"
        "When gathering a new household's information from scratch, follow this intake "
        "guide:\n\n" + INTAKE_PROMPT
    )


def run_agent_turn(client, model, system, messages, tools, execute_tool, on_tool=None):
    """
    Manual tool-use loop for one user turn.

    *messages* is mutated in place: the caller appends the user message before
    calling; this function appends assistant turns and tool results as the
    loop progresses, so the full history (including thinking and tool blocks)
    is preserved for subsequent turns.

    *execute_tool(name, args) -> str* runs a tool; *on_tool(name)* is an
    optional UI callback fired before each tool execution.

    Returns the assistant's final text.
    """
    kwargs = dict(
        model=model,
        max_tokens=16000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        tools=tools,
        thinking={"type": "adaptive"},
    )

    for _ in range(MAX_ITERATIONS):
        try:
            response = client.messages.create(messages=messages, **kwargs)
        except Exception as e:
            # Gateways and non-Anthropic models may reject the thinking parameter;
            # drop it once and retry rather than failing the conversation.
            if "thinking" in kwargs and "thinking" in str(e).lower():
                kwargs.pop("thinking")
                response = client.messages.create(messages=messages, **kwargs)
            else:
                raise

        if response.stop_reason == "refusal":
            return "I can't help with that request."

        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            messages.append({"role": "assistant", "content": response.content})
            text = "".join(b.text for b in response.content if b.type == "text")
            if response.stop_reason == "max_tokens":
                text += "\n\n*(response truncated — ask me to continue)*"
            return text

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for tool in tool_uses:
            if on_tool is not None:
                on_tool(tool.name)
            try:
                out = execute_tool(tool.name, dict(tool.input or {}))
                results.append({"type": "tool_result", "tool_use_id": tool.id, "content": out})
            except Exception as e:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool.id,
                        "content": f"Error: {e}",
                        "is_error": True,
                    }
                )
        # All results for parallel calls go back in a single user message.
        messages.append({"role": "user", "content": results})

    return "I stopped after too many tool calls in a single turn — please break the request into smaller steps."


def extract_text(content) -> str:
    """Concatenate the text blocks of an assistant content list."""
    return "".join(getattr(b, "text", "") for b in content if getattr(b, "type", "") == "text")


def to_compact_json(obj) -> str:
    return json.dumps(obj, default=str)
