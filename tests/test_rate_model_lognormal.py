"""
Tests for the lognormal and histolognormal rate models.

Covers:
- Model attributes (name, flags)
- Output shape and range
- Log-normal property: returns strictly > -1 (no total-loss)
- Reproducibility
- Mean and stdev accuracy (lognormal, histolognormal)
- Correlation handling (lognormal)
- Historical window sensitivity (histolognormal)
- Parameter validation (frm/to bounds, invalid range)
- GaussianRateModel / StochasticRateModel class identity

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
from owlplanner.rate_models.builtin import (LognormalRateModel, HistolognormalRateModel, GaussianRateModel,
                                            StochasticRateModel)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

_MEANS = [7.0, 4.5, 3.5, 2.5]
_STDEV = [17.0, 8.0, 6.0, 2.0]


def _make_plan():
    return Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)


def _make_lognormal(seed=None):
    config = {"method": "lognormal", "values": _MEANS, "stdev": _STDEV}
    return LognormalRateModel(config, seed=seed)


def _make_histolognormal(frm=1928, to=2024, seed=None):
    config = {"method": "histolognormal", "frm": frm, "to": to}
    return HistolognormalRateModel(config, seed=seed)


def _set_lognormal(p, seed=None):
    if seed is not None:
        p.setReproducible(True, seed=seed)
    else:
        p.setReproducible(False)
    p.setRates("lognormal", values=_MEANS, stdev=_STDEV)


def _set_histolognormal(p, frm=1928, to=2024, seed=None):
    if seed is not None:
        p.setReproducible(True, seed=seed)
    else:
        p.setReproducible(False)
    p.setRates("histolognormal", frm=frm, to=to)


# ------------------------------------------------------------
# Model attributes — lognormal
# ------------------------------------------------------------

def test_model_name_lognormal():
    assert LognormalRateModel.model_name == "lognormal"


def test_deterministic_flag_lognormal():
    assert LognormalRateModel.deterministic is False


def test_constant_flag_lognormal():
    assert LognormalRateModel.constant is False


# ------------------------------------------------------------
# Model attributes — histolognormal
# ------------------------------------------------------------

def test_model_name_histolognormal():
    assert HistolognormalRateModel.model_name == "histolognormal"


def test_deterministic_flag_histolognormal():
    assert HistolognormalRateModel.deterministic is False


def test_constant_flag_histolognormal():
    assert HistolognormalRateModel.constant is False


# ------------------------------------------------------------
# Output shape — lognormal
# ------------------------------------------------------------

def test_shape_via_plan_lognormal():
    p = _make_plan()
    _set_lognormal(p)
    assert p.tau_kn.shape == (4, p.N_n)


def test_output_is_finite_lognormal():
    p = _make_plan()
    _set_lognormal(p)
    assert np.all(np.isfinite(p.tau_kn))


def test_generate_shape_direct_lognormal():
    model = _make_lognormal(seed=42)
    out = model.generate(30)
    assert out.shape == (30, 4)


def test_rates_bounded_below_lognormal():
    """Log-normal property: all returns strictly > -1.0 (no total-loss)."""
    model = _make_lognormal(seed=0)
    out = model.generate(500)
    assert np.all(out > -1.0), "Some log-normal returns below -100%"


def test_rates_in_plausible_range_lognormal():
    model = _make_lognormal(seed=0)
    out = model.generate(500)
    assert np.all(out > -1.0), "Some returns below -100%"
    assert np.all(out < 2.0), "Some returns above +200%"


# ------------------------------------------------------------
# Output shape — histolognormal
# ------------------------------------------------------------

def test_shape_via_plan_histolognormal():
    p = _make_plan()
    _set_histolognormal(p)
    assert p.tau_kn.shape == (4, p.N_n)


def test_output_is_finite_histolognormal():
    p = _make_plan()
    _set_histolognormal(p)
    assert np.all(np.isfinite(p.tau_kn))


def test_generate_shape_direct_histolognormal():
    model = _make_histolognormal(seed=42)
    out = model.generate(30)
    assert out.shape == (30, 4)


def test_rates_bounded_below_histolognormal():
    """Log-normal property: all returns strictly > -1.0."""
    model = _make_histolognormal(seed=0)
    out = model.generate(500)
    assert np.all(out > -1.0), "Some histolognormal returns below -100%"


def test_rates_in_plausible_range_histolognormal():
    model = _make_histolognormal(seed=0)
    out = model.generate(500)
    assert np.all(out > -1.0), "Some returns below -100%"
    assert np.all(out < 2.0), "Some returns above +200%"


# ------------------------------------------------------------
# Reproducibility — lognormal
# ------------------------------------------------------------

def test_reproducible_same_seed_lognormal():
    p1 = _make_plan()
    _set_lognormal(p1, seed=42)
    p2 = _make_plan()
    _set_lognormal(p2, seed=42)
    assert np.allclose(p1.tau_kn, p2.tau_kn)


def test_different_seeds_differ_lognormal():
    p1 = _make_plan()
    _set_lognormal(p1, seed=1)
    p2 = _make_plan()
    _set_lognormal(p2, seed=2)
    assert not np.allclose(p1.tau_kn, p2.tau_kn)


def test_non_reproducible_regen_changes_lognormal():
    p = _make_plan()
    _set_lognormal(p)
    tau1 = p.tau_kn.copy()
    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()
    assert not np.allclose(tau1, tau2)


# ------------------------------------------------------------
# Reproducibility — histolognormal
# ------------------------------------------------------------

def test_reproducible_same_seed_histolognormal():
    p1 = _make_plan()
    _set_histolognormal(p1, seed=42)
    p2 = _make_plan()
    _set_histolognormal(p2, seed=42)
    assert np.allclose(p1.tau_kn, p2.tau_kn)


def test_different_seeds_differ_histolognormal():
    p1 = _make_plan()
    _set_histolognormal(p1, seed=1)
    p2 = _make_plan()
    _set_histolognormal(p2, seed=2)
    assert not np.allclose(p1.tau_kn, p2.tau_kn)


def test_non_reproducible_regen_changes_histolognormal():
    p = _make_plan()
    _set_histolognormal(p)
    tau1 = p.tau_kn.copy()
    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()
    assert not np.allclose(tau1, tau2)


# ------------------------------------------------------------
# Mean accuracy — lognormal
# ------------------------------------------------------------

def test_lognormal_mean_approx():
    """
    Over a large sample, the sample arithmetic mean should be close
    to the specified arithmetic means.
    """
    rng = np.random.default_rng(0)
    means = np.array(_MEANS) / 100.0
    from owlplanner.rate_models._builtin_impl import generate_lognormal_series
    series, _, _, _ = generate_lognormal_series(10000, _MEANS, _STDEV, rng=rng)
    sample_means = series.mean(axis=0)
    # Within 1% absolute (loose tolerance for large-N Monte Carlo)
    np.testing.assert_allclose(sample_means, means, atol=0.01,
                               err_msg="Sample means deviate too far from specified arithmetic means")


def test_lognormal_stdev_approx():
    """
    Over a large sample, the sample arithmetic standard deviation should be
    close to the specified standard deviations.
    """
    rng = np.random.default_rng(123)
    stdev_decimal = np.array(_STDEV) / 100.0
    from owlplanner.rate_models._builtin_impl import generate_lognormal_series
    series, _, _, _ = generate_lognormal_series(15000, _MEANS, _STDEV, rng=rng)
    sample_stdev = series.std(axis=0)
    # Within 1.5% absolute (loose tolerance for Monte Carlo variance of variance)
    np.testing.assert_allclose(sample_stdev, stdev_decimal, atol=0.015,
                               err_msg="Sample stdevs deviate too far from specified standard deviations")


def test_lognormal_with_correlation():
    """
    Lognormal model with non-identity correlation matrix produces valid
    output and preserves positive correlation in log-space.
    """
    # Positive correlation between assets 0 and 1
    corr_upper = [0.3, 0.1, 0.0, 0.2, 0.1, 0.15]  # 6 off-diagonals for 4x4
    config = {"method": "lognormal", "values": _MEANS, "stdev": _STDEV, "corr": corr_upper}
    model = LognormalRateModel(config, seed=7)
    out = model.generate(500)
    assert out.shape == (500, 4)
    assert np.all(np.isfinite(out))
    assert np.all(out > -1.0), "Some returns below -100%"
    # Log-returns should show positive correlation between assets 0 and 1
    log_returns = np.log(1.0 + out)
    sample_corr = np.corrcoef(log_returns.T)
    assert sample_corr[0, 1] > 0.1, "Expected positive correlation in log-space for assets 0 and 1"


# ------------------------------------------------------------
# Moment accuracy — histolognormal
# ------------------------------------------------------------

def test_histolognormal_mean_approx():
    """
    Over a large sample, the sample arithmetic mean should be close
    to the fitted arithmetic mean from the historical log-space fit.
    """
    from owlplanner.rate_models._builtin_impl import generate_histolognormal_series
    rng = np.random.default_rng(77)
    series, means, _, _ = generate_histolognormal_series(15000, 1928, 2024, rng=rng)
    sample_means = series.mean(axis=0)
    np.testing.assert_allclose(sample_means, means, atol=0.01,
                               err_msg="Sample means deviate too far from fitted arithmetic means")


def test_histolognormal_stdev_approx():
    """
    Over a large sample, the sample arithmetic standard deviation should be
    close to the fitted arithmetic standard deviation from the historical fit.
    """
    from owlplanner.rate_models._builtin_impl import generate_histolognormal_series
    rng = np.random.default_rng(88)
    series, _, stdev, _ = generate_histolognormal_series(15000, 1928, 2024, rng=rng)
    sample_stdev = series.std(axis=0)
    np.testing.assert_allclose(sample_stdev, stdev, atol=0.015,
                               err_msg="Sample stdevs deviate too far from fitted standard deviations")


# ------------------------------------------------------------
# Historical window sensitivity — histolognormal
# ------------------------------------------------------------

def test_histolognormal_different_windows_differ():
    p1 = _make_plan()
    _set_histolognormal(p1, frm=1928, to=1970, seed=7)
    p2 = _make_plan()
    _set_histolognormal(p2, frm=1980, to=2024, seed=7)
    assert not np.allclose(p1.tau_kn, p2.tau_kn)


# ------------------------------------------------------------
# Parameter validation — histolognormal
# ------------------------------------------------------------

def test_invalid_frm_to_raises_histolognormal():
    """frm >= to should raise ValueError."""
    config = {"method": "histolognormal", "frm": 2000, "to": 2000}
    with pytest.raises(ValueError):
        HistolognormalRateModel(config)


def test_histolognormal_frm_out_of_bounds_raises():
    """frm before valid historical range should raise ValueError."""
    from owlplanner.rates import FROM
    config = {"method": "histolognormal", "frm": FROM - 10, "to": FROM + 5}
    with pytest.raises(ValueError):
        HistolognormalRateModel(config)


# ------------------------------------------------------------
# Backward compatibility
# ------------------------------------------------------------

def test_gaussian_alias():
    """GaussianRateModel is the primary class; StochasticRateModel is an alias."""
    assert StochasticRateModel is GaussianRateModel


def test_gaussian_method_produces_valid_output():
    """method='gaussian' produces valid output via setRates."""
    p = _make_plan()
    p.setReproducible(False)
    p.setRates("gaussian", values=_MEANS, stdev=_STDEV)
    assert p.tau_kn.shape == (4, p.N_n)
    assert np.all(np.isfinite(p.tau_kn))
