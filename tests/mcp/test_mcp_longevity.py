"""
Tests for run_longevity_stochastic and list_mortality_tables MCP tools.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio
import json

import pytest

from owlplanner.assistant.tools import list_mortality_tables, run_longevity_stochastic

_SINGLE = dict(
    sexes=["F"],
    names=["Sam"],
    birth_dates=["1962-07-01"],
    life_expectancy=[87],
    state="TX",
    taxable=[0.0],
    tax_deferred=[1_000_000.0],
    roth=[0.0],
    ss_monthly_pias=[2_300.0],
    ss_ages=[67],
    rate_method="gmm",
    objective="maxSpending",
)


def _run(coro):
    return asyncio.run(coro)


def test_list_mortality_tables_structure():
    result = json.loads(list_mortality_tables())
    assert "mortality_tables" in result
    assert len(result["mortality_tables"]) >= 1
    entry = result["mortality_tables"][0]
    for key in ("key", "le_at_65", "description"):
        assert key in entry


def test_list_mortality_tables_sorted_by_le():
    result = json.loads(list_mortality_tables())
    les = [t["le_at_65"] for t in result["mortality_tables"]]
    assert les == sorted(les)


def test_run_longevity_historical_rejected_upfront():
    result = _run(
        run_longevity_stochastic(
            scenario_method="historical",
            n_scenarios=5,
            **_SINGLE,
        )
    )
    data = json.loads(result)
    assert "error" in data
    assert "historical" in data["error"].lower()


@pytest.mark.toml
def test_run_longevity_stochastic_mc_smoke():
    result = _run(
        run_longevity_stochastic(
            scenario_method="mc",
            target_success_rate_pct=70.0,
            n_scenarios=10,
            seed=42,
            **_SINGLE,
        )
    )
    data = json.loads(result)
    assert data["status"] == "completed"
    assert data["mortality_table"] == "SSA2025"
    assert data["sexes"] == ["F"]
    assert data["n_scenarios_run"] == 10
    # Longevity sampling can zero out spending for imminent-death draws; max is more stable.
    assert data["max_spending"]["today_dollars"] >= 0
    assert len(data["frontier"]) >= 1


def test_run_longevity_old_convention_target_returns_error():
    """target_success_rate_pct=0.70 (old 0-1 convention) is rejected with a 'Did you mean' hint."""
    result = _run(
        run_longevity_stochastic(
            scenario_method="mc",
            target_success_rate_pct=0.70,
            n_scenarios=10,
            seed=42,
            **_SINGLE,
        )
    )
    data = json.loads(result)
    assert "error" in data
    assert "(1, 100]" in data["error"]
    assert "70" in data["error"]


def test_run_longevity_target_above_100_returns_error():
    result = _run(
        run_longevity_stochastic(
            scenario_method="mc",
            target_success_rate_pct=150.0,
            n_scenarios=10,
            seed=42,
            **_SINGLE,
        )
    )
    data = json.loads(result)
    assert "error" in data
    assert "(1, 100]" in data["error"]
