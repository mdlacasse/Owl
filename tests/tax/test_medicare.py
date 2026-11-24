"""
Tests for Medicare Part B, Part D, and IRMAA calculations (tax_federal.mediCosts, mediVals).

Verifies that single individuals are charged the standard Part B basic premium
in eligible years, that values align with CMS published figures (e.g. 2026),
and that Part D (base + IRMAA) is included when enabled.

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

import pytest
import numpy as np
from datetime import date

from owlplanner import tax_federal as tx


def test_mediCosts_single_individual_basic_premium():
    """Single individual aged 65+ is charged the Part B basic premium each eligible year."""
    thisyear = date.today().year
    # Single person, born so they are 70 at plan start (thisyear)
    yobs = np.array([thisyear - 70])
    Nn = 10
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn)
    magi = np.zeros(Nn)  # Low MAGI -> no IRMAA surcharge
    prevmagi = np.zeros(2)

    # With Part D included, low MAGI still has no Part D IRMAA; cost = Part B only
    costs = tx.mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn)

    # Annual basic premium = 12 * monthly standard (e.g. 202.90 for 2026)
    basic_annual = tx.partB_irmaa_fees[0]
    assert basic_annual == pytest.approx(12 * 202.90)

    # Every year the person is 65+ and in horizon should have at least the basic premium
    for n in range(Nn):
        age_in_year = thisyear + n - yobs[0]
        if age_in_year >= 65 and n < horizons[0]:
            assert costs[n] >= basic_annual, f"Year n={n} (age {age_in_year}) should charge basic premium"
            assert costs[n] == pytest.approx(basic_annual, rel=1e-9), (
                f"Low MAGI: cost should equal basic premium in year n={n}"
            )
        else:
            assert costs[n] == 0


def test_mediCosts_single_irmaa_brackets():
    """Single individual with high MAGI gets Part B IRMAA surcharges (2026 brackets)."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 70])
    Nn = 5
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn)
    prevmagi = np.array([0.0, 0.0])

    # MAGI just above first single bracket (109k) -> basic + first surcharge (Part B only for this test)
    magi = np.full(Nn, 120_000)
    costs = tx.mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn, include_part_d=False)
    # For n>=2 we use magi[n-2]; for n<2 we use prevmagi[n]
    # Bracket 1 is > 109k: add partB_irmaa_fees[1] = 12*81.20
    expected_low = tx.partB_irmaa_fees[0] + tx.partB_irmaa_fees[1]
    for n in range(2, Nn):
        assert costs[n] == pytest.approx(expected_low), f"Single MAGI 120k: expect basic + first IRMAA in year n={n}"


def test_irmaa_values_2026_cms():
    """IRMAA fees and brackets match CMS 2026 (single: ≤109k, 109–137k, etc.)."""
    # Standard monthly Part B 2026 = $202.90
    assert tx.partB_irmaa_fees[0] == pytest.approx(12 * 202.90)
    # Single brackets (index 0): 0, 109_000, 137_000, 171_000, 205_000, 500_000
    assert tx.irmaaBrackets[0][1] == 109_000
    assert tx.irmaaBrackets[0][2] == 137_000
    assert tx.irmaaBrackets[0][5] == 500_000
    monthly_totals = tx.partB_irmaa_costs / 12
    np.testing.assert_allclose(monthly_totals, [202.90, 284.10, 405.80, 527.50, 649.20, 689.90])
    # Part D IRMAA, CMS 2026 fact sheet and SSA POMS HI 01101.020 (#214).
    np.testing.assert_allclose(tx.partD_irmaa_costs / 12, [0.0, 14.50, 37.50, 60.40, 83.30, 91.00])


