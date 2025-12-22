import click
from pathlib import Path
from loguru import logger

import owlplanner as owl


@click.command(name="list")
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
def cmd_list(directory):
    """
    List OWL plan files in a directory.

    DIRECTORY defaults to the current directory.
    """
    logger.debug(f"Listing plans in directory: {directory}")

    toml_files = sorted(directory.glob("*.toml"))

    if not toml_files:
        click.echo("No .toml files found.")
        return

    plans = []

    for filename in toml_files:
        try:
            logger.debug(f"Loading plan from {filename}")
            plan = owl.readConfig(str(filename), logstreams="loguru", readContributions=False)
            plans.append((filename.stem, plan))
        except Exception as e:
            logger.warning(f"Failed to load {filename}: {e}")

    if not plans:
        click.echo("No valid OWL plans found.")
        return

    click.echo(f"{'FILE':<30} {'PLAN NAME':<20} {' TIME LISTS FILE':<30}")
    click.echo("-" * 80)

    CHECK = "✓"
    CROSS = "✗"

    plan_dir = directory

    for stem, plan in plans:
        # Truncate plan name if needed
        plan_name = plan._name
        if len(plan_name) > 20:
            plan_name = plan_name[:16] + "..."

        # Check if timeListsFileName exists in current directory
        tl_name = plan.timeListsFileName
        exists = (plan_dir / tl_name).exists() if tl_name else False
        mark = CHECK if exists else CROSS

        click.echo(f"{stem:<30} {plan_name:<20}  {mark}{tl_name:<30}")
