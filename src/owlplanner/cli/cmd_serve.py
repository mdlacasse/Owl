"""
CLI command that starts an MCP (Model Context Protocol) server for Owl.

Exposes seven tools over stdio so any MCP-compatible AI client (Claude Desktop,
Claude Code, etc.) can discover cases, inspect configurations, run optimizations,
and compare scenarios without touching the filesystem directly.

Tools exposed:
  list_cases        — enumerate .toml case files in a directory
  explain_case      — describe a case without solving
  list_rate_models  — enumerate available rate models and their parameters
  run_case          — solve a case and return structured JSON results
  compare_cases     — run base + variant and return delta metrics
  run_from_params   — build and solve a plan from structured parameters (no TOML needed)
  save_case         — save structured parameters to TOML + HFP Excel for reproducibility

All tool output is JSON.  Plan solver output goes to stderr so it never
pollutes the MCP stdio transport.

Copyright (C) 2025-2026 The Owl Authors
"""

import asyncio
import datetime
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import click
from mcp.server.fastmcp import FastMCP

from owlplanner import Plan
from owlplanner.config import load_toml, config_to_plan
from owlplanner.config.plan_bridge import plan_to_config
from owlplanner.config.toml_io import save_toml
from owlplanner.config.schema import CLI_SOLVER_OVERRIDE_MAP, parse_solver_options
from owlplanner.export import plan_metrics
from owlplanner.hfp_io import conditionDebtsAndFixedAssetsDF
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
# Helpers for run_from_params / save_case
# ─────────────────────────────────────────────────────────────────────────────

_ACCOUNT_J = {"taxable": 0, "tax_deferred": 1, "roth": 2, "hsa": 3}


def _build_plan_from_params(
    names, birth_years, life_expectancy, state,
    taxable, tax_deferred, roth, hsa, cost_basis,
    ss_annual_amounts, ss_ages,
    pension_monthly_amounts, pension_ages,
    wages, contributions, big_ticket_items,
    debts, fixed_assets,
    objective, rate_method, survivor_fraction,
    initial_allocation, final_allocation,
):
    """Build and configure a Plan from structured parameters.  Does not solve."""
    N_i = len(names)
    thisyear = datetime.date.today().year
    dobs = [f"{by}-07-01" for by in birth_years]
    case_name = "+".join(n.lower() for n in names)

    plan = Plan(names, dobs, list(life_expectancy), case_name,
                verbose=False, logstreams=[sys.stderr])

    # Account balances (in $k, matching Plan API default)
    plan.setAccountBalances(
        taxable=list(taxable),
        taxDeferred=list(tax_deferred),
        taxFree=list(roth),
        hsa=list(hsa) if hsa else None,
    )
    if cost_basis:
        plan.setCostBasis(list(cost_basis))

    # Social Security: user provides annual $/year; Plan API wants monthly PIA
    ss_pias = [a / 12 for a in (ss_annual_amounts or [0] * N_i)]
    ss_claim_ages = list(ss_ages or [67] * N_i)
    plan.setSocialSecurity(ss_pias, ss_claim_ages)

    # Pensions (monthly $/month, matching Plan API)
    if pension_monthly_amounts and any(a > 0 for a in pension_monthly_amounts):
        plan.setPension(
            list(pension_monthly_amounts),
            list(pension_ages or [65] * N_i),
        )

    # Rates, state tax, spending profile
    plan.setRates(rate_method)
    if state:
        plan.setStateTax(state)
    plan.setSpendingProfile("flat", percent=int(survivor_fraction))

    # Asset allocation glide path
    alloc_init = list(initial_allocation)
    alloc_final = list(final_allocation)
    if N_i == 2:
        plan.setAllocationRatios("spouses", generic=[alloc_init, alloc_final])
    else:
        plan.setAllocationRatios("individual", generic=[[alloc_init, alloc_final]])

    # Time-series: wages → omega_in  (annual $/year)
    if wages:
        for w in wages:
            i = int(w.get("person", 0))
            if i >= N_i:
                continue
            amount = float(w["annual_amount"])
            start_yr = int(w.get("start_year", thisyear))
            end_yr = int(w.get("end_year", thisyear + int(plan.horizons[i])))
            for n in range(plan.N_n):
                if start_yr <= thisyear + n < end_yr:
                    plan.omega_in[i, n] += amount

    # Time-series: contributions → kappa_ijn  (annual $/year)
    if contributions:
        for c in contributions:
            i = int(c.get("person", 0))
            if i >= N_i:
                continue
            j = _ACCOUNT_J.get(str(c["account"]).lower(), 1)
            amount = float(c["annual_amount"])
            start_yr = int(c.get("start_year", thisyear))
            end_yr = int(c.get("end_year", thisyear + int(plan.horizons[i])))
            for n in range(plan.N_n):
                if start_yr <= thisyear + n < end_yr:
                    plan.kappa_ijn[i, j, n] += amount

    # Time-series: big-ticket items → Lambda_in  (annual $/year, positive = extra expense)
    if big_ticket_items:
        for bt in big_ticket_items:
            i = int(bt.get("person", 0))
            if i >= N_i:
                continue
            amount = float(bt["annual_amount"])
            start_yr = int(bt["start_year"])
            end_yr = int(bt.get("end_year", start_yr + 1))
            for n in range(plan.N_n):
                if start_yr <= thisyear + n < end_yr:
                    plan.Lambda_in[i, n] += amount

    # Debts → houseLists["Debts"]
    # balance = remaining principal (starts today), rate in %, years_remaining = remaining term
    if debts:
        rows = [
            {
                "active": True,
                "name": d.get("label", "debt"),
                "type": d.get("type", "loan"),
                "year": thisyear,
                "term": int(d["years_remaining"]),
                "amount": float(d["balance"]),
                "rate": float(d["rate"]),
            }
            for d in debts
        ]
        plan.houseLists["Debts"] = conditionDebtsAndFixedAssetsDF(
            pd.DataFrame(rows), "Debts"
        )

    # Fixed assets → houseLists["Fixed Assets"]
    # value/basis in $; rate = real above-inflation growth for residence/real estate,
    # nominal growth for others; sell_year = 4-digit year (0 = end of plan)
    if fixed_assets:
        rows = [
            {
                "active": True,
                "name": fa.get("label", "asset"),
                "type": fa["type"],
                "year": thisyear,
                "basis": float(fa["basis"]),
                "value": float(fa["value"]),
                "rate": float(fa.get("rate", 0.0)),
                "yod": int(fa.get("sell_year", 0)),
                "commission": float(fa.get("commission", 0.0)),
            }
            for fa in fixed_assets
        ]
        plan.houseLists["Fixed Assets"] = conditionDebtsAndFixedAssetsDF(
            pd.DataFrame(rows), "Fixed Assets"
        )

    # houseLists is now populated; processDebtsAndFixedAssets() will be called
    # automatically by solve() after _adjustParameters sets the inflation path.
    plan.objective = objective
    return plan


