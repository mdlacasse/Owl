"""
Tests for withSSTaxability="convex" (issue #193).

Under the loop, the taxable share of Social Security is a constant in each LP, so income in a
phase-in year is priced at the bracket rate alone and the loop settles (or cycles) well short of
the exact plan. The convex mode prices the phase-in with LP rows and chooses the capped years by
probing, without binaries.

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

import pandas as pd

from owlplanner import Plan
from owlplanner.hfp_io import conditionDebtsAndFixedAssetsDF
from owlplanner.utils import normalize_mode_option


def _phase_in_couple():
    """Issue #193: most SS years in the 50-85% phase-in, large tax-deferred balances, SS at 70."""
    p = Plan(["Joe", "Jane"], ["1964-03-15", "1964-09-15"], [89, 92], "ss-convex", verbose=False)
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


def _solve(mode):
    p = _phase_in_couple()
    opts = {"noRothConversions": "None", "netSpending": 105}
    if mode != "loop":
        opts["withSSTaxability"] = mode
    p.solve("maxBequest", options=opts)
    assert p.caseStatus == "solved"
    return p


def test_convex_is_a_mode():
    assert normalize_mode_option("withSSTaxability", "Convex") == "convex"


def test_convex_beats_the_loop_and_is_consistent():
    loop = _solve("loop")
    cvx = _solve("convex")
    # The loop settles well short of the exact plan here (by $16k of p.bequest, today's dollars,
    # and $38k of after-tax estate in the issue); convex recovers it.
    gain = (cvx.bequest - loop.bequest) / cvx.gamma_n[-1]
    assert gain > 10_000, gain
    # The plan's own provisional income implies the taxable SS it was charged.
    assert cvx.fixedPointResidual["SS"]["abs_sum"] < cvx.N_n
    assert cvx.convergenceType != "max iteration"
