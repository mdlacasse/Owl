import click

@click.command(name="run")
def cmd_run():
    """Run something."""
    click.echo("Running...")