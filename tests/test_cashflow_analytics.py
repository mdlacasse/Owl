"""
Cashflow and reporting checks for Owl.

These tests compare LP results to closed-form identities where the scenario pins
the optimum (e.g. pure Roth trajectories, flat spending vs inflation). They also
assert internal consistency of post-solve reporting (e.g. ``bequest`` vs
terminal balances) and document optimizer behavior when the optimum relocates
tax-deferred wealth into taxable under ``maxBequest`` with no other ordinary
income (retiree marginal tax below the modeled heir wedge on traditional
balances).

  Test 1  tax-deferred bequest: closed-form when TD survives to death, else relocation FV
  Test 2  year-by-year Roth balance trajectory (intermediate values)
  Test 3  nominal spending array g_n[n] follows cumulative inflation
  Test 4  mixed j=1 + j=2 bequest (same split as test 1)
  Test 5  annuity formula for j=1 (tax-deferred, below standard deduction)
  Test 6  zero real return: rate == inflation => g = B0/N
  Test 7  pension income leaves Roth portfolio intact (zero Roth withdrawals)
  Test 8  explicit relocation: maxBequest with no other income drains j=1 to j=0

Shared solver options disable the SC loop and Medicare.

Formula reference
-----------------
  Compound interest    FV  = PV * (1 + r)^N
  Annuity-due (start)  PMT = PV * r / ((1 - (1+r)^-N) * (1+r))
  Zero real return     g   = B0 / N   when r == pi (gamma_n/cum_r_n == 1)
  Inflation array      g_n[n] = basis * gamma_n[n]  (flat spending profile)

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from datetime import date
import numpy as np

import owlplanner as owl

solver = 'HiGHS'

# Shared solver options that eliminate all SC-loop features.
_BASE = {
    'maxRothConversion': 0,
    'solver': solver,
    'withSCLoop': False,
    'withMedicare': False,
}


def createPlan(ni, name, ny, topAge):
    """Year-independent plan helper (mirrors test_regressions.createPlan)."""
    assert ny >= 2
    thisyear = date.today().year
    ny -= 1
    if ni == 1:
        inames = ['Joe']
        expectancy = [topAge]
        yobs = [thisyear - topAge + ny]
        dobs = [f"{yobs[0]}-01-15"]
    else:
        inames = ['Joe', 'Jane']
        expectancy = [topAge - 2, topAge]
        yobs = [thisyear - topAge + ny, thisyear - topAge + ny]
        dobs = [f"{yobs[0]}-01-15", f"{yobs[1]}-01-16"]
    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile('flat', 100)
    return p


def _bequest_from_terminal_balances(p):
    """Mirror plan.py terminal estate_j / bequest (today's dollars)."""
    Nn = p.N_n
    nu = p.nu
    estate_j = np.sum(p.b_ijn[:, :, Nn], axis=0).copy()
    estate_j[1] *= 1 - nu
    estate_j[3] *= 1 - nu
    total_estate = np.sum(estate_j) - p.remaining_debt_balance
    return max(0.0, total_estate) / p.gamma_n[-1]


def _assert_bequest_matches_aggregate(p):
    np.testing.assert_allclose(
        _bequest_from_terminal_balances(p),
        p.bequest,
        rtol=0,
        atol=0.02,
        err_msg="bequest disagrees with terminal b_ijn + estate_j rules",
    )


# ---------------------------------------------------------------------------
# Test 1: Tax-deferred (j=1) compounding with heir-tax discount
#
# When tax-deferred wealth remains in j=1 at the last node, heirs tax nu
# applies in reporting: bequest = FV * (1-nu) / gamma_N (today's $).
#
# With no wages/other income, maxBequest may optimally relocate j=1 into j=0
# at ~0 retiree marginal tax; then nu is not applied to that wealth and
# bequest ~= nominal FV / gamma_N. This test accepts either regime and always
# checks that p.bequest matches aggregation from terminal b_ijn.
# ---------------------------------------------------------------------------

def test_taxdeferred_compounding():
    """TD bequest: closed-form if j=1 survives; else relocation to j=0 (aggregate invariant)."""
    n, amount, rate = 12, 120, 4
    p = createPlan(1, 'td_compound', n, 72)
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    p.setRates('user', values=[0, 0, rate, 0])
    p.setHeirsTaxRate(30)
    p.solve('maxBequest', options={**_BASE, 'netSpending': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    _assert_bequest_matches_aggregate(p)
    fv_nom = 1000 * amount * (1 + rate / 100) ** n
    td_terminal = float(np.sum(p.b_ijn[:, 1, p.N_n]))
    if td_terminal > 1.0:
        assert p.bequest == pytest.approx(fv_nom * (1 - p.nu) / p.gamma_n[-1], abs=1.0)
    else:
        assert td_terminal < 1.0
        assert float(np.sum(p.b_ijn[:, 0, p.N_n])) > 1000.0


def test_taxdeferred_compounding_couple():
    """Couple TD bequest: same logic as single (phi transfer + aggregation)."""
    n, amount, rate = 12, 120, 4
    p = createPlan(2, 'td_compound_couple', n, 72)
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[amount/2, amount/2],
                         taxFree=[0, 0], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    p.setRates('user', values=[0, 0, rate, 0])
    p.setHeirsTaxRate(30)
    p.solve('maxBequest', options={**_BASE, 'netSpending': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    _assert_bequest_matches_aggregate(p)
    fv_nom = 1000 * amount * (1 + rate / 100) ** n
    td_terminal = float(np.sum(p.b_ijn[:, 1, p.N_n]))
    if td_terminal > 1.0:
        assert p.bequest == pytest.approx(fv_nom * (1 - p.nu) / p.gamma_n[-1], abs=1.0)
    else:
        assert td_terminal < 1.0
        assert float(np.sum(p.b_ijn[:, 0, p.N_n])) > 1000.0


# ---------------------------------------------------------------------------
# Test 2: Year-by-year Roth balance trajectory
#
# Formula:  b_ijn[0, 2, n] = b0 * (1+r)^n  for n = 0 .. N
#
# Existing tests check only the FINAL bequest scalar. This verifies that the
# compound formula holds at every intermediate year, exercising the balance
# carryover constraint b[n+1] = Tau1 * b[n] for all years.
# ---------------------------------------------------------------------------

def test_yearly_balance_trajectory():
    """b_ijn[0,2,n] matches b0*(1+r)^n at every year from 0 to N."""
    n, amount, rate = 10, 100, 5
    p = createPlan(1, 'balance_traj', n, 70)
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    p.setRates('user', values=[0, 0, rate, 0])
    p.solve('maxBequest', options={**_BASE, 'netSpending': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    _assert_bequest_matches_aggregate(p)
    expected = 1000 * amount * (1 + rate/100)**np.arange(n + 1)
    np.testing.assert_allclose(
        p.b_ijn[0, 2, :], expected, rtol=1e-5,
        err_msg="Roth balance does not match compound formula at every year",
    )


# ---------------------------------------------------------------------------
# Test 3: Nominal spending array follows cumulative inflation
#
# Formula:  g_n[n] = basis * gamma_n[n]   (flat profile, xi_n == 1)
#
# Existing tests check only the scalar `basis` (today's dollars). This verifies
# the full array structure, confirming that nominal spending = real basis times
# the cumulative inflation multiplier for every year in the plan.
# ---------------------------------------------------------------------------

def test_nominal_spending_array_inflation():
    """g_n[n] == basis * gamma_n[n] for all years (flat profile, 2% inflation)."""
    n, amount, rate, pi = 15, 120, 4, 2
    p = createPlan(1, 'spend_inflation', n, 75)
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    p.setRates('user', values=[0, 0, rate, pi])
    p.solve('maxSpending', options={**_BASE, 'bequest': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    N = p.N_n
    np.testing.assert_allclose(
        p.g_n[:N], p.basis * p.gamma_n[:N], rtol=1e-5,
        err_msg="Nominal spending does not equal basis * gamma_n at each year",
    )


# ---------------------------------------------------------------------------
# Test 4: Mixed j=1 + j=2 combined bequest with asymmetric heir-tax
#
# If j=1 survives at the terminal node: bequest matches
#   b1*(1+r)^N*(1-nu) + b2*(1+r)^N  (today's $ after /gamma_N).
# If j=1 is drained into j=0, nu does not apply to that wealth; with j=2
# untouched, bequest ~= (b1+b2)*(1+r)^N / gamma_N.
# ---------------------------------------------------------------------------

def test_mixed_accounts_bequest():
    """Mixed j=1 + j=2: closed-form if TD at death; else full FV / gamma."""
    n, rate, b1, b2 = 12, 4, 60, 60
    p = createPlan(1, 'mixed_bequest', n, 72)
    p.setAccountBalances(taxable=[0], taxDeferred=[b1], taxFree=[b2], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    p.setRates('user', values=[0, 0, rate, 0])
    p.setHeirsTaxRate(30)
    p.solve('maxBequest', options={**_BASE, 'netSpending': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    _assert_bequest_matches_aggregate(p)
    r = rate / 100
    td_terminal = float(np.sum(p.b_ijn[:, 1, p.N_n]))
    if td_terminal > 1.0:
        expected = 1000 * (b1 * (1 + r)**n * (1 - p.nu) + b2 * (1 + r)**n) / p.gamma_n[-1]
        assert p.bequest == pytest.approx(expected, abs=1.0)
    else:
        assert td_terminal < 1.0
        assert float(np.sum(p.b_ijn[:, 0, p.N_n])) > 1.0


def test_mixed_accounts_bequest_couple():
    """Couple mixed accounts: same regime split as single."""
    n, rate, b1, b2 = 12, 4, 60, 60
    p = createPlan(2, 'mixed_bequest_couple', n, 72)
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[b1/2, b1/2],
                         taxFree=[b2/2, b2/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    p.setRates('user', values=[0, 0, rate, 0])
    p.setHeirsTaxRate(30)
    p.solve('maxBequest', options={**_BASE, 'netSpending': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    _assert_bequest_matches_aggregate(p)
    r = rate / 100
    td_terminal = float(np.sum(p.b_ijn[:, 1, p.N_n]))
    if td_terminal > 1.0:
        expected = 1000 * (b1 * (1 + r)**n * (1 - p.nu) + b2 * (1 + r)**n) / p.gamma_n[-1]
        assert p.bequest == pytest.approx(expected, abs=1.0)
    else:
        assert td_terminal < 1.0
        assert float(np.sum(p.b_ijn[:, 0, p.N_n])) > 1.0


# ---------------------------------------------------------------------------
# Test 5: Annuity formula for tax-deferred account (no effective income tax)
#
# Formula:  PMT = b0 * r / ((1 - (1+r)^-N) * (1+r))   (start-of-period)
#
# All existing annuity tests use Roth (j=2). For j=1 (tax-deferred), the
# same formula holds only when annual withdrawals fall below the standard
# deduction so that no income tax is owed. With b0=40k and r=4% over 10
# years, each withdrawal is ~$4,800/year << $15k standard deduction.
# ---------------------------------------------------------------------------

def test_taxdeferred_annuity():
    """Start-of-period annuity-due formula matches j=1 spending (no income tax)."""
    n, amount, rate = 10, 40, 4
    p = createPlan(1, 'td_annuity', n, 70)
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    p.setRates('user', values=[0, 0, rate, 0])
    p.solve('maxSpending', options={**_BASE, 'bequest': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    r = rate / 100
    expected = 1000 * amount * r / ((1 - (1 + r)**-n) * (1 + r))
    assert p.basis == pytest.approx(expected, abs=0.5)


def test_taxdeferred_annuity_couple():
    """Same annuity formula holds for a couple's combined j=1 balance."""
    n, amount, rate = 10, 40, 4
    p = createPlan(2, 'td_annuity_couple', n, 70)
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[amount/2, amount/2],
                         taxFree=[0, 0], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    p.setRates('user', values=[0, 0, rate, 0])
    p.solve('maxSpending', options={**_BASE, 'bequest': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    r = rate / 100
    expected = 1000 * amount * r / ((1 - (1 + r)**-n) * (1 + r))
    assert p.basis == pytest.approx(expected, abs=0.5)


# ---------------------------------------------------------------------------
# Test 6: Zero real return collapses annuity to uniform withdrawal
#
# Formula:  g = B0 / N   when r == pi
#
# Derivation: annuity formula g = B0 / sum_n(gamma_n[n]/cum_r_n).
# When r == pi, gamma_n[n]/cum_r_n = (1+pi)^n / (1+r)^n = 1 for all n,
# so sum = N and g = B0/N.
#
# Existing taxfreegrowth5-8 test the BEQUEST side (rate=inflation => real
# bequest unchanged). This tests the SPENDING side of the same identity.
# ---------------------------------------------------------------------------

def test_zero_real_return_annuity():
    """With rate == inflation, g = B0/N (annuity collapses to uniform withdrawal)."""
    n, amount, rate = 15, 120, 4
    p = createPlan(1, 'zero_real', n, 75)
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    p.setRates('user', values=[0, 0, rate, rate])   # pi == r
    p.solve('maxSpending', options={**_BASE, 'bequest': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    assert p.basis == pytest.approx(1000 * amount / n, abs=0.5)


def test_zero_real_return_annuity_couple():
    """Zero real return formula for a couple with 1-year horizon difference."""
    n, amount, rate = 15, 120, 4
    thisyear = date.today().year
    topAge = 75
    # Construct a couple where the surviving spouse still has n total years,
    # matching the N_n used in the formula. Use a 1-year horizon difference
    # (instead of createPlan's 2-year) so the formula stays n = topAge horizon.
    yob = thisyear - topAge + (n - 1)
    p = owl.Plan(
        ['Joe', 'Jane'],
        [f"{yob}-01-15", f"{yob}-01-16"],
        [topAge - 1, topAge],
        'zero_real_couple',
    )
    p.setSpendingProfile('flat', 100)
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    p.setRates('user', values=[0, 0, rate, rate])
    p.solve('maxSpending', options={**_BASE, 'bequest': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    assert p.basis == pytest.approx(1000 * amount / n, abs=0.5)


# ---------------------------------------------------------------------------
# Test 7: Pension income leaves Roth portfolio intact
#
# Formula:  b_ijn[0, 2, N_n] = b0 * (1+r)^N   (Roth compounds untouched)
#
# With pension income exceeding the minimum spending floor (netSpending=0),
# the optimizer has no reason to withdraw from Roth. The Roth balance
# therefore follows the pure compound formula and all Roth withdrawal
# variables w_ijn[0,2,:] remain zero.
# ---------------------------------------------------------------------------

def test_pension_leaves_portfolio_intact():
    """Pension covers spending; Roth balance compounds at exact FV formula."""
    n, amount, rate = 12, 120, 4
    topAge = 72
    # Age at plan start derived from createPlan's formula: age = topAge - (n-1)
    start_age = topAge - (n - 1)
    p = createPlan(1, 'pension_intact', n, topAge)
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    p.setRates('user', values=[0, 0, rate, 0])
    # $700/month = $8,400/year; non-indexed, starts immediately.
    # Annual amount is well below the standard deduction — no income tax.
    p.setPension([700], [start_age], indexed=[False])
    p.solve('maxBequest', options={**_BASE, 'netSpending': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    _assert_bequest_matches_aggregate(p)
    # Roth portfolio should compound without any withdrawals.
    assert np.all(p.w_ijn[0, 2, :] < 0.01), (
        f"Expected zero Roth withdrawals; got {p.w_ijn[0, 2, :]}"
    )
    assert p.b_ijn[0, 2, p.N_n] == pytest.approx(
        1000 * amount * (1 + rate/100)**n, abs=1.0
    )


# ---------------------------------------------------------------------------
# Test 8: Relocation under maxBequest (no other ordinary income)
#
# With netSpending=0 and only tax-deferred savings, the LP may optimally move
# balance into taxable before death when retiree marginal ordinary tax on
# withdrawals is negligible; terminal j=1 is then ~0 and bequest reflects
# bucket-based reporting (no nu on j=0).
# ---------------------------------------------------------------------------

def test_taxdeferred_relocation_maxBequest_no_other_income():
    """maxBequest + TD-only: optimizer relocates j=1 to j=0; reporting stays consistent."""
    n, amount, rate = 12, 120, 4
    p = createPlan(1, 'td_reloc', n, 72)
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    p.setRates('user', values=[0, 0, rate, 0])
    p.setHeirsTaxRate(30)
    p.solve('maxBequest', options={**_BASE, 'netSpending': 0})
    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    _assert_bequest_matches_aggregate(p)
    td_terminal = float(np.sum(p.b_ijn[:, 1, p.N_n]))
    tx_terminal = float(np.sum(p.b_ijn[:, 0, p.N_n]))
    assert td_terminal < 1.0, f"expected relocation; terminal TD={td_terminal}"
    assert tx_terminal > 1000.0, f"expected taxable terminal balance; got {tx_terminal}"