def test_mediCosts_part_d_irmaa_increases_cost():
    """With Part D included, high MAGI yields higher total than Part B only."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 70])
    Nn = 5
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn)
    prevmagi = np.array([0.0, 0.0])
    magi = np.full(Nn, 120_000)  # Above first bracket

    costs_part_b_only = tx.mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn, include_part_d=False)
    costs_with_part_d = tx.mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn, include_part_d=True)
    # Part D first bracket surcharge = 12 * 14.50
    expected_extra = 12 * 14.50
    for n in range(2, Nn):
        assert costs_with_part_d[n] == pytest.approx(costs_part_b_only[n] + expected_extra), (
            f"Year n={n}: Part D should add first-bracket surcharge"
        )


def test_mediCosts_part_d_base_premium():
    """Part D base premium increases cost by expected amount per eligible person per year."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 70])
    Nn = 4
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn)
    magi = np.zeros(Nn)
    prevmagi = np.zeros(2)
    base_monthly = 40.0
    base_annual = base_monthly * 12

    costs_no_base = tx.mediCosts(
        yobs,
        horizons,
        magi,
        prevmagi,
        gamma_n,
        Nn,
        include_part_d=True,
        part_d_base_annual_per_person=0.0,
    )
    costs_with_base = tx.mediCosts(
        yobs,
        horizons,
        magi,
        prevmagi,
        gamma_n,
        Nn,
        include_part_d=True,
        part_d_base_annual_per_person=base_annual,
    )
    for n in range(Nn):
        if thisyear + n - yobs[0] >= 65 and n < horizons[0]:
            assert costs_with_base[n] == pytest.approx(costs_no_base[n] + base_annual), (
                f"Year n={n}: Part D base should add {base_annual} for one person"
            )


