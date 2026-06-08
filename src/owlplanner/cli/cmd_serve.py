"""
CLI command that starts an MCP (Model Context Protocol) server for Owl.

Exposes five tools over stdio so any MCP-compatible AI client (Claude Desktop,
Claude Code, etc.) can discover cases, inspect configurations, run optimizations,
and compare scenarios without touching the filesystem directly.

Tools exposed:
  list_cases        — enumerate .toml case files in a directory
  explain_case      — describe a case without solving
  list_rate_models  — enumerate available rate models and their parameters
  run_case          — solve a case and return structured JSON results
  compare_cases     — run base + variant and return delta metrics

All tool output is JSON.  Plan solver output goes to stderr so it never
pollutes the MCP stdio transport.

Copyright (C) 2025-2026 The Owl Authors
"""

import asyncio
import json
import sys
from pathlib import Path

import click
from mcp.server.fastmcp import FastMCP

from owlplanner.config import load_toml, config_to_plan
from owlplanner.config.schema import CLI_SOLVER_OVERRIDE_MAP, parse_solver_options
from owlplanner.export import plan_metrics
from owlplanner.rate_models.loader import get_all_models_metadata, RATE_MODEL_ALIASES

from .cmd_explain import _plan_to_explain
from .cmd_run import _parse_solver_opts
from .formatters import plan_to_dict, _NumpyEncoder
from .set_override import apply_overrides


