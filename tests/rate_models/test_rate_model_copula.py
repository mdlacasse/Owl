"""
Tests for the historical_copula rate model (Gaussian copula).

Covers:
- Model attributes (name, flags)
- Output shape and finiteness
- Inflation floor: no generated inflation below INFLATION_FLOOR
- Marginal bounds: no extrapolation beyond the historical [min, max] per asset
- Correlation preservation: generated rank correlations close to historical
- Marginal statistics: sample means and stdevs close to historical
- Reproducibility via Plan.setReproducible and direct seed
- Historical window sensitivity
- Parameter validation (frm/to bounds, invalid range)
- Constants sanity (INFLATION_FLOOR type and value)

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

import numpy as np
import pytest

from owlplanner import Plan
from owlplanner.rate_models.copula import HistoCopulaRateModel, generate_histocopula_series
from owlplanner.rate_models._builtin_impl import INFLATION_FLOOR, FROM, TO
from owlplanner.rates import SP500, BondsBaa, TNotes, Inflation


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------


def _make_plan():
    return Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)


def _make_copula(frm=FROM, to=TO, seed=None):
    config = {"method": "historical_copula", "frm": frm, "to": to}
    return HistoCopulaRateModel(config, seed=seed)


def _set_copula(p, frm=FROM, to=TO, seed=None):
    if seed is not None:
        p.setReproducible(True, seed=seed)
    else:
        p.setReproducible(False)
    p.setRates("historical_copula", frm=frm, to=to)


def _historical_bounds(frm=FROM, to=TO):
    """Return (min, max) per asset from the historical window."""
    ifrm = frm - FROM
    ito = to - FROM
    arrays = [SP500, BondsBaa, TNotes, Inflation]
    lo = np.array([a.iloc[ifrm : ito + 1].to_numpy().min() / 100.0 for a in arrays])
    hi = np.array([a.iloc[ifrm : ito + 1].to_numpy().max() / 100.0 for a in arrays])
    return lo, hi


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------


def test_inflation_floor_is_negative():
    assert INFLATION_FLOOR < 0.0


def test_inflation_floor_is_reasonable():
    assert -0.20 < INFLATION_FLOOR < 0.0, "Floor should be between -20% and 0%"


# ------------------------------------------------------------
# Model attributes
# ------------------------------------------------------------


def test_model_name():
    assert HistoCopulaRateModel.model_name == "historical_copula"


def test_deterministic_flag():
    assert HistoCopulaRateModel.deterministic is False


def test_constant_flag():
    assert HistoCopulaRateModel.constant is False


# ------------------------------------------------------------
# Output shape and finiteness
# ------------------------------------------------------------


def test_shape_via_plan():
    p = _make_plan()
    _set_copula(p)
    assert p.tau_kn.shape == (4, p.N_n)


def test_output_is_finite_via_plan():
    p = _make_plan()
    _set_copula(p)
    assert np.all(np.isfinite(p.tau_kn))


def test_generate_shape_direct():
    model = _make_copula(seed=42)
    out = model.generate(30)
    assert out.shape == (30, 4)


def test_generate_shape_large():
    rng = np.random.default_rng(0)
    series, _, _, _ = generate_histocopula_series(2000, FROM, TO, rng)
    assert series.shape == (2000, 4)


def test_output_is_finite():
    rng = np.random.default_rng(0)
    series, _, _, _ = generate_histocopula_series(500, FROM, TO, rng)
    assert np.all(np.isfinite(series))


# ------------------------------------------------------------
# Inflation floor
# ------------------------------------------------------------


def test_inflation_floor_enforced_direct():
    """Generated inflation must never fall below INFLATION_FLOOR."""
    rng = np.random.default_rng(7)
    series, _, _, _ = generate_histocopula_series(5000, FROM, TO, rng)
    assert np.all(series[:, 3] >= INFLATION_FLOOR), (
        f"Some inflation samples below floor {INFLATION_FLOOR:.2%}: min={series[:, 3].min():.4f}"
    )


def test_inflation_floor_enforced_via_plan():
    """Inflation floor holds on the tau_kn series used by Plan."""
    p = _make_plan()
    _set_copula(p, seed=3)
    assert np.all(p.tau_kn[3] >= INFLATION_FLOOR)


def test_inflation_floor_enforced_short_window():
    """Floor applies even on a short historical window that includes Great Depression."""
    rng = np.random.default_rng(99)
    series, _, _, _ = generate_histocopula_series(2000, 1928, 1950, rng)
    assert np.all(series[:, 3] >= INFLATION_FLOOR)


# ------------------------------------------------------------
# Marginal bounds: no extrapolation beyond historical [min, max]
# ------------------------------------------------------------


def test_marginals_bounded_by_history():
    """All generated values must lie within the historical [min, max] for each asset."""
    lo, hi = _historical_bounds()
    # Apply floor to inflation's lower bound (the floor replaces the historical min)
    lo[3] = INFLATION_FLOOR
    rng = np.random.default_rng(42)
    series, _, _, _ = generate_histocopula_series(3000, FROM, TO, rng)
    for k, name in enumerate(["S&P 500", "Bonds Baa", "T-Notes", "Inflation"]):
        assert np.all(series[:, k] >= lo[k] - 1e-9), (
            f"{name}: generated min {series[:, k].min():.4f} below historical min {lo[k]:.4f}"
        )
        assert np.all(series[:, k] <= hi[k] + 1e-9), (
            f"{name}: generated max {series[:, k].max():.4f} above historical max {hi[k]:.4f}"
        )


# ------------------------------------------------------------
# Correlation preservation
# ------------------------------------------------------------


def test_correlation_preserved():
    """Generated rank correlations should be close to historical rank correlations."""
    from scipy.stats import spearmanr

    ifrm, ito = FROM - FROM, TO - FROM
    hist_data = np.column_stack(
        [
            SP500.iloc[ifrm : ito + 1].to_numpy() / 100.0,
            BondsBaa.iloc[ifrm : ito + 1].to_numpy() / 100.0,
            TNotes.iloc[ifrm : ito + 1].to_numpy() / 100.0,
            Inflation.iloc[ifrm : ito + 1].to_numpy() / 100.0,
        ]
    )
    hist_corr = spearmanr(hist_data).statistic  # (4, 4)

    rng = np.random.default_rng(5)
    series, _, _, _ = generate_histocopula_series(10000, FROM, TO, rng)
    gen_corr = spearmanr(series).statistic  # (4, 4)

    # Allow up to 0.10 absolute deviation on any rank-correlation pair
    np.testing.assert_allclose(
        gen_corr, hist_corr, atol=0.10, err_msg="Generated rank correlations deviate too far from historical"
    )


# ------------------------------------------------------------
# Marginal statistics
# ------------------------------------------------------------


def test_mean_close_to_historical():
    """Generated arithmetic means should be close to historical means (large N)."""
    ifrm, ito = FROM - FROM, TO - FROM
    hist_data = np.column_stack(
        [
            SP500.iloc[ifrm : ito + 1].to_numpy() / 100.0,
            BondsBaa.iloc[ifrm : ito + 1].to_numpy() / 100.0,
            TNotes.iloc[ifrm : ito + 1].to_numpy() / 100.0,
            Inflation.iloc[ifrm : ito + 1].to_numpy() / 100.0,
        ]
    )
    hist_means = hist_data.mean(axis=0)

    rng = np.random.default_rng(11)
    series, means_meta, _, _ = generate_histocopula_series(15000, FROM, TO, rng)

    # Metadata means should equal historical means exactly
    np.testing.assert_allclose(
        means_meta, hist_means, atol=1e-12, err_msg="Metadata means do not match historical means"
    )

    # Sample means from 15k draws should be within 1% of historical
    np.testing.assert_allclose(
        series.mean(axis=0), hist_means, atol=0.01, err_msg="Sample means deviate too far from historical means"
    )


def test_stdev_close_to_historical():
    """Generated standard deviations should be close to historical stdevs (large N)."""
    ifrm, ito = FROM - FROM, TO - FROM
    hist_data = np.column_stack(
        [
            SP500.iloc[ifrm : ito + 1].to_numpy() / 100.0,
            BondsBaa.iloc[ifrm : ito + 1].to_numpy() / 100.0,
            TNotes.iloc[ifrm : ito + 1].to_numpy() / 100.0,
            Inflation.iloc[ifrm : ito + 1].to_numpy() / 100.0,
        ]
    )
    hist_stdev = hist_data.std(axis=0, ddof=1)

    rng = np.random.default_rng(22)
    series, _, stdev_meta, _ = generate_histocopula_series(15000, FROM, TO, rng)

    # Metadata stdev should equal historical stdev exactly
    np.testing.assert_allclose(
        stdev_meta, hist_stdev, atol=1e-12, err_msg="Metadata stdevs do not match historical stdevs"
    )

    # Sample stdevs within 1.5% of historical (Monte Carlo variance of variance)
    # Exclude inflation since clipping at floor reduces its variance slightly
    np.testing.assert_allclose(
        series[:, :3].std(axis=0),
        hist_stdev[:3],
        atol=0.015,
        err_msg="Sample stdevs (non-inflation) deviate too far from historical",
    )


# ------------------------------------------------------------
# Reproducibility
# ------------------------------------------------------------


def test_reproducible_same_seed():
    p1 = _make_plan()
    _set_copula(p1, seed=42)
    p2 = _make_plan()
    _set_copula(p2, seed=42)
    assert np.allclose(p1.tau_kn, p2.tau_kn)


def test_different_seeds_differ():
    p1 = _make_plan()
    _set_copula(p1, seed=1)
    p2 = _make_plan()
    _set_copula(p2, seed=2)
    assert not np.allclose(p1.tau_kn, p2.tau_kn)


def test_non_reproducible_regen_changes():
    p = _make_plan()
    _set_copula(p)
    tau1 = p.tau_kn.copy()
    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()
    assert not np.allclose(tau1, tau2)


def test_direct_model_seed_reproducible():
    m1 = _make_copula(seed=7)
    m2 = _make_copula(seed=7)
    assert np.allclose(m1.generate(50), m2.generate(50))


# ------------------------------------------------------------
# Historical window sensitivity
# ------------------------------------------------------------


def test_different_windows_differ():
    p1 = _make_plan()
    _set_copula(p1, frm=1928, to=1970, seed=7)
    p2 = _make_plan()
    _set_copula(p2, frm=1980, to=TO, seed=7)
    assert not np.allclose(p1.tau_kn, p2.tau_kn)


def test_post_1950_window_respects_floor():
    """With a post-1950 window the historical min inflation is mild; floor still holds."""
    rng = np.random.default_rng(55)
    series, _, _, _ = generate_histocopula_series(2000, 1950, TO, rng)
    assert np.all(series[:, 3] >= INFLATION_FLOOR)


# ------------------------------------------------------------
# Parameter validation
# ------------------------------------------------------------


def test_invalid_frm_equal_to_raises():
    config = {"method": "historical_copula", "frm": 2000, "to": 2000}
    with pytest.raises(ValueError):
        HistoCopulaRateModel(config)


def test_invalid_frm_greater_than_to_raises():
    config = {"method": "historical_copula", "frm": 2010, "to": 2000}
    with pytest.raises(ValueError):
        HistoCopulaRateModel(config)


def test_frm_out_of_bounds_raises():
    config = {"method": "historical_copula", "frm": FROM - 10, "to": FROM + 5}
    with pytest.raises(ValueError):
        HistoCopulaRateModel(config)


def test_to_out_of_bounds_raises():
    config = {"method": "historical_copula", "frm": FROM, "to": TO + 10}
    with pytest.raises(ValueError):
        HistoCopulaRateModel(config)


def test_window_too_short_raises():
    """T=2 window must be rejected — tied values would produce NaN in Rho."""
    config = {"method": "historical_copula", "frm": 1952, "to": 1953}
    with pytest.raises(ValueError, match="at least 3"):
        HistoCopulaRateModel(config)


def test_seed_in_config_makes_rng_deterministic():
    """rate_seed in config must be stored as self.seed (used by stresstests to reset _rng)."""
    m1 = HistoCopulaRateModel({"method": "historical_copula", "frm": FROM, "to": TO, "rate_seed": 42})
    m2 = HistoCopulaRateModel({"method": "historical_copula", "frm": FROM, "to": TO, "rate_seed": 42})
    assert np.allclose(m1.generate(50), m2.generate(50)), "Same rate_seed must give same output"
    assert m1.seed == 42, f"self.seed should be 42, got {m1.seed}"


# ------------------------------------------------------------
# Integration: Plan.setRates with method string
# ------------------------------------------------------------


def test_setrates_string_method():
    """Plan.setRates('historical_copula') should work and produce valid tau_kn."""
    p = _make_plan()
    p.setReproducible(False)
    p.setRates("historical_copula", frm=FROM, to=TO)
    assert p.tau_kn.shape == (4, p.N_n)
    assert np.all(np.isfinite(p.tau_kn))
    assert np.all(p.tau_kn[3] >= INFLATION_FLOOR)
