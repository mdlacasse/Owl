"""
Tests for the big-M of the withdrawal-ordering gates (withdrawalOrder="taxable_first", #178).

Each gate row gets its own bound (Plan._gateCeilings): the best growth path through the one-way
order of accounts (tax-deferred -> Roth -> taxable), instead of the whole portfolio compounded at
the best return any account sees. The bounds must hold for every plan, and stay far below the old
ceiling when the accounts are invested differently over a long plan.

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

import owlplanner as owl


def _plan(life=70, frm=1969):
    p = owl.Plan(["Sam"], ["1976-04-10"], [life], "gates", verbose=False)
    p.setAccountBalances(taxable=[3600], taxDeferred=[580], taxFree=[720])
    p.setCostBasis([1380])
    p.setSocialSecurity([3700], [70])
    p.setAllocationRatios(
        "account",
        taxable=[[[94, 0, 6, 0], [94, 0, 6, 0]]],
        taxDeferred=[[[0, 0, 100, 0], [0, 0, 100, 0]]],
        taxFree=[[[0, 0, 100, 0], [0, 0, 100, 0]]],
    )
    p.setSpendingProfile("flat")
    p.setRates("historical", frm=frm)
    return p


@pytest.mark.parametrize("order", ["taxable_first", "optimal"])
def test_gate_ceilings_bound_every_balance_and_withdrawal(order):
    """Without the factor of two, each bound still holds for the solved plan."""
    p = _plan()
    p.solve("maxBequest", {"netSpending": 105, "withdrawalOrder": order})
    assert p.caseStatus == "solved"
    tax, td, txdef, roth = (a / 2.0 for a in p._gateCeilings())
    tol = 1.0  # cents of rounding
    N = p.N_n
    assert np.all(p.b_ijn[:, 0, 1:].sum(axis=0) <= tax[1:] + tol)
    assert np.all(p.b_ijn[:, 1, 1:].sum(axis=0) <= td[1:] + tol)
    assert np.all(p.w_ijn[:, 1, :N].max(axis=0) <= txdef + tol)
    assert np.all(p.w_ijn[:, 2, :N].max(axis=0) <= roth + tol)


def test_gate_ceilings_are_much_tighter_than_the_portfolio_ceiling():
    """Taxable in equities, the rest in T-notes: the old ceiling let money hop to the best each year."""
    p = _plan(life=94)
    p.solve("maxBequest", {"netSpending": 105, "withdrawalOrder": "taxable_first", "maxIter": 1})
    tax, td, txdef, roth = p._gateCeilings()
    old = p._portfolioCeiling()
    assert tax[-1] < old[-1] / 3
    assert td[-1] < old[-1] / 10
    assert roth[-1] < old[-1] / 3
