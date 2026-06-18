"""
Multivariate Gaussian Mixture Model rate model.

Fits a K-component full-covariance GMM on historical returns via the
Expectation-Maximization (EM) algorithm, capturing cross-asset correlations
within each market regime (e.g., bull, bear, crisis).

Dependencies: numpy, scipy (both already required by owlplanner).

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
###########################################################################
import numpy as np
from scipy.special import logsumexp
from scipy.stats import multivariate_normal

from owlplanner.rate_models.base import BaseRateModel
from owlplanner.rate_models._builtin_impl import apply_return_floors, constrain_series_mean, load_historical_slice
from owlplanner.rates import FROM, TO

_MAX_ITER = 200
_TOL = 1e-6
_REG_COVAR = 1e-6  # diagonal regularization added to each covariance matrix


class GMMRateModel(BaseRateModel):

    model_name = "gmm"

    description = (
        "Fits a multivariate Gaussian Mixture Model on historical returns via EM, "
        "capturing regime-dependent cross-asset correlations (bull, bear, crisis). "
        "Each component is a full 4D Gaussian; joint samples preserve realistic inter-asset dependencies."
    )

    deterministic = False
    constant = False

    required_parameters = {}

    optional_parameters = {
        "frm": {
            "type": "int",
            "description": "First historical year for fitting (inclusive).",
            "default": FROM,
            "example": "1928",
        },
        "to": {
            "type": "int",
            "description": "Last historical year for fitting (inclusive).",
            "default": TO,
            "example": "2025",
        },
        "n_components": {
            "type": "int",
            "description": "Number of mixture components (market regimes).",
            "default": 3,
            "example": "3",
        },
        "constrain_mean": {
            "type": "bool",
            "description": (
                "Shift each generated series so its arithmetic mean matches the historical window mean. "
                "Preserves distribution shape; only the mean is corrected. Default False."
            ),
            "default": False,
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
        self.n_components = int(self.get_param("n_components"))

        if not (FROM <= self.frm <= TO):
            raise ValueError(f"frm={self.frm} out of range [{FROM}, {TO}].")
        if not (FROM <= self.to <= TO):
            raise ValueError(f"to={self.to} out of range [{FROM}, {TO}].")
        if self.frm >= self.to:
            raise ValueError("frm must be < to.")
        if self.n_components < 2:
            raise ValueError("n_components must be >= 2.")

        self._rng = np.random.default_rng(seed)
        self._historical_data, _ = load_historical_slice(self.frm, self.to)
        T = len(self._historical_data)
        if T < self.n_components:
            raise ValueError(
                f"Historical window [{self.frm}, {self.to}] has only {T} observations "
                f"but n_components={self.n_components}. "
                f"Use a wider year range (need at least {self.n_components} years) "
                f"or reduce n_components."
            )
        self._weights, self._means, self._covs = self._fit_em(self._historical_data)
        self._constrain_mean = bool(self.get_param("constrain_mean"))
        if self._constrain_mean:
            self._hist_target_means = self._historical_data.mean(axis=0)

    #######################################################################
    # EM Algorithm
    #######################################################################

    def _fit_em(self, X):
        """
        Fit a K-component full-covariance GMM via EM.

        Returns (weights, means, covs) where:
          weights : (K,)      mixture weights summing to 1
          means   : (K, D)    component mean vectors
          covs    : (K, D, D) component covariance matrices
        """
        N, D = X.shape
        K = self.n_components

        # Initialize: K distinct data points as means, uniform weights,
        # pooled covariance for all components.
        idx = self._rng.choice(N, K, replace=False)
        means = X[idx].copy()
        weights = np.full(K, 1.0 / K)
        cov0 = np.cov(X.T) + _REG_COVAR * np.eye(D)
        covs = np.array([cov0.copy() for _ in range(K)])

        prev_ll = -np.inf

        for _ in range(_MAX_ITER):
            # ----------------------------------------------------------
            # E-step: compute log responsibilities (unnormalized first)
            # ----------------------------------------------------------
            log_r = np.column_stack([
                np.log(weights[k]) + multivariate_normal.logpdf(X, mean=means[k], cov=covs[k])
                for k in range(K)
            ])  # shape (N, K)

            ll = logsumexp(log_r, axis=1).sum()
            log_r -= logsumexp(log_r, axis=1, keepdims=True)  # normalize
            resp = np.exp(log_r)  # shape (N, K)

            # ----------------------------------------------------------
            # M-step: update parameters from responsibilities
            # ----------------------------------------------------------
            Nk = resp.sum(axis=0) + 1e-300          # effective count per component
            weights = Nk / N
            means = (resp.T @ X) / Nk[:, None]      # (K, D)
            covs = np.array([
                ((resp[:, k:k+1] * (X - means[k])).T @ (X - means[k])) / Nk[k]
                + _REG_COVAR * np.eye(D)
                for k in range(K)
            ])                                       # (K, D, D)

            if ll - prev_ll < _TOL:
                break
            prev_ll = ll

        return weights, means, covs

    #######################################################################
    #######################################################################
    # Generate
    #######################################################################

    def generate(self, N: int) -> np.ndarray:
        """Draw N joint annual return vectors from the fitted GMM."""
        k_idx = self._rng.choice(self.n_components, size=N, p=self._weights)
        D = self._historical_data.shape[1]
        out = np.empty((N, D))
        for k in range(self.n_components):
            mask = k_idx == k
            n_k = int(mask.sum())
            if n_k > 0:
                out[mask] = self._rng.multivariate_normal(self._means[k], self._covs[k], size=n_k)
        if self._constrain_mean:
            out = constrain_series_mean(out, self._hist_target_means)
        return apply_return_floors(out)

    #######################################################################
    # Log-likelihood (used by the offline sklearn comparison test)
    #######################################################################

    def log_likelihood(self, X: np.ndarray) -> float:
        """Evaluate the fitted GMM log-likelihood on data X (shape N×D)."""
        log_r = np.column_stack([
            np.log(self._weights[k]) + multivariate_normal.logpdf(X, mean=self._means[k], cov=self._covs[k])
            for k in range(self.n_components)
        ])
        return float(logsumexp(log_r, axis=1).sum())