def test_mediVals_combined_costs_increase_by_bracket():
    """Combined Part B + Part D cumulative costs are strictly increasing by bracket."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 65])  # 65 at plan start
    Nn = 3
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn + 1)
    Nq = 6

    nm, Lbar, Cbar = tx.mediVals(
        yobs,
        horizons,
        gamma_n,
        Nn,
        Nq,
        include_part_d=True,
        part_d_base_annual_per_person=0.0,
    )
    assert nm == 0
    for nn in range(Cbar.shape[0]):
        for q in range(1, Nq):
            assert Cbar[nn, q] > Cbar[nn, q - 1], f"Year nn={nn}: bracket {q} cost should exceed bracket {q - 1}"


def test_medicare_n_carries_the_total_in_both_modes():
    """plan.medicare_n is the whole premium whichever way Medicare was solved.

    The cost lands in a different array per mode: withMedicare='optimize' puts it in the
    LP variable m_n and leaves M_n at zero, loop mode does the reverse. Reading either
    array alone silently reports zero on the other path, so the total has one name.
    """
    import owlplanner as owl

    thisyear = date.today().year
    p = owl.Plan(["Sam"], [f"{thisyear - 66}-01-15"], [78], "medicare_total", verbose=False)
    p.setVerbose(False)
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[300], taxDeferred=[1200], taxFree=[100], startDate="1-1")
    p.setInterpolationMethod("s-curve")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0], [65])
    p.setSocialSecurity([2000], [67])
    p.setRates("historical average", 1928, 2025)

    totals = {}
    for mode in ("loop", "optimize"):
        p.solve("maxSpending", options={"withMedicare": mode, "bequest": 0})
        assert p.caseStatus == "solved", f"withMedicare='{mode}' failed: {p.caseStatus}"
        np.testing.assert_allclose(p.medicare_n, p.m_n + p.M_n, atol=1e-9)
        totals[mode] = float(np.sum(p.medicare_n))
        assert totals[mode] > 0, f"withMedicare='{mode}' charged no Medicare at all"

    # Each mode leaves the other mode's array empty -- the reason the property exists.
    p.solve("maxSpending", options={"withMedicare": "loop", "bequest": 0})
    assert np.all(p.m_n == 0), "loop mode should leave the LP variable m_n at zero"
    p.solve("maxSpending", options={"withMedicare": "optimize", "bequest": 0})
    assert np.all(p.M_n == 0), "optimize mode should leave the loop array M_n at zero"


@pytest.mark.toml
def test_part_d_options_passed_to_solve_take_effect():
    """includeMedicarePartD and medicarePartDBasePremium given to solve() apply to that solve and the next (#156)."""
    import owlplanner as owl

    plan = owl.readConfig("examples/Case_john+sally.toml", verbose=False)
    plan.mylog.setVerbose(False)
    base = {**plan.solverOptions, "solver": "HiGHS", "medicarePartDBasePremium": 40}

    plan.solve("maxSpending", base)
    with_d = float(plan.M_n.sum())
    assert plan._include_medicare_part_d is True

    plan.solve("maxSpending", {**base, "includeMedicarePartD": False})
    without_d = float(plan.M_n.sum())
    assert plan._include_medicare_part_d is False
    assert without_d < with_d
    assert plan.solverOptions["includeMedicarePartD"] is False  # kept for saving with the case

    plan.solve("maxSpending", {**plan.solverOptions})  # re-solve with the stored options
    assert plan._include_medicare_part_d is False
    assert float(plan.M_n.sum()) == pytest.approx(without_d)


def test_mediVals_plan_ending_before_medicare():
    """A plan can end before anyone reaches 65; Medicare then never starts within it."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 50])  # 65 in 15 years
    Nn = 10
    nm, Lbar, Cbar = tx.mediVals(yobs, np.array([Nn]), np.ones(Nn + 1), Nn, 6)
    assert nm == Nn
    assert Lbar.shape == (0, 5)
    assert Cbar.shape == (0, 6)


def test_plan_ending_before_medicare_solves():
    """A plan that ends before anyone reaches 65 solves, with no Medicare premiums."""
    from pathlib import Path

    from owlplanner.config import readConfig
    from owlplanner.config.plan_bridge import clone

    case = Path(__file__).resolve().parents[2] / "examples" / "Case_joe.toml"
    plan = readConfig(str(case), verbose=False)
    age = date.today().year - int(plan.yobs[0])
    short = clone(plan, expectancy=[age + 3], verbose=False)  # ends well before 65
    short.solve(short.objective, dict(short.solverOptions, solver="HiGHS"))
    assert short.caseStatus == "solved"
    assert float(np.sum(short.medicare_n)) == 0.0


@pytest.mark.parametrize("thisyear", [2026, 2027, 2028, 2030])
def test_irmaa_top_tier_frozen_before_2028(thisyear):
    """The top tier stays at $500k/$750k through 2027 and follows inflation from 2028 (#191)."""
    gamma_n = 1.03 ** np.arange(8)
    for status in (0, 1):
        top = tx.irmaaBrackets[status][-1]
        for n in range(8):
            L = tx.irmaaThresholds(status, gamma_n, n, thisyear)
            assert np.allclose(L[:-1], gamma_n[n] * tx.irmaaBrackets[status][1:-1])
            if thisyear + n <= 2027:
                assert L[-1] == top
            else:
                assert np.isclose(L[-1], top * 1.03 ** (thisyear + n - max(thisyear, 2027)))


def test_mediCosts_top_tier_frozen_in_2027():
    """MAGI just above $500k pays the top tier in 2027 even though lower thresholds grew."""
    thisyear = date.today().year
    if thisyear > 2027:
        pytest.skip("Freeze only applies to bill years before 2028.")
    Nn = 2028 - thisyear + 1
    yobs = np.array([thisyear - 70])
    horizons = np.array([Nn])
    gamma_n = 1.05 ** np.arange(Nn + 1)
    n = 2027 - thisyear
    prevmagi = np.full(2, 501_000.0)
    magi = np.full(Nn, 501_000.0)
    costs = tx.mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn, include_part_d=False)
    top = gamma_n[n] * tx.partB_irmaa_costs[-1]
    assert costs[n] == pytest.approx(top)


# ---------------------------------------------------------------------------
# First Medicare year by months of coverage (issue #208)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mob, tob, first, second",
    [
        (12, 15, 1, 12),  # December 15: December only
        (12, 1, 2, 12),  # December 1: from November 1
        (6, 15, 7, 12),  # June 15: June to December
        (2, 1, 12, 12),  # February 1: from January 1
    ],
)
def test_medicareMonths_first_year(mob, tob, first, second):
    thisyear = date.today().year
    months = tx.medicareMonths([thisyear - 65], [5], 3, [mob], [tob], thisyear)
    assert list(months[0]) == [first, second, second]


