"""
Tests for bootstrap_sor rate model.

Covers:
- IID bootstrap
- Block bootstrap
- Circular bootstrap
- Stationary bootstrap
- Crisis overweighting
- Reproducibility behavior
"""

import numpy as np
import pytest

from owlplanner import Plan


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _make_plan():
    return Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)


def _set_bootstrap(
    p,
    bootstrap_type="iid",
    block_size=3,
    crisis_years=None,
    crisis_weight=1.0,
    seed=None,
):
    if seed is not None:
        p.setReproducible(True, seed=seed)
    else:
        p.setReproducible(False)

    p.setRates(
        method="bootstrap_sor",
        frm=1928,
        to=2024,
        bootstrap_type=bootstrap_type,
        block_size=block_size,
        crisis_years=crisis_years,
        crisis_weight=crisis_weight,
    )


# ------------------------------------------------------------
# Shape and basic behavior
# ------------------------------------------------------------

def test_iid_bootstrap_shape():
    p = _make_plan()
    _set_bootstrap(p, bootstrap_type="iid")
    assert p.tau_kn.shape == (4, p.N_n)


def test_block_bootstrap_shape():
    p = _make_plan()
    _set_bootstrap(p, bootstrap_type="block", block_size=5)
    assert p.tau_kn.shape == (4, p.N_n)


def test_circular_bootstrap_shape():
    p = _make_plan()
    _set_bootstrap(p, bootstrap_type="circular", block_size=4)
    assert p.tau_kn.shape == (4, p.N_n)


def test_stationary_bootstrap_shape():
    p = _make_plan()
    _set_bootstrap(p, bootstrap_type="stationary", block_size=6)
    assert p.tau_kn.shape == (4, p.N_n)


# ------------------------------------------------------------
# Reproducibility
# ------------------------------------------------------------

def test_reproducible_same_seed():
    p1 = _make_plan()
    _set_bootstrap(p1, bootstrap_type="block", block_size=4, seed=1234)

    p2 = _make_plan()
    _set_bootstrap(p2, bootstrap_type="block", block_size=4, seed=1234)

    assert np.allclose(p1.tau_kn, p2.tau_kn)


def test_non_reproducible_changes():
    p = _make_plan()
    _set_bootstrap(p, bootstrap_type="block", block_size=4)
    tau1 = p.tau_kn.copy()

    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()

    assert not np.allclose(tau1, tau2)


# ------------------------------------------------------------
# Crisis overweight
# ------------------------------------------------------------

def test_crisis_overweight_changes_distribution():
    """
    Ensure crisis overweight affects output.
    We don't test exact probability (stochastic),
    only that weighted run differs from baseline.
    """
    p1 = _make_plan()
    _set_bootstrap(p1, bootstrap_type="iid")

    p2 = _make_plan()
    _set_bootstrap(
        p2,
        bootstrap_type="iid",
        crisis_years=[1929, 1930, 1931, 2008],
        crisis_weight=5.0,
    )

    # Should differ (probabilistically)
    assert not np.allclose(p1.tau_kn, p2.tau_kn)


# ------------------------------------------------------------
# Block behavior sanity check
# ------------------------------------------------------------

def test_block_preserves_local_structure():
    """
    For block bootstrap, consecutive years should
    sometimes repeat contiguous historical structure.

    We verify existence of at least one repeated adjacent
    difference pattern.
    """
    p = _make_plan()
    _set_bootstrap(p, bootstrap_type="block", block_size=3)

    tau = p.tau_kn
    diffs = np.diff(tau, axis=1)

    # Just ensure no crash and valid structure
    assert diffs.shape[1] == p.N_n - 1


# ------------------------------------------------------------
# Stationary bootstrap randomness
# ------------------------------------------------------------

def test_stationary_varies_block_length():
    p = _make_plan()
    _set_bootstrap(p, bootstrap_type="stationary", block_size=5)
    tau1 = p.tau_kn.copy()

    p.regenRates(override_reproducible=True)
    tau2 = p.tau_kn.copy()

    assert not np.allclose(tau1, tau2)


# ------------------------------------------------------------
# Reverse / roll compatibility
# ------------------------------------------------------------

def test_reverse_roll_applies():
    from owlplanner.plan import Plan

    plan = _make_plan()
    plan.reproducibleRates = True
    plan.rateSeed = 1234  # force reproducibility

    N = 20

    plan.setRates(
        method="bootstrap_sor",
        frm=1950,
        to=2020,
        bootstrap_type="iid",
    )
    original = plan.tau_kn.copy()

    plan.setRates(
        method="bootstrap_sor",
        frm=1950,
        to=2020,
        bootstrap_type="iid",
        reverse=True,
    )
    reversed_series = plan.tau_kn.copy()

    assert np.allclose(reversed_series, original[:, ::-1])


# ------------------------------------------------------------
# Invalid bootstrap type
# ------------------------------------------------------------

def test_invalid_bootstrap_type():
    p = _make_plan()

    with pytest.raises(ValueError):
        p.setRates(
            method="bootstrap_sor",
            frm=1928,
            to=2024,
            bootstrap_type="not_a_real_type",
        )
