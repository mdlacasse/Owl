"""
Tests for the spending/bequest efficient frontier.

The frontier sweeps the bequest floor under maxSpending. Each point is an ordinary
solve, so what needs testing is not the optimization but the sweep: that the curve
has the shape a Pareto frontier must have, that the stochastic modes really are the
existing scenario machinery applied at each level, and that the awkward cases --
a floor beyond reach, a Monte Carlo ensemble that must not be redrawn between
levels -- behave as documented.

The frontier replaces the withdrawn fixedSpending option (issue #140). The property
that matters is in test_spending_is_monotone_in_the_floor: raising the floor must
never buy more spending. That is what makes each point an optimum rather than an
arbitrary vertex, and it is exactly what pinning the spending level destroyed.

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

import owlplanner as owl
from owlplanner import run_spending_bequest_frontier, summarize_spending_bequest_frontier
from owlplanner.config import readConfig
from owlplanner.stresstests import run_stochastic_spending

CASE = "examples/Case_jack+jill.toml"
# Kept short: these tests check sweep mechanics, not scenario coverage.
HIST_YSTART, HIST_YEND = 1970, 1980
NOISE = 1.0  # $/yr tolerance on monotonicity


@pytest.fixture(scope="module")
def case():
    p = readConfig(CASE, verbose=False)
    return p


@pytest.fixture(scope="module")
def opts(case):
    o = dict(case.solverOptions)
    o["solver"] = "HiGHS"
    return o


@pytest.mark.toml
class TestDeterministic:
    """One scenario per level: the interactive path, and the fixedSpending replacement."""

    @staticmethod
    @pytest.fixture(scope="class")
    def result(case, opts):
        return run_spending_bequest_frontier(
            case, opts, [0, 500, 1000, 2000], scenario_method="deterministic", with_duals=True
        )

    def test_zero_floor_reproduces_the_plain_solve(self, case, opts, result):
        """The B=0 point must be the unconstrained maxSpending answer, not a nearby one."""
        p = owl.clone(case, verbose=False)
        o = dict(opts)
        o["bequest"] = 0
        p.solve("maxSpending", o)
        assert result["base_basis"][0] == pytest.approx(p.basis, abs=NOISE)

    def test_spending_is_monotone_in_the_floor(self, result):
        """A Pareto frontier: reserving more for the estate can never buy more spending."""
        b = result["base_basis"]
        assert not np.isnan(b).any(), "every level in this grid should be reachable"
        for lo, hi in zip(b, b[1:]):
            assert hi <= lo + NOISE, f"spending rose from {lo:.2f} to {hi:.2f} as the floor increased"

    def test_shadow_price_is_slack_at_zero_and_binding_above(self, result):
        """At B=0 the floor costs nothing; once it binds it has a positive price."""
        shadow = result["bequest_shadow_price"]
        assert shadow[0] == pytest.approx(0.0, abs=1e-6)
        assert (shadow[1:] > 0).all(), "a binding bequest floor must cost lifetime spending"

    def test_shape_and_provenance(self, result):
        assert result["scenario_method"] == "deterministic"
        assert result["n_scenarios"] == 1
        assert result["bases"].shape == (4, 1)
        # A single scenario has no shortfall distribution to sweep.
        assert result["frontier_g"] is None
        assert result["bequest_dollars"] == pytest.approx(result["bequest_grid"] * 1000)

    def test_summary_is_json_ready(self, result):
        s = summarize_spending_bequest_frontier(result)
        assert s["scenario_method"] == "deterministic"
        assert len(s["frontier"]) == 4
        assert s["n_levels_failed"] == 0
        # Every measured segment must slope down.
        assert all(e["spending_per_dollar_of_bequest"] < 0 for e in s["exchange_rate"])


@pytest.mark.toml
class TestHistorical:
    """Each level solved across the ensemble: the S(B, p) surface."""

    @staticmethod
    @pytest.fixture(scope="class")
    def result(case, opts):
        return run_spending_bequest_frontier(
            case,
            opts,
            [0, 1000, 3000],
            scenario_method="historical",
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            success_rates=(50.0, 75.0, 90.0),
            with_duals=False,
        )

    def test_row_matches_a_direct_scenario_run(self, case, opts, result):
        """
        The surface must be the existing machinery, not a reimplementation of it.

        Fixing B and reading across must reproduce run_stochastic_spending exactly.
        """
        o = dict(opts)
        o["bequest"] = 1000
        direct = run_stochastic_spending(case, o, "historical", ystart=HIST_YSTART, yend=HIST_YEND)
        assert np.allclose(direct["bases"], result["bases"][1, :])
        assert np.allclose(direct["frontier_g"], result["frontier_g"][1, :])

    def test_spending_is_monotone_in_the_floor_at_every_confidence(self, result):
        G = result["g_at_success"]
        for j in range(G.shape[1]):
            col = G[:, j]
            for lo, hi in zip(col, col[1:]):
                assert hi <= lo + NOISE, f"spending rose from {lo:.2f} to {hi:.2f} at column {j}"

    def test_confidence_fan_is_ordered(self, result):
        """Demanding a higher success rate cannot allow more spending."""
        G = result["g_at_success"]
        assert (G[:, 0] >= G[:, 1] - NOISE).all(), "50% must permit at least as much as 75%"
        assert (G[:, 1] >= G[:, 2] - NOISE).all(), "75% must permit at least as much as 90%"

    def test_shape_and_provenance(self, result):
        S = HIST_YEND - HIST_YSTART + 1
        assert result["n_scenarios"] == S
        assert result["bases"].shape == (3, S)
        assert result["g_at_success"].shape == (3, 3)
        assert result["frontier_g"].shape[0] == 3
        assert list(result["start_years"]) == list(range(HIST_YSTART, HIST_YEND + 1))

    def test_summary_requires_a_traced_rate(self, result):
        """Asking for a confidence the sweep never traced is an error, not an interpolation."""
        with pytest.raises(ValueError, match="not among the rates traced"):
            summarize_spending_bequest_frontier(result, target_success_rate_pct=99.0)

    def test_summary_reports_the_requested_rate(self, result):
        s = summarize_spending_bequest_frontier(result, target_success_rate_pct=90.0)
        assert s["target_success_rate_pct"] == 90.0
        assert s["n_scenarios"] == HIST_YEND - HIST_YSTART + 1
        for row in s["frontier"]:
            assert "spending_at_90pct" in row


@pytest.mark.toml
class TestAwkwardCases:
    def test_unreachable_level_is_recorded_not_raised(self, case, opts):
        """
        A floor beyond reach must not abort the sweep.

        run_stochastic_spending raises once fewer than two scenarios solve; the sweep
        has to absorb that so the reachable part of the curve still comes back.
        """
        res = run_spending_bequest_frontier(
            case,
            opts,
            [0, 100_000],
            scenario_method="historical",
            ystart=HIST_YSTART,
            yend=1975,
            with_duals=False,
        )
        assert not res["level_failed"][0]
        assert res["level_failed"][1]
        assert np.isnan(res["g_at_success"][1]).all()

        s = summarize_spending_bequest_frontier(res, target_success_rate_pct=90.0)
        assert s["n_levels_failed"] == 1

    def test_mc_uses_common_random_numbers(self, case):
        """
        Every level must meet the same ensemble.

        Monte Carlo draws a fresh ensemble per call unless the rate RNG is pinned, which
        would make the surface wander non-monotonically on sampling noise alone.
        """
        p = readConfig(CASE, verbose=False)
        p.setRates("historical_bootstrap", 1928, 2025)
        o = dict(p.solverOptions)
        o["solver"] = "HiGHS"

        kw = dict(scenario_method="mc", N=10, seed=7, with_duals=False)
        a = run_spending_bequest_frontier(p, o, [0, 1000], **kw)
        b = run_spending_bequest_frontier(p, o, [0, 1000], **kw)
        assert np.allclose(a["bases"], b["bases"]), "same seed must reproduce the same ensemble"

        G = a["g_at_success"]
        for j in range(G.shape[1]):
            assert G[1, j] <= G[0, j] + NOISE, "common random numbers should keep the surface monotone"

    def test_grid_is_sorted_and_deduplicated(self, case, opts):
        res = run_spending_bequest_frontier(
            case, opts, [1000, 0, 1000], scenario_method="deterministic", with_duals=False
        )
        assert list(res["bequest_grid"]) == [0.0, 1000.0]


class TestValidation:
    """Guards, checked without solving anything."""

    @pytest.mark.toml
    @pytest.mark.parametrize(
        "kwargs, grid, match",
        [
            ({"scenario_method": "nope"}, [0], "scenario_method"),
            ({"scenario_method": "deterministic"}, [], "non-empty"),
            ({"scenario_method": "deterministic"}, [-5], "non-negative"),
            ({"scenario_method": "deterministic", "success_rates": (0.9,)}, [0], "percentage"),
        ],
    )
    def test_bad_arguments_are_rejected(self, case, opts, kwargs, grid, match):
        with pytest.raises(ValueError, match=match):
            run_spending_bequest_frontier(case, opts, grid, **kwargs)


def test_summarize_is_pure():
    """The summarizer takes a result dict and no Plan, so it can run on stored output."""
    result = {
        "bequest_grid": np.array([0.0, 1000.0, 2000.0]),
        "bequest_dollars": np.array([0.0, 1_000_000.0, 2_000_000.0]),
        "base_basis": np.array([100_000.0, 94_000.0, 88_000.0]),
        "bases": np.zeros((3, 1)),
        "g_at_success": np.full((3, 1), np.nan),
        "lam_at_success": np.full((3, 1), np.nan),
        "frontier_g": None,
        "frontier_prob": None,
        "frontier_shortfall": None,
        "n_infeasible": np.zeros(3, dtype=int),
        "level_failed": np.zeros(3, dtype=bool),
        "bequest_shadow_price": np.array([0.0, 0.18, 0.18]),
        "max_gap": np.array([-1.0, -1.0, -1.0]),
        "xi_sum": 30.0,
        "success_rates": (90.0,),
        "scenario_method": "deterministic",
        "n_scenarios": 1,
        "start_years": None,
        "year_n": np.arange(2026, 2029),
        "n_d": 2,
    }
    s = summarize_spending_bequest_frontier(result)

    assert s["free_bequest_today_dollars"] == 0.0
    assert s["max_feasible_bequest_today_dollars"] == 2_000_000.0
    assert s["n_levels_failed"] == 0
    # -6000 spending per $1M of bequest.
    assert s["exchange_rate"][0]["spending_per_dollar_of_bequest"] == pytest.approx(-0.006)
    # The dual is a lifetime figure; dividing by the profile sum puts it in basis units.
    assert s["exchange_rate"][0]["shadow_price_implied"] == pytest.approx(-0.18 / 30.0)


def test_summarize_reports_free_bequest():
    """The flat left region: estate the plan leaves behind anyway, costing no spending."""
    result = {
        "bequest_grid": np.array([0.0, 100.0, 200.0]),
        "bequest_dollars": np.array([0.0, 100_000.0, 200_000.0]),
        "base_basis": np.array([100_000.0, 100_000.0, 94_000.0]),
        "bases": np.zeros((3, 1)),
        "g_at_success": np.full((3, 1), np.nan),
        "lam_at_success": np.full((3, 1), np.nan),
        "frontier_g": None,
        "frontier_prob": None,
        "frontier_shortfall": None,
        "n_infeasible": np.zeros(3, dtype=int),
        "level_failed": np.zeros(3, dtype=bool),
        "bequest_shadow_price": np.full(3, np.nan),
        "max_gap": np.full(3, -1.0),
        "xi_sum": 30.0,
        "success_rates": (90.0,),
        "scenario_method": "deterministic",
        "n_scenarios": 1,
        "start_years": None,
        "year_n": np.arange(2026, 2029),
        "n_d": 2,
    }
    s = summarize_spending_bequest_frontier(result)
    assert s["free_bequest_today_dollars"] == 100_000.0
