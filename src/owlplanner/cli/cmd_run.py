"""
CLI command for running retirement planning cases.

This module provides the 'run' command for executing retirement planning
optimization from the command line.

Copyright (C) 2025-2026 The Owlplanner Authors

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

import click
from loguru import logger
import owlplanner as owl
from pathlib import Path

from owlplanner.config.schema import CLI_SOLVER_OVERRIDE_MAP, parse_solver_options

from .params_help import print_solver_options_help


def validate_toml(ctx, param, value: Path):
    if value is None:
        return None

    # If no suffix, append .toml
    if value.suffix == "":
        value = value.with_suffix(".toml")

    # Enforce .toml extension
    if value.suffix.lower() != ".toml":
        raise click.BadParameter("File must have a .toml extension")

    # Check existence AFTER normalization
    if not value.exists():
        raise click.BadParameter(f"File '{value}' does not exist")

    if not value.is_file():
        raise click.BadParameter(f"'{value}' is not a file")

    return value


def _parse_solver_opts(value):
    """Parse KEY=VALUE pairs for --solver-opt. Returns list of (key, value) tuples.
    Values are strings; schema coerces on validation."""
    if not value:
        return []
    result = []
    for item in value:
        if "=" not in item:
            raise click.BadParameter(
                f"Each --solver-opt must be KEY=VALUE (e.g. solver=HiGHS). Got: {item!r}"
            )
        key, _, val = item.partition("=")
        key = key.strip()
        if not key:
            raise click.BadParameter("Option key cannot be empty")
        result.append((key, val.strip()))
    return result


@click.command(
    name="run",
    epilog="Solver options can also be set in the [solver_options] section of the TOML file. "
    "Use --help-solver-options to list all options from PARAMETERS.md.",
)
@click.argument(
    "filename",
    type=click.Path(exists=False, dir_okay=False, path_type=Path),
    callback=validate_toml,
)
@click.option(
    "--with-config",
    "with_config",
    type=click.Choice(["no", "first", "last"], case_sensitive=False),
    default="first",
    show_default=True,
    help="Include case TOML as a worksheet: first tab, last tab, or omit.",
)
@click.option(
    "--solver",
    type=click.Choice(["default", "HiGHS", "MOSEK"], case_sensitive=True),
    default=None,
    help="Solver to use. 'default' picks MOSEK if licensed, else HiGHS.",
)
@click.option(
    "--max-time",
    type=float,
    default=None,
    help="Solver time limit in seconds.",
)
@click.option(
    "--gap",
    type=float,
    default=None,
    help="MIP relative gap tolerance (e.g. 1e-4).",
)
@click.option(
    "--verbose/--no-verbose",
    "verbose",
    default=None,
    help="Enable solver verbosity.",
)
@click.option(
    "--solver-opt",
    "solver_opts",
    multiple=True,
    help="Override solver option as KEY=VALUE. Repeat for multiple. E.g. --solver-opt maxRothConversion=50.",
)
@click.option(
    "--help-solver-options",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=lambda ctx, param, value: (print_solver_options_help(), ctx.exit(0)) if value else None,
    help="Show all solver options (parsed from PARAMETERS.md) and exit.",
)
def cmd_run(filename: Path, with_config: str, solver, max_time, gap, verbose, solver_opts):
    """Run the retirement planning optimizer on an OWL case file.

    Loads the case from FILENAME (a .toml file), solves the optimization
    problem, and writes results to an Excel workbook. The output file is
    named by appending '_results.xlsx' to the input stem.

    Solver options are read from the [solver_options] section of the TOML
    file. Command-line flags override those values. Use --solver-opt to
    set any option (see PARAMETERS.md for the full list).
    """
    logger.debug(f"Executing the run command with file: {filename}")

    plan = owl.readConfig(str(filename), logstreams="loguru", loadHFP=True)
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

    plan.solve(plan.objective, opts)
    click.echo(f"Case status: {plan.caseStatus}")
    if plan.caseStatus == "solved":
        output_filename = filename.with_name(filename.stem + "_results.xlsx")
        plan.saveWorkbook(basename=output_filename, overwrite=True, with_config=with_config)
        click.echo(f"Results saved to: {output_filename}")
