"""
Tests for the run_stochastic MCP tool.

Coverage:
  - _stochastic_blocking: historical and MC paths, error cases
  - _build_stochastic_json: output structure and value correctness
  - run_stochastic (async): flat params and TOML-based, error handling

Historical scenarios use a short year range (1990–2005, ~14 scenarios) for speed.
MC tests use n_scenarios=20 with a fast stochastic method.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio
import json

import numpy as np
import pytest

from owlplanner.assistant.tools import (
    _build_plan_from_params,
    _build_stochastic_json,
    _stochastic_blocking,
    run_stochastic,
)

BILL_TOML = "examples/Case_bill.toml"

# Short historical window keeps each test under ~5 seconds
HIST_YSTART = 1990
HIST_YEND = 2005  # 14 scenarios for a 23-year plan

# Minimal flat params shared across tests
_SINGLE = dict(
    names=["Martin"],
    birth_years=[1960],
    life_expectancy=[88],
    state="TX",
    taxable=[200_000],
    tax_deferred=[800_000],
    roth=[100_000],
    ss_monthly_pias=[2_500],
    ss_ages=[67],
    rate_method="conservative",
    objective="maxSpending",
)

_COUPLE = dict(
    names=["Alice", "Bob"],
    birth_years=[1963, 1961],
    life_expectancy=[90, 87],
    state="TX",
    taxable=[150_000, 150_000],
    tax_deferred=[600_000, 600_000],
    roth=[75_000, 75_000],
    ss_monthly_pias=[2_333, 2_667],
    ss_ages=[67, 67],
    rate_method="conservative",
    objective="maxSpending",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _build_single(**kwargs):
    p = dict(
        hsa=None,
        cost_basis=None,
        pension_monthly_amounts=None,
        pension_ages=None,
        wages=None,
        contributions=None,
        big_ticket_items=None,
        debts=None,
        fixed_assets=None,
        spias=None,
        survivor_fraction=60.0,
        initial_allocation=[60, 40, 0, 0],
        final_allocation=[40, 60, 0, 0],
        constrain_mean=False,
    )
    p.update(_SINGLE)
    p.update(kwargs)
    return _build_plan_from_params(**p)


# ---------------------------------------------------------------------------
# _stochastic_blocking — historical path
# ---------------------------------------------------------------------------


@pytest.mark.toml
def test_stochastic_blocking_historical_returns_result():
    plan = _build_single()
    plan, result = _stochastic_blocking(plan, "historical", HIST_YSTART, HIST_YEND, None, {}, None)
    assert plan.caseStatus == "solved"
    assert "bases" in result
    assert "frontier_g" in result
    assert "frontier_prob" in result
    assert "lambdas" in result


@pytest.mark.toml
def test_stochastic_blocking_historical_n_scenarios():
    plan = _build_single()
    _, result = _stochastic_blocking(plan, "historical", HIST_YSTART, HIST_YEND, None, {}, None)
    # yend may be clipped if yend + N_n > thisyear; just check ≥ 1 scenario ran
    assert len(result["bases"]) >= 1
    assert len(result["bases"]) <= HIST_YEND - HIST_YSTART + 1


@pytest.mark.toml
def test_stochastic_blocking_start_years_recorded():
    plan = _build_single()
    _, result = _stochastic_blocking(plan, "historical", HIST_YSTART, HIST_YEND, None, {}, None)
    assert result["start_years"] is not None
    assert result["start_years"][0] == HIST_YSTART
    # last start year may be ≤ HIST_YEND if yend was clipped
    assert result["start_years"][-1] <= HIST_YEND


@pytest.mark.toml
def test_stochastic_blocking_bases_positive():
    plan = _build_single()
    _, result = _stochastic_blocking(plan, "historical", HIST_YSTART, HIST_YEND, None, {}, None)
    assert np.all(result["bases"] >= 0)
    assert np.any(result["bases"] > 0)


@pytest.mark.toml
def test_stochastic_blocking_frontier_monotone():
    """frontier_prob must be non-increasing: as lambda increases, spending falls and fewer scenarios fail."""
    plan = _build_single()
    _, result = _stochastic_blocking(plan, "historical", HIST_YSTART, HIST_YEND, None, {}, None)
    prob = result["frontier_prob"]
    assert np.all(np.diff(prob) <= 1e-9), "frontier_prob must be non-increasing"


@pytest.mark.toml
def test_stochastic_blocking_mc_requires_stochastic_rate():
    """MC mode with a deterministic rate model must raise ValueError."""
    plan = _build_single(rate_method="conservative")  # deterministic
    with pytest.raises(ValueError, match="stochastic"):
        _stochastic_blocking(plan, "mc", None, None, 20, {}, None)


@pytest.mark.toml
def test_stochastic_blocking_mc_with_stochastic_rate():
    plan = _build_single(rate_method="gmm")  # gmm: stochastic, no required params
    plan, result = _stochastic_blocking(plan, "mc", None, None, 20, {}, seed=42)
    assert len(result["bases"]) == 20
    assert result["start_years"] is None  # MC has no start years


@pytest.mark.toml
def test_stochastic_blocking_invalid_method():
    plan = _build_single()
    plan.solve("maxSpending", {})
    with pytest.raises(ValueError, match="Unknown scenario_method"):
        _stochastic_blocking(plan, "bogus", None, None, None, {}, None)


# ---------------------------------------------------------------------------
# _build_stochastic_json — output structure
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _hist_result():
    """Run once and reuse for all _build_stochastic_json tests."""
    plan = _build_single()
    plan, result = _stochastic_blocking(plan, "historical", HIST_YSTART, HIST_YEND, None, {}, None)
    return plan, result


@pytest.mark.toml
def test_build_json_top_level_keys(_hist_result):
    plan, result = _hist_result
    out = _build_stochastic_json(plan, result, 90.0, "historical")
    for key in (
        "status",
        "case_name",
        "scenario_method",
        "n_scenarios_run",
        "n_scenarios_infeasible",
        "target_success_rate_pct",
        "achieved_success_rate_pct",
        "spending_at_target",
        "max_spending",
        "frontier",
    ):
        assert key in out, f"Missing key: {key}"


@pytest.mark.toml
def test_build_json_status_completed(_hist_result):
    plan, result = _hist_result
    out = _build_stochastic_json(plan, result, 90.0, "historical")
    assert out["status"] == "completed"


@pytest.mark.toml
def test_build_json_spending_at_target_keys(_hist_result):
    plan, result = _hist_result
    out = _build_stochastic_json(plan, result, 90.0, "historical")
    assert "today_dollars" in out["spending_at_target"]
    assert "year1_nominal" in out["spending_at_target"]


@pytest.mark.toml
def test_build_json_spending_positive(_hist_result):
    plan, result = _hist_result
    out = _build_stochastic_json(plan, result, 90.0, "historical")
    assert out["spending_at_target"]["today_dollars"] > 0
    assert out["max_spending"]["today_dollars"] > 0


@pytest.mark.toml
def test_build_json_target_le_max_spending(_hist_result):
    """Constrained (90%) spending must be ≤ unconstrained maximum."""
    plan, result = _hist_result
    out = _build_stochastic_json(plan, result, 90.0, "historical")
    assert out["spending_at_target"]["today_dollars"] <= out["max_spending"]["today_dollars"]


@pytest.mark.toml
def test_build_json_achieved_success_rate_at_least_target(_hist_result):
    """Achieved success rate must meet or exceed the requested target."""
    plan, result = _hist_result
    out = _build_stochastic_json(plan, result, 90.0, "historical")
    assert out["achieved_success_rate_pct"] >= 90.0 - 1e-6


@pytest.mark.toml
def test_build_json_frontier_structure(_hist_result):
    plan, result = _hist_result
    out = _build_stochastic_json(plan, result, 90.0, "historical")
    assert len(out["frontier"]) >= 5
    for pt in out["frontier"]:
        assert "success_rate_pct" in pt
        assert "spending_today_dollars" in pt
        assert "spending_year1_nominal" in pt


@pytest.mark.toml
def test_build_json_frontier_rates_in_range(_hist_result):
    plan, result = _hist_result
    out = _build_stochastic_json(plan, result, 90.0, "historical")
    for pt in out["frontier"]:
        assert 0.0 <= pt["success_rate_pct"] <= 100.0


@pytest.mark.toml
def test_build_json_different_targets_order(_hist_result):
    """Higher target success rate yields lower or equal spending."""
    plan, result = _hist_result
    out_90 = _build_stochastic_json(plan, result, 90.0, "historical")
    out_70 = _build_stochastic_json(plan, result, 70.0, "historical")
    assert out_90["spending_at_target"]["today_dollars"] <= out_70["spending_at_target"]["today_dollars"]


@pytest.mark.toml
def test_build_json_n_scenarios_matches(_hist_result):
    plan, result = _hist_result
    out = _build_stochastic_json(plan, result, 90.0, "historical")
    # yend may be clipped so n_scenarios_run ≤ requested range
    assert out["n_scenarios_run"] >= 1
    assert out["n_scenarios_run"] <= HIST_YEND - HIST_YSTART + 1


# ---------------------------------------------------------------------------
# run_stochastic (async) — flat params
# ---------------------------------------------------------------------------


@pytest.mark.toml
def test_run_stochastic_historical_single():
    result = _run(
        run_stochastic(
            scenario_method="historical",
            target_success_rate_pct=90.0,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    d = json.loads(result)
    assert d["status"] == "completed"
    assert d["spending_at_target"]["today_dollars"] > 0


@pytest.mark.toml
def test_run_stochastic_historical_couple():
    result = _run(
        run_stochastic(
            scenario_method="historical",
            target_success_rate_pct=85.0,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_COUPLE,
        )
    )
    d = json.loads(result)
    assert d["status"] == "completed"
    # yend is clipped for the longer couple horizon; just verify scenarios ran
    assert d["n_scenarios_run"] >= 1


@pytest.mark.toml
def test_run_stochastic_mc_single():
    result = _run(
        run_stochastic(
            scenario_method="mc",
            target_success_rate_pct=90.0,
            n_scenarios=20,
            seed=42,
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            state="TX",
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2_500],
            ss_ages=[67],
            rate_method="gmm",  # stochastic, no required params
            objective="maxSpending",
        )
    )
    d = json.loads(result)
    assert d["status"] == "completed"
    assert d["n_scenarios_run"] == 20


@pytest.mark.toml
def test_run_stochastic_full_json_structure():
    result = _run(
        run_stochastic(
            scenario_method="historical",
            target_success_rate_pct=90.0,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    d = json.loads(result)
    for key in (
        "status",
        "case_name",
        "scenario_method",
        "n_scenarios_run",
        "target_success_rate_pct",
        "achieved_success_rate_pct",
        "spending_at_target",
        "max_spending",
        "frontier",
    ):
        assert key in d, f"Missing key: {key}"


@pytest.mark.toml
def test_run_stochastic_frontier_non_empty():
    result = _run(
        run_stochastic(
            scenario_method="historical",
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    d = json.loads(result)
    assert len(d["frontier"]) >= 5


@pytest.mark.toml
def test_run_stochastic_higher_target_lower_spending():
    r90 = _run(
        run_stochastic(
            scenario_method="historical",
            target_success_rate_pct=90.0,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    r70 = _run(
        run_stochastic(
            scenario_method="historical",
            target_success_rate_pct=70.0,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    d90 = json.loads(r90)
    d70 = json.loads(r70)
    assert d90["spending_at_target"]["today_dollars"] <= d70["spending_at_target"]["today_dollars"]


# ---------------------------------------------------------------------------
# run_stochastic — TOML-based input
# ---------------------------------------------------------------------------


@pytest.mark.toml
def test_run_stochastic_from_toml():
    result = _run(
        run_stochastic(
            filename=BILL_TOML,
            scenario_method="historical",
            target_success_rate_pct=90.0,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
        )
    )
    d = json.loads(result)
    assert d["status"] == "completed"
    assert d["case_name"] == "bill"


@pytest.mark.toml
def test_run_stochastic_from_toml_with_override():
    result = _run(
        run_stochastic(
            filename=BILL_TOML,
            overrides=["basic_info.state=CA"],
            scenario_method="historical",
            target_success_rate_pct=90.0,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
        )
    )
    d = json.loads(result)
    assert d["status"] == "completed"


# ---------------------------------------------------------------------------
# run_stochastic — error handling
# ---------------------------------------------------------------------------


def test_run_stochastic_missing_params_returns_error():
    result = _run(run_stochastic())  # no filename, no flat params
    d = json.loads(result)
    assert "error" in d


def test_run_stochastic_bad_filename_returns_error():
    result = _run(run_stochastic(filename="nonexistent_xyz.toml"))
    d = json.loads(result)
    assert "error" in d


@pytest.mark.toml
def test_run_stochastic_mc_deterministic_rate_returns_error():
    """MC with conservative (deterministic) rate should return error JSON, not raise."""
    result = _run(
        run_stochastic(
            scenario_method="mc",
            n_scenarios=10,
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            state="TX",
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            rate_method="conservative",  # deterministic — should fail gracefully
            objective="maxSpending",
        )
    )
    d = json.loads(result)
    assert "error" in d


def test_run_stochastic_bad_scenario_method_returns_error():
    result = _run(
        run_stochastic(
            scenario_method="unknown_method",
            **_SINGLE,
        )
    )
    d = json.loads(result)
    assert "error" in d


# ---------------------------------------------------------------------------
# run_stochastic — target_success_rate_pct validation (0-100 convention)
# ---------------------------------------------------------------------------


def test_run_stochastic_old_convention_target_returns_error():
    """target_success_rate_pct=0.90 (old 0-1 convention) is rejected with a 'Did you mean' hint."""
    result = _run(
        run_stochastic(
            scenario_method="historical",
            target_success_rate_pct=0.90,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    d = json.loads(result)
    assert "error" in d
    assert "(1, 100]" in d["error"]
    assert "90" in d["error"]


def test_run_stochastic_target_above_100_returns_error():
    result = _run(
        run_stochastic(
            scenario_method="historical",
            target_success_rate_pct=150.0,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    d = json.loads(result)
    assert "error" in d
    assert "(1, 100]" in d["error"]


def test_run_stochastic_target_zero_returns_error():
    result = _run(
        run_stochastic(
            scenario_method="historical",
            target_success_rate_pct=0.0,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    d = json.loads(result)
    assert "error" in d


# ---------------------------------------------------------------------------
# run_stochastic — n_scenarios ignored in historical mode
# ---------------------------------------------------------------------------


@pytest.mark.toml
def test_run_stochastic_historical_n_scenarios_note():
    """A non-default n_scenarios in historical mode is ignored, with an explanatory note."""
    result = _run(
        run_stochastic(
            scenario_method="historical",
            n_scenarios=5,
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    d = json.loads(result)
    assert d["status"] == "completed"
    assert "note" in d
    assert "n_scenarios=5" in d["note"]


@pytest.mark.toml
def test_run_stochastic_historical_default_n_scenarios_no_note():
    """The default n_scenarios=200 in historical mode does not trigger the note."""
    result = _run(
        run_stochastic(
            scenario_method="historical",
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **_SINGLE,
        )
    )
    d = json.loads(result)
    assert d["status"] == "completed"
    assert "note" not in d
