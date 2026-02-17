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

from owlplanner.rate_models.builtin import BuiltinRateModel
from owlplanner.rate_models.dataframe import DataFrameRateModel
from owlplanner.rate_models.bootstrap_sor import BootstrapSORRateModel


# ------------------------------------------------------------
# Allowed built-in method names
# ------------------------------------------------------------

BUILTIN_CORE_METHODS = BuiltinRateModel.list_methods()

BUILTIN_EXTENDED_METHODS = {
    "dataframe",
    "bootstrap_sor",
}

ALLOWED_METHODS = BUILTIN_CORE_METHODS | BUILTIN_EXTENDED_METHODS


# ------------------------------------------------------------
# Loader
# ------------------------------------------------------------

def load_rate_model(method, method_file=None):
    """
    Resolve and return a RateModel class.

    Priority order:
        1. External plugin (if method_file provided)
        2. Extended built-in models (dataframe, bootstrap_sor)
        3. Core built-in models
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
    # 2. Extended built-ins
    # ------------------------------------------------------------
    if method == "dataframe":
        return DataFrameRateModel

    if method == "bootstrap_sor":
        return BootstrapSORRateModel

    # ------------------------------------------------------------
    # 3. Core built-ins
    # ------------------------------------------------------------
    if method in BUILTIN_CORE_METHODS:
        return BuiltinRateModel

    # ------------------------------------------------------------
    # Unknown method
    # ------------------------------------------------------------
    raise ValueError(
        f"Unknown rate method '{method}'. "
        f"Allowed methods: {sorted(ALLOWED_METHODS)} "
        f"or provide method_file for plugin."
    )


def list_available_rate_models():
    return sorted(ALLOWED_METHODS)


def get_rate_model_metadata(method, method_file=None):
    ModelClass = load_rate_model(method, method_file)

    if ModelClass is BuiltinRateModel:
        return BuiltinRateModel.get_method_metadata(method)

    return ModelClass.get_metadata()

import pathlib
from urllib.parse import urlparse


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

    # Built-in methods
    for method, md in BuiltinRateModel.BUILTINS_METADATA.items():
        metadata.append({
            "method": method,
            "description": md.get("description", ""),
            "more_info": md.get("more_info"),
            "required_parameters": md.get("required_parameters", {}),
            "optional_parameters": md.get("optional_parameters", {}),
            "deterministic": md.get("deterministic", True),
            "constant": md.get("constant", True),
        })

    # Extended models
    for method in sorted(ALLOWED_METHODS):
        ModelClass = load_rate_model(method)

        if ModelClass is BuiltinRateModel:
            continue

        md = ModelClass.get_metadata().copy()

        metadata.append({
            "method": method,
            "description": md.get("description", ""),
            "more_info": md.get("more_info"),
            "required_parameters": md.get("required_parameters", {}),
            "optional_parameters": md.get("optional_parameters", {}),
            "deterministic": md.get("deterministic", False),
            "constant": md.get("constant", False),
        })

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


# ------------------------------------------------------------
# Markdown generation
# ------------------------------------------------------------

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
    lines.append("## :orange[Available Rate Models]")
    lines.append("")
    lines.append(
        "The following rate models are available via the `method` field "
        "in `[rates_selection]`."
    )
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
                    description = (
                        description.rstrip()
                        + f" [click here for more info]({more_info})"
                    )

                lines.append(description)
                lines.append("")

            # -------------------------
            # Parameter table
            # -------------------------
            lines.append("| Parameter | Required | Type | Description |")
            lines.append("|-----------|----------|------|-------------|")

            # method parameter always first
            lines.append(
                f"| `method` | Yes | str | model name (`\"{method}\"`) |"
            )

            # Required parameters in declared order
            for name, p in required.items():
                lines.append(
                    f"| `{name}` | Yes | {p.get('type','')} | {p.get('description','')} |"
                )

            # Optional parameters
            for name, p in optional.items():
                lines.append(
                    f"| `{name}` | No | {p.get('type','')} | {p.get('description','')} |"
                )

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

                lines.append(f"{name} = {example_value}")

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
