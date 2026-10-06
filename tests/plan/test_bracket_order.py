"""
Tests for the bottom-up fill of the tax brackets.

The bracket variables are a relaxation: the LP fills the cheap brackets first only because tax
costs it something. In a year whose cash has no value -- late surplus that can only swell a
bequest above its floor -- any split is optimal, and the solver used to fill the top bracket
first, reporting tax the plan did not owe. The loop now prices tax from the first iterate that
does this, and the solved plan is checked.

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

import glob
import os

import numpy as np
import pytest

from owlplanner import Plan
from owlplanner.config import readConfig


def _solver():
    """Honour OWL_TEST_SOLVER, as the conftest does for plans that pick their solver themselves."""
    return "MOSEK" if os.environ.get("OWL_TEST_SOLVER", "").lower() == "mosek" else "HiGHS"


def _cash_rich_late_plan():
    """Spending is capped by the first years; a large pension from 70 then piles up as surplus."""
    p = Plan(["Ann"], ["1961-03-15"], [90], "brackets", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[50], taxDeferred=[100], taxFree=[0], startDate="01-01")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("user", values=[6, 4, 3, 2.5])
    p.setPension([12000], [70], indexed=[True])
    p.setSocialSecurity([2500], [70])
    return p


def _out_of_order_years(p):
    years = []
    for n in range(p.N_n):
        for t in range(1, p.N_t):
            if p.f_tn[t, n] > 1 and p.f_tn[t - 1, n] < p.DeltaBar_tn[t - 1, n] - 1:
                years.append(int(p.year_n[n]))
                break
    return years


def _ordered_tax(p, n):
    total, tax = float(np.sum(p.f_tn[:, n])), 0.0
    for t in range(p.N_t):
        part = min(total, p.DeltaBar_tn[t, n])
        tax += part * p.theta_tn[t, n]
        total -= part
    return tax


def test_brackets_fill_bottom_up_when_late_cash_is_worthless():
    p = _cash_rich_late_plan()
    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
    assert p.caseStatus == "solved"
    # The case does exercise the degenerate face: surplus in the late years, bequest far above 0.
    assert np.sum(p.s_n > 1) > 10
    assert p.bequest > 1e6

    assert _out_of_order_years(p) == []
    assert p.bracketOrderExcess == 0.0
    for n in range(p.N_n):
        assert abs(p.T_n[n] - _ordered_tax(p, n)) < 1.0


def test_pricing_tax_leaves_spending_unchanged():
    """Spending is set by the early years, where cash is valuable; the tie-break must not move it."""
    p = _cash_rich_late_plan()
    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
    # Recorded before the fix, when the late years were filled top-down: basis 31,580.
    assert abs(p.basis - 31580) < 5


def test_excess_measures_an_out_of_order_fill():
    """_bracket_order_excess charges the gap between the fill given and the bottom-up one."""
    p = _cash_rich_late_plan()
    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
    n = int(np.flatnonzero(np.sum(p.f_tn, axis=0) > 1e5)[0])
    total = float(np.sum(p.f_tn[:, n]))
    p.f_tn = p.f_tn.copy()
    p.f_tn[:, n] = 0.0
    p.f_tn[-1, n] = total  # all of it in the top bracket
    years, excess = p._bracket_order_excess()
    assert years == [int(p.year_n[n])]
    expected = (total * p.theta_tn[-1, n] - _ordered_tax(p, n)) / p.gamma_n[n]
    assert abs(excess - expected) < 1.0


def _ordered(total, width, rate):
    tax = 0.0
    for t in range(len(width)):
        part = min(max(total, 0.0), width[t])
        tax += part * rate[t]
        total -= part
    return tax


@pytest.mark.toml
@pytest.mark.parametrize("path", sorted(glob.glob("examples/Case_*.toml")), ids=lambda s: s.split("Case_")[1][:-5])
def test_example_brackets_are_filled_bottom_up(path):
    """Every shipped case charges each year's income in bracket order, federal, state and capital gains."""
    p = readConfig(path, verbose=False)
    p.mylog.setVerbose(False)
    p.solverOptions["solver"] = _solver()
    p.resolve()
    assert p.caseStatus == "solved"
    assert p.bracketOrderExcess == 0.0, f"{p.bracketOrderExcess:,.2f} of tax charged out of bracket order"
    # Capital gains: in loop mode the 0%/15% room comes from the previous iterate's ordinary income and
    # is not kept after the loop, so U_n can legitimately differ from what this iterate's income implies,
    # in either direction (reported as the LTCG fixed-point residual). What holds whatever the room is
    # that no year is charged more than the top 20% rate on all of its gains.
    over = p.U_n - 0.20 * np.maximum(p.Q_n, 0.0)
    assert np.all(over <= 1.0), f"capital-gains tax above 20% of gains in {p.year_n[np.argmax(over)]}"


def test_state_brackets_fill_bottom_up_when_late_cash_is_worthless():
    """The same worthless-cash plan in a graduated-rate state: the state brackets are filled in order too."""
    p = _cash_rich_late_plan()
    p.setStateTax("CA")
    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
    assert p.caseStatus == "solved"
    assert np.sum(p.s_n > 1) > 10  # still on the degenerate face
    assert p.N_st > 1 and np.any(p.st_f_tn > 1)
    assert p.bracketOrderExcess == 0.0
    for n in range(p.N_n):
        charged = float(p.st_f_tn[:, n] @ p.st_theta_tn[:, n])
        ordered = _ordered(float(np.sum(p.st_f_tn[:, n])), p.st_DeltaBar_tn[:, n], p.st_theta_tn[:, n])
        assert charged == pytest.approx(ordered, abs=1.0), int(p.year_n[n])
        assert p.T_n[n] == pytest.approx(_ordered_tax(p, n), abs=1.0), int(p.year_n[n])
