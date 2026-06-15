"""
Tests for the VAR(1) rate model.

Covers:
- Output shape and range
- Deterministic flag and model attributes
- Reproducibility (same seed → same sequence)
- Non-reproducible regeneration produces different output
- regenRates() integration with Plan
- Stationarity shrinkage path
- Parameter validation (bounds, insufficient data)
- Reverse / roll sequence transforms
- Monte Carlo guard (runMC does not return None for var)

Copyright (C) 2025-2026 The Owl Authors

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
from owlplanner.rate_models._builtin_impl import _historical_arith_means
from owlplanner.rate_models.vector_ar import VARRateModel


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _make_plan():
    return Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)


def _set_var(p, frm=1928, to=2024, shrink=True, seed=None, reverse=False, roll=0):
    if seed is not None:
        p.setReproducible(True, seed=seed)
    else:
        p.setReproducible(False)
    p.setRates(method="vector_ar", frm=frm, to=to, shrink=shrink, reverse=reverse, roll=roll)


# ------------------------------------------------------------
# Model attributes
# ------------------------------------------------------------

def test_deterministic_flag_is_false():
    assert VARRateModel.deterministic is False


def test_constant_flag_is_false():
    assert VARRateModel.constant is False


def test_model_name():
    assert VARRateModel.model_name == "vector_ar"


# ------------------------------------------------------------
# Output shape and sanity
# ------------------------------------------------------------

def test_var_shape():
    """tau_kn should be (4, N_n) after setRates."""
    p = _make_plan()
    _set_var(p)
    assert p.tau_kn.shape == (4, p.N_n)


def test_var_output_is_finite():
    """All generated rates should be finite (no NaN/Inf)."""
    p = _make_plan()
    _set_var(p)
    assert np.all(np.isfinite(p.tau_kn))


def test_var_generate_shape_direct():
    """VARRateModel.generate(N) should return (N, 4)."""
    config = {"method": "vector_ar", "frm": 1950, "to": 2020}
    model = VARRateModel(config, seed=42)
    out = model.generate(30)
    assert out.shape == (30, 4)


def test_var_rates_in_plausible_range():
    """
    Annual returns should stay within a wide but plausible range.
    Values outside [-100%, +200%] per year would indicate a model failure.
    """
    config = {"method": "vector_ar", "frm": 1928, "to": 2024}
    model = VARRateModel(config, seed=0)
    # Generate a large sample to stress-test
    out = model.generate(500)
    assert np.all(out > -1.0), "Some returns below -100%"
    assert np.all(out < 2.0), "Some returns above +200%"


# ------------------------------------------------------------
# Reproducibility
# ------------------------------------------------------------

def test_reproducible_same_seed():
    """Two plans with the same seed must produce identical tau_kn."""
    p1 = _make_plan()
    _set_var(p1, seed=42)

    p2 = _make_plan()
    _set_var(p2, seed=42)

    assert np.allclose(p1.tau_kn, p2.tau_kn)


def test_different_seeds_produce_different_output():
    """Different seeds should (with overwhelming probability) differ."""
    p1 = _make_plan()
    _set_var(p1, seed=1)

    p2 = _make_plan()
    _set_var(p2, seed=2)

    assert not np.allclose(p1.tau_kn, p2.tau_kn)


def test_non_reproducible_regen_changes_output():
    """regenRates(override_reproducible=True) must produce a new sequence."""
    p = _make_plan()
    _set_var(p)
    tau1 = p.tau_kn.copy()

    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()

    assert not np.allclose(tau1, tau2)


def test_reproducible_regen_does_not_change_output():
    """regenRates() without override must leave tau_kn unchanged when reproducible."""
    p = _make_plan()
    _set_var(p, seed=99)
    tau1 = p.tau_kn.copy()

    p.regenRates()   # reproducible=True, no override → no-op
    tau2 = p.tau_kn.copy()

    assert np.allclose(tau1, tau2)


# ------------------------------------------------------------
# Fitting internals
# ------------------------------------------------------------

def test_fitted_matrices_shapes():
    """After fitting, _c should be (4,) and _A should be (4, 4)."""
    config = {"method": "vector_ar", "frm": 1928, "to": 2024}
    model = VARRateModel(config)
    assert model._c.shape == (4,)
    assert model._A.shape == (4, 4)
    assert model._L.shape == (4, 4)


def test_cholesky_factor_lower_triangular():
    """_L must be lower-triangular (Cholesky of residual covariance)."""
    config = {"method": "vector_ar", "frm": 1928, "to": 2024}
    model = VARRateModel(config)
    L = model._L
    assert np.allclose(np.triu(L, k=1), 0), "_L should be lower-triangular"


def test_shrinkage_applied_on_short_window():
    """
    A very short window can produce a high spectral radius; shrink=True
    should scale A down so the spectral radius is < 0.95.
    """
    config = {"method": "vector_ar", "frm": 1995, "to": 2010, "shrink": True}
    model = VARRateModel(config)
    rho = float(np.max(np.abs(np.linalg.eigvals(model._A))))
    assert rho < 0.95 + 1e-6, f"Spectral radius {rho:.4f} should be < 0.95 after shrinkage"


def test_shrink_false_does_not_raise():
    """shrink=False should not raise even if spectral radius is >= 0.95."""
    config = {"method": "vector_ar", "frm": 1995, "to": 2010, "shrink": False}
    model = VARRateModel(config)   # should not raise
    assert model._A is not None


# ------------------------------------------------------------
# Parameter validation
# ------------------------------------------------------------

def test_invalid_frm_too_low():
    p = _make_plan()
    with pytest.raises((ValueError, Exception)):
        p.setRates(method="vector_ar", frm=1800, to=2024)


def test_invalid_to_too_high():
    p = _make_plan()
    with pytest.raises((ValueError, Exception)):
        p.setRates(method="vector_ar", frm=1928, to=2200)


def test_frm_equals_to_raises():
    p = _make_plan()
    with pytest.raises((ValueError, Exception)):
        p.setRates(method="vector_ar", frm=2000, to=2000)


def test_frm_greater_than_to_raises():
    p = _make_plan()
    with pytest.raises((ValueError, Exception)):
        p.setRates(method="vector_ar", frm=2010, to=2000)


def test_too_few_observations_raises():
    """Window with fewer than 10 years should raise ValueError."""
    config = {"method": "vector_ar", "frm": 2020, "to": 2024}  # only 5 rows
    with pytest.raises(ValueError, match="at least 10 observations"):
        VARRateModel(config)


# ------------------------------------------------------------
# Historical window sensitivity
# ------------------------------------------------------------

def test_different_windows_produce_different_output():
    """
    Two VAR models fitted on different historical windows should
    generate different rate sequences (different c, A, L parameters).
    """
    p1 = _make_plan()
    _set_var(p1, frm=1928, to=1970, seed=7)

    p2 = _make_plan()
    _set_var(p2, frm=1980, to=2024, seed=7)

    assert not np.allclose(p1.tau_kn, p2.tau_kn)


# ------------------------------------------------------------
# Reverse / roll sequence transforms
# ------------------------------------------------------------

def test_reverse_applies():
    """Reversing the sequence should flip tau_kn along the time axis."""
    p_fwd = _make_plan()
    _set_var(p_fwd, seed=5, reverse=False)
    tau_fwd = p_fwd.tau_kn.copy()

    p_rev = _make_plan()
    _set_var(p_rev, seed=5, reverse=True)
    tau_rev = p_rev.tau_kn.copy()

    assert np.allclose(tau_rev, tau_fwd[:, ::-1])


def test_roll_applies():
    """Rolling by k should be equivalent to np.roll along the time axis."""
    k = 5
    p_base = _make_plan()
    _set_var(p_base, seed=3, roll=0)
    tau_base = p_base.tau_kn.copy()

    p_rolled = _make_plan()
    _set_var(p_rolled, seed=3, roll=k)
    tau_rolled = p_rolled.tau_kn.copy()

    assert np.allclose(tau_rolled, np.roll(tau_base, k, axis=1))


# ------------------------------------------------------------
# Constrain-mean option
# ------------------------------------------------------------

def test_constrain_mean_declared():
    """The constrain_mean option must be exposed in optional_parameters."""
    assert "constrain_mean" in VARRateModel.optional_parameters


def test_constrain_mean_matches_historical_window_mean():
    """
    With constrain_mean=True, each generated column's arithmetic mean must equal
    the historical window's arithmetic mean (additive correction is exact).
    """
    frm, to = 1928, 2024
    config = {"method": "vector_ar", "frm": frm, "to": to, "constrain_mean": True}
    model = VARRateModel(config, seed=42)
    out = model.generate(400)

    target = _historical_arith_means(frm, to)
    # Inflation (col 3) passes through a non-linear floor; the equities/bonds/T-notes
    # columns are corrected additively and should match the target exactly.
    assert np.allclose(out[:, :3].mean(axis=0), target[:3], atol=1e-9)


def test_constrain_mean_off_does_not_match_exactly():
    """
    Without the option, the sample mean is free to drift from the historical mean
    (sequence-of-return / sample fluctuation is retained).
    """
    frm, to = 1928, 2024
    config = {"method": "vector_ar", "frm": frm, "to": to, "constrain_mean": False}
    model = VARRateModel(config, seed=42)
    out = model.generate(400)

    target = _historical_arith_means(frm, to)
    assert not np.allclose(out[:, :3].mean(axis=0), target[:3], atol=1e-9)


def test_constrain_mean_preserves_spread():
    """
    The correction is a pure shift: the per-column standard deviation should be
    unchanged between constrained and unconstrained runs sharing the same seed.
    """
    frm, to = 1928, 2024
    base = VARRateModel({"method": "vector_ar", "frm": frm, "to": to}, seed=7).generate(300)
    shifted = VARRateModel(
        {"method": "vector_ar", "frm": frm, "to": to, "constrain_mean": True}, seed=7
    ).generate(300)
    # Equities/bonds/T-notes are shifted additively → identical spread.
    assert np.allclose(base[:, :3].std(axis=0), shifted[:, :3].std(axis=0), atol=1e-9)


# ------------------------------------------------------------
# Monte Carlo integration
# ------------------------------------------------------------

def test_runmc_does_not_return_none():
    """
    runMC() should not return None when using the var method.
    The guard in runMC() checks rateModel.deterministic, which is False for var.
    """
    p = _make_plan()
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[200], taxDeferred=[400], taxFree=[100])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    _set_var(p, frm=1928, to=2024)
    result = p.runMC("maxSpending", {}, N=10, figure=False, verbose=False)
    assert result is not None, "runMC() returned None for var method"