mcp = FastMCP(
    "owl",
    instructions=(
        "Owl (Optimal Wealth Lab) is a US retirement financial planning tool. "
        "Use list_cases to discover available scenarios, explain_case to inspect "
        "a configuration, list_rate_models to see return-modeling options, "
        "run_case to optimize a scenario, and compare_cases to evaluate the impact "
        "of a parameter change. All monetary values in JSON output are nominal dollars "
        "unless the key ends with '_today' or '_today_dollars'."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_cases
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_cases(directory: str = ".") -> str:
    """List Owl case files (.toml) in a directory.

    Returns a JSON array of objects, each with:
      - stem: filename without extension
      - filename: full path
      - has_hfp: whether the associated time-lists Excel file exists
      - hfp_file: name of the HFP file (or null)
    """
    path = Path(directory)
    if not path.exists() or not path.is_dir():
        return json.dumps({"error": f"Directory not found: {directory}"})

    toml_files = sorted(path.glob("*.toml"))
    if not toml_files:
        return json.dumps([])

    cases = []
    for f in toml_files:
        try:
            plan = config_to_plan(
                load_toml(str(f))[0],
                str(path),
                verbose=False,
                logstreams=[sys.stderr],
                loadHFP=False,
            )
            hfp = plan.hfpFileName if plan.hfpFileName != "None" else None
            cases.append({
                "stem": f.stem,
                "filename": str(f),
                "case_name": plan._name,
                "has_hfp": bool(hfp and (path / hfp).exists()),
                "hfp_file": hfp,
            })
        except Exception as e:
            cases.append({"stem": f.stem, "filename": str(f), "error": str(e)})

    return json.dumps(cases, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: explain_case
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def explain_case(filename: str, overrides: list[str] = []) -> str:
    """Describe a retirement planning case without solving it.

    Loads and validates the TOML case file, applies any overrides, and returns
    a JSON document with: individuals, time horizon, account balances, Social
    Security and pension income, rate method, objective, and solver options.

    The 'overrides' list uses KEY.PATH=VALUE syntax, e.g.:
      ["basic_info.state=CA", "fixed_income.social_security_ages=[70,68]"]
    """
    try:
        diconf, dirname, _ = load_toml(filename)
    except Exception as e:
        return json.dumps({"error": f"Failed to load {filename}: {e}"})

    if overrides:
        try:
            diconf = apply_overrides(diconf, overrides)
        except Exception as e:
            return json.dumps({"error": f"Invalid override: {e}"})

    try:
        plan = config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=False)
    except Exception as e:
        return json.dumps({"error": f"Failed to build plan: {e}"})

    result = _plan_to_explain(plan, filename, overrides)
    return json.dumps(result, indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_rate_models
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_rate_models(category: str = "all") -> str:
    """List available rate models for return-sequence generation.

    Returns a JSON document with:
      - models: list of rate models with description, category, parameters
      - aliases: legacy name → canonical name mapping

    Categories: single (constant), deterministic (year-varying), stochastic
    (Monte Carlo), dataframe (programmatic only), all.

    Use the 'method' field value in rates_selection.method when building
    --set overrides for run_case or compare_cases.
    """
    valid = {"single", "deterministic", "stochastic", "dataframe", "all"}
    if category not in valid:
        return json.dumps({"error": f"Unknown category '{category}'. Choose from: {sorted(valid)}"})

    models = get_all_models_metadata()
    if category != "all":
        models = [m for m in models if m["category"] == category]

    reverse: dict[str, list[str]] = {}
    for alias, canonical in RATE_MODEL_ALIASES.items():
        reverse.setdefault(canonical, []).append(alias)
    for m in models:
        m["aliases"] = sorted(reverse.get(m["method"], []))

    result = {
        "models": sorted(models, key=lambda m: (m["category"], m["method"])),
        "aliases": {a: c for a, c in sorted(RATE_MODEL_ALIASES.items())},
    }
    return json.dumps(result, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: run_case
# ─────────────────────────────────────────────────────────────────────────────

def _build_opts(plan, solver, max_time, gap, verbose_flag, solver_opts_raw):
    """Merge CLI flags into the plan's solver options dict and validate."""
    opts = dict(plan.solverOptions)
    if solver is not None:
        opts["solver"] = solver
    if max_time is not None:
        opts["maxTime"] = max_time
    if gap is not None:
        opts["gap"] = gap
    if verbose_flag is not None:
        opts["verbose"] = verbose_flag
    for key, val in _parse_solver_opts(solver_opts_raw or []):
        opts[CLI_SOLVER_OVERRIDE_MAP.get(key, key)] = val
    return parse_solver_options(opts)


def _solve_blocking(diconf, dirname, solver, max_time, gap, seed, solver_opts_raw):
    """Load, configure, solve, and return the Plan. Runs in a thread executor."""
    plan = config_to_plan(diconf, dirname, verbose=True, logstreams=[sys.stderr], loadHFP=True)
    if seed is not None:
        plan.setReproducible(True, seed=seed)
    opts = _build_opts(plan, solver, max_time, gap, None, solver_opts_raw)
    plan.solve(plan.objective, opts)
    return plan


@mcp.tool()
async def run_case(
    filename: str,
    overrides: list[str] = [],
    solver: str | None = None,
    max_time: float | None = None,
    gap: float | None = None,
    seed: int | None = None,
) -> str:
    """Solve a retirement planning case and return structured JSON results.

    Loads FILENAME, applies any overrides, solves the optimization, and returns
    a JSON document with a summary of key metrics and per-year arrays.

    Args:
        filename:  Path to the .toml case file.
        overrides: KEY.PATH=VALUE overrides, e.g. ["basic_info.state=TX"].
        solver:    "HiGHS", "MOSEK", or "default" (default picks best available).
        max_time:  Solver time limit in seconds.
        gap:       MIP relative gap tolerance (e.g. 1e-4).
        seed:      Random seed for stochastic rate methods.
    """
    try:
        diconf, dirname, _ = load_toml(filename)
    except Exception as e:
        return json.dumps({"error": f"Failed to load {filename}: {e}"})

    if overrides:
        try:
            diconf = apply_overrides(diconf, overrides)
        except Exception as e:
            return json.dumps({"error": f"Invalid override: {e}"})

    try:
        plan = await asyncio.get_event_loop().run_in_executor(
            None,
            _solve_blocking,
            diconf, dirname, solver, max_time, gap, seed, [],
        )
    except Exception as e:
        return json.dumps({"error": f"Solver error: {e}"})

    if plan.caseStatus != "solved":
        return json.dumps({"status": plan.caseStatus, "case_name": plan._name,
                           "error": "Case did not solve to optimality."})

    result = plan_to_dict(plan)
    return json.dumps(result, indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: compare_cases
# ─────────────────────────────────────────────────────────────────────────────

def _diff(base: dict, variant: dict) -> dict:
    delta = {}
    for k in base:
        if k not in variant:
            continue
        bv, vv = base[k], variant[k]
        if isinstance(bv, (int, float)) and isinstance(vv, (int, float)):
            delta[k] = round(vv - bv, 6)
        else:
            delta[k] = None
    return delta


def _pct(delta_val, base_val):
    if base_val and base_val != 0:
        return round((delta_val / abs(base_val)) * 100, 2)
    return None


def _compare_blocking(diconf_base, diconf_variant, dirname, solver, max_time, gap, seed):
    plan_base = _solve_blocking(diconf_base, dirname, solver, max_time, gap, seed, [])
    plan_variant = _solve_blocking(diconf_variant, dirname, solver, max_time, gap, seed, [])
    return plan_base, plan_variant


@mcp.tool()
async def compare_cases(
    filename: str,
    overrides: list[str],
    solver: str | None = None,
    max_time: float | None = None,
    gap: float | None = None,
    seed: int | None = None,
) -> str:
    """Compare a base case against a variant defined by parameter overrides.

    Runs both scenarios and returns a JSON document with base metrics, variant
    metrics, the numeric delta (variant minus base), and percent changes for
    key decision metrics.

    Args:
        filename:  Path to the .toml case file.
        overrides: KEY.PATH=VALUE overrides defining the variant (required).
                   e.g. ["basic_info.state=MN"] or
                        ["fixed_income.social_security_ages=[70,68]"]
        solver:    Solver for both runs ("HiGHS", "MOSEK", or "default").
        max_time:  Per-run solver time limit in seconds.
        gap:       MIP relative gap tolerance.
        seed:      Random seed for stochastic rate methods.
    """
    if not overrides:
        return json.dumps({"error": "At least one override is required to define the variant."})

    try:
        diconf_base, dirname, _ = load_toml(filename)
    except Exception as e:
        return json.dumps({"error": f"Failed to load {filename}: {e}"})

    try:
        diconf_variant = apply_overrides(diconf_base, overrides)
    except Exception as e:
        return json.dumps({"error": f"Invalid override: {e}"})

    try:
        plan_base, plan_variant = await asyncio.get_event_loop().run_in_executor(
            None,
            _compare_blocking,
            diconf_base, diconf_variant, dirname, solver, max_time, gap, seed,
        )
    except Exception as e:
        return json.dumps({"error": f"Solver error: {e}"})

    if plan_base.caseStatus != "solved" or plan_variant.caseStatus != "solved":
        return json.dumps({
            "error": "One or both cases did not solve.",
            "base_status": plan_base.caseStatus,
            "variant_status": plan_variant.caseStatus,
        })

    m_base = plan_metrics(plan_base)
    m_variant = plan_metrics(plan_variant)
    delta = _diff(m_base, m_variant)

    key_metrics = [
        "spending_basis", "total_spending_today", "total_spending_nominal",
        "ss_income_today", "roth_conversions_today",
        "federal_income_tax_today", "state_tax_today", "medicare_today", "aca_today",
        "final_bequest_today", "final_bequest_nominal", "effective_tax_rate",
    ]
    pct_change = {
        k: _pct(delta[k], m_base[k])
        for k in key_metrics
        if k in delta and delta[k] is not None
    }

    result = {
        "filename": filename,
        "overrides": list(overrides),
        "base": {k: round(v, 4) if isinstance(v, float) else v for k, v in m_base.items()},
        "variant": {k: round(v, 4) if isinstance(v, float) else v for k, v in m_variant.items()},
        "delta": {k: round(v, 4) if isinstance(v, float) else v for k, v in delta.items() if v is not None},
        "pct_change": pct_change,
    }
    return json.dumps(result, indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Click command
# ─────────────────────────────────────────────────────────────────────────────

@click.command(name="serve")
def cmd_serve():
    """Start the Owl MCP server (stdio transport).

    Exposes five tools to any MCP-compatible AI client:

    \b
      list_cases        enumerate .toml case files in a directory
      explain_case      describe a case without solving
      list_rate_models  enumerate available rate models
      run_case          solve and return JSON results
      compare_cases     run base + variant and return delta metrics

    Configure Claude Desktop by adding to mcpServers in claude_desktop_config.json:

    \b
      "owl": {
        "command": "owlcli",
        "args": ["serve"]
      }
    """
    mcp.run(transport="stdio")
