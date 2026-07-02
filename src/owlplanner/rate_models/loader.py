"""
Loader for pluggable rate models.

Resolves which RateModel class to use based on:
    - method name
    - optional external plugin file


Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

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
import types
from urllib.parse import urlparse

from owlplanner.rate_models.builtin import (
    Trailing30RateModel,
    OptimisticRateModel,
    ConservativeRateModel,
    UserRateModel,
    HistoricalRateModel,
    HistoricalAverageRateModel,
    GaussianRateModel,
    LognormalRateModel,
    HistolognormalRateModel,
    HistogaussianRateModel,
)
from owlplanner.rate_models.copula import HistoCopulaRateModel
from owlplanner.rate_models.dataframe import DataFrameRateModel
from owlplanner.rate_models.historical_bootstrap import BootstrapSORRateModel
from owlplanner.rate_models.vector_ar import VARRateModel
from owlplanner.rate_models.garch_dcc import GARCHDCCRateModel
from owlplanner.rate_models.gmm import GMMRateModel
from owlplanner.rate_models.hmm import HMMRateModel


# ------------------------------------------------------------
# Unified registry of all built-in rate models
# ------------------------------------------------------------

# Method aliases; resolved at load_rate_model() lookup, not in registry
_METHOD_ALIASES = {
    # Backward-compatible aliases for renamed methods
    "default": "trailing_30",
    "trailing-30": "trailing_30",
    "historical average": "historical_average",
    "histogaussian": "historical_gaussian",
    "histochastic": "historical_gaussian",
    "stochastic": "historical_gaussian",
    "histolognormal": "historical_lognormal",
    "bootstrap_sor": "historical_bootstrap",
    "var": "vector_ar",
}

_RATE_MODEL_REGISTRY = {
    "trailing_30": Trailing30RateModel,
    "optimistic": OptimisticRateModel,
    "conservative": ConservativeRateModel,
    "user": UserRateModel,
    "historical": HistoricalRateModel,
    "historical_average": HistoricalAverageRateModel,
    "gaussian": GaussianRateModel,
    "lognormal": LognormalRateModel,
    "historical_lognormal": HistolognormalRateModel,
    "historical_gaussian": HistogaussianRateModel,
    "historical_copula": HistoCopulaRateModel,
    "dataframe": DataFrameRateModel,
    "historical_bootstrap": BootstrapSORRateModel,
    "vector_ar": VARRateModel,
    "garch_dcc": GARCHDCCRateModel,
    "gmm": GMMRateModel,
    "hmm": HMMRateModel,
}

BUILTIN_CORE_METHODS = frozenset(
    {
        "trailing_30",
        "optimistic",
        "conservative",
        "user",
        "historical",
        "historical_average",
        "gaussian",
        "historical_gaussian",
        "lognormal",
        "historical_lognormal",
    }
)

ALLOWED_METHODS = frozenset(_RATE_MODEL_REGISTRY.keys())


# ------------------------------------------------------------
# Loader
# ------------------------------------------------------------


def load_rate_model(method, method_file=None):
    """
    Resolve and return a RateModel class.

    Priority order:
        1. External plugin (if method_file provided)
        2. Registry lookup (builtin + extended models)

    Deprecated method aliases (e.g. stochastic → gaussian) are resolved before lookup.
    """
    method = _METHOD_ALIASES.get(method, method)

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
            raise ValueError(f"Plugin file '{method_file}' must define class 'RateModel'.")

        return module.RateModel

    # ------------------------------------------------------------
    # 2. Registry lookup
    # ------------------------------------------------------------
    if method in _RATE_MODEL_REGISTRY:
        return _RATE_MODEL_REGISTRY[method]

    # ------------------------------------------------------------
    # Unknown method
    # ------------------------------------------------------------
    raise ValueError(
        f"Unknown rate method '{method}'. Allowed methods: {sorted(ALLOWED_METHODS)} or provide method_file for plugin."
    )


def list_available_rate_models():
    return sorted(ALLOWED_METHODS)


def get_rate_model_metadata(method, method_file=None):
    return load_rate_model(method, method_file).get_metadata()


def get_all_models_metadata():
    """Return a list of metadata dicts for all registered rate models, with 'category' added."""
    entries = _collect_all_model_metadata()
    for e in entries:
        e["category"] = _categorize(e)
    return entries


RATE_MODEL_ALIASES = types.MappingProxyType(_METHOD_ALIASES)


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------


def _is_valid_url(url: str) -> bool:
    """
    Return True if string is a valid http/https URL.
    """
    if not isinstance(url, str):
        return False

    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


# ------------------------------------------------------------
# Metadata collection
# ------------------------------------------------------------


def _collect_all_model_metadata():
    """
    Collect normalized metadata for all individual rate methods.
    Each method is rendered separately.
    """

    metadata = []

    for method, ModelClass in _RATE_MODEL_REGISTRY.items():
        md = ModelClass.get_metadata()
        metadata.append(
            {
                "method": method,
                "model_name": md.get("model_name", method),
                "description": md.get("description", ""),
                "more_info": md.get("more_info"),
                "required_parameters": md.get("required_parameters", {}),
                "optional_parameters": md.get("optional_parameters", {}),
                "deterministic": md.get("deterministic", False),
                "constant": md.get("constant", False),
            }
        )

    return metadata


def _categorize(entry):
    """
    Determine grouping section.
    """
    if entry["method"] == "dataframe":
        return "dataframe"

    if entry["deterministic"] and entry["constant"]:
        return "single"

    if entry["deterministic"] and not entry["constant"]:
        return "deterministic"

    return "stochastic"


# TOML key aliases: internal param names → canonical TOML keys (match PARAMETERS.md)
_TOML_DISPLAY_KEYS = {"frm": "from"}


def generate_rate_models_markdown():
    """
    Generate structured Markdown documentation.
    Each model gets:
        - its own subsection
        - parameter table
        - TOML example using metadata-provided examples
        - optional more_info link appended to description
    """

    models = _collect_all_model_metadata()

    categories = {
        "single": [],
        "deterministic": [],
        "stochastic": [],
        "dataframe": [],
    }

    for entry in models:
        cat = _categorize(entry)
        categories.setdefault(cat, []).append(entry)

    lines = []
    lines.append("<!--")
    lines.append("Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors")
    lines.append("SPDX-License-Identifier: CC-BY-NC-SA-4.0")
    lines.append(
        "This documentation is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0; "
        "see LICENSE-docs in the repository root."
    )
    lines.append("-->")
    lines.append("")
    lines.append("## :orange[Available Rate Models]")
    lines.append("")
    lines.append("The following rate models are available via the `method` field in `[rates_selection]`.")
    lines.append("")

    def render_section(title, entries):
        if not entries:
            return

        lines.append(f"### :orange[{title}]")
        lines.append("")

        for entry in sorted(entries, key=lambda e: e["method"]):
            method = entry["method"]
            description = entry["description"]
            more_info = entry.get("more_info")
            required = entry["required_parameters"]
            optional = entry["optional_parameters"]

            lines.append(f"#### `{method}`")
            lines.append("")

            if description:
                if _is_valid_url(more_info):
                    description = description.rstrip() + f" [click here for more info]({more_info})"

                lines.append(description)
                lines.append("")

            # -------------------------
            # Parameter table
            # -------------------------
            lines.append("| Parameter | Required | Type | Description |")
            lines.append("|-----------|----------|------|-------------|")

            # method parameter always first
            lines.append(f'| `method` | Yes | str | model name (`"{method}"`) |')

            # Required parameters in declared order
            for name, p in required.items():
                doc_name = _TOML_DISPLAY_KEYS.get(name, name)
                lines.append(f"| `{doc_name}` | Yes | {p.get('type', '')} | {p.get('description', '')} |")

            # Optional parameters
            for name, p in optional.items():
                doc_name = _TOML_DISPLAY_KEYS.get(name, name)
                lines.append(f"| `{doc_name}` | No | {p.get('type', '')} | {p.get('description', '')} |")

            lines.append("")

            # -------------------------
            # Example block (required only)
            # -------------------------
            lines.append("**Example:**")
            lines.append("")
            lines.append("```toml")
            lines.append("[rates_selection]")
            lines.append(f'method = "{method}"')

            for name, p in required.items():
                doc_name = _TOML_DISPLAY_KEYS.get(name, name)
                example_value = p.get("example")

                if example_value is None:
                    # Safe fallback if metadata incomplete
                    ptype = p.get("type", "").lower()
                    if "int" in ptype:
                        example_value = "2000"
                    elif "float" in ptype:
                        example_value = "5.0"
                    elif "list" in ptype:
                        example_value = "[...]"
                    else:
                        example_value = '"value"'

                lines.append(f"{doc_name} = {example_value}")

            lines.append("```")
            lines.append("")

    render_section("Single-rate modes", categories.get("single", []))
    render_section("Deterministic models", categories.get("deterministic", []))
    render_section("Stochastic models", categories.get("stochastic", []))
    render_section("DataFrame model", categories.get("dataframe", []))

    return "\n".join(lines)


# ------------------------------------------------------------
# Export helper
# ------------------------------------------------------------


def export_rate_models_markdown(path: str):
    """
    Export generated Markdown documentation to file.
    """
    content = generate_rate_models_markdown()
    p = pathlib.Path(path)
    p.write_text(content, encoding="utf-8")
