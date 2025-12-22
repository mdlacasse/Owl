import click
from loguru import logger

@click.command(name="run")
def cmd_run():
    """Run something."""
    logger.debug("Executing the run command")    
    click.echo("Running...")