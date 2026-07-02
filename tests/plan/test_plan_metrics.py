"""
Tests for plan_metrics(), plan_to_dict(), and BaseRateModel abstract enforcement.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import json
import numpy as np
import pytest

import owlplanner as owl
from owlplanner.export import plan_metrics, METRICS_COLUMN_MAP
from owlplanner.cli.formatters import plan_to_dict, plan_to_json


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def solved_single():
    """Minimal solved single-person plan."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [85], "test_single")
    p.setAccountBalances(taxable=[100], taxDeferred=[500], taxFree=[50])
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("conservative")
    p.solve("maxSpending", {"withMedicare": "None", "withSCLoop": False})
    assert p.caseStatus == "solved"
    return p


@pytest.fixture(scope="module")
def solved_couple():
    """Minimal solved couple plan."""
    p = owl.Plan(["Alice", "Bob"], ["1960-03-10", "1958-07-22"], [88, 85], "test_couple")
    p.setAccountBalances(taxable=[100, 80], taxDeferred=[500, 400], taxFree=[50, 40])
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]], [[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("conservative")
    p.solve("maxSpending", {"withMedicare": "None", "withSCLoop": False})
    assert p.caseStatus == "solved"
    return p


# ---------------------------------------------------------------------------
# plan_metrics() — key presence
# ---------------------------------------------------------------------------

EXPECTED_KEYS = [
    "spending_basis",
    "spending_year1",
    "effective_tax_rate",
    "total_spending_today",
    "total_spending_nominal",
    "total_fixed_income_today",
    "total_fixed_income_nominal",
    "ss_income_today",
    "ss_income_nominal",
    "pension_income_today",
    "pension_income_nominal",
    "roth_conversions_today",
    "roth_conversions_nominal",
    "federal_income_tax_today",
    "federal_income_tax_nominal",
    "ltcg_tax_today",
    "ltcg_tax_nominal",
    "niit_today",
    "niit_nominal",
    "state_tax_today",
    "state_tax_nominal",
    "medicare_today",
    "medicare_nominal",
    "aca_today",
    "aca_nominal",
    "debt_payments_today",
    "debt_payments_nominal",
    "heirs_tax_liability_nominal",
    "final_bequest_today",
    "final_bequest_nominal",
    "remaining_debt_balance",
    "time_horizon_years",
    "inflation_factor",
]


def test_plan_metrics_all_keys_present(solved_single):
    m = plan_metrics(solved_single)
    for key in EXPECTED_KEYS:
        assert key in m, f"Missing key: {key}"


def test_plan_metrics_all_floats(solved_single):
    m = plan_metrics(solved_single)
    for k, v in m.items():
        assert isinstance(v, (int, float)), f"Non-numeric value for {k}: {type(v)}"


# ---------------------------------------------------------------------------
# plan_metrics() — value correctness
# ---------------------------------------------------------------------------


def test_spending_basis_matches_plan(solved_single):
    m = plan_metrics(solved_single)
    expected = float(solved_single.g_n[0] / solved_single.xi_n[0])
    assert m["spending_basis"] == pytest.approx(expected, rel=1e-6)


def test_spending_year1_matches_plan(solved_single):
    m = plan_metrics(solved_single)
    assert m["spending_year1"] == pytest.approx(float(solved_single.g_n[0]), rel=1e-6)


def test_total_spending_nominal_matches_sum(solved_single):
    m = plan_metrics(solved_single)
    p = solved_single
    expected = float(np.sum(p.g_n[: p.N_n]))
    assert m["total_spending_nominal"] == pytest.approx(expected, rel=1e-6)


def test_today_less_than_nominal_for_spending(solved_single):
    """today's $ < nominal $ for positive-inflation plans."""
    m = plan_metrics(solved_single)
    assert m["total_spending_today"] < m["total_spending_nominal"]


def test_time_horizon_years_matches_plan(solved_single):
    m = plan_metrics(solved_single)
    assert m["time_horizon_years"] == solved_single.N_n


def test_effective_tax_rate_in_range(solved_single):
    m = plan_metrics(solved_single)
    assert 0.0 <= m["effective_tax_rate"] <= 1.0


def test_inflation_factor_greater_than_one(solved_single):
    """Cumulative inflation over a multi-year plan should exceed 1."""
    m = plan_metrics(solved_single)
    assert m["inflation_factor"] > 1.0


def test_plan_metrics_couple(solved_couple):
    """plan_metrics works for a couple plan."""
    m = plan_metrics(solved_couple)
    for key in EXPECTED_KEYS:
        assert key in m


# ---------------------------------------------------------------------------
# METRICS_COLUMN_MAP
# ---------------------------------------------------------------------------


def test_metrics_column_map_keys_subset_of_plan_metrics(solved_single):
    m = plan_metrics(solved_single)
    for key, (_col_label, fmt) in METRICS_COLUMN_MAP.items():
        if fmt != "usd_skip":
            assert key in m, f"METRICS_COLUMN_MAP key '{key}' not in plan_metrics()"


def test_metrics_column_map_fmt_values():
    valid_fmts = {"usd", "pct", "usd_skip"}
    for key, (_col_label, fmt) in METRICS_COLUMN_MAP.items():
        assert fmt in valid_fmts, f"Unknown fmt '{fmt}' for key '{key}'"


# ---------------------------------------------------------------------------
# plan_to_dict() / plan_to_json()
# ---------------------------------------------------------------------------


def test_plan_to_dict_top_level_keys(solved_single):
    d = plan_to_dict(solved_single)
    for key in (
        "status",
        "case_name",
        "objective",
        "summary",
        "by_year",
        "individuals",
        "start_year",
        "end_year",
        "time_horizon_years",
    ):
        assert key in d, f"Missing top-level key: {key}"


def test_plan_to_dict_status_solved(solved_single):
    d = plan_to_dict(solved_single)
    assert d["status"] == "solved"


def test_plan_to_dict_by_year_length(solved_single):
    d = plan_to_dict(solved_single)
    assert len(d["by_year"]) == solved_single.N_n


def test_plan_to_dict_by_year_fields(solved_single):
    d = plan_to_dict(solved_single)
    row = d["by_year"][0]
    for field in ("year", "ages", "spending", "federal_income_tax", "roth_conversions", "portfolio_total"):
        assert field in row, f"Missing by_year field: {field}"


def test_plan_to_dict_summary_monetary_are_ints(solved_single):
    d = plan_to_dict(solved_single)
    s = d["summary"]
    for k, v in s.items():
        if "rate" not in k and "factor" not in k and "years" not in k:
            assert isinstance(v, int), f"Expected int for summary[{k}], got {type(v)}"


def test_plan_to_json_is_valid_json(solved_single):
    s = plan_to_json(solved_single)
    parsed = json.loads(s)
    assert parsed["status"] == "solved"


def test_plan_to_dict_raises_if_not_solved():
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "unsolved")
    p.setAccountBalances(taxable=[100], taxDeferred=[500], taxFree=[50])
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("conservative")
    with pytest.raises(ValueError, match="not solved"):
        plan_to_dict(p)


# ---------------------------------------------------------------------------
# BaseRateModel abstract enforcement
# ---------------------------------------------------------------------------


def test_missing_model_name_raises():
    from owlplanner.rate_models.base import BaseRateModel

    class BadPlugin(BaseRateModel):
        description = "Has description but no model_name."

        def generate(self, N):
            return np.zeros((N, 4))

    with pytest.raises(TypeError, match="model_name"):
        BadPlugin({})


def test_missing_description_raises():
    from owlplanner.rate_models.base import BaseRateModel

    class BadPlugin(BaseRateModel):
        model_name = "bad"

        def generate(self, N):
            return np.zeros((N, 4))

    with pytest.raises(TypeError, match="description"):
        BadPlugin({})


def test_complete_plugin_instantiates():
    from owlplanner.rate_models.base import BaseRateModel

    class GoodPlugin(BaseRateModel):
        model_name = "good"
        description = "Complete plugin."

        def generate(self, N):
            return np.zeros((N, 4))

    plugin = GoodPlugin({})
    assert plugin.model_name == "good"
    assert plugin.description == "Complete plugin."
