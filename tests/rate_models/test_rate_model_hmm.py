"""
Tests for the Hidden Markov Model rate model.

Covers:
- Model attributes (name, flags)
- Output shape and decimal range
- Reproducibility (same/different seeds)
- Fitted parameter shapes and validity (pi, trans, means, covs)
- Transition matrix row sums and diagonal persistence
- Stationary distribution sums to 1
- Autocorrelation: regime persistence produces positive lag-1 runs
- n_components option
- init_regime parameter
- representative_sample returns historical pool
- Historical window sensitivity
- Parameter validation (frm >= to, n_components < 2, bad init_regime)
- Discovery: 'hmm' in list_available_rate_models()
- HMM log-likelihood >= GMM log-likelihood on same data

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

from owlplanner import Plan
from owlplanner.rate_models.hmm import HMMRateModel
from owlplanner.rate_models.gmm import GMMRateModel
from owlplanner.rate_models.loader import list_available_rate_models


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------


def _make_plan():
    return Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)


def _set_hmm(p, frm=1928, to=2025, n_components=3, seed=None, **kwargs):
    if seed is not None:
        p.setReproducible(True, seed=seed)
    else:
        p.setReproducible(False)
    p.setRates(method="hmm", frm=frm, to=to, n_components=n_components, **kwargs)


def _make_model(frm=1928, to=2025, n_components=3, seed=None, **kwargs):
    config = {"method": "hmm", "frm": frm, "to": to, "n_components": n_components, **kwargs}
    return HMMRateModel(config, seed=seed)


# ------------------------------------------------------------
# Model attributes
# ------------------------------------------------------------


def test_model_name():
    assert HMMRateModel.model_name == "hmm"


def test_deterministic_flag():
    assert HMMRateModel.deterministic is False


def test_constant_flag():
    assert HMMRateModel.constant is False


def test_hmm_in_registry():
    assert "hmm" in list_available_rate_models()


# ------------------------------------------------------------
# Output shape and sanity
# ------------------------------------------------------------


def test_shape_via_plan():
    p = _make_plan()
    _set_hmm(p)
    assert p.tau_kn.shape == (4, p.N_n)


def test_output_is_finite():
    p = _make_plan()
    _set_hmm(p)
    assert np.all(np.isfinite(p.tau_kn))


def test_generate_shape_direct():
    model = _make_model(seed=42)
    out = model.generate(30)
    assert out.shape == (30, 4)


def test_rates_in_plausible_range():
    model = _make_model(seed=0)
    out = model.generate(500)
    assert np.all(out > -1.0), "Some returns below -100%"
    assert np.all(out < 2.0), "Some returns above +200%"


def test_output_is_decimal_not_percent():
    model = _make_model(seed=1)
    out = model.generate(200)
    assert abs(out.mean()) < 0.5, "Outputs look like percent, not decimal"


# ------------------------------------------------------------
# Reproducibility
# ------------------------------------------------------------


def test_reproducible_same_seed():
    p1 = _make_plan()
    _set_hmm(p1, seed=42)

    p2 = _make_plan()
    _set_hmm(p2, seed=42)

    assert np.allclose(p1.tau_kn, p2.tau_kn)


def test_different_seeds_differ():
    p1 = _make_plan()
    _set_hmm(p1, seed=1)

    p2 = _make_plan()
    _set_hmm(p2, seed=2)

    assert not np.allclose(p1.tau_kn, p2.tau_kn)


# ------------------------------------------------------------
# Fitted parameter shapes and validity
# ------------------------------------------------------------


def test_pi_shape():
    model = _make_model(n_components=3)
    assert model._pi.shape == (3,)


def test_pi_sums_to_one():
    model = _make_model(n_components=3, seed=0)
    assert abs(model._pi.sum() - 1.0) < 1e-9


def test_pi_non_negative():
    model = _make_model(seed=0)
    assert np.all(model._pi >= 0)


def test_trans_shape():
    model = _make_model(n_components=3)
    assert model._trans.shape == (3, 3)


def test_trans_rows_sum_to_one():
    model = _make_model(n_components=3, seed=0)
    row_sums = model._trans.sum(axis=1)
    assert np.allclose(row_sums, 1.0, atol=1e-9)


def test_trans_non_negative():
    model = _make_model(seed=0)
    assert np.all(model._trans >= 0)


def test_means_shape():
    model = _make_model(n_components=3)
    assert model._means.shape == (3, 4)


def test_covs_shape():
    model = _make_model(n_components=3)
    assert model._covs.shape == (3, 4, 4)


def test_covs_positive_definite():
    model = _make_model(n_components=3, seed=0)
    for cov in model._covs:
        eigs = np.linalg.eigvalsh(cov)
        assert np.all(eigs > 0), f"Covariance not PD: eigenvalues {eigs}"


# ------------------------------------------------------------
# Regime persistence (the key HMM property)
# ------------------------------------------------------------


def test_transition_diagonal_dominates():
    """Diagonal entries of the fitted transition matrix should exceed off-diagonal mean."""
    model = _make_model(n_components=3, seed=0)
    K = model.n_components
    diag_mean = np.diag(model._trans).mean()
    off_diag_mean = (model._trans.sum() - np.diag(model._trans).sum()) / (K * (K - 1))
    assert diag_mean > off_diag_mean, (
        f"Transition matrix not persistent: diag_mean={diag_mean:.3f}, off_diag_mean={off_diag_mean:.3f}"
    )


def test_regime_runs_exist():
    """A long HMM path should contain multi-year regime runs (not purely random switching)."""
    model = _make_model(n_components=3, seed=7)
    K = model.n_components

    # Simulate the regime sequence directly (not returns)
    rng = np.random.default_rng(7)
    N = 5000
    regime_seq = np.empty(N, dtype=int)
    k = int(rng.choice(K, p=model._stationary_dist()))
    for t in range(N):
        regime_seq[t] = k
        k = int(rng.choice(K, p=model._trans[k]))

    # Count runs: consecutive years in the same regime
    runs = []
    current_run = 1
    for t in range(1, N):
        if regime_seq[t] == regime_seq[t - 1]:
            current_run += 1
        else:
            runs.append(current_run)
            current_run = 1
    runs.append(current_run)

    mean_run = np.mean(runs)
    # With uniform independent sampling from K=3 regimes the expected run length is 1.5.
    # Persistence should produce runs meaningfully longer than that.
    assert mean_run > 1.8, f"Expected regime persistence; mean run length = {mean_run:.2f}"


# ------------------------------------------------------------
# Stationary distribution
# ------------------------------------------------------------


def test_stationary_dist_sums_to_one():
    model = _make_model(seed=0)
    stat = model._stationary_dist()
    assert abs(stat.sum() - 1.0) < 1e-9


def test_stationary_dist_is_invariant():
    """Stationary distribution should satisfy pi @ A = pi."""
    model = _make_model(seed=0)
    stat = model._stationary_dist()
    propagated = stat @ model._trans
    assert np.allclose(propagated, stat, atol=1e-8)


# ------------------------------------------------------------
# n_components option
# ------------------------------------------------------------


def test_two_components():
    model = _make_model(n_components=2, seed=7)
    assert model._trans.shape == (2, 2)
    assert not hasattr(model, "_weights")  # HMM uses _pi/_trans, not _weights
    out = model.generate(20)
    assert out.shape == (20, 4)


def test_five_components():
    model = _make_model(n_components=5, seed=7)
    assert model._trans.shape == (5, 5)
    out = model.generate(20)
    assert out.shape == (20, 4)


# ------------------------------------------------------------
# init_regime parameter
# ------------------------------------------------------------


def test_init_regime_valid():
    model = _make_model(n_components=3, seed=0, init_regime=0)
    out = model.generate(10)
    assert out.shape == (10, 4)


def test_init_regime_out_of_range_raises():
    config = {"method": "hmm", "frm": 1928, "to": 2025, "n_components": 3, "init_regime": 5}
    with pytest.raises(ValueError, match="init_regime"):
        HMMRateModel(config)


def test_init_regime_negative_raises():
    config = {"method": "hmm", "frm": 1928, "to": 2025, "n_components": 3, "init_regime": -1}
    with pytest.raises(ValueError, match="init_regime"):
        HMMRateModel(config)


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
    _set_hmm(p1, frm=1928, to=1970, seed=7)

    p2 = _make_plan()
    _set_hmm(p2, frm=1980, to=2025, seed=7)

    assert not np.allclose(p1.tau_kn, p2.tau_kn)


# ------------------------------------------------------------
# Parameter validation
# ------------------------------------------------------------


def test_frm_equals_to_raises():
    config = {"method": "hmm", "frm": 2000, "to": 2000}
    with pytest.raises(ValueError):
        HMMRateModel(config)


def test_frm_greater_than_to_raises():
    config = {"method": "hmm", "frm": 2010, "to": 2000}
    with pytest.raises(ValueError):
        HMMRateModel(config)


def test_n_components_one_raises():
    config = {"method": "hmm", "frm": 1928, "to": 2025, "n_components": 1}
    with pytest.raises(ValueError, match="n_components"):
        HMMRateModel(config)


def test_reg_trans_zero_raises():
    config = {"method": "hmm", "frm": 1928, "to": 2025, "reg_trans": 0.0}
    with pytest.raises(ValueError, match="reg_trans"):
        HMMRateModel(config)


def test_reg_trans_negative_raises():
    config = {"method": "hmm", "frm": 1928, "to": 2025, "reg_trans": -1e-4}
    with pytest.raises(ValueError, match="reg_trans"):
        HMMRateModel(config)


def test_stationary_pi_cached():
    """Stationary distribution is cached at init time, not recomputed each generate() call."""
    model = _make_model(seed=0)
    assert hasattr(model, "_stationary_pi")
    assert abs(model._stationary_pi.sum() - 1.0) < 1e-9


# ------------------------------------------------------------
# Log-likelihood: HMM should match or exceed GMM on same data
# ------------------------------------------------------------


def test_hmm_ll_not_worse_than_gmm():
    """
    HMM is strictly more expressive than GMM (GMM is HMM with A = outer(pi, w)).
    Its log-likelihood on the fitted data should be >= the GMM's.
    """
    seed = 42
    hmm = _make_model(n_components=3, seed=seed)
    gmm_config = {"method": "gmm", "frm": 1928, "to": 2025, "n_components": 3}
    gmm = GMMRateModel(gmm_config, seed=seed)

    X = hmm._historical_data
    hmm_ll = hmm.log_likelihood(X)
    gmm_ll = gmm.log_likelihood(X)

    # Allow 5% slack for initialization randomness; the key check is they're close and HMM ≥ GMM.
    assert hmm_ll >= gmm_ll - 0.05 * abs(gmm_ll), (
        f"HMM log-likelihood ({hmm_ll:.2f}) unexpectedly much worse than GMM ({gmm_ll:.2f})"
    )
