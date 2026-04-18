"""
Edge-case tests for short planning horizons.

Background
----------
plan.py used to reject N_n <= 2, and stresstests.py used to treat any
last-survivor horizon <= 2 as g_s = 0.  Both thresholds were too conservative:

  * For a single individual N_n = 2 is perfectly valid.
  * For a couple, the bug was actually in _add_roth_conversions (plan.py:1820),
    which accessed x[i, horizons[i] - 2] without guarding against horizons[i] < 2.
    A couple with horizons = [1, 3] (N_n = 3) would silently corrupt variable
    bounds via a negative index, yet N_n = 3 passed the old guard.

Fixes applied
-------------
  * plan.py:218   — threshold lowered from <= 2 to <= 1.
  * plan.py:1820  — loop guarded with max(0, horizons[i] - 2) so horizons[i] = 1
                    no longer produces a negative index.
  * stresstests.py — both `horizon <= 2` checks lowered to `horizon <= 1`.

Tests in this file verify those three changes end-to-end.
"""
from datetime import date

import numpy as np
import pytest

import owlplanner as owl
import owlplanner.stresstests as stresstests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

THISYEAR = date.today().year


def _single_plan(n_n: int, name: str = "test") -> owl.Plan:
    """Return a minimal single-person plan whose horizon is exactly n_n years."""
    # horizons[0] = yobs + expectancy - thisyear + 1 = n_n
    # so expectancy = n_n + thisyear - yobs - 1 = n_n + age - 1
    age = 65
    yobs = THISYEAR - age
    expectancy = n_n + age - 1   # gives horizons[0] = n_n
    p = owl.Plan([name], [f"{yobs}-06-15"], [expectancy], name, verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[200], taxDeferred=[400], taxFree=[100], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setSocialSecurity([0], [70])
    p.setRates("default")
    return p


def _couple_plan(horizons: list, name: str = "test-couple") -> owl.Plan:
    """
    Return a minimal couple plan with the given individual horizons (in years).
    horizons must have exactly 2 elements; N_n = max(horizons).
    """
    assert len(horizons) == 2
    age0, age1 = 65, 62
    yobs0, yobs1 = THISYEAR - age0, THISYEAR - age1
    exp0 = horizons[0] + age0 - 1
    exp1 = horizons[1] + age1 - 1
    inames = ["Abi", "Bob"]
    dobs = [f"{yobs0}-06-15", f"{yobs1}-06-15"]
    p = owl.Plan(inames, dobs, [exp0, exp1], name, verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(
        taxable=[150, 100], taxDeferred=[300, 200], taxFree=[80, 60], startDate="1-1"
    )
    p.setAllocationRatios(
        "individual",
        generic=[
            [[60, 40, 0, 0], [60, 40, 0, 0]],
            [[60, 40, 0, 0], [60, 40, 0, 0]],
        ],
    )
    p.setSocialSecurity([0, 0], [70, 70])
    p.setRates("default")
    return p


# ---------------------------------------------------------------------------
# Plan constructor threshold
# ---------------------------------------------------------------------------

class TestPlanConstructorThreshold:
    def test_n_n_1_raises(self):
        """N_n = 1 must still be rejected."""
        age = 65
        yobs = THISYEAR - age
        # expectancy = age gives horizons = 1
        with pytest.raises(ValueError, match="more than"):
            owl.Plan(["Pat"], [f"{yobs}-06-15"], [age], "too-short", verbose=False)

    def test_n_n_2_single_constructs(self):
        """Single person with N_n = 2 must now construct without error."""
        p = _single_plan(2)
        assert p.N_n == 2
        assert list(p.horizons) == [2]

    def test_n_n_2_single_solves(self):
        """Single person with N_n = 2 must solve to optimality."""
        p = _single_plan(2)
        p.solve("maxSpending")
        assert p.caseStatus == "solved"
        assert p.g_n[0] > 0

    def test_n_n_3_single_constructs(self):
        """N_n = 3 must still construct (regression guard)."""
        p = _single_plan(3)
        assert p.N_n == 3


# ---------------------------------------------------------------------------
# Roth disallowance for short individual horizons
# ---------------------------------------------------------------------------

class TestRothDisallowanceShortHorizon:
    def test_n_n_2_single_no_roth(self):
        """For a 2-year single plan both Roth conversion years must be zeroed."""
        p = _single_plan(2)
        p.solve("maxSpending")
        # x_in shape (N_i, N_n); both years must be zero (rounded to 0 by solver)
        assert p.x_in is not None
        np.testing.assert_allclose(p.x_in[0, :], 0, atol=1)

    def test_couple_horizon_1_3_no_roth_for_deceased(self):
        """
        Couple with horizons [1, 3]: individual 0 lives only 1 year.
        The Roth guard must not produce a negative index (old bug) and
        must zero year 0 for individual 0 without corrupting other bounds.
        """
        p = _couple_plan([1, 3])
        assert list(p.horizons) == [1, 3]
        assert p.N_n == 3
        p.solve("maxSpending")
        assert p.caseStatus == "solved"
        # Individual 0 (horizon=1): only year 0 exists; it must be zero
        assert p.x_in[0, 0] == pytest.approx(0, abs=1)

    def test_couple_horizon_2_4_last_two_zeroed(self):
        """
        Couple with horizons [2, 4]: individual 0 has exactly 2 years.
        Both years must be Roth-excluded; individual 1's last 2 of 4 must also be zeroed.
        """
        p = _couple_plan([2, 4])
        assert p.N_n == 4
        p.solve("maxSpending")
        assert p.caseStatus == "solved"
        # Individual 0 (horizon=2): years 0 and 1 must be zero
        np.testing.assert_allclose(p.x_in[0, :2], 0, atol=1)
        # Individual 1 (horizon=4): years 2 and 3 must be zero
        np.testing.assert_allclose(p.x_in[1, 2:4], 0, atol=1)


# ---------------------------------------------------------------------------
# Couple with one 1-year horizon: the previously crashing bug
# ---------------------------------------------------------------------------

class TestCoupleOneYearHorizon:
    def test_horizons_1_3_constructs(self):
        """Couple with horizons [1, 3] must construct (N_n = 3, was crashing)."""
        p = _couple_plan([1, 3])
        assert p.N_n == 3
        assert list(p.horizons) == [1, 3]

    def test_horizons_1_3_solves(self):
        """Couple with horizons [1, 3] must solve to optimality."""
        p = _couple_plan([1, 3])
        p.solve("maxSpending")
        assert p.caseStatus == "solved"
        assert p.g_n[0] > 0

    def test_horizons_1_4_solves(self):
        """Couple with horizons [1, 4] must also solve correctly."""
        p = _couple_plan([1, 4])
        assert p.N_n == 4
        p.solve("maxSpending")
        assert p.caseStatus == "solved"


# ---------------------------------------------------------------------------
# Stochastic spending: short-horizon threshold is now <= 1
# ---------------------------------------------------------------------------

def _stochastic_plan() -> owl.Plan:
    """Minimal single-person plan suitable for stochastic spending."""
    age = 65
    yobs = THISYEAR - age
    p = owl.Plan(["Lee"], [f"{yobs}-06-15"], [85], "stochastic-edge", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[200], taxDeferred=[400], taxFree=[100], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setSocialSecurity([0], [70])
    p.setReproducible(True, seed=42)
    p.setRates("gaussian", values=[6, 3, 2, 2], stdev=[10, 4, 3, 1],
               corr=[0.46, 0.06, -0.12, 0.68, -0.27, -0.21])
    return p


class TestStochasticShortHorizonThreshold:
    def test_horizon_1_treated_as_gs0(self, monkeypatch):
        """A drawn lifespan giving a 1-year horizon must be pre-assigned g_s = 0.

        When all scenarios have horizon = 1 (all skipped), the frontier LP has
        no solved scenarios and raises RuntimeError rather than returning an
        empty result.  That is the expected, correct behavior.
        """
        def _die_immediately(_sex, ca, n, rng=None, table="SSA2025"):
            # Return age-at-death equal to current age → remaining horizon = 1
            return np.array([ca], dtype=int)

        monkeypatch.setattr(stresstests, "sample_lifespans", _die_immediately)
        p = _stochastic_plan()
        with pytest.raises(RuntimeError, match="Fewer than 2 scenarios"):
            p.runStochasticSpending({}, "mc", N=4, with_longevity=True,
                                    sexes=["M"], seed=1)

    def test_horizon_2_now_runs_lp(self, monkeypatch):
        """A drawn lifespan giving a 2-year horizon must now run the LP (not g_s=0)."""
        def _two_year_life(_sex, ca, n, rng=None, table="SSA2025"):
            # Return age-at-death = current_age + 1 → horizon = 2
            return np.array([ca + 1], dtype=int)

        monkeypatch.setattr(stresstests, "sample_lifespans", _two_year_life)
        p = _stochastic_plan()
        out = p.runStochasticSpending({}, "mc", N=4, with_longevity=True,
                                      sexes=["M"], seed=1)
        # Horizon = 2 is now a real scenario; bases must be positive
        assert all(b > 0 for b in out["bases"]), f"Expected positive bases, got {out['bases']}"
        assert out["n_infeasible"] == 0

    def test_horizon_3_runs_lp(self, monkeypatch):
        """A 3-year horizon must run the LP (regression guard for prior behaviour)."""
        def _three_year_life(_sex, ca, n, rng=None, table="SSA2025"):
            return np.array([ca + 2], dtype=int)

        monkeypatch.setattr(stresstests, "sample_lifespans", _three_year_life)
        p = _stochastic_plan()
        out = p.runStochasticSpending({}, "mc", N=4, with_longevity=True,
                                      sexes=["M"], seed=1)
        assert all(b > 0 for b in out["bases"])
