"""
Tests for the shared compute budget.

Every page that solves more than once is governed by one model rather than by per-page
opinion. Before it, the cheapest multi-solve page was blocked on the Community Cloud while
Spending vs Bequest - which can be asked for 20,000 optimizations - was not.

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

import ui.owlbridge as owb


@pytest.fixture
def cloud(monkeypatch):
    """A Community Cloud session whose case has never been solved (no time estimate)."""
    monkeypatch.delenv("OWL_UNCAPPED", raising=False)
    monkeypatch.setattr(owb.referrer, "onCommunityCloud", lambda: True)
    monkeypatch.setattr(owb.kz, "getCaseKey", lambda key: None)


def _keys(mapping):
    return lambda key: mapping.get(key)


class TestCostFormulas:
    """Each page's cost must reflect what the backend actually solves."""

    def test_monte_carlo_is_one_solve_per_trial(self, monkeypatch):
        monkeypatch.setattr(owb.kz, "getCaseKey", _keys({"MC_cases": 2500}))
        solves, width, _ = owb.monteCarloCost()
        assert solves == 2500 and width == 2500

    def test_historical_range_is_one_solve_per_year(self, monkeypatch):
        monkeypatch.setattr(owb.kz, "getCaseKey", _keys({"hyfrm": 1928, "hyto": 1999}))
        solves, _, _ = owb.histRangeCost()
        assert solves == 72

    def test_augmented_sampling_multiplies_by_the_variant_count(self, monkeypatch):
        class P:
            N_n = 30

        monkeypatch.setattr(owb.kz, "getCaseKey",
                            _keys({"hyfrm": 1928, "hyto": 1999, "augmented_sampling": True, "plan": P()}))
        solves, _, _ = owb.histRangeCost()
        assert solves == 72 * 2 * 30      # every (reverse, roll) pair

    def test_frontier_multiplies_levels_by_scenarios(self, monkeypatch):
        """
        The hole this closes: each bequest level re-solves the whole scenario set, and
        nothing capped the level count.
        """
        monkeypatch.setattr(owb.kz, "getCaseKey", _keys({
            "frontier_bequest_grid": "0, 500, 1_000, 1_500, 2_000",
            "frontier_scenario_method": "mc",
            "frontier_N_mc": 2000,
        }))
        solves, width, _ = owb.frontierCost()
        assert solves == 5 * 2000 and width == 2000

    def test_frontier_deterministic_is_one_solve_per_level(self, monkeypatch):
        monkeypatch.setattr(owb.kz, "getCaseKey", _keys({
            "frontier_bequest_grid": "0, 500, 1_000",
            "frontier_scenario_method": "deterministic",
        }))
        assert owb.frontierCost()[0] == 3

    def test_a_malformed_level_list_does_not_explode(self, monkeypatch):
        """The grid is free text; a typo must not crash the cost estimate."""
        monkeypatch.setattr(owb.kz, "getCaseKey", _keys({
            "frontier_bequest_grid": "0, abc, 500",
            "frontier_scenario_method": "deterministic",
        }))
        assert owb.frontierCost()[0] >= 1


class TestBudgetIsCoherentAcrossPages:
    def test_the_worst_frontier_run_is_refused(self, cloud, monkeypatch):
        """10 levels x 2,000 scenarios = 20,000 solves used to be allowed with no warning."""
        allowed, caption = owb.costOfRun(10 * 2000, 2000)
        assert allowed is False and "Community Cloud" in caption

    def test_the_max_monte_carlo_is_refused(self, cloud):
        assert owb.costOfRun(10_000, 10_000)[0] is False

    def test_a_full_historical_range_is_allowed(self, cloud):
        """72 solves is the kind of run the cloud should keep serving."""
        assert owb.costOfRun(72, 72)[0] is True

    def test_augmented_sampling_is_refused(self, cloud):
        """Previously carried a prose warning only."""
        assert owb.costOfRun(72 * 2 * 30, 72)[0] is False

    def test_everything_is_allowed_when_self_hosted(self, monkeypatch):
        monkeypatch.delenv("OWL_UNCAPPED", raising=False)
        monkeypatch.setattr(owb.referrer, "onCommunityCloud", lambda: False)
        monkeypatch.setattr(owb.kz, "getCaseKey", lambda key: None)
        for n in (72, 10_000, 20_000):
            assert owb.costOfRun(n, 72)[0] is True
