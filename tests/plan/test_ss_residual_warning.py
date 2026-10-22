"""
Tests for the warning when the self-consistent loop leaves taxable Social Security unsettled (#193).

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

import io

import pandas as pd

from owlplanner import Plan
from owlplanner.hfp_io import conditionDebtsAndFixedAssetsDF

WARNING = "Taxable Social Security did not settle"


def _phase_in_couple(log):
    """Issue #193: most SS years in the 50-85% phase-in, large tax-deferred balances, SS at 70."""
    p = Plan(["Joe", "Jane"], ["1964-03-15", "1964-09-15"], [89, 92], "ss-warning", verbose=False,
             logstreams=[log])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[150, 150], taxDeferred=[900, 600], taxFree=[75, 75])
    mix = [[60, 40, 0, 0]] * 2
    p.setAllocationRatios("account", taxable=[mix] * 2, taxDeferred=[mix] * 2, taxFree=[mix] * 2)
    p.setRates("conservative")
    p.setSocialSecurity([3000, 2400], [70, 70])
    p.houseLists["Debts"] = conditionDebtsAndFixedAssetsDF(pd.DataFrame(
        [{"active": True, "name": "m", "type": "mortgage", "year": int(p.year_n[0]), "term": 30,
          "amount": 600000.0, "rate": 6.5}]), "Debts")
    p.Lambda_in[0, 0] = 600000.0
    p.setStateTax("NY")
    p.setExpirationYearOBBBA(2032)
    return p


def _solve(**extra):
    log = io.StringIO()
    p = _phase_in_couple(log)
    p.solve("maxBequest", options={"noRothConversions": "None", "netSpending": 90, **extra})
    assert p.caseStatus == "solved"
    return p, log.getvalue()


def test_loop_warns_when_ss_does_not_settle():
    # At $90k the loop ends with thousands of dollars of SS residual under both solvers: the log
    # points to the exact model. (At $95k and $105k under MOSEK, with the tests' frozen date and the
    # first Medicare year prorated (#208), the loop's residual stays below the bar although its plan
    # is short of the exact one: the warning reports a loop that did not settle, not one that
    # settled short.)
    p, log = _solve()
    assert p.fixedPointResidual["SS"]["abs_sum"] > p.N_n * p._residual_tol
    assert WARNING in log
    assert 'withSSTaxability="optimize"' in log


def test_no_warning_under_the_exact_model():
    p, log = _solve(withSSTaxability="optimize")
    assert WARNING not in log


def test_no_warning_for_a_pinned_fraction():
    # A pinned taxable fraction is the user's choice, not a loop that failed to settle.
    _, log = _solve(withSSTaxability=0.85)
    assert WARNING not in log
