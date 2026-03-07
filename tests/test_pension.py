"""
Tests for pension module - pension benefit timing calculations.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import numpy as np
import pytest
from datetime import date

from owlplanner import pension


def test_compute_pension_benefits_single():
    """Single individual: pi_in has correct shape and non-zero where expected."""
    thisyear = date.today().year
    yob = thisyear - 66  # 66 years old now
    amounts = np.array([1000.0])
    ages = np.array([65.0])
    yobs = np.array([yob])
    mobs = np.array([1])
    horizons = np.array([20])
    N_i, N_n = 1, 20

    pi_in = pension.compute_pension_benefits(
        amounts, ages, yobs, mobs, horizons, N_i, N_n, thisyear=thisyear
    )
    assert pi_in.shape == (1, 20)
    assert np.sum(pi_in) > 0
    assert np.sum(pi_in) == pytest.approx(12 * 1000 * 20, rel=0.01)  # ~full 20 years


def test_compute_pension_benefits_couple():
    """Two individuals: pi_in has correct shape."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 66, thisyear - 63])
    amounts = np.array([500.0, 0.0])
    ages = np.array([65.0, 65.0])
    mobs = np.array([1, 6])
    horizons = np.array([20, 20])
    N_i, N_n = 2, 20

    pi_in = pension.compute_pension_benefits(
        amounts, ages, yobs, mobs, horizons, N_i, N_n, thisyear=thisyear
    )
    assert pi_in.shape == (2, 20)
    assert np.sum(pi_in[0]) > 0
    assert np.sum(pi_in[1]) == 0


def test_compute_pension_benefits_zero_amounts():
    """All zero amounts: pi_in is all zeros."""
    thisyear = date.today().year
    amounts = np.array([0.0, 0.0])
    ages = np.array([65.0, 65.0])
    yobs = np.array([thisyear - 66, thisyear - 63])
    mobs = np.array([1, 1])
    horizons = np.array([20, 20])
    N_i, N_n = 2, 20

    pi_in = pension.compute_pension_benefits(
        amounts, ages, yobs, mobs, horizons, N_i, N_n, thisyear=thisyear
    )
    assert np.all(pi_in == 0)


def test_compute_pension_benefits_annual_conversion():
    """Output is annual (monthly × 12)."""
    thisyear = date.today().year
    amounts = np.array([100.0])  # $100/month
    ages = np.array([50.0])  # Start in past
    yobs = np.array([thisyear - 55])  # 55 now, started at 50
    mobs = np.array([1])
    horizons = np.array([10])
    N_i, N_n = 1, 10

    pi_in = pension.compute_pension_benefits(
        amounts, ages, yobs, mobs, horizons, N_i, N_n, thisyear=thisyear
    )
    # Should be 100*12 = 1200 per year for years 0-9 (already started)
    assert np.all(pi_in[0] == 1200)


def test_pension_survivor_benefit_added_to_pibar():
    """
    Couple with different life expectancies: first-to-die has pension with 50% J&S.
    Verify survivor receives 50% of primary's pension in piBar_in from n_d onward.
    """
    import owlplanner as owl

    # Jack (0) born 1960, lives to 85; Jill (1) born 1962, lives to 90.
    # Jack dies first → i_d=0, i_s=1, n_d = Jack's horizon.
    p = owl.Plan(
        ["Jack", "Jill"],
        ["1960-01-15", "1962-01-15"],
        [85, 90],
        "pension survivor test",
    )
    p.setSpendingProfile("flat", 50)
    p.setAccountBalances(
        taxable=[100, 100], taxDeferred=[200, 200], taxFree=[50, 50], startDate="1-1"
    )
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]] * 2)
    p.setSocialSecurity([0, 0], [67, 67])
    # Jack: $1000/month ($12k/year), 50% survivor. Jill: no pension.
    p.setPension([1000, 0], [65, 65], indexed=[False, False], survivor_fraction=[0.5, 0])
    p.setRates("user", values=[0.05, 0.03, 0.02, 0.01])

    p.solve("maxSpending", options={"maxRothConversion": 0, "withSCLoop": False})

    assert p.caseStatus == "solved"
    assert p.N_i == 2
    assert p.n_d < p.N_n  # Jack dies before plan end
    assert p.i_d == 0 and p.i_s == 1

    # Primary's last year amount (non-indexed): $12k
    primary_last = p.piBar_in[0, p.n_d - 1]
    assert primary_last == pytest.approx(12000, rel=0.01)

    # Survivor should receive 50% = $6k/year from n_d until her horizon
    survivor_amt = 0.5 * primary_last
    for n in range(p.n_d, p.horizons[1]):
        assert p.piBar_in[1, n] >= survivor_amt * 0.99, (
            f"Survivor piBar_in[1,{n}]={p.piBar_in[1, n]:.0f} "
            f"expected >= {survivor_amt:.0f}"
        )


