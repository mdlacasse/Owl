"""
CLI command for tracing the spending/bequest efficient frontier.

Sweeps the bequest floor under the maxSpending objective and reports how much net
spending each level of estate costs. In the stochastic modes each level is solved
across the whole scenario ensemble, so the curve carries a confidence fan.

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

import json
import sys

import click
from pathlib import Path

from owlplanner.config import load_toml, config_to_plan
from owlplanner.config.schema import CLI_SOLVER_OVERRIDE_MAP, parse_solver_options
from owlplanner.stresstests import run_spending_bequest_frontier, summarize_spending_bequest_frontier

from .cmd_run import _parse_solver_opts, validate_toml
from .set_override import apply_overrides


def _parse_float_list(value, what):
    """Parse a comma-separated list of numbers, as accepted by --bequest-grid."""
    try:
        out = [float(v) for v in str(value).split(",") if v.strip() != ""]
    except ValueError as e:
        raise click.BadParameter(f"{what} must be a comma-separated list of numbers. Got: {value!r}") from e
    if not out:
        raise click.BadParameter(f"{what} cannot be empty.")
    return out


@click.command(
    name="frontier",
    epilog="Bequest levels are in the case's solver units (k by default). "
    "Use --output-format json to pipe the full curve elsewhere.",
)
@click.argument(
    "filename",
    type=click.Path(exists=False, dir_okay=False, path_type=Path),
    callback=validate_toml,
)
@click.option(
    "--bequest-grid",
    "bequest_grid",
    default="0,500,1000,2000,4000",
    show_default=True,
    help="Comma-separated bequest floors to trace, in the case's solver units.",
)
@click.option(
    "--scenario-method",
    type=click.Choice(["deterministic", "historical", "mc"], case_sensitive=False),
    default="deterministic",
    show_default=True,
    help="Scenarios per level. 'deterministic' uses the case's own rates and is fastest.",
)
@click.option("--ystart", type=int, default=None, help="First historical start year.")
@click.option("--yend", type=int, default=None, help="Last historical start year.")
@click.option("--num-scenarios", "num_scenarios", type=int, default=None, help="Monte Carlo draws per level.")
@click.option(
    "--success-rates",
    "success_rates",
    default="50,75,90",
    show_default=True,
    help="Comma-separated success percentages to trace. Ignored when deterministic.",
)
@click.option(
    "--target-success-rate",
    "target_success_rate",
    type=float,
    default=90.0,
    show_default=True,
    help="Which traced rate the summary reports against.",
)
@click.option(
    "--solver",
    type=click.Choice(["default", "HiGHS", "MOSEK"], case_sensitive=True),
    default=None,
    help="Solver to use. 'default' picks MOSEK if licensed, else HiGHS.",
)
@click.option("--max-time", type=float, default=None, help="Solver time limit in seconds.")
@click.option("--verbose/--no-verbose", "verbose", default=None, help="Enable solver verbosity.")
@click.option(
    "--solver-opt",
    "solver_opts",
    multiple=True,
    help="Override solver option as KEY=VALUE. Repeat for multiple.",
)
@click.option(
    "--set",
    "set_overrides",
    multiple=True,
    metavar="KEY.PATH=VALUE",
    help="Override any TOML parameter before solving. Repeat for multiple.",
)
@click.option("--seed", type=int, default=None, help="Random seed for the Monte Carlo draws.")
@click.option(
    "--with-duals",
    "with_duals",
    is_flag=True,
    default=False,
    help="Also compute the bequest shadow price, at one extra LP re-solve per level. "
    "Only surfaces under --output-format json; the text table reports the measured rate.",
)
@click.option(
    "--output-format",
    "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--loguru",
    "use_loguru",
    is_flag=True,
    default=False,
    help="Route plan logs through loguru instead of the default stream handler.",
)
def cmd_frontier(
    filename: Path,
    bequest_grid,
    scenario_method,
    ystart,
    yend,
    num_scenarios,
    success_rates,
    target_success_rate,
    solver,
    max_time,
    verbose,
    solver_opts,
    set_overrides,
    seed,
    with_duals,
    output_format,
    use_loguru,
):
    """Trace the trade-off between net spending and bequest for an OWL case file.

    Sweeps the bequest floor under maxSpending, reporting the net spending each
    level of estate permits. Every point is an ordinary solve, so the curve shows
    a real trade-off rather than one arbitrary operating point.

    With --scenario-method historical or mc, each level is additionally solved
    across the whole scenario ensemble and spending is reported at each of
    --success-rates. The spread between those curves is sequence-of-returns risk.
    """
    grid = _parse_float_list(bequest_grid, "--bequest-grid")
    rates_pct = _parse_float_list(success_rates, "--success-rates")

    diconf, dirname, _ = load_toml(str(filename))
    if set_overrides:
        diconf = apply_overrides(diconf, set_overrides)
    logstreams = "loguru" if use_loguru else [sys.stderr]
    plan = config_to_plan(diconf, dirname, verbose=True, logstreams=logstreams, loadHFP=True)

    opts = dict(plan.solverOptions)
    if solver is not None:
        opts["solver"] = solver
    if max_time is not None:
        opts["maxTime"] = max_time
    if verbose is not None:
        opts["verbose"] = verbose
    for key, val in _parse_solver_opts(solver_opts):
        opts[CLI_SOLVER_OVERRIDE_MAP.get(key, key)] = val

    try:
        opts = parse_solver_options(opts)
        result = run_spending_bequest_frontier(
            plan,
            opts,
            grid,
            scenario_method=scenario_method.lower(),
            ystart=ystart,
            yend=yend,
            N=num_scenarios,
            success_rates=rates_pct,
            seed=seed,
            with_duals=with_duals,
        )
        summary = summarize_spending_bequest_frontier(
            result, target_success_rate_pct=target_success_rate
        )
    except ValueError as e:
        raise click.BadParameter(str(e)) from e

    if output_format.lower() == "json":
        sys.stdout.write(json.dumps(summary, indent=2))
        sys.stdout.write("\n")
        return

    deterministic = summary["scenario_method"] == "deterministic"
    fixed = float(summary.get("fixed_assets_today_dollars", 0.0) or 0.0)
    click.echo(f"\nSpending vs bequest trade-off — {plan._name}")
    click.echo(f"  scenarios: {summary['scenario_method']} ({summary['n_scenarios']})")
    if not deterministic:
        click.echo(f"  reporting at {summary['target_success_rate_pct']:g}% success")

    head = f"\n{'savings':>14}"
    if fixed > 0:
        head += f"{'fixed assets':>14}{'total estate':>14}"
    if deterministic:
        head += f"{'spending':>14}{'$/yr per $':>14}"
    else:
        head += "".join(f"{r:>13g}%" for r in summary["success_rates"])
    click.echo(head)

    for k, row in enumerate(summary["frontier"]):
        if not row["feasible"]:
            click.echo(f"{row['bequest_today_dollars']:>14,.0f}{'unreachable':>14}")
            continue
        line = f"{row['bequest_today_dollars']:>14,.0f}"
        if fixed > 0:
            line += f"{fixed:>14,.0f}{row['total_estate_today_dollars']:>14,.0f}"
        if deterministic:
            line += f"{row['spending_today_dollars']:>14,.0f}"
            rate = summary["exchange_rate"][k - 1]["spending_per_dollar_of_bequest"] if k else None
            line += f"{rate:>14.4f}" if rate is not None else f"{'':>14}"
        else:
            for r in summary["success_rates"]:
                v = row.get(f"spending_at_{r:g}pct")
                line += f"{v:>14,.0f}" if v is not None else f"{'n/a':>14}"
        click.echo(line)

    if fixed > 0:
        click.echo(
            f"\n  Fixed assets add ${fixed:,.0f} to every level: assets still held at the end "
            "of the plan, passing outside the savings accounts."
        )

    lo = summary["max_feasible_bequest_today_dollars"]
    hi = summary["first_unreachable_bequest_today_dollars"]
    what = "savings" if fixed > 0 else "this plan"  # be explicit when assets sit outside
    if hi is None and lo is not None:
        click.echo(f"\n  Every level traced is reachable; the most {what} can leave is above ${lo:,.0f}.")
    elif lo is None and hi is not None:
        click.echo(f"\n  No level traced is reachable: even ${hi:,.0f} of {what} is out of reach.")
    elif lo is not None:
        click.echo(f"\n  The most {what} can leave is between ${lo:,.0f} and ${hi:,.0f}.")
