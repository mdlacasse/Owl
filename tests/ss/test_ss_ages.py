"""
Tests for SS claiming age optimization (withSSAges='optimize').

Tests cover:
- Single individual: the age chosen is the best of the fixed-age solves.
- Couple: both individuals get independent claiming ages.
- Already-claimed: optimizer respects a fixed claiming age for the already-claiming individual.
- Consistency: optimize result >= fixed-age result for maxSpending (optimizer can only do equal or better).

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
from owlplanner import readConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def joe():
    """Single individual plan from example."""
    return readConfig("examples/Case_joe.toml")


@pytest.fixture
def jack_jill():
    """Couple plan from example."""
    return readConfig("examples/Case_jack+jill.toml")


# ---------------------------------------------------------------------------
# withSSAges='optimize' integration tests
# ---------------------------------------------------------------------------


class TestSSAgesOptimize:
    def test_single_solves(self, joe):
        """Single individual: solve completes successfully with optimize."""
        joe.solve("maxSpending", options={"withSSAges": "optimize"})
        assert joe.caseStatus == "solved"

    def test_single_claiming_age_valid(self, joe):
        """Optimal claiming age must be in [62, 70]."""
        joe.solve("maxSpending", options={"withSSAges": "optimize"})
        age = float(joe.ssecAges[0])
        assert 62.0 <= age <= 70.0 + 1e-9

    def test_single_is_best_of_fixed_ages(self, joe):
        """The age chosen gives the same plan as entering it, and no other age entered does better."""
        joe.solve("maxSpending", options={"withSSAges": "optimize"})
        assert joe.caseStatus == "solved"
        age, spending = float(joe.ssecAges[0]), float(joe.g_n[0])
        for other in (age, 62 + 1 / 12, 67, 68 + 2 / 12, 70):
            fixed = readConfig("examples/Case_joe.toml")
            fixed.setSocialSecurity(fixed.ssecAmounts, [other])
            fixed.solve("maxSpending")
            assert fixed.caseStatus == "solved"
            if other == age:
                assert spending == pytest.approx(float(fixed.g_n[0]), abs=1.0)
            else:
                assert spending >= float(fixed.g_n[0]) - 1.0, f"fixed claim at {other:.2f}"

    def test_selection_kept_after_solve(self, joe):
        """The UI reads the selection and the chosen ages back from the plan after a solve."""
        joe.solve("maxSpending", options={"withSSAges": "optimize"})
        assert joe.solverOptions["withSSAges"] == "optimize"
        assert joe._ssa_optimize_set == {0}

    def test_optimize_not_worse_than_fixed(self, joe):
        """Optimize mode should produce spending >= fixed claiming age."""
        joe.solve("maxSpending", options={"withSSAges": "fixed"})
        spending_fixed = float(joe.g_n[0])
        joe.solve("maxSpending", options={"withSSAges": "optimize"})
        spending_opt = float(joe.g_n[0])
        # Optimizer can only do equal or better (within solver gap tolerance)
        assert spending_opt >= spending_fixed - 100, (
            f"Optimize ({spending_opt:.0f}) worse than fixed ({spending_fixed:.0f})"
        )

    def test_couple_both(self, jack_jill):
        """Both ages searched in turn: the solve completes, both ages are in [62, 70], and the plan
        is at least as good as at the ages entered."""
        jack_jill.solve("maxSpending")
        entered = float(jack_jill.g_n[0])
        jack_jill.solve("maxSpending", options={"withSSAges": "optimize"})
        assert jack_jill.caseStatus == "solved"
        for i, age in enumerate(jack_jill.ssecAges):
            assert 62.0 <= float(age) <= 70.0 + 1e-9, f"Individual {i}: age {age:.2f} out of range"
        assert float(jack_jill.g_n[0]) >= entered - 1.0

    def test_partial_optimize_individual_0_only(self, jack_jill):
        """withSSAges=name: only individual 0's age is optimized; individual 1 keeps entered age."""
        name0 = jack_jill.inames[0]
        age1_before = float(jack_jill.ssecAges[1])
        jack_jill.solve("maxSpending", options={"withSSAges": name0})
        assert jack_jill.caseStatus == "solved"
        assert 62.0 <= float(jack_jill.ssecAges[0]) <= 70.0 + 1e-9
        assert abs(float(jack_jill.ssecAges[1]) - age1_before) < 1 / 12, (
            f"Individual 1's age changed: {age1_before:.2f} → {jack_jill.ssecAges[1]:.2f}"
        )

    def test_partial_optimize_individual_1_only(self, jack_jill):
        """withSSAges=[name]: only individual 1's age is optimized; individual 0 keeps entered age."""
        name1 = jack_jill.inames[1]
        age0_before = float(jack_jill.ssecAges[0])
        jack_jill.solve("maxSpending", options={"withSSAges": [name1]})
        assert jack_jill.caseStatus == "solved"
        assert abs(float(jack_jill.ssecAges[0]) - age0_before) < 1 / 12, (
            f"Individual 0's age changed: {age0_before:.2f} → {jack_jill.ssecAges[0]:.2f}"
        )
        assert 62.0 <= float(jack_jill.ssecAges[1]) <= 70.0 + 1e-9


