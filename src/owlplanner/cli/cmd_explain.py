"""
CLI command for describing a case configuration without solving it.

Loads and validates the TOML case file, applies any --set overrides, and
prints a structured JSON document describing the scenario — individuals,
time horizon, account balances, income streams, and solver options.

Copyright (C) 2025-2026 The Owl Authors
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

    plan = config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=False)

    result = _plan_to_explain(plan, filename, set_overrides)
    sys.stdout.write(json.dumps(result, indent=2, cls=_NumpyEncoder))
    sys.stdout.write("\n")
