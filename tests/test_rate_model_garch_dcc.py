"""
Tests for the DCC-GARCH(1,1) rate model.

Covers:
- Model attributes (name, flags)
- Output shape and range
- Reproducibility
- Fitted parameter shapes and stationarity
- DCC parameter validity
- Q_bar positive-definiteness
- Historical window sensitivity
- Edge-case validation (too few observations, invalid range)

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

import numpy as np
import pytest

from owlplanner import Plan
from owlplanner.rate_models.garch_dcc import GARCHDCCRateModel


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _make_plan():
    return Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)


def _set_garch_dcc(p, frm=1928, to=2024, seed=None):
    if seed is not None:
        p.setReproducible(True, seed=seed)
    else:
        p.setReproducible(False)
    p.setRates(method="garch_dcc", frm=frm, to=to)


def _make_model(frm=1928, to=2024, seed=None):
    config = {"method": "garch_dcc", "frm": frm, "to": to}
    return GARCHDCCRateModel(config, seed=seed)


# ------------------------------------------------------------
# Model attributes
# ------------------------------------------------------------

def test_model_name():
    assert GARCHDCCRateModel.model_name == "garch_dcc"


def test_deterministic_flag():
    assert GARCHDCCRateModel.deterministic is False


def test_constant_flag():
    assert GARCHDCCRateModel.constant is False


# ------------------------------------------------------------
# Output shape and sanity
# ------------------------------------------------------------

def test_shape_via_plan():
    """tau_kn should be (4, N_n) after setRates with garch_dcc."""
    p = _make_plan()
    _set_garch_dcc(p)
    assert p.tau_kn.shape == (4, p.N_n)


def test_output_is_finite():
    """All generated rates should be finite (no NaN/Inf)."""
    p = _make_plan()
    _set_garch_dcc(p)
    assert np.all(np.isfinite(p.tau_kn))


def test_generate_shape_direct():
    """GARCHDCCRateModel.generate(N) should return (N, 4)."""
    model = _make_model(seed=42)
    out = model.generate(30)
    assert out.shape == (30, 4)


def test_rates_in_plausible_range():
    """
    Annual returns should stay within a wide but plausible range.
    Values outside [-100%, +200%] per year would indicate a model failure.
    """
    model = _make_model(seed=0)
    out = model.generate(500)
    assert np.all(out > -1.0), "Some returns below -100%"
    assert np.all(out < 2.0), "Some returns above +200%"


# ------------------------------------------------------------
# Reproducibility
# ------------------------------------------------------------

def test_reproducible_same_seed():
    """Two plans with the same seed must produce identical tau_kn."""
    p1 = _make_plan()
    _set_garch_dcc(p1, seed=42)

    p2 = _make_plan()
    _set_garch_dcc(p2, seed=42)

    assert np.allclose(p1.tau_kn, p2.tau_kn)


def test_different_seeds_differ():
    """Different seeds should (with overwhelming probability) produce different output."""
    p1 = _make_plan()
    _set_garch_dcc(p1, seed=1)

    p2 = _make_plan()
    _set_garch_dcc(p2, seed=2)

    assert not np.allclose(p1.tau_kn, p2.tau_kn)


def test_non_reproducible_regen_changes():
    """regenRates(override_reproducible=True) must produce a new sequence."""
    p = _make_plan()
    _set_garch_dcc(p)
    tau1 = p.tau_kn.copy()

    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()

    assert not np.allclose(tau1, tau2)


# ------------------------------------------------------------
# Fitted GARCH parameters
# ------------------------------------------------------------

def test_fitted_garch_param_shapes():
    """omega, alpha, beta, sigma2_0 must all be shape (4,)."""
    model = _make_model()
    assert model._garch_omega.shape == (4,)
    assert model._garch_alpha.shape == (4,)
    assert model._garch_beta.shape == (4,)
    assert model._sigma2_0.shape == (4,)


def test_garch_stationarity():
    """alpha + beta < 1 for all assets (stationarity condition)."""
    model = _make_model()
    assert np.all(model._garch_alpha + model._garch_beta < 1.0)


# ------------------------------------------------------------
# Fitted DCC parameters
# ------------------------------------------------------------

def test_dcc_params_valid():
    """a, b must be scalars in (0, 1) with a + b < 1."""
    model = _make_model()
    a = model._dcc_a
    b = model._dcc_b
    assert 0 < a < 1, f"DCC a={a} out of (0,1)"
    assert 0 < b < 1, f"DCC b={b} out of (0,1)"
    assert a + b < 1.0, f"DCC a+b={a+b} >= 1"


def test_Q_bar_positive_definite():
    """Q_bar must be positive definite (all eigenvalues > 0)."""
    model = _make_model()
    eigs = np.linalg.eigvalsh(model._Q_bar)
    assert np.all(eigs > 0), f"Q_bar eigenvalues: {eigs}"


# ------------------------------------------------------------
# Historical window sensitivity
# ------------------------------------------------------------

def test_different_windows_differ():
    """
    Models fitted on different windows should generate different sequences
    even with the same seed.
    """
    p1 = _make_plan()
    _set_garch_dcc(p1, frm=1928, to=1970, seed=7)

    p2 = _make_plan()
    _set_garch_dcc(p2, frm=1980, to=2024, seed=7)

    assert not np.allclose(p1.tau_kn, p2.tau_kn)


# ------------------------------------------------------------
# Parameter validation
# ------------------------------------------------------------

def test_too_few_observations_raises():
    """Window of only 5 years should raise ValueError."""
    config = {"method": "garch_dcc", "frm": 2020, "to": 2024}
    with pytest.raises(ValueError, match="at least 15 observations"):
        GARCHDCCRateModel(config)


def test_frm_equals_to_raises():
    """frm == to should raise ValueError."""
    config = {"method": "garch_dcc", "frm": 2000, "to": 2000}
    with pytest.raises(ValueError):
        GARCHDCCRateModel(config)
