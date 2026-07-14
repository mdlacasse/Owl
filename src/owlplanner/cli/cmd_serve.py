"""
CLI command that starts an MCP (Model Context Protocol) server for Owl.

Exposes seventeen tools over stdio so any MCP-compatible AI client (Claude Desktop,
Claude Code, Gemini CLI, etc.) can discover cases, inspect configurations, run optimizations,
and compare scenarios without touching the filesystem directly.

The tool implementations live in owlplanner.assistant.tools so they can be
reused by other assistant front ends; this module only registers them with
FastMCP and provides the click entry point.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import click
from mcp.server.fastmcp import FastMCP

from owlplanner.assistant.intake import INTAKE_PROMPT, modeling_capabilities_text
from owlplanner.assistant.tools import MCP_TOOLS, SERVER_INSTRUCTIONS


mcp = FastMCP("owl", instructions=SERVER_INSTRUCTIONS)

for _tool in MCP_TOOLS:
    mcp.tool()(_tool)


@mcp.prompt(
    name="owl_intake",
    title="Owl retirement-plan intake",
    description="Interview script for gathering the data Owl needs to build a plan; "
    "separates must-ask questions from parameters that may be assumed with disclosure.",
)
def owl_intake() -> str:
    return INTAKE_PROMPT


@mcp.resource(
    "owl://intake-checklist",
    name="intake-checklist",
    title="Owl intake checklist",
    description="Checklist of the questions to ask before building a plan, tiered by "
    "whether a default assumption is defensible.",
    mime_type="text/markdown",
)
def intake_checklist() -> str:
    return INTAKE_PROMPT


@mcp.resource(
    "owl://modeling-capabilities",
    name="modeling-capabilities",
    title="Owl modeling capabilities",
    description="Reference table of every modeled component, its approach, and its "
    "assumptions and limitations.",
    mime_type="text/markdown",
)
def modeling_capabilities() -> str:
    return modeling_capabilities_text()


@click.command(name="serve")
def cmd_serve():
    """Start the Owl MCP server (stdio transport).

    Exposes seventeen tools to any MCP-compatible AI client:

    \b
      list_cases               enumerate .toml case files in a directory
      explain_case             describe a case without solving
      list_rate_models         enumerate available rate models
      list_mortality_tables    actuarial tables for longevity sampling
      convert_ss_benefit       convert between SS PIA and benefit at a claiming age
      list_contribution_limits IRS contribution-limit ceilings by birth year
      run_case                 solve and return JSON results
      compare_cases            run base + variant and return delta metrics
      compare_to_baseline      value of optimization vs conventional baseline strategy
      explain_results          shadow-price explanation of a solved plan
      run_from_params          build and solve from structured parameters (no TOML needed)
      save_case                save structured parameters to TOML + HFP Excel
      run_stochastic           spending frontier over historical or Monte Carlo scenarios
      run_year1_robustness     distribution of first-year decisions across scenarios
      run_longevity_stochastic frontier with joint market + lifespan sampling
      run_historical           backtest across historical sequences, return outcome distribution
      run_monte_carlo          Monte Carlo simulations, return outcome distribution

    Configure Claude Desktop by adding to mcpServers in claude_desktop_config.json:

    \b
      "owl": {
        "command": "owlcli",
        "args": ["serve"]
      }
    """
    mcp.run(transport="stdio")
