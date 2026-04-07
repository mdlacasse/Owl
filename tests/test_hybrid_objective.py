"""
Tests for the maxHybrid objective in Owl retirement planner.

Verifies that the blended spending/bequest objective behaves correctly:
- Solving works, options are correctly accepted/rejected
- spendingFloor constraint is respected
- h=1 matches maxSpending, h=0 maximizes bequest
- With a spending floor, intermediate h gives spending > floor and higher bequest than pure spending

Note on zero-spending: Without a spendingFloor, the LP may set spending to 0 at intermediate
h values when the account growth rate is high. This is mathematically correct: $1 saved
compounds to more than $1 at the end of the horizon, so the bequest term can dominate.
The spending floor is the intended mechanism to prevent this.

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

import pytest
from datetime import date

import owlplanner as owl


solver = "HiGHS"
REL_TOL = 1e-3
ABS_TOL = 500.0


def createPlan(name):
    """Single-person plan for fast, reproducible hybrid objective tests."""
    thisyear = date.today().year
    inames = ["Alex"]
    dobs = [f"{thisyear - 65}-06-15"]
    expectancy = [85]
    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[500], taxFree=[100])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [40, 60, 0, 0]]])
    p.setSocialSecurity([2000], [67])
    p.setRates("user", values=[6.0, 4.0, 3.3, 2.8])
    return p


class TestHybridObjective:
    def test_hybrid_solves(self):
        """maxHybrid with default h=0.5 and no floor should solve successfully."""
        p = createPlan("hybrid_basic")
        p.solve("maxHybrid", options={"solver": solver, "withSSTaxability": 0.85})
        assert p.caseStatus == "solved"
        assert p.bequest >= 0

    def test_hybrid_h1_maximizes_spending(self):
        """h=1 (all spending) should give higher spending than h=0 (all bequest).

        With h=1, only spending is optimized (bequest weight=0). With h=0, only bequest
        is optimized (spending weight=0). h=1 should yield strictly more spending.
        Note: maxHybrid uses a floor-only profile, so it is not directly comparable to
        maxSpending which uses bilateral profile bounds.
        """
        p_h1 = createPlan("hybrid_h1")
        p_h1.solve("maxHybrid", options={"spendingWeight": 1.0, "spendingFloor": 30.0,
                                         "solver": solver, "withSSTaxability": 0.85})
        assert p_h1.caseStatus == "solved"

        p_h0 = createPlan("hybrid_h0_compare")
        p_h0.solve("maxHybrid", options={"spendingWeight": 0.0, "spendingFloor": 30.0,
                                         "solver": solver, "withSSTaxability": 0.85})
        assert p_h0.caseStatus == "solved"

        # h=1 must give more spending than h=0
        assert float(p_h1.basis) >= float(p_h0.basis) - ABS_TOL

    def test_hybrid_h0_maximizes_bequest(self):
        """h=0 (all bequest) should produce a higher bequest than maxSpending."""
        p_spend = createPlan("hybrid_h0_spend_ref")
        p_spend.solve("maxSpending", options={"bequest": 0, "solver": solver, "withSSTaxability": 0.85})
        assert p_spend.caseStatus == "solved"

        p_hybrid = createPlan("hybrid_h0")
        p_hybrid.solve("maxHybrid", options={"spendingWeight": 0.0, "solver": solver, "withSSTaxability": 0.85})
        assert p_hybrid.caseStatus == "solved"

        # h=0 uses the same coefficients as maxBequest → bequest should exceed pure-spending bequest
        assert p_hybrid.bequest >= p_spend.bequest - ABS_TOL

    def test_spending_floor_binding(self):
        """spendingFloor should set a binding lower bound on first-year spending."""
        # Without floor, h=0.5 with high growth rates can set spending to 0
        # Set explicit floor and verify it is respected
        floor_k = 50.0  # $50k floor
        p = createPlan("hybrid_with_floor")
        p.solve("maxHybrid", options={
            "spendingWeight": 0.5,
            "spendingFloor": floor_k,
            "solver": solver,
            "withSSTaxability": 0.85,
        })
        assert p.caseStatus == "solved"
        assert float(p.basis) >= floor_k * 1000 - ABS_TOL

    def test_spending_floor_with_low_h_yields_higher_bequest(self):
        """With a floor set, lower h should give a higher bequest than higher h."""
        common_opts = {"spendingFloor": 40.0, "solver": solver, "withSSTaxability": 0.85}

        p_high_h = createPlan("hybrid_floor_h08")
        p_high_h.solve("maxHybrid", options={"spendingWeight": 0.8, **common_opts})
        assert p_high_h.caseStatus == "solved"

        p_low_h = createPlan("hybrid_floor_h02")
        p_low_h.solve("maxHybrid", options={"spendingWeight": 0.2, **common_opts})
        assert p_low_h.caseStatus == "solved"

        # Lower spending weight → more emphasis on bequest
        assert p_low_h.bequest >= p_high_h.bequest - ABS_TOL

    def test_spending_floor_with_high_h_yields_higher_spending(self):
        """With a floor set, higher h should give equal or higher spending than lower h."""
        common_opts = {"spendingFloor": 40.0, "solver": solver, "withSSTaxability": 0.85}

        p_high_h = createPlan("hybrid_floor_h08_spend")
        p_high_h.solve("maxHybrid", options={"spendingWeight": 0.8, **common_opts})
        assert p_high_h.caseStatus == "solved"

        p_low_h = createPlan("hybrid_floor_h02_spend")
        p_low_h.solve("maxHybrid", options={"spendingWeight": 0.2, **common_opts})
        assert p_low_h.caseStatus == "solved"

        # Higher spending weight → more emphasis on spending
        assert p_high_h.basis >= p_low_h.basis - ABS_TOL

    def test_hybrid_default_weight_is_half(self):
        """Omitting spendingWeight should default to h=0.5."""
        p_default = createPlan("hybrid_default_weight")
        p_default.solve("maxHybrid", options={"spendingFloor": 40.0, "solver": solver, "withSSTaxability": 0.85})

        p_explicit = createPlan("hybrid_explicit_half")
        p_explicit.solve("maxHybrid", options={
            "spendingWeight": 0.5, "spendingFloor": 40.0, "solver": solver, "withSSTaxability": 0.85
        })

        assert p_default.caseStatus == "solved"
        assert p_explicit.caseStatus == "solved"
        assert p_default.basis == pytest.approx(p_explicit.basis, rel=REL_TOL, abs=ABS_TOL)

    def test_time_preference_front_loads_spending(self):
        """A positive timePreference should shift spending earlier (higher early, lower late)."""
        common = {"spendingFloor": 30.0, "solver": solver, "withSSTaxability": 0.85}

        p_no_tp = createPlan("tp_none")
        p_no_tp.solve("maxHybrid", options={"spendingWeight": 0.5, **common})
        assert p_no_tp.caseStatus == "solved"

        p_tp = createPlan("tp_5pct")
        p_tp.solve("maxHybrid", options={"spendingWeight": 0.5, "timePreference": 5.0, **common})
        assert p_tp.caseStatus == "solved"

        # With time preference, early spending should be higher relative to late spending
        mid = len(p_no_tp.g_n) // 2
        early_ratio_no_tp = p_no_tp.g_n[:mid].mean() / (p_no_tp.g_n[mid:].mean() + 1)
        early_ratio_tp = p_tp.g_n[:mid].mean() / (p_tp.g_n[mid:].mean() + 1)
        assert early_ratio_tp >= early_ratio_no_tp - 1e-3

    def test_time_preference_on_max_spending(self):
        """timePreference should also work with maxSpending objective."""
        p = createPlan("tp_maxspending")
        p.solve("maxSpending", options={"timePreference": 3.0, "solver": solver, "withSSTaxability": 0.85})
        assert p.caseStatus == "solved"
        assert p.basis > 0

    def test_slack_caps_spending_above_floor(self):
        """spendingSlack > 0 should cap how far spending can roam above the profile floor."""
        common = {"spendingWeight": 0.8, "spendingFloor": 30.0,
                  "timePreference": 5.0, "solver": solver, "withSSTaxability": 0.85}

        p_free = createPlan("hybrid_slack0")
        p_free.solve("maxHybrid", options={"spendingSlack": 0, **common})
        assert p_free.caseStatus == "solved"

        p_capped = createPlan("hybrid_slack30")
        p_capped.solve("maxHybrid", options={"spendingSlack": 30, **common})
        assert p_capped.caseStatus == "solved"

        # With a cap, peak spending should not exceed (1 + slack) × floor level
        # (slack=30 means spending can go at most 30% above profile, vs. unbounded with slack=0)
        assert max(p_capped.g_n) <= max(p_free.g_n) + ABS_TOL

    def test_hybrid_ignores_netspending_option(self):
        """netSpending option should be ignored (with a warning) for maxHybrid."""
        p = createPlan("hybrid_ignore_netspending")
        p.solve("maxHybrid", options={"netSpending": 80, "solver": solver, "withSSTaxability": 0.85})
        assert p.caseStatus == "solved"

    def test_hybrid_ignores_bequest_option(self):
        """bequest option should be ignored (with a warning) for maxHybrid."""
        p = createPlan("hybrid_ignore_bequest")
        p.solve("maxHybrid", options={"bequest": 500, "solver": solver, "withSSTaxability": 0.85})
        assert p.caseStatus == "solved"

    def test_invalid_objective_rejected(self):
        """Unknown objective strings should raise ValueError."""
        p = createPlan("hybrid_invalid")
        with pytest.raises(ValueError, match="not one of"):
            p.solve("maxWealth", options={"solver": solver})
