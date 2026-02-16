"""
Loader for pluggable rate models.

Resolves which RateModel class to use based on:
    - method name
    - optional external plugin file


Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
###########################################################################
import importlib.util
import pathlib

from owlplanner.rate_models.legacy import LegacyRateModel
from owlplanner.rate_models.dataframe import DataFrameRateModel
from owlplanner.rate_models.bootstrap_sor import BootstrapSORRateModel


# ------------------------------------------------------------
# Allowed built-in method names
# ------------------------------------------------------------

LEGACY_METHODS = {
    "default",
    "optimistic",
    "conservative",
    "user",
    "historical",
    "historical average",
    "stochastic",
    "histochastic",
}

BUILTIN_NEW_METHODS = {
    "dataframe",
    "bootstrap_sor",
}

ALLOWED_METHODS = LEGACY_METHODS | BUILTIN_NEW_METHODS

# ------------------------------------------------------------
# Loader
# ------------------------------------------------------------


def load_rate_model(method, method_file=None):
    """
    Resolve and return a RateModel class.

    Priority order:
        1. External plugin (if method_file provided)
        2. Built-in new models (e.g., dataframe)
        3. Legacy built-in models

    Raises:
        ValueError if method is unknown and no plugin file provided.
    """

    # ------------------------------------------------------------
    # 1. External plugin file
    # ------------------------------------------------------------
    if method_file is not None:
        path = pathlib.Path(method_file)

        if not path.exists():
            raise FileNotFoundError(f"Rate model file '{method_file}' not found.")

        spec = importlib.util.spec_from_file_location("rate_plugin", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "RateModel"):
            raise ValueError(
                f"Plugin file '{method_file}' must define class 'RateModel'."
            )

        return module.RateModel

    # ------------------------------------------------------------
    # 2. Built-in new models
    # ------------------------------------------------------------
    if method == "dataframe":
        return DataFrameRateModel

    if method == "bootstrap_sor":
        return BootstrapSORRateModel

    # ------------------------------------------------------------
    # 3. Legacy built-in models
    # ------------------------------------------------------------
    if method in LEGACY_METHODS:
        return LegacyRateModel

    # ------------------------------------------------------------
    # Unknown method
    # ------------------------------------------------------------
    raise ValueError(
        f"Unknown rate method '{method}'. "
        f"Allowed methods: {sorted(ALLOWED_METHODS)} "
        f"or provide method_file for plugin."
    )


def list_available_rate_models():
    """
    Return list of available model names.
    """
    return sorted(ALLOWED_METHODS)


def get_rate_model_metadata(method, method_file=None):
    """
    Return metadata dictionary for a rate model.
    """

    ModelClass = load_rate_model(method, method_file)

    # Legacy special handling
    if ModelClass is LegacyRateModel:
        return LegacyRateModel.get_method_metadata(method)

    return ModelClass.get_metadata()
