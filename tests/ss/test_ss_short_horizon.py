"""
Tests for compute_social_security_benefits with short plan horizons.

Edge cases covered:
- Claiming age beyond plan horizon: payment_start_n >= N_n (no IndexError, zero benefits).
- Claiming age exactly at the last year of the plan.
- Couple where one spouse's claiming age falls outside their drawn longevity horizon.
- Couple where both spouses' claiming ages fall outside their short horizons.
- Integration: clone with short expectancy + setSocialSecurity should not raise.

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
from owlplanner.socialsecurity import compute_social_security_benefits
from owlplanner import readConfig
from owlplanner.config.plan_bridge import clone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

THISYEAR = 2026


def _ss(pias, ages, yobs, mobs, tobs, horizons, N_n):
    """Thin wrapper so tests don't repeat keyword args."""
    return compute_social_security_benefits(
        pias,
        ages,
        yobs,
        mobs,
        tobs,
        horizons,
        N_i=len(pias),
        N_n=N_n,
        thisyear=THISYEAR,
    )


# ---------------------------------------------------------------------------
# Single individual
# ---------------------------------------------------------------------------


class TestSingleShortHorizon:
    def test_claiming_age_beyond_horizon_no_error(self):
        """payment_start_n > N_n must not raise IndexError; benefits should be zero."""
        # Born 1963-01, claiming at 70 → payment_start_n = 1963 + 70 - 2026 = 7
        # Plan horizon = 6 years (die at age 68 in 2031)
        yobs, mobs, tobs = [1963], [1], [15]
        horizons = [6]
        N_n = 6
        zeta, _ = _ss([2000], [70], yobs, mobs, tobs, horizons, N_n)
        assert zeta.shape == (1, N_n)
        assert np.all(zeta == 0), "No benefits should be paid if SS starts after plan ends."

    def test_claiming_age_at_last_year(self):
        """payment_start_n == N_n - 1: benefits only in final year, partial-year prorated."""
        # Born 1963-01, claiming at 67 → payment_start_n = 1963 + 67 - 2026 = 4
        # Plan horizon = 5 (die at age 67 in 2030, last year index = 4)
        yobs, mobs, tobs = [1963], [1], [15]
        horizons = [5]
        N_n = 5
        zeta, _ = _ss([1200], [67], yobs, mobs, tobs, horizons, N_n)
        assert zeta.shape == (1, N_n)
        assert zeta[0, 4] >= 0, "Partial benefit in final year must be non-negative."
        assert np.all(zeta[0, :4] == 0), "No benefits before claiming year."

    def test_normal_horizon_unchanged(self):
        """Long horizon: benefits are positive for most years (regression guard)."""
        yobs, mobs, tobs = [1963], [1], [15]
        horizons = [30]
        N_n = 30
        zeta, _ = _ss([2000], [67], yobs, mobs, tobs, horizons, N_n)
        assert zeta.shape == (1, N_n)
        assert np.sum(zeta) > 0, "Should receive benefits over a 30-year horizon."


# ---------------------------------------------------------------------------
# Couple
# ---------------------------------------------------------------------------


class TestCoupleShortHorizon:
    def test_one_spouse_claiming_beyond_horizon(self):
        """One spouse's claiming age falls past their short horizon; other is normal."""
        # Chris born 1963-01, claims at 70 → payment_start_n = 7, horizon = 6
        # Pat  born 1966-01, claims at 62 → payment_start_n = 2, horizon = 6
        yobs = [1963, 1966]
        mobs = [1, 1]
        tobs = [15, 15]
        horizons = [6, 6]
        N_n = 6
        zeta, _ = _ss([2000, 1400], [70, 62], yobs, mobs, tobs, horizons, N_n)
        assert zeta.shape == (2, N_n)
        assert np.all(zeta[0] == 0), "Chris SS starts after plan ends; should be zero."
        assert np.sum(zeta[1]) > 0, "Pat claims at 62, within horizon; should have benefits."

    def test_both_spouses_claiming_beyond_horizon(self):
        """Both claiming ages fall past their (drawn) short horizons; no error, all zeros."""
        # Born 1963 and 1966, both claim at 70
        # Horizons = 4 and 3 years → both die before 70
        yobs = [1963, 1966]
        mobs = [1, 1]
        tobs = [15, 15]
        horizons = [4, 3]
        N_n = 4
        zeta, _ = _ss([2000, 1400], [70, 70], yobs, mobs, tobs, horizons, N_n)
        assert zeta.shape == (2, N_n)
        assert np.all(zeta == 0), "Both die before claiming age 70; all zeros expected."

    def test_short_survivor_horizon(self):
        """Shorter-lived spouse dies early; survivor benefits must not overflow."""
        # Chris born 1963-01 horizon=4, Pat born 1966-01 horizon=8, N_n=8
        # Chris claims at 67 (payment_start_n=4 = nd for Chris; slice is empty)
        yobs = [1963, 1966]
        mobs = [1, 1]
        tobs = [15, 15]
        horizons = [4, 8]
        N_n = 8
        zeta, _ = _ss([2000, 1400], [67, 67], yobs, mobs, tobs, horizons, N_n)
        assert zeta.shape == (2, N_n)
        # Pat survives; should receive something (own + possible survivor)
        assert np.sum(zeta[1]) > 0