def test_compute_piBar_in_rate_sensitivity():
    """
    Verify piBar_in responds correctly to rate/inflation (gamma_n) changes:
    - Non-indexed: piBar_in = pi_in (independent of gamma)
    - Indexed: piBar_in scales with gamma_n
    - Survivor amount scales with primary's piBar (inherits indexing)
    """
    N_i, N_n = 2, 10
    # Simple pi_in: person 0 gets 12k/year in years 0-4, person 1 gets 0
    pi_in = np.zeros((N_i, N_n))
    pi_in[0, :5] = 12000
    horizons = np.array([5, 10])  # person 0 dies at n_d=5, person 1 survives to 10
    n_d, i_d, i_s = 5, 0, 1

    # Case 1: Non-indexed — piBar should equal pi_in regardless of gamma
    gamma_flat = np.ones(N_n)
    gamma_2x = np.linspace(1.0, 2.0, N_n)  # inflation grows 1 -> 2
    for gamma in (gamma_flat, gamma_2x):
        piBar = pension.compute_piBar_in(
            pi_in, gamma,
            indexed=[False, False],
            survivor_fraction=np.array([0.5, 0.0]),
            n_d=n_d, i_d=i_d, i_s=i_s,
            horizons=horizons, N_i=N_i, N_n=N_n,
        )
        np.testing.assert_array_almost_equal(piBar[0], pi_in[0], err_msg="Non-indexed: piBar should equal pi_in")
        # Survivor gets 6k (50% of 12k), constant
        assert piBar[1, 5] == pytest.approx(6000)
        assert piBar[1, 9] == pytest.approx(6000)

    # Case 2: Indexed — piBar should scale with gamma
    piBar_flat = pension.compute_piBar_in(
        pi_in, gamma_flat,
        indexed=[True, False],
        survivor_fraction=np.array([0.5, 0.0]),
        n_d=n_d, i_d=i_d, i_s=i_s,
        horizons=horizons, N_i=N_i, N_n=N_n,
    )
    piBar_2x = pension.compute_piBar_in(
        pi_in, gamma_2x,
        indexed=[True, False],
        survivor_fraction=np.array([0.5, 0.0]),
        n_d=n_d, i_d=i_d, i_s=i_s,
        horizons=horizons, N_i=N_i, N_n=N_n,
    )
    # Primary: piBar[0,n] = pi_in[0,n] * gamma[n]; ratio should equal gamma ratio
    for n in range(5):
        if piBar_flat[0, n] != 0:
            ratio = piBar_2x[0, n] / piBar_flat[0, n]
            assert ratio == pytest.approx(gamma_2x[n] / gamma_flat[n], rel=1e-10)
    # Survivor: raw amount = 0.5 * pi_in[i_d, n_d-1] = 6000 (pre-inflation),
    # then inflated by gamma_n[n] per year (inheriting primary's indexing).
    # With gamma_flat: survivor = 6000 * 1.0 = 6000 in every year.
    # With gamma_2x: survivor = 6000 * gamma_2x[n] (grows with inflation).
    assert piBar_flat[1, 5] == pytest.approx(6000)
    assert piBar_2x[1, 5] == pytest.approx(6000 * gamma_2x[5], rel=0.01)
    assert piBar_2x[1, 9] == pytest.approx(6000 * gamma_2x[9], rel=0.01)
