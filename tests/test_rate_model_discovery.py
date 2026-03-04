"""
Tests for rate model discovery / metadata system.

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

import pytest
from owlplanner.rate_models.loader import (
    list_available_rate_models,
    get_rate_model_metadata,
)


# ------------------------------------------------------------
# 1. Available models listing
# ------------------------------------------------------------

def test_list_available_rate_models_contains_expected():
    models = list_available_rate_models()

    assert "default" in models
    assert "user" in models
    assert "stochastic" in models
    assert "historical" in models
    assert "dataframe" in models


# ------------------------------------------------------------
# 2. setRate metadata
# ------------------------------------------------------------

def test_rate_user_metadata():
    meta = get_rate_model_metadata("user")

    assert meta["model_name"] == "user"
    assert "User-specified" in meta["description"]
    assert "values" in meta["required_parameters"]
    assert meta["required_parameters"]["values"]["length"] == 4


def test_legacy_stochastic_metadata():
    meta = get_rate_model_metadata("stochastic")

    assert "values" in meta["required_parameters"]
    assert "stdev" in meta["required_parameters"]
    assert "corr" in meta["optional_parameters"]


# ------------------------------------------------------------
# 3. DataFrame model metadata
# ------------------------------------------------------------

def test_dataframe_metadata():
    meta = get_rate_model_metadata("dataframe")

    assert meta["model_name"] == "dataframe"
    assert "DataFrame" in meta["description"]
    assert "df" in meta["required_parameters"]


# ------------------------------------------------------------
# 4. Unknown method should raise
# ------------------------------------------------------------

def test_unknown_method_raises():
    with pytest.raises(ValueError):
        get_rate_model_metadata("not_a_real_method")


# ------------------------------------------------------------
# 5. External plugin metadata
# ------------------------------------------------------------

def test_external_plugin_metadata(tmp_path):

    plugin_code = """
from owlplanner.rate_models.base import BaseRateModel
import numpy as np

class RateModel(BaseRateModel):

    model_name = "my_plugin"
    description = "Test plugin model."

    required_parameters = {
        "foo": {"type": "float"}
    }

    optional_parameters = {}

    def generate(self, N):
        return np.ones((N, 4)) * 0.01
"""

    plugin_path = tmp_path / "my_plugin.py"
    plugin_path.write_text(plugin_code)

    meta = get_rate_model_metadata("custom", method_file=str(plugin_path))

    assert meta["model_name"] == "my_plugin"
    assert "Test plugin model." in meta["description"]
    assert "foo" in meta["required_parameters"]


# ------------------------------------------------------------
# 6. Plugin missing RateModel class
# ------------------------------------------------------------

def test_plugin_missing_class_raises(tmp_path):

    plugin_code = """
# no RateModel class here
"""

    plugin_path = tmp_path / "bad_plugin.py"
    plugin_path.write_text(plugin_code)

    with pytest.raises(ValueError):
        get_rate_model_metadata("custom", method_file=str(plugin_path))
