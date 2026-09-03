"""
Tests for the two units the spending pages report.

The optimizer maximizes a spending *basis*: the profile-neutral level that a smile or
flat profile then shapes year by year. What a household commits to, and what the
maxBequest objective's netSpending option pins, is the *first year's* spending. The two
differ by xi_n[0] and coincide only on a flat profile, so reporting one under the other's
name makes two pages of the same case look like they disagree.

What has to hold: the stochastic frontier says the same thing in either unit (the LP is
positively homogeneous, so the success rates and the RES cannot move), and under longevity
sampling -- where every scenario is cloned with a drawn horizon and so carries a profile of
its own -- the first-year figures come from each scenario's own g_n[0] rather than from one
shared factor.

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
import pytest

import owlplanner as owl
from owlplanner import compute_cvar, compute_res, g_for_success_rate
from owlplanner.stresstests import _compute_efficient_frontier

# A spread of scenario outcomes with a clear floor and a long right tail, which is what
# gives the frontier something to trade off.
BASES = np.array([61_000.0, 74_500.0, 80_000.0, 92_300.0, 97_000.0, 110_000.0, 141_000.0])
XI_0 = 1.0907  # a smile profile's first-year factor, as on the reported case


class TestFrontierIsUnitAgnostic:
    """
    Rescaling every scenario rescales the answer and nothing else.

    This is what lets the page quote first-year dollars while the paper quotes the basis:
    the two are the same curve, so no success rate, floor-relative risk measure or optimal
    confidence depends on which one is on the axis.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def swept():
        return _compute_efficient_frontier(BASES, n_points=20)

    @staticmethod
    @pytest.fixture(scope="class")
    def swept_year1():
        return _compute_efficient_frontier(BASES * XI_0, n_points=20)

    def test_spending_scales_and_probability_does_not(self, swept, swept_year1):
        lam, g, prob, short = swept
        lam1, g1, prob1, short1 = swept_year1
        np.testing.assert_allclose(lam1, lam, rtol=1e-12)
        np.testing.assert_allclose(g1, g * XI_0, rtol=1e-9)
        np.testing.assert_allclose(short1, short * XI_0, rtol=1e-9, atol=1e-9)
        # The probabilities are counts of scenarios that fall short, and scaling every
        # scenario by the same factor cannot move which ones do.
        np.testing.assert_array_equal(prob1, prob)

    @pytest.mark.parametrize("rate", [50.0, 75.0, 90.0])
    def test_the_commitment_at_a_success_rate_scales(self, swept, swept_year1, rate):
        lam, g, prob, _ = swept
        _, g1, prob1, _ = swept_year1
        g_basis, _ = g_for_success_rate(rate, lam, g, prob)
        g_year1, _ = g_for_success_rate(rate, lam, g1, prob1)
        assert g_year1 == pytest.approx(g_basis * XI_0, rel=1e-9)

    def test_res_and_rho_star_are_invariant(self, swept, swept_year1):
        """
        RES is (g - floor) / CVaR. Both halves scale together, so the score itself does
        not move -- and neither does the confidence that maximizes it.
        """
        _, g, prob, _ = swept
        _, g1, prob1, _ = swept_year1
        floor, floor1 = float(BASES.min()), float(BASES.min() * XI_0)

        cvar = compute_cvar(BASES, g, prob, floor)
        cvar1 = compute_cvar(BASES * XI_0, g1, prob1, floor1)
        np.testing.assert_allclose(cvar1, cvar * XI_0, rtol=1e-9, atol=1e-9)

        res = compute_res(g, prob, cvar, floor, 85.0)
        res1 = compute_res(g1, prob1, cvar1, floor1, 85.0)
        assert res is not None and res1 is not None
        assert res1["rho_star_pct"] == pytest.approx(res["rho_star_pct"])
        assert res1["res_star"] == pytest.approx(res["res_star"], rel=1e-9)
        assert res1["cvar_star"] == pytest.approx(res["cvar_star"] * XI_0, rel=1e-9)


def _smile_plan():
    """A single retiree on a smile profile, so xi_n[0] is well away from 1."""
    thisyear = date.today().year
    p = owl.Plan(["Pat"], [f"{thisyear - 68}-01-15"], [90], "spending-units")
    p.setSpendingProfile("smile")
    p.setAccountBalances(taxable=[80], taxDeferred=[400], taxFree=[60], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setPension([0], [65])
    p.setSocialSecurity([30], [70])
    p.setReproducible(True, seed=12345)
    p.setRates("gaussian", values=[6, 3, 2, 2], stdev=[10, 4, 3, 1])
    return p


OPTIONS = {"maxRothConversion": 100, "bequest": 0, "withSSTaxability": 0.85, "solver": "HiGHS"}


def test_a_fixed_horizon_puts_year1_at_exactly_xi_0_times_the_basis():
    p = _smile_plan()
    out = p.runStochasticSpending(OPTIONS, "mc", N=6, seed=2026)
    xi_0 = out["xi_0"]
    assert xi_0 == pytest.approx(float(p.xi_n[0]))
    assert xi_0 > 1.0, "a smile profile must separate the two, or the test proves nothing"
    # Every scenario shares the plan's horizon here, so one factor converts the ensemble.
    np.testing.assert_allclose(out["bases_year1"], np.asarray(out["bases"]) * xi_0, rtol=1e-9)
    np.testing.assert_allclose(out["frontier_g_year1"], out["frontier_g"] * xi_0, rtol=1e-6)
    np.testing.assert_array_equal(out["frontier_prob_year1"], out["frontier_prob"])


def test_year1_comes_from_each_scenarios_own_first_year():
    """
    The provenance that matters under longevity sampling.

    bases_year1 is read from the scenario's g_n[0], which is also what year1_decisions
    records, so the two must agree scenario by scenario. Scaling the basis by the parent
    plan's xi_n[0] would instead impose one profile on horizons that do not share it.
    """
    p = _smile_plan()
    out = p.runStochasticSpending(OPTIONS, "mc", N=6, seed=2026)
    for basis, y1, decisions in zip(out["bases"], out["bases_year1"], out["year1_decisions"], strict=True):
        if decisions is None:
            # An infeasible or short-horizon scenario is a full shortfall in either unit.
            assert basis == 0.0 and y1 == 0.0
        else:
            assert y1 == pytest.approx(decisions["g0"])


def test_longevity_scenarios_do_not_share_one_profile():
    """
    Drawn horizons give each scenario its own xi_n[0], so bases_year1 is not the parent's
    factor times the basis. If this ever collapses to a single ratio the exactness of
    reading g_n[0] has been lost, and a rescale would have been good enough.
    """
    p = _smile_plan()
    out = p.runStochasticSpending(
        OPTIONS, "mc", N=12, with_longevity=True, sexes=["M"], seed=2026
    )
    bases = np.asarray(out["bases"], float)
    year1 = np.asarray(out["bases_year1"], float)
    solved = bases > 0
    assert solved.sum() >= 2, "need at least two solved scenarios to compare ratios"
    ratios = year1[solved] / bases[solved]
    # Each ratio is that scenario's own xi_n[0]: near the parent's, but not equal to it.
    assert ratios.min() > 1.0
    assert ratios.std() > 0.0, "every scenario drew the same horizon; the draw is not varying"
