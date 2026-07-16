"""
Tests for year-1 robustness: summarize_year1 and the run_year1_robustness MCP tool.

Coverage:
  - summarize_year1: pure aggregation on hand-built snapshots (percentile ordering,
    shares, infeasible counting)
  - run_stochastic_spending: year1_decisions alignment with bases (historical, short range)
  - MC reproducibility of the year-1 conversion median with a fixed seed
  - run_year1_robustness (async): flat-params path, output structure and notes

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio
import json

import numpy as np
import pytest

from owlplanner.stresstests import run_stochastic_spending, summarize_year1
from owlplanner.assistant.tools import _build_plan_from_params, run_year1_robustness

HIST_YSTART = 1990
HIST_YEND = 2000  # 11 scenarios

_SINGLE = dict(
    names=["Martin"],
    birth_dates=["1960-07-01"],
    life_expectancy=[88],
    state="TX",
    taxable=[200_000],
    tax_deferred=[800_000],
    roth=[100_000],
    hsa=None,
    cost_basis=None,
    ss_monthly_pias=[2_500],
    ss_ages=[67],
    pension_monthly_amounts=None,
    pension_ages=None,
    rate_method="conservative",
    objective="maxSpending",
)


def _run(coro):
    return asyncio.run(coro)


def _snapshot(x, g0, top=12.0, filled=True):
    return {
        "x": [x],
        "w": [[10_000.0, 5_000.0, 0.0, 0.0]],
        "g0": g0,
        "s0": 0.0,
        "top_bracket_pct": top,
        "filled_to_boundary": filled,
    }


def test_summarize_year1_pure():
    year1 = [_snapshot(50_000, 70_000), _snapshot(60_000, 75_000), _snapshot(55_000, 72_000), None]
    out = summarize_year1(year1, ["Martin"])
    assert out["n_scenarios"] == 4
    assert out["n_infeasible"] == 1
    rc = out["per_person"][0]["roth_conversion"]
    assert rc["p10"] <= rc["p25"] <= rc["median"] <= rc["p75"] <= rc["p90"]
    assert rc["median"] == 55_000
    assert rc["share_converting"] == 1.0
    assert 0.0 <= rc["share_within_10pct_of_median"] <= 1.0
    wd = out["per_person"][0]["withdrawals"]
    assert wd["taxable"]["median"] == 10_000
    assert out["net_spending"]["median"] == 72_000
    assert out["top_bracket"] == {"modal_rate_pct": 12.0, "frequency": 1.0}
    assert out["share_filled_to_boundary"] == 1.0


def test_summarize_year1_no_conversion_agreement():
    # Median conversion is zero: agreement = share of scenarios also not converting.
    year1 = [_snapshot(0.0, 70_000), _snapshot(0.0, 71_000), _snapshot(40_000, 75_000)]
    out = summarize_year1(year1, ["Martin"])
    rc = out["per_person"][0]["roth_conversion"]
    assert rc["median"] == 0.0
    assert rc["share_converting"] == pytest.approx(1 / 3, abs=1e-3)
    assert rc["share_within_10pct_of_median"] == pytest.approx(2 / 3, abs=1e-3)


def test_summarize_year1_all_infeasible():
    out = summarize_year1([None, None], ["Martin"])
    assert out["n_infeasible"] == 2
    assert out["per_person"] == []


@pytest.mark.toml
def test_year1_decisions_aligned_with_bases_historical():
    plan = _build_plan_from_params(**_SINGLE)
    result = run_stochastic_spending(
        plan, {"units": "1"}, "historical", ystart=HIST_YSTART, yend=HIST_YEND
    )
    y1 = result["year1_decisions"]
    assert len(y1) == len(result["bases"]) == HIST_YEND - HIST_YSTART + 1
    for basis, snap in zip(result["bases"], y1, strict=True):
        if basis > 0:
            assert snap is not None
            assert snap["g0"] > 0
            assert len(snap["x"]) == 1 and len(snap["w"][0]) == 4
    summary = summarize_year1(y1, plan.inames)
    assert summary["per_person"][0]["person"] == "Martin"
    # Spending distribution must bracket its own median.
    ns = summary["net_spending"]
    assert ns["p10"] <= ns["median"] <= ns["p90"]


@pytest.mark.toml
def test_year1_mc_reproducible_with_seed():
    # Seed applied at build time (before setRates), the original supported ordering.
    plan = _build_plan_from_params(
        **{**_SINGLE, "rate_method": "historical_gaussian", "rate_frm": 1928}, reproducible_seed=42
    )
    medians = []
    for _ in range(2):
        result = run_stochastic_spending(plan, {"units": "1"}, "mc", N=8)
        g0 = np.array([y["g0"] for y in result["year1_decisions"] if y is not None])
        medians.append(float(np.median(g0)))
    assert medians[0] == pytest.approx(medians[1], rel=1e-9)


@pytest.mark.toml
def test_mc_seed_effective_after_build():
    # Regression: setReproducible() AFTER the plan is built (the ordering used by the
    # run_stochastic and run_year1_robustness MCP tools' seed parameter) must reach
    # the scenario RNG. Previously the reset read the rate model's stale
    # construction-time seed and the runs were not reproducible.
    def _bases(seed):
        plan = _build_plan_from_params(
            **{**_SINGLE, "rate_method": "historical_gaussian", "rate_frm": 1928}
        )
        plan.setReproducible(True, seed=seed)
        return run_stochastic_spending(plan, {"units": "1"}, "mc", N=8)["bases"]

    b1, b2, b3 = _bases(7), _bases(7), _bases(11)
    assert np.allclose(b1, b2, atol=1e-6)  # same seed reproduces
    assert not np.allclose(b1, b3, atol=1e-6)  # different seed differs


@pytest.mark.toml
def test_run_year1_robustness_tool():
    result = _run(
        run_year1_robustness(
            scenario_method="historical",
            ystart=HIST_YSTART,
            yend=HIST_YEND,
            **{k: v for k, v in _SINGLE.items() if k != "objective"},
        )
    )
    data = json.loads(result)
    assert "error" not in data
    assert data["status"] == "completed"
    rb = data["year1_robustness"]
    assert rb["n_scenarios"] == HIST_YEND - HIST_YSTART + 1
    assert rb["per_person"][0]["person"] == "Martin"
    base = data["base_plan_year1"]
    assert base["net_spending"] > 0
    assert base["per_person"][0]["withdrawals"]["taxable"] >= 0
    assert data["notes"]  # honest-interpretation contract present
    assert any("perfect foresight" in n for n in data["notes"])
    flagged = {e["parameter"] for e in data.get("assumed_defaults", [])}
    assert "cost_basis" in flagged


# ---------------------------------------------------------------------------
# Case-file solver options must reach the scenario solves (filename path)
# ---------------------------------------------------------------------------

CHRIS_PAT_TOML = "examples/Case_chris+pat.toml"


def test_merge_case_opts_scales_and_overrides():
    from owlplanner.assistant.tools import _merge_case_opts

    class _P:
        solverOptions = {
            "maxRothConversion": 100,
            "bequest": 400.0,
            "previousMAGIs": [170.0, 150.0],
            "spendingSlack": 0,
            "withMedicare": "loop",
        }

    merged = _merge_case_opts(_P(), {"units": "1", "bequest": 250_000.0})
    assert merged["maxRothConversion"] == 100_000.0  # file $k scaled to full dollars
    assert merged["bequest"] == 250_000.0  # explicit MCP argument wins over the file
    assert merged["previousMAGIs"] == [170_000.0, 150_000.0]
    assert merged["withMedicare"] == "loop"
    assert merged["units"] == "1"


def test_year1_filename_path_merges_case_solver_options(monkeypatch):
    """The filename path must not silently drop the case's [solver_options]."""
    import owlplanner.assistant.tools as tools

    captured = {}

    def _stub(plan, scenario_method, ystart, yend, n_scenarios, opts, seed):
        captured.update(opts)
        raise RuntimeError("stop after capturing opts")

    monkeypatch.setattr(tools, "_year1_robustness_blocking", _stub)
    result = json.loads(_run(tools.run_year1_robustness(filename=CHRIS_PAT_TOML)))
    assert "error" in result
    assert captured["bequest"] == 400_000.0
    assert captured["maxRothConversion"] == 100_000.0
    assert captured["units"] == "1"