# ---------------------------------------------------------------------------
# Survivor benefit interaction with claiming-age optimization
# ---------------------------------------------------------------------------


class TestSurvivorClaimAge:
    def test_optimize_solves_with_survivor_fra(self, jack_jill):
        """A deferred survivor benefit still solves and is not better than claiming earlier."""
        survivor = jack_jill.inames[1]
        jack_jill.solve("maxSpending", options={"withSSAges": survivor})
        spending_immediate = float(jack_jill.g_n[0])

        deferred = readConfig("examples/Case_jack+jill.toml")
        deferred.setSocialSecurity(
            deferred.ssecAmounts, deferred.ssecAges, survivor_claim_age="FRA"
        )
        deferred.solve("maxSpending", options={"withSSAges": survivor})
        assert deferred.caseStatus == "solved"
        # Jill is past her survivor FRA when Jack dies, so 'fra' resolves to the same date.
        assert float(deferred.g_n[0]) == pytest.approx(spending_immediate, rel=5e-3)


# ---------------------------------------------------------------------------
# Taxes on SS follow the claiming age the MILP picks
# ---------------------------------------------------------------------------


def _exact_ss_plan(age):
    """Single, tax-deferred only, constant rates, an indexed pension from 63.

    With Medicare off and the SS taxable share pinned, the only quantity the loop still feeds
    back is the benefit stream itself, so each claiming-age MILP is exact once taxable SS
    follows the ssb variables.
    """
    import io
    from datetime import date

    import owlplanner as owl

    ty = date.today().year
    p = owl.Plan(["Bo"], [f"{ty - 61}-03-15"], [85], "ss_age_tax", verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[0], taxDeferred=[300], taxFree=[0], startDate="01-01")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("user", values=[6, 4, 3, 2.5])
    p.setSocialSecurity([3000], [age])
    p.setPension([8000], [63], indexed=[True])
    return p


_EXACT_OPTS = {"withMedicare": "None", "withSSTaxability": 0.85, "bequest": 0}


class TestClaimingAgeTaxes:
    def test_result_independent_of_starting_age_and_consistent(self):
        """Same age and spending from any starting age, equal to a fixed-age solve at that age.

        When taxable SS came from the previous iterate's benefits, the plan started at 62 stopped
        on 64 5/12 reporting $104,526/yr, while a fixed-age solve at 64 5/12 gives $104,518/yr:
        the accepted plan had not been charged the tax on its own benefits.
        """
        results = []
        for start in (62, 70):
            p = _exact_ss_plan(start)
            p.solve("maxSpending", options={**_EXACT_OPTS, "withSSAges": "optimize"})
            assert p.caseStatus == "solved"
            results.append((float(p.ssecAges[0]), float(p.g_n[0])))
        assert results[0][0] == pytest.approx(results[1][0])
        assert results[0][1] == pytest.approx(results[1][1], abs=1.0)

        fixed = _exact_ss_plan(results[0][0])
        fixed.solve("maxSpending", options=_EXACT_OPTS)
        assert results[0][1] == pytest.approx(float(fixed.g_n[0]), abs=1.0)

    def test_state_ss_exclusion_follows_the_claiming_age(self):
        """In a state that excludes SS (CA), the state base removes the taxable share of the own
        benefit the MILP picks. With the previous iterate's benefits removed instead, the result
        depended on the starting age (64 2/12 at $99,331 or $99,348/yr) and neither start
        matched the fixed-age solve."""
        results = []
        for start in (62, 70):
            p = _exact_ss_plan(start)
            p.setStateTax("CA")
            p.solve("maxSpending", options={**_EXACT_OPTS, "withSSAges": "optimize"})
            assert p.caseStatus == "solved"
            results.append((float(p.ssecAges[0]), float(p.g_n[0])))
        assert results[0][0] == pytest.approx(results[1][0])
        assert results[0][1] == pytest.approx(results[1][1], abs=1.0)

        fixed = _exact_ss_plan(results[0][0])
        fixed.setStateTax("CA")
        fixed.solve("maxSpending", options=_EXACT_OPTS)
        assert results[0][1] == pytest.approx(float(fixed.g_n[0]), abs=1.0)


# ---------------------------------------------------------------------------
# Claiming ages already in the past cannot be chosen (issue #195)
# ---------------------------------------------------------------------------


