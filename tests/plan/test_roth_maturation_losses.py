"""
The Roth 5-year rule follows the account's real returns, losses included (#184).

The maturation rows keep the last five years of conversions in the Roth account at their
compounded value. They used to floor each year's growth at zero ("ignore market downs") while the
balance carryover grew the account at its real returns. After a loss year, a Roth holding only
recent conversions had to keep more than they were worth: the one feasible point was then no
conversion at all, an equality hidden behind two nearly equal sets of coefficients, and HiGHS's
simplex stalled on it without a verdict. Owl reported a solver error on a plan that solves.

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

from datetime import date

import numpy as np
import pandas as pd
import pytest

import owlplanner as owl


def _single(years, balance_k=2000):
    """One person, all savings tax-deferred and in stocks, starting at 55."""
    this = date.today().year
    p = owl.Plan(["Sam"], [f"{this - 55}-06-01"], [55 + years - 1], "maturation", verbose=False)
    p.setAccountBalances(taxable=[0], taxDeferred=[balance_k], taxFree=[0], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[100, 0, 0, 0], [100, 0, 0, 0]]])
    p.setSocialSecurity([2000], [67])
    p.setSpendingProfile("flat")
    return p


def _row(plan, tag):
    k = plan.A.tags.index(tag)
    return dict(zip(plan.A.Aind[k], plan.A.Aval[k])), plan.A.lb[k]


def test_conversions_are_kept_at_their_real_value_after_a_loss():
    p = _single(20)
    stocks = [10.0] * p.N_n
    stocks[3] = -30.0
    p.setRates("dataframe", df=pd.DataFrame({"S&P 500": stocks, "Bonds Baa": [4.0] * p.N_n,
                                             "T-Notes": [3.0] * p.N_n, "Inflation": [2.5] * p.N_n}))
    p.solve("maxSpending", {"solver": "HiGHS"})
    coef, _ = _row(p, ("roth_maturation", 0, 5))
    # A conversion made in year 2 grows through year 2 (+10%), then loses 30% in year 3, then
    # gains 10% in year 4. It is worth 1.1 * 0.7 * 1.1 = 0.847 of itself at the start of year 5.
    assert -coef[p.vm["x"].idx(0, 2)] == pytest.approx(1.1 * 0.7 * 1.1)
    assert -coef[p.vm["x"].idx(0, 4)] == pytest.approx(1.1)


def test_long_historical_plan_solves_with_highs():
    """The reproduction from #184: 65 years on the 1958 sequence ended as a solver error."""
    p = _single(65)
    p.setRates("historical", 1958)
    p.solve("maxSpending", {"solver": "HiGHS"})
    assert p.caseStatus == "solved", p.solverMessage


def test_contribution_gains_are_never_negative_after_a_loss():
    """Only a contribution's gains are retained; a contribution that lost money has none to keep."""
    p = _single(20)
    table = p.timeLists["Sam"].copy()
    this = date.today().year
    table.loc[table["year"].isin([this, this + 1]), "Roth IRA ctrb"] = 7000
    p.setContributions({"Sam": table})
    stocks = [10.0] * p.N_n
    stocks[1] = -40.0
    p.setRates("dataframe", df=pd.DataFrame({"S&P 500": stocks, "Bonds Baa": [4.0] * p.N_n,
                                             "T-Notes": [3.0] * p.N_n, "Inflation": [2.5] * p.N_n}))
    p.solve("maxSpending", {"solver": "HiGHS"})
    lbs = [p.A.lb[k] for k, tag in enumerate(p.A.tags) if tag and tag[0] == "roth_maturation"]
    assert np.all(np.asarray(lbs) >= 0.0)
