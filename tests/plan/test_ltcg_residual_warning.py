"""
Tests for the warning when the self-consistent loop leaves the tax on capital gains unsettled (#239).

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

from owlplanner import Plan

WARNING = "The tax on capital gains did not settle"


def _solve(**extra):
    """Issue #239: a large taxable account whose gains sit near the top of the 0% band, and
    tax-deferred balances whose conversions compete for the same room."""
    log = io.StringIO()
    p = Plan(["A", "B"], ["1964-06-15", "1966-03-10"], [90, 92], "ltcg-warning", verbose=False,
             logstreams=[log])
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[1500, 1], taxDeferred=[600, 300], taxFree=[0, 0], startDate="01-01")
    p.setAllocationRatios("individual", generic=[[[60, 0, 0, 40], [60, 0, 0, 40]]] * 2)
    p.setRates("user", values=[6, 4, 4, 2.5])
    p.setDividendRate(1.5)
    p.setExpirationYearOBBBA(2099)
    p.setSocialSecurity([2200, 1600], [67, 67])
    p.solve("maxSpending", options={"bequest": 0, "withMedicare": "loop", **extra})
    assert p.caseStatus == "solved"
    return p, log.getvalue()


def test_loop_warns_when_the_gain_tax_does_not_settle():
    # The loop cycles between plans charged $0 of gain tax in a year whose income implies $2,407,
    # and $2,292 in a year whose gains all sit in the 0% band.
    p, log = _solve()
    assert p.fixedPointResidual["LTCG"]["abs_sum"] > p.N_n * p._residual_tol
    assert WARNING in log
    assert 'withLTCG="optimize"' in log


def test_no_warning_under_the_exact_model():
    p, log = _solve(withLTCG="optimize")
    assert p.fixedPointResidual["LTCG"]["abs_sum"] < 1.0
    assert WARNING not in log
