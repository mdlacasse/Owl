"""
Configuration management for Owl case parameters.

Provides loading/saving in TOML format with support for user-defined keys.
Uses Pydantic schema for structure and validation.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

from __future__ import annotations

from owlplanner import mylogging as log

from . import legacy
from .plan_bridge import apply_config_to_plan, config_to_plan, plan_to_config
from .schema import CaseConfig
from .toml_io import load_toml, save_toml, sanitize_config
from .ui_bridge import config_to_ui, ui_to_config


# Backward compatibility
translate_old_keys = legacy.translate_old_keys


def readConfig(file, *, verbose=True, logstreams=None, loadHFP=True):
    """
    Read plan parameters from case file *basename*.toml.
    A new plan is created and returned.
    Argument file can be a filename, a file, or a stringIO.
    """
    mylog = log.Logger(verbose, logstreams)

    diconf, dirname, filename = load_toml(file)

    if filename is not None:
        mylog.vprint(f"Reading plan from case file '{filename}'.")

    return config_to_plan(
        diconf,
        dirname,
        verbose=verbose,
        logstreams=logstreams,
        loadHFP=loadHFP,
    )


def saveConfig(myplan, file, mylog):
    """
    Save case parameters to TOML file.
    User-defined sections are preserved if they were present when the plan was loaded.
    """
    diconf = plan_to_config(myplan)
    save_toml(diconf, file, mylog=mylog)
    return diconf


def load_config(file):
    """
    Load configuration dict from TOML file (no Plan creation).
    Returns (diconf, dirname, filename).
    """
    return load_toml(file)


__all__ = [
    "readConfig",
    "saveConfig",
    "load_config",
    "load_toml",
    "sanitize_config",
    "save_toml",
    "config_to_plan",
    "plan_to_config",
    "apply_config_to_plan",
    "config_to_ui",
    "ui_to_config",
    "CaseConfig",
    "translate_old_keys",
]
