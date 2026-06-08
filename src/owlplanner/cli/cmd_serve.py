"""
CLI command that starts an MCP (Model Context Protocol) server for Owl.

Exposes eight tools over stdio so any MCP-compatible AI client (Claude Desktop,
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
  run_stochastic    — efficient frontier over historical or Monte Carlo scenarios

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
        "run_case to optimize a scenario, compare_cases to evaluate the impact "
        "of a parameter change, run_from_params to solve directly from user-provided "
        "numbers without a TOML file, save_case to persist those parameters, and "
        "run_stochastic to compute an efficient spending frontier across historical "
        "or Monte Carlo scenarios and answer probability-of-success questions. "
        "All monetary values in JSON output are nominal dollars "
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
    ss_monthly_pias, ss_ages,
    pension_monthly_amounts, pension_ages,
    wages, contributions, big_ticket_items,
    debts, fixed_assets, spias,
    objective, rate_method, survivor_fraction,
    initial_allocation, final_allocation,
    spending_profile="smile", smile_dip=15, smile_increase=12, smile_delay=0,
    constrain_mean=False,
):
    """Build and configure a Plan from structured parameters.  Does not solve."""
    N_i = len(names)
    thisyear = datetime.date.today().year
    dobs = [f"{by}-07-01" for by in birth_years]
    case_name = "+".join(n.lower() for n in names)

    plan = Plan(names, dobs, list(life_expectancy), case_name,
                verbose=False, logstreams=[sys.stderr])

    # Account balances: MCP uses full dollars; override Plan API default of $k
    plan.setAccountBalances(
        taxable=list(taxable),
        taxDeferred=list(tax_deferred),
        taxFree=list(roth),
        hsa=list(hsa) if hsa else None,
        units="1",
    )
    if cost_basis:
        plan.setCostBasis(list(cost_basis), units="1")

    # Social Security: monthly PIA ($/month) passed directly to Plan API
    ss_pias = list(ss_monthly_pias or [0] * N_i)
    ss_claim_ages = list(ss_ages or [67] * N_i)
    plan.setSocialSecurity(ss_pias, ss_claim_ages)

    # Pensions (monthly $/month, matching Plan API)
    if pension_monthly_amounts and any(a > 0 for a in pension_monthly_amounts):
        plan.setPension(
            list(pension_monthly_amounts),
            list(pension_ages or [65] * N_i),
        )

    # Rates, state tax, spending profile
    plan.setRates(rate_method, constrain_mean=constrain_mean)
    if state:
        plan.setStateTax(state)
    plan.setSpendingProfile(spending_profile, percent=int(survivor_fraction),
                            dip=int(smile_dip), increase=int(smile_increase), delay=int(smile_delay))

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

    # SPIAs
    if spias:
        for s in spias:
            plan.addSPIA(
                individual=int(s.get("person", 0)),
                buy_year=int(s["buy_year"]),
                premium=float(s.get("premium", 0.0)),
                monthly_income=float(s["monthly_income"]),
                indexed=bool(s.get("indexed", False)),
                survivor_fraction=float(s.get("survivor_fraction", 0.0)),
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
    ss_monthly_pias, ss_ages,
    pension_monthly_amounts, pension_ages,
    wages, contributions, big_ticket_items,
    debts, fixed_assets, spias,
    objective, rate_method, survivor_fraction,
    initial_allocation, final_allocation,
    solver, max_time, gap, net_spending, min_taxable_balance,
    spending_profile="smile", smile_dip=15, smile_increase=12, smile_delay=0,
    start_roth_year=None, no_roth_person=None, max_roth_conversion=None,
    bequest=None, optimize_ss_ages=False, constrain_mean=False,
):
    plan = _build_plan_from_params(
        names, birth_years, life_expectancy, state,
        taxable, tax_deferred, roth, hsa, cost_basis,
        ss_monthly_pias, ss_ages,
        pension_monthly_amounts, pension_ages,
        wages, contributions, big_ticket_items,
        debts, fixed_assets, spias,
        objective, rate_method, survivor_fraction,
        initial_allocation, final_allocation,
        spending_profile, smile_dip, smile_increase, smile_delay,
        constrain_mean,
    )
    opts = {"units": "1"}  # MCP uses full dollars; plan API defaults to $k
    if solver:
        opts["solver"] = solver
    if max_time is not None:
        opts["maxTime"] = max_time
    if gap is not None:
        opts["gap"] = gap
    if net_spending is not None:
        opts["netSpending"] = net_spending
    if min_taxable_balance is not None:
        opts["minTaxableBalance"] = list(min_taxable_balance)
    if start_roth_year is not None:
        opts["startRothConversions"] = int(start_roth_year)
    if no_roth_person is not None:
        opts["noRothConversions"] = no_roth_person
    if max_roth_conversion is not None:
        opts["maxRothConversion"] = max_roth_conversion
    if bequest is not None:
        opts["bequest"] = bequest
    if optimize_ss_ages:
        opts["withSSAges"] = "optimize"
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
    ss_monthly_pias: list[float] | None = None,
    ss_ages: list[int] | None = None,
    pension_monthly_amounts: list[float] | None = None,
    pension_ages: list[int] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    spias: list[dict] | None = None,
    state: str = "TX",
    objective: str = "maxSpending",
    rate_method: str = "conservative",
    survivor_fraction: float = 60.0,
    initial_allocation: list[float] = [60, 40, 0, 0],
    final_allocation: list[float] = [40, 60, 0, 0],
    spending_profile: str = "smile",
    smile_dip: int = 15,
    smile_increase: int = 12,
    smile_delay: int = 0,
    solver: str | None = None,
    max_time: float | None = None,
    gap: float | None = None,
    net_spending: float | None = None,
    min_taxable_balance: list[float] | None = None,
    start_roth_year: int | None = None,
    no_roth_person: str | None = None,
    max_roth_conversion: float | None = None,
    bequest: float | None = None,
    optimize_ss_ages: bool = False,
    constrain_mean: bool = False,
) -> str:
    """Build and solve a retirement plan from structured parameters — no TOML file needed.

    All monetary values are in full dollars ($).  Time-series amounts are in $/year.
    Social Security and pensions are in $/month (monthly amounts, matching the Plan API).

    Args:
        names:          List of names, e.g. ["Alice", "Bob"] or ["Martin"].
        birth_years:    List of birth years, e.g. [1963, 1961].
        life_expectancy: Life expectancy in years for each person, e.g. [90, 87].
        taxable:        Taxable account balances in $ per person, e.g. [150000, 150000].
        tax_deferred:   Tax-deferred (401k/IRA) balances in $ per person.
        roth:           Roth account balances in $ per person.
        hsa:            HSA balances in $ per person (optional).
        cost_basis:     Taxable cost basis in $ per person (default: 50% of taxable balance).
        ss_monthly_pias: Monthly Social Security PIA (Primary Insurance Amount) in $/month
                        per person — the benefit at Full Retirement Age from your SSA
                        statement (e.g. [2667, 1833]).  Omit or use [0,...] if none.
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
                        Tax treatment by type — residence: IRC §121 exclusion applied
                        ($250k single / $500k MFJ); gain above exclusion is LTCG, excluded
                        gain + basis are tax-free.  fixed annuity: gain is ordinary income,
                        basis tax-free.  All others: full gain is LTCG, basis tax-free.
        spias:          Single Premium Immediate Annuities.  Each entry:
                        {"person": 0, "buy_year": 2026, "premium": 200000,
                         "monthly_income": 1100, "indexed": false, "survivor_fraction": 0.0}.
                        person: 0 = first individual, 1 = second (couple cases).
                        buy_year: 4-digit calendar year of purchase; income begins that year.
                          Use a year before today to model an already-purchased annuity
                          (premium is then ignored — income starts immediately).
                        premium: lump-sum cost in nominal $, deducted from the individual's
                          tax-deferred account as a non-taxable IRA rollover.
                        monthly_income: benefit per month in nominal $ at time of purchase.
                          Payments are fully taxable as ordinary income.
                        indexed: true = CPI-linked payments; false = fixed nominal (default).
                        survivor_fraction: fraction of income (0–1) continuing to the other
                          person after the annuitant dies; 0 = single-life (default);
                          0.5, 0.75, or 1.0 = joint-and-survivor.
        state:          2-letter state abbreviation for state income tax (default "TX").
        objective:      Optimization objective: "maxSpending" (default) or "maxBequest".
        rate_method:    Return model name (use list_rate_models to see options).
        survivor_fraction: Surviving-spouse spending as percent of joint spending (default 60).
        initial_allocation: Starting stock/bond/other/cash split in percent, e.g. [60,40,0,0].
        final_allocation:   Ending allocation at end of plan horizon, e.g. [40,60,0,0].
        spending_profile: Shape of the retirement spending curve: "smile" (default) or "flat".
                        "flat" = constant inflation-adjusted spending throughout retirement.
                        "smile" = go-go/slow-go/no-go shape: higher spending in the active
                        go-go years (early retirement), a dip in the slow-go years (mid-
                        retirement), and a rise in the no-go years (late retirement, driven
                        by medical costs).  The overall budget is normalized so total lifetime
                        spending is the same as flat.
        smile_dip:      Depth of the slow-go spending dip as a percent of the baseline
                        (default 15).  A value of 15 means spending at the mid-retirement
                        trough is roughly 15% below the go-go peak.
        smile_increase: Additional spending growth toward the no-go years as a percent over
                        the full plan horizon (default 12).  Captures rising medical costs
                        in late retirement.  Can be negative to model a spending decline.
        smile_delay:    Number of initial go-go years to hold spending flat at the peak
                        before the smile dip begins (default 0).  Use e.g. 5 to model 5
                        active years before the slow-go phase starts.
        solver:         "HiGHS" or "MOSEK" (default: best available).
        max_time:       Solver time limit in seconds.
        gap:            MIP relative optimality gap (e.g. 1e-4).
        net_spending:   Required when objective is "maxBequest": the annual spending floor
                        in $/year (e.g. 90000).  Ignored for maxSpending.
        min_taxable_balance: Minimum taxable account balance to keep as a safety net (emergency
                        fund), in $ per person, e.g. [20000] or [15000, 15000].  The optimizer
                        will not draw the taxable account below this floor in any year.
                        Inflation-indexed internally. Omit or use None to impose no floor.
        start_roth_year: 4-digit calendar year before which no Roth conversions are allowed
                        (e.g. 2030 = no conversions until 2030).  Useful when the user expects
                        to remain in a high bracket for several years and wants conversions
                        deferred until a lower-bracket window opens.
        no_roth_person: Name of the individual to exclude from all Roth conversions
                        (e.g. "Alice").  The other person's conversions are unaffected.
                        Couples only; ignored for single-person plans.
        max_roth_conversion: Annual cap on Roth conversions in $/year per person
                        (e.g. 50000).  The optimizer will never convert more than this
                        amount in any single year for any individual.
        bequest:        Target bequest (estate) value in today's dollars when objective is
                        "maxSpending" (e.g. 500000).  The optimizer maximizes spending
                        subject to leaving at least this amount to heirs.  Ignored when
                        objective is "maxBequest" (use net_spending there instead).
        optimize_ss_ages: If True, the optimizer finds the best Social Security claiming
                        month for each person (ages 62–70, monthly resolution) instead of
                        using the fixed ss_ages values.  The fixed ss_ages are used as
                        starting hints but the MIP is free to choose any claiming month.
                        Adds binary variables; increases solve time.
        constrain_mean: If True, each generated rate series is post-processed so its
                        arithmetic mean exactly matches the historical mean of the selected
                        window, isolating sequence-of-returns (SOR) risk from mean-estimation
                        noise.  Useful when the user is specifically worried about bad luck
                        in the ordering of returns, not about whether average returns will
                        meet historical norms.  Only effective for history-fitted stochastic
                        methods: historical_gaussian, historical_lognormal, historical_copula,
                        garch_dcc, gmm, hmm.  Silently ignored for all other methods.

    NOTE — ACA marketplace coverage: If any individual is under 65 and not yet on Medicare,
    ACA marketplace premiums may apply and are NOT modeled unless the user supplies an SLCSP
    benchmark premium via the slcsp parameter (see run_case / TOML options).  When this
    situation arises, flag it to the user and ask whether the person is covered by an
    employer plan (their own or a working spouse's) or needs ACA marketplace coverage.
    """
    try:
        plan = await asyncio.get_event_loop().run_in_executor(
            None,
            _run_from_params_blocking,
            names, birth_years, life_expectancy, state,
            taxable, tax_deferred, roth, hsa, cost_basis,
            ss_monthly_pias, ss_ages,
            pension_monthly_amounts, pension_ages,
            wages, contributions, big_ticket_items,
            debts, fixed_assets, spias,
            objective, rate_method, survivor_fraction,
            initial_allocation, final_allocation,
            solver, max_time, gap, net_spending, min_taxable_balance,
            spending_profile, smile_dip, smile_increase, smile_delay,
            start_roth_year, no_roth_person, max_roth_conversion,
            bequest, optimize_ss_ages, constrain_mean,
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
    ss_monthly_pias: list[float] | None = None,
    ss_ages: list[int] | None = None,
    pension_monthly_amounts: list[float] | None = None,
    pension_ages: list[int] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    spias: list[dict] | None = None,
    state: str = "TX",
    objective: str = "maxSpending",
    rate_method: str = "conservative",
    survivor_fraction: float = 60.0,
    initial_allocation: list[float] = [60, 40, 0, 0],
    final_allocation: list[float] = [40, 60, 0, 0],
    spending_profile: str = "smile",
    smile_dip: int = 15,
    smile_increase: int = 12,
    smile_delay: int = 0,
    net_spending: float | None = None,
    min_taxable_balance: list[float] | None = None,
    start_roth_year: int | None = None,
    no_roth_person: str | None = None,
    max_roth_conversion: float | None = None,
    bequest: float | None = None,
    optimize_ss_ages: bool = False,
    constrain_mean: bool = False,
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
    with "+", e.g. "alice+bob").  Set net_spending ($/year) when objective is
    "maxBequest" to record the spending floor in the saved TOML.
    """
    try:
        plan = _build_plan_from_params(
            names, birth_years, life_expectancy, state,
            taxable, tax_deferred, roth, hsa, cost_basis,
            ss_monthly_pias, ss_ages,
            pension_monthly_amounts, pension_ages,
            wages, contributions, big_ticket_items,
            debts, fixed_assets, spias,
            objective, rate_method, survivor_fraction,
            initial_allocation, final_allocation,
            spending_profile, smile_dip, smile_increase, smile_delay,
            constrain_mean,
        )
    except Exception as e:
        return json.dumps({"error": f"Plan build error: {e}"})

    plan.solverOptions["units"] = "1"  # MCP uses full dollars; plan API defaults to $k
    if net_spending is not None:
        plan.solverOptions["netSpending"] = net_spending
    if min_taxable_balance is not None:
        plan.solverOptions["minTaxableBalance"] = list(min_taxable_balance)
    if start_roth_year is not None:
        plan.solverOptions["startRothConversions"] = int(start_roth_year)
    if no_roth_person is not None:
        plan.solverOptions["noRothConversions"] = no_roth_person
    if max_roth_conversion is not None:
        plan.solverOptions["maxRothConversion"] = max_roth_conversion
    if bequest is not None:
        plan.solverOptions["bequest"] = bequest
    if optimize_ss_ages:
        plan.solverOptions["withSSAges"] = "optimize"

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
# Tool: run_stochastic
# ─────────────────────────────────────────────────────────────────────────────

def _stochastic_blocking(plan, scenario_method, ystart, yend, n_scenarios, opts, seed):
    """Solve base plan then run multi-scenario efficient frontier. Runs in a thread."""
    from owlplanner.stresstests import run_stochastic_spending
    from owlplanner.rates import FROM, TO

    plan.solve(plan.objective, opts)
    if plan.caseStatus != "solved":
        raise RuntimeError(f"Base deterministic plan did not solve (status: {plan.caseStatus}).")

    if seed is not None:
        plan.setReproducible(True, seed=seed)

    _ystart = ystart if ystart is not None else FROM
    _yend = yend if yend is not None else TO

    if scenario_method == "historical":
        result = run_stochastic_spending(plan, opts, "historical", ystart=_ystart, yend=_yend)
    elif scenario_method == "mc":
        if getattr(plan, "rateModel", None) is None or getattr(plan.rateModel, "deterministic", True):
            raise ValueError(
                "Monte Carlo requires a stochastic rate method "
                "(e.g. 'historical_gaussian', 'lognormal', 'historical_bootstrap'). "
                "Current rate method is deterministic."
            )
        result = run_stochastic_spending(plan, opts, "mc", N=n_scenarios)
    else:
        raise ValueError(f"Unknown scenario_method '{scenario_method}'. Use 'historical' or 'mc'.")

    return plan, result


def _build_stochastic_json(plan, result, target_success_rate, scenario_method):
    """Distil run_stochastic_spending result into a compact JSON-ready dict."""
    from owlplanner.stresstests import g_for_success_rate

    bases = result["bases"]
    lambdas = result["lambdas"]
    frontier_g = result["frontier_g"]
    frontier_prob = result["frontier_prob"]
    n_infeasible = result.get("n_infeasible", 0)

    xi0 = float(plan.xi_n[0])

    # Spending commitment at the requested success rate (frontier_g units = today's $)
    g_target, _ = g_for_success_rate(target_success_rate, lambdas, frontier_g, frontier_prob)

    # Achieved success rate at that frontier point
    target_shortfall = 1.0 - target_success_rate
    candidates = np.where(frontier_prob <= target_shortfall)[0]
    achieved_success = round(1.0 - float(frontier_prob[candidates[0] if len(candidates) else -1]), 4)

    # Downsample frontier to ~20 evenly spaced points for compact output
    step = max(1, len(frontier_g) // 20)
    frontier_pts = [
        {
            "success_rate": round(1.0 - float(frontier_prob[i]), 4),
            "spending_today_dollars": int(round(float(frontier_g[i]))),
            "spending_year1_nominal": int(round(float(frontier_g[i]) * xi0)),
        }
        for i in range(0, len(frontier_g), step)
    ]

    return {
        "status": "completed",
        "case_name": plan._name,
        "scenario_method": scenario_method,
        "n_scenarios_run": int(len(bases)),
        "n_scenarios_infeasible": int(n_infeasible),
        "target_success_rate": target_success_rate,
        "achieved_success_rate": achieved_success,
        "spending_at_target": {
            "today_dollars": int(round(g_target)),
            "year1_nominal": int(round(g_target * xi0)),
        },
        "max_spending": {
            "today_dollars": int(round(float(frontier_g[0]))),
            "year1_nominal": int(round(float(frontier_g[0]) * xi0)),
            "success_rate": round(1.0 - float(frontier_prob[0]), 4),
        },
        "frontier": frontier_pts,
    }


@mcp.tool()
async def run_stochastic(
    scenario_method: str = "historical",
    target_success_rate: float = 0.90,
    filename: str | None = None,
    overrides: list[str] = [],
    names: list[str] | None = None,
    birth_years: list[int] | None = None,
    life_expectancy: list[int] | None = None,
    taxable: list[float] | None = None,
    tax_deferred: list[float] | None = None,
    roth: list[float] | None = None,
    hsa: list[float] | None = None,
    cost_basis: list[float] | None = None,
    ss_monthly_pias: list[float] | None = None,
    ss_ages: list[int] | None = None,
    pension_monthly_amounts: list[float] | None = None,
    pension_ages: list[int] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    spias: list[dict] | None = None,
    state: str = "TX",
    objective: str = "maxSpending",
    rate_method: str = "conservative",
    survivor_fraction: float = 60.0,
    initial_allocation: list[float] = [60, 40, 0, 0],
    final_allocation: list[float] = [40, 60, 0, 0],
    spending_profile: str = "smile",
    smile_dip: int = 15,
    smile_increase: int = 12,
    smile_delay: int = 0,
    net_spending: float | None = None,
    min_taxable_balance: list[float] | None = None,
    start_roth_year: int | None = None,
    no_roth_person: str | None = None,
    max_roth_conversion: float | None = None,
    bequest: float | None = None,
    optimize_ss_ages: bool = False,
    constrain_mean: bool = False,
    n_scenarios: int = 200,
    ystart: int | None = None,
    yend: int | None = None,
    solver: str | None = None,
    max_time: float | None = None,
    seed: int | None = None,
) -> str:
    """Run multi-scenario spending optimization and return an efficient frontier.

    Solves the plan across many historical or Monte Carlo scenarios, then computes
    the Pareto frontier between committed spending and shortfall risk.  Returns the
    spending level that achieves a given probability of success and the full frontier.

    Provide the plan either as a saved TOML file (filename=) or directly via flat
    parameters (names=, birth_years=, ...) — the same set accepted by run_from_params.

    Args:
        scenario_method:      "historical" (sweep 1928–present, default) or "mc" (Monte Carlo).
                              Monte Carlo requires a stochastic rate_method such as
                              'historical_gaussian', 'lognormal', or 'historical_bootstrap'.
        target_success_rate:  Desired fraction of scenarios with no shortfall, e.g. 0.90 for 90%.
        filename:             Path to a .toml case file (alternative to flat params).
        overrides:            KEY.PATH=VALUE overrides when using filename=.
        names:                Person names, e.g. ["Alice", "Bob"].
        birth_years:          Birth years, e.g. [1963, 1961].
        life_expectancy:      Life expectancy in years per person.
        taxable:              Taxable account balances in $ per person.
        tax_deferred:         Tax-deferred (401k/IRA) balances in $ per person.
        roth:                 Roth account balances in $ per person.
        hsa:                  HSA balances in $ per person (optional).
        cost_basis:           Taxable cost basis in $ per person (optional).
        ss_monthly_pias:    Monthly SS PIA per person in $/month (benefit at FRA from SSA statement).
        ss_ages:              SS claiming ages per person.
        pension_monthly_amounts: Monthly pension amounts in $/month per person.
        pension_ages:         Pension commencement ages per person.
        wages:                Wage streams: [{"person":0,"annual_amount":90000,"end_year":2030}].
        contributions:        Contributions: [{"person":0,"account":"tax_deferred","annual_amount":23000}].
        big_ticket_items:     Extra annual expenses: [{"person":0,"annual_amount":5000,"start_year":2027}].
        debts:                Debts: [{"label":"mortgage","type":"mortgage","balance":300000,
                              "rate":3.5,"years_remaining":20}].
        fixed_assets:         Assets: [{"label":"house","type":"residence","value":800000,
                              "basis":400000,"sell_year":2040}].
                              Tax treatment: residence applies IRC §121 exclusion ($250k
                              single / $500k MFJ); fixed annuity gain is ordinary income;
                              all others (real estate, stocks, etc.) gain is LTCG.
        spias:                SPIAs: [{"person":0,"buy_year":2026,"premium":200000,
                              "monthly_income":1100,"indexed":false,"survivor_fraction":0.0}].
                              See run_from_params for full parameter documentation.
        state:                Two-letter US state code for state income tax (default "TX" = no tax).
        objective:            "maxSpending" (default) or "maxBequest".
        rate_method:          Rate model for the base deterministic solve and for MC scenarios.
        survivor_fraction:    Survivor spending as % of couple spending (default 60).
        initial_allocation:   Starting [stocks,bonds,real_estate,cash] allocation percentages.
        final_allocation:     Ending allocation percentages (glide path).
        spending_profile:     "smile" (default) or "flat".  See run_from_params for details.
        smile_dip:            Depth of slow-go spending dip in % (default 15).
        smile_increase:       No-go medical cost increase over full horizon in % (default 12).
        smile_delay:          Go-go years to hold flat before the smile dip begins (default 0).
        n_scenarios:          Number of Monte Carlo scenarios (mc mode only, default 200).
        ystart:               First historical start year (historical mode, default 1928).
        yend:                 Last historical start year (historical mode, default uses full data).
        net_spending:         Required when objective is "maxBequest": the annual spending
                              floor in $/year (e.g. 90000).  Ignored for maxSpending.
        min_taxable_balance:  Minimum taxable account balance (safety net / emergency fund),
                              in $ per person, e.g. [20000] or [15000, 15000].
        start_roth_year:      4-digit year before which Roth conversions are disabled.
        no_roth_person:       Name of individual excluded from all Roth conversions (couples only).
        max_roth_conversion:  Annual per-person Roth conversion cap in $/year.
        bequest:              Target bequest in today's $ for maxSpending objective.
        optimize_ss_ages:     If True, MIP optimizes SS claiming month (62–70) per person.
        constrain_mean:       If True, generated rate series means are pinned to historical
                              averages, isolating sequence-of-returns risk.  Supported by
                              historical_gaussian, historical_lognormal, historical_copula,
                              garch_dcc, gmm, hmm.  Ignored for other methods.
        solver:               "HiGHS", "MOSEK", or None (auto-select).
        max_time:             Per-scenario solver time limit in seconds.
        seed:                 Random seed for reproducibility.
    """
    # Build or load plan
    if filename is not None:
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
                lambda: config_to_plan(diconf, dirname, verbose=False,
                                       logstreams=[sys.stderr], loadHFP=True),
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to build plan from {filename}: {e}"})
    else:
        if names is None or birth_years is None or life_expectancy is None:
            return json.dumps({"error": (
                "Provide either 'filename' or flat parameters: "
                "names, birth_years, life_expectancy, taxable, tax_deferred, roth are required."
            )})
        try:
            plan = _build_plan_from_params(
                names, birth_years, life_expectancy, state,
                taxable, tax_deferred, roth, hsa, cost_basis,
                ss_monthly_pias, ss_ages,
                pension_monthly_amounts, pension_ages,
                wages, contributions, big_ticket_items,
                debts, fixed_assets, spias,
                objective, rate_method, survivor_fraction,
                initial_allocation, final_allocation,
                spending_profile, smile_dip, smile_increase, smile_delay,
                constrain_mean,
            )
        except Exception as e:
            return json.dumps({"error": f"Plan build error: {e}"})

    opts = {"units": "1"}  # MCP uses full dollars; plan API defaults to $k
    if solver:
        opts["solver"] = solver
    if max_time is not None:
        opts["maxTime"] = max_time
    if net_spending is not None:
        opts["netSpending"] = net_spending
    if min_taxable_balance is not None:
        opts["minTaxableBalance"] = list(min_taxable_balance)
    if start_roth_year is not None:
        opts["startRothConversions"] = int(start_roth_year)
    if no_roth_person is not None:
        opts["noRothConversions"] = no_roth_person
    if max_roth_conversion is not None:
        opts["maxRothConversion"] = max_roth_conversion
    if bequest is not None:
        opts["bequest"] = bequest
    if optimize_ss_ages:
        opts["withSSAges"] = "optimize"

    try:
        plan, result = await asyncio.get_event_loop().run_in_executor(
            None,
            _stochastic_blocking,
            plan, scenario_method, ystart, yend, n_scenarios, opts, seed,
        )
    except Exception as e:
        return json.dumps({"error": f"Stochastic run error: {e}"})

    try:
        out = _build_stochastic_json(plan, result, target_success_rate, scenario_method)
    except Exception as e:
        return json.dumps({"error": f"Result processing error: {e}"})

    return json.dumps(out, indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Click command
# ─────────────────────────────────────────────────────────────────────────────

@click.command(name="serve")
def cmd_serve():
    """Start the Owl MCP server (stdio transport).

    Exposes eight tools to any MCP-compatible AI client:

    \b
      list_cases        enumerate .toml case files in a directory
      explain_case      describe a case without solving
      list_rate_models  enumerate available rate models
      run_case          solve and return JSON results
      compare_cases     run base + variant and return delta metrics
      run_from_params   build and solve from structured parameters (no TOML needed)
      save_case         save structured parameters to TOML + HFP Excel
      run_stochastic    efficient frontier over historical or Monte Carlo scenarios

    Configure Claude Desktop by adding to mcpServers in claude_desktop_config.json:

    \b
      "owl": {
        "command": "owlcli",
        "args": ["serve"]
      }
    """
    mcp.run(transport="stdio")
