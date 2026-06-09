"""
Tests for run_longevity_stochastic and list_mortality_tables MCP tools.

Copyright (C) 2025-2026 The Owl Authors
"""

import asyncio
import json

import pytest

from owlplanner.cli.cmd_serve import list_mortality_tables, run_longevity_stochastic

_SINGLE = dict(
    sexes=["F"],
    names=["Sam"],
    birth_years=[1962],
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
    result = _run(run_longevity_stochastic(
        scenario_method="historical",
        n_scenarios=5,
        **_SINGLE,
    ))
    data = json.loads(result)
    assert "error" in data
    assert "historical" in data["error"].lower()


@pytest.mark.toml
def test_run_longevity_stochastic_mc_smoke():
    result = _run(run_longevity_stochastic(
        scenario_method="mc",
        target_success_rate=0.70,
        n_scenarios=10,
        seed=42,
        **_SINGLE,
    ))
    data = json.loads(result)
    assert data["status"] == "completed"
    assert data["mortality_table"] == "SSA2025"
    assert data["sexes"] == ["F"]
    assert data["n_scenarios_run"] == 10
    # Longevity sampling can zero out spending for imminent-death draws; max is more stable.
    assert data["max_spending"]["today_dollars"] >= 0
    assert len(data["frontier"]) >= 1