def _build_hfp_dataframes(plan):
    """Reconstruct timeLists and houseLists DataFrames from plan arrays for HFP export."""
    from owlplanner.hfp_io import _timeHorizonItems  # noqa: PLC2701
    thisyear = datetime.date.today().year
    tl = {}
    for i, iname in enumerate(plan.inames):
        h = int(plan.horizons[i])
        years = list(range(thisyear - 5, thisyear + h))
        n_rows = len(years)
        df = pd.DataFrame(0.0, index=range(n_rows), columns=_timeHorizonItems)
        df["year"] = years
        # Plan arrays cover [0, N_n); offset 5 = thisyear in the time-list row ordering
        for n in range(h):
            row = 5 + n
            df.at[row, "anticipated wages"] = float(plan.omega_in[i, n])
            df.at[row, "big-ticket items"] = float(plan.Lambda_in[i, n])
            df.at[row, "taxable ctrb"] = float(plan.kappa_ijn[i, 0, n])
            df.at[row, "401k ctrb"] = float(plan.kappa_ijn[i, 1, n])
            df.at[row, "Roth IRA ctrb"] = float(plan.kappa_ijn[i, 2, n])
            df.at[row, "HSA ctrb"] = float(plan.kappa_ijn[i, 3, n])
        tl[iname] = df

    hl = {}
    from owlplanner.hfp_io import _debtItems, _fixedAssetItems  # noqa: PLC2701
    debts_df = plan.houseLists.get("Debts", pd.DataFrame(columns=_debtItems))
    fa_df = plan.houseLists.get("Fixed Assets", pd.DataFrame(columns=_fixedAssetItems))
    hl["Debts"] = debts_df
    hl["Fixed Assets"] = fa_df
    return tl, hl


# ─────────────────────────────────────────────────────────────────────────────
# Tool: run_from_params
# ─────────────────────────────────────────────────────────────────────────────

