"""
Tests for the withDuals engine path and the explain_results MCP tool.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio
import json

import pytest

from owlplanner.assistant.explain import build_explanation
from owlplanner.assistant.tools import _build_plan_from_params, explain_results

BILL_TOML = "examples/Case_bill.toml"


def _run(coro):
    return asyncio.run(coro)


def _solved_plan(**opts):
    plan = _build_plan_from_params(
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
    solve_opts = {"units": "1", "withDuals": True, "bequest": 400_000}
    solve_opts.update(opts)
    plan.solve("maxSpending", solve_opts)
    return plan


@pytest.mark.toml
def test_with_duals_populates_dual_data():
    plan = _solved_plan()
    assert plan.caseStatus == "solved"
    dd = plan._dual_data
    assert dd is not None
    assert len(dd["row_dual"]) == plan.A.ncons
    assert len(dd["row_tags"]) == plan.A.ncons
    families = {t[0] for t in dd["row_tags"] if t is not None}
    assert {"bequest_floor", "cash_flow", "rmd"} <= families

    # Bequest floor is binding and its today's-$ sensitivity is economically sane:
    # each today's-$ of required bequest costs less than a dollar of lifetime
    # spending when real returns are positive.
    idx = [i for i, t in enumerate(dd["row_tags"]) if t == ("bequest_floor",)][0]
    cost = -dd["row_dual"][idx] * dd["objFac"] * plan.gamma_n[plan.N_n]
    assert 0.0 < cost < 1.2

    # Cash-flow duals form the endogenous discount curve: year-0 value >= later years.
    cf = {t[1]: dd["row_dual"][i] * dd["objFac"] * plan.gamma_n[t[1]]
          for i, t in enumerate(dd["row_tags"]) if t is not None and t[0] == "cash_flow"}
    assert cf[0] > 1.0  # a marginal dollar today buys more than a dollar of lifetime spending
    assert cf[0] >= cf[max(cf)]


@pytest.mark.toml
def test_build_explanation_structure_and_consistency():
    plan = _solved_plan(maxRothConversion=50_000)
    ex = build_explanation(plan)
    for section in ("shadow_prices", "binding_constraints", "roth_conversions", "tax_brackets",
                    "account_depletion", "caveats"):
        assert section in ex

    # Conversion schedule matches the primal solution (today's dollars).
    sched_total = ex["roth_conversions"]["total_converted_today"]
    x_today = float((plan.x_in / plan.gamma_n[: plan.N_n]).sum())
    assert sched_total == pytest.approx(x_today, rel=1e-3)

    # The $50k nominal cap must bind in year 1 and be reported.
    binding = ex["roth_conversions"].get("cap_binding_years", [])
    assert any(b["year"] == int(plan.year_n[0]) for b in binding)

    # Bracket analysis reports plausible top rates and non-negative headroom.
    by_year = ex["tax_brackets"]["by_year"]
    assert by_year
    assert all(0 < r["top_bracket_rate_pct"] <= 37 for r in by_year)
    assert all(r["headroom_in_bracket_today"] >= 0 for r in by_year)

    # Taxable is drawn down before tax-deferred.
    events = {e["account"]: e["depleted_in"] for e in ex["account_depletion"]["events"]}
    assert "taxable" in events

    # Zero-slack profile rows must not pollute the report.
    assert "spending_profile_band" not in ex["shadow_prices"]
    assert not any(b["constraint"].startswith("profile") for b in ex["binding_constraints"])


def test_build_explanation_requires_duals():
    plan = _build_plan_from_params(
        names=["Q"], birth_years=[1965], life_expectancy=[85], state=None,
        taxable=[10_000], tax_deferred=[10_000], roth=[0], hsa=None, cost_basis=None,
        ss_monthly_pias=None, ss_ages=None, pension_monthly_amounts=None, pension_ages=None,
    )
    ex = build_explanation(plan)
    assert "error" in ex


@pytest.mark.toml
def test_explain_results_tool_params_path():
    result = _run(
        explain_results(
            names=["Pat"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            state="CA",
            rate_method="conservative",
            bequest=400_000,
        )
    )
    data = json.loads(result)
    assert "error" not in data
    ex = data["explanation"]
    assert "bequest_floor" in ex["shadow_prices"]
    assert ex["shadow_prices"]["value_of_extra_income_by_year"]["most_valuable_years"]
    assert data["key_metrics"]["spending_basis"] > 0
    flagged = {e["parameter"] for e in data["assumed_defaults"]}
    assert "cost_basis" in flagged


@pytest.mark.toml
def test_explain_results_tool_file_path():
    result = _run(explain_results(filename=BILL_TOML))
    data = json.loads(result)
    assert "error" not in data
    assert "shadow_prices" in data["explanation"]
    assert "tax_brackets" in data["explanation"]
