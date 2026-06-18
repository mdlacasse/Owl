"""
CLI command for comparing two scenarios of the same case.

Runs the base case and a variant (defined by --set overrides), then diffs
their key metrics and prints structured JSON to stdout.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import json
import sys

import click
from pathlib import Path

from owlplanner.config import load_toml, config_to_plan
from owlplanner.config.schema import CLI_SOLVER_OVERRIDE_MAP, parse_solver_options
from owlplanner.export import plan_metrics

from .cmd_run import validate_toml, _parse_solver_opts
from .formatters import _NumpyEncoder, _diff, _pct, KEY_METRICS
from .params_help import print_solver_options_help
from .set_override import apply_overrides


def _solve_case(diconf, dirname, solver, max_time, gap, verbose, solver_opts, seed, label):
    """Load, configure, and solve one scenario. Returns (plan, metrics_dict)."""
    plan = config_to_plan(diconf, dirname, verbose=True, logstreams=[sys.stderr], loadHFP=True)
    if seed is not None:
        plan.setReproducible(True, seed=seed)

    opts = dict(plan.solverOptions)
    if solver is not None:
        opts["solver"] = solver
    if max_time is not None:
        opts["maxTime"] = max_time
    if gap is not None:
        opts["gap"] = gap
    if verbose is not None:
        opts["verbose"] = verbose
    for key, val in _parse_solver_opts(solver_opts):
        canonical_key = CLI_SOLVER_OVERRIDE_MAP.get(key, key)
        opts[canonical_key] = val
    try:
        opts = parse_solver_options(opts)
    except Exception as e:
        raise click.BadParameter(str(e)) from e

    click.echo(f"Solving {label}…", err=True)
    plan.solve(plan.objective, opts)
    return plan


@click.command(
    name="compare",
    epilog="Use --set to define the variant. All solver flags apply to both runs. "
    "Use --help-solver-options to list solver options.",
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
    required=True,
    metavar="KEY.PATH=VALUE",
    help=(
        "Parameter override defining the variant. Repeat for multiple. "
        "Same syntax as 'owlcli run --set'. At least one is required."
    ),
)
@click.option(
    "--solver",
    type=click.Choice(["default", "HiGHS", "MOSEK"], case_sensitive=True),
    default=None,
    help="Solver to use for both runs.",
)
@click.option("--max-time", type=float, default=None, help="Solver time limit in seconds.")
@click.option("--gap", type=float, default=None, help="MIP relative gap tolerance.")
@click.option("--verbose/--no-verbose", "verbose", default=None, help="Enable solver verbosity.")
@click.option(
    "--solver-opt",
    "solver_opts",
    multiple=True,
    help="Override solver option as KEY=VALUE. Repeat for multiple.",
)
@click.option("--seed", type=int, default=None, help="Random seed for stochastic rates.")
@click.option(
    "--help-solver-options",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=lambda ctx, param, value: (print_solver_options_help(), ctx.exit(0)) if value else None,
    help="Show all solver options and exit.",
)
def cmd_compare(filename, set_overrides, solver, max_time, gap, verbose, solver_opts, seed):
    """Compare a base case against a variant defined by --set overrides.

    Runs both scenarios and prints a JSON document with base metrics, variant
    metrics, and the numeric delta (variant minus base) for every metric.

    \b
    Examples:
      owlcli compare case.toml --set basic_info.state=MN
      owlcli compare case.toml --set 'fixed_income.social_security_ages=[70,68]'
      owlcli compare case.toml \\
          --set optimization_parameters.objective=maxBequest \\
          --set solver_options.netSpending=90
    """
    diconf_base, dirname, _ = load_toml(str(filename))
    diconf_variant = apply_overrides(diconf_base, set_overrides)

    solver_kwargs = dict(
        solver=solver, max_time=max_time, gap=gap,
        verbose=verbose, solver_opts=solver_opts, seed=seed,
    )

    plan_base = _solve_case(diconf_base, dirname, label="base", **solver_kwargs)
    plan_variant = _solve_case(diconf_variant, dirname, label="variant", **solver_kwargs)

    if plan_base.caseStatus != "solved" or plan_variant.caseStatus != "solved":
        result = {
            "error": "One or both cases did not solve",
            "base_status": plan_base.caseStatus,
            "variant_status": plan_variant.caseStatus,
        }
        sys.stdout.write(json.dumps(result, indent=2))
        sys.stdout.write("\n")
        sys.exit(1)

    m_base = plan_metrics(plan_base)
    m_variant = plan_metrics(plan_variant)
    delta = _diff(m_base, m_variant)

    pct_change = {
        k: _pct(delta[k], m_base[k])
        for k in KEY_METRICS
        if k in delta and delta[k] is not None
    }

    result = {
        "filename": str(filename),
        "overrides": list(set_overrides),
        "base": {k: round(v, 4) if isinstance(v, float) else v for k, v in m_base.items()},
        "variant": {k: round(v, 4) if isinstance(v, float) else v for k, v in m_variant.items()},
        "delta": {k: round(v, 4) if isinstance(v, float) else v for k, v in delta.items() if v is not None},
        "pct_change": pct_change,
    }

    sys.stdout.write(json.dumps(result, indent=2, cls=_NumpyEncoder))
    sys.stdout.write("\n")