def test_medicareMonths_january_first_starts_the_december_before():
    thisyear = date.today().year
    months = tx.medicareMonths([thisyear - 64], [5], 3, [1], [1], thisyear)
    assert list(months[0]) == [1, 12, 12]
    assert list(tx.medicareStartYear([thisyear - 64], [1], [1])) == [thisyear]


def test_medicareMonths_yearly_model_and_horizon():
    """Without birth months, coverage is the whole year of the 65th birthday; none past the horizon."""
    thisyear = date.today().year
    months = tx.medicareMonths([thisyear - 64, thisyear - 70], [3, 2], 4, thisyear=thisyear)
    assert list(months[0]) == [0, 12, 12, 0]
    assert list(months[1]) == [12, 12, 0, 0]


def test_mediCosts_prorates_the_first_year():
    """Born December 15: one month of premium and IRMAA in the year of the 65th birthday."""
    thisyear = date.today().year
    Nn = 3
    magi = np.full(Nn, 1e6)  # top IRMAA tier
    prevmagi = np.full(2, 1e6)
    full = tx.mediCosts([thisyear - 66], [Nn], magi, prevmagi, np.ones(Nn + 1), Nn)
    first = tx.mediCosts([thisyear - 65], [Nn], magi, prevmagi, np.ones(Nn + 1), Nn, mobs=[12], tobs=[15])
    assert np.isclose(first[0], full[0] / 12)
    assert np.isclose(first[1], full[1])


def test_mediVals_prorates_the_first_year():
    """Couple: one spouse born December 1 turns 65 this year, the other is already on Medicare."""
    thisyear = date.today().year
    Nn = 3
    nm, _, Cbar = tx.mediVals([thisyear - 70, thisyear - 65], [Nn, Nn], np.ones(Nn + 1), Nn, 6,
                              mobs=[5, 12], tobs=[10, 1])
    assert nm == 0
    np.testing.assert_allclose(Cbar[0], (1 + 2 / 12) * Cbar[1] / 2)
    # January 1 birthday: Medicare starts in December of the year before.
    nm, _, Cbar = tx.mediVals([thisyear - 64], [Nn], np.ones(Nn + 1), Nn, 6, mobs=[1], tobs=[1])
    assert nm == 0
    np.testing.assert_allclose(Cbar[0], Cbar[1] / 12)


# ---------------------------------------------------------------------------
# Filing status of the lookback return after a death (#213)
# ---------------------------------------------------------------------------


def test_irmaa_status_follows_the_lookback_return():
    """20 CFR 418.1115(c), 418.1135(a): the table of the return 2 years back. First death at the end
    of year 2: years 3 and 4 look back to joint returns; the single table starts in year 5."""
    assert [tx.irmaaStatus([3, 6], n) for n in range(7)] == [1, 1, 1, 1, 1, 0, 0]
    assert [tx.irmaaStatus([6, 3], n) for n in range(7)] == [1, 1, 1, 1, 1, 0, 0]
    assert [tx.irmaaStatus([6], n) for n in range(3)] == [0, 0, 0]


def test_survivor_keeps_the_joint_table_for_two_years():
    """#213 repro: couple's MAGI $190k (single tier 3, below the $218k joint edge), then $120k alone."""
    this_year = date.today().year
    yobs, horizons = np.array([this_year - 70] * 2), np.array([3, 6])
    magi = np.array([190_000.0] * 3 + [120_000.0] * 3)
    costs = tx.mediCosts(yobs, horizons, magi, np.array([190_000.0] * 2), np.ones(6), 6)
    # Annual fees: one survivor, no surcharge (12 x $202.90 = $2,434.80).
    np.testing.assert_allclose(costs[3:5], tx.partB_irmaa_fees[0])
    # Year 5 looks back to year 3, the survivor's own $120k on the single table: tier 1.
    assert costs[5] == pytest.approx(tx.partB_irmaa_fees[0] + tx.partB_irmaa_fees[1] + tx.partD_irmaa_fees[1])
    _, L, _ = tx.mediVals(yobs, horizons, np.ones(6), 6, 6)
    np.testing.assert_allclose(L[:5, 0], tx.irmaaBrackets[1][1])
    assert L[5, 0] == pytest.approx(tx.irmaaBrackets[0][1])