# ---------------------------------------------------------------------------
# Integration: clone with short expectancy
# ---------------------------------------------------------------------------


class TestCloneShortExpectancy:
    @pytest.fixture
    def chris_pat(self):
        return readConfig("examples/Case_chris+pat.toml")

    def test_scenario_185_no_error(self, chris_pat):
        """Clone reproducing scenario 185: Chris age 68, Pat age 64 (N_n=6)."""
        p2 = clone(chris_pat, expectancy=[68, 64])
        p2.setRates("conservative")
        p2.solve("maxSpending")
        assert p2.N_n == 6

    def test_scenario_161_no_error(self, chris_pat):
        """Clone reproducing scenario 161: Chris age 63, Pat age 65 (N_n=6)."""
        p2 = clone(chris_pat, expectancy=[63, 65])
        p2.setRates("conservative")
        p2.solve("maxSpending")
        assert p2.N_n == 6

    def test_very_short_horizon_no_error(self, chris_pat):
        """Extreme short horizon: both die at 64; SS claiming age 70 is beyond horizon."""
        # Chris born 1963: horizon = 1963+64-2026+1 = 2; Pat born 1966: horizon = 5; N_n = 5
        p2 = clone(chris_pat, expectancy=[64, 64])
        p2.setRates("conservative")
        p2.solve("maxSpending")
        assert p2.N_n == 5


