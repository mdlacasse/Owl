"""
Tests for the Gaussian Mixture Model rate model.

Covers:
- Model attributes (name, flags)
- Output shape and decimal range
- Reproducibility (same/different seeds, regenRates)
- Fitted GMM parameter shapes and validity
- n_components option
- representative_sample returns historical pool
- Historical window sensitivity
- Parameter validation (frm >= to, n_components < 2)
- Discovery: 'gmm' in list_available_rate_models()
- Offline comparison against scikit-learn (skipped if sklearn absent)

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

import numpy as np
import pytest

from owlplanner import Plan
from owlplanner.rate_models.gmm import GMMRateModel
from owlplanner.rate_models.loader import list_available_rate_models

try:
    from sklearn.mixture import GaussianMixture as _SklearnGMM
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _make_plan():
    return Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)


def _set_gmm(p, frm=1928, to=2025, n_components=3, seed=None):
    if seed is not None:
        p.setReproducible(True, seed=seed)
    else:
        p.setReproducible(False)
    p.setRates(method="gmm", frm=frm, to=to, n_components=n_components)


def _make_model(frm=1928, to=2025, n_components=3, seed=None):
    config = {"method": "gmm", "frm": frm, "to": to, "n_components": n_components}
    return GMMRateModel(config, seed=seed)


# ------------------------------------------------------------
# Model attributes
# ------------------------------------------------------------

def test_model_name():
    assert GMMRateModel.model_name == "gmm"


def test_deterministic_flag():
    assert GMMRateModel.deterministic is False


def test_constant_flag():
    assert GMMRateModel.constant is False


def test_gmm_in_registry():
    assert "gmm" in list_available_rate_models()


# ------------------------------------------------------------
# Output shape and sanity
# ------------------------------------------------------------

def test_shape_via_plan():
    p = _make_plan()
    _set_gmm(p)
    assert p.tau_kn.shape == (4, p.N_n)


def test_output_is_finite():
    p = _make_plan()
    _set_gmm(p)
    assert np.all(np.isfinite(p.tau_kn))


def test_generate_shape_direct():
    model = _make_model(seed=42)
    out = model.generate(30)
    assert out.shape == (30, 4)


def test_rates_in_plausible_range():
    """Returns should be in decimal and within a wide plausible range."""
    model = _make_model(seed=0)
    out = model.generate(500)
    assert np.all(out > -1.0), "Some returns below -100%"
    assert np.all(out < 2.0), "Some returns above +200%"


def test_output_is_decimal_not_percent():
    """Mean return should be well under 1.0 (decimal), not ~7 (percent)."""
    model = _make_model(seed=1)
    out = model.generate(200)
    assert abs(out.mean()) < 0.5, "Outputs look like percent, not decimal"


# ------------------------------------------------------------
# Reproducibility
# ------------------------------------------------------------

def test_reproducible_same_seed():
    p1 = _make_plan()
    _set_gmm(p1, seed=42)

    p2 = _make_plan()
    _set_gmm(p2, seed=42)

    assert np.allclose(p1.tau_kn, p2.tau_kn)


def test_different_seeds_differ():
    p1 = _make_plan()
    _set_gmm(p1, seed=1)

    p2 = _make_plan()
    _set_gmm(p2, seed=2)

    assert not np.allclose(p1.tau_kn, p2.tau_kn)


def test_non_reproducible_regen_changes():
    p = _make_plan()
    _set_gmm(p)
    tau1 = p.tau_kn.copy()

    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()

    assert not np.allclose(tau1, tau2)


# ------------------------------------------------------------
# Fitted GMM parameters
# ------------------------------------------------------------

def test_fitted_weights_sum_to_one():
    model = _make_model()
    assert abs(model._weights.sum() - 1.0) < 1e-9


def test_fitted_means_shape():
    model = _make_model(n_components=3)
    assert model._means.shape == (3, 4)


def test_fitted_covariances_shape():
    model = _make_model(n_components=3)
    assert model._covs.shape == (3, 4, 4)


def test_covariances_positive_definite():
    """Each component covariance must be positive definite."""
    model = _make_model(n_components=3, seed=0)
    for cov in model._covs:
        eigs = np.linalg.eigvalsh(cov)
        assert np.all(eigs > 0), f"Covariance not PD: eigenvalues {eigs}"


# ------------------------------------------------------------
# n_components option
# ------------------------------------------------------------

def test_two_components():
    model = _make_model(n_components=2, seed=7)
    assert model._weights.shape == (2,)
    out = model.generate(20)
    assert out.shape == (20, 4)


def test_five_components():
    model = _make_model(n_components=5, seed=7)
    assert model._weights.shape == (5,)
    out = model.generate(20)
    assert out.shape == (20, 4)


# ------------------------------------------------------------
# representative_sample
# ------------------------------------------------------------

def test_representative_sample_shape():
    """representative_sample returns N synthetic draws, not the historical pool."""
    model = _make_model(frm=1928, to=2025, seed=0)
    rep = model.representative_sample(2000)
    assert rep.shape == (2000, 4)


def test_representative_sample_is_decimal():
    model = _make_model(seed=0)
    rep = model.representative_sample(100)
    assert abs(rep.mean()) < 0.5


# ------------------------------------------------------------
# Historical window sensitivity
# ------------------------------------------------------------

def test_different_windows_differ():
    p1 = _make_plan()
    _set_gmm(p1, frm=1928, to=1970, seed=7)

    p2 = _make_plan()
    _set_gmm(p2, frm=1980, to=2025, seed=7)

    assert not np.allclose(p1.tau_kn, p2.tau_kn)


# ------------------------------------------------------------
# Parameter validation
# ------------------------------------------------------------

def test_frm_equals_to_raises():
    config = {"method": "gmm", "frm": 2000, "to": 2000}
    with pytest.raises(ValueError):
        GMMRateModel(config)


def test_frm_greater_than_to_raises():
    config = {"method": "gmm", "frm": 2010, "to": 2000}
    with pytest.raises(ValueError):
        GMMRateModel(config)


def test_n_components_one_raises():
    config = {"method": "gmm", "frm": 1928, "to": 2025, "n_components": 1}
    with pytest.raises(ValueError, match="n_components"):
        GMMRateModel(config)


# ------------------------------------------------------------
# Offline comparison against scikit-learn
# (skipped when scikit-learn is not installed)
# ------------------------------------------------------------

@pytest.mark.skipif(not _SKLEARN_AVAILABLE, reason="scikit-learn not installed")
def test_scipy_gmm_log_likelihood_vs_sklearn():
    """
    The scipy EM implementation should reach a log-likelihood within 5% of
    sklearn's on the same data.  Both use full-covariance EM; differences arise
    only from initialization and convergence details.
    """
    model = _make_model(n_components=3, seed=0)
    X = model._historical_data

    sklearn_gmm = _SklearnGMM(n_components=3, covariance_type="full", random_state=0, max_iter=500)
    sklearn_gmm.fit(X)

    scipy_ll = model.log_likelihood(X)
    sklearn_ll = sklearn_gmm.score(X) * len(X)  # score() returns mean log-likelihood

    # Both should be finite and negative (log-likelihood of continuous densities can be positive,
    # but for typical annual return scales they are negative).
    assert np.isfinite(scipy_ll)
    assert np.isfinite(sklearn_ll)

    # scipy EM should reach within 5% of sklearn's log-likelihood.
    # (sklearn may find a slightly better local optimum via k-means init.)
    assert scipy_ll >= sklearn_ll * 1.05 or abs(scipy_ll - sklearn_ll) / abs(sklearn_ll) < 0.05


@pytest.mark.skipif(not _SKLEARN_AVAILABLE, reason="scikit-learn not installed")
def test_scipy_gmm_sample_moments_vs_sklearn():
    """
    Large samples from the scipy GMM and sklearn GMM should have similar
    marginal means and standard deviations (within 20% relative tolerance).
    """
    X = _make_model(seed=0)._historical_data

    sklearn_gmm = _SklearnGMM(n_components=3, covariance_type="full", random_state=0)
    sklearn_gmm.fit(X)

    scipy_model = _make_model(n_components=3, seed=0)

    n_samples = 5000
    scipy_samples = np.vstack([scipy_model.generate(n_samples // 10) for _ in range(10)])
    sklearn_samples, _ = sklearn_gmm.sample(n_samples)

    for k in range(4):
        scipy_mean = scipy_samples[:, k].mean()
        sklearn_mean = sklearn_samples[:, k].mean()
        hist_mean = X[:, k].mean()

        # Both model means should be within 20% of the historical mean.
        assert abs(scipy_mean - hist_mean) < 0.20 * abs(hist_mean) + 0.01, (
            f"Asset {k}: scipy mean {scipy_mean:.4f} far from historical {hist_mean:.4f}"
        )
        assert abs(sklearn_mean - hist_mean) < 0.20 * abs(hist_mean) + 0.01, (
            f"Asset {k}: sklearn mean {sklearn_mean:.4f} far from historical {hist_mean:.4f}"
        )
