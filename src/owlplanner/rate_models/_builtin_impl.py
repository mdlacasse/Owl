"""
Implementation helpers for built-in rate models.

Extracted from the legacy Rates class. Used by BuiltinRateModel to generate
rate series without depending on Rates.setMethod.

Copyright (C) 2025-2026 The Owlplanner Authors
"""
from __future__ import annotations

import numpy as np

from owlplanner.rates import (
    FROM,
    TO,
    BondsBaa,
    Inflation,
    SP500,
    TNotes,
    getRatesDistributions,
)


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
    Generate Nx4 fixed series from historical average, and return distribution params.

    Returns:
        (rate_series, means, stdev, corr) - series in decimal, params for metadata
    """
    means, stdev, corr, _ = getRatesDistributions(frm, to, mylog, in_percent=False)
    rate_series = np.tile(means, (N, 1))
    return rate_series, means, stdev, corr


def generate_histochastic_series(
    N: int,
    frm: int,
    to: int,
    rng: np.random.Generator,
    mylog=None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Nx4 stochastic series from historical distribution params.

    Returns:
        (rate_series, means, stdev, corr) - series in decimal, params for metadata
    """
    means, stdev, corr, covar = getRatesDistributions(frm, to, mylog, in_percent=False)
    rate_series = rng.multivariate_normal(means, covar, size=N)
    return rate_series, means, stdev, corr


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
        values_pct: Mean returns in percent (length 4)
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

    if corr is None:
        corr_matrix = np.identity(Nk)
    else:
        corr_matrix = _build_corr_matrix(corr, Nk)

    covar = _build_covar(stdev, corr_matrix)
    rate_series = rng.multivariate_normal(means, covar, size=N)

    return rate_series, means, stdev, corr_matrix
