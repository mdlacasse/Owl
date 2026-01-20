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


@click.command(name="run")
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
    help="Include config TOML sheet at the first or last position.",
)
def cmd_run(filename: Path, with_config: str):
    """Run the solver for an input OWL plan file.

    FILENAME is the OWL plan file to run. If no extension is provided,
    .toml will be appended. The file must exist.

    An output Excel file with results will be created in the current directory.
    The output filename is derived from the input filename by appending
    '_results.xlsx' to the stem of the input filename.

    Optionally include the case configuration as a TOML worksheet.

    """
    logger.debug(f"Executing the run command with file: {filename}")

    plan = owl.readConfig(str(filename), logstreams="loguru", readContributions=True)
    plan.solve(plan.objective, plan.solverOptions)
    click.echo(f"Case status: {plan.caseStatus}")
    if plan.caseStatus == "solved":
        output_filename = filename.with_name(filename.stem + "_results.xlsx")
        plan.saveWorkbook(basename=output_filename, overwrite=True, with_config=with_config)
        click.echo(f"Results saved to: {output_filename}")
