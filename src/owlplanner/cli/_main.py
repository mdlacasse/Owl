"""
Command-line interface main entry point for Owl retirement planner.

This module provides the main CLI group and command registration for the
Owl command-line interface.

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


from .cli_logging import configure_logging, LOG_LEVELS
from .cmd_list import cmd_list
from .cmd_run import cmd_run


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(LOG_LEVELS, case_sensitive=False),
    default="INFO",
    show_default=True,
    help="Set logging verbosity.",
)
@click.pass_context
def cli(ctx, log_level: str):
    """SSG command-line interface."""
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level.upper()

    configure_logging(log_level)


cli.add_command(cmd_list)
cli.add_command(cmd_run)

if __name__ == "__main__":
    cli()
