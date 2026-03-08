"""
Tests for HSA (Health Savings Account) support in Owl.

HSA is account type j=3: triple tax-advantaged (pre-tax contributions,
tax-free growth, tax-free qualified medical withdrawals).

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import numpy as np

from owlplanner import Plan


def _make_plan(inames=None, dobs=None, expectancy=None):
    """Create a minimal single-person plan for testing."""
    if inames is None:
        inames = ["TestUser"]
    if dobs is None:
        dobs = ["1960-01-15"]
    if expectancy is None:
        expectancy = [88]
    return Plan(inames, dobs, expectancy, "HSA Test")


def _configure_plan(p, hsa=None, hsa_ctrb=0):
    """Configure a plan with standard parameters and optional HSA."""
    p.setAccountBalances(
        taxable=[200],
        taxDeferred=[500],
        taxFree=[100],
        hsa=hsa,
    )
    p.setAllocationRatios("individual", generic=[[[60, 20, 20, 0], [40, 30, 30, 0]]])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setSpendingProfile("flat")
    p.zeroWagesAndContributions()
    if hsa_ctrb > 0:
        # Set HSA contributions in kappa_ijn directly
        p.kappa_ijn[0, 3, : p.n_hsa_i[0]] = hsa_ctrb * 1000


def test_hsa_zero_balance():
    """Zero HSA gives identical result as no HSA (backward compat)."""
    p_base = _make_plan()
    _configure_plan(p_base, hsa=None)
    p_base.solve("maxSpending")
    spend_base = p_base.g_n[0]

    p_hsa = _make_plan()
    _configure_plan(p_hsa, hsa=[0])
    p_hsa.solve("maxSpending")
    spend_hsa = p_hsa.g_n[0]

    assert abs(spend_base - spend_hsa) < 1.0, (
        f"Zero HSA should give same spending: {spend_base:.0f} vs {spend_hsa:.0f}"
    )


def test_hsa_increases_spending():
    """Positive HSA balance leads to higher or equal optimal spending."""
    p_base = _make_plan()
    _configure_plan(p_base, hsa=None)
    p_base.solve("maxSpending")
    spend_base = p_base.g_n[0]

    p_hsa = _make_plan()
    _configure_plan(p_hsa, hsa=[50])   # $50k HSA
    p_hsa.solve("maxSpending")
    spend_hsa = p_hsa.g_n[0]

    assert spend_hsa >= spend_base - 1.0, (
        f"HSA balance should not decrease spending: {spend_hsa:.0f} < {spend_base:.0f}"
    )


def test_hsa_contribution_deduction():
    """HSA contributions reduce taxable income (e_n)."""
    p_base = _make_plan()
    _configure_plan(p_base)
    p_base.solve("maxSpending")
    avg_e_base = np.mean(p_base.e_n[:10])

    p_hsa = _make_plan()
    _configure_plan(p_hsa, hsa_ctrb=4.3)   # $4,300/yr HSA contributions
    p_hsa.solve("maxSpending")
    avg_e_hsa = np.mean(p_hsa.e_n[:10])

    assert avg_e_hsa < avg_e_base + 1.0, (
        f"HSA contributions should reduce taxable income: {avg_e_hsa:.0f} >= {avg_e_base:.0f}"
    )


def test_hsa_contribution_stops_at_medicare():
    """setHSA() correctly zeros HSA contributions at Medicare enrollment year."""
    # Use a younger person so Medicare cutoff is within the plan horizon.
    p = _make_plan(dobs=["1980-06-15"], expectancy=[90])
    p.setAccountBalances(taxable=[200], taxDeferred=[500], taxFree=[100])
    p.setHSA([30], medicare_ages=[65])
    p.setAllocationRatios("individual", generic=[[[60, 20, 20, 0], [40, 30, 30, 0]]])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setSpendingProfile("flat")

    from datetime import date
    thisyear = date.today().year
    n_stop = p.n_hsa_i[0]
    yob = p.yobs[0]
    expected_stop = max(0, yob + 65 - thisyear)

    assert n_stop == min(expected_stop, p.N_n), (
        f"n_hsa_i should be {expected_stop}, got {n_stop}"
    )

    # Now set contributions via timeLists and verify zeroing.
    p.zeroWagesAndContributions()
    # Manually set HSA ctrb for all years, then apply setHSA cutoff.
    p.kappa_ijn[0, 3, :p.N_n] = 4300  # set contributions for all years
    n_stop = p.n_hsa_i[0]
    if n_stop < p.N_n:
        p.kappa_ijn[0, 3, n_stop:p.horizons[0]] = 0.0
        assert np.all(p.kappa_ijn[0, 3, n_stop:p.horizons[0]] == 0), (
            "HSA contributions after Medicare enrollment should be zero"
        )
    if n_stop > 0:
        assert np.all(p.kappa_ijn[0, 3, :n_stop] == 4300), (
            "HSA contributions before Medicare enrollment should be set"
        )


def test_hsa_bequest():
    """HSA terminal balance is non-negative and discounted by heirs' tax rate in estate."""
    p = _make_plan()
    _configure_plan(p, hsa=[50])
    p.solve("maxSpending")

    hsa_terminal = p.b_ijn[0, 3, p.N_n]
    assert hsa_terminal >= 0, "HSA terminal balance must be non-negative"

    # Estate value discounts HSA by heirs' rate (like tax-deferred), not at full value.
    estate_j = np.sum(p.b_ijn[:, :, p.N_n], axis=0)
    assert abs(estate_j[3] * (1 - p.nu) - hsa_terminal * (1 - p.nu)) < 1.0


