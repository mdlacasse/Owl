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

    def test_survivor_folded_when_deceased_age_is_fixed(self, jack_jill):
        """Optimizing only the survivor's age leaves the survivor stream constant, so it folds.

        Jack dies first; optimizing Jill's claiming age alone keeps Jack's fixed, which is the
        common real case (one spouse already collecting).
        """
        from owlplanner import socialsecurity as socsec

        survivor_name = jack_jill.inames[1]
        jack_jill.solve("maxSpending", options={"withSSAges": survivor_name})
        assert jack_jill._ssa_fold_survivor

        survivor = socsec.compute_survivor_stream(
            jack_jill.ssecAmounts,
            jack_jill.ssecAges,
            jack_jill.yobs,
            jack_jill.mobs,
            jack_jill.tobs,
            jack_jill.horizons,
            jack_jill.N_i,
            jack_jill.N_n,
            survivor_claim_age=jack_jill.ssecSurvivorClaimAge,
            trim_pct=jack_jill.ssecTrimPct or 0,
            trim_year=jack_jill.ssecTrimYear,
        )
        assert survivor.survivor_idx >= 0
        nd, isv = survivor.death_year_n, survivor.survivor_idx
        # Every candidate claiming age carries at least the survivor benefit after the death.
        surv_nominal = survivor.annual[nd:] * jack_jill.gamma_n[:-1][nd:]
        assert np.all(jack_jill._ssa_B_own[isv, :, nd:] >= surv_nominal - 1e-6)
        # And the offset carries nothing after the death: the fold made it exact.
        assert np.allclose(jack_jill._ssa_spousal_offset[isv, nd:], 0.0, atol=1e-6)

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
        """When the first-to-die's age is also a variable, the survivor rides in the offset.

        Jack is 63 with a claiming age of 70, so 'optimize' leaves his age free and the survivor
        amount depends on the age the solver picks; the fold cannot apply.
        """
        jack_jill.solve("maxSpending", options={"withSSAges": "optimize"})
        assert jack_jill.caseStatus == "solved"
        assert not jack_jill._ssa_fold_survivor
        assert np.all(jack_jill._ssa_spousal_offset > -1e-6)