class TestSurvivorClaimAgeUnderSampledLongevity:
    """Longevity sampling clones a plan per drawn lifespan (see stresstests.py).

    Each clone is rebuilt from the case configuration, so the survivor claiming setting
    carries over and is *re-resolved* against that scenario's death year. It is a policy
    ("claim at the survivor's FRA"), not a fixed calendar date — which is the meaningful
    reading when the year of the first death is itself random.
    """

    @pytest.fixture
    def jack_jill(self):
        return readConfig("examples/Case_jack+jill.toml")

    # Draws chosen to cover: the base case, a swapped survivor, equal lifespans,
    # and early deaths that leave the survivor below their survivor FRA.
    DRAWS = [[89, 92], [95, 70], [70, 95], [85, 85], [64, 95], [95, 64], [66, 100]]

    @pytest.mark.parametrize("setting", ["immediate", "FRA", 63])
    def test_setting_survives_cloning(self, jack_jill, setting):
        jack_jill.setSocialSecurity(jack_jill.ssecAmounts, jack_jill.ssecAges, survivor_claim_age=setting)
        expected = jack_jill.ssecSurvivorClaimAge
        for draw in self.DRAWS:
            c = clone(jack_jill, expectancy=draw, verbose=False)
            assert c.ssecSurvivorClaimAge == expected, f"draw {draw} lost the setting"

    @pytest.mark.parametrize("setting", ["immediate", "FRA", 63])
    def test_invariants_hold_for_every_draw(self, jack_jill, setting):
        from owlplanner import socialsecurity as socsec

        jack_jill.setSocialSecurity(jack_jill.ssecAmounts, jack_jill.ssecAges, survivor_claim_age=setting)
        for draw in self.DRAWS:
            c = clone(jack_jill, expectancy=draw, verbose=False)
            surv = socsec.compute_survivor_stream(
                c.ssecAmounts, c.ssecAges, c.yobs, c.mobs, c.tobs, c.horizons, c.N_i, c.N_n,
                survivor_claim_age=c.ssecSurvivorClaimAge,
            )
            if surv.survivor_idx < 0:
                assert np.all(surv.annual == 0)
                continue
            isv, nd = surv.survivor_idx, surv.death_year_n
            age_at_death = (c.year_n[0] + nd) - c.yobs[isv] - (c.mobs[isv] - 1) / 12
            msg = f"draw {draw}, setting {setting!r}"
            assert surv.claim_age >= 60 - 1e-9, msg
            assert surv.claim_age >= age_at_death - 1e-9, msg  # never before the first death
            assert surv.claim_age <= max(surv.survivor_fra, age_at_death) + 1e-9, msg
            assert np.all(surv.annual[:nd] == 0), msg  # nothing paid before the first death
            assert len(surv.annual) == c.N_n, msg

    def test_deferral_only_bites_when_survivor_is_below_fra(self, jack_jill):
        """'FRA' matches 'immediate' unless the survivor is under their survivor FRA at death."""
        from owlplanner import socialsecurity as socsec

        def stream(setting, draw):
            jack_jill.setSocialSecurity(jack_jill.ssecAmounts, jack_jill.ssecAges, survivor_claim_age=setting)
            c = clone(jack_jill, expectancy=draw, verbose=False)
            return socsec.compute_survivor_stream(
                c.ssecAmounts, c.ssecAges, c.yobs, c.mobs, c.tobs, c.horizons, c.N_i, c.N_n,
                survivor_claim_age=c.ssecSurvivorClaimAge,
            )

        # Survivor is 87 at the first death: already past their survivor FRA, so identical.
        assert np.allclose(stream("immediate", [89, 92]).annual, stream("FRA", [89, 92]).annual)
        # Survivor is 62 at the first death: deferral delays the start and raises the amount.
        early_now, early_fra = stream("immediate", [64, 95]), stream("FRA", [64, 95])
        assert not np.allclose(early_now.annual, early_fra.annual)
        assert early_fra.claim_age > early_now.claim_age
        assert early_fra.annual.max() > early_now.annual.max()


class TestSurvivorClaimAgeLogging:
    """An overridden survivor claiming age must not pass silently."""

    @pytest.fixture
    def jack_jill(self):
        return readConfig("examples/Case_jack+jill.toml")

    @staticmethod
    def _log_for(plan, draw, setting):
        import io

        p = clone(plan, expectancy=draw, verbose=False)
        buf = io.StringIO()
        p.setLogstreams(True, [buf, buf])
        p.setSocialSecurity(p.ssecAmounts, p.ssecAges, survivor_claim_age=setting)
        return buf.getvalue()

    def test_age_before_the_first_death_warns(self, jack_jill):
        """Jill is 87 when Jack dies, so an age of 62 cannot be honored."""
        log = self._log_for(jack_jill, [89, 92], 62)
        assert "WARNING" in log
        assert "ignored" in log and "87.00" in log

    def test_age_past_survivor_fra_warns(self, jack_jill):
        """Survivor benefits earn no delayed credits, so 70 is capped and flagged."""
        log = self._log_for(jack_jill, [64, 95], 70)
        assert "WARNING" in log
        assert "no delayed credits" in log

    def test_honored_age_does_not_warn(self, jack_jill):
        """An age Owl can honor produces no warning."""
        log = self._log_for(jack_jill, [64, 95], 65)
        assert "WARNING" not in log

    def test_permanent_reduction_is_reported(self, jack_jill):
        """Claiming below the survivor FRA is reported even though nothing was overridden."""
        log = self._log_for(jack_jill, [64, 95], "immediate")
        assert "WARNING" not in log  # nothing was overridden
        assert "permanently reduced" in log
        assert "'FRA'" in log  # points at the alternative

    def test_no_reduction_notice_when_past_survivor_fra(self, jack_jill):
        """The common case — survivor already past their survivor FRA — stays quiet."""
        log = self._log_for(jack_jill, [89, 92], "immediate")
        assert "WARNING" not in log
        assert "permanently reduced" not in log
