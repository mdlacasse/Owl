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
    _build_plan_from_params,
    compare_to_baseline,
)

BILL_TOML = "examples/Case_bill.toml"


def _run(coro):
    return asyncio.run(coro)


def _single_plan():
    return _build_plan_from_params(
        names=["Pat"],
        birth_years=[1960],
        life_expectancy=[88],
        state="CA",
        taxable=[200_000],
        tax_deferred=[800_000],
        roth=[100_000],
        hsa=None,
        cost_basis=None,
        ss_monthly_pias=[2500],
        ss_ages=[67],
        pension_monthly_amounts=None,
        pension_ages=None,
        rate_method="conservative",
    )


@pytest.mark.toml
def test_taxable_first_ordering_respected():
    plan = _single_plan()
    plan.solve("maxSpending", {"units": "1", "maxRothConversion": 0, "withdrawalOrder": "taxable_first"})
    assert plan.caseStatus == "solved"
    b, w, rho = plan.b_ijn, plan.w_ijn, plan.rho_in
    for n in range(plan.N_n):
        # While taxable money remains at year end, tax-deferred withdrawals stay at the RMD.
        if b[0, 0, n + 1] > 1.0:
            assert w[0, 1, n] <= rho[0, n] * b[0, 1, n] + 1.0
        # While tax-deferred money remains at year end, no Roth withdrawals.
        if b[0, 1, n + 1] > 1.0:
            assert w[0, 2, n] <= 1.0

    # The ordering is a restriction: it cannot beat the free withdrawal order.
    free = _single_plan()
    free.solve("maxSpending", {"units": "1", "maxRothConversion": 0})
    assert plan.basis <= free.basis + 1.0


def test_bad_withdrawal_order_rejected():
    plan = _single_plan()
    with pytest.raises(ValueError, match="withdrawalOrder"):
        plan.solve("maxSpending", {"units": "1", "withdrawalOrder": "roth_first"})


def test_unknown_policy_rejected():
    result = _run(
        compare_to_baseline(
            names=["X"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[1],
            tax_deferred=[1],
            roth=[1],
            baseline_policies=["four_percent_rule"],
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
    assert so["withdrawalOrder"] == "taxable_first"
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
def test_ordering_policy_tightens_baseline():
    """Adding taxable_first_ordering must not raise the baseline (monotone restriction)."""
    kwargs = dict(
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
    two = json.loads(_run(compare_to_baseline(baseline_policies=["no_roth_conversions"], **kwargs)))
    three = json.loads(
        _run(compare_to_baseline(baseline_policies=["no_roth_conversions", "taxable_first_ordering"], **kwargs))
    )
    assert "error" not in two and "error" not in three
    assert three["baseline"]["spending_basis"] <= two["baseline"]["spending_basis"] + 1.0
    assert three["headline"]["extra_annual_spending_today"] >= two["headline"]["extra_annual_spending_today"] - 1.0


@pytest.mark.toml
def test_compare_to_baseline_from_file():
    result = _run(compare_to_baseline(filename=BILL_TOML))
    data = json.loads(result)
    assert "error" not in data
    assert data["baseline"]["roth_conversions_today"] == 0
    assert data["optimized"]["spending_basis"] >= data["baseline"]["spending_basis"] - 1.0
    assert "seed_used" in data
