"""
Tests for rate_models code.


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
import numpy as np
import pandas as pd
from owlplanner import Plan
from owlplanner.rate_models.constants import REQUIRED_RATE_COLUMNS


def test_rate_model_default():

    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setRates("default")
    assert p.tau_kn.shape == (4, p.N_n)


def test_stochastic_regen_changes_series():
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setReproducible(False)
    p.setRates(
        method="stochastic",
        values=[7.0, 4.0, 3.0, 2.0],
        stdev=[15.0, 8.0, 6.0, 2.0],
    )
    tau1 = p.tau_kn.copy()
    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()
    assert not np.allclose(tau1, tau2)


def test_default_does_not_regen():
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    p.setRates("default")
    tau1 = p.tau_kn.copy()

    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()

    assert np.allclose(tau1, tau2)


def test_user_fixed_rates():
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    p.setRates(
        method="user",
        values=[5.0, 3.0, 2.0, 1.5],
    )

    # First year should equal fixed rates (converted to decimal)
    first_year = p.tau_kn[:, 0]

    assert np.allclose(first_year, [0.05, 0.03, 0.02, 0.015])


def test_stochastic_reproducible_same_series():
    p1 = Plan(["Joe"], ["1961-01-15"], [80], "test1", verbose=False)
    p1.setReproducible(True, seed=1234)
    p1.setRates(
        method="stochastic",
        values=[7.0, 4.0, 3.0, 2.0],
        stdev=[15.0, 8.0, 6.0, 2.0],
    )

    p2 = Plan(["Joe"], ["1961-01-15"], [80], "test2", verbose=False)
    p2.setReproducible(True, seed=1234)
    p2.setRates(
        method="stochastic",
        values=[7.0, 4.0, 3.0, 2.0],
        stdev=[15.0, 8.0, 6.0, 2.0],
    )

    assert np.allclose(p1.tau_kn, p2.tau_kn)


def test_historical_range():
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    p.setRates(method="historical", frm=1980)

    assert p.tau_kn.shape == (4, p.N_n)


def test_reverse_sequence():
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    p.setRates(method="historical", frm=1980)
    tau_forward = p.tau_kn.copy()

    p.setRates(method="historical", frm=1980, reverse=True)
    tau_reverse = p.tau_kn.copy()

    assert np.allclose(tau_forward[:, ::-1], tau_reverse)


def test_roll_sequence():
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    p.setRates(method="historical", frm=1980)
    tau_forward = p.tau_kn.copy()

    p.setRates(method="historical", frm=1980, roll=3)
    tau_roll = p.tau_kn.copy()

    assert np.allclose(np.roll(tau_forward, shift=3, axis=1), tau_roll)


def test_dataframe_method():
    # Sequential format: no year column, rows read in order
    # Values in percent (default in_percent=True)
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    n = p.N_n

    df = pd.DataFrame({
        "S&P 500":   [5.0] * n,   # percent → stored as 0.05
        "Bonds Baa": [3.0] * n,
        "T-Notes":    [2.5] * n,
        "Inflation": [2.0] * n,
    })

    p.setRates(method="dataframe", df=df)

    # tau_kn is (4, N) and always decimal
    assert np.allclose(p.tau_kn[0], 0.05)


def test_dataframe_method_in_percent_false():
    # Values already in decimal; in_percent=False skips the /100 conversion
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    n = p.N_n

    df = pd.DataFrame({
        "S&P 500":   [0.05] * n,
        "Bonds Baa": [0.03] * n,
        "T-Notes":    [0.025] * n,
        "Inflation": [0.02] * n,
    })

    p.setRates(method="dataframe", df=df, in_percent=False)

    # tau_kn is (4, N) and always decimal
    assert np.allclose(p.tau_kn[0], 0.05)


def test_external_plugin_loading(tmp_path):
    plugin_code = """
from owlplanner.rate_models.base import BaseRateModel
import numpy as np

