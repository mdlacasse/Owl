"""
Gaussian copula rate model.

Fits a Gaussian copula to historical return data, preserving each asset's
empirical marginal distribution exactly while capturing joint dependence
through a 4x4 copula correlation matrix.

Unlike historical_gaussian and historical_lognormal (which impose a Gaussian
shape on every marginal), the copula approach allows S&P 500 to remain
left-skewed, T-Notes right-skewed, and inflation bounded by INFLATION_FLOOR,
while still generating new year-combinations that honour all pairwise
rank correlations.

Dependencies: numpy, scipy (both already required by owlplanner).

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
###########################################################################
import numpy as np
from scipy.special import ndtri
from scipy.stats import norm, rankdata

from owlplanner.rate_models.base import BaseRateModel
from owlplanner.rate_models._builtin_impl import INFLATION_FLOOR
from owlplanner.rates import FROM, TO, SP500, BondsBaa, TNotes, Inflation


def generate_histocopula_series(
    N: int,
    frm: int,
    to: int,
    rng: np.random.Generator,
    mylog=None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Nx4 series using a Gaussian copula fitted to the historical window.

    Each asset's marginal distribution is preserved exactly via the empirical CDF,
    while the joint dependence structure is captured by a 4x4 Gaussian copula.
    This avoids imposing a Gaussian shape on any individual marginal (S&P 500 is
    left-skewed, T-Notes right-skewed, inflation right-skewed) while still
    generating new year combinations that honour all pairwise correlations.

    Algorithm:
        1. Map each marginal to U[0,1] via rank-based empirical CDF.
        2. Apply Φ⁻¹ to obtain standard-normal copula variates.
        3. Fit the 4x4 copula correlation matrix Rho in that normal space.
        4. Sample N draws from N(0, Rho).
        5. Map back through Φ and the empirical quantile function.
        6. Floor inflation at INFLATION_FLOOR.

    Generated values are bounded to the historical [min, max] for each asset
    (no parametric extrapolation beyond observed data).

    Returns:
        (rate_series, means, stdev, corr) - series in decimal, historical stats for metadata
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

    T, K = data.shape

    # Step 1: rank-based empirical CDF → U[0,1].
    # (rank − 0.5) / T keeps all values strictly inside (0, 1) so Φ⁻¹ is finite.
    U_hist = np.zeros_like(data)
    for k in range(K):
        U_hist[:, k] = (rankdata(data[:, k]) - 0.5) / T

    # Step 2: Φ⁻¹(U) → standard normals in copula space.
    Z_hist = ndtri(U_hist)                   # (T, K)

    # Step 3: Gaussian copula correlation matrix.
    Rho = np.corrcoef(Z_hist.T)              # (K, K)
    if np.any(np.isnan(Rho)):
        raise ValueError(
            f"Historical window [{frm}, {to}] produced a degenerate correlation matrix "
            f"(T={T} years, likely tied values in one asset column). Use a wider window."
        )
    if mylog:
        mylog.vprint(f"historical_copula: Rho fitted on {T} years ({frm}-{to}).")

    # Step 4: sample from multivariate normal with the copula correlation.
    Z_samples = rng.multivariate_normal(np.zeros(K), Rho, size=N)   # (N, K)

    # Step 5a: Φ(Z) → U[0,1].
    U_samples = norm.cdf(Z_samples)          # (N, K)

    # Step 5b: empirical quantile back-transform (linear interpolation over sorted history).
    # u_grid[i] = (i + 0.5) / T matches the forward transform.
    # np.interp clamps U outside [u_grid[0], u_grid[-1]] to the historical min/max,
    # preventing extrapolation beyond observed data.
    u_grid = (np.arange(T) + 0.5) / T
    rate_series = np.zeros((N, K))
    for k in range(K):
        rate_series[:, k] = np.interp(U_samples[:, k], u_grid, np.sort(data[:, k]))

    # Step 6: apply inflation floor to avoid Great Depression tail artefacts.
    rate_series[:, 3] = np.maximum(rate_series[:, 3], INFLATION_FLOOR)

    # Metadata: report historical arithmetic statistics for UI display.
    means = data.mean(axis=0)
    stdev = data.std(axis=0, ddof=1)
    corr = np.corrcoef(data.T)

    return rate_series, means, stdev, corr


class HistoCopulaRateModel(BaseRateModel):
    model_name = "historical_copula"
    description = (
        "Samples from a Gaussian copula fitted to the selected historical window. "
        "Each asset's marginal distribution is preserved exactly via the empirical CDF "
        "(no Gaussian shape imposed on any marginal), while joint dependence is captured "
        "by a 4×4 copula correlation matrix. Generates new year-combinations that were "
        "not observed historically but honour all pairwise correlations. "
        "Inflation is floored at -5% to exclude Great Depression tail artefacts."
    )
    deterministic = False
    constant = False
    required_parameters = {
        "frm": {
            "type": "int",
            "description": "First year of historical window (inclusive).",
            "example": "1928",
        },
        "to": {
            "type": "int",
            "description": "Last year of historical window (inclusive).",
            "example": "2024",
        },
    }
    optional_parameters = {}

    def __init__(self, config, seed=None, logger=None):
        config = dict(config or {})
        rate_seed = config.pop("rate_seed", seed)
        super().__init__(config, seed=rate_seed, logger=logger)
        self._rng = np.random.default_rng(rate_seed)
        frm = self.get_param("frm")
        to = self.get_param("to")
        _validate_historical_range(frm, to)
        self._frm = frm
        self._to = to

    def generate(self, N):
        series, means, stdev_arr, corr_arr = generate_histocopula_series(
            N, self._frm, self._to, self._rng, self.logger
        )
        self.params["values"] = means.copy()
        self.params["stdev"] = stdev_arr.copy()
        self.params["corr"] = corr_arr.copy()
        return series


def _validate_historical_range(frm: int, to: int) -> None:
    if not (FROM <= frm <= TO):
        raise ValueError(f"frm={frm} out of range [{FROM}, {TO}].")
    if not (FROM <= to <= TO):
        raise ValueError(f"to={to} out of range [{FROM}, {TO}].")
    if frm >= to:
        raise ValueError(f"frm={frm} must be less than to={to}.")
    if to - frm < 2:
        raise ValueError(f"Window [{frm}, {to}] has only {to - frm + 1} years; need at least 3.")
