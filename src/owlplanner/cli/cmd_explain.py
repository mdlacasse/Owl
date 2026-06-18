"""
CLI command for describing a case configuration without solving it.

Loads and validates the TOML case file, applies any --set overrides, and
prints a structured JSON document describing the scenario — individuals,
time horizon, account balances, income streams, and solver options.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import json
import sys
import datetime

import click
from pathlib import Path

from owlplanner.config import load_toml, config_to_plan

from .cmd_run import validate_toml
from .formatters import _NumpyEncoder
from .set_override import apply_overrides


def _plan_to_explain(plan, filename, set_overrides) -> dict:
    current_year = datetime.date.today().year
    N_i = plan.N_i

    individuals = []
    for i in range(N_i):
        birth_year = int(plan.yobs[i])
        individuals.append({
            "name": plan.inames[i],
            "birth_year": birth_year,
            "current_age": current_year - birth_year,
            "life_expectancy": int(plan.expectancy[i]),
            "plan_end_year": int(plan.year_n[0]) + int(plan.horizons[i]) - 1,
        })

    # beta_ij shape: (N_i, N_j), values in dollars; j=0 taxable, 1 tax-deferred, 2 roth, 3 hsa
    account_labels = ["taxable", "tax_deferred", "roth", "hsa"]
    account_balances = {}
    if plan.beta_ij is not None:
        for i in range(N_i):
            name = plan.inames[i]
            account_balances[name] = {lbl: int(plan.beta_ij[i, j]) for j, lbl in enumerate(account_labels)}
        account_balances["total"] = {
            lbl: int(sum(plan.beta_ij[i, j] for i in range(N_i)))
            for j, lbl in enumerate(account_labels)
        }

    social_security = [
        {
            "name": plan.inames[i],
            "claiming_age": round(float(plan.ssecAges[i]), 4),
            "monthly_pia": int(plan.ssecAmounts[i]),
        }
        for i in range(N_i)
    ]

    pensions = [
        {
            "name": plan.inames[i],
            "start_age": int(plan.pensionAges[i]),
            "monthly_amount": int(plan.pensionAmounts[i]),
        }
        for i in range(N_i)
        if plan.pensionAmounts[i] > 0
    ]

    # Fixed assets and debts come from the HFP workbook (houseLists).  These are
    # only populated when the HFP file was loaded; otherwise the lists are empty.
    house_lists = getattr(plan, "houseLists", None) or {}

    def _active(row):
        val = row.get("active", True)
        return True if val is None or (isinstance(val, float) and val != val) else bool(val)

    fixed_assets = []
    fa_df = house_lists.get("Fixed Assets")
    if fa_df is not None and not fa_df.empty:
        for _, row in fa_df.iterrows():
            if not _active(row):
                continue
            fixed_assets.append({
                "name": str(row["name"]),
                "type": str(row["type"]),
                "value": int(round(float(row["value"]))),
                "basis": int(round(float(row["basis"]))),
                "annual_growth_pct": round(float(row["rate"]), 4),
                "sell_year": int(row["yod"]),
                "commission_pct": round(float(row["commission"]), 4),
            })

    debts = []
    debt_df = house_lists.get("Debts")
    if debt_df is not None and not debt_df.empty:
        for _, row in debt_df.iterrows():
            if not _active(row):
                continue
            debts.append({
                "name": str(row["name"]),
                "type": str(row["type"]),
                "balance": int(round(float(row["amount"]))),
                "rate_pct": round(float(row["rate"]), 4),
                "years_remaining": int(row["term"]),
            })

    # Opening balance sheet (reference-year dollars): savings + fixed assets - debts.
    savings_total = int(sum(account_balances["total"].values())) if account_balances else 0
    fixed_assets_total = int(sum(a["value"] for a in fixed_assets))
    debt_total = int(sum(d["balance"] for d in debts))
    deferred_tax = int(round(
        (account_balances["total"].get("tax_deferred", 0) + account_balances["total"].get("hsa", 0))
        * plan.liquidationTaxRate
    )) if account_balances else 0
    opening_balance_sheet = {
        "savings_total": savings_total,
        "fixed_assets_total": fixed_assets_total,
        "total_assets": savings_total + fixed_assets_total,
        "debt_total": debt_total,
        "net_worth": savings_total + fixed_assets_total - debt_total,
        "deferred_income_tax": deferred_tax,
        "liquid_net_worth": savings_total + fixed_assets_total - debt_total - deferred_tax,
    }

    return {
        "filename": str(filename),
        "case_name": plan._name,
        "filing_status": plan.filingStatus,
        "state": plan.state or None,
        "individuals": individuals,
        "time_horizon": {
            "start_year": int(plan.year_n[0]),
            "end_year": int(plan.year_n[-1]),
            "years": int(plan.N_n),
        },
        "objective": plan.objective,
        "rate_method": plan.rateMethod,
        "hfp_file": plan.hfpFileName if plan.hfpFileName != "None" else None,
        "account_balances": account_balances,
        "fixed_assets": fixed_assets,
        "debts": debts,
        "opening_balance_sheet": opening_balance_sheet,
        "liquidation_tax_rate": round(float(plan.liquidationTaxRate), 4),
        "liquidation_capgains_rate": round(float(plan.liquidationCapGainsRate), 4),
        "social_security": social_security,
        "pensions": pensions,
        "solver_options": plan.solverOptions,
        "overrides_applied": list(set_overrides),
    }


@click.command(
    name="explain",
    epilog="Does not solve — use 'owlcli run' to optimize the case.",
)
@click.argument(
    "filename",
    type=click.Path(exists=False, dir_okay=False, path_type=Path),
    callback=validate_toml,
)
@click.option(
    "--set",
    "set_overrides",
    multiple=True,
    metavar="KEY.PATH=VALUE",
    help=(
        "Override any TOML parameter before describing. "
        "Same syntax as 'owlcli run --set'."
    ),
)
def cmd_explain(filename, set_overrides):
    """Describe a case configuration without solving it.

    Loads the TOML case file, applies any --set overrides, and prints a JSON
    document describing the scenario: individuals, time horizon, account
    balances, income streams, and solver options.

    \b
    Examples:
      owlcli explain case.toml
      owlcli explain case.toml --set basic_info.state=CA
    """
    diconf, dirname, _ = load_toml(str(filename))
    if set_overrides:
        diconf = apply_overrides(diconf, set_overrides)

    # Load the HFP workbook so fixed assets and debts are described too; fall
    # back to skipping it if the referenced file is missing.
    try:
        plan = config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=True)
    except FileNotFoundError:
        plan = config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=False)

    result = _plan_to_explain(plan, filename, set_overrides)
    sys.stdout.write(json.dumps(result, indent=2, cls=_NumpyEncoder))
    sys.stdout.write("\n")