class RateModel(BaseRateModel):
    def generate(self, N):
        return np.ones((N, 4)) * 0.05
"""

    plugin_path = tmp_path / "my_plugin.py"
    plugin_path.write_text(plugin_code)

    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    p.setRates(
        method="custom",
        method_file=str(plugin_path),
    )

    assert np.allclose(p.tau_kn, 0.05)


def test_plugin_bad_shape(tmp_path):
    plugin_code = """
from owlplanner.rate_models.base import BaseRateModel
import numpy as np

class RateModel(BaseRateModel):
    def generate(self, N):
        return np.ones((N, 3))
"""

    plugin_path = tmp_path / "bad_plugin.py"
    plugin_path.write_text(plugin_code)

    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    with pytest.raises(RuntimeError):
        p.setRates(method="custom", method_file=str(plugin_path))


def test_unknown_method_raises():
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    with pytest.raises(ValueError):
        p.setRates(method="unknown_method")


def test_plugin_missing_class(tmp_path):
    plugin_code = """
# No RateModel class here
"""

    plugin_path = tmp_path / "bad_plugin.py"
    plugin_path.write_text(plugin_code)

    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    with pytest.raises(ValueError):
        p.setRates(method="custom", method_file=str(plugin_path))


def test_plugin_file_not_found():
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    with pytest.raises(FileNotFoundError):
        p.setRates(method="custom", method_file="does_not_exist.py")


def test_deterministic_plugin_no_regen(tmp_path):
    plugin_code = """
from owlplanner.rate_models.base import BaseRateModel
import numpy as np

class RateModel(BaseRateModel):
    @property
    def deterministic(self):
        return True

    def generate(self, N):
        return np.ones((N, 4)) * 0.03
"""
    plugin_path = tmp_path / "det_plugin.py"
    plugin_path.write_text(plugin_code)

    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    p.setRates(method="custom", method_file=str(plugin_path))
    tau1 = p.tau_kn.copy()

    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()

    assert np.allclose(tau1, tau2)


def test_plugin_reverse_roll(tmp_path):
    plugin_code = """
from owlplanner.rate_models.base import BaseRateModel
import numpy as np

class RateModel(BaseRateModel):
    def generate(self, N):
        arr = np.arange(N).reshape(N,1)
        return np.hstack([arr, arr, arr, arr]) / 100.0
"""
    plugin_path = tmp_path / "seq_plugin.py"
    plugin_path.write_text(plugin_code)

    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)

    p.setRates(method="custom", method_file=str(plugin_path))
    forward = p.tau_kn.copy()

    p.setRates(method="custom", method_file=str(plugin_path), reverse=True)
    reversed_series = p.tau_kn.copy()

    assert np.allclose(forward[:, ::-1], reversed_series)


@pytest.mark.parametrize("missing_col", REQUIRED_RATE_COLUMNS)
def test_dataframe_missing_column(missing_col):
    """DataFrame must include every required column; reject when any one is missing."""
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    n = p.N_n

    # Build df with all columns except the one under test
    data = {"S&P 500": [5.0] * n, "Bonds Baa": [3.0] * n, "T-Notes": [2.5] * n, "Inflation": [2.0] * n}
    del data[missing_col]
    df = pd.DataFrame(data)

    with pytest.raises(ValueError, match="missing required columns"):
        p.setRates(method="dataframe", df=df)


def test_dataframe_insufficient_rows():
    """DataFrame must have at least n_years + offset rows."""
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    n = p.N_n

    # Too few rows (n-1 instead of n)
    df = pd.DataFrame({
        "S&P 500": [5.0] * (n - 1),
        "Bonds Baa": [3.0] * (n - 1),
        "T-Notes": [2.5] * (n - 1),
        "Inflation": [2.0] * (n - 1),
    })

    with pytest.raises(ValueError, match="needs at least"):
        p.setRates(method="dataframe", df=df)
