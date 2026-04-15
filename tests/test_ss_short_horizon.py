"""
Tests for compute_social_security_benefits with short plan horizons.

Edge cases covered:
- Claiming age beyond plan horizon: payment_start_n >= N_n (no IndexError, zero benefits).
- Claiming age exactly at the last year of the plan.
- Couple where one spouse's claiming age falls outside their drawn longevity horizon.
- Couple where both spouses' claiming ages fall outside their short horizons.
- Integration: clone with short expectancy + setSocialSecurity should not raise.
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
        pias, ages, yobs, mobs, tobs, horizons,
        N_i=len(pias), N_n=N_n, thisyear=THISYEAR,
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
