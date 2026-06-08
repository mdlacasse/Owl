"""
--set KEY.PATH=VALUE override parsing and application.

Overrides are applied to the raw config dict (post-TOML load, pre-plan-bridge)
so that all existing validation and type coercion in config_to_plan still runs.

Usage::

    owlcli run case.toml --set basic_info.state=TX
    owlcli run case.toml --set fixed_income.social_security_ages=[70,67]
    owlcli run case.toml --set solver_options.withSSAges=optimize
    owlcli run case.toml --set rates_selection.method=conservative

Supported value syntax (JSON subset):
    Scalars:   TX  42  3.14  true  false  null
    Lists:     [70,67]  ["Jack","Jill"]
    Strings:   unquoted strings are tried as JSON first, then kept as-is
"""

import copy
import json

import click


def _parse_value(raw: str):
    """
    Coerce a CLI string to the most natural Python type.

    Try JSON first (handles true/false/null/numbers/lists/quoted strings),
    then fall back to plain string so bare words like ``TX`` or ``optimize``
    work without quotes.
    """
    stripped = raw.strip()
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return stripped


def _parse_one(spec: str) -> tuple[list[str], object]:
    """
    Parse a single ``KEY.PATH=VALUE`` spec.

    Returns (path_parts, value).  Raises click.BadParameter on bad syntax.
    """
    if "=" not in spec:
        raise click.BadParameter(
            f"--set requires KEY=VALUE syntax (got {spec!r}). "
            "Example: --set basic_info.state=TX"
        )
    key_part, _, val_part = spec.partition("=")
    key_part = key_part.strip()
    if not key_part:
        raise click.BadParameter(f"--set key cannot be empty (got {spec!r})")
    path = [p.strip() for p in key_part.split(".")]
    if any(not p for p in path):
        raise click.BadParameter(
            f"--set key has empty path component (got {key_part!r})"
        )
    return path, _parse_value(val_part)


def apply_overrides(diconf: dict, specs: tuple[str, ...] | list[str]) -> dict:
    """
    Apply a sequence of ``KEY.PATH=VALUE`` override specs to a raw config dict.

    Returns a deep copy of *diconf* with all overrides applied.
    Raises click.BadParameter for syntax errors or unknown top-level sections.
    """
    if not specs:
        return diconf

    result = copy.deepcopy(diconf)

    for spec in specs:
        path, value = _parse_one(spec)
        _set_path(result, path, value, spec)

    return result


def _set_path(d: dict, path: list[str], value, spec: str) -> None:
    """Navigate *path* into *d* and set the leaf to *value*."""
    node = d
    for part in path[:-1]:
        if part not in node:
            # Create intermediate section if it doesn't exist yet.
            node[part] = {}
        if not isinstance(node[part], dict):
            raise click.BadParameter(
                f"--set path {spec!r}: '{part}' is not a section "
                f"(got {type(node[part]).__name__})"
            )
        node = node[part]
    node[path[-1]] = value