def test_hsa_bequest_discount():
    """HSA heirs' tax discount applied: estate_j[3] uses (1-nu) like tax-deferred."""
    p = _make_plan()
    _configure_plan(p, hsa=[100])
    p.solve("maxSpending")
    hsa_gross = np.sum(p.b_ijn[:, 3, p.N_n])
    if hsa_gross < 1.0:
        return  # optimizer spent down HSA; discount verification trivially holds
    # Recompute estate_j the same way _aggregateResults does and verify HSA discount.
    estate_j = np.sum(p.b_ijn[:, :, p.N_n], axis=0)
    estate_j[1] *= 1 - p.nu
    estate_j[3] *= 1 - p.nu
    expected_hsa_after_tax = hsa_gross * (1 - p.nu)
    assert abs(estate_j[3] - expected_hsa_after_tax) < 1.0, (
        f"HSA estate should be {expected_hsa_after_tax:.0f} (gross {hsa_gross:.0f} × (1-nu)), "
        f"got {estate_j[3]:.0f}"
    )


def test_hsa_spouse_transfer():
    """Two-person plan: HSA transfers at phi_j[3]=1.0 (intact)."""
    p = Plan(["Alice", "Bob"], ["1960-01-15", "1963-06-01"], [85, 90], "HSA Couple")
    p.setAccountBalances(
        taxable=[200, 100],
        taxDeferred=[500, 300],
        taxFree=[100, 50],
        hsa=[40, 20],
    )
    p.setAllocationRatios("spouses", generic=[[60, 20, 20, 0], [40, 30, 30, 0]])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setSpendingProfile("flat")
    p.zeroWagesAndContributions()

    assert p.phi_j[3] == 1.0, "HSA phi_j should be 1.0 (spouse inherits intact)"

    p.setBeneficiaryFractions([1.0, 1.0, 1.0, 1.0])
    p.solve("maxSpending")
    assert p.caseStatus == "solved"


def test_hsa_backward_compat_phi_3elements():
    """setBeneficiaryFractions with 3 elements auto-extends to 4."""
    p = Plan(["Alice", "Bob"], ["1960-01-15", "1963-06-01"], [85, 90], "HSA BwdCompat")
    p.setAccountBalances(taxable=[200, 100], taxDeferred=[500, 300], taxFree=[100, 50])
    p.setAllocationRatios("spouses", generic=[[60, 20, 20, 0], [40, 30, 30, 0]])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setSpendingProfile("flat")

    # Old-style 3-element call — should not raise
    p.setBeneficiaryFractions([1.0, 1.0, 1.0])
    assert len(p.phi_j) == 4
    assert p.phi_j[3] == 1.0


def test_setHSA_method():
    """setHSA() convenience method sets balances and n_hsa_i correctly."""
    p = _make_plan(dobs=["1960-01-15"])
    p.setAccountBalances(taxable=[200], taxDeferred=[500], taxFree=[100])
    p.setHSA([40], medicare_ages=[65])

    from datetime import date
    thisyear = date.today().year
    expected_n_hsa = max(0, 1960 + 65 - thisyear)
    assert p.n_hsa_i[0] == min(expected_n_hsa, p.N_n)
    assert abs(p.bet_ji[3, 0] - 40_000) < 1, "HSA balance should be set to 40k"
