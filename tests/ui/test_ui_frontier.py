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
            # Underscores group digits without colliding with the comma that separates
            # levels, so they are the safe way to write a large figure legibly.
            ("0, 500, 1_000, 2_000", [0.0, 500.0, 1000.0, 2000.0]),
            ("1_000_000", [1_000_000.0]),
            ("0;1_500;10_000", [0.0, 1500.0, 10000.0]),
            ("", []),
            (None, []),
        ],
    )
    def test_accepts_what_a_user_would_type(self, raw, expected):
        assert owb._parse_bequest_grid(raw) == expected

    @pytest.mark.parametrize("raw", ["_1000", "1000_"])
    def test_rejects_a_misplaced_underscore(self, raw):
        """Grouping underscores must sit between digits, as in a Python literal."""
        with pytest.raises(ValueError):
            owb._parse_bequest_grid(raw)

    def test_rejects_a_non_numeric_entry(self):
        """Better to refuse than to silently drop a level the user meant to trace."""
        with pytest.raises(ValueError):
            owb._parse_bequest_grid("0, abc, 500")


def _prose(text):
    """
    Collapse the summary to one line for prose assertions.

    The notes under the table are wrapped to its width so the page never scrolls
    sideways, which means a sentence can break anywhere. Layout is asserted on the raw
    text (see the column-alignment tests); wording is asserted on this.
    """
    return " ".join(text.split())


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
        "fixed_assets_today_dollars": 0.0,
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


@pytest.fixture(autouse=True)
def _close_figures():
    """
    Discard figures these tests build.

    _render_frontier returns a live matplotlib figure; left open they accumulate
    until matplotlib warns, and under a GUI backend each one is a window.
    """
    yield
    import matplotlib.pyplot as plt

    plt.close("all")


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
        assert "the most this plan can leave" in _prose(text)

    def test_stochastic_table_has_one_column_per_success_rate(self, monkeypatch):
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        owb._render_frontier(_fake_result("historical"), MatplotlibBackend())

        text = stored["frontierSummary"]
        for rate in ("50% success", "75% success", "90% success"):
            assert rate in text
        # The 90%-confidence column, which is what a cautious planner reads.
        assert "95,000" in text and "83,000" in text

    def test_fixed_assets_are_shown_beside_the_savings(self, monkeypatch):
        """
        The bequest axis is savings only, so a plan with a house understates the estate.

        Fixed assets do not vary with the floor, so they are shown as their own column
        and added into a total rather than folded silently into the swept figure.
        """
        from owlplanner import summarize_spending_bequest_frontier
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        result = _fake_result("historical")
        result["fixed_assets_today_dollars"] = 1_067_389.0
        owb._render_frontier(result, MatplotlibBackend())

        text = stored["frontierSummary"]
        assert "Fixed assets" in text and "Total estate" in text
        assert "1,067,389" in text
        # Savings 1,000,000 + fixed 1,067,389.
        assert "2,067,389" in text
        assert "add $1,067,389 to every level" in text

        s = summarize_spending_bequest_frontier(result, target_success_rate_pct=90.0)
        assert s["fixed_assets_today_dollars"] == 1_067_389.0
        assert s["frontier"][1]["total_estate_today_dollars"] == 2_067_389.0

    def test_no_fixed_assets_means_no_extra_columns(self, monkeypatch):
        """A plan with nothing outside its accounts should not carry empty columns."""
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        result = _fake_result("historical")
        result["fixed_assets_today_dollars"] = 0.0
        owb._render_frontier(result, MatplotlibBackend())

        text = stored["frontierSummary"]
        assert "Fixed assets" not in text and "Total estate" not in text

    def test_unreachable_level_is_labelled(self, monkeypatch):
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        result = _fake_result("deterministic")
        result["level_failed"] = np.array([False, False, True])
        result["base_basis"] = np.array([100_000.0, 94_000.0, np.nan])
        owb._render_frontier(result, MatplotlibBackend())

        assert "unreachable" in stored["frontierSummary"]

    def test_mid_grid_hole_renders(self, monkeypatch):
        """
        A level failing in the middle of the grid used to abort the whole render.

        exchange_rate was compacted, so indexing it by grid position raised
        IndexError and the UI reported "trade-off failed", discarding the sweep.
        """
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        result = _fake_result("deterministic")
        result["level_failed"] = np.array([False, True, False])
        result["base_basis"] = np.array([100_000.0, np.nan, 88_000.0])
        owb._render_frontier(result, MatplotlibBackend())

        text = stored["frontierSummary"]
        assert "unreachable" in text
        assert "100,000" in text and "88,000" in text, "the solved levels must still print"
        # A failure below the best success is not "every level is reachable".
        assert "Every level traced is reachable" not in text
        assert "1 lower level(s) did not solve" in _prose(text)

    def test_unreachable_marker_sits_under_spending(self, monkeypatch):
        """
        The missing value is the spending, not the estate.

        Fixed assets are known whether or not the level is reachable, so the marker
        has to clear those columns; printed too early it lands under Fixed assets and
        reads as the assets being unreachable.
        """
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = self._capture(monkeypatch)
        result = _fake_result("deterministic")
        result["fixed_assets_today_dollars"] = 1_067_389.0
        result["level_failed"] = np.array([False, False, True])
        result["base_basis"] = np.array([100_000.0, 94_000.0, np.nan])
        owb._render_frontier(result, MatplotlibBackend())

        header, *rows = stored["frontierSummary"].splitlines()
        bad = [r for r in rows if "unreachable" in r][0]
        assert header.index("Net spending") + len("Net spending") == bad.index("unreachable") + len(
            "unreachable"
        ), "the marker must be right-aligned in the Net spending column"
        # The estate columns are still filled on that row.
        assert "1,067,389" in bad and "3,067,389" in bad


