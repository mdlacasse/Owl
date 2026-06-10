"""
Piecewise-linear normalization transform for inflation rates.

Historical inflation is right-skewed (long tail from high-inflation episodes).
Models that assume Gaussian residuals — historical_gaussian, historical_lognormal,
vector_ar, garch_dcc — violate this assumption.

φ(z) stretches the left tail and compresses the right tail so the distribution
is closer to Gaussian before fitting. φ⁻¹ recovers actual inflation values from
generated samples.

    φ(z)  = (z − k) · slope_lo + k    for z ≤ k
    φ(z)  = (z − k) · slope_hi + k    for z > k

The kink point k is the empirical median; slope_lo and slope_hi are auto-fit
to minimize skewness² + excess-kurtosis² of the transformed values.
"""

import numpy as np
from scipy.optimize import minimize
from scipy.stats import skew


def fit_inflation_transform(z: np.ndarray) -> tuple[float, float, float]:
    """
    Fit (k, slope_lo, slope_hi) to minimize skewness of φ(z).

    Minimizes skewness² with a small regularization toward the identity (slopes = 1)
    to select a unique, low-distortion solution when many slope pairs zero out skewness.

    Parameters
    ----------
    z : 1-D array
        Inflation values in the space where Gaussianity is desired (return space for
        historical_gaussian / vector_ar / garch_dcc; log-return space for
        historical_lognormal).

    Returns
    -------
    k : float
        Kink point (empirical median of z).
    slope_lo : float
        Slope below the median.
    slope_hi : float
        Slope above the median.
    """
    z = np.asarray(z, dtype=float)
    k = float(np.median(z))

    def obj(params: np.ndarray) -> float:
        slope_lo, slope_hi = params
        w = pwl_transform(z, k, slope_lo, slope_hi)
        # Minimize skewness; regularize toward identity to get unique minimum
        return float(skew(w) ** 2 + 0.1 * ((slope_lo - 1.0) ** 2 + (slope_hi - 1.0) ** 2))

    result = minimize(
        obj,
        x0=[2.0, 0.75],
        bounds=[(0.1, 10.0), (0.1, 10.0)],
        method="L-BFGS-B",
    )
    slope_lo, slope_hi = result.x
    return k, float(slope_lo), float(slope_hi)


def pwl_transform(z: np.ndarray, k: float, slope_lo: float, slope_hi: float) -> np.ndarray:
    """Apply the PWL normalization transform to inflation values."""
    z = np.asarray(z, dtype=float)
    return np.where(z <= k, (z - k) * slope_lo + k, (z - k) * slope_hi + k)


def inv_pwl_transform(w: np.ndarray, k: float, slope_lo: float, slope_hi: float) -> np.ndarray:
    """Invert the PWL normalization transform to recover actual inflation values."""
    w = np.asarray(w, dtype=float)
    return np.where(w <= k, (w - k) / slope_lo + k, (w - k) / slope_hi + k)
