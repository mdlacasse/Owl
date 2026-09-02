"""
Tests for the conversion-regret helpers in the UI bridge.

The Streamlit page itself is not testable without a browser, but the pieces that can
silently go wrong are pure: the run-cost arithmetic shown next to the Run button, the
Community Cloud gate, and the narrative block that reports what the plot deliberately
leaves off.

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


class TestRunCost:
    """The estimate beside the Run button: S x (grid + baseline + never-convert)."""

    def test_solve_count_matches_the_preset(self):
        # Standard sweeps 36 windows on a 9-point grid: 36 x (9 + 2).
        assert owb.estimateRegretSolves("Standard", 1928, 1999) == 36 * 11
        assert owb.estimateRegretSolves("Quick look", 1928, 1999) == 18 * 9

    def test_the_full_preset_uses_every_window_in_range(self):
        """Thorough does not subsample, so the requested range sets the count."""
        assert owb.regretScenarioCount("Thorough", 1928, 1999) == 72
        assert owb.estimateRegretSolves("Thorough", 1928, 1999) == 72 * 13

    def test_a_short_range_caps_a_subsampling_preset(self):
        """Asking for 36 windows out of 10 must sweep 10, not fail or over-count."""
        assert owb.regretScenarioCount("Standard", 1990, 1999) == 10
        assert owb.estimateRegretSolves("Standard", 1990, 1999) == 10 * 11

    def test_eta_is_withheld_until_the_case_has_been_solved(self, monkeypatch):
        """
        Per-solve time varies by more than an order of magnitude between cases, so an
        estimate is only offered once this case has actually been measured.
        """
        monkeypatch.setattr(owb.kz, "getCaseKey", lambda key: None)
        assert owb.estimateRegretSeconds("Standard", 1928, 1999) is None

    def test_eta_scales_with_the_measured_solve_time(self, monkeypatch):
        class FakePlan:
            lastSolveWallTime = 0.5

        monkeypatch.setattr(owb.kz, "getCaseKey", lambda key: FakePlan() if key == "plan" else None)
        quick = owb.estimateRegretSeconds("Quick look", 1928, 1999)
        standard = owb.estimateRegretSeconds("Standard", 1928, 1999)
        assert quick is not None and standard > quick


class TestSharedBudget:
    """
    Every multi-solve page is governed by one budget rather than per-page opinion. The
    regret page used to be blocked outright while pages costing far more were not.
    """

    @staticmethod
    def _cloud(monkeypatch, on):
        monkeypatch.delenv("OWL_UNCAPPED", raising=False)
        monkeypatch.setattr(owb.referrer, "onCommunityCloud", lambda: on)
        monkeypatch.setattr(owb.kz, "getCaseKey", lambda key: None)   # no measured solve time

    def test_self_hosted_is_uncapped(self, monkeypatch):
        self._cloud(monkeypatch, False)
        allowed, _ = owb.costOfRun(100_000, 72)
        assert allowed is True

    def test_cloud_refuses_a_run_over_budget(self, monkeypatch):
        self._cloud(monkeypatch, True)
        allowed, caption = owb.costOfRun(owb.CLOUD_SOLVE_BUDGET + 1, 72)
        assert allowed is False
        assert "Community Cloud" in caption

    def test_cloud_allows_a_run_within_budget(self, monkeypatch):
        self._cloud(monkeypatch, True)
        allowed, _ = owb.costOfRun(owb.CLOUD_SOLVE_BUDGET, 72)
        assert allowed is True

    def test_uncapped_env_lifts_the_cap(self, monkeypatch):
        self._cloud(monkeypatch, True)
        monkeypatch.setenv("OWL_UNCAPPED", "1")
        allowed, _ = owb.costOfRun(100_000, 72)
        assert allowed is True

    def test_the_cheapest_regret_preset_fits_the_cloud_budget(self, monkeypatch):
        """
        Quick look costs 163 solves - less than a mid-size Monte Carlo the cloud already
        permits - so a coherent budget must admit it.
        """
        self._cloud(monkeypatch, True)
        quick = owb.estimateRegretSolves("Quick look", 1928, 1999)
        assert quick <= owb.CLOUD_SOLVE_BUDGET
        assert owb.costOfRun(quick, 18)[0] is True

    def test_the_full_regret_preset_does_not(self, monkeypatch):
        self._cloud(monkeypatch, True)
        thorough = owb.estimateRegretSolves("Thorough", 1928, 1999)
        assert thorough > owb.CLOUD_SOLVE_BUDGET
        assert owb.costOfRun(thorough, 72)[0] is False

    def test_a_slow_case_is_refused_on_time_even_within_the_solve_cap(self, monkeypatch):
        """Per-solve time varies ~30x by case tightness, so the count alone is not enough."""
        monkeypatch.delenv("OWL_UNCAPPED", raising=False)
        monkeypatch.setattr(owb.referrer, "onCommunityCloud", lambda: True)

        class SlowPlan:
            lastSolveWallTime = 5.0

        monkeypatch.setattr(owb.kz, "getCaseKey", lambda key: SlowPlan() if key == "plan" else None)
        allowed, caption = owb.costOfRun(400, 1)      # under the count cap, way over on time
        assert allowed is False
        assert "Community Cloud" in caption


class TestCurves:
    def test_failed_baselines_are_dropped_from_the_curve(self):
        result = {
            "v_star": np.array([100.0, np.nan, 200.0]),
            "v_at": np.array([[90.0, 80.0], [1.0, 2.0], [190.0, 170.0]]),
        }
        mean, lo, hi = owb._regret_curves(result)
        # Regret is [10, 20] and [10, 30]; the failed scenario contributes nothing.
        assert mean == pytest.approx([10.0, 25.0])
        assert lo[0] == pytest.approx(10.0) and hi[1] == pytest.approx(29.0, abs=1.0)

    def test_all_baselines_failed_yields_nothing_to_draw(self):
        result = {"v_star": np.array([np.nan, np.nan]), "v_at": np.full((2, 3), np.nan)}
        assert owb._regret_curves(result) == (None, None, None)


class TestSummaryText:
    @staticmethod
    def _result():
        return {"grid": [0.0, 50_000.0, 100_000.0], "seed": 3, "milp_downgraded": ["withMedicare"]}

    def test_reports_the_band_and_the_value_of_converting(self):
        summary = {
            "n_scenarios": 36,
            "valley_resolvable": True,
            "valley": {"x": 50_000.0, "mean_regret": 900.0},
            "valley_ci": {"p10": 45_000.0, "p90": 60_000.0},
            "commit_band": {"x_lo": 25_000.0, "x_hi": 70_000.0, "band_frac": 0.02},
            "never_convert_regret": {"mean": 253_543.0},
            "resolution_floor": 120.0,
            "x_star": {"median": 50_000.0, "p10": 10_000.0, "p90": 90_000.0, "share_converting": 0.97},
            "asymmetry": [{"delta": 30_000, "mean_regret_over": 9_000.0, "mean_regret_under": 1_500.0}],
            "convergence": {"share_clean": 0.5},
            "n_failed_baselines": 0,
        }
        txt = owb._regret_summary_text(summary, self._result(), "maxBequest", elapsed=75.0)
        assert "Best commitment: $50,000" in txt
        assert "Commit band: $25,000 to $70,000" in txt
        # Every line must fit a normal-width code block without wrapping.
        assert max(len(ln) for ln in txt.splitlines()) <= 72, "summary line too wide"
        assert "Never converting at all costs: $253,543" in txt
        assert "the 100% mark on the right-hand axis" in txt
        # The over/under ratio is not stable enough to print as a number; only its sign is.
        assert "Over-converting is the costlier error" in txt
        assert "ratio of the two is not stable" in txt
        assert "withMedicare" in txt and "seed 3" in txt

    def test_says_so_plainly_when_the_curve_is_flat(self):
        summary = {
            "n_scenarios": 18,
            "valley_resolvable": False,
            "valley": {"x": 0.0, "mean_regret": 3.0},
            "resolution_floor": 9.0,
            "x_star": {"median": 0.0, "p10": 0.0, "p90": 0.0, "share_converting": 0.0},
            "asymmetry": [],
            "never_convert_regret": {"mean": 12.0},
        }
        txt = owb._regret_summary_text(summary, self._result(), "maxSpending")
        assert "No resolvable valley" in txt
        assert "Best commitment" not in txt
        # Spending outcomes are per-year, and the text must say so.
        assert "$12/yr" in txt
        assert max(len(ln) for ln in txt.splitlines()) <= 72


class TestPageRenders:
    """Smoke-test the page through AppTest: it must render, and the gate must bite."""

    @staticmethod
    def _render(monkeypatch, blocked, preset="Standard"):
        from pathlib import Path

        from streamlit.testing.v1 import AppTest

        from owlplanner import readConfig

        ui_dir = Path(__file__).resolve().parents[2] / "ui"
        case_file = Path(__file__).resolve().parents[2] / "examples" / "Case_dana.toml"
        plan = readConfig(str(case_file), verbose=False)
        # Exercise the natural path in both directions rather than the escape hatch.
        monkeypatch.delenv("OWL_UNCAPPED", raising=False)
        monkeypatch.setattr(owb.referrer, "onCommunityCloud", lambda: blocked)

        at = AppTest.from_file(str(ui_dir / "Regret_Curve.py"), default_timeout=120)
        at.session_state["cases"] = {
            "t": {"plan": plan, "name": "t", "id": "t1", "iname0": "Dana",
                  "status": "single", "caseStatus": "modified", "summaryDf": None,
                  "objective": "Bequest", "regret_preset": preset}
        }
        at.session_state["currentCase"] = "t"
        at.run()
        return at

    def test_renders_and_reports_the_run_cost(self, monkeypatch):
        at = self._render(monkeypatch, blocked=False)
        assert not at.exception, [str(e.message) for e in at.exception]
        captions = " ".join(c.value for c in at.caption)
        assert "optimizations" in captions and "scenarios" in captions

    def test_the_default_preset_fits_the_cloud_budget(self, monkeypatch):
        """
        Standard is 397 solves, inside the 500 budget, so the cloud runs it. The page is no
        longer blocked wholesale - the shared budget decides, as it does for every page.
        """
        at = self._render(monkeypatch, blocked=True)
        assert not at.exception, [str(e.message) for e in at.exception]
        assert at.button[0].disabled is False
        captions = " ".join(c.value for c in at.caption)
        assert "optimizations" in captions
        assert "Community Cloud" not in captions

    def test_the_cloud_refuses_an_over_budget_preset(self, monkeypatch):
        at = self._render(monkeypatch, blocked=True, preset="Thorough")
        assert not at.exception, [str(e.message) for e in at.exception]
        assert at.button[0].disabled is True
        assert any("Community Cloud" in c.value for c in at.caption)

    def test_self_hosted_runs_the_heaviest_preset(self, monkeypatch):
        at = self._render(monkeypatch, blocked=False, preset="Thorough")
        assert at.button[0].disabled is False
        assert not any("Community Cloud" in c.value for c in at.caption)