def _run_from_params_blocking(
    names, birth_years, life_expectancy, state,
    taxable, tax_deferred, roth, hsa, cost_basis,
    ss_annual_amounts, ss_ages,
    pension_monthly_amounts, pension_ages,
    wages, contributions, big_ticket_items,
    debts, fixed_assets,
    objective, rate_method, survivor_fraction,
    initial_allocation, final_allocation,
    solver, max_time, gap,
):
    plan = _build_plan_from_params(
        names, birth_years, life_expectancy, state,
        taxable, tax_deferred, roth, hsa, cost_basis,
        ss_annual_amounts, ss_ages,
        pension_monthly_amounts, pension_ages,
        wages, contributions, big_ticket_items,
        debts, fixed_assets,
        objective, rate_method, survivor_fraction,
        initial_allocation, final_allocation,
    )
    opts = {}
    if solver:
        opts["solver"] = solver
    if max_time is not None:
        opts["maxTime"] = max_time
    if gap is not None:
        opts["gap"] = gap
    plan.solve(objective, opts)
    return plan


@mcp.tool()
async def run_from_params(
    names: list[str],
    birth_years: list[int],
    life_expectancy: list[int],
    taxable: list[float],
    tax_deferred: list[float],
    roth: list[float],
    hsa: list[float] | None = None,
    cost_basis: list[float] | None = None,
    ss_annual_amounts: list[float] | None = None,
    ss_ages: list[int] | None = None,
    pension_monthly_amounts: list[float] | None = None,
    pension_ages: list[int] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    state: str = "TX",
    objective: str = "maxSpending",
    rate_method: str = "conservative",
    survivor_fraction: float = 60.0,
    initial_allocation: list[float] = [60, 40, 0, 0],
    final_allocation: list[float] = [40, 60, 0, 0],
    solver: str | None = None,
    max_time: float | None = None,
    gap: float | None = None,
) -> str:
    """Build and solve a retirement plan from structured parameters — no TOML file needed.

    All monetary balances are in $k (thousands).  All time-series amounts are in $/year.
    Social Security is specified as annual $/year (converted internally to monthly PIA).
    Pensions are in $/month (monthly benefit, matching IRS convention).

    Args:
        names:          List of names, e.g. ["Alice", "Bob"] or ["Martin"].
        birth_years:    List of birth years, e.g. [1963, 1961].
        life_expectancy: Life expectancy in years for each person, e.g. [90, 87].
        taxable:        Taxable account balances in $k per person, e.g. [150, 150].
        tax_deferred:   Tax-deferred (401k/IRA) balances in $k per person.
        roth:           Roth account balances in $k per person.
        hsa:            HSA balances in $k per person (optional).
        cost_basis:     Taxable cost basis in $k per person (default: 50% of taxable balance).
        ss_annual_amounts: Annual Social Security benefit in $/year per person at their
                        claiming age (e.g. [28000, 32000]).  Omit or use [0,...] if none.
        ss_ages:        SS claiming ages per person (e.g. [67, 67]).
        pension_monthly_amounts: Monthly pension amounts in $/month per person.
        pension_ages:   Pension commencement ages per person.
        wages:          List of wage streams.  Each entry: {"person": 0, "annual_amount": 120000,
                        "start_year": 2026, "end_year": 2032}.  person defaults to 0.
        contributions:  List of retirement contributions.  Each entry: {"person": 0,
                        "account": "tax_deferred", "annual_amount": 23000, "end_year": 2032}.
                        account is one of: taxable, tax_deferred, roth, hsa.
        big_ticket_items: One-time or recurring extra expenses that reduce the spending budget.
                        Each entry: {"person": 0, "annual_amount": 15000, "start_year": 2026,
                        "end_year": 2030, "label": "healthcare"}.  Use for planned large
                        purchases or recurring costs NOT covered by the spending floor.
                        Distinct from debts (which have an amortization schedule).
        debts:          Amortizing loans.  Each entry: {"label": "mortgage", "type": "mortgage",
                        "balance": 350000, "rate": 3.5, "years_remaining": 20}.
                        type is "mortgage" or "loan".  balance = remaining principal today;
                        rate = annual interest rate in percent.
        fixed_assets:   Assets to be sold during or after the plan.  Each entry:
                        {"label": "house", "type": "residence", "value": 800000,
                        "basis": 400000, "rate": 0.0, "sell_year": 2035, "commission": 3.0}.
                        type: residence, real estate, stocks, collectibles, precious metals,
                        fixed annuity.  rate = real (above-inflation) growth for residence/
                        real estate; nominal growth for all others.  sell_year: 4-digit year,
                        or 0 = end of plan, or negative = years before end of plan.
                        commission in percent (e.g. 3.0 for 3%).
        state:          2-letter state abbreviation for state income tax (default "TX").
        objective:      Optimization objective: "maxSpending" (default) or "maxBequest".
        rate_method:    Return model name (use list_rate_models to see options).
        survivor_fraction: Surviving-spouse spending as percent of joint spending (default 60).
        initial_allocation: Starting stock/bond/other/cash split in percent, e.g. [60,40,0,0].
        final_allocation:   Ending allocation at end of plan horizon, e.g. [40,60,0,0].
        solver:         "HiGHS" or "MOSEK" (default: best available).
        max_time:       Solver time limit in seconds.
        gap:            MIP relative optimality gap (e.g. 1e-4).
    """
    try:
        plan = await asyncio.get_event_loop().run_in_executor(
            None,
            _run_from_params_blocking,
            names, birth_years, life_expectancy, state,
            taxable, tax_deferred, roth, hsa, cost_basis,
            ss_annual_amounts, ss_ages,
            pension_monthly_amounts, pension_ages,
            wages, contributions, big_ticket_items,
            debts, fixed_assets,
            objective, rate_method, survivor_fraction,
            initial_allocation, final_allocation,
            solver, max_time, gap,
        )
    except Exception as e:
        return json.dumps({"error": f"Plan build/solve error: {e}"})

    if plan.caseStatus != "solved":
        return json.dumps({"status": plan.caseStatus, "case_name": plan._name,
                           "error": "Case did not solve to optimality."})

    return json.dumps(plan_to_dict(plan), indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: save_case
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def save_case(
    names: list[str],
    birth_years: list[int],
    life_expectancy: list[int],
    taxable: list[float],
    tax_deferred: list[float],
    roth: list[float],
    hsa: list[float] | None = None,
    cost_basis: list[float] | None = None,
    ss_annual_amounts: list[float] | None = None,
    ss_ages: list[int] | None = None,
    pension_monthly_amounts: list[float] | None = None,
    pension_ages: list[int] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    state: str = "TX",
    objective: str = "maxSpending",
    rate_method: str = "conservative",
    survivor_fraction: float = 60.0,
    initial_allocation: list[float] = [60, 40, 0, 0],
    final_allocation: list[float] = [40, 60, 0, 0],
    output_dir: str = ".",
    case_name: str | None = None,
) -> str:
    """Save a retirement planning case to a TOML file and an HFP Excel file.

    Accepts the same parameters as run_from_params (see that tool for full
    parameter documentation).  Writes two files to output_dir:
      - Case_<name>.toml  — the plan configuration, reloadable by owlcli run
      - HFP_<name>.xlsx   — wages, contributions, big-ticket items, debts, and
                            fixed assets as time-series sheets

    Returns a JSON object with the paths of the files written.

    The case_name argument overrides the auto-generated name (default: names joined
    with "+", e.g. "alice+bob").
    """
    try:
        plan = _build_plan_from_params(
            names, birth_years, life_expectancy, state,
            taxable, tax_deferred, roth, hsa, cost_basis,
            ss_annual_amounts, ss_ages,
            pension_monthly_amounts, pension_ages,
            wages, contributions, big_ticket_items,
            debts, fixed_assets,
            objective, rate_method, survivor_fraction,
            initial_allocation, final_allocation,
        )
    except Exception as e:
        return json.dumps({"error": f"Plan build error: {e}"})

    stem = (case_name or plan._name).replace(" ", "_")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # TOML: wire up the HFP file reference before serialising
    hfp_filename = f"HFP_{stem}.xlsx"
    plan.hfpFileName = hfp_filename
    diconf = plan_to_config(plan)
    diconf["household_financial_profile"]["HFP_file_name"] = hfp_filename
    toml_path = out / f"Case_{stem}.toml"
    try:
        save_toml(diconf, str(toml_path))
    except Exception as e:
        return json.dumps({"error": f"Failed to write TOML: {e}"})

    # HFP Excel: one sheet per person (time horizons) + Debts + Fixed Assets
    hfp_path = out / hfp_filename
    tl, hl = _build_hfp_dataframes(plan)
    try:
        with pd.ExcelWriter(str(hfp_path), engine="openpyxl") as writer:
            for iname, df in tl.items():
                df.to_excel(writer, sheet_name=iname, index=False)
            for sheet_name, df in hl.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
    except Exception as e:
        return json.dumps({"error": f"Failed to write HFP Excel: {e}"})

    return json.dumps({
        "toml_file": str(toml_path),
        "hfp_file": str(hfp_path),
        "case_name": stem,
        "individuals": names,
    }, indent=2)


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
      run_from_params   build and solve from structured parameters (no TOML needed)
      save_case         save structured parameters to TOML + HFP Excel

    Configure Claude Desktop by adding to mcpServers in claude_desktop_config.json:

    \b
      "owl": {
        "command": "owlcli",
        "args": ["serve"]
      }
    """
    mcp.run(transport="stdio")
