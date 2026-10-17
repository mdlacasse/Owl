"""
Tests for SS claiming age optimization (withSSAges='optimize').

Tests cover:
- Single individual: optimizer should delay claiming when horizon is long.
- Couple: both individuals get independent claiming ages.
- Already-claimed: optimizer respects a fixed claiming age for the already-claiming individual.
- Consistency: optimize result >= fixed-age result for maxSpending (optimizer can only do equal or better).
- build_own_benefit_table: basic shape and value checks.

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
from owlplanner import readConfig
from owlplanner.socialsecurity import build_own_benefit_table, getFRAs


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
# build_own_benefit_table tests
# ---------------------------------------------------------------------------


class TestBuildOwnBenefitTable:
    def test_shape(self):
        pias = [2000]
        yobs = [1960]
        mobs = [6]
        tobs = [15]
        horizons = [30]
        N_i, N_n = 1, 30
        gamma_n = np.ones(N_n)
        fras = getFRAs(yobs, mobs, tobs)
        B, ages_k = build_own_benefit_table(pias, fras, yobs, mobs, tobs, horizons, N_i, N_n, gamma_n)
        assert B.shape == (1, 97, 30)
        assert ages_k.shape == (97,)

    def test_ages_k_range(self):
        """ages_k should span 62.0 to 70.0 in 1/12-year steps."""
        pias = [2000]
        yobs = [1960]
        mobs = [6]
        tobs = [15]
        horizons = [30]
        N_i, N_n = 1, 30
        gamma_n = np.ones(N_n)
        fras = getFRAs(yobs, mobs, tobs)
        _, ages_k = build_own_benefit_table(pias, fras, yobs, mobs, tobs, horizons, N_i, N_n, gamma_n)
        assert abs(ages_k[0] - 62.0) < 1e-9
        assert abs(ages_k[96] - 70.0) < 1e-9
        assert abs(ages_k[1] - ages_k[0] - 1 / 12) < 1e-9

    def test_zero_pia(self):
        """Zero PIA produces all-zero benefit table."""
        pias = [0]
        yobs = [1960]
        mobs = [6]
        tobs = [15]
        horizons = [30]
        N_i, N_n = 1, 30
        gamma_n = np.ones(N_n)
        fras = getFRAs(yobs, mobs, tobs)
        B, _ = build_own_benefit_table(pias, fras, yobs, mobs, tobs, horizons, N_i, N_n, gamma_n)
        assert np.all(B == 0)

    def test_delay_increases_benefit(self):
        """Claiming at 70 should yield higher per-year benefit than at 62 (FRA=67, delay rate=8%/yr)."""
        pias = [2000]
        yobs = [1960]
        mobs = [6]
        tobs = [15]
        N_n = 35
        horizons = [N_n]
        gamma_n = np.ones(N_n)
        fras = getFRAs(yobs, mobs, tobs)
        B, ages_k = build_own_benefit_table(pias, fras, yobs, mobs, tobs, horizons, 1, N_n, gamma_n, thisyear=2026)
        # Find k=0 (age 62) and k=96 (age 70)
        # B_at_70 > B_at_62 for years after both payment start dates
        k_62 = 0
        k_70 = 96
        # Benefit after both start paying (year 31+ since born 1960, planning from 2026)
        # age 70 in year 2030, age 62 in year 2022 (already started)
        # For years deep in the plan, compare per-year benefits
        mid = 20
        assert B[0, k_70, mid] > B[0, k_62, mid]

    def test_trim(self):
        """trim_pct reduces benefits from trim_year onward."""
        pias = [2000]
        yobs = [1960]
        mobs = [6]
        tobs = [15]
        N_n = 30
        horizons = [N_n]
        gamma_n = np.ones(N_n)
        fras = getFRAs(yobs, mobs, tobs)
        B_no_trim, _ = build_own_benefit_table(pias, fras, yobs, mobs, tobs, horizons, 1, N_n, gamma_n, thisyear=2026)
        B_trimmed, _ = build_own_benefit_table(
            pias, fras, yobs, mobs, tobs, horizons, 1, N_n, gamma_n, trim_pct=25, trim_year=2036, thisyear=2026
        )
        # Before trim year: equal
        np.testing.assert_array_almost_equal(B_no_trim[:, :, :10], B_trimmed[:, :, :10])
        # After trim year: trimmed is 75% of full
        np.testing.assert_allclose(B_trimmed[:, :, 10:], B_no_trim[:, :, 10:] * 0.75)


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

    def test_single_delays_claiming(self, joe):
        """For a healthy long horizon, optimizer should delay past FRA (67)."""
        joe.solve("maxSpending", options={"withSSAges": "optimize"})
        age = float(joe.ssecAges[0])
        assert age > 67.0, f"Expected age > 67, got {age:.2f}"

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

    def test_couple_solves(self, jack_jill):
        """Couple: solve completes successfully."""
        jack_jill.solve("maxSpending", options={"withSSAges": "optimize"})
        assert jack_jill.caseStatus == "solved"

    def test_couple_claiming_ages_valid(self, jack_jill):
        """Both individuals must claim in [62, 70]."""
        jack_jill.solve("maxSpending", options={"withSSAges": "optimize"})
        for i, age in enumerate(jack_jill.ssecAges):
            assert 62.0 <= float(age) <= 70.0 + 1e-9, f"Individual {i}: age {age:.2f} out of range"

    def test_couple_ages_may_differ(self, jack_jill):
        """Each individual should have an independent optimal claiming age."""
        jack_jill.solve("maxSpending", options={"withSSAges": "optimize"})
        # Not strictly required to differ, but they typically will for a couple
        # (at least one should differ from default 67)
        ages = [float(a) for a in jack_jill.ssecAges]
        assert any(abs(a - 67.0) > 1 / 12 for a in ages), f"Both ages appear to be 67: {ages}"

    def test_ssa_lp_flag_reset_between_solves(self, joe):
        """_ssa_lp flag is reset when switching back to fixed mode."""
        joe.solve("maxSpending", options={"withSSAges": "optimize"})
        assert joe._ssa_lp is True
        joe.solve("maxSpending")  # default: fixed
        assert joe._ssa_lp is False

    def test_zssa_not_in_vm_for_fixed_mode(self, joe):
        """In fixed mode, zssa and ssb should not be in vm."""
        joe.solve("maxSpending")
        assert "zssa" not in joe.vm
        assert "ssb" not in joe.vm

    def test_zssa_in_vm_for_optimize_mode(self, joe):
        """In optimize mode, zssa and ssb must be in vm."""
        joe.solve("maxSpending", options={"withSSAges": "optimize"})
        assert "zssa" in joe.vm
        assert "ssb" in joe.vm

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


class TestSurvivorOffset:
    """The spousal/survivor parameter offset must stay well-formed in optimize mode.

    Regression: the survivor benefit used to overwrite the survivor's own benefit for the
    rest of the horizon, which made `zetaBar_in - B_own[k]` go sharply negative and fed the
    LP a large phantom income deduction for every candidate claiming age.
    """

    def test_offset_is_non_negative(self, jack_jill):
        jack_jill.solve("maxSpending", options={"withSSAges": "optimize"})
        offset = jack_jill._ssa_spousal_offset
        assert np.all(offset > -1e-6), f"Negative SS offset: min {offset.min():.2f}"

    def test_pair_tabulated_when_one_age_is_free(self, jack_jill):
        """Optimizing one spouse's age alone makes every household benefit a function of it.

        Jack dies first; optimizing Jill's claiming age alone keeps Jack's fixed, which is the
        common real case (one spouse already collecting). The full streams are tabulated, so
        the modeled benefit at the chosen ages is the benefit itself and the offset vanishes.
        """
        survivor_name = jack_jill.inames[1]
        jack_jill.solve("maxSpending", options={"withSSAges": survivor_name})
        assert jack_jill._ssa_pair_exact

        k_opt = np.round((np.asarray(jack_jill.ssecAges, dtype=float) - 62) * 12).astype(int)
        np.testing.assert_allclose(jack_jill._ssaModeledBenefit(k_opt), jack_jill.zetaBar_in, atol=1e-6)
        assert np.allclose(jack_jill._ssa_spousal_offset, 0.0, atol=1e-6)

    def test_optimize_solves_with_survivor_fra(self, jack_jill):
        """A deferred survivor benefit still solves and is not better than claiming earlier."""
        jack_jill.solve("maxSpending", options={"withSSAges": "optimize"})
        spending_immediate = float(jack_jill.g_n[0])

        deferred = readConfig("examples/Case_jack+jill.toml")
        deferred.setSocialSecurity(
            deferred.ssecAmounts, deferred.ssecAges, survivor_claim_age="FRA"
        )
        deferred.solve("maxSpending", options={"withSSAges": "optimize"})
        assert deferred.caseStatus == "solved"
        # Jill is past her survivor FRA when Jack dies, so 'fra' resolves to the same date.
        assert float(deferred.g_n[0]) == pytest.approx(spending_immediate, rel=5e-3)

    def test_both_optimized_uses_offset_path(self, jack_jill):
        """When both ages are variables, spousal and survivor amounts ride in the offset.

        Jack is 63 with a claiming age of 70, so 'optimize' leaves both ages free and the
        survivor amount depends on the pair of ages the solver picks; it cannot be tabulated.
        """
        jack_jill.solve("maxSpending", options={"withSSAges": "optimize"})
        assert jack_jill.caseStatus == "solved"
        assert not jack_jill._ssa_pair_exact
        assert not np.any(jack_jill._ssa_B_cross)
        assert np.all(jack_jill._ssa_spousal_offset > -1e-6)


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
    def test_tax_rows_carry_ssb(self):
        """The taxable-income row charges Psi_n on the own-benefit variable."""
        p = _exact_ss_plan(67)
        p.solve("maxSpending", options={**_EXACT_OPTS, "withSSAges": "optimize"})
        assert p.caseStatus == "solved"
        const, idx = p._ss_benefit_terms(0, 10)
        assert idx == p.vm["ssb"].idx(0, 10)
        assert const == pytest.approx(p._ssa_spousal_offset[0, 10])

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
    def test_past_months_blocked_in_benefit_choice(self):
        """Every zssa column for a month already behind us is bounded to zero."""
        p = _issue195_plan()
        p.solve("maxSpending", options=_ISSUE195_OPTS)
        assert p.caseStatus == "solved"
        current = p._ssaCurrentAgeMonths(0)
        assert current == 66 * 12 + 9
        _, ub = p.B.arrays()
        for k in range(p._ssa_N_K):
            month = 62 * 12 + k
            expected = 0 if month < current else 1
            assert ub[p.vm["zssa"].idx(0, k)] == expected, f"Claiming month {month // 12}y{month % 12}m"

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
        assert p._ssa_pair_exact
        assert float(p.ssecAges[0]) == pytest.approx(70.0)
        assert float(p.g_n[0]) >= float(fixed.g_n[0]) - 1.0
