"""
Implementation helpers for built-in rate models.

Extracted from the legacy Rates class. Used by BuiltinRateModel to generate
rate series without depending on Rates.setMethod.

Copyright (C) 2025-2026 The Owl Authors
"""
from __future__ import annotations

import functools
import os
import sys

import numpy as np
import pandas as pd

from owlplanner.rate_models.constants import REQUIRED_RATE_COLUMNS
from owlplanner.rate_models.inflation_transform import fit_inflation_transform, inv_pwl_transform, pwl_transform
from owlplanner.rates import (
    FROM,
    TO,
    BondsBaa,
    Inflation,
    SP500,
    TNotes,
    getRatesDistributions,
)


@functools.lru_cache(maxsize=None)
def load_historical_slice(frm: int, to: int):
    """Return (data_decimal, years) for the given year range, cached by (frm, to)."""
    where = os.path.dirname(sys.modules["owlplanner"].__file__)
    file = os.path.join(where, "data/rates.csv")
    df = pd.read_csv(file)
    if "year" not in df.columns:
        raise ValueError("Historical rates.csv must contain a 'year' column.")
    mask = (df["year"] >= frm) & (df["year"] <= to)
    df_slice = df.loc[mask]
    if df_slice.empty:
        raise ValueError(f"No historical data in range [{frm}, {to}].")
    data = df_slice[list(REQUIRED_RATE_COLUMNS)].values.astype(float) / 100.0
    years = df_slice["year"].values
    return data, years


def _validate_historical_range(frm: int, to: int) -> None:
    if not (FROM <= frm <= TO):
        raise ValueError(f"frm={frm} out of range [{FROM}, {TO}].")
    if not (FROM <= to <= TO):
        raise ValueError(f"to={to} out of range [{FROM}, {TO}].")
    if frm >= to:
        raise ValueError(f"frm={frm} must be less than to={to}.")
    if to - frm < 2:
        raise ValueError(f"Window [{frm}, {to}] has only {to - frm + 1} years; need at least 3.")


