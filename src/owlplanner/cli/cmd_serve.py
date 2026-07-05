"""
CLI command that starts an MCP (Model Context Protocol) server for Owl.

Exposes fourteen tools over stdio so any MCP-compatible AI client (Claude Desktop,
Claude Code, Gemini CLI, etc.) can discover cases, inspect configurations, run optimizations,
and compare scenarios without touching the filesystem directly.

The tool implementations live in owlplanner.assistant.tools so they can be
reused by other assistant front ends; this module only registers them with
FastMCP and provides the click entry point.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import click
from mcp.server.fastmcp import FastMCP

from owlplanner.assistant.tools import MCP_TOOLS, SERVER_INSTRUCTIONS


mcp = FastMCP("owl", instructions=SERVER_INSTRUCTIONS)

for _tool in MCP_TOOLS:
    mcp.tool()(_tool)


@click.command(name="serve")
def cmd_serve():
    """Start the Owl MCP server (stdio transport).

    Exposes fourteen tools to any MCP-compatible AI client:

    \b
      list_cases               enumerate .toml case files in a directory
      explain_case             describe a case without solving
      list_rate_models         enumerate available rate models
      list_mortality_tables    actuarial tables for longevity sampling
      convert_ss_benefit       convert between SS PIA and benefit at a claiming age
      list_contribution_limits IRS contribution-limit ceilings by birth year
      run_case                 solve and return JSON results
      compare_cases            run base + variant and return delta metrics
      run_from_params          build and solve from structured parameters (no TOML needed)
      save_case                save structured parameters to TOML + HFP Excel
      run_stochastic           spending frontier over historical or Monte Carlo scenarios
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
