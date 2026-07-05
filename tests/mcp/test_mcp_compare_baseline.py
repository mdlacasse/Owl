"""
Tests for the compare_to_baseline MCP tool.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio
import json

import pytest

from owlplanner.assistant.tools import (
    BASELINE_POLICIES,
    _apply_baseline_policies_config,
    compare_to_baseline,
)

BILL_TOML = "examples/Case_bill.toml"


def _run(coro):
    return asyncio.run(coro)


def test_unknown_policy_rejected():
    result = _run(
        compare_to_baseline(
            names=["X"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[1],
            tax_deferred=[1],
            roth=[1],
            baseline_policies=["taxable_first_ordering"],
        )
    )
    data = json.loads(result)
    assert "Unknown baseline policies" in data["error"]


def test_empty_policies_rejected():
    result = _run(
        compare_to_baseline(
            names=["X"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[1],
            tax_deferred=[1],
            roth=[1],
            baseline_policies=[],
        )
    )
    data = json.loads(result)
    assert "At least one baseline policy" in data["error"]


def test_filename_and_params_mutually_exclusive():
    result = _run(compare_to_baseline(filename=BILL_TOML, names=["X"]))
    data = json.loads(result)
    assert "not both" in data["error"]


def test_baseline_config_mutations():
    diconf = {"solver_options": {"startRothConversions": 2030, "withSSAges": "optimize"}}
    base = _apply_baseline_policies_config(diconf, list(BASELINE_POLICIES))
    so = base["solver_options"]
    assert so["maxRothConversion"] == 0
    assert so["useRothConvOverrides"] is False
    assert "startRothConversions" not in so
    assert "withSSAges" not in so
    # The original config is untouched.
    assert diconf["solver_options"]["startRothConversions"] == 2030
    assert diconf["solver_options"]["withSSAges"] == "optimize"


@pytest.mark.toml
def test_compare_to_baseline_params_end_to_end():
    result = _run(
        compare_to_baseline(
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            state="TX",
            rate_method="conservative",
        )
    )
    data = json.loads(result)
    assert "error" not in data
    assert data["baseline_policies"] == list(BASELINE_POLICIES)
    # The baseline truly never converts.
    assert data["baseline"]["roth_conversions_today"] == 0
    # The baseline is a restriction, so optimized >= baseline (up to solver tolerance).
    assert data["optimized"]["spending_basis"] >= data["baseline"]["spending_basis"] - 1.0
    assert data["headline"]["extra_annual_spending_today"] == pytest.approx(
        data["advantage"]["spending_basis"], abs=0.01
    )
    # Ledger travels: state and rate_method were given, cost basis was not.
    flagged = {e["parameter"] for e in data["assumed_defaults"]}
    assert "cost_basis" in flagged
    assert "state" not in flagged


@pytest.mark.toml
def test_compare_to_baseline_from_file():
    result = _run(compare_to_baseline(filename=BILL_TOML))
    data = json.loads(result)
    assert "error" not in data
    assert data["baseline"]["roth_conversions_today"] == 0
    assert data["optimized"]["spending_basis"] >= data["baseline"]["spending_basis"] - 1.0
    assert "seed_used" in data
