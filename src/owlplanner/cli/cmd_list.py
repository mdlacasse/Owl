import click
from loguru import logger

@click.command(name="list")
def cmd_list():
    """List something."""
    logger.debug("Executing the list command")
    click.echo("Listing items...")
