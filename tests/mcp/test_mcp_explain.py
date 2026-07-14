"""
Tests for the withDuals engine path and the explain_results MCP tool.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio
import json

import pytest

from owlplanner.assistant.explain import build_explanation
from owlplanner.assistant.explain_schema import SCHEMA_VERSION, PlanExplanation
from owlplanner.assistant.tools import _build_plan_from_params, explain_results

BILL_TOML = "examples/Case_bill.toml"


def _run(coro):
    return asyncio.run(coro)


def _solved_plan(**opts):
    plan = _build_plan_from_params(
        names=["Pat"],
        birth_dates=["1960-07-01"],
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
    for section in ("this_year", "shadow_prices", "binding_constraints", "roth_conversions",
                    "tax_brackets", "account_depletion", "caveats"):
        assert section in ex

    # Conversion schedule matches the primal solution (today's dollars).
    sched_total = ex["roth_conversions"]["total_converted_today"]
    x_today = float((plan.x_in / plan.gamma_n[: plan.N_n]).sum())
    assert sched_total == pytest.approx(x_today, rel=1e-3)

    # The $50k nominal cap must bind in year 1 and be reported.
    binding = ex["roth_conversions"].get("cap_binding_years", [])
    assert any(b["year"] == int(plan.year_n[0]) for b in binding)
    # Relaxing an upper bound can never hurt: cap values must be non-negative.
    assert all(b["value_per_dollar_of_extra_cap_today"] >= 0 for b in binding)

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
        names=["Q"], birth_dates=["1965-07-01"], life_expectancy=[85], state=None,
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
            birth_dates=["1960-07-01"],
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


@pytest.mark.toml
def test_this_year_section_leads_and_matches_primal():
    plan = _solved_plan()
    ex = build_explanation(plan)
    ty = ex["this_year"]
    assert ty["year"] == int(plan.year_n[0])

    # this_year comes before the multi-year sections so the narration leads with it.
    keys = list(ex.keys())
    assert keys.index("this_year") < keys.index("shadow_prices")

    # Actions match the primal solution (year-0 nominal ~ today's dollars).
    pat = ty["actions"]["per_person"][0]
    assert pat["person"] == "Pat"
    assert pat["roth_conversion"] == pytest.approx(float(plan.x_in[0, 0]), rel=1e-6, abs=0.01)
    assert pat["withdrawals"]["tax_deferred"] == pytest.approx(float(plan.w_ijn[0, 1, 0]), rel=1e-6, abs=0.01)
    assert ty["actions"]["net_spending"] == pytest.approx(float(plan.g_n[0]), rel=1e-6, abs=0.01)

    # Threshold proximity reports the NIIT headroom for a single filer.
    niit = ty["threshold_proximity"]["niit"]
    assert niit["threshold"] == 200_000.0
    assert niit["headroom"] == pytest.approx(200_000.0 - float(plan.MAGI_n[0]), abs=1.0)

    # A dollar now is worth more than a dollar of lifetime spending.
    assert ty["marginal_values"]["value_of_extra_dollar_now"] > 1.0


@pytest.mark.toml
def test_explanation_validates_against_schema():
    plan = _solved_plan(maxRothConversion=50_000, minTaxableBalance=[150_000])
    ex = build_explanation(plan)
    assert ex["schema_version"] == SCHEMA_VERSION
    model = PlanExplanation.model_validate(ex)  # round-trips without error
    assert model.this_year.year == int(plan.year_n[0])
    # Registry-added shadow-price families survive the schema round-trip (extra="allow"):
    # taxable_balance_floor is not a typed field, so it rides through model_extra.
    assert "taxable_balance_floor" in ex["shadow_prices"]


@pytest.mark.toml
def test_taxable_balance_floor_binding():
    # A safety net high enough to bind: taxable would otherwise be drawn down early.
    plan = _solved_plan(minTaxableBalance=[150_000])
    ex = build_explanation(plan)
    floor = ex["shadow_prices"]["taxable_balance_floor"]
    assert floor["binding_bounds"]
    assert all(e["gain_per_dollar_of_relaxation_today"] > 0 for e in floor["binding_bounds"])
    # Primal consistency: the balance actually sits at the (inflation-indexed) floor.
    years = {e["year"] for e in floor["binding_bounds"]}
    n0 = int(plan.year_n[0])
    assert any(
        abs(plan.b_ijn[0, 0, y - n0] - 150_000 * plan.gamma_n[y - n0]) < 1.0 for y in years
    )


@pytest.mark.toml
def test_disallowed_conversions_priced():
    # Baseline converts (cap test above); pinning conversions to zero must surface
    # the forgone value as reduced costs on the zero-fixed x variables.
    plan = _solved_plan(noRothConversions="Pat")
    assert float(plan.x_in.sum()) < 1.0
    ex = build_explanation(plan)
    disallowed = ex["shadow_prices"]["roth_conversion_disallowed"]["binding_bounds"]
    assert disallowed
    assert all(e["value_per_dollar_if_allowed_today"] > 0 for e in disallowed)
    # Early years are where conversions are most valuable for this case.
    assert any(e["year"] == int(plan.year_n[0]) for e in disallowed)


@pytest.mark.toml
def test_explain_results_downgrades_milp_tax_modes():
    result = _run(
        explain_results(
            names=["Pat"],
            birth_dates=["1960-07-01"],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            state="CA",
            rate_method="conservative",
            bequest=400_000,
            with_medicare="optimize",
        )
    )
    data = json.loads(result)
    assert "error" not in data
    caveats = data["explanation"]["caveats"]
    assert any("withMedicare" in c and "downgraded" in c for c in caveats)
    # The loop-mode solve still produces the full explanation.
    assert "this_year" in data["explanation"]
    assert "bequest_floor" in data["explanation"]["shadow_prices"]