class TestSpendingColumns:
    """
    The table reports the first year's spending, and says so when a profile makes that
    differ from the basis.

    A curve labelled with basis dollars is what made this page look like it contradicted
    a maxBequest run of the same case: the goal there is the first year's amount, so the
    two were being read off different scales.
    """

    @staticmethod
    def _capture(monkeypatch):
        stored = {}
        monkeypatch.setattr(owb.kz, "storeCaseKey", lambda k, v: stored.__setitem__(k, v))
        return stored

    @staticmethod
    def _render(monkeypatch, result):
        from owlplanner.plotting.matplotlib_backend import MatplotlibBackend

        stored = TestSpendingColumns._capture(monkeypatch)
        owb._render_frontier(result, MatplotlibBackend())
        return stored

    def test_a_smile_profile_shows_both_columns(self, monkeypatch):
        result = _fake_result("deterministic")
        result["xi_0"] = 1.0907
        stored = self._render(monkeypatch, result)

        header, *rows = stored["frontierSummary"].splitlines()
        assert "Net spending" in header and "Spending basis" in header
        # Year 1 leads, the basis follows: 100,000 of basis is 109,070 in the first year.
        assert "109,070" in rows[0] and "100,000" in rows[0]
        assert header.index("Net spending") < header.index("Spending basis")
        assert "1.09 times the spending basis" in _prose(stored["frontierSummary"])

    def test_a_flat_profile_shows_only_one(self, monkeypatch):
        """Nothing to disambiguate when the two coincide, so the column is not spent."""
        result = _fake_result("deterministic")
        result["xi_0"] = 1.0
        stored = self._render(monkeypatch, result)

        text = stored["frontierSummary"]
        assert "Net spending" in text
        assert "Spending basis" not in text
        assert "100,000" in text and "88,000" in text

    def test_the_stochastic_table_converts_without_widening(self, monkeypatch):
        """
        One column per success rate either way: doubling them would not fit, so the
        conversion is carried by the note instead.
        """
        result = _fake_result("historical")
        result["xi_0"] = 1.0907
        stored = self._render(monkeypatch, result)

        header, *rows = stored["frontierSummary"].splitlines()
        assert header.count("% success") == 3
        assert "Spending basis" not in header
        # 105,000 of basis at the 50% rate is 114,524 in the first year.
        assert "114,524" in rows[0]
        assert "1.09 times the spending basis" in _prose(stored["frontierSummary"])

    def test_the_exchange_rate_is_in_the_same_dollars_as_the_column(self, monkeypatch):
        """
        A $/yr figure quoted against a year-1 column has to be a year-1 difference, or the
        reader cannot check the arithmetic against two neighbouring rows.
        """
        result = _fake_result("deterministic")
        result["xi_0"] = 1.0907
        stored = self._render(monkeypatch, result)

        rows = stored["frontierSummary"].splitlines()[1:4]
        spend = [float(r.split()[1].replace(",", "")) for r in rows]
        rate = float(rows[1].split()[-1])
        # Column falls by (109,070 - 102,516) over $1M of estate, reported per $1,000.
        # Printed to one decimal, so the check is only good to half of that.
        assert rate == pytest.approx((spend[1] - spend[0]) / 1_000_000.0 * 1000.0, abs=0.05)

    def test_a_result_without_xi_0_still_renders(self, monkeypatch):
        """A run cached before the column existed must not break the page."""
        result = _fake_result("deterministic")
        result.pop("xi_0", None)
        stored = self._render(monkeypatch, result)

        text = stored["frontierSummary"]
        assert "Spending basis" not in text
        assert "100,000" in text
