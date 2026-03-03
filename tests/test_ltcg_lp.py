"""
Tests for LTCG tax computation via LP bracket-allocation variables q_{pn} (p=0,1,2).

The LP bracket formulation is always used (no SC-loop fallback). Validates that:
- The solver produces a feasible solution for typical plans.
- q[0,n] + q[1,n] + q[2,n] == Q_n for all years (partition constraint is tight).
- U_n == 0.15*q[1,n] + 0.20*q[2,n] exactly (LTCG tax definition).
- Effective LTCG rate U_n/Q_n is in [0%, 20%] when Q_n > 0.
- 15% bracket is used when Q_n > T15_n − e_n (large-taxable-account plan).

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
    """LP LTCG formulation produces a feasible solution for a typical couple plan."""
    p = _make_couple_plan(
        'ltcg_feasible',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
    )
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"


def test_ltcg_lp_partition_exact():
    """q[0]+q[1]+q[2] == Q_n for all years (partition constraint is tight)."""
    p = _make_single_plan('ltcg_partition', taxable=2000, tax_deferred=0, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved'
    ltcg_sum = p.q_pn[0] + p.q_pn[1] + p.q_pn[2]
    total_ltcg = np.maximum(p.Q_n, 0)
    np.testing.assert_allclose(ltcg_sum, total_ltcg, atol=1.0,
                               err_msg="Partition sum does not match Q_n")


def test_ltcg_lp_tax_identity():
    """U_n == 0.15*q[1,n] + 0.20*q[2,n] exactly for all years."""
    p = _make_single_plan('ltcg_tax_identity', taxable=2000, tax_deferred=0, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved'
    expected_U = 0.15 * p.q_pn[1] + 0.20 * p.q_pn[2]
    np.testing.assert_allclose(p.U_n, expected_U, atol=0.01,
                               err_msg="U_n does not equal 0.15*q[1] + 0.20*q[2]")


def test_ltcg_lp_psi_consistency():
    """Effective LTCG rate U_n/Q_n is in [0%, 20%] in years with positive LTCG."""
    p = _make_single_plan('ltcg_psi', taxable=2000, tax_deferred=0, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved'
    has_ltcg = p.Q_n > 0
    if has_ltcg.any():
        effective_rate = p.U_n[has_ltcg] / np.maximum(p.Q_n[has_ltcg], 1e-8)
        np.testing.assert_array_less(-1e-6, effective_rate)
        np.testing.assert_array_less(effective_rate, 0.20 + 1e-6)


def test_ltcg_lp_15pct_bracket_used():
    """
    Large taxable account (100% equity, no tax-deferred) with historical returns
    should push some LTCG above the 0% bracket → q[1,n] > 0 in growth years.
    """
    p = _make_single_plan('ltcg_15pct', taxable=2000, tax_deferred=0, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved'
    # Expect at least one year with 15% bracket LTCG (historical 1997 bull run creates large Q_n).
    assert np.any(p.q_pn[1] > 0), "Expected some LTCG in the 15% bracket for large-taxable plan."
    # No 20% bracket expected for this moderate case.
    assert np.all(p.q_pn[2] == pytest.approx(0, abs=1.0)), "Unexpected 20% bracket LTCG."


def test_ltcg_lp_rate_within_bounds():
    """Effective LTCG rate U_n/Q_n is in [0%, 20%] for all years with positive LTCG.

    Uses a large taxable account (generates LTCG) combined with a large tax-deferred
    account (generates ordinary income via withdrawals) to ensure that ordinary income
    stacks into the LTCG brackets, producing positive LTCG tax U_n > 0 in some years.
    """
    p = _make_single_plan('ltcg_rate_bounds', taxable=2000, tax_deferred=1000, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved'
    has_ltcg = p.Q_n > 0
    assert has_ltcg.any(), "Expected positive LTCG in at least one year."
    assert np.any(p.U_n > 0), "Expected positive LTCG tax in at least one year."
    rate = p.U_n[has_ltcg] / p.Q_n[has_ltcg]
    assert np.all(rate >= -1e-6), f"Negative LTCG rate: min={rate.min():.4f}"
    assert np.all(rate <= 0.20 + 1e-6), f"LTCG rate exceeds 20%: max={rate.max():.4f}"


def test_ltcg_lp_nonnegative():
    """All LTCG bracket variables are non-negative."""
    p = _make_couple_plan(
        'ltcg_nonneg',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
    )
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved'
    assert np.all(p.q_pn[0] >= -1.0), "q[0,n] has negative values"
    assert np.all(p.q_pn[1] >= -1.0), "q[1,n] has negative values"
    assert np.all(p.q_pn[2] >= -1.0), "q[2,n] has negative values"


def test_ltcg_lp_matches_capital_gain_tax():
    """
    Cross-validate LP LTCG tax U_n against tax2026.capitalGainTax().

    Given a solved plan with G_n (ordinary taxable income) and Q_n (LTCG + qualified
    dividends), the LP-derived U_n should match the reference capitalGainTax computation
    for years with positive Q_n.
    """
    from owlplanner import tax2026 as tx

    p = _make_single_plan('ltcg_crossval', taxable=2000, tax_deferred=500, tax_free=0)
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved'
    _assert_ltcg_matches_ref(p, tx)


def test_ltcg_lp_matches_capital_gain_tax_couple():
    """Cross-validate LP U_n vs capitalGainTax for a couple (MFJ→Single at n_d)."""
    from owlplanner import tax2026 as tx

    p = _make_couple_plan(
        'ltcg_crossval_couple',
        taxable=[90, 60],
        tax_deferred=[600, 150],
        tax_free=[70, 40],
        ss_pias=[2_333, 2_083],
        ss_ages=[67, 70],
    )
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved'
    _assert_ltcg_matches_ref(p, tx)


def _assert_ltcg_matches_ref(plan, tax_module):
    """Compare plan.U_n to tax_module.capitalGainTax() for years with positive Q_n."""
    tx_income_n = plan.G_n + plan.Q_n
    ltcg_n = np.maximum(plan.Q_n, 0)

    ref_cg_tax = tax_module.capitalGainTax(
        plan.N_i,
        tx_income_n,
        ltcg_n,
        plan.gamma_n,
        plan.n_d,
        plan.N_n,
    )

    has_ltcg = plan.Q_n > 0
    if has_ltcg.any():
        np.testing.assert_allclose(
            plan.U_n[has_ltcg],
            ref_cg_tax[has_ltcg],
            atol=1.0,
            err_msg="LP U_n does not match tax2026.capitalGainTax()",
        )