@pytest.fixture
def october_2026(monkeypatch):
    """Run on the date issue #195 was reported, past the January date the suite freezes."""
    import datetime

    import owlplanner.plan as plan_module

    class _October(datetime.date):
        @classmethod
        def today(cls):
            return datetime.date(2026, 10, 17)

    monkeypatch.setattr(plan_module, "date", _October)


def _issue195_plan():
    """Couple from issue #195: the higher earner is 66 9/12 in October 2026 and plans to claim
    at 70; the longer-lived spouse already claimed at 62."""
    import io

    import owlplanner as owl

    p = owl.Plan(
        ["Higher Income", "Lower Income"],
        ["1960-01-15", "1958-01-15"],
        [75, 95],
        "issue195",
        verbose=False,
        logstreams=[io.StringIO()],
    )
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[100, 50], taxDeferred=[1000, 0], taxFree=[1000, 0], hsa=[50, 0], startDate="10-16")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("user", values=[6, 4, 3, 2.5])
    p.setSocialSecurity([3800, 1500], [70, 62 + 1 / 12])
    return p


_ISSUE195_OPTS = {"withSSAges": "Higher Income", "bequest": 0}


@pytest.mark.usefixtures("october_2026")
class TestNoPastClaimingAge:
    def test_open_ages_start_this_month(self):
        """The candidates run from the age reached this month to 70, never a month behind us."""
        p = _issue195_plan()
        assert p._ssaCurrentAgeMonths(0) == 66 * 12 + 9
        ages = p._ssaOpenAges(0)
        assert round(ages[0] * 12) == 66 * 12 + 9
        assert ages[-1] == pytest.approx(70.0)
        assert len(ages) == 40

    def test_optimized_age_not_in_the_past(self):
        """The optimizer used to pick 65 11/12, collecting a full year of benefits it never could."""
        p = _issue195_plan()
        p.solve("maxSpending", options=_ISSUE195_OPTS)
        assert p.caseStatus == "solved"
        assert round(float(p.ssecAges[0]) * 12) >= 66 * 12 + 9
        assert float(p.ssecAges[1]) == pytest.approx(62 + 1 / 12)

    def test_selected_past_age_is_refused(self):
        """A selected individual whose entered age is past is an error, not silently skipped.

        The unselected spouse, who claimed at 62, keeps that age without complaint.
        """
        p = _issue195_plan()
        p.setSocialSecurity([3800, 1500], [66 + 6 / 12, 62 + 1 / 12])
        with pytest.raises(ValueError, match="Higher Income's SS claiming age .* is already past"):
            p.solve("maxSpending", options=_ISSUE195_OPTS)
        p.setSocialSecurity([3800, 1500], [66 + 9 / 12, 62 + 1 / 12])  # this month: still open
        p.solve("maxSpending", options=_ISSUE195_OPTS)
        assert p.caseStatus == "solved"
        assert float(p.ssecAges[1]) == pytest.approx(62 + 1 / 12)

    def test_optimize_matches_best_fixed_age(self):
        """With the loops made exact, optimizing must do at least as well as the entered age.

        The survivor (living to 95) depends on the deceased's claiming age, but that benefit and
        the spousal add-on were parameters from the previous iterate, so the MILP did not see
        that claiming later raises them: it picked 66 9/12 at $186,526/yr against $188,445/yr
        for claiming at 70. With the household's streams tabulated per candidate age it picks 70.
        """
        exact = {"withSSTaxability": 0.85, "withMedicare": "None", "bequest": 0}
        fixed = _issue195_plan()
        fixed.solve("maxSpending", options=exact)
        p = _issue195_plan()
        p.solve("maxSpending", options={**exact, "withSSAges": "Higher Income"})
        assert p.caseStatus == "solved"
        assert float(p.ssecAges[0]) == pytest.approx(70.0)
        assert float(p.g_n[0]) >= float(fixed.g_n[0]) - 1.0

    def test_loop_mode_not_worse_than_any_entered_age(self):
        """Issue #195 follow-up, with the taxes left to the loop as reported.

        The MILP taxed each candidate age's benefits at the share the loop had settled for the
        current age. Here it returned $190,539/yr where entering 70 gives $190,692/yr; on the case
        as reported, 66 9/12 at $212,026/yr where 68 6/12 entered by hand gives $212,233/yr.
        Each candidate is now a fixed-age solve.
        """
        p = _issue195_plan()
        p.solve("maxSpending", options=_ISSUE195_OPTS)
        assert p.caseStatus == "solved"
        for age in (66 + 9 / 12, 68 + 6 / 12, 70):
            fixed = _issue195_plan()
            fixed.setSocialSecurity([3800, 1500], [age, 62 + 1 / 12])
            fixed.solve("maxSpending", options={"bequest": 0})
            assert fixed.caseStatus == "solved"
            assert float(p.g_n[0]) >= float(fixed.g_n[0]) - 1.0, f"fixed claim at {age:.2f}"
