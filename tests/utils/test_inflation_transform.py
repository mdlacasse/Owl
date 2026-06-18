"""
Tests for the PWL inflation normalization transform.

Covers:
- pwl_transform: identity at kink, correct slopes on each side, vectorized
- inv_pwl_transform: exact inverse of pwl_transform
- fit_inflation_transform: kink = median, skewness reduced, slopes positive,
  adapts to different data windows, right-skewed data gets slope_lo > slope_hi

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
from scipy.stats import skew

from owlplanner.rate_models.inflation_transform import (
    fit_inflation_transform,
    inv_pwl_transform,
    pwl_transform,
)


# ---------------------------------------------------------------------------
# pwl_transform
# ---------------------------------------------------------------------------

def test_pwl_transform_at_kink():
    """φ(k) = k regardless of slopes."""
    k, slope_lo, slope_hi = 0.03, 2.5, 0.75
    assert pwl_transform(np.array([k]), k, slope_lo, slope_hi)[0] == pytest.approx(k)


def test_pwl_transform_below_kink():
    """Values below k use slope_lo."""
    k, slope_lo, slope_hi = 0.03, 2.5, 0.75
    z = np.array([0.01])
    expected = (0.01 - k) * slope_lo + k
    assert pwl_transform(z, k, slope_lo, slope_hi)[0] == pytest.approx(expected)


def test_pwl_transform_above_kink():
    """Values above k use slope_hi."""
    k, slope_lo, slope_hi = 0.03, 2.5, 0.75
    z = np.array([0.06])
    expected = (0.06 - k) * slope_hi + k
    assert pwl_transform(z, k, slope_lo, slope_hi)[0] == pytest.approx(expected)


def test_pwl_transform_identity_slopes():
    """With slope_lo = slope_hi = 1, transform is the identity."""
    z = np.linspace(-0.1, 0.15, 50)
    k = 0.03
    np.testing.assert_allclose(pwl_transform(z, k, 1.0, 1.0), z)


def test_pwl_transform_vectorized():
    """Transform handles arrays of arbitrary length correctly."""
    rng = np.random.default_rng(0)
    z = rng.normal(0.03, 0.04, 200)
    k, slope_lo, slope_hi = 0.03, 2.0, 0.8
    w = pwl_transform(z, k, slope_lo, slope_hi)
    assert w.shape == z.shape
    assert np.all(np.isfinite(w))


def test_pwl_transform_monotone():
    """Monotone transform: larger input → larger output."""
    z = np.sort(np.linspace(-0.12, 0.18, 100))
    k, slope_lo, slope_hi = 0.03, 2.5, 0.75
    w = pwl_transform(z, k, slope_lo, slope_hi)
    assert np.all(np.diff(w) >= 0)


# ---------------------------------------------------------------------------
# inv_pwl_transform
# ---------------------------------------------------------------------------

def test_inv_pwl_transform_roundtrip():
    """φ⁻¹(φ(z)) = z for all values."""
    rng = np.random.default_rng(42)
    z = rng.normal(0.03, 0.05, 500)
    k, slope_lo, slope_hi = 0.029, 2.3, 0.8
    np.testing.assert_allclose(
        inv_pwl_transform(pwl_transform(z, k, slope_lo, slope_hi), k, slope_lo, slope_hi),
        z,
        rtol=1e-12,
    )


def test_pwl_transform_roundtrip_forward():
    """φ(φ⁻¹(w)) = w for all values."""
    rng = np.random.default_rng(7)
    w = rng.normal(0.03, 0.07, 500)
    k, slope_lo, slope_hi = 0.029, 2.3, 0.8
    np.testing.assert_allclose(
        pwl_transform(inv_pwl_transform(w, k, slope_lo, slope_hi), k, slope_lo, slope_hi),
        w,
        rtol=1e-12,
    )


def test_inv_pwl_transform_at_kink():
    """φ⁻¹(k) = k."""
    k, slope_lo, slope_hi = 0.029, 2.5, 0.75
    assert inv_pwl_transform(np.array([k]), k, slope_lo, slope_hi)[0] == pytest.approx(k)


# ---------------------------------------------------------------------------
# fit_inflation_transform
# ---------------------------------------------------------------------------

def test_fit_kink_equals_median():
    """Fitted kink point equals the empirical median of the input data."""
    rng = np.random.default_rng(1)
    z = rng.normal(0.03, 0.04, 100)
    k, _, _ = fit_inflation_transform(z)
    assert k == pytest.approx(float(np.median(z)))


def test_fit_slopes_positive():
    """Both fitted slopes are strictly positive."""
    rng = np.random.default_rng(2)
    z = rng.normal(0.03, 0.04, 100)
    _, slope_lo, slope_hi = fit_inflation_transform(z)
    assert slope_lo > 0
    assert slope_hi > 0


def test_fit_reduces_skewness():
    """Skewness of φ(z) is smaller in magnitude than skewness of z for right-skewed data."""
    rng = np.random.default_rng(3)
    # Simulate right-skewed inflation: normal + exponential tail
    z = rng.normal(0.03, 0.03, 300) + rng.exponential(0.02, 300) - 0.02
    original_skew = abs(float(skew(z)))
    k, slope_lo, slope_hi = fit_inflation_transform(z)
    transformed_skew = abs(float(skew(pwl_transform(z, k, slope_lo, slope_hi))))
    assert transformed_skew < original_skew


def test_fit_right_skewed_gives_slope_lo_greater_than_slope_hi():
    """For right-skewed data, slope_lo > slope_hi (stretch left, compress right)."""
    rng = np.random.default_rng(4)
    z = rng.normal(0.03, 0.03, 500) + rng.exponential(0.03, 500) - 0.03
    assert float(skew(z)) > 0, "Test data must be right-skewed"
    _, slope_lo, slope_hi = fit_inflation_transform(z)
    assert slope_lo > slope_hi


def test_fit_symmetric_data_near_identity():
    """For already-symmetric data, fitted slopes are close to 1 (near-identity)."""
    rng = np.random.default_rng(5)
    z = rng.normal(0.03, 0.04, 2000)
    _, slope_lo, slope_hi = fit_inflation_transform(z)
    assert slope_lo == pytest.approx(1.0, abs=0.3)
    assert slope_hi == pytest.approx(1.0, abs=0.3)


def test_fit_adapts_to_different_windows():
    """Fitted slopes differ when the historical window changes."""
    rng = np.random.default_rng(6)
    z1 = rng.normal(0.03, 0.04, 50)
    z2 = rng.normal(0.08, 0.06, 50) + rng.exponential(0.05, 50)
    _, sl1, sh1 = fit_inflation_transform(z1)
    _, sl2, sh2 = fit_inflation_transform(z2)
    # The two windows should produce noticeably different slopes
    assert not (np.isclose(sl1, sl2, atol=0.1) and np.isclose(sh1, sh2, atol=0.1))


def test_fit_uses_actual_historical_inflation():
    """Fit on actual Owl historical inflation data returns plausible slopes."""
    from owlplanner.rates import Inflation
    z = Inflation.iloc[:].to_numpy() / 100.0  # full 1928-2025 window
    k, slope_lo, slope_hi = fit_inflation_transform(z)
    assert k == pytest.approx(float(np.median(z)), rel=1e-6)
    assert slope_lo > 1.0, "Right-skewed inflation should need slope_lo > 1"
    assert slope_hi < slope_lo, "slope_hi should be less than slope_lo for right-skewed data"
    assert 0.1 <= slope_lo <= 10.0
    assert 0.1 <= slope_hi <= 10.0
