"""
Tests for LTCG tax computation via the LP bracket-allocation variables (withLTCG="optimize").

Validates that:
- withLTCG="optimize" solves successfully and produces the same order-of-magnitude spending
  as the SC-loop baseline.
- ltcg0_n + ltcg15_n + ltcg20_n == Q_n for all years (partition constraint is tight).
- U_n == 0.15*ltcg15_n + 0.20*ltcg20_n exactly.
- psi_n is consistent with U_n / Q_n.
- 15% bracket is used when Q_n > T15_n − e_n (large-taxable-account plan).
- LP spending is >= SC-loop spending (LP finds at least as good a solution).

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

import numpy as np
import pytest
from datetime import date

import owlplanner as owl
from owlplanner import tax2026 as tx

solver = 'HiGHS'


def _make_couple_plan(name, taxable, tax_deferred, tax_free, ss_pias, ss_ages,
                      pension=None, pension_ages=None, rate_year=2000, expectancy=None):
    """
    Create a minimal couple plan for LTCG LP testing.
    Account balances in thousands; SS/pension in monthly $.
    """
    thisyear = date.today().year
    inames = ['Jack', 'Jill']
    dobs = [f"{thisyear - 66}-01-15", f"{thisyear - 63}-01-16"]
    if expectancy is None:
        expectancy = [80, 80]

    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile('flat', 60)
    p.setAccountBalances(taxable=taxable, taxDeferred=tax_deferred, taxFree=tax_free,
                         startDate="1-1")
    p.setInterpolationMethod('s-curve')
    p.setAllocationRatios('individual',
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]],
                                   [[50, 50, 0, 0], [70, 30, 0, 0]]])
    if pension is not None:
        p.setPension(pension, pension_ages)
    else:
        p.setPension([0, 0], [65, 65])
    p.setSocialSecurity(ss_pias, ss_ages)
    p.setRates('historical', rate_year)
    return p


def _make_single_plan(name, taxable, tax_deferred, tax_free, rate_year=1997):
    """
    Create a minimal single-individual plan with a large taxable account.
    Balance in thousands; all-equity allocation to maximise LTCG generation.
    """
    thisyear = date.today().year
    inames = ['Jack']
    dobs = [f"{thisyear - 66}-01-15"]

    p = owl.Plan(inames, dobs, [80], name)
    p.setSpendingProfile('flat', 60)
    p.setAccountBalances(taxable=[taxable], taxDeferred=[tax_deferred], taxFree=[tax_free],
                         startDate="1-1")
    p.setInterpolationMethod('s-curve')
    p.setAllocationRatios('individual',
                          generic=[[[100, 0, 0, 0], [100, 0, 0, 0]]])
    p.setPension([0], [65])
    p.setSocialSecurity([0], [67])
    p.setRates('historical', rate_year)
    return p


def test_ltcg_lp_feasible():
    """withLTCG='optimize' produces a feasible solution for a typical couple plan."""
    p = _make_couple_plan(
        'ltcg_feasible',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
    )
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None',
                            'withLTCG': 'optimize'})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"


def test_ltcg_lp_partition_exact():
    """ltcg0 + ltcg15 + ltcg20 == Q_n for all years (partition constraint is tight)."""
    p = _make_single_plan('ltcg_partition', taxable=2000, tax_deferred=0, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None',
                            'withLTCG': 'optimize'})
    assert p.caseStatus == 'solved'
    ltcg_sum = p.ltcg0_n + p.ltcg15_n + p.ltcg20_n
    total_ltcg = np.maximum(p.Q_n, 0)
    np.testing.assert_allclose(ltcg_sum, total_ltcg, atol=1.0,
                               err_msg="Partition sum does not match Q_n")


def test_ltcg_lp_tax_identity():
    """U_n == 0.15*ltcg15_n + 0.20*ltcg20_n exactly for all years."""
    p = _make_single_plan('ltcg_tax_identity', taxable=2000, tax_deferred=0, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None',
                            'withLTCG': 'optimize'})
    assert p.caseStatus == 'solved'
    expected_U = 0.15 * p.ltcg15_n + 0.20 * p.ltcg20_n
    np.testing.assert_allclose(p.U_n, expected_U, atol=0.01,
                               err_msg="U_n does not equal 0.15*ltcg15 + 0.20*ltcg20")


def test_ltcg_lp_psi_consistency():
    """psi_n == U_n / Q_n in years with positive LTCG."""
    p = _make_single_plan('ltcg_psi', taxable=2000, tax_deferred=0, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None',
                            'withLTCG': 'optimize'})
    assert p.caseStatus == 'solved'
    has_ltcg = p.Q_n > 0
    if has_ltcg.any():
        expected_psi = np.where(has_ltcg, p.U_n / np.maximum(p.Q_n, 1e-8), 0.0)
        np.testing.assert_allclose(p.psi_n[has_ltcg], expected_psi[has_ltcg], atol=1e-6)


def test_ltcg_lp_15pct_bracket_used():
    """
    Large taxable account (100% equity, no tax-deferred) with historical returns
    should push some LTCG above the 0% bracket → ltcg15_n > 0 in growth years.
    """
    p = _make_single_plan('ltcg_15pct', taxable=2000, tax_deferred=0, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None',
                            'withLTCG': 'optimize'})
    assert p.caseStatus == 'solved'
    # Expect at least one year with 15% bracket LTCG (historical 1997 bull run creates large Q_n).
    assert np.any(p.ltcg15_n > 0), "Expected some LTCG in the 15% bracket for large-taxable plan."
    # No 20% bracket expected for this moderate case.
    assert np.all(p.ltcg20_n == pytest.approx(0, abs=1.0)), "Unexpected 20% bracket LTCG."


def test_ltcg_lp_nonnegative():
    """All LTCG bracket variables are non-negative."""
    p = _make_couple_plan(
        'ltcg_nonneg',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
    )
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None',
                            'withLTCG': 'optimize'})
    assert p.caseStatus == 'solved'
    assert np.all(p.ltcg0_n >= -1.0), "ltcg0_n has negative values"
    assert np.all(p.ltcg15_n >= -1.0), "ltcg15_n has negative values"
    assert np.all(p.ltcg20_n >= -1.0), "ltcg20_n has negative values"


def test_ltcg_lp_spending_at_least_sc_loop():
    """
    LP LTCG spending should be >= SC-loop spending: the LP finds at least as
    good a solution since it has exact LTCG tax information from the first solve.
    """
    common_kwargs = dict(
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
    )
    p_sc = _make_couple_plan('ltcg_sc', **common_kwargs)
    p_sc.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})

    p_lp = _make_couple_plan('ltcg_lp', **common_kwargs)
    p_lp.solve('maxSpending', {'solver': solver, 'withMedicare': 'None',
                               'withLTCG': 'optimize'})

    assert p_sc.caseStatus == 'solved'
    assert p_lp.caseStatus == 'solved'
    # LP spending should be >= SC-loop (with tolerance for solver noise).
    assert p_lp.g_n[0] >= p_sc.g_n[0] - 10, (
        f"LP spending {p_lp.g_n[0]:.2f} unexpectedly lower than SC-loop {p_sc.g_n[0]:.2f}")


def test_ltcg_lp_u_n_close_to_sc_loop():
    """
    The LTCG tax (U_n) from the LP should be close to the SC-loop result:
    both compute the same piecewise-linear LTCG tax, just via different paths.
    """
    p_sc = _make_single_plan('ltcg_sc_u', taxable=2000, tax_deferred=0, tax_free=0)
    p_sc.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})

    p_lp = _make_single_plan('ltcg_lp_u', taxable=2000, tax_deferred=0, tax_free=0)
    p_lp.solve('maxSpending', {'solver': solver, 'withMedicare': 'None',
                               'withLTCG': 'optimize'})

    assert p_sc.caseStatus == 'solved'
    assert p_lp.caseStatus == 'solved'
    # The LTCG tax totals should be within 2% of each other.
    total_sc = np.sum(p_sc.U_n)
    total_lp = np.sum(p_lp.U_n)
    if total_sc > 0:
        rel_diff = abs(total_lp - total_sc) / total_sc
        assert rel_diff < 0.02, (
            f"LTCG tax total differs by {100*rel_diff:.1f}%: LP={total_lp:.0f}, SC={total_sc:.0f}")