def _build_corr_matrix(corr, Nk: int = 4) -> np.ndarray:
    """
    Build full correlation matrix from user input.

    Accepts:
        - Full (Nk, Nk) matrix
        - Upper-triangle off-diagonals as 1d array of length Nk*(Nk-1)//2

    Returns:
        Symmetric (Nk, Nk) correlation matrix.
    """
    corrarr = np.array(corr)
    if corrarr.shape == (Nk, Nk):
        if not np.allclose(corrarr, corrarr.T):
            raise ValueError("Correlation matrix must be symmetric.")
        return corrarr
    if corrarr.shape == ((Nk * (Nk - 1)) // 2,):
        newcorr = np.identity(Nk)
        x = 0
        for i in range(Nk):
            for j in range(i + 1, Nk):
                newcorr[i, j] = corrarr[x]
                newcorr[j, i] = corrarr[x]
                x += 1
        return newcorr
    raise RuntimeError(f"Unable to process correlation shape of {corrarr.shape}.")


def _build_covar(stdev: np.ndarray, corr: np.ndarray) -> np.ndarray:
    """Build covariance matrix from standard deviations and correlation matrix."""
    covar = corr * stdev
    covar = covar.T * stdev
    return covar


def constrain_series_mean(series: np.ndarray, target_means: np.ndarray) -> np.ndarray:
    """
    Shift a generated rate series so its arithmetic mean matches target_means.

    Additive correction per asset column: series += (target - sample_mean).
    Preserves the shape (variance, skew, autocorrelation) of the distribution.
    Callers must apply return floors after this function (see apply_return_floors).

    Args:
        series: (N, 4) array of annual returns in decimal.
        target_means: (4,) array of target arithmetic means in decimal.

    Returns:
        Shifted (N, 4) array with no floor applied.
    """
    return series + (target_means - series.mean(axis=0))


def apply_return_floors(series: np.ndarray) -> np.ndarray:
    """
    Apply minimum-return floors to a generated rate series.

    Equity, bonds, and T-notes (cols 0-2) are floored at -1.0 (total loss = -100%).
    Inflation (col 3) is floored at INFLATION_FLOOR.
    Must be called as the final step of every generate() method.

    Args:
        series: (N, 4) array of annual returns in decimal.

    Returns:
        Series with floors applied (in-place modification, same array returned).
    """
    series[:, :3] = np.maximum(series[:, :3], -1.0)
    series[:, 3] = np.maximum(series[:, 3], INFLATION_FLOOR)
    return series


def _historical_arith_means(frm: int, to: int) -> np.ndarray:
    """Return the arithmetic mean of historical returns for the given window (decimal)."""
    if not (FROM <= frm <= TO):
        raise ValueError(f"Lower range 'frm={frm}' out of bounds.")
    if not (FROM <= to <= TO):
        raise ValueError(f"Upper range 'to={to}' out of bounds.")
    ifrm = frm - FROM
    ito = to - FROM
    data = np.column_stack([
        SP500.iloc[ifrm:ito + 1].to_numpy() / 100.0,
        BondsBaa.iloc[ifrm:ito + 1].to_numpy() / 100.0,
        TNotes.iloc[ifrm:ito + 1].to_numpy() / 100.0,
        Inflation.iloc[ifrm:ito + 1].to_numpy() / 100.0,
    ])
    return data.mean(axis=0)


def generate_fixed_series(
    N: int,
    rates_decimal: np.ndarray,
) -> np.ndarray:
    """
    Generate Nx4 rate series with constant rates (repeated each year).

    Args:
        N: Number of years
        rates_decimal: Array of 4 rates in decimal

    Returns:
        (N, 4) array of rates in decimal
    """
    return np.tile(rates_decimal, (N, 1))


def generate_historical_series(
    N: int,
    frm: int,
    to: int,
) -> np.ndarray:
    """
    Generate Nx4 rate series from historical data, repeating modulo span.

    Args:
        N: Number of years
        frm: Start year (inclusive)
        to: End year (inclusive)

    Returns:
        (N, 4) array of rates in decimal
    """
    if not (FROM <= frm <= TO):
        raise ValueError(f"Lower range 'frm={frm}' out of bounds.")
    if not (FROM <= to <= TO):
        raise ValueError(f"Upper range 'to={to}' out of bounds.")
    if frm >= to:
        raise ValueError("Unacceptable range.")
    ifrm = frm - FROM
    ito = to - FROM
    span = ito - ifrm + 1

    rate_series = np.zeros((N, 4))
    for n in range(N):
        idx = ifrm + (n % span)
        rate_series[n, 0] = SP500.iloc[idx] / 100.0
        rate_series[n, 1] = BondsBaa.iloc[idx] / 100.0
        rate_series[n, 2] = TNotes.iloc[idx] / 100.0
        rate_series[n, 3] = Inflation.iloc[idx] / 100.0

    return rate_series


def generate_historical_average_series(
    N: int,
    frm: int,
    to: int,
    mylog=None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Nx4 fixed series from historical geometric mean, and return distribution params.

    Uses geometric means as the fixed rates: the constant annual return that
    replicates the same compound growth as the historical window.

    Returns:
        (rate_series, means, stdev, corr) - series in decimal, geometric params for metadata
    """
    dist = getRatesDistributions(frm, to, mylog, in_percent=False)
    rate_series = np.tile(dist.geo_means, (N, 1))
    return rate_series, dist.geo_means, dist.stdev, dist.corr


def generate_histogaussian_series(
    N: int,
    frm: int,
    to: int,
    rng: np.random.Generator,
    mylog=None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Nx4 stochastic series from historical distribution params.

    Uses the arithmetic mean of historical returns as the Gaussian center, with
    sample covariance computed from the same window. This is the standard
    maximum-likelihood fit of a multivariate normal to the historical data.

    Inflation (dimension 3) is pre-processed with a PWL normalization transform
    φ before fitting to correct for right-skew, then φ⁻¹ is applied to generated
    samples so outputs remain in actual inflation units.

    Returns:
        (rate_series, means, stdev, corr) - series in decimal, arithmetic params for metadata
    """
    if not (FROM <= frm <= TO):
        raise ValueError(f"Lower range 'frm={frm}' out of bounds.")
    if not (FROM <= to <= TO):
        raise ValueError(f"Upper range 'to={to}' out of bounds.")
    if frm >= to:
        raise ValueError("Unacceptable range.")

    ifrm = frm - FROM
    ito = to - FROM
    data = np.column_stack([
        SP500.iloc[ifrm:ito + 1].to_numpy() / 100.0,
        BondsBaa.iloc[ifrm:ito + 1].to_numpy() / 100.0,
        TNotes.iloc[ifrm:ito + 1].to_numpy() / 100.0,
        Inflation.iloc[ifrm:ito + 1].to_numpy() / 100.0,
    ])

    # Metadata from original data for UI display
    orig_means = data.mean(axis=0)
    orig_stdev = np.std(data, axis=0, ddof=1)
    orig_corr = np.corrcoef(data.T)

    # PWL transform on inflation (dim 3) to correct right-skew before fitting
    k, slope_lo, slope_hi = fit_inflation_transform(data[:, 3])
    if mylog:
        mylog.vprint(f"histogaussian inflation PWL: k={k:.4f}, slope_lo={slope_lo:.4f}, slope_hi={slope_hi:.4f}")
    data_t = data.copy()
    data_t[:, 3] = pwl_transform(data[:, 3], k, slope_lo, slope_hi)

    arith_means = data_t.mean(axis=0)
    covar = np.cov(data_t.T)
    rate_series = rng.multivariate_normal(arith_means, covar, size=N)

    # Invert inflation transform on generated samples
    rate_series[:, 3] = inv_pwl_transform(rate_series[:, 3], k, slope_lo, slope_hi)
    rate_series[:, 3] = np.maximum(rate_series[:, 3], INFLATION_FLOOR)

    return rate_series, orig_means, orig_stdev, orig_corr


def generate_lognormal_series(
    N: int,
    values_pct: list[float] | np.ndarray,
    stdev_pct: list[float] | np.ndarray,
    corr=None,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Nx4 log-normal rate series from user-specified arithmetic mean and volatility.

    Converts arithmetic (mean, std) to log-space parameters, then samples from
    a multivariate normal in log-space and exponentiates: R = exp(Z) - 1.

    Args:
        N: Number of years
        values_pct: Arithmetic mean returns in percent (length 4)
        stdev_pct: Arithmetic standard deviations in percent (length 4)
        corr: Correlation matrix (4x4) or off-diagonal list (6). None = identity.
        rng: Random generator. If None, uses default_rng().

    Returns:
        (rate_series, means, stdev, corr) - series in decimal, params for metadata
    """
    if rng is None:
        rng = np.random.default_rng()

    means = np.array(values_pct, dtype=float) / 100.0
    stdev = np.array(stdev_pct, dtype=float) / 100.0

    if np.any(stdev < 0):
        raise ValueError(
            "Lognormal model requires non-negative standard deviations. "
            f"Got stdev in percent: {np.array(stdev_pct).tolist()}"
        )
    if np.any(means <= -1.0):
        raise ValueError(
            "Lognormal model requires mean returns > -100% (1 + mean > 0). "
            f"Got means in percent: {np.array(values_pct).tolist()}"
        )

    # Convert arithmetic parameters to log-space
    sigma_z2 = np.log(1.0 + (stdev / (1.0 + means)) ** 2)
    mu_z = np.log(1.0 + means) - sigma_z2 / 2.0
    sigma_z = np.sqrt(sigma_z2)

    if corr is None:
        corr_matrix = np.identity(4)
    else:
        corr_matrix = _build_corr_matrix(corr)

    Sigma_z = _build_covar(sigma_z, corr_matrix)
    Z = rng.multivariate_normal(mu_z, Sigma_z, size=N)
    rate_series = np.exp(Z) - 1.0

    return rate_series, means, stdev, corr_matrix


def generate_histolognormal_series(
    N: int,
    frm: int,
    to: int,
    rng: np.random.Generator,
    mylog=None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Nx4 log-normal series fitted to a historical window.

    Computes log-returns from history, estimates log-space mean and covariance
    directly, then samples from a multivariate normal and exponentiates.

    Returns:
        (rate_series, means, stdev, corr) - series in decimal, arithmetic params for metadata

    Note:
        If any historical return is exactly -100% (decimal -1.0), log(1 + r) = -inf
        and the model will produce invalid results. This is extremely rare in
        real historical data.
    """
    # Re-load raw historical data to compute log-returns
    if not (FROM <= frm <= TO):
        raise ValueError(f"Lower range 'frm={frm}' out of bounds.")
    if not (FROM <= to <= TO):
        raise ValueError(f"Upper range 'to={to}' out of bounds.")
    if frm >= to:
        raise ValueError("Unacceptable range.")

    ifrm = frm - FROM
    ito = to - FROM
    data = np.column_stack([
        SP500.iloc[ifrm:ito + 1].to_numpy() / 100.0,
        BondsBaa.iloc[ifrm:ito + 1].to_numpy() / 100.0,
        TNotes.iloc[ifrm:ito + 1].to_numpy() / 100.0,
        Inflation.iloc[ifrm:ito + 1].to_numpy() / 100.0,
    ])

    lr = np.log(1.0 + data)            # log-returns, shape (T, 4)

    # PWL transform on inflation LOG-RETURNS (dim 3) to correct skew before Gaussian fit.
    # Applied in log-space: no log(1 + .) domain constraint needed.
    k, slope_lo, slope_hi = fit_inflation_transform(lr[:, 3])
    if mylog:
        mylog.vprint(f"histolognormal inflation PWL: k={k:.4f}, slope_lo={slope_lo:.4f}, slope_hi={slope_hi:.4f}")
    lr_t = lr.copy()
    lr_t[:, 3] = pwl_transform(lr[:, 3], k, slope_lo, slope_hi)

    mu_z = lr_t.mean(axis=0)           # log-space mean (transformed inflation)
    Sigma_z = np.cov(lr_t.T)           # log-space covariance (transformed inflation)

    Z = rng.multivariate_normal(mu_z, Sigma_z, size=N)

    # Invert inflation transform in log-return space before exponentiating
    Z[:, 3] = inv_pwl_transform(Z[:, 3], k, slope_lo, slope_hi)

    rate_series = np.exp(Z) - 1.0
    rate_series[:, 3] = np.maximum(rate_series[:, 3], INFLATION_FLOOR)

    # Metadata derived from original (untransformed) log-returns for UI display
    lr_orig_cov = np.cov(lr.T)
    sigma_z_orig = np.sqrt(np.diag(lr_orig_cov))
    mu_z_orig = lr.mean(axis=0)
    sigma_z_orig_diag = np.diag(lr_orig_cov)
    means = np.exp(mu_z_orig + 0.5 * sigma_z_orig_diag) - 1.0
    stdev = (means + 1.0) * np.sqrt(np.exp(sigma_z_orig_diag) - 1.0)
    corr = lr_orig_cov / np.outer(sigma_z_orig, sigma_z_orig)

    return rate_series, means, stdev, corr


# Inflation floor for stochastic models: prevents Great Depression-level deflation
# from appearing in Gaussian tail samples. Post-1950 historical minimum is -0.7%;
# this floor allows extreme-but-plausible scenarios while excluding outliers driven
# by fitting to the 1928-1950 era.
INFLATION_FLOOR = -0.05


def generate_stochastic_series(
    N: int,
    values_pct: list[float] | np.ndarray,
    stdev_pct: list[float] | np.ndarray,
    corr=None,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Nx4 stochastic series from user-provided mean and volatility.

    Args:
        N: Number of years
        values_pct: Arithmetic mean returns in percent (length 4)
        stdev_pct: Standard deviations in percent (length 4)
        corr: Correlation matrix (4x4) or off-diagonal list (6). None = identity.
        rng: Random generator. If None, uses default_rng().

    Returns:
        (rate_series, means, stdev, corr) - series in decimal, params for metadata
    """
    Nk = 4
    if rng is None:
        rng = np.random.default_rng()

    means = np.array(values_pct, dtype=float) / 100.0
    stdev = np.array(stdev_pct, dtype=float) / 100.0

    if np.any(stdev < 0):
        raise ValueError(
            "Gaussian model requires non-negative standard deviations. "
            f"Got stdev in percent: {np.array(stdev_pct).tolist()}"
        )

    if corr is None:
        corr_matrix = np.identity(Nk)
    else:
        corr_matrix = _build_corr_matrix(corr, Nk)

    covar = _build_covar(stdev, corr_matrix)
    rate_series = rng.multivariate_normal(means, covar, size=N)

    return rate_series, means, stdev, corr_matrix
