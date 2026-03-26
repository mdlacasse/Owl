"""
DCC-GARCH(1,1) Rate Model (Engle 2002).

Two-step MLE:
  Step 1 — per-asset GARCH(1,1) fitted by scipy L-BFGS-B.
  Step 2 — DCC dynamics fitted on standardized residuals.

Captures time-varying volatility (volatility clustering) and time-varying
cross-asset correlations.  Implemented with numpy and scipy only.

Reference: Engle, R. F. (2002). Dynamic Conditional Correlation: A Simple
Class of Multivariate Generalized Autoregressive Conditional
Heteroskedasticity Models. Journal of Business & Economic Statistics 20(3).

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
###########################################################################
import numpy as np
import pandas as pd
import os
import sys

from scipy.optimize import minimize
from numpy.linalg import cholesky, eigvalsh, LinAlgError

from owlplanner.rate_models.base import BaseRateModel
from owlplanner.rate_models.constants import GARCH_DCC_MIN_OBSERVATIONS, REQUIRED_RATE_COLUMNS
from owlplanner.rates import FROM, TO


# ---------------------------------------------------------------------------
# Module-level helper: normalise Q → R (correlation matrix)
# ---------------------------------------------------------------------------

def _normalize_Q(Q):
    """Convert a quasi-correlation matrix Q to a proper correlation matrix R."""
    d = np.sqrt(np.maximum(np.diag(Q), 1e-10))
    R = Q / np.outer(d, d)
    # Enforce exact symmetry
    R = (R + R.T) / 2.0
    return R


def _pd_cholesky(M):
    """
    Cholesky factor of M with positive-definite guard.

    If M is not PD (minimum eigenvalue <= 1e-10) we add a small diagonal
    correction before decomposing.  Falls back to identity on failure.
    """
    min_eig = float(np.min(eigvalsh(M)))
    if min_eig <= 1e-10:
        M = M + (-min_eig + 1e-8) * np.eye(M.shape[0])
    try:
        return cholesky(M)
    except LinAlgError:
        return np.eye(M.shape[0])


###########################################################################


class GARCHDCCRateModel(BaseRateModel):

    model_name = "garch_dcc"

    description = (
        "DCC-GARCH(1,1) model (Engle 2002) fitted by two-step MLE on historical data. "
        "Captures time-varying volatility (GARCH) and time-varying cross-asset correlations (DCC). "
        "Produces realistic volatility clustering and correlation spikes during market stress."
    )

    more_info = "https://github.com/mdlacasse/Owl/blob/main/src/owlplanner/rate_models/README.md"

    deterministic = False
    constant = False

    required_parameters = {
        "frm": {
            "type": "int",
            "description": "First year of historical window.",
            "example": "1928",
        },
        "to": {
            "type": "int",
            "description": "Last year of historical window.",
            "example": "2024",
        },
    }

    optional_parameters = {}

    #######################################################################
    # Initialization
    #######################################################################

    def __init__(self, config, seed=None, logger=None):
        super().__init__(config, seed, logger)

        self.frm = int(self.get_param("frm"))
        self.to = int(self.get_param("to"))

        if not (FROM <= self.frm <= TO):
            raise ValueError(f"frm={self.frm} out of bounds [{FROM}, {TO}].")

        if not (FROM <= self.to <= TO):
            raise ValueError(f"to={self.to} out of bounds [{FROM}, {TO}].")

        if self.frm >= self.to:
            raise ValueError("frm must be strictly less than to.")

        data = self._load_historical_slice()
        T = len(data)

        if T < GARCH_DCC_MIN_OBSERVATIONS:
            raise ValueError(
                f"DCC-GARCH(1,1) requires at least {GARCH_DCC_MIN_OBSERVATIONS} observations; "
                f"frm={self.frm}, to={self.to} yields only {T}."
            )

        self._mu = data.mean(axis=0)
        self._fit(data)

        # RNG is initialised last, after all deterministic fitting
        self._rng = np.random.default_rng(seed)

    #######################################################################
    # Historical Data
    #######################################################################

    def _load_historical_slice(self):
        """Load and return decimal-scale historical data (T x 4)."""
        where = os.path.dirname(sys.modules["owlplanner"].__file__)
        file = os.path.join(where, "data/rates.csv")

        df = pd.read_csv(file)

        if "year" not in df.columns:
            raise ValueError("Historical rates.csv must contain a 'year' column.")

        mask = (df["year"] >= self.frm) & (df["year"] <= self.to)
        df_slice = df.loc[mask]

        if df_slice.empty:
            raise ValueError("No historical data in selected range.")

        data = df_slice[list(REQUIRED_RATE_COLUMNS)].values.astype(float)
        data = data / 100.0  # percent → decimal

        return data

    #######################################################################
    # Fitting orchestration
    #######################################################################

    def _fit(self, data):
        """
        Two-step DCC-GARCH(1,1) fitting.

        Step 1: per-asset GARCH(1,1) → omega, alpha, beta, sigma2_path per asset.
        Step 2: DCC on standardised residuals z[t,i] = eps[t,i] / sqrt(sigma2[t,i]).
        """
        eps = data - self._mu          # (T, 4) demeaned returns

        self._fit_garch(eps)

        # Build standardised residuals using the fitted sigma2 paths
        T, K = eps.shape
        z = np.zeros_like(eps)
        for i in range(K):
            # Reproduce sigma2 path using fitted params
            omega_i = self._garch_omega[i]
            alpha_i = self._garch_alpha[i]
            beta_i = self._garch_beta[i]
            var_i = float(np.var(eps[:, i]))
            h = var_i
            for t in range(T):
                h = max(omega_i + alpha_i * eps[t, i] ** 2 + beta_i * h, 1e-10)
                z[t, i] = eps[t, i] / np.sqrt(h)

        self._fit_dcc(z)

    #######################################################################
    # Step 1: per-asset GARCH(1,1)
    #######################################################################

    def _fit_garch(self, eps):
        """
        Fit GARCH(1,1) independently for each of the 4 asset classes.

        h[0] = var(eps_i)
        h[t] = omega + alpha * eps[t-1]^2 + beta * h[t-1]

        Stores:
            self._garch_omega  (4,)
            self._garch_alpha  (4,)
            self._garch_beta   (4,)
            self._sigma2_0     (4,)  terminal conditional variances (warm-start)
        """
        T, K = eps.shape
        omega = np.zeros(K)
        alpha = np.zeros(K)
        beta = np.zeros(K)
        sigma2_0 = np.zeros(K)

        for i in range(K):
            e = eps[:, i]
            var_i = float(np.var(e))

            def nll(params):
                w, a, b = params
                if w <= 0 or a <= 0 or b <= 0 or a + b >= 1.0:
                    return 1e10
                h = var_i
                ll = 0.0
                for t in range(1, T):
                    h = w + a * e[t - 1] ** 2 + b * h
                    h = max(h, 1e-10)
                    ll += np.log(h) + e[t] ** 2 / h
                return 0.5 * ll

            x0 = [var_i * 0.05, 0.10, 0.85]
            bounds = [(1e-8, None), (1e-6, 0.9999), (1e-6, 0.9999)]

            result = minimize(nll, x0, method="L-BFGS-B", bounds=bounds)

            if result.success and result.x[1] + result.x[2] < 1.0:
                w_fit, a_fit, b_fit = result.x
            else:
                # Fallback: EWMA-style with stationary persistence
                a_fit = 0.06
                b_fit = 0.94
                w_fit = var_i * 0.0001

            # Enforce stationarity by rescaling if needed
            if a_fit + b_fit >= 1.0:
                scale = 0.999 / (a_fit + b_fit)
                a_fit *= scale
                b_fit *= scale

            omega[i] = w_fit
            alpha[i] = a_fit
            beta[i] = b_fit

            # Forward pass to get terminal conditional variance
            h = var_i
            for t in range(T):
                h = w_fit + a_fit * e[t] ** 2 + b_fit * h
                h = max(h, 1e-10)
            sigma2_0[i] = h

        self._garch_omega = omega
        self._garch_alpha = alpha
        self._garch_beta = beta
        self._sigma2_0 = sigma2_0

    #######################################################################
    # Step 2: DCC
    #######################################################################

    def _fit_dcc(self, z):
        """
        Fit DCC(1,1) on standardised residuals z (T x 4).

        Q[0] = Q_bar = z.T @ z / T
        Q[t] = (1-a-b)*Q_bar + a * outer(z[t-1], z[t-1]) + b * Q[t-1]

        Stores:
            self._Q_bar       (4,4) unconditional quasi-correlation
            self._dcc_a       scalar
            self._dcc_b       scalar
            self._Q_0         (4,4) terminal Q (warm-start for generation)
            self._chol_R_0    (4,4) Cholesky of normalised terminal Q
        """
        T, K = z.shape
        Q_bar = z.T @ z / T
        Q_bar = (Q_bar + Q_bar.T) / 2.0

        def dcc_nll(params):
            a, b = params
            if a <= 0 or b <= 0 or a + b >= 1.0:
                return 1e10
            Q = Q_bar.copy()
            ll = 0.0
            for t in range(1, T):
                d = np.sqrt(np.maximum(np.diag(Q), 1e-10))
                R = Q / np.outer(d, d)
                R = (R + R.T) / 2.0
                # Positive-definiteness check
                if np.min(eigvalsh(R)) <= 0:
                    return 1e10
                try:
                    sign, logdet = np.linalg.slogdet(R)
                    if sign <= 0:
                        return 1e10
                    ll += logdet + z[t] @ np.linalg.solve(R, z[t])
                except LinAlgError:
                    return 1e10
                Q = (1 - a - b) * Q_bar + a * np.outer(z[t - 1], z[t - 1]) + b * Q
                Q = (Q + Q.T) / 2.0
            return 0.5 * ll

        x0 = [0.05, 0.90]
        bounds = [(1e-5, 0.4999), (1e-5, 0.9999)]

        result = minimize(dcc_nll, x0, method="L-BFGS-B", bounds=bounds)

        if result.success and result.x[0] + result.x[1] < 1.0:
            a_fit, b_fit = result.x
        else:
            a_fit, b_fit = 0.05, 0.90

        # Forward pass to get terminal Q
        Q = Q_bar.copy()
        for t in range(1, T):
            Q = (1 - a_fit - b_fit) * Q_bar + a_fit * np.outer(z[t - 1], z[t - 1]) + b_fit * Q
            Q = (Q + Q.T) / 2.0

        self._Q_bar = Q_bar
        self._dcc_a = float(a_fit)
        self._dcc_b = float(b_fit)
        self._Q_0 = Q.copy()
        self._chol_R_0 = _pd_cholesky(_normalize_Q(Q))

    #######################################################################
    # Generate
    #######################################################################

    def generate(self, N):
        """
        Simulate N years from the fitted DCC-GARCH(1,1) model.

        Returns
        -------
        np.ndarray, shape (N, 4), decimal-scale annual returns.
        """
        rng = self._rng
        omega = self._garch_omega
        alpha = self._garch_alpha
        beta = self._garch_beta
        a = self._dcc_a
        b = self._dcc_b
        Q_bar = self._Q_bar

        sigma2 = self._sigma2_0.copy()
        Q = self._Q_0.copy()
        chol_R = self._chol_R_0.copy()

        out = np.empty((N, 4))

        for t in range(N):
            z = chol_R @ rng.standard_normal(4)
            eps = np.sqrt(sigma2) * z
            out[t] = self._mu + eps

            # GARCH update
            sigma2 = omega + alpha * eps ** 2 + beta * sigma2
            sigma2 = np.maximum(sigma2, 1e-10)

            # DCC update
            Q = (1 - a - b) * Q_bar + a * np.outer(z, z) + b * Q
            Q = (Q + Q.T) / 2.0
            chol_R = _pd_cholesky(_normalize_Q(Q))

        return out
