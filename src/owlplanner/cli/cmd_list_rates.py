"""
CLI command for listing available rate models and their parameters.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import json
import sys

import click

from owlplanner.rate_models.loader import get_all_models_metadata, RATE_MODEL_ALIASES


@click.command(name="list-rates")
@click.option(
    "--category",
    type=click.Choice(["single", "deterministic", "stochastic", "dataframe", "all"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Filter by category.",
)
def cmd_list_rates(category):
    """List available rate models and their parameters.

    Prints a JSON document with every registered rate model: its canonical
    name, description, category, determinism flags, required and optional
    parameters, and any legacy aliases that resolve to it.

    Categories:
      single       — constant rates (no year-to-year variation)
      deterministic — year-varying but reproducible (e.g. historical replay)
      stochastic   — random sampling (Monte Carlo)
      dataframe    — programmatic only, not TOML-serializable

    \b
    Examples:
      owlcli list-rates
      owlcli list-rates --category stochastic
    """
    models = get_all_models_metadata()

    if category != "all":
        models = [m for m in models if m["category"] == category]

    # Build reverse alias map: canonical → [alias, ...]
    reverse_aliases: dict[str, list[str]] = {}
    for alias, canonical in RATE_MODEL_ALIASES.items():
        reverse_aliases.setdefault(canonical, []).append(alias)

    # Attach aliases to each model entry
    for m in models:
        m["aliases"] = sorted(reverse_aliases.get(m["method"], []))

    result = {
        "models": sorted(models, key=lambda m: (m["category"], m["method"])),
        "aliases": {alias: canonical for alias, canonical in sorted(RATE_MODEL_ALIASES.items())},
    }

    sys.stdout.write(json.dumps(result, indent=2))
    sys.stdout.write("\n")
