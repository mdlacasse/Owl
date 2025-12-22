import click
import hydra
from loguru import logger
from pathlib import Path
from hydra.errors import HydraException
from omegaconf import OmegaConf
from omegaconf.errors import OmegaConfBaseException


@click.command(
    name="hydra",
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
)
@click.pass_context
def cmd_hydra(ctx):
    """Hydra something."""
    logger.debug("Running hydra command")
    logger.debug("Overrides: {}", ctx.args)

    if 0:
        try:
            with hydra.initialize_config_dir(
                version_base="1.2",
                config_dir=str(Path.cwd()),
            ):
                cfg = hydra.compose(
                    config_name="owlconfig",
                    overrides=list(ctx.args),
                )

                logger.success("Hydra config composed successfully")
                click.echo(OmegaConf.to_yaml(cfg))

        except (HydraException, OmegaConfBaseException) as e:
            raise click.ClickException(str(e)) from None
