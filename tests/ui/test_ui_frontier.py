"""
Tests for the spending/bequest frontier helpers in the UI bridge.

The Streamlit page itself is not testable without a browser, but the two pieces
that can silently go wrong are pure functions: parsing the bequest levels a user
types, and turning a frontier result into the table shown under the plot.

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

import ui.owlbridge as owb


class TestParseBequestGrid:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("0, 500, 1000", [0.0, 500.0, 1000.0]),
            ("0;500;1000", [0.0, 500.0, 1000.0]),
            (" 0 , 500 ,, ", [0.0, 500.0]),
            ("1000", [1000.0]),
            ("", []),
            (None, []),
        ],
    )
    def test_accepts_what_a_user_would_type(self, raw, expected):
        assert owb._parse_bequest_grid(raw) == expected

    def test_rejects_a_non_numeric_entry(self):
        """Better to refuse than to silently drop a level the user meant to trace."""
        with pytest.raises(ValueError):
            owb._parse_bequest_grid("0, abc, 500")


def _fake_result(scenario_method="deterministic"):
    """A minimal frontier result, shaped like run_spending_bequest_frontier's."""
    stochastic = scenario_method != "deterministic"
    return {
        "bequest_grid": np.array([0.0, 1000.0, 2000.0]),
        "bequest_dollars": np.array([0.0, 1_000_000.0, 2_000_000.0]),
        "base_basis": np.array([100_000.0, 94_000.0, 88_000.0]),
        "bases": np.zeros((3, 1)),
        "g_at_success": (
            np.array([[105_000.0, 100_000.0, 95_000.0], [99_000.0, 94_000.0, 89_000.0], [93_000.0, 88_000.0, 83_000.0]])
            if stochastic
            else np.full((3, 3), np.nan)
        ),
        "lam_at_success": np.full((3, 3), np.nan),
        "frontier_g": np.zeros((3, 5)) if stochastic else None,
        "frontier_prob": np.zeros((3, 5)) if stochastic else None,
        "frontier_shortfall": np.zeros((3, 5)) if stochastic else None,
        "n_infeasible": np.zeros(3, dtype=int),
        "level_failed": np.zeros(3, dtype=bool),
        "bequest_shadow_price": np.array([0.0, 0.18, 0.18]),
        "max_gap": np.full(3, -1.0),
        "xi_sum": 30.0,
        "success_rates": (50.0, 75.0, 90.0),
        "scenario_method": scenario_method,
        "n_scenarios": 11 if stochastic else 1,
        "start_years": np.arange(1970, 1981) if stochastic else None,
        "year_n": np.arange(2026, 2059),
        "n_d": 32,
    }


class TestRenderFrontier:
    """_render_frontier writes into session state, so the stores are captured."""

    @staticmethod
    def _capture(monkeypatch):
        stored = {}
        monkeypatch.setattr(owb.kz, "storeCaseKey", lambda k, v: stored.__setitem__(k, v))
        return stored

    def test_deterministic_table_and_plot(self, monkeypatch):
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        owb._render_frontier(_fake_result("deterministic"), MatplotlibBackend())

        assert stored["frontierPlot"] is not None
        text = stored["frontierSummary"]
        assert "Net spending" in text
        assert "100,000" in text and "88,000" in text
        assert "the most this plan can leave" in text

    def test_stochastic_table_has_one_column_per_success_rate(self, monkeypatch):
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        owb._render_frontier(_fake_result("historical"), MatplotlibBackend())

        text = stored["frontierSummary"]
        for rate in ("50% success", "75% success", "90% success"):
            assert rate in text
        # The 90%-confidence column, which is what a cautious planner reads.
        assert "95,000" in text and "83,000" in text

    def test_stochastic_scalars_are_reported_for_every_curve(self, monkeypatch):
        """
        No hidden selection: the exchange rate is read off one curve, so it is shown
        for every curve rather than one being chosen for the reader.
        """
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        owb._render_frontier(_fake_result("historical"), MatplotlibBackend())

        text = stored["frontierSummary"]
        assert "$/yr per $" in text
        # One rate row per curve, on top of the header row naming the same curves.
        for rate in ("50% success", "75% success", "90% success"):
            assert text.count(rate) == 2

    def test_unreachable_level_is_labelled(self, monkeypatch):
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        result = _fake_result("deterministic")
        result["level_failed"] = np.array([False, False, True])
        result["base_basis"] = np.array([100_000.0, 94_000.0, np.nan])
        owb._render_frontier(result, MatplotlibBackend())

        assert "unreachable" in stored["frontierSummary"]


class TestOverallExchangeRate:
    def test_slope_across_the_traced_range(self):
        b = np.array([0.0, 1_000_000.0, 2_000_000.0])
        g = np.array([100_000.0, 94_000.0, 88_000.0])
        assert owb._overall_exchange_rate(b, g) == pytest.approx(-0.006)

    def test_ignores_unreachable_levels(self):
        b = np.array([0.0, 1_000_000.0, 2_000_000.0])
        g = np.array([100_000.0, 94_000.0, np.nan])
        assert owb._overall_exchange_rate(b, g) == pytest.approx(-0.006)

    def test_returns_none_when_there_is_no_range(self):
        assert owb._overall_exchange_rate(np.array([0.0]), np.array([100_000.0])) is None
        assert owb._overall_exchange_rate(np.array([0.0, 1.0]), np.array([np.nan, np.nan])) is None
