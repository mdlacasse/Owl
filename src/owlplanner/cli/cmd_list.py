import click

@click.command(name="list")
def cmd_list():
    """List something."""
    click.echo("Listing items...")