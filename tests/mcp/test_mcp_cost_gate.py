"""
Tests for the run-time confirmation gate on the MCP scenario sweeps.

A sweep projected to take longer than OWL_MCP_CONFIRM_MINUTES stops after one pilot
solve and returns needs_confirmation; confirm_long_run=True runs it regardless.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio
import json

import pytest

from owlplanner.assistant.tools import _check_run_cost, _NeedsConfirmation, run_monte_carlo


def _mc(**kwargs):
    args = dict(
        names=["Martin"],
        birth_dates=["1960-07-01"],
        life_expectancy=[88],
        taxable=[200_000],
        tax_deferred=[800_000],
        roth=[100_000],
        ss_monthly_pias=[2500],
        ss_ages=[67],
        state="TX",
        rate_method="gmm",
        n_scenarios=5,
        seed=42,
    )
    args.update(kwargs)
    return json.loads(asyncio.run(run_monte_carlo(**args)))


def test_short_run_passes(monkeypatch):
    monkeypatch.setenv("OWL_MCP_CONFIRM_MINUTES", "2")
    _check_run_cost(1.0, 100, {}, parallel=False, confirm=False)  # 100 s < 2 min


def test_long_run_stops_with_estimate(monkeypatch):
    monkeypatch.setenv("OWL_MCP_CONFIRM_MINUTES", "2")
    with pytest.raises(_NeedsConfirmation) as exc:
        _check_run_cost(6.0, 1000, {"withMedicare": "optimize"}, parallel=False, confirm=False)
    info = exc.value.info
    assert info["needs_confirmation"] is True
    assert info["total_solves"] == 1000
    assert info["estimated_minutes"] == 100.0
    assert any("withMedicare" in d for d in info["cost_drivers"])
    assert any("n_scenarios=20" in a for a in info["cheaper_alternatives"])


def test_very_long_run_flagged_but_confirmable(monkeypatch):
    monkeypatch.setenv("OWL_MCP_CONFIRM_MINUTES", "2")
    monkeypatch.setenv("OWL_MCP_VERY_LONG_MINUTES", "60")
    with pytest.raises(_NeedsConfirmation) as exc:
        _check_run_cost(60.0, 100_000, {}, parallel=False, confirm=False)
    info = exc.value.info
    assert info["needs_confirmation"] is True
    assert info["very_long"] is True
    assert info["estimated_duration"] == "69 days"
    _check_run_cost(60.0, 100_000, {}, parallel=False, confirm=True)  # the user agreed: runs


def test_long_but_not_very_long(monkeypatch):
    monkeypatch.setenv("OWL_MCP_CONFIRM_MINUTES", "2")
    monkeypatch.setenv("OWL_MCP_VERY_LONG_MINUTES", "60")
    with pytest.raises(_NeedsConfirmation) as exc:
        _check_run_cost(1.0, 600, {}, parallel=False, confirm=False)
    assert exc.value.info["very_long"] is False
    assert exc.value.info["estimated_duration"] == "10 minutes"


def test_confirm_bypasses_gate(monkeypatch):
    monkeypatch.setenv("OWL_MCP_CONFIRM_MINUTES", "0")
    _check_run_cost(60.0, 10_000, {}, parallel=False, confirm=True)


def test_parallel_sweep_credited_with_speedup(monkeypatch):
    monkeypatch.setenv("OWL_MCP_CONFIRM_MINUTES", "0")
    monkeypatch.setattr("os.cpu_count", lambda: 10)
    with pytest.raises(_NeedsConfirmation) as exc:
        _check_run_cost(3.5, 100, {}, parallel=True, confirm=False)
    assert exc.value.info["parallel_speedup"] == 3.5
    assert exc.value.info["estimated_minutes"] == pytest.approx(100 / 60, abs=0.05)


@pytest.mark.toml
def test_run_monte_carlo_asks_then_runs(monkeypatch):
    monkeypatch.setenv("OWL_MCP_CONFIRM_MINUTES", "0")
    data = _mc()
    assert data.get("needs_confirmation") is True
    assert data["total_solves"] == 5
    assert "distribution" not in data

    data = _mc(confirm_long_run=True)
    assert data["status"] == "completed"
    assert data["n_scenarios_attempted"] == 5


# Scenarios keep the plan's claiming ages, so optimize_ss_ages costs nothing per scenario.


def test_ss_ages_not_a_cost_driver():
    from owlplanner.assistant.tools import _cost_drivers

    assert _cost_drivers({"withSSAges": "optimize"}) == []


@pytest.fixture
def no_age_search(monkeypatch):
    from owlplanner.plan import Plan

    def no_search(self, *args, **kwargs):
        raise AssertionError("claiming ages searched inside a scenario run")

    monkeypatch.setattr(Plan, "_ssAgeSearch", no_search)


def test_monte_carlo_holds_claiming_ages(no_age_search):
    out = _mc(optimize_ss_ages=True, confirm_long_run=True)
    assert "error" not in out, out


def test_historical_range_holds_claiming_ages(no_age_search):
    from owlplanner.assistant.tools import _historical_blocking
    from owlplanner.config import readConfig

    plan = readConfig("examples/Case_dana.toml", verbose=False)
    opts = {"solver": "HiGHS", "withSSAges": "optimize"}
    _, n, results, _, _ = _historical_blocking(plan, "maxSpending", opts, 1966, 1967, False, False, 0)
    assert n == 2 and len(results) == 2
    assert opts["withSSAges"] == "optimize", "must not mutate the caller's options"


def test_pilot_times_one_held_solve(monkeypatch):
    """A base solve that searched the ages is timed again, once, at the ages chosen."""
    from owlplanner.assistant.tools import _timed_solve
    from owlplanner.config import readConfig
    from owlplanner.plan import Plan

    plan = readConfig("examples/Case_dana.toml", verbose=False)
    calls = []
    solve = Plan.solve

    def spy(self, objective, options=None):
        calls.append((self is plan, dict(options or {}).get("withSSAges")))
        return solve(self, objective, options)

    monkeypatch.setattr(Plan, "solve", spy)
    _timed_solve(plan, "maxSpending", {"solver": "HiGHS", "withSSAges": "optimize"})
    assert plan.caseStatus == "solved"
    assert plan.solverOptions["withSSAges"] == "optimize"
    assert calls[-1] == (False, None)
