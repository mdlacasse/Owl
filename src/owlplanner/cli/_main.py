import click


from .cli_logging import configure_logging, LOG_LEVELS
from .cmd_list import cmd_list
from .cmd_run import cmd_run
from .cmd_hydra import cmd_hydra


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
cli.add_command(cmd_hydra)

if __name__ == "__main__":
    cli()
