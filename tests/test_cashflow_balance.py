"""
Cash flow balance tests.

Verifies that for every year of a solved plan the LP cash flow constraint
holds in aggregated post-solve form:

    g_n + T_n + U_n + J_n + (m_n + M_n) + ACA_n + debt_n
        == wages + other_inc + net_inv + SS + pensions + BTI
           + FA_ord + FA_cap + FA_taxfree + sum(w_ijn)

This is the equality constraint built in _add_net_cash_flow(), verified here
against the aggregated arrays produced by _aggregateResults(). A failure
would indicate a term is missing or double-counted in the post-solve output.

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
from datetime import date

import owlplanner as owl


def _assert_cashflow_balance(p, atol=1.0):
    """
    Assert that the LP cash flow constraint closes to zero for every year.
    atol is in dollars; $1 accommodates floating-point residuals from the
    SC-loop convergence tolerance.

    """
    lhs = (p.g_n
           + p.s_n
           + p.T_n
           + p.U_n
           + p.J_n
           + p.m_n + p.M_n
           + p.aca_costs_n
           + p.debt_payments_n)
    rhs = (np.sum(p.omega_in, axis=0)
           + np.sum(p.other_inc_in, axis=0)
           + np.sum(p.netinv_in, axis=0)
           + np.sum(p.zetaBar_in, axis=0)
           + np.sum(p.piBar_in, axis=0)
           + np.sum(p.spiaBar_in, axis=0)
           + np.sum(p.Lambda_in, axis=0)
           + p.fixed_assets_ordinary_income_n
           + p.fixed_assets_capital_gains_n
           + p.fixed_assets_tax_free_n
           + np.sum(p.w_ijn, axis=(0, 1)))
    np.testing.assert_allclose(lhs, rhs, atol=atol,
                               err_msg="Cash flow balance violated")


def _make_single(name, taxable, tax_deferred, tax_free, ss_pia=[0], ss_age=[67],
                 rate_year=2000):
    thisyear = date.today().year
    p = owl.Plan(['Alex'], [f"{thisyear - 66}-06-01"], [85], name)
    p.setSpendingProfile('flat', 60)
    p.setAccountBalances(taxable=taxable, taxDeferred=tax_deferred,
                         taxFree=tax_free, startDate="1-1")
    p.setAllocationRatios('individual',
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setSocialSecurity(ss_pia, ss_age)
    p.setRates('historical', rate_year)
    return p


def _make_couple(name, taxable, tax_deferred, tax_free, ss_pias, ss_ages,
                 rate_year=2000):
    thisyear = date.today().year
    p = owl.Plan(['Alex', 'Pat'],
                 [f"{thisyear - 66}-06-01", f"{thisyear - 63}-06-01"],
                 [85, 85], name)
    p.setSpendingProfile('flat', 60)
    p.setAccountBalances(taxable=taxable, taxDeferred=tax_deferred,
                         taxFree=tax_free, startDate="1-1")
    p.setAllocationRatios('individual',
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]],
                                   [[50, 50, 0, 0], [60, 40, 0, 0]]])
    p.setSocialSecurity(ss_pias, ss_ages)
    p.setRates('historical', rate_year)
    return p


class TestCashflowBalance:
    def test_single_roth_only(self):
        """Single person, all Roth: simple case with only Medicare as outflow."""
        p = _make_single('roth_only', taxable=[0], tax_deferred=[0],
                         tax_free=[1000], ss_pia=[0])
        p.solve('maxSpending')
        _assert_cashflow_balance(p)

    def test_single_tax_deferred(self):
        """Single person, IRA-heavy: RMDs and ordinary income tax in play."""
        p = _make_single('ira_heavy', taxable=[0], tax_deferred=[800],
                         tax_free=[200], ss_pia=[1800], ss_age=[67])
        p.solve('maxSpending')
        _assert_cashflow_balance(p)

    def test_single_mixed_accounts(self):
        """Single person with taxable, IRA, and Roth accounts and SS."""
        p = _make_single('mixed', taxable=[200], tax_deferred=[500],
                         tax_free=[300], ss_pia=[2000], ss_age=[67])
        p.solve('maxSpending')
        _assert_cashflow_balance(p)

    def test_couple_mixed_accounts(self):
        """Couple with all three account types and SS."""
        p = _make_couple('couple_mixed',
                         taxable=[100, 100], tax_deferred=[400, 300],
                         tax_free=[100, 100],
                         ss_pias=[2000, 1500], ss_ages=[67, 67])
        p.solve('maxSpending')
        _assert_cashflow_balance(p)

    def test_couple_with_pension(self):
        """Couple with pension income exercising piBar_in."""
        p = _make_couple('couple_pension',
                         taxable=[50, 50], tax_deferred=[300, 200],
                         tax_free=[100, 100],
                         ss_pias=[1500, 1000], ss_ages=[67, 67])
        p.setPension([1500, 800], [62, 62])
        p.solve('maxSpending')
        _assert_cashflow_balance(p)

    def test_max_bequest_objective(self):
        """Balance holds under maxBequest objective."""
        p = _make_single('bequest', taxable=[100], tax_deferred=[500],
                         tax_free=[200], ss_pia=[1800], ss_age=[67])
        p.solve('maxBequest', options={'netSpending': 60})
        _assert_cashflow_balance(p)

    def test_with_hsa(self):
        """Balance holds with an HSA account (j=3) in play."""
        thisyear = date.today().year
        p = owl.Plan(['Alex'], [f"{thisyear - 60}-06-01"], [85], 'hsa_balance')
        p.setSpendingProfile('flat', 60)
        p.setAccountBalances(taxable=[0], taxDeferred=[500], taxFree=[100],
                             hsa=[50], startDate="1-1")
        p.setAllocationRatios('individual',
                              generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
        p.setSocialSecurity([1800], [67])
        p.setRates('historical', 2000)
        p.solve('maxSpending')
        _assert_cashflow_balance(p)

    @pytest.mark.toml
    def test_toml_jack_and_jill(self):
        """Balance holds for the canonical jack+jill example case."""
        p = owl.readConfig('examples/Case_jack+jill.toml')
        p.solve('maxSpending')
        _assert_cashflow_balance(p)

    @pytest.mark.toml
    def test_toml_bill(self):
        """Balance holds for the single-person Bill example case."""
        p = owl.readConfig('examples/Case_bill.toml')
        p.solve('maxSpending')
        _assert_cashflow_balance(p)
