"""
VAR(1) Rate Model — Vector Autoregression of order 1.

Parametric stochastic model that captures year-to-year serial correlations
(momentum, mean-reversion) and contemporaneous cross-asset correlations.

Model:  y_t = c + A @ y_{t-1} + ε_t,   ε_t ~ N(0, Σ)

where y_t ∈ R^4 is [S&P 500, Bonds Baa, T-Notes, Inflation] in decimal.

Parameters c (intercept) and A (transition matrix) are estimated by OLS
from historical data.  Σ is the residual covariance matrix.

Reference: Campbell & Viceira (2002), "Strategic Asset Allocation",
Oxford University Press.

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

from owlplanner.rate_models.base import BaseRateModel
from owlplanner.rate_models.constants import REQUIRED_RATE_COLUMNS
from owlplanner.rates import FROM, TO


class VARRateModel(BaseRateModel):

    model_name = "var"

    description = (
        "VAR(1) model fitted by Ordinary Least Squares (OLS) on the historical window. "
        "Captures momentum and mean-reversion — each year's returns depend on the previous year across all four asset classes."
    )

    more_info = "https://github.com/mdlacasse/Owl/blob/main/src/owlplanner/rate_models/README.md"

    deterministic = False
    constant = False

    required_parameters = {
        "frm": {
            "type": "int",
            "description": "First historical year used for fitting (inclusive).",
            "example": "1928",
        },
        "to": {
            "type": "int",
            "description": "Last historical year used for fitting (inclusive).",
            "example": "2024",
        },
    }

    optional_parameters = {
        "shrink": {
            "type": "bool",
            "default": True,
            "description": (
                "If True, apply spectral shrinkage to A when its spectral radius >= 0.95, "
                "ensuring stationarity."
            ),
            "example": "true",
        },
    }

    #######################################################################
    # Initialization
    #######################################################################

    def __init__(self, config, seed=None, logger=None):
        super().__init__(config, seed, logger)

        self.frm = int(self.get_param("frm"))
        self.to = int(self.get_param("to"))
        self.shrink = bool(self.get_param("shrink"))

        if not (FROM <= self.frm <= TO):
            raise ValueError(f"frm={self.frm} out of bounds [{FROM}, {TO}].")

        if not (FROM <= self.to <= TO):
            raise ValueError(f"to={self.to} out of bounds [{FROM}, {TO}].")

        if self.frm >= self.to:
            raise ValueError("frm must be < to (need at least 2 observations to fit VAR(1)).")

        data = self._load_historical_slice()

        if len(data) < 10:
            raise ValueError(
                f"VAR(1) requires at least 10 observations; "
                f"frm={self.frm}, to={self.to} yields only {len(data)}."
            )

        self._mean = data.mean(axis=0)
        self._fit(data)

        self._rng = np.random.default_rng(seed)

    #######################################################################
    # Historical Data
    #######################################################################

    def _load_historical_slice(self):
        """Load and return decimal-scale historical data (T × 4)."""
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
    # OLS Fitting
    #######################################################################

    def _fit(self, data):
        """
        Fit VAR(1) by OLS.

        Solves  Y = X @ B  where
            Y  shape (T-1, 4) = data[1:]
            X  shape (T-1, 5) = [ones | data[:-1]]
            B  shape (5, 4)

        Extracts:
            c  = B[0, :]      intercept (4,)
            A  = B[1:, :].T   transition matrix (4, 4)
            Σ  residual covariance (4, 4)
            L  Cholesky factor of Σ (4, 4)
        """
        T = len(data)

        Y = data[1:]          # (T-1, 4)
        ones = np.ones((T - 1, 1))
        X = np.hstack([ones, data[:-1]])   # (T-1, 5)

        B, _, _, _ = np.linalg.lstsq(X, Y, rcond=None)   # (5, 4)

        self._c = B[0, :]          # (4,)
        self._A = B[1:, :].T       # (4, 4)

        # Residuals and covariance
        E = Y - X @ B              # (T-1, 4)
        dof = T - 1 - 5            # degrees of freedom
        if dof <= 0:
            dof = T - 1            # fallback for very short windows
        Sigma = E.T @ E / dof      # (4, 4)

        # Stationarity check
        eigenvalues = np.linalg.eigvals(self._A)
        rho = float(np.max(np.abs(eigenvalues)))

        if rho >= 0.95:
            if self.shrink:
                scale = 0.95 / rho
                self._A = self._A * scale
                if self.logger:
                    self.logger.warning(
                        f"VAR(1): spectral radius {rho:.4f} >= 0.95; "
                        f"shrinking A by {scale:.4f} to ensure stationarity."
                    )
            else:
                if self.logger:
                    self.logger.warning(
                        f"VAR(1): spectral radius {rho:.4f} >= 0.95 (stationarity not guaranteed). "
                        "Set shrink=True to auto-correct."
                    )

        # Cholesky decomposition — ensure Sigma is symmetric positive definite
        Sigma = (Sigma + Sigma.T) / 2.0
        min_eig = float(np.min(np.linalg.eigvalsh(Sigma)))
        if min_eig <= 0:
            Sigma += (-min_eig + 1e-10) * np.eye(4)

        self._L = np.linalg.cholesky(Sigma)

    #######################################################################
    # Generate
    #######################################################################

    def generate(self, N):
        """
        Simulate a VAR(1) chain of length N.

        Returns
        -------
        np.ndarray, shape (N, 4), decimal-scale returns.
        """
        out = np.empty((N, 4))
        y_prev = self._mean.copy()

        for t in range(N):
            eps = self._L @ self._rng.standard_normal(4)
            y_t = self._c + self._A @ y_prev + eps
            out[t] = y_t
            y_prev = y_t

        return out
