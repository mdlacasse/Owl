"""
Hidden Markov Model (HMM) rate model with Gaussian emissions.

Extends the GMM by adding temporal autocorrelation through a Markov
transition matrix between K regimes, fit via the Baum-Welch algorithm.
Regime persistence produces realistic multi-year bull/bear runs, capturing
sequence-of-returns risk beyond the i.i.d. GMM.

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
from scipy.stats import multivariate_normal

from owlplanner.rate_models.base import BaseRateModel
from owlplanner.rate_models._builtin_impl import apply_return_floors, constrain_series_mean, load_historical_slice
from owlplanner.rates import FROM, TO

_MAX_ITER = 200
_TOL = 1e-6
_REG_COVAR = 1e-6  # diagonal regularization for emission covariances


class HMMRateModel(BaseRateModel):
    model_name = "hmm"

    description = (
        "Fits a Hidden Markov Model on historical returns via Baum-Welch EM, "
        "adding temporal autocorrelation through a Markov transition matrix between K regimes. "
        "Regime persistence produces realistic multi-year bull/bear runs, capturing "
        "sequence-of-returns risk beyond the i.i.d. GMM."
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
            "description": "Number of hidden states (market regimes).",
            "default": 3,
            "example": "3",
        },
        "reg_trans": {
            "type": "float",
            "description": "Additive smoothing on transition counts (prevents zero-probability transitions).",
            "default": 1e-3,
            "example": "0.001",
        },
        "init_regime": {
            "type": "int",
            "description": "Starting regime index for generation (0 to n_components-1). "
            "None = draw from stationary distribution.",
            "default": None,
            "example": "0",
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
        self.reg_trans = float(self.get_param("reg_trans"))
        self.init_regime = self.get_param("init_regime")

        if not (FROM <= self.frm <= TO):
            raise ValueError(f"frm={self.frm} out of range [{FROM}, {TO}].")
        if not (FROM <= self.to <= TO):
            raise ValueError(f"to={self.to} out of range [{FROM}, {TO}].")
        if self.frm >= self.to:
            raise ValueError("frm must be < to.")
        if self.n_components < 2:
            raise ValueError("n_components must be >= 2.")
        if self.reg_trans <= 0:
            raise ValueError(f"reg_trans={self.reg_trans} must be > 0.")
        if self.init_regime is not None:
            ir = int(self.init_regime)
            if not (0 <= ir < self.n_components):
                raise ValueError(f"init_regime={ir} out of range [0, {self.n_components - 1}].")
            self.init_regime = ir

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
        self._pi, self._trans, self._means, self._covs = self._fit_baum_welch(self._historical_data)
        self._stationary_pi = self._stationary_dist()
        self._constrain_mean = bool(self.get_param("constrain_mean"))
        if self._constrain_mean:
            self._hist_target_means = self._historical_data.mean(axis=0)

    #######################################################################
    # Baum-Welch Algorithm
    #######################################################################

    def _compute_emissions(self, X, means, covs):
        """Return B[t, k] = p(x_t | regime k), shape (T, K). Clipped to avoid exact zeros."""
        T = len(X)
        K = self.n_components
        B = np.empty((T, K))
        for k in range(K):
            B[:, k] = multivariate_normal.pdf(X, mean=means[k], cov=covs[k])
        return np.maximum(B, 1e-300)

    def _forward(self, B, pi, trans):
        """Scaled forward pass. Returns (alpha_hat, scales) with shapes (T,K) and (T,)."""
        T, K = B.shape
        alpha = np.empty((T, K))
        scales = np.empty(T)

        alpha[0] = pi * B[0]
        scales[0] = alpha[0].sum()
        alpha[0] /= scales[0]

        for t in range(1, T):
            alpha[t] = B[t] * (alpha[t - 1] @ trans)
            scales[t] = alpha[t].sum()
            alpha[t] /= scales[t]

        return alpha, scales

    def _backward(self, B, trans, scales):
        """Scaled backward pass. Returns beta_hat of shape (T, K)."""
        T, K = B.shape
        beta = np.ones((T, K))

        for t in range(T - 2, -1, -1):
            beta[t] = (trans @ (B[t + 1] * beta[t + 1])) / scales[t + 1]

        return beta

    def _fit_baum_welch(self, X):
        """
        Fit K-component HMM via Baum-Welch EM.

        Returns (pi, trans, means, covs) where:
          pi    : (K,)      initial state distribution
          trans : (K, K)    transition matrix, rows sum to 1
          means : (K, D)    emission mean vectors
          covs  : (K, D, D) emission covariance matrices
        """
        T, D = X.shape
        K = self.n_components

        # Initialize emission parameters: K distinct data points as means,
        # pooled covariance.
        idx = self._rng.choice(T, K, replace=False)
        means = X[idx].copy()
        cov0 = np.cov(X.T) + _REG_COVAR * np.eye(D)
        covs = np.array([cov0.copy() for _ in range(K)])

        # Initialize transition matrix to be near-diagonal (regime persistence),
        # and initial state distribution to uniform.
        off = 0.2 / max(K - 1, 1)
        trans = np.full((K, K), off)
        np.fill_diagonal(trans, 1.0 - 0.2)
        pi = np.ones(K) / K

        prev_ll = -np.inf

        for _ in range(_MAX_ITER):
            # ----------------------------------------------------------
            # E-step: forward-backward
            # ----------------------------------------------------------
            B = self._compute_emissions(X, means, covs)
            alpha, scales = self._forward(B, pi, trans)
            beta = self._backward(B, trans, scales)

            ll = float(np.log(scales).sum())

            # Posterior state probabilities (gamma)
            gamma = alpha * beta  # (T, K)
            gamma_sum = gamma.sum(axis=1, keepdims=True)
            gamma /= np.maximum(gamma_sum, 1e-300)

            # Joint transition posteriors (xi), shape (T-1, K, K)
            xi = (
                alpha[:-1, :, None]  # (T-1, K, 1)
                * trans[None, :, :]  # (1,  K, K)
                * B[1:, None, :]  # (T-1, 1, K)
                * beta[1:, None, :]  # (T-1, 1, K)
            )
            xi_row_sum = xi.reshape(T - 1, -1).sum(axis=1, keepdims=True).reshape(T - 1, 1, 1)
            xi /= np.maximum(xi_row_sum, 1e-300)

            # ----------------------------------------------------------
            # M-step: update parameters
            # ----------------------------------------------------------
            pi = gamma[0] / gamma[0].sum()

            # Transition matrix with Laplace smoothing
            xi_sum = xi.sum(axis=0)  # (K, K)
            gamma_sum_t = gamma[:-1].sum(axis=0)  # (K,)
            trans = (xi_sum + self.reg_trans) / (gamma_sum_t[:, None] + K * self.reg_trans)

            Nk = gamma.sum(axis=0) + 1e-300  # (K,)
            means = (gamma.T @ X) / Nk[:, None]  # (K, D)
            covs = np.array(
                [
                    ((gamma[:, k : k + 1] * (X - means[k])).T @ (X - means[k])) / Nk[k] + _REG_COVAR * np.eye(D)
                    for k in range(K)
                ]
            )

            if ll - prev_ll < _TOL:
                break
            prev_ll = ll

        return pi, trans, means, covs

    #######################################################################
    # Stationary Distribution
    #######################################################################

    def _stationary_dist(self):
        """Compute the stationary distribution of the transition matrix via power iteration."""
        pi = np.ones(self.n_components) / self.n_components
        for _ in range(2000):
            pi_new = pi @ self._trans
            if np.max(np.abs(pi_new - pi)) < 1e-12:
                break
            pi = pi_new
        return pi_new

    #######################################################################
    #######################################################################
    # Generate
    #######################################################################

    def generate(self, N: int) -> np.ndarray:
        """Draw N joint annual return vectors by simulating the fitted HMM."""
        K = self.n_components
        D = self._historical_data.shape[1]

        if self.init_regime is not None:
            k = self.init_regime
        else:
            k = int(self._rng.choice(K, p=self._stationary_pi))

        out = np.empty((N, D))
        for t in range(N):
            out[t] = self._rng.multivariate_normal(self._means[k], self._covs[k])
            k = int(self._rng.choice(K, p=self._trans[k]))

        if self._constrain_mean:
            out = constrain_series_mean(out, self._hist_target_means)
        return apply_return_floors(out)

    #######################################################################
    # Log-likelihood
    #######################################################################

    def log_likelihood(self, X: np.ndarray) -> float:
        """Evaluate the fitted HMM log-likelihood on data X (shape T×D)."""
        B = self._compute_emissions(X, self._means, self._covs)
        _, scales = self._forward(B, self._pi, self._trans)
        return float(np.log(scales).sum())