# ---------------------------------------------------------------------------
# The top IRMAA tier includes its edge (#216)
# ---------------------------------------------------------------------------


def test_irmaa_tier_top_includes_its_edge():
    """42 U.S.C. 1395r(i)(3)(C)(i)(III), 20 CFR 418.1115(b)(3): "less than $500,000" for tier 4,
    "at least $500,000" for the top; every lower tier excludes its edge."""
    edges = tx.irmaaBrackets[0][1:]  # 109k, 137k, 171k, 205k, 500k
    assert tx.irmaaTier(109_000, edges) == 0
    assert tx.irmaaTier(109_001, edges) == 1
    assert tx.irmaaTier(499_999, edges) == 4
    assert tx.irmaaTier(500_000, edges) == 5
    # Slack reads a MAGI parked on an edge on that edge's side: below the lower ones, at the top one.
    assert tx.irmaaTier(109_000.5, edges, slack=1.0) == 0
    assert tx.irmaaTier(500_000 - 1e-6, edges, slack=1.0) == 5
    assert tx.irmaaTier(499_998, edges, slack=1.0) == 4  # the optimizer's bracket 4 stops $2 short


@pytest.mark.parametrize("status, edge", [(0, 500_000.0), (1, 750_000.0)])
def test_mediCosts_at_the_top_edge(status, edge):
    """#216 repro: Part B at exactly $500,000 ($750,000 joint) is the top tier, $689.90 (CMS 2026)."""
    this_year = date.today().year
    n_i = status + 1

    def part_b(m):
        return tx.mediCosts(np.array([this_year - 70] * n_i), np.array([3] * n_i), np.full(3, m), np.zeros(2),
                            np.ones(3), 3, include_part_d=False)[2] / n_i / 12
    assert part_b(edge - 1) == pytest.approx(649.20)
    assert part_b(edge) == pytest.approx(689.90)
    assert part_b(edge + 1) == pytest.approx(689.90)


def test_mediCosts_pinned_years_use_the_top_edge():
    """Years 0 and 1 read previousMAGIs: exactly $500,000 is the top tier there too."""
    this_year = date.today().year
    c = tx.mediCosts(np.array([this_year - 70]), np.array([3]), np.zeros(3), np.array([500_000.0, 499_999.0]),
                     np.ones(3), 3, include_part_d=False)
    assert c[0] / 12 == pytest.approx(689.90)
    assert c[1] / 12 == pytest.approx(649.20)


# ---------------------------------------------------------------------------
# A previous MAGI above the year's income ceiling (#215)
# ---------------------------------------------------------------------------


def test_previous_magi_above_the_income_ceiling_is_feasible():
    """Single, 70, $10k/month pension, no savings, $520k MAGI last year (a one-time gain): the pinned
    year's MAGI exceeds the year's income ceiling. Optimize mode was infeasible; it now matches loop."""
    import io
    import warnings

    from owlplanner import Plan

    this_year = date.today().year
    results = {}
    for mode in ("loop", "optimize"):
        p = Plan(["A"], [f"{this_year - 70}-06-15"], [73], "prevmagi", verbose=False, logstreams=[io.StringIO()])
        p.setSpendingProfile("flat")
        p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[0], startDate="01-01")
        p.setPension([10_000], [65], [False])
        p.setAllocationRatios("individual", generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
        p.setRates("user", values=[6, 4, 4, 2.5])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p.solve("maxSpending", {"bequest": 0, "withMedicare": mode, "previousMAGIs": [100, 520]})
        assert p.caseStatus == "solved", mode
        results[mode] = (float(p.g_n[0]), p.medicare_n[:3].copy())
        medical_1 = float(p._medical_n(p.gamma_n)[1])
    assert results["optimize"][0] == pytest.approx(results["loop"][0], rel=1e-6)
    np.testing.assert_allclose(results["optimize"][1], results["loop"][1], rtol=1e-6)
    # Year 1 reads the $520k lookback: the top tier, a year of medical inflation on.
    top = tx.partB_irmaa_costs[5] + tx.partD_irmaa_costs[5]
    assert results["loop"][1][1] == pytest.approx(top * medical_1)
