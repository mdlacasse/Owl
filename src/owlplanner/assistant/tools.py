"""
Shared assistant tool layer for Owl.

Implements the tool functions exposed by the MCP server (owlcli serve) so they
can also be reused by other assistant front ends (e.g., an embedded chat page)
without importing the MCP or click machinery.  This module deliberately does
not import mcp or click; registration with FastMCP happens in
owlplanner.cli.cmd_serve.

Tools implemented:
  list_cases               — enumerate .toml case files in a directory
  explain_case             — describe a case without solving
  list_rate_models         — enumerate available rate models and their parameters
  list_mortality_tables    — actuarial tables for longevity risk sampling
  convert_ss_benefit       — convert between SS PIA and actual benefit at a claiming age
  list_contribution_limits — IRS contribution-limit ceilings (incl. catch-up) by birth year
  run_case                 — solve a case and return structured JSON results
  compare_cases            — run base + variant and return delta metrics
  run_from_params          — build and solve from structured parameters (no TOML needed)
  save_case                — save structured parameters to TOML + HFP Excel for reproducibility
  run_stochastic           — spending frontier over historical or Monte Carlo scenarios
  run_longevity_stochastic — frontier with joint market + lifespan sampling
  run_historical           — backtest across historical sequences, return outcome distribution
  run_monte_carlo          — Monte Carlo simulations, return outcome distribution

All tool output is JSON.  Plan solver output goes to stderr so it never
pollutes the MCP stdio transport.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio
import datetime
import json
import sys
from pathlib import Path
from typing import Annotated

import numpy as np
import pandas as pd

from pydantic import Field

from owlplanner import Plan
from owlplanner.config import load_toml, config_to_plan
from owlplanner.config.plan_bridge import plan_to_config
from owlplanner.config.toml_io import save_toml
from owlplanner.config.schema import CLI_SOLVER_OVERRIDE_MAP, parse_solver_options
from owlplanner.export import plan_metrics
from owlplanner.hfp_io import conditionDebtsAndFixedAssetsDF, build_hfp_dataframes
from owlplanner.rate_models.loader import get_all_models_metadata, RATE_MODEL_ALIASES
from owlplanner.data.mortality_tables import MORTALITY_TABLE_KEYS, MORTALITY_TABLE_INFO
from owlplanner.socialsecurity import getFRAs, getSelfFactor
from owlplanner.tax_federal import contributionLimits
from owlplanner.utils import derive_swap_roth_converters

from owlplanner.rate_models.constants import CONSTRAIN_MEAN_METHODS

from owlplanner.cli.cmd_explain import _plan_to_explain
from owlplanner.cli.cmd_run import _parse_solver_opts
from owlplanner.cli.formatters import plan_to_dict, _NumpyEncoder, _diff, _pct, KEY_METRICS
from owlplanner.cli.set_override import apply_overrides


SERVER_INSTRUCTIONS = (
    "Owl (Optimal Wealth Lab) is a US retirement financial planning tool. "
    "Before building a plan for a new user, follow the owl_intake prompt "
    "(also readable as resource owl://intake-checklist): ask for state, balances, "
    "Social Security, work status, and pre-65 health coverage rather than assuming "
    "defaults; the owl://modeling-capabilities resource documents what Owl models "
    "and its limitations. "
    "Use list_cases to discover available scenarios, explain_case to inspect "
    "a configuration, list_rate_models to see return-modeling options, "
    "run_case to optimize a scenario, compare_cases to evaluate the impact "
    "of a parameter change, run_from_params to solve directly from user-provided "
    "numbers without a TOML file, save_case to persist those parameters, "
    "run_stochastic to compute an efficient spending frontier across historical "
    "or Monte Carlo scenarios and answer probability-of-success questions, "
    "run_longevity_stochastic for a frontier that jointly samples market sequences "
    "and random lifespans (use list_mortality_tables to select the right actuarial "
    "table based on the user's occupation and smoking status). "
    "All monetary values in JSON output are nominal dollars "
    "unless the key ends with '_today' or '_today_dollars'. "
    "Asset allocation arrays are [equities, corporate_bonds, t_notes, cash] — "
    "always ask the user to clarify 'bonds' before filling in an allocation, "
    "since corporate bonds (index 1) and T-notes/Treasuries (index 2) have "
    "meaningfully different historical return series. "
    "Responses from the solve tools may include an 'assumed_defaults' list "
    "describing material assumptions made for parameters the caller omitted; "
    "relay these assumptions to the user and ask for the true values when they "
    "could change the results. "
    "File paths (directory, filename) must be absolute or resolvable from the "
    "MCP server working directory — prefer absolute paths to the Owl repo or "
    "user workspace."
)


def _norm_overrides(overrides: list[str] | None) -> list[str]:
    """Return a fresh overrides list (avoids mutable default args)."""
    return list(overrides) if overrides is not None else []


def _ss_ages_opt(v) -> str | list | None:
    """Map optimize_ss_ages value to a withSSAges option string/list, or None to skip."""
    if not v:  # None, False, empty string/list
        return None
    if v is True or v == "all":
        return "optimize"
    return v  # single name string or list of names — pass through directly


def _check_person_index(person: int, n_individuals: int, context: str) -> None:
    if person < 0 or person >= n_individuals:
        raise ValueError(
            f"{context}: person index {person} is out of range "
            f"(plan has {n_individuals} individual(s), valid indices 0..{n_individuals - 1})."
        )


def _apply_roth_conversion_overrides(plan, roth_conversions, N_i, thisyear):
    """Populate plan.myRothX_in from roth_conversions (per-cell pin/force-zero overrides).

    Positive amount pins x[i,n] to that exact conversion amount; negative (any
    magnitude) forces x[i,n] to 0 that year. Only enforced when
    use_roth_conv_overrides is set on the solve options.
    """
    for rc in roth_conversions:
        i = int(rc.get("person", 0))
        _check_person_index(i, N_i, "roth_conversions")
        amount = float(_get_field(rc, "annual_amount"))
        year = int(_get_field(rc, "start_year"))
        n = year - thisyear
        if 0 <= n < plan.N_n:
            plan.myRothX_in[i, n] = amount


def _swap_roth_converters_value(inames, first_name, year):
    """Signed swapRothConverters value from (first-converter name, switch year).

    Positive = inames[0] converts first until abs(value); negative = inames[1] first
    (matches plan.py's swapRothConverters convention). Returns None if year is None.
    """
    if year is None:
        return None
    return derive_swap_roth_converters(inames, True, first_name, year)


def _build_mcp_opts(
    solver=None,
    max_time=None,
    net_spending=None,
    min_taxable_balance=None,
    start_roth_year=None,
    no_roth_person=None,
    max_roth_conversion=None,
    bequest=None,
    optimize_ss_ages=None,
    previous_magis=None,
    with_medicare=None,
    with_aca=None,
    use_roth_conv_overrides=None,
    swap_roth_converters_first=None,
    swap_roth_converters_year=None,
    inames=None,
):
    """Build solver opts dict for MCP tools (always full-dollar units)."""
    opts = {"units": "1"}
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
    _ssa = _ss_ages_opt(optimize_ss_ages)
    if _ssa is not None:
        opts["withSSAges"] = _ssa
    if previous_magis is not None:
        opts["previousMAGIs"] = list(previous_magis)
    if with_medicare is not None:
        opts["withMedicare"] = with_medicare
    if with_aca is not None:
        opts["withACA"] = with_aca
    if use_roth_conv_overrides is not None:
        opts["useRothConvOverrides"] = bool(use_roth_conv_overrides)
    _swap = _swap_roth_converters_value(inames, swap_roth_converters_first, swap_roth_converters_year)
    if _swap is not None:
        opts["swapRothConverters"] = _swap
    return opts


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_cases
# ─────────────────────────────────────────────────────────────────────────────


def list_cases(
    directory: Annotated[
        str,
        Field(
            description="Directory to scan for .toml case files (prefer absolute path).",
        ),
    ] = ".",
) -> str:
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
            diconf = load_toml(str(f))[0]
            case_name = diconf.get("case_name", f.stem)
            raw_hfp = diconf.get("household_financial_profile", {}).get("HFP_file_name", "None")
            hfp = None if (not raw_hfp or raw_hfp.lower() in ("none", "dictionary of dataframes")) else raw_hfp
            cases.append(
                {
                    "stem": f.stem,
                    "filename": str(f),
                    "case_name": case_name,
                    "has_hfp": bool(hfp and (path / hfp).exists()),
                    "hfp_file": hfp,
                }
            )
        except Exception as e:
            cases.append({"stem": f.stem, "filename": str(f), "error": str(e)})

    return json.dumps(cases, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: explain_case
# ─────────────────────────────────────────────────────────────────────────────


def explain_case(
    filename: Annotated[str, Field(description="Path to the .toml case file (prefer absolute path).")],
    overrides: Annotated[
        list[str] | None,
        Field(description='KEY.PATH=VALUE overrides, e.g. ["basic_info.state=CA"].'),
    ] = None,
) -> str:
    """Describe a retirement planning case without solving it.

    Loads and validates the TOML case file, applies any overrides, and returns
    a JSON document with: individuals, time horizon, account balances, Social
    Security and pension income, rate method, objective, and solver options.

    The 'overrides' list uses KEY.PATH=VALUE syntax, e.g.:
      ["basic_info.state=CA", "fixed_income.social_security_ages=[70,68]"]
    """
    overrides = _norm_overrides(overrides)
    try:
        diconf, dirname, _ = load_toml(filename)
    except Exception as e:
        return json.dumps({"error": f"Failed to load {filename}: {e}"})

    if overrides:
        try:
            diconf = apply_overrides(diconf, overrides)
        except Exception as e:
            return json.dumps({"error": f"Invalid override: {e}"})

    # Load the HFP workbook so fixed assets and debts are described too; fall
    # back to skipping it if the referenced file is missing.
    try:
        plan = config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=True)
    except FileNotFoundError:
        try:
            plan = config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=False)
        except Exception as e:
            return json.dumps({"error": f"Failed to build plan: {e}"})
    except Exception as e:
        return json.dumps({"error": f"Failed to build plan: {e}"})

    result = _plan_to_explain(plan, filename, overrides)
    return json.dumps(result, indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_rate_models
# ─────────────────────────────────────────────────────────────────────────────


def list_rate_models(
    category: Annotated[
        str,
        Field(description='Filter: "single", "deterministic", "stochastic", "dataframe", or "all".'),
    ] = "all",
) -> str:
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
# Tool: list_mortality_tables
# ─────────────────────────────────────────────────────────────────────────────


def list_mortality_tables() -> str:
    """List available actuarial mortality tables for longevity risk sampling.

    Returns a JSON array of mortality tables ordered from shortest to longest
    life expectancy, with the key to pass to run_longevity_stochastic and a
    plain-language description to guide table selection.

    SELECTION GUIDE — ask the user these questions in order:
      1. Does the individual smoke or have a significant smoking history?
         Yes → "VBT2015-SM"
      2. Is the individual a teacher or school employee?
         Yes → "Pub2010-Teacher"
      3. Is the individual a public safety worker (police, fire, corrections)?
         Yes → "Pub2010-Safety"
      4. Does the individual work or worked for the government (non-safety)?
         Yes → "Pub2010-General"
      5. Does the individual receive (or expect) a private-sector pension?
         Yes → "RP2014"
      6. Does the individual own or plan to buy a life annuity (SPIA)?
         Yes → "IAM2012"
      7. Is the individual a confirmed non-smoker with no occupational table?
         Yes → "VBT2015-NS"
      8. None of the above / general population:
         → "SSA2025" (default)

    For couples, use the table for the individual whose longevity matters most
    (typically the younger or healthier spouse), or call run_longevity_stochastic
    twice with different tables to bracket the range.
    """
    tables = [
        {
            "key": key,
            "le_at_65": MORTALITY_TABLE_INFO[key]["le_at_65"],
            "description": MORTALITY_TABLE_INFO[key]["description"],
        }
        for key in MORTALITY_TABLE_KEYS
        if key in MORTALITY_TABLE_INFO
    ]
    tables.sort(key=lambda t: t["le_at_65"])
    return json.dumps({"mortality_tables": tables}, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: convert_ss_benefit
# ─────────────────────────────────────────────────────────────────────────────


def convert_ss_benefit(
    birth_year: Annotated[int, Field(description="Birth year, e.g. 1961.")],
    claiming_age: Annotated[
        float,
        Field(description="SS claiming age in years (62-70); can be fractional, e.g. 65.5."),
    ],
    pia: Annotated[
        float | None,
        Field(
            description="Monthly PIA (Primary Insurance Amount, the benefit at Full "
            "Retirement Age) in $/month. Provide this OR actual_benefit, not both."
        ),
    ] = None,
    actual_benefit: Annotated[
        float | None,
        Field(
            description="Actual (or projected) monthly benefit at claiming_age, in "
            "$/month — e.g. the check amount someone says they 'get'. "
            "Provide this OR pia, not both."
        ),
    ] = None,
    birth_month: Annotated[int, Field(description="Birth month (1-12). Default 7.")] = 7,
    birth_day: Annotated[int, Field(description="Birth day of month (1-31). Default 1.")] = 1,
) -> str:
    """Convert between Social Security PIA and the actual monthly benefit at a claiming age.

    run_from_params, save_case, run_stochastic, run_longevity_stochastic, run_historical,
    and run_monte_carlo all take ss_monthly_pias — the Primary Insurance Amount (PIA),
    i.e. the benefit at Full Retirement Age (FRA) shown on the SSA statement. This is
    NOT the same as the check amount someone describes if they claimed before or after
    FRA. Use this tool to convert in either direction:

      - Given pia: returns the actual benefit payable starting at claiming_age.
      - Given actual_benefit (e.g. "I'm 65 and I get a $2,800 check"): returns the
        equivalent PIA, which can then be passed as ss_monthly_pias (with
        ss_ages=[claiming_age]) to the run_* tools.

    Provide exactly one of pia or actual_benefit. birth_month/birth_day default to
    Owl's internal convention (July 1) and only matter for FRA-transition birth years
    (1955-1959) and for the exact early/delayed-claiming reduction near month boundaries.
    """
    if (pia is None) == (actual_benefit is None):
        return json.dumps({"error": "Provide exactly one of 'pia' or 'actual_benefit'."})

    try:
        fra = float(getFRAs([birth_year], [birth_month], [birth_day])[0])
        born_on_first = birth_day == 1
        factor = getSelfFactor(fra, claiming_age, born_on_first)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    if pia is not None:
        result = {"pia": pia, "actual_benefit": round(pia * factor, 2)}
    else:
        result = {"pia": round(actual_benefit / factor, 2), "actual_benefit": actual_benefit}

    result.update({"fra": round(fra, 4), "claiming_age": claiming_age, "factor": round(factor, 4)})
    return json.dumps(result, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_contribution_limits
# ─────────────────────────────────────────────────────────────────────────────


def list_contribution_limits(
    birth_years: Annotated[list[int], Field(description="Birth years, e.g. [1963, 1961].")],
    tax_year: Annotated[
        int | None,
        Field(description="4-digit tax year, e.g. 2026 (default: the current calendar year)."),
    ] = None,
) -> str:
    """IRS contribution-limit ceilings for retirement accounts and HSAs, by person.

    For each birth year, returns the maximum annual contribution for tax_year,
    including the age-50+ catch-up and (for 401(k)/403(b)/457(b)/TSP) the
    SECURE 2.0 "super" catch-up for ages 60-63. Useful for individuals in their
    50s and 60s who want to maximize tax-advantaged saving — ask whether they'd
    like to contribute the max to each account type, then use these figures to
    populate the 'contributions' list in run_from_params / save_case:
      - 'elective_deferral' -> employer-plan contributions: account="tax_deferred"
        (traditional 401(k)/403(b)) or account="roth" (Roth 401(k)/403(b)).
      - 'ira'               -> IRA contributions: account="tax_deferred"
        (traditional IRA) or account="roth" (Roth IRA). If the person maxes
        BOTH an employer plan and an IRA in the same account bucket, sum the
        two 'max' values into one contributions entry (or add two entries —
        kappa_ijn accumulates them either way).
      - 'hsa_self_only' / 'hsa_family' -> account="hsa" (pick the tier matching
        the person's HDHP coverage).

    Limitations — this reports statutory ceilings ONLY. It does NOT check:
      - Roth IRA eligibility (phases out at higher MAGI),
      - traditional IRA deduction phase-outs when covered by a workplace plan,
      - HSA eligibility (requires enrollment in a qualifying high-deductible
        health plan, and no other disqualifying coverage).
    Flag these to the user if their income or coverage situation suggests they
    may not qualify for the full amount.
    """
    persons = [{"birth_year": by, **contributionLimits(by, tax_year=tax_year)} for by in birth_years]
    return json.dumps({"persons": persons}, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: run_case
# ─────────────────────────────────────────────────────────────────────────────


def _build_opts(plan, solver, max_time, verbose_flag, solver_opts_raw):
    """Merge CLI flags into the plan's solver options dict and validate."""
    opts = dict(plan.solverOptions)
    if solver is not None:
        opts["solver"] = solver
    if max_time is not None:
        opts["maxTime"] = max_time
    if verbose_flag is not None:
        opts["verbose"] = verbose_flag
    for key, val in _parse_solver_opts(solver_opts_raw or []):
        opts[CLI_SOLVER_OVERRIDE_MAP.get(key, key)] = val
    return parse_solver_options(opts)


def _solve_blocking(diconf, dirname, solver, max_time, seed, solver_opts_raw):
    """Load, configure, solve, and return the Plan. Runs in a thread executor."""
    plan = config_to_plan(diconf, dirname, verbose=True, logstreams=[sys.stderr], loadHFP=True)
    if seed is not None:
        plan.setReproducible(True, seed=seed)
    opts = _build_opts(plan, solver, max_time, None, solver_opts_raw)
    plan.solve(plan.objective, opts)
    return plan


async def run_case(
    filename: Annotated[str, Field(description="Path to the .toml case file (prefer absolute path).")],
    overrides: Annotated[
        list[str] | None,
        Field(description='KEY.PATH=VALUE overrides, e.g. ["basic_info.state=TX"].'),
    ] = None,
    solver: Annotated[
        str | None,
        Field(description="Solver: HiGHS, MOSEK, or omit for auto-select."),
    ] = None,
    max_time: Annotated[float | None, Field(description="Solver time limit in seconds.")] = None,
    seed: Annotated[
        int | None,
        Field(description="Random seed for stochastic rate methods."),
    ] = None,
) -> str:
    """Solve a retirement planning case and return structured JSON results.

    Loads FILENAME, applies any overrides, solves the optimization, and returns
    a JSON document with a summary of key metrics and per-year arrays.

    Args:
        filename:  Path to the .toml case file.
        overrides: KEY.PATH=VALUE overrides, e.g. ["basic_info.state=TX"].
        solver:    "HiGHS", "MOSEK", or "default" (default picks best available).
        max_time:  Solver time limit in seconds.
        seed:      Random seed for stochastic rate methods.
    """
    overrides = _norm_overrides(overrides)
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
        plan = await asyncio.get_running_loop().run_in_executor(
            None,
            _solve_blocking,
            diconf,
            dirname,
            solver,
            max_time,
            seed,
            [],
        )
    except Exception as e:
        return json.dumps({"error": f"Solver error: {e}"})

    if plan.caseStatus != "solved":
        return json.dumps(
            {"status": plan.caseStatus, "case_name": plan._name, "error": "Case did not solve to optimality."}
        )

    result = plan_to_dict(plan)
    return json.dumps(result, indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: compare_cases
# ─────────────────────────────────────────────────────────────────────────────


def _compare_blocking(diconf_base, diconf_variant, dirname, solver, max_time, seed):
    plan_base = _solve_blocking(diconf_base, dirname, solver, max_time, seed, [])
    plan_variant = _solve_blocking(diconf_variant, dirname, solver, max_time, seed, [])
    return plan_base, plan_variant


async def compare_cases(
    filename: Annotated[str, Field(description="Path to the .toml case file (prefer absolute path).")],
    overrides: Annotated[
        list[str],
        Field(description='KEY.PATH=VALUE overrides defining the variant, e.g. ["basic_info.state=MN"].'),
    ],
    solver: Annotated[str | None, Field(description="Solver: HiGHS, MOSEK, or omit for auto-select.")] = None,
    max_time: Annotated[float | None, Field(description="Per-run solver time limit in seconds.")] = None,
    seed: Annotated[int | None, Field(description="Random seed for stochastic rate methods.")] = None,
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
        plan_base, plan_variant = await asyncio.get_running_loop().run_in_executor(
            None,
            _compare_blocking,
            diconf_base,
            diconf_variant,
            dirname,
            solver,
            max_time,
            seed,
        )
    except Exception as e:
        return json.dumps({"error": f"Solver error: {e}"})

    if plan_base.caseStatus != "solved" or plan_variant.caseStatus != "solved":
        return json.dumps(
            {
                "error": "One or both cases did not solve.",
                "base_status": plan_base.caseStatus,
                "variant_status": plan_variant.caseStatus,
            }
        )

    m_base = plan_metrics(plan_base)
    m_variant = plan_metrics(plan_variant)
    delta = _diff(m_base, m_variant)

    pct_change = {k: _pct(delta[k], m_base[k]) for k in KEY_METRICS if k in delta and delta[k] is not None}

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

# Aliases accepted for dict fields in wages / contributions / big_ticket_items / debts / spias.
# Each list is [canonical, *accepted_aliases] — canonical first so error messages are clear.
_FIELD_ALIASES = {
    "annual_amount": ["annual_amount", "amount", "value"],
    "start_year": ["start_year", "year", "from_year", "start"],
    "end_year": ["end_year", "to_year", "end", "thru_year"],
    "balance": ["balance", "principal", "amount"],
    "years_remaining": ["years_remaining", "term", "years"],
    "buy_year": ["buy_year", "year", "purchase_year"],
    "monthly_income": ["monthly_income", "income", "monthly_amount", "amount"],
}


def _get_field(d: dict, canonical: str, default=None):
    """Return d[alias] for the first matching alias of *canonical*, or *default*."""
    for alias in _FIELD_ALIASES.get(canonical, [canonical]):
        if alias in d:
            return d[alias]
    if default is not None:
        return default
    known = _FIELD_ALIASES.get(canonical, [canonical])
    raise KeyError(f"Missing required field '{canonical}' (also accepted: {known[1:]}). Got keys: {list(d.keys())}")


def _build_plan_from_params(
    names,
    birth_years,
    life_expectancy,
    state,
    taxable,
    tax_deferred,
    roth,
    hsa,
    cost_basis,
    ss_monthly_pias,
    ss_ages,
    pension_monthly_amounts,
    pension_ages,
    pension_indexed=None,
    pension_survivor_fractions=None,
    wages=None,
    contributions=None,
    big_ticket_items=None,
    roth_conversions=None,
    debts=None,
    fixed_assets=None,
    spias=None,
    objective="maxSpending",
    rate_method=None,
    rate_values=None,
    rate_frm=None,
    rate_to=None,
    survivor_fraction=None,
    initial_allocation=None,
    final_allocation=None,
    spending_profile=None,
    smile_dip=15,
    smile_increase=12,
    smile_delay=0,
    constrain_mean=False,
    interpolation_method="linear",
    interpolation_center=None,
    interpolation_width=None,
    balance_date=None,
    heirs_tax_rate=None,
    slcsp=None,
    aca_start_year=None,
    rate_params=None,
    ss_trim_pct=None,
    ss_trim_year=None,
    obbba_expiration_year=None,
    dividend_rate=None,
    liquidation_tax_rate=None,
    liquidation_capgains_rate=None,
    assumed=None,
):
    """Build and configure a Plan from structured parameters.  Does not solve.

    When *assumed* is a list, material default assumptions made for omitted
    parameters are appended to it as {"parameter", "assumed", "note"} dicts
    (the assumed_defaults ledger reported back to the caller).
    """
    if assumed is None:
        assumed = []

    def _assume(parameter, value, note):
        assumed.append({"parameter": parameter, "assumed": value, "note": note})

    N_i = len(names)
    thisyear = datetime.date.today().year

    if not state:
        state = "TX"
        _assume(
            "state",
            "TX",
            "No state given; assumed TX (no state income tax). Results overstate net spending "
            "for residents of states that tax income — pass the two-letter state code.",
        )
    if rate_method is None:
        rate_method = "conservative"
        _assume(
            "rate_method",
            "conservative",
            "Fixed 'conservative' (below-average historical) returns assumed. Specify rate_method, "
            "or stress-test the plan with run_historical or run_monte_carlo.",
        )
    if spending_profile is None:
        spending_profile = "smile"
        _assume(
            "spending_profile",
            "smile",
            "Spending shape assumed 'smile' (mid-retirement dip 15%, late-life increase 12%); "
            "use 'flat' for constant inflation-adjusted spending.",
        )
    if survivor_fraction is None:
        survivor_fraction = 60.0
        if N_i == 2:
            _assume(
                "survivor_fraction",
                60,
                "Household spending assumed to drop to 60% of the profile after the first spouse dies.",
            )
    dobs = [f"{by}-07-01" for by in birth_years]
    case_name = "+".join(n.lower() for n in names)

    plan = Plan(names, dobs, list(life_expectancy), case_name, verbose=False, logstreams=[sys.stderr])

    # Account balances: MCP uses full dollars; override Plan API default of $k
    plan.setAccountBalances(
        taxable=list(taxable),
        taxDeferred=list(tax_deferred),
        taxFree=list(roth),
        hsa=list(hsa) if hsa else None,
        startDate=balance_date,
        units="1",
    )
    if cost_basis:
        plan.setCostBasis(list(cost_basis), units="1")
    elif any(taxable):
        _assume(
            "cost_basis",
            "gains from current-year appreciation only",
            "No taxable cost basis given, so realized capital gains are modeled from current-year "
            "price appreciation only — an underestimate when the account holds embedded gains. "
            "Provide cost_basis per person for accurate LTCG.",
        )

    # Social Security: monthly PIA ($/month) passed directly to Plan API
    if ss_monthly_pias is None:
        _assume(
            "ss_monthly_pias",
            0,
            "No Social Security benefits modeled. If the household expects benefits, provide the "
            "monthly PIA per person from their SSA statements.",
        )
    elif ss_ages is None and any(ss_monthly_pias):
        _assume("ss_ages", 67, "Social Security claiming ages assumed 67 for everyone.")
    ss_pias = list(ss_monthly_pias or [0] * N_i)
    ss_claim_ages = list(ss_ages or [67] * N_i)
    plan.setSocialSecurity(
        ss_pias,
        ss_claim_ages,
        trim_pct=int(ss_trim_pct) if ss_trim_pct is not None else 0,
        trim_year=int(ss_trim_year) if ss_trim_year is not None else None,
    )

    # Pensions (monthly $/month, matching Plan API)
    if pension_monthly_amounts:
        plan.setPension(
            list(pension_monthly_amounts),
            list(pension_ages or [65] * N_i),
            indexed=list(pension_indexed) if pension_indexed is not None else None,
            survivor_fraction=list(pension_survivor_fractions) if pension_survivor_fractions is not None else None,
        )

    # Rates, state tax, spending profile
    if constrain_mean and rate_method not in CONSTRAIN_MEAN_METHODS:
        raise ValueError(
            f"constrain_mean=True has no effect for rate_method='{rate_method}'. "
            f"Supported methods: {', '.join(sorted(CONSTRAIN_MEAN_METHODS))}."
        )
    plan.setRates(
        rate_method, frm=rate_frm, to=rate_to, values=rate_values, constrain_mean=constrain_mean, **(rate_params or {})
    )
    if state:
        plan.setStateTax(state)
    plan.setSpendingProfile(
        spending_profile,
        percent=int(survivor_fraction),
        dip=int(smile_dip),
        increase=int(smile_increase),
        delay=int(smile_delay),
    )

    # Asset allocation glide path
    if interpolation_method == "s-curve":
        plan.setInterpolationMethod("s-curve", float(interpolation_center or 15), float(interpolation_width or 5))
    elif interpolation_method != "linear":
        raise ValueError(f"interpolation_method must be 'linear' or 's-curve', got '{interpolation_method}'")
    alloc_init = list(initial_allocation) if initial_allocation is not None else [60, 40, 0, 0]
    alloc_final = list(final_allocation) if final_allocation is not None else [40, 60, 0, 0]
    if initial_allocation is None and final_allocation is None:
        _assume(
            "asset_allocation",
            "60/40 gliding to 40/60",
            "Allocation assumed 60% equities / 40% corporate bonds, gliding linearly to 40/60 over "
            "the plan; pass initial_allocation and final_allocation to override.",
        )
    elif initial_allocation is None:
        _assume("initial_allocation", "60/40/0/0", "Initial allocation assumed 60% equities / 40% corporate bonds.")
    elif final_allocation is None:
        _assume("final_allocation", "40/60/0/0", "Final allocation assumed 40% equities / 60% corporate bonds.")
    if N_i == 2:
        plan.setAllocationRatios("spouses", generic=[alloc_init, alloc_final])
    else:
        plan.setAllocationRatios("individual", generic=[[alloc_init, alloc_final]])

    # Time-series: wages → omega_in  (annual $/year)
    if wages:
        for w in wages:
            i = int(w.get("person", 0))
            _check_person_index(i, N_i, "wages")
            amount = float(_get_field(w, "annual_amount"))
            start_yr = int(_get_field(w, "start_year", thisyear))
            end_yr = int(_get_field(w, "end_year", thisyear + int(plan.horizons[i])))
            for n in range(plan.N_n):
                if start_yr <= thisyear + n < end_yr:
                    plan.omega_in[i, n] += amount

    # Time-series: contributions → kappa_ijn  (annual $/year)
    if contributions:
        for c in contributions:
            i = int(c.get("person", 0))
            _check_person_index(i, N_i, "contributions")
            j = _ACCOUNT_J.get(str(c["account"]).lower(), 1)
            amount = float(_get_field(c, "annual_amount"))
            start_yr = int(_get_field(c, "start_year", thisyear))
            end_yr = int(_get_field(c, "end_year", thisyear + int(plan.horizons[i])))
            for n in range(plan.N_n):
                if start_yr <= thisyear + n < end_yr:
                    plan.kappa_ijn[i, j, n] += amount

    # Time-series: big-ticket items → Lambda_in  (annual $/year, positive = extra expense)
    if big_ticket_items:
        for bt in big_ticket_items:
            i = int(bt.get("person", 0))
            _check_person_index(i, N_i, "big_ticket_items")
            amount = float(_get_field(bt, "annual_amount"))
            start_yr = int(_get_field(bt, "start_year"))
            end_yr = int(_get_field(bt, "end_year", start_yr + 1))
            for n in range(plan.N_n):
                if start_yr <= thisyear + n < end_yr:
                    plan.Lambda_in[i, n] += amount

    # Roth conversion overrides → myRothX_in (see _apply_roth_conversion_overrides)
    if roth_conversions:
        _apply_roth_conversion_overrides(plan, roth_conversions, N_i, thisyear)

    # Debts → houseLists["Debts"]
    # balance = remaining principal (starts today), rate in %, years_remaining = remaining term
    if debts:
        rows = [
            {
                "active": True,
                "name": d.get("label", "debt"),
                "type": d.get("type", "loan"),
                "year": thisyear,
                "term": int(_get_field(d, "years_remaining")),
                "amount": float(_get_field(d, "balance")),
                "rate": float(d["rate"]),
            }
            for d in debts
        ]
        plan.houseLists["Debts"] = conditionDebtsAndFixedAssetsDF(pd.DataFrame(rows), "Debts")

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
        plan.houseLists["Fixed Assets"] = conditionDebtsAndFixedAssetsDF(pd.DataFrame(rows), "Fixed Assets")

    # SPIAs
    if spias:
        for s in spias:
            plan.addSPIA(
                individual=int(s.get("person", 0)),
                buy_year=int(_get_field(s, "buy_year")),
                premium=float(s.get("premium", 0.0)),
                monthly_income=float(_get_field(s, "monthly_income")),
                indexed=bool(s.get("indexed", False)),
                survivor_fraction=float(s.get("survivor_fraction", 0.0)),
            )

    if heirs_tax_rate is not None:
        plan.setHeirsTaxRate(float(heirs_tax_rate))
    elif any(tax_deferred) or (hsa and any(hsa)):
        _assume(
            "heirs_tax_rate",
            30,
            "Heirs' marginal income-tax rate on inherited tax-deferred and HSA balances assumed 30% "
            "when valuing the after-tax bequest.",
        )

    # Liquidation rates drive the liquid balance sheet (set before solve so the
    # disposition-cost array uses the requested capital-gains rate).
    if liquidation_tax_rate is not None:
        plan.setLiquidationTaxRate(float(liquidation_tax_rate))
    if liquidation_capgains_rate is not None:
        plan.setLiquidationCapGainsRate(float(liquidation_capgains_rate))

    if slcsp is not None and float(slcsp) > 0:
        plan.setACA(float(slcsp), units="1", start_year=aca_start_year)
    elif slcsp is None and any(thisyear - by < 65 for by in birth_years):
        _assume(
            "slcsp",
            "no ACA modeling",
            "Household has pre-65 years but no SLCSP benchmark premium was given, so ACA marketplace "
            "premiums and credits are not modeled. Fine when employer coverage lasts until 65; "
            "otherwise provide slcsp (annual Silver benchmark premium).",
        )

    if obbba_expiration_year is not None:
        plan.setExpirationYearOBBBA(int(obbba_expiration_year))
    if dividend_rate is not None:
        plan.setDividendRate(float(dividend_rate))

    # houseLists is now populated; processDebtsAndFixedAssets() will be called
    # automatically by solve() after _adjustParameters sets the inflation path.
    plan.objective = objective
    return plan


# ─────────────────────────────────────────────────────────────────────────────
# Tool: run_from_params
# ─────────────────────────────────────────────────────────────────────────────


def _run_from_params_blocking(
    names,
    birth_years,
    life_expectancy,
    state,
    taxable,
    tax_deferred,
    roth,
    hsa,
    cost_basis,
    ss_monthly_pias,
    ss_ages,
    pension_monthly_amounts,
    pension_ages,
    pension_indexed=None,
    pension_survivor_fractions=None,
    wages=None,
    contributions=None,
    big_ticket_items=None,
    roth_conversions=None,
    debts=None,
    fixed_assets=None,
    spias=None,
    objective="maxSpending",
    rate_method=None,
    rate_values=None,
    rate_frm=None,
    rate_to=None,
    survivor_fraction=None,
    initial_allocation=None,
    final_allocation=None,
    solver=None,
    max_time=None,
    net_spending=None,
    min_taxable_balance=None,
    spending_profile=None,
    smile_dip=15,
    smile_increase=12,
    smile_delay=0,
    start_roth_year=None,
    no_roth_person=None,
    max_roth_conversion=None,
    use_roth_conv_overrides=None,
    swap_roth_converters_first=None,
    swap_roth_converters_year=None,
    bequest=None,
    optimize_ss_ages=None,
    constrain_mean=False,
    interpolation_method="linear",
    interpolation_center=None,
    interpolation_width=None,
    balance_date=None,
    heirs_tax_rate=None,
    previous_magis=None,
    with_medicare=None,
    with_aca=None,
    aca_start_year=None,
    slcsp=None,
    ss_trim_pct=None,
    ss_trim_year=None,
    obbba_expiration_year=None,
    dividend_rate=None,
    liquidation_tax_rate=None,
    liquidation_capgains_rate=None,
    assumed=None,
):
    plan = _build_plan_from_params(
        names,
        birth_years,
        life_expectancy,
        state,
        taxable,
        tax_deferred,
        roth,
        hsa,
        cost_basis,
        ss_monthly_pias,
        ss_ages,
        pension_monthly_amounts,
        pension_ages,
        pension_indexed,
        pension_survivor_fractions,
        wages,
        contributions,
        big_ticket_items,
        roth_conversions,
        debts,
        fixed_assets,
        spias,
        objective,
        rate_method,
        rate_values,
        rate_frm,
        rate_to,
        survivor_fraction,
        initial_allocation,
        final_allocation,
        spending_profile,
        smile_dip,
        smile_increase,
        smile_delay,
        constrain_mean,
        interpolation_method,
        interpolation_center,
        interpolation_width,
        balance_date,
        heirs_tax_rate=heirs_tax_rate,
        slcsp=slcsp,
        aca_start_year=aca_start_year,
        ss_trim_pct=ss_trim_pct,
        ss_trim_year=ss_trim_year,
        obbba_expiration_year=obbba_expiration_year,
        dividend_rate=dividend_rate,
        liquidation_tax_rate=liquidation_tax_rate,
        liquidation_capgains_rate=liquidation_capgains_rate,
        assumed=assumed,
    )
    if (
        assumed is not None
        and previous_magis is None
        and any(datetime.date.today().year - by >= 63 for by in birth_years)
    ):
        assumed.append(
            {
                "parameter": "previous_magis",
                "assumed": 0,
                "note": "Prior-year MAGIs not provided; assumed zero, so the first two plan years "
                "carry base Medicare premiums with no IRMAA surcharge.",
            }
        )
    opts = _build_mcp_opts(
        solver=solver,
        max_time=max_time,
        net_spending=net_spending,
        min_taxable_balance=min_taxable_balance,
        start_roth_year=start_roth_year,
        no_roth_person=no_roth_person,
        max_roth_conversion=max_roth_conversion,
        bequest=bequest,
        optimize_ss_ages=optimize_ss_ages,
        previous_magis=previous_magis,
        with_medicare=with_medicare,
        with_aca=with_aca,
        use_roth_conv_overrides=use_roth_conv_overrides,
        swap_roth_converters_first=swap_roth_converters_first,
        swap_roth_converters_year=swap_roth_converters_year,
        inames=plan.inames,
    )
    plan.solve(objective, opts)
    return plan


async def run_from_params(
    names: Annotated[list[str], Field(description='Person names, e.g. ["Alice", "Bob"].')],
    birth_years: Annotated[list[int], Field(description="Birth years, e.g. [1963, 1961].")],
    life_expectancy: Annotated[list[int], Field(description="Life expectancy in years per person, e.g. [90, 87].")],
    taxable: Annotated[list[float], Field(description="Taxable account balances in $ per person.")],
    tax_deferred: Annotated[list[float], Field(description="Tax-deferred (401k/IRA/403b) balances in $ per person.")],
    roth: Annotated[list[float], Field(description="Roth account balances in $ per person.")],
    hsa: list[float] | None = None,
    cost_basis: list[float] | None = None,
    ss_monthly_pias: list[float] | None = None,
    ss_ages: list[int] | None = None,
    pension_monthly_amounts: list[float] | None = None,
    pension_ages: list[int] | None = None,
    pension_indexed: list[bool] | None = None,
    pension_survivor_fractions: list[float] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    roth_conversions: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    spias: list[dict] | None = None,
    state: Annotated[
        str | None,
        Field(
            description="Two-letter US state for income tax. Strongly recommended; if omitted, "
            "TX (no state income tax) is assumed and flagged in assumed_defaults."
        ),
    ] = None,
    objective: Annotated[str, Field(description="maxSpending (default) or maxBequest.")] = "maxSpending",
    rate_method: Annotated[
        str | None,
        Field(
            description="Return model name (use list_rate_models). If omitted, fixed 'conservative' "
            "rates are assumed and flagged in assumed_defaults."
        ),
    ] = None,
    rate_values: Annotated[
        list[float] | None,
        Field(description='Fixed rates in % [equities, corporate_bonds, t_notes, inflation] for rate_method="user".'),
    ] = None,
    rate_frm: Annotated[int | None, Field(description="First year of historical rate window (e.g. 1966).")] = None,
    rate_to: Annotated[int | None, Field(description="Last year of historical rate window (e.g. 1996).")] = None,
    survivor_fraction: float | None = None,
    initial_allocation: list[float] | None = None,
    final_allocation: list[float] | None = None,
    interpolation_method: str = "linear",
    interpolation_center: float | None = None,
    interpolation_width: float | None = None,
    balance_date: str | None = None,
    spending_profile: str | None = None,
    smile_dip: int = 15,
    smile_increase: int = 12,
    smile_delay: int = 0,
    solver: str | None = None,
    max_time: float | None = None,
    net_spending: float | None = None,
    min_taxable_balance: list[float] | None = None,
    start_roth_year: int | None = None,
    no_roth_person: str | None = None,
    max_roth_conversion: float | None = None,
    use_roth_conv_overrides: bool | None = None,
    swap_roth_converters_first: str | None = None,
    swap_roth_converters_year: int | None = None,
    bequest: float | None = None,
    heirs_tax_rate: float | None = None,
    previous_magis: list[float] | None = None,
    with_medicare: str | None = None,
    with_aca: str | None = None,
    aca_start_year: int | None = None,
    optimize_ss_ages: bool | str | list[str] | None = None,
    constrain_mean: bool = False,
    slcsp: Annotated[
        float | None,
        Field(description="Annual ACA Silver benchmark premium in $/year (today's $) for pre-65 individuals."),
    ] = None,
    ss_trim_pct: int | None = None,
    ss_trim_year: int | None = None,
    obbba_expiration_year: int | None = None,
    dividend_rate: float | None = None,
    liquidation_tax_rate: Annotated[
        float | None,
        Field(
            description="Assumed ordinary tax rate (%) on tax-deferred/HSA if liquidated, for the "
            "liquid balance sheet (default 24)."
        ),
    ] = None,
    liquidation_capgains_rate: Annotated[
        float | None,
        Field(
            description="Assumed capital-gains tax rate (%) on fixed-asset disposition, for the "
            "liquid balance sheet (default 15)."
        ),
    ] = None,
) -> str:
    """Build and solve a retirement plan from structured parameters — no TOML file needed.

    All monetary values are in full dollars ($).  Time-series amounts are in $/year.
    Social Security and pensions are in $/month (monthly amounts, matching the Plan API).

    Material defaults applied to omitted parameters are reported in the 'assumed_defaults'
    field of the response — relay them to the user and refine the inputs when they matter.

    Args:
        names:          List of names, e.g. ["Alice", "Bob"] or ["Martin"].
        birth_years:    List of birth years, e.g. [1963, 1961].
        life_expectancy: Life expectancy in years for each person, e.g. [90, 87].
        taxable:        Taxable account balances in $ per person, e.g. [150000, 150000].
        tax_deferred:   Tax-deferred (401k/IRA) balances in $ per person.
        roth:           Roth account balances in $ per person.
        hsa:            HSA balances in $ per person (optional).
        cost_basis:     Taxable cost basis in $ per person.  If omitted, realized gains are
                        modeled from current-year appreciation only (flagged in assumed_defaults).
        ss_monthly_pias: Monthly Social Security PIA (Primary Insurance Amount) in $/month
                        per person — the benefit at Full Retirement Age from your SSA
                        statement (e.g. [2667, 1833]).  Omit or use [0,...] if none.
        ss_ages:        SS claiming ages per person (e.g. [67, 67]).
        pension_monthly_amounts: Monthly pension amounts in $/month per person.
        pension_ages:   Pension commencement ages per person.
        pension_indexed: Whether each pension is inflation-indexed (CPI-linked), one bool per
                        person, e.g. [True, False].  Default: all False (fixed nominal payments).
        pension_survivor_fractions: Fraction of each pension continuing to the surviving spouse
                        after the pensioner dies (0–1), one value per person, e.g. [0.5, 0.0].
                        Default: all 0 (single-life, no survivor benefit).
        wages:          List of wage streams.  Each entry: {"person": 0, "annual_amount": 120000,
                        "start_year": 2026, "end_year": 2032}.  person defaults to 0.
        contributions:  List of retirement contributions.  Each entry: {"person": 0,
                        "account": "tax_deferred", "annual_amount": 23000, "end_year": 2032}.
                        account is one of: taxable, tax_deferred, roth, hsa.  For
                        individuals in their 50s/60s, call list_contribution_limits
                        first to find the IRS max (including 50+ and 60-63 "super"
                        catch-up amounts) before filling in annual_amount.
        big_ticket_items: One-time or recurring extra expenses that reduce the spending budget.
                        Each entry: {"person": 0, "annual_amount": 15000, "start_year": 2026,
                        "end_year": 2030, "label": "healthcare"}.  Use for planned large
                        purchases or recurring costs NOT covered by the spending floor.
                        Distinct from debts (which have an amortization schedule).
        roth_conversions: Per-cell Roth conversion overrides, only enforced when
                        use_roth_conv_overrides is true.  Each entry: {"person": 0,
                        "year": 2026, "amount": 20000}.  A positive amount pins that
                        person's conversion for that year to exactly this value
                        (bypassing max_roth_conversion and other Roth policy options);
                        a negative amount forces zero conversion that year (the
                        magnitude is ignored, so flipping the sign toggles a value on/off
                        without losing it).  Years/cells not listed remain free, governed
                        by the other Roth options.  Use this to pin a conversion you've
                        already made this year, test skipping a specific year, or supply
                        your own bracket-surfing schedule for some years while letting
                        Owl optimize the rest.
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
        state:          2-letter state abbreviation for state income tax.  Ask for it; when
                        omitted, TX (no state tax) is assumed and flagged in assumed_defaults.
        objective:      Optimization objective: "maxSpending" (default) or "maxBequest".
        rate_method:    Return model name (use list_rate_models to see options).  Use "user"
                        together with rate_values to specify custom fixed rates; use
                        "historical" together with rate_frm/rate_to for a specific
                        historical sequence.
        rate_values:    Four rates in percent [equities, corporate_bonds, t_notes, inflation]
                        for the "user" rate method, e.g. [7.0, 4.0, 3.3, 2.8].  Ignored unless
                        rate_method is "user".
        rate_frm:       First calendar year of the historical window, e.g. 1966.  Only
                        relevant for history-based methods (historical, historical_gaussian,
                        historical_lognormal, historical_bootstrap, historical_average, etc.).
                        Defaults to the earliest available year (1928).
        rate_to:        Last calendar year of the historical window, e.g. 1996.  Defaults
                        to the most recent available year.
        survivor_fraction: Surviving-spouse spending as percent of joint spending (default 60).
        initial_allocation: Starting allocation as [i0, i1, i2, i3] in percent (must sum to 100).
                        The four indices are FIXED and order-sensitive:
                          i0 = equities (S&P 500 / broad stock market)
                          i1 = corporate bonds (investment-grade)
                          i2 = fixed income / T-notes (government bonds, e.g. 10-yr Treasury)
                          i3 = cash / money market
                        IMPORTANT: "bonds" is ambiguous — always clarify whether the user
                        means corporate bonds (i1) or T-notes/Treasuries (i2) before
                        populating this field.  Example: [60, 40, 0, 0] is 60% equities +
                        40% corporate bonds; [60, 0, 40, 0] is 60% equities + 40% T-notes.
        final_allocation:   Ending allocation at end of plan horizon, same [i0,i1,i2,i3]
                        encoding as initial_allocation.
        interpolation_method: Shape of the glide path between initial and final allocation.
                        "linear" (default) — straight-line interpolation year by year.
                        "s-curve" — smooth S-shaped transition using a hyperbolic tangent;
                        requires interpolation_center and interpolation_width.
        interpolation_center: For "s-curve": year from the start of the plan where the
                        midpoint of the transition occurs (default 15).  E.g. 15 means
                        the allocation is halfway between initial and final at year 15.
        interpolation_width: For "s-curve": half-width of the transition in years (default 5).
                        The bulk of the shift happens between center±width; smaller values
                        give a sharper step, larger values a more gradual sweep.
        balance_date:   Date the account balances were recorded, as "MM-DD" or "YYYY-MM-DD"
                        (default: today).  Only the month and day are used; the year is
                        ignored.  Sets the fraction of the first calendar year remaining,
                        which scales first-year cash flows.  Use this when balances come
                        from a year-end statement (e.g. "12-31") or a mid-year snapshot.
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
        use_roth_conv_overrides: When true, enforce the per-cell pins/exclusions given in
                        roth_conversions as hard constraints (see roth_conversions for the
                        positive/negative semantics).  Default false: roth_conversions
                        entries, if any, are ignored.
        swap_roth_converters_first: Name of the individual who performs Roth conversions
                        first (e.g. "Alice").  Couples only.  Combine with
                        swap_roth_converters_year to switch which spouse converts partway
                        through the plan; the other spouse converts before that year and
                        is excluded afterward (and vice versa).  Setting this takes
                        precedence over no_roth_person.
        swap_roth_converters_year: 4-digit calendar year at which Roth conversion
                        responsibility switches from swap_roth_converters_first to the
                        other individual.  Required (with swap_roth_converters_first) to
                        activate the swap; ignored for single-person plans.
        bequest:        Target bequest (estate) value in today's dollars when objective is
                        "maxSpending" (e.g. 500000).  The optimizer maximizes spending
                        subject to leaving at least this amount to heirs.  Ignored when
                        objective is "maxBequest" (use net_spending there instead).
        heirs_tax_rate: Marginal income tax rate (%) applied to the tax-deferred portion
                        of the estate when heirs inherit (default 30%).  Affects Roth
                        conversion aggressiveness: higher rates make Roth conversions more
                        attractive.  E.g. 22 if heirs are in the 22% bracket.
        with_aca:       ACA premium modeling mode: "none", "loop" (iterative, default when
                        slcsp is set), or "optimize" (embed in MIP).  Requires slcsp > 0.
        aca_start_year: Calendar year ACA coverage begins (e.g. 2028 if retiring that year).
                        Omit or 0 to start from the plan's first year.
        with_medicare:  Medicare IRMAA modeling mode: "none" (disable), "loop" (iterative
                        SC-loop, default when Medicare is on), or "optimize" (embed IRMAA
                        bracket selection in the MIP for a globally optimal result).  Use
                        "none" for cases where Medicare premiums are irrelevant (e.g. Roth-
                        only portfolios with no taxable income).  Omit to use Owl's default
                        (currently "loop" when Medicare ages are reached).
        previous_magis:  Prior-year MAGI for each person in $ (e.g. [200000, 200000]).
                        Used to determine the Medicare IRMAA surcharge bracket in the first
                        two plan years, where premiums are based on income two years prior.
                        Omit if unknown; Owl will assume the lowest bracket.
        optimize_ss_ages: Controls SS claiming-age optimization (MIP, monthly precision, 62–70).
                        True or "all" → optimize all individuals.
                        A single name string (e.g. "Alice") → optimize only that person.
                        A list of names (e.g. ["Alice"]) → optimize those people.
                        None or False → use fixed ss_ages for everyone (default).
                        Already-claimed individuals are detected automatically (current age >=
                        ss_ages value) and pinned to their recorded age regardless of this setting.
                        Formerly: If True, the optimizer finds the best Social Security claiming
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
        ss_trim_pct:    SS trust fund haircut — percent reduction in SS benefits (0–100).
                        Combined with ss_trim_year, models trust fund depletion.  Example:
                        ss_trim_pct=23, ss_trim_year=2033 matches the SSA trustees report
                        baseline scenario.  Default 0 (no reduction).
        ss_trim_year:   Year when the SS benefit reduction begins (e.g. 2033).  Only
                        effective when ss_trim_pct > 0.
        obbba_expiration_year: Year OBBBA (2025 Tax Reform) rates are assumed to sunset
                        and revert to pre-TCJA levels (default 2032).  Adjusting this
                        models different Congressional scenarios.
        dividend_rate:  Annual dividend yield for taxable accounts in % (default 1.8).
        liquidation_tax_rate: Assumed ordinary income tax rate (%) applied to
                        tax-deferred and HSA balances on the liquid balance sheet —
                        the tax owed if those accounts were liquidated (default 24).
        liquidation_capgains_rate: Assumed capital-gains tax rate (%) on fixed-asset
                        disposition (commission plus gains tax) for the liquid
                        balance sheet (default 15).

    slcsp:          Annual ACA Silver benchmark premium in $/year (today's $) for
                    individuals under 65 not yet on Medicare.  Omit if covered by
                    employer plan or ACA not applicable.

    NOTE — ACA marketplace coverage: If any individual is under 65 and not yet on Medicare,
    ACA marketplace premiums may apply and are NOT modeled unless slcsp is set AND with_aca
    is provided (e.g. with_aca="loop").  When this situation arises, flag it to the user and
    ask whether the person is covered by an employer plan (their own or a working
    spouse's) or needs ACA marketplace coverage.
    """
    assumed: list[dict] = []
    try:
        plan = await asyncio.get_running_loop().run_in_executor(
            None,
            _run_from_params_blocking,
            names,
            birth_years,
            life_expectancy,
            state,
            taxable,
            tax_deferred,
            roth,
            hsa,
            cost_basis,
            ss_monthly_pias,
            ss_ages,
            pension_monthly_amounts,
            pension_ages,
            pension_indexed,
            pension_survivor_fractions,
            wages,
            contributions,
            big_ticket_items,
            roth_conversions,
            debts,
            fixed_assets,
            spias,
            objective,
            rate_method,
            rate_values,
            rate_frm,
            rate_to,
            survivor_fraction,
            initial_allocation,
            final_allocation,
            solver,
            max_time,
            net_spending,
            min_taxable_balance,
            spending_profile,
            smile_dip,
            smile_increase,
            smile_delay,
            start_roth_year,
            no_roth_person,
            max_roth_conversion,
            use_roth_conv_overrides,
            swap_roth_converters_first,
            swap_roth_converters_year,
            bequest,
            optimize_ss_ages,
            constrain_mean,
            interpolation_method,
            interpolation_center,
            interpolation_width,
            balance_date,
            heirs_tax_rate,
            previous_magis,
            with_medicare,
            with_aca,
            aca_start_year,
            slcsp,
            ss_trim_pct,
            ss_trim_year,
            obbba_expiration_year,
            dividend_rate,
            liquidation_tax_rate,
            liquidation_capgains_rate,
            assumed,
        )
    except Exception as e:
        return json.dumps({"error": f"Plan build/solve error: {e}"})

    if plan.caseStatus != "solved":
        failed = {"status": plan.caseStatus, "case_name": plan._name, "error": "Case did not solve to optimality."}
        if assumed:
            failed["assumed_defaults"] = assumed
        return json.dumps(failed)

    result = plan_to_dict(plan)
    if assumed:
        result["assumed_defaults"] = assumed
    return json.dumps(result, indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: save_case
# ─────────────────────────────────────────────────────────────────────────────


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
    pension_indexed: list[bool] | None = None,
    pension_survivor_fractions: list[float] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    roth_conversions: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    spias: list[dict] | None = None,
    state: str | None = None,
    objective: str = "maxSpending",
    rate_method: str = "conservative",
    rate_values: list[float] | None = None,
    rate_frm: int | None = None,
    rate_to: int | None = None,
    survivor_fraction: float | None = None,
    initial_allocation: list[float] | None = None,
    final_allocation: list[float] | None = None,
    interpolation_method: str = "linear",
    interpolation_center: float | None = None,
    interpolation_width: float | None = None,
    balance_date: str | None = None,
    spending_profile: str | None = None,
    smile_dip: int = 15,
    smile_increase: int = 12,
    smile_delay: int = 0,
    net_spending: float | None = None,
    min_taxable_balance: list[float] | None = None,
    start_roth_year: int | None = None,
    no_roth_person: str | None = None,
    max_roth_conversion: float | None = None,
    use_roth_conv_overrides: bool | None = None,
    swap_roth_converters_first: str | None = None,
    swap_roth_converters_year: int | None = None,
    bequest: float | None = None,
    heirs_tax_rate: float | None = None,
    previous_magis: list[float] | None = None,
    with_medicare: str | None = None,
    with_aca: str | None = None,
    aca_start_year: int | None = None,
    optimize_ss_ages: bool | str | list[str] | None = None,
    constrain_mean: bool = False,
    slcsp: float | None = None,
    ss_trim_pct: int | None = None,
    ss_trim_year: int | None = None,
    obbba_expiration_year: int | None = None,
    dividend_rate: float | None = None,
    liquidation_tax_rate: float | None = None,
    liquidation_capgains_rate: float | None = None,
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
    assumed: list[dict] = []
    try:
        plan = _build_plan_from_params(
            names,
            birth_years,
            life_expectancy,
            state,
            taxable,
            tax_deferred,
            roth,
            hsa,
            cost_basis,
            ss_monthly_pias,
            ss_ages,
            pension_monthly_amounts,
            pension_ages,
            pension_indexed,
            pension_survivor_fractions,
            wages,
            contributions,
            big_ticket_items,
            roth_conversions,
            debts,
            fixed_assets,
            spias,
            objective,
            rate_method,
            rate_values,
            rate_frm,
            rate_to,
            survivor_fraction,
            initial_allocation,
            final_allocation,
            spending_profile,
            smile_dip,
            smile_increase,
            smile_delay,
            constrain_mean,
            interpolation_method,
            interpolation_center,
            interpolation_width,
            balance_date,
            heirs_tax_rate=heirs_tax_rate,
            slcsp=slcsp,
            aca_start_year=aca_start_year,
            ss_trim_pct=ss_trim_pct,
            ss_trim_year=ss_trim_year,
            obbba_expiration_year=obbba_expiration_year,
            dividend_rate=dividend_rate,
            liquidation_tax_rate=liquidation_tax_rate,
            liquidation_capgains_rate=liquidation_capgains_rate,
            assumed=assumed,
        )
    except Exception as e:
        return json.dumps({"error": f"Plan build error: {e}"})

    plan.solverOptions["units"] = "1"  # MCP uses full dollars; plan API defaults to $k
    if previous_magis is not None:
        plan.solverOptions["previousMAGIs"] = list(previous_magis)
    if with_medicare is not None:
        plan.solverOptions["withMedicare"] = with_medicare
    if with_aca is not None:
        plan.solverOptions["withACA"] = with_aca
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
    if use_roth_conv_overrides is not None:
        plan.solverOptions["useRothConvOverrides"] = bool(use_roth_conv_overrides)
    _swap = _swap_roth_converters_value(plan.inames, swap_roth_converters_first, swap_roth_converters_year)
    if _swap is not None:
        plan.solverOptions["swapRothConverters"] = _swap
    if bequest is not None:
        plan.solverOptions["bequest"] = bequest
    _ssa = _ss_ages_opt(optimize_ss_ages)
    if _ssa is not None:
        plan.solverOptions["withSSAges"] = _ssa

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
    tl, hl = build_hfp_dataframes(plan)
    try:
        with pd.ExcelWriter(str(hfp_path), engine="openpyxl") as writer:
            for iname, df in tl.items():
                df.to_excel(writer, sheet_name=iname, index=False)
            for sheet_name, df in hl.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
    except Exception as e:
        return json.dumps({"error": f"Failed to write HFP Excel: {e}"})

    saved = {
        "toml_file": str(toml_path),
        "hfp_file": str(hfp_path),
        "case_name": stem,
        "individuals": names,
    }
    if assumed:
        saved["assumed_defaults"] = assumed
    return json.dumps(saved, indent=2)


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


def _build_stochastic_json(plan, result, target_success_rate_pct, scenario_method):
    """Distil run_stochastic_spending result into a compact JSON-ready dict."""
    from owlplanner.stresstests import g_for_success_rate

    bases = result["bases"]
    lambdas = result["lambdas"]
    frontier_g = result["frontier_g"]
    frontier_prob = result["frontier_prob"]
    n_infeasible = result.get("n_infeasible", 0)

    xi0 = float(plan.xi_n[0])

    # Spending commitment at the requested success rate (frontier_g units = today's $)
    g_target, _ = g_for_success_rate(target_success_rate_pct, lambdas, frontier_g, frontier_prob)

    # Achieved success rate at that frontier point
    target_shortfall = 1.0 - target_success_rate_pct / 100.0
    candidates = np.where(frontier_prob <= target_shortfall)[0]
    achieved_success_pct = round(100.0 * (1.0 - float(frontier_prob[candidates[0] if len(candidates) else -1])), 2)

    # Downsample frontier to ~20 evenly spaced points for compact output
    step = max(1, len(frontier_g) // 20)
    frontier_pts = [
        {
            "success_rate_pct": round(100.0 * (1.0 - float(frontier_prob[i])), 2),
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
        "target_success_rate_pct": target_success_rate_pct,
        "achieved_success_rate_pct": achieved_success_pct,
        "spending_at_target": {
            "today_dollars": int(round(g_target)),
            "year1_nominal": int(round(g_target * xi0)),
        },
        "max_spending": {
            "today_dollars": int(round(float(frontier_g[0]))),
            "year1_nominal": int(round(float(frontier_g[0]) * xi0)),
            "success_rate_pct": round(100.0 * (1.0 - float(frontier_prob[0])), 2),
        },
        "frontier": frontier_pts,
    }


def _build_distribution_json(plan, results, objective, scenario_method, n_attempted):
    """Build a compact JSON-ready dict from a list of per-scenario result dicts."""
    xi0 = float(plan.xi_n[0])
    n_solved = len(results)

    if objective == "maxSpending":
        values = np.array([r["value"] for r in results])
        label_today = "spending_today_dollars"
        label_nominal = "spending_year1_nominal"
    else:
        values = np.array([r["value"] for r in results])
        label_today = "bequest_today_dollars"
        label_nominal = "bequest_final_nominal"

    def _pct(arr, q):
        return int(round(float(np.percentile(arr, q))))

    dist = {
        "min": int(round(float(np.min(values)))),
        "p10": _pct(values, 10),
        "p25": _pct(values, 25),
        "median": int(round(float(np.median(values)))),
        "mean": int(round(float(np.mean(values)))),
        "p75": _pct(values, 75),
        "p90": _pct(values, 90),
        "max": int(round(float(np.max(values)))),
    }

    out = {
        "status": "completed",
        "case_name": plan._name,
        "objective": objective,
        "scenario_method": scenario_method,
        "n_scenarios_attempted": int(n_attempted),
        "n_scenarios_solved": int(n_solved),
        "distribution": {label_today: dist},
    }

    # Historical (non-augmented): include per-year breakdown
    if scenario_method == "historical" and results and "year" in results[0]:
        by_year = []
        for r in results:
            v = r["value"]
            entry = {
                "year": r["year"],
                label_today: int(round(float(v))),
            }
            if objective == "maxSpending":
                entry[label_nominal] = int(round(float(v) * xi0))
            else:
                gamma_end = r.get("gamma_n_end", float(plan.gamma_n[-1]))
                entry[label_nominal] = int(round(float(v) * gamma_end))
            by_year.append(entry)
        out["by_start_year"] = by_year

    return out


def _historical_blocking(plan, objective, opts, ystart, yend, augmented, reverse, roll):
    """Solve plan across historical year sequences; returns (plan, n_attempted, results)."""
    from itertools import product as iproduct
    from owlplanner.rates import FROM, TO

    _ystart = int(ystart) if ystart is not None else FROM
    _yend = int(yend) if yend is not None else TO

    if _yend + plan.N_n > TO + 1:
        _yend = TO + 1 - plan.N_n

    if _yend < _ystart:
        raise ValueError(f"ystart={_ystart} too large: a {plan.N_n}-year horizon needs yend ≤ {TO + 1 - plan.N_n}.")

    if augmented:
        pairs = list(iproduct([False, True], range(plan.N_n)))
    else:
        pairs = [(bool(reverse), int(roll))]

    n_attempted = (_yend - _ystart + 1) * len(pairs)
    results = []

    for year in range(_ystart, _yend + 1):
        for rev, rll in pairs:
            plan.setRates("historical", year, reverse=rev, roll=rll)
            plan.solve(objective, opts)
            if plan.caseStatus == "solved":
                val = float(plan.basis) if objective == "maxSpending" else float(plan.bequest)
                entry = {"value": val, "gamma_n_end": float(plan.gamma_n[-1])}
                if not augmented:
                    entry["year"] = year
                results.append(entry)

    return plan, n_attempted, results, _ystart, _yend


def _monte_carlo_blocking(plan, objective, opts, n_scenarios, seed):
    """Solve plan across Monte Carlo rate draws; returns (plan, n_attempted, results)."""
    from owlplanner.stresstests import MC_TIME_LIMIT

    if getattr(plan, "rateModel", None) is None or getattr(plan.rateModel, "deterministic", True):
        raise ValueError(
            "Monte Carlo requires a stochastic rate method "
            "(e.g. 'historical_gaussian', 'lognormal', 'historical_bootstrap'). "
            "Current rate model is deterministic."
        )

    if seed is not None:
        plan.setReproducible(True, seed=int(seed))

    myopts = dict(opts)
    if "maxTime" not in myopts:
        myopts["maxTime"] = MC_TIME_LIMIT

    if plan.reproducibleRates and hasattr(plan.rateModel, "_rng"):
        plan.rateModel._rng = np.random.default_rng(plan.rateSeed)

    results = []
    for _ in range(int(n_scenarios)):
        plan.regenRates(override_reproducible=True)
        plan.solve(objective, myopts)
        if plan.caseStatus == "solved":
            val = float(plan.basis) if objective == "maxSpending" else float(plan.bequest)
            results.append({"value": val, "gamma_n_end": float(plan.gamma_n[-1])})

    return plan, int(n_scenarios), results


async def run_stochastic(
    scenario_method: str = "historical",
    target_success_rate_pct: float = 90.0,
    filename: str | None = None,
    overrides: list[str] | None = None,
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
    pension_indexed: list[bool] | None = None,
    pension_survivor_fractions: list[float] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    roth_conversions: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    spias: list[dict] | None = None,
    state: str | None = None,
    objective: str = "maxSpending",
    rate_method: str = "conservative",
    rate_values: list[float] | None = None,
    rate_frm: int | None = None,
    rate_to: int | None = None,
    survivor_fraction: float | None = None,
    initial_allocation: list[float] | None = None,
    final_allocation: list[float] | None = None,
    interpolation_method: str = "linear",
    interpolation_center: float | None = None,
    interpolation_width: float | None = None,
    balance_date: str | None = None,
    spending_profile: str | None = None,
    smile_dip: int = 15,
    smile_increase: int = 12,
    smile_delay: int = 0,
    net_spending: float | None = None,
    min_taxable_balance: list[float] | None = None,
    start_roth_year: int | None = None,
    no_roth_person: str | None = None,
    max_roth_conversion: float | None = None,
    use_roth_conv_overrides: bool | None = None,
    swap_roth_converters_first: str | None = None,
    swap_roth_converters_year: int | None = None,
    bequest: float | None = None,
    heirs_tax_rate: float | None = None,
    previous_magis: list[float] | None = None,
    with_medicare: str | None = None,
    with_aca: str | None = None,
    aca_start_year: int | None = None,
    optimize_ss_ages: bool | str | list[str] | None = None,
    constrain_mean: bool = False,
    slcsp: float | None = None,
    rate_params: dict | None = None,
    ss_trim_pct: int | None = None,
    ss_trim_year: int | None = None,
    obbba_expiration_year: int | None = None,
    dividend_rate: float | None = None,
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
        target_success_rate_pct: Desired percentage of scenarios with no shortfall, in (1, 100],
                              e.g. 90 for a 90% success rate. Like other percent-valued
                              parameters, this is on a 0-100 scale, not 0-1.
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
        pension_indexed:      CPI-indexed pension flags per person, e.g. [True, False].
        pension_survivor_fractions: Survivor benefit fractions per person (0–1), e.g. [0.5, 0.0].
        wages:                Wage streams: [{"person":0,"annual_amount":90000,"end_year":2030}].
        contributions:        Contributions: [{"person":0,"account":"tax_deferred","annual_amount":23000}].
                              Use list_contribution_limits to find IRS max amounts (incl. catch-up).
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
        state:                Two-letter US state code for state income tax.  Ask for it; when
                              omitted, TX (no state tax) is assumed and flagged in assumed_defaults.
        objective:            "maxSpending" (default) or "maxBequest".
        rate_method:          Rate model for the base deterministic solve and for MC scenarios.
        survivor_fraction:    Survivor spending as % of couple spending (default 60).
        initial_allocation:   Starting [equities, corporate_bonds, t_notes, cash] allocation %.
        final_allocation:     Ending allocation percentages (glide path).
        rate_values:          Fixed rates in % [equities, corporate_bonds, t_notes, inflation]
                              for rate_method="user".
        rate_frm:             First year of historical rate window.
        rate_to:              Last year of historical rate window.
        previous_magis:       Prior-year MAGI per person in $ for Medicare IRMAA (first 2 years).
        with_medicare:        Medicare IRMAA mode: "none", "loop", or "optimize".
        slcsp:                Annual ACA Silver benchmark premium in $/year for pre-65 individuals.
        interpolation_method: "linear" (default) or "s-curve".  See run_from_params for details.
        interpolation_center: S-curve inflection point in years from plan start (default 15).
        interpolation_width:  S-curve transition half-width in years (default 5).
        balance_date:         Date balances were recorded as "MM-DD" or "YYYY-MM-DD" (default: today).
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
        roth_conversions:     Per-cell Roth conversion pins/exclusions, only enforced when
                              use_roth_conv_overrides is true. See run_from_params for the
                              {"person","year","amount"} format and sign semantics.
        use_roth_conv_overrides: Enforce roth_conversions as hard per-cell constraints.
        swap_roth_converters_first: Name of individual converting first (couples only); pair
                              with swap_roth_converters_year. See run_from_params for details.
        swap_roth_converters_year: Calendar year conversion responsibility switches to the
                              other individual. Takes precedence over no_roth_person.
        bequest:              Target bequest in today's $ for maxSpending objective.
        optimize_ss_ages:     Controls SS claiming-age optimization (MIP, monthly precision, 62–70).
                              None/False → disabled; True/"all" → all persons; a single name
                              string → that person only; a list of names → those persons only.
                              Individuals who have already claimed are auto-detected and excluded.
        constrain_mean:       If True, generated rate series means are pinned to historical
                              averages, isolating sequence-of-returns risk.  Supported by
                              historical_gaussian, historical_lognormal, historical_copula,
                              garch_dcc, gmm, hmm.  Ignored for other methods.
        rate_params:          Extra rate model parameters as a dict, e.g.
                              {"bootstrap_type": "block", "block_size": 5}.  Only used with
                              flat params (not filename=); ignored for historical scenarios.
        ss_trim_pct:          SS trust fund haircut — percent reduction in SS benefits (0–100).
                              Example: ss_trim_pct=23, ss_trim_year=2033 (SSA trustees baseline).
        ss_trim_year:         Year when the SS benefit reduction begins (e.g. 2033).
        obbba_expiration_year: Year OBBBA (2025 Tax Reform) rates sunset to pre-TCJA levels
                              (default 2032).
        dividend_rate:        Annual dividend yield for taxable accounts in % (default 1.8).
        solver:               "HiGHS", "MOSEK", or None (auto-select).
        max_time:             Per-scenario solver time limit in seconds.
        seed:                 Random seed for reproducibility.
    """
    from owlplanner.stresstests import _validate_success_rate_pct

    try:
        _validate_success_rate_pct(target_success_rate_pct)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    assumed: list[dict] = []
    overrides = _norm_overrides(overrides)
    if filename is not None and names is not None:
        msg = "Provide either 'filename' or flat parameters (names, birth_years, ...) — not both."
        return json.dumps({"error": msg})
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
            plan = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=True),
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to build plan from {filename}: {e}"})
    else:
        if (
            names is None
            or birth_years is None
            or life_expectancy is None
            or taxable is None
            or tax_deferred is None
            or roth is None
        ):
            return json.dumps(
                {
                    "error": (
                        "Provide either 'filename' or flat parameters: "
                        "names, birth_years, life_expectancy, taxable, tax_deferred, roth are required."
                    )
                }
            )
        try:
            plan = _build_plan_from_params(
                names,
                birth_years,
                life_expectancy,
                state,
                taxable,
                tax_deferred,
                roth,
                hsa,
                cost_basis,
                ss_monthly_pias,
                ss_ages,
                pension_monthly_amounts,
                pension_ages,
                pension_indexed,
                pension_survivor_fractions,
                wages,
                contributions,
                big_ticket_items,
                roth_conversions,
                debts,
                fixed_assets,
                spias,
                objective,
                rate_method,
                rate_values,
                rate_frm,
                rate_to,
                survivor_fraction,
                initial_allocation,
                final_allocation,
                spending_profile,
                smile_dip,
                smile_increase,
                smile_delay,
                constrain_mean,
                interpolation_method,
                interpolation_center,
                interpolation_width,
                balance_date,
                heirs_tax_rate=heirs_tax_rate,
                slcsp=slcsp,
                aca_start_year=aca_start_year,
                rate_params=rate_params,
                ss_trim_pct=ss_trim_pct,
                ss_trim_year=ss_trim_year,
                obbba_expiration_year=obbba_expiration_year,
                dividend_rate=dividend_rate,
                assumed=assumed,
            )
        except Exception as e:
            return json.dumps({"error": f"Plan build error: {e}"})

    opts = _build_mcp_opts(
        solver=solver,
        max_time=max_time,
        net_spending=net_spending,
        min_taxable_balance=min_taxable_balance,
        start_roth_year=start_roth_year,
        no_roth_person=no_roth_person,
        max_roth_conversion=max_roth_conversion,
        bequest=bequest,
        optimize_ss_ages=optimize_ss_ages,
        previous_magis=previous_magis,
        with_medicare=with_medicare,
        with_aca=with_aca,
        use_roth_conv_overrides=use_roth_conv_overrides,
        swap_roth_converters_first=swap_roth_converters_first,
        swap_roth_converters_year=swap_roth_converters_year,
        inames=plan.inames,
    )

    try:
        plan, result = await asyncio.get_running_loop().run_in_executor(
            None,
            _stochastic_blocking,
            plan,
            scenario_method,
            ystart,
            yend,
            n_scenarios,
            opts,
            seed,
        )
    except Exception as e:
        return json.dumps({"error": f"Stochastic run error: {e}"})

    try:
        out = _build_stochastic_json(plan, result, target_success_rate_pct, scenario_method)
    except Exception as e:
        return json.dumps({"error": f"Result processing error: {e}"})

    if scenario_method == "historical" and n_scenarios != 200:
        out["note"] = (
            f"n_scenarios={n_scenarios} was ignored: 'historical' mode ran "
            f"{out['n_scenarios_run']} scenarios, one per historical start year "
            "(controlled by ystart/yend, default the full 1928-present range). "
            "Use scenario_method='mc' to control the scenario count via n_scenarios."
        )

    if assumed:
        out["assumed_defaults"] = assumed
    return json.dumps(out, indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: run_longevity_stochastic
# ─────────────────────────────────────────────────────────────────────────────


def _longevity_stochastic_blocking(
    names,
    birth_years,
    life_expectancy,
    state,
    taxable,
    tax_deferred,
    roth,
    hsa,
    cost_basis,
    ss_monthly_pias,
    ss_ages,
    pension_monthly_amounts,
    pension_ages,
    pension_indexed,
    pension_survivor_fractions,
    wages,
    contributions,
    big_ticket_items,
    roth_conversions,
    debts,
    fixed_assets,
    spias,
    objective,
    rate_method,
    rate_values,
    rate_frm,
    rate_to,
    survivor_fraction,
    initial_allocation,
    final_allocation,
    spending_profile,
    smile_dip,
    smile_increase,
    smile_delay,
    constrain_mean,
    interpolation_method,
    interpolation_center,
    interpolation_width,
    balance_date,
    sexes,
    mortality_table,
    scenario_method,
    ystart,
    yend,
    n_scenarios,
    opts,
    seed,
    heirs_tax_rate=None,
    slcsp=None,
    aca_start_year=None,
    rate_params=None,
    ss_trim_pct=None,
    ss_trim_year=None,
    obbba_expiration_year=None,
    dividend_rate=None,
    assumed=None,
):
    """Build plan, configure longevity sampling, solve, run stochastic frontier."""
    from owlplanner.stresstests import run_stochastic_spending
    from owlplanner.rates import FROM, TO

    plan = _build_plan_from_params(
        names,
        birth_years,
        life_expectancy,
        state,
        taxable,
        tax_deferred,
        roth,
        hsa,
        cost_basis,
        ss_monthly_pias,
        ss_ages,
        pension_monthly_amounts,
        pension_ages,
        pension_indexed,
        pension_survivor_fractions,
        wages,
        contributions,
        big_ticket_items,
        roth_conversions,
        debts,
        fixed_assets,
        spias,
        objective,
        rate_method,
        rate_values,
        rate_frm,
        rate_to,
        survivor_fraction,
        initial_allocation,
        final_allocation,
        spending_profile,
        smile_dip,
        smile_increase,
        smile_delay,
        constrain_mean,
        interpolation_method,
        interpolation_center,
        interpolation_width,
        balance_date,
        heirs_tax_rate=heirs_tax_rate,
        slcsp=slcsp,
        aca_start_year=aca_start_year,
        rate_params=rate_params,
        ss_trim_pct=ss_trim_pct,
        ss_trim_year=ss_trim_year,
        obbba_expiration_year=obbba_expiration_year,
        dividend_rate=dividend_rate,
        assumed=assumed,
    )

    plan.setSexes(list(sexes))
    if mortality_table:
        plan.setMortalityTable(mortality_table)

    plan.solve(plan.objective, opts)
    if plan.caseStatus != "solved":
        raise RuntimeError(f"Base deterministic plan did not solve (status: {plan.caseStatus}).")

    if seed is not None:
        plan.setReproducible(True, seed=seed)

    _ystart = ystart if ystart is not None else FROM
    _yend = yend if yend is not None else TO

    if scenario_method == "historical":
        result = run_stochastic_spending(
            plan,
            opts,
            "historical",
            ystart=_ystart,
            yend=_yend,
            with_longevity=True,
            sexes=list(sexes),
        )
    elif scenario_method == "mc":
        if getattr(plan, "rateModel", None) is None or getattr(plan.rateModel, "deterministic", True):
            raise ValueError(
                "Monte Carlo requires a stochastic rate method "
                "(e.g. 'historical_gaussian', 'lognormal', 'historical_bootstrap'). "
                "Current rate method is deterministic."
            )
        result = run_stochastic_spending(
            plan,
            opts,
            "mc",
            N=n_scenarios,
            with_longevity=True,
            sexes=list(sexes),
        )
    else:
        raise ValueError(f"Unknown scenario_method '{scenario_method}'. Use 'historical' or 'mc'.")

    return plan, result


async def run_longevity_stochastic(
    sexes: list[str],
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
    pension_indexed: list[bool] | None = None,
    pension_survivor_fractions: list[float] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    roth_conversions: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    spias: list[dict] | None = None,
    state: str | None = None,
    objective: str = "maxSpending",
    rate_method: str = "conservative",
    rate_values: list[float] | None = None,
    rate_frm: int | None = None,
    rate_to: int | None = None,
    survivor_fraction: float | None = None,
    initial_allocation: list[float] | None = None,
    final_allocation: list[float] | None = None,
    interpolation_method: str = "linear",
    interpolation_center: float | None = None,
    interpolation_width: float | None = None,
    balance_date: str | None = None,
    spending_profile: str | None = None,
    smile_dip: int = 15,
    smile_increase: int = 12,
    smile_delay: int = 0,
    net_spending: float | None = None,
    min_taxable_balance: list[float] | None = None,
    start_roth_year: int | None = None,
    no_roth_person: str | None = None,
    max_roth_conversion: float | None = None,
    use_roth_conv_overrides: bool | None = None,
    swap_roth_converters_first: str | None = None,
    swap_roth_converters_year: int | None = None,
    bequest: float | None = None,
    heirs_tax_rate: float | None = None,
    previous_magis: list[float] | None = None,
    with_medicare: str | None = None,
    with_aca: str | None = None,
    aca_start_year: int | None = None,
    optimize_ss_ages: bool | str | list[str] | None = None,
    constrain_mean: bool = False,
    slcsp: float | None = None,
    rate_params: dict | None = None,
    ss_trim_pct: int | None = None,
    ss_trim_year: int | None = None,
    obbba_expiration_year: int | None = None,
    dividend_rate: float | None = None,
    mortality_table: str = "SSA2025",
    scenario_method: str = "mc",
    target_success_rate_pct: float = 90.0,
    n_scenarios: int = 200,
    ystart: int | None = None,
    yend: int | None = None,
    solver: str | None = None,
    max_time: float | None = None,
    seed: int | None = None,
) -> str:
    """Run a spending frontier that jointly samples market sequences AND random lifespans.

    Each scenario draws a random lifespan for each individual from an actuarial mortality
    table before solving, so the frontier captures both sequence-of-returns risk and
    longevity risk simultaneously.  This is a more realistic (and more conservative)
    analysis than run_stochastic, which uses fixed life expectancy across all scenarios.

    BEFORE calling this tool, call list_mortality_tables to get the selection guide and
    ask the user about smoking status, occupation, and annuity ownership to choose the
    right table.  Default is "SSA2025" (general US population) when no category fits.

    All plan parameters are identical to run_from_params / run_stochastic.

    Args:
        sexes:            Biological sex of each individual for mortality table lookup:
                          "M" (male) or "F" (female), e.g. ["M", "F"] for a couple.
        mortality_table:  Actuarial table key (from list_mortality_tables) for lifespan
                          draws (default "SSA2025").
        scenario_method:  "mc" (default).  Longevity sampling requires Monte Carlo;
                          "historical" is rejected (lifespans can exceed data range).
        target_success_rate_pct: Desired percentage of scenarios with no shortfall, in (1, 100]
                          (default 90). Like other percent-valued parameters, this is on a
                          0-100 scale, not 0-1.
        names:            Person names, e.g. ["Alice", "Bob"].
        birth_years:      Birth years, e.g. [1963, 1961].
        life_expectancy:  Deterministic life expectancy used for the base solve (years per
                          person).  Longevity sampling overrides this per scenario, but the
                          base solve still uses this value.
        taxable:          Taxable account balances in $ per person.
        tax_deferred:     Tax-deferred (401k/IRA) balances in $ per person.
        roth:             Roth account balances in $ per person.
        hsa:              HSA balances in $ per person (optional).
        cost_basis:       Taxable cost basis in $ per person (optional).
        ss_monthly_pias:  Monthly SS PIA per person in $/month.
        ss_ages:          SS claiming ages per person.
        pension_monthly_amounts: Monthly pension amounts in $/month per person.
        pension_ages:     Pension commencement ages per person.
        pension_indexed:  CPI-indexed pension flags per person, e.g. [True, False].
        pension_survivor_fractions: Survivor benefit fractions per person (0–1).
        wages:            Wage streams (see run_from_params for format).
        contributions:    Retirement contributions (see run_from_params).
        big_ticket_items: Extra annual expenses (see run_from_params).
        debts:            Amortizing loans (see run_from_params).
        fixed_assets:     Assets to be sold (see run_from_params).
        spias:            Single Premium Immediate Annuities (see run_from_params).
        state:            Two-letter US state code.  When omitted, TX (no state tax) is
                          assumed and flagged in assumed_defaults.
        objective:        "maxSpending" (default) or "maxBequest".
        rate_method:      Rate model for scenarios.
        survivor_fraction: Survivor spending as % of couple spending (default 60).
        initial_allocation: Starting [equities, corporate_bonds, t_notes, cash] allocation %.
        final_allocation:   Ending allocation percentages (glide path).
        rate_values:        Fixed rates in % [equities, corporate_bonds, t_notes, inflation].
        rate_frm:           First year of historical rate window.
        rate_to:            Last year of historical rate window.
        previous_magis:     Prior-year MAGI per person in $ for Medicare IRMAA.
        with_medicare:      Medicare IRMAA mode: "none", "loop", or "optimize".
        slcsp:              Annual ACA Silver benchmark premium in $/year for pre-65 individuals.
        interpolation_method: "linear" (default) or "s-curve".
        interpolation_center: S-curve inflection point in years (default 15).
        interpolation_width:  S-curve half-width in years (default 5).
        balance_date:     Date balances were recorded as "MM-DD" or "YYYY-MM-DD" (default: today).
        spending_profile: "smile" (default) or "flat".
        smile_dip:        Slow-go dip depth in % (default 15).
        smile_increase:   No-go medical cost increase in % (default 12).
        smile_delay:      Go-go years before dip begins (default 0).
        net_spending:     Annual spending floor in $/year for maxBequest objective.
        min_taxable_balance: Minimum taxable account safety net in $ per person.
        start_roth_year:  Year before which Roth conversions are disabled.
        no_roth_person:   Name of individual excluded from Roth conversions.
        max_roth_conversion: Annual per-person Roth conversion cap in $/year.
        roth_conversions:     Per-cell Roth conversion pins/exclusions, only enforced when
                              use_roth_conv_overrides is true. See run_from_params for the
                              {"person","year","amount"} format and sign semantics.
        use_roth_conv_overrides: Enforce roth_conversions as hard per-cell constraints.
        swap_roth_converters_first: Name of individual converting first (couples only); pair
                              with swap_roth_converters_year. See run_from_params for details.
        swap_roth_converters_year: Calendar year conversion responsibility switches to the
                              other individual. Takes precedence over no_roth_person.
        bequest:          Target bequest in today's $ for maxSpending objective.
        optimize_ss_ages: Controls SS claiming-age optimization (MIP, monthly precision, 62–70).
                          None/False → disabled; True/"all" → all persons; a single name string
                          → that person only; a list of names → those persons only.
                          Individuals who have already claimed are auto-detected and excluded.
        constrain_mean:   If True, pin rate series means to historical averages.
        rate_params:      Extra rate model parameters, e.g. {"bootstrap_type":"block","block_size":5}.
                          Only used with flat params (not filename=).
        ss_trim_pct:      SS trust fund haircut — percent reduction in SS benefits (0–100).
                          Example: ss_trim_pct=23, ss_trim_year=2033 (SSA trustees baseline).
        ss_trim_year:     Year when the SS benefit reduction begins (e.g. 2033).
        obbba_expiration_year: Year OBBBA rates sunset to pre-TCJA levels (default 2032).
        dividend_rate:    Annual dividend yield for taxable accounts in % (default 1.8).
        n_scenarios:      Number of Monte Carlo scenarios (mc mode only, default 200).
        ystart:           First historical start year (historical mode).
        yend:             Last historical start year (historical mode).
        solver:           "HiGHS", "MOSEK", or None (auto-select).
        max_time:         Per-scenario solver time limit in seconds.
        seed:             Random seed for reproducibility.
    """
    from owlplanner.stresstests import _validate_success_rate_pct

    try:
        _validate_success_rate_pct(target_success_rate_pct)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    if scenario_method == "historical":
        return json.dumps(
            {
                "error": (
                    "Longevity risk is not supported with historical scenarios "
                    "(drawn lifespans can exceed the available historical data range). "
                    "Use scenario_method='mc' with a stochastic rate_method."
                ),
            }
        )

    opts = _build_mcp_opts(
        solver=solver,
        max_time=max_time,
        net_spending=net_spending,
        min_taxable_balance=min_taxable_balance,
        start_roth_year=start_roth_year,
        no_roth_person=no_roth_person,
        max_roth_conversion=max_roth_conversion,
        bequest=bequest,
        optimize_ss_ages=optimize_ss_ages,
        previous_magis=previous_magis,
        with_medicare=with_medicare,
        with_aca=with_aca,
        use_roth_conv_overrides=use_roth_conv_overrides,
        swap_roth_converters_first=swap_roth_converters_first,
        swap_roth_converters_year=swap_roth_converters_year,
        inames=names,
    )

    assumed: list[dict] = []
    try:
        plan, result = await asyncio.get_running_loop().run_in_executor(
            None,
            _longevity_stochastic_blocking,
            names,
            birth_years,
            life_expectancy,
            state,
            taxable,
            tax_deferred,
            roth,
            hsa,
            cost_basis,
            ss_monthly_pias,
            ss_ages,
            pension_monthly_amounts,
            pension_ages,
            pension_indexed,
            pension_survivor_fractions,
            wages,
            contributions,
            big_ticket_items,
            roth_conversions,
            debts,
            fixed_assets,
            spias,
            objective,
            rate_method,
            rate_values,
            rate_frm,
            rate_to,
            survivor_fraction,
            initial_allocation,
            final_allocation,
            spending_profile,
            smile_dip,
            smile_increase,
            smile_delay,
            constrain_mean,
            interpolation_method,
            interpolation_center,
            interpolation_width,
            balance_date,
            sexes,
            mortality_table,
            scenario_method,
            ystart,
            yend,
            n_scenarios,
            opts,
            seed,
            heirs_tax_rate,
            slcsp,
            aca_start_year,
            rate_params,
            ss_trim_pct,
            ss_trim_year,
            obbba_expiration_year,
            dividend_rate,
            assumed,
        )
    except Exception as e:
        return json.dumps({"error": f"Longevity stochastic run error: {e}"})

    try:
        out = _build_stochastic_json(plan, result, target_success_rate_pct, scenario_method)
    except Exception as e:
        return json.dumps({"error": f"Result processing error: {e}"})

    out["mortality_table"] = mortality_table
    out["sexes"] = list(sexes)
    if assumed:
        out["assumed_defaults"] = assumed
    return json.dumps(out, indent=2, cls=_NumpyEncoder)


async def run_historical(
    filename: str | None = None,
    overrides: list[str] | None = None,
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
    pension_indexed: list[bool] | None = None,
    pension_survivor_fractions: list[float] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    roth_conversions: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    spias: list[dict] | None = None,
    state: str | None = None,
    objective: str = "maxSpending",
    rate_method: str = "conservative",
    rate_values: list[float] | None = None,
    rate_frm: int | None = None,
    rate_to: int | None = None,
    survivor_fraction: float | None = None,
    initial_allocation: list[float] | None = None,
    final_allocation: list[float] | None = None,
    interpolation_method: str = "linear",
    interpolation_center: float | None = None,
    interpolation_width: float | None = None,
    balance_date: str | None = None,
    spending_profile: str | None = None,
    smile_dip: int = 15,
    smile_increase: int = 12,
    smile_delay: int = 0,
    net_spending: float | None = None,
    min_taxable_balance: list[float] | None = None,
    start_roth_year: int | None = None,
    no_roth_person: str | None = None,
    max_roth_conversion: float | None = None,
    use_roth_conv_overrides: bool | None = None,
    swap_roth_converters_first: str | None = None,
    swap_roth_converters_year: int | None = None,
    bequest: float | None = None,
    heirs_tax_rate: float | None = None,
    previous_magis: list[float] | None = None,
    with_medicare: str | None = None,
    with_aca: str | None = None,
    aca_start_year: int | None = None,
    slcsp: float | None = None,
    ss_trim_pct: int | None = None,
    ss_trim_year: int | None = None,
    obbba_expiration_year: int | None = None,
    dividend_rate: float | None = None,
    optimize_ss_ages: bool | str | list[str] | None = None,
    ystart: int | None = None,
    yend: int | None = None,
    augmented: bool = False,
    reverse: bool = False,
    roll: int = 0,
    solver: str | None = None,
    max_time: float | None = None,
) -> str:
    """Backtest a plan across historical rate sequences and return a distribution of outcomes.

    For each historical start year in [ystart, yend], the optimizer finds the best possible
    outcome (max spending or max bequest) using rates drawn from that year onward.  The result
    is a distribution showing how the plan would have fared under every historical market cycle
    in the data window (1928–present).

    Unlike run_stochastic, which pre-commits to a spending level and measures shortfall risk,
    run_historical lets the optimizer adapt fully to each scenario — the distribution shows the
    range of outcomes if you could have foreseen the sequence.

    Provide the plan either as a saved TOML file (filename=) or directly via flat parameters
    (same set accepted by run_from_params).

    Args:
        filename:         Path to a .toml case file (alternative to flat params).
        overrides:        KEY.PATH=VALUE overrides when using filename=.
        names:            Person names, e.g. ["Alice", "Bob"].
        birth_years:      Birth years, e.g. [1963, 1961].
        life_expectancy:  Life expectancy in years per person.
        taxable:          Taxable account balances in $ per person.
        tax_deferred:     Tax-deferred (401k/IRA) balances in $ per person.
        roth:             Roth account balances in $ per person.
        hsa:              HSA balances in $ per person (optional).
        cost_basis:       Taxable cost basis in $ per person (optional).
        ss_monthly_pias:  Monthly SS PIA per person in $/month.
        ss_ages:          SS claiming ages per person.
        pension_monthly_amounts: Monthly pension amounts in $/month per person.
        pension_ages:     Pension commencement ages per person.
        pension_indexed:  CPI-indexed pension flags per person.
        pension_survivor_fractions: Survivor benefit fractions per person (0–1).
        wages:            Wage streams (see run_from_params for format).
        contributions:    Retirement contributions (see run_from_params).
        big_ticket_items: Extra annual expenses (see run_from_params).
        debts:            Amortizing loans (see run_from_params).
        fixed_assets:     Assets to be sold (see run_from_params).
        spias:            Single Premium Immediate Annuities (see run_from_params).
        state:            Two-letter US state code.  When omitted, TX (no state tax) is
                          assumed and flagged in assumed_defaults.
        objective:        "maxSpending" (default) or "maxBequest".
        rate_method:      Rate model for the base/deterministic context (does not affect
                          the historical scenarios, which always use historical data).
        survivor_fraction: Survivor spending as % of couple spending (default 60).
        initial_allocation: Starting [equities, corporate_bonds, t_notes, cash] allocation %.
        final_allocation:   Ending allocation percentages (glide path).
        rate_values:      Fixed rates in % [equities, corporate_bonds, t_notes, inflation]
                          for rate_method="user".
        rate_frm:         First year of historical rate window for the base solve.
        rate_to:          Last year of historical rate window for the base solve.
        interpolation_method: "linear" (default) or "s-curve".
        interpolation_center: S-curve inflection point in years from plan start (default 15).
        interpolation_width:  S-curve transition half-width in years (default 5).
        balance_date:     Date balances were recorded as "MM-DD" or "YYYY-MM-DD" (default: today).
        spending_profile: "smile" (default) or "flat".
        smile_dip:        Slow-go dip depth in % (default 15).
        smile_increase:   No-go medical cost increase in % (default 12).
        smile_delay:      Go-go years before dip begins (default 0).
        net_spending:     Required when objective is "maxBequest": the annual spending
                          floor in $/year (e.g. 90000).  Ignored for maxSpending.
        min_taxable_balance: Minimum taxable account balance (safety net) in $ per person.
        start_roth_year:  Year before which Roth conversions are disabled.
        no_roth_person:   Name of individual excluded from Roth conversions.
        max_roth_conversion: Annual per-person Roth conversion cap in $/year.
        roth_conversions:     Per-cell Roth conversion pins/exclusions, only enforced when
                              use_roth_conv_overrides is true. See run_from_params for the
                              {"person","year","amount"} format and sign semantics.
        use_roth_conv_overrides: Enforce roth_conversions as hard per-cell constraints.
        swap_roth_converters_first: Name of individual converting first (couples only); pair
                              with swap_roth_converters_year. See run_from_params for details.
        swap_roth_converters_year: Calendar year conversion responsibility switches to the
                              other individual. Takes precedence over no_roth_person.
        bequest:          Target bequest in today's $ for maxSpending objective.
        heirs_tax_rate:   Override heirs' marginal tax rate (0–1) for estate planning.
        previous_magis:   Prior-year MAGI per person in $ for Medicare IRMAA (first 2 years).
        with_medicare:    Medicare IRMAA mode: "none", "loop", or "optimize".
        slcsp:            Annual ACA Silver benchmark premium in $/year for pre-65 individuals.
        with_aca:         ACA premium modeling: "none", "loop", or "optimize". Requires slcsp > 0.
        aca_start_year:   Calendar year ACA coverage begins.
        ss_trim_pct:      SS trust fund haircut — percent reduction in SS benefits (0–100).
                          Example: ss_trim_pct=23, ss_trim_year=2033 (SSA trustees baseline).
        ss_trim_year:     Year when the SS benefit reduction begins (e.g. 2033).
        obbba_expiration_year: Year OBBBA rates sunset to pre-TCJA levels (default 2032).
        dividend_rate:    Annual dividend yield for taxable accounts in % (default 1.8).
        ystart:           First historical start year to test (default: earliest available, 1928).
        yend:             Last historical start year to test (default: latest year that fits
                          the plan horizon in the data).
        augmented:        If True, run every combination of reverse/roll for each year,
                          expanding the sample to n_years × 2 × N_plan_years scenarios.
                          Produces a much larger (and slower) sample.
        reverse:          Reverse the rate sequence in time for this run (non-augmented only).
        roll:             Shift the rate sequence by this many years (non-augmented only).
        solver:           "HiGHS", "MOSEK", or None (auto-select).
        max_time:         Per-scenario solver time limit in seconds.
    """
    assumed: list[dict] = []
    overrides = _norm_overrides(overrides)
    if filename is not None and names is not None:
        msg = "Provide either 'filename' or flat parameters (names, birth_years, ...) — not both."
        return json.dumps({"error": msg})

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
            plan = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=True),
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to build plan from {filename}: {e}"})
    else:
        if (
            names is None
            or birth_years is None
            or life_expectancy is None
            or taxable is None
            or tax_deferred is None
            or roth is None
        ):
            return json.dumps(
                {
                    "error": (
                        "Provide either 'filename' or flat parameters: "
                        "names, birth_years, life_expectancy, taxable, tax_deferred, roth are required."
                    )
                }
            )
        try:
            plan = _build_plan_from_params(
                names,
                birth_years,
                life_expectancy,
                state,
                taxable,
                tax_deferred,
                roth,
                hsa,
                cost_basis,
                ss_monthly_pias,
                ss_ages,
                pension_monthly_amounts,
                pension_ages,
                pension_indexed,
                pension_survivor_fractions,
                wages,
                contributions,
                big_ticket_items,
                roth_conversions,
                debts,
                fixed_assets,
                spias,
                objective,
                rate_method,
                rate_values,
                rate_frm,
                rate_to,
                survivor_fraction,
                initial_allocation,
                final_allocation,
                spending_profile,
                smile_dip,
                smile_increase,
                smile_delay,
                False,  # constrain_mean (N/A for historical)
                interpolation_method,
                interpolation_center,
                interpolation_width,
                balance_date,
                heirs_tax_rate=heirs_tax_rate,
                slcsp=slcsp,
                aca_start_year=aca_start_year,
                ss_trim_pct=ss_trim_pct,
                ss_trim_year=ss_trim_year,
                obbba_expiration_year=obbba_expiration_year,
                dividend_rate=dividend_rate,
                assumed=assumed,
            )
        except Exception as e:
            return json.dumps({"error": f"Plan build error: {e}"})

    opts = _build_mcp_opts(
        solver=solver,
        max_time=max_time,
        net_spending=net_spending,
        min_taxable_balance=min_taxable_balance,
        start_roth_year=start_roth_year,
        no_roth_person=no_roth_person,
        max_roth_conversion=max_roth_conversion,
        bequest=bequest,
        optimize_ss_ages=optimize_ss_ages,
        previous_magis=previous_magis,
        with_medicare=with_medicare,
        with_aca=with_aca,
        use_roth_conv_overrides=use_roth_conv_overrides,
        swap_roth_converters_first=swap_roth_converters_first,
        swap_roth_converters_year=swap_roth_converters_year,
        inames=plan.inames,
    )

    try:
        plan, n_attempted, results, ystart_actual, yend_actual = await asyncio.get_running_loop().run_in_executor(
            None,
            _historical_blocking,
            plan,
            objective,
            opts,
            ystart,
            yend,
            augmented,
            reverse,
            roll,
        )
    except Exception as e:
        return json.dumps({"error": f"Historical run error: {e}"})

    if not results:
        return json.dumps({"error": "No scenarios solved successfully."})

    out = _build_distribution_json(plan, results, objective, "historical", n_attempted)
    out["ystart_used"] = ystart_actual
    out["yend_used"] = yend_actual
    out["augmented"] = augmented
    if assumed:
        out["assumed_defaults"] = assumed
    return json.dumps(out, indent=2, cls=_NumpyEncoder)


async def run_monte_carlo(
    filename: str | None = None,
    overrides: list[str] | None = None,
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
    pension_indexed: list[bool] | None = None,
    pension_survivor_fractions: list[float] | None = None,
    wages: list[dict] | None = None,
    contributions: list[dict] | None = None,
    big_ticket_items: list[dict] | None = None,
    roth_conversions: list[dict] | None = None,
    debts: list[dict] | None = None,
    fixed_assets: list[dict] | None = None,
    spias: list[dict] | None = None,
    state: str | None = None,
    objective: str = "maxSpending",
    rate_method: str = "gmm",
    rate_values: list[float] | None = None,
    rate_frm: int | None = None,
    rate_to: int | None = None,
    survivor_fraction: float | None = None,
    initial_allocation: list[float] | None = None,
    final_allocation: list[float] | None = None,
    interpolation_method: str = "linear",
    interpolation_center: float | None = None,
    interpolation_width: float | None = None,
    balance_date: str | None = None,
    spending_profile: str | None = None,
    smile_dip: int = 15,
    smile_increase: int = 12,
    smile_delay: int = 0,
    net_spending: float | None = None,
    min_taxable_balance: list[float] | None = None,
    start_roth_year: int | None = None,
    no_roth_person: str | None = None,
    max_roth_conversion: float | None = None,
    use_roth_conv_overrides: bool | None = None,
    swap_roth_converters_first: str | None = None,
    swap_roth_converters_year: int | None = None,
    bequest: float | None = None,
    heirs_tax_rate: float | None = None,
    previous_magis: list[float] | None = None,
    with_medicare: str | None = None,
    with_aca: str | None = None,
    aca_start_year: int | None = None,
    slcsp: float | None = None,
    constrain_mean: bool = False,
    optimize_ss_ages: bool | str | list[str] | None = None,
    rate_params: dict | None = None,
    ss_trim_pct: int | None = None,
    ss_trim_year: int | None = None,
    obbba_expiration_year: int | None = None,
    dividend_rate: float | None = None,
    n_scenarios: int = 200,
    solver: str | None = None,
    max_time: float | None = None,
    seed: int | None = None,
) -> str:
    """Run Monte Carlo simulations and return a distribution of optimal outcomes.

    Generates stochastic rate sequences and solves the plan independently for each one.
    Each scenario finds the best possible outcome (max spending or max bequest) given its
    randomly drawn rate path.  The result is a distribution showing the range of outcomes
    across simulated market environments.

    A stochastic rate_method is required (e.g. 'historical_gaussian', 'lognormal',
    'historical_bootstrap').  Use list_rate_models("stochastic") to see all options.

    The bootstrap family ('historical_bootstrap') supports extra parameters via rate_params:
      - bootstrap_type: "iid" (default), "block", "circular", or "stationary"
      - block_size:     block length for block-based types (default 1)
      - crisis_years:   list of years to oversample, e.g. [1973, 2000, 2008]
      - crisis_weight:  sampling multiplier for crisis years (default 1.0)

    Provide the plan either as a saved TOML file (filename=) or directly via flat parameters
    (same set accepted by run_from_params).

    Args:
        filename:         Path to a .toml case file (alternative to flat params).
        overrides:        KEY.PATH=VALUE overrides when using filename=.
        names:            Person names, e.g. ["Alice", "Bob"].
        birth_years:      Birth years, e.g. [1963, 1961].
        life_expectancy:  Life expectancy in years per person.
        taxable:          Taxable account balances in $ per person.
        tax_deferred:     Tax-deferred (401k/IRA) balances in $ per person.
        roth:             Roth account balances in $ per person.
        hsa:              HSA balances in $ per person (optional).
        cost_basis:       Taxable cost basis in $ per person (optional).
        ss_monthly_pias:  Monthly SS PIA per person in $/month.
        ss_ages:          SS claiming ages per person.
        pension_monthly_amounts: Monthly pension amounts in $/month per person.
        pension_ages:     Pension commencement ages per person.
        pension_indexed:  CPI-indexed pension flags per person.
        pension_survivor_fractions: Survivor benefit fractions per person (0–1).
        wages:            Wage streams (see run_from_params for format).
        contributions:    Retirement contributions (see run_from_params).
        big_ticket_items: Extra annual expenses (see run_from_params).
        debts:            Amortizing loans (see run_from_params).
        fixed_assets:     Assets to be sold (see run_from_params).
        spias:            Single Premium Immediate Annuities (see run_from_params).
        state:            Two-letter US state code.  When omitted, TX (no state tax) is
                          assumed and flagged in assumed_defaults.
        objective:        "maxSpending" (default) or "maxBequest".
        rate_method:      Stochastic rate model (REQUIRED to be stochastic).  Default "gmm"
                          (Gaussian mixture — defaults to full 1928-present calibration window).
                          All methods that draw from historical data (gmm, hmm, garch_dcc,
                          historical_gaussian, historical_lognormal, historical_bootstrap)
                          use the full historical range when rate_frm/rate_to are omitted;
                          provide them to calibrate from a specific sub-period.
                          historical_* methods require rate_frm and rate_to.
                          See list_rate_models("stochastic") for all options.
        rate_values:      Fixed rates in % for rate_method="user" (rarely used for MC).
        rate_frm:         First year of the historical calibration or data window (e.g. 1970).
                          Required for historical_* methods; optional (but recommended) for
                          gmm, hmm, garch_dcc, and vector_ar — defaults to full history.
        rate_to:          Last year of the calibration window (e.g. 2020).  Same rules as rate_frm.
        survivor_fraction: Survivor spending as % of couple spending (default 60).
        initial_allocation: Starting [equities, corporate_bonds, t_notes, cash] allocation %.
        final_allocation:   Ending allocation percentages (glide path).
        interpolation_method: "linear" (default) or "s-curve".
        interpolation_center: S-curve inflection point in years from plan start (default 15).
        interpolation_width:  S-curve transition half-width in years (default 5).
        balance_date:     Date balances were recorded as "MM-DD" or "YYYY-MM-DD" (default: today).
        spending_profile: "smile" (default) or "flat".
        smile_dip:        Slow-go dip depth in % (default 15).
        smile_increase:   No-go medical cost increase in % (default 12).
        smile_delay:      Go-go years before dip begins (default 0).
        net_spending:     Required when objective is "maxBequest": the annual spending
                          floor in $/year (e.g. 90000).  Ignored for maxSpending.
        min_taxable_balance: Minimum taxable account balance (safety net) in $ per person.
        start_roth_year:  Year before which Roth conversions are disabled.
        no_roth_person:   Name of individual excluded from Roth conversions.
        max_roth_conversion: Annual per-person Roth conversion cap in $/year.
        roth_conversions:     Per-cell Roth conversion pins/exclusions, only enforced when
                              use_roth_conv_overrides is true. See run_from_params for the
                              {"person","year","amount"} format and sign semantics.
        use_roth_conv_overrides: Enforce roth_conversions as hard per-cell constraints.
        swap_roth_converters_first: Name of individual converting first (couples only); pair
                              with swap_roth_converters_year. See run_from_params for details.
        swap_roth_converters_year: Calendar year conversion responsibility switches to the
                              other individual. Takes precedence over no_roth_person.
        bequest:          Target bequest in today's $ for maxSpending objective.
        heirs_tax_rate:   Override heirs' marginal tax rate (0–1) for estate planning.
        previous_magis:   Prior-year MAGI per person in $ for Medicare IRMAA (first 2 years).
        with_medicare:    Medicare IRMAA mode: "none", "loop", or "optimize".
        slcsp:            Annual ACA Silver benchmark premium in $/year for pre-65 individuals.
        with_aca:         ACA premium modeling: "none", "loop", or "optimize". Requires slcsp > 0.
        aca_start_year:   Calendar year ACA coverage begins.
        constrain_mean:   If True, pin each scenario's mean returns to historical averages,
                          isolating sequence-of-returns risk.
        rate_params:      Extra rate model parameters as a dict.  Bootstrap example:
                          {"bootstrap_type": "block", "block_size": 5,
                           "crisis_years": [1973, 2000, 2008], "crisis_weight": 2.0}.
                          Gaussian/lognormal: none needed.  Only used with flat params.
        ss_trim_pct:      SS trust fund haircut — percent reduction in SS benefits (0–100).
                          Example: ss_trim_pct=23, ss_trim_year=2033 (SSA trustees baseline).
        ss_trim_year:     Year when the SS benefit reduction begins (e.g. 2033).
        obbba_expiration_year: Year OBBBA rates sunset to pre-TCJA levels (default 2032).
        dividend_rate:    Annual dividend yield for taxable accounts in % (default 1.8).
        n_scenarios:      Number of Monte Carlo trials (default 200).
        solver:           "HiGHS", "MOSEK", or None (auto-select).
        max_time:         Per-scenario solver time limit in seconds.
        seed:             Random seed for reproducible results.
    """
    assumed: list[dict] = []
    overrides = _norm_overrides(overrides)

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
            plan = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=True),
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to build plan from {filename}: {e}"})
        # MC needs a stochastic model. Apply rate_method (default "gmm") when the
        # TOML's rate model is deterministic so the tool always works out of the box.
        try:
            if getattr(getattr(plan, "rateModel", None), "deterministic", True):
                plan.setRates(
                    rate_method, frm=rate_frm, to=rate_to, constrain_mean=constrain_mean, **(rate_params or {})
                )
        except Exception as e:
            return json.dumps({"error": f"Failed to set rate model '{rate_method}': {e}"})
    else:
        if names is None or birth_years is None or life_expectancy is None:
            return json.dumps(
                {
                    "error": (
                        "Provide either 'filename' or flat parameters: "
                        "names, birth_years, life_expectancy, taxable, tax_deferred, roth are required."
                    )
                }
            )
        try:
            plan = _build_plan_from_params(
                names,
                birth_years,
                life_expectancy,
                state,
                taxable,
                tax_deferred,
                roth,
                hsa,
                cost_basis,
                ss_monthly_pias,
                ss_ages,
                pension_monthly_amounts,
                pension_ages,
                pension_indexed,
                pension_survivor_fractions,
                wages,
                contributions,
                big_ticket_items,
                roth_conversions,
                debts,
                fixed_assets,
                spias,
                objective,
                rate_method,
                rate_values,
                rate_frm,
                rate_to,
                survivor_fraction,
                initial_allocation,
                final_allocation,
                spending_profile,
                smile_dip,
                smile_increase,
                smile_delay,
                constrain_mean,
                interpolation_method,
                interpolation_center,
                interpolation_width,
                balance_date,
                heirs_tax_rate=heirs_tax_rate,
                slcsp=slcsp,
                aca_start_year=aca_start_year,
                rate_params=rate_params,
                ss_trim_pct=ss_trim_pct,
                ss_trim_year=ss_trim_year,
                obbba_expiration_year=obbba_expiration_year,
                dividend_rate=dividend_rate,
                assumed=assumed,
            )
        except Exception as e:
            return json.dumps({"error": f"Plan build error: {e}"})

    opts = _build_mcp_opts(
        solver=solver,
        max_time=max_time,
        net_spending=net_spending,
        min_taxable_balance=min_taxable_balance,
        start_roth_year=start_roth_year,
        no_roth_person=no_roth_person,
        max_roth_conversion=max_roth_conversion,
        bequest=bequest,
        optimize_ss_ages=optimize_ss_ages,
        previous_magis=previous_magis,
        with_medicare=with_medicare,
        with_aca=with_aca,
        use_roth_conv_overrides=use_roth_conv_overrides,
        swap_roth_converters_first=swap_roth_converters_first,
        swap_roth_converters_year=swap_roth_converters_year,
        inames=plan.inames,
    )

    try:
        plan, n_attempted, results = await asyncio.get_running_loop().run_in_executor(
            None,
            _monte_carlo_blocking,
            plan,
            objective,
            opts,
            n_scenarios,
            seed,
        )
    except Exception as e:
        return json.dumps({"error": f"Monte Carlo run error: {e}"})

    if not results:
        return json.dumps({"error": "No scenarios solved successfully."})

    out = _build_distribution_json(plan, results, objective, "mc", n_attempted)
    out["rate_method"] = plan.rateMethod if hasattr(plan, "rateMethod") else rate_method
    if assumed:
        out["assumed_defaults"] = assumed
    return json.dumps(out, indent=2, cls=_NumpyEncoder)


# ─────────────────────────────────────────────────────────────────────────────
# Registry of tool functions, in the order they are exposed by the MCP server.
# ─────────────────────────────────────────────────────────────────────────────

MCP_TOOLS = (
    list_cases,
    explain_case,
    list_rate_models,
    list_mortality_tables,
    convert_ss_benefit,
    list_contribution_limits,
    run_case,
    compare_cases,
    run_from_params,
    save_case,
    run_stochastic,
    run_longevity_stochastic,
    run_historical,
    run_monte_carlo,
)
