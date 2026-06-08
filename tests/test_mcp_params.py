"""
Tests for run_from_params and save_case MCP tools.

Coverage:
  - _build_plan_from_params: array population, SS conversion, unit conventions,
    debts/fixed-assets DataFrame construction, edge cases
  - run_from_params: single and couple end-to-end solve (marked toml)
  - save_case: TOML + HFP round-trip (file reload via config_to_plan)

Copyright (C) 2025-2026 The Owl Authors
"""

import asyncio
import datetime
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from owlplanner.cli.cmd_serve import (
    _build_plan_from_params,
    _build_hfp_dataframes,
    run_from_params,
    save_case,
)

THISYEAR = datetime.date.today().year


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _single(**kwargs):
    """Minimal single-person _build_plan_from_params call; kwargs override defaults."""
    defaults = dict(
        names=["Martin"],
        birth_years=[1960],
        life_expectancy=[90],
        state="TX",
        taxable=[200_000],
        tax_deferred=[800_000],
        roth=[100_000],
        hsa=None,
        cost_basis=None,
        ss_monthly_pias=[2500],
        ss_ages=[67],
        pension_monthly_amounts=None,
        pension_ages=None,
        wages=None,
        contributions=None,
        big_ticket_items=None,
        debts=None,
        fixed_assets=None,
        spias=None,
        objective="maxSpending",
        rate_method="conservative",
        survivor_fraction=60.0,
        initial_allocation=[60, 40, 0, 0],
        final_allocation=[40, 60, 0, 0],
        constrain_mean=False,
    )
    defaults.update(kwargs)
    return _build_plan_from_params(**defaults)


def _couple(**kwargs):
    """Minimal couple _build_plan_from_params call; kwargs override defaults."""
    defaults = dict(
        names=["Alice", "Bob"],
        birth_years=[1963, 1961],
        life_expectancy=[90, 87],
        state="TX",
        taxable=[150_000, 150_000],
        tax_deferred=[600_000, 600_000],
        roth=[75_000, 75_000],
        hsa=None,
        cost_basis=None,
        ss_monthly_pias=[2333, 2667],
        ss_ages=[67, 67],
        pension_monthly_amounts=None,
        pension_ages=None,
        wages=None,
        contributions=None,
        big_ticket_items=None,
        debts=None,
        fixed_assets=None,
        spias=None,
        objective="maxSpending",
        rate_method="conservative",
        survivor_fraction=60.0,
        initial_allocation=[60, 40, 0, 0],
        final_allocation=[40, 60, 0, 0],
        constrain_mean=False,
    )
    defaults.update(kwargs)
    return _build_plan_from_params(**defaults)


# ---------------------------------------------------------------------------
# _build_plan_from_params — basic plan construction
# ---------------------------------------------------------------------------

def test_single_plan_creates_correctly():
    plan = _single()
    assert plan.N_i == 1
    assert plan.N_n == 25  # 2026-01 to 2050-07 (born 1960, live to 90)
    assert plan._name == "martin"


def test_couple_plan_creates_correctly():
    plan = _couple()
    assert plan.N_i == 2
    assert plan.inames == ["Alice", "Bob"]


def test_account_balances_in_dollars():
    """taxable=[200_000] means $200,000 (full dollars, not $k)."""
    plan = _single(taxable=[200_000], tax_deferred=[800_000], roth=[100_000])
    assert plan.beta_ij[0, 0] == pytest.approx(200_000)
    assert plan.beta_ij[0, 1] == pytest.approx(800_000)
    assert plan.beta_ij[0, 2] == pytest.approx(100_000)


def test_ss_monthly_pia_passed_directly():
    """Monthly PIA of 2500 is passed directly — no conversion."""
    plan = _single(ss_monthly_pias=[2500], ss_ages=[67])
    assert plan.ssecAmounts[0] == pytest.approx(2500, rel=1e-6)


def test_ss_zero_no_error():
    plan = _single(ss_monthly_pias=[0], ss_ages=[67])
    assert plan.ssecAmounts[0] == 0


def test_objective_stored():
    plan = _single(objective="maxSpending")
    assert plan.objective == "maxSpending"


def test_state_applied():
    plan_tx = _single(state="TX")
    plan_ca = _single(state="CA")
    # CA has state tax; TX does not — state is stored on plan
    assert getattr(plan_ca, "state", None) == "CA"
    assert getattr(plan_tx, "state", None) == "TX"


def test_houseLists_empty_when_no_debts_or_assets():
    plan = _single()
    # houseLists may or may not exist; if it does, both tables should be absent or empty
    debts_df = plan.houseLists.get("Debts", pd.DataFrame())
    fa_df = plan.houseLists.get("Fixed Assets", pd.DataFrame())
    assert len(debts_df) == 0
    assert len(fa_df) == 0


# ---------------------------------------------------------------------------
# _build_plan_from_params — wages
# ---------------------------------------------------------------------------

def test_wages_populate_omega_in():
    plan = _single(wages=[
        {"person": 0, "annual_amount": 90_000, "end_year": THISYEAR + 4}
    ])
    assert plan.omega_in[0, 0] == pytest.approx(90_000)
    assert plan.omega_in[0, 3] == pytest.approx(90_000)
    assert plan.omega_in[0, 4] == pytest.approx(0)


def test_wages_start_year_respected():
    plan = _single(wages=[
        {"person": 0, "annual_amount": 50_000,
         "start_year": THISYEAR + 2, "end_year": THISYEAR + 5}
    ])
    assert plan.omega_in[0, 0] == pytest.approx(0)
    assert plan.omega_in[0, 1] == pytest.approx(0)
    assert plan.omega_in[0, 2] == pytest.approx(50_000)
    assert plan.omega_in[0, 5] == pytest.approx(0)


def test_wages_multiple_streams_accumulate():
    plan = _couple(wages=[
        {"person": 0, "annual_amount": 80_000, "end_year": THISYEAR + 3},
        {"person": 1, "annual_amount": 60_000, "end_year": THISYEAR + 2},
    ])
    assert plan.omega_in[0, 0] == pytest.approx(80_000)
    assert plan.omega_in[1, 0] == pytest.approx(60_000)
    assert plan.omega_in[1, 2] == pytest.approx(0)


# ---------------------------------------------------------------------------
# _build_plan_from_params — contributions
# ---------------------------------------------------------------------------

def test_contributions_tax_deferred():
    plan = _single(contributions=[
        {"person": 0, "account": "tax_deferred", "annual_amount": 23_000,
         "end_year": THISYEAR + 3}
    ])
    assert plan.kappa_ijn[0, 1, 0] == pytest.approx(23_000)
    assert plan.kappa_ijn[0, 1, 2] == pytest.approx(23_000)
    assert plan.kappa_ijn[0, 1, 3] == pytest.approx(0)


def test_contributions_roth():
    plan = _single(contributions=[
        {"person": 0, "account": "roth", "annual_amount": 7000,
         "end_year": THISYEAR + 2}
    ])
    assert plan.kappa_ijn[0, 2, 0] == pytest.approx(7000)
    assert plan.kappa_ijn[0, 2, 2] == pytest.approx(0)


def test_contributions_per_person():
    plan = _couple(contributions=[
        {"person": 0, "account": "tax_deferred", "annual_amount": 23_000, "end_year": THISYEAR + 2},
        {"person": 1, "account": "roth",          "annual_amount":  7000, "end_year": THISYEAR + 2},
    ])
    assert plan.kappa_ijn[0, 1, 0] == pytest.approx(23_000)
    assert plan.kappa_ijn[1, 2, 0] == pytest.approx(7000)
    assert plan.kappa_ijn[1, 1, 0] == pytest.approx(0)


# ---------------------------------------------------------------------------
# _build_plan_from_params — big-ticket items
# ---------------------------------------------------------------------------

def test_big_ticket_items_populate_lambda_in():
    plan = _single(big_ticket_items=[
        {"person": 0, "annual_amount": 15_000,
         "start_year": THISYEAR, "end_year": THISYEAR + 3}
    ])
    assert plan.Lambda_in[0, 0] == pytest.approx(15_000)
    assert plan.Lambda_in[0, 2] == pytest.approx(15_000)
    assert plan.Lambda_in[0, 3] == pytest.approx(0)


def test_big_ticket_items_single_year():
    plan = _single(big_ticket_items=[
        {"person": 0, "annual_amount": 60_000,
         "start_year": THISYEAR + 5, "end_year": THISYEAR + 6}
    ])
    assert plan.Lambda_in[0, 4] == pytest.approx(0)
    assert plan.Lambda_in[0, 5] == pytest.approx(60_000)
    assert plan.Lambda_in[0, 6] == pytest.approx(0)


# ---------------------------------------------------------------------------
# _build_plan_from_params — debts
# ---------------------------------------------------------------------------

def test_debts_dataframe_created():
    plan = _single(debts=[
        {"label": "mortgage", "type": "mortgage",
         "balance": 350_000, "rate": 3.5, "years_remaining": 20}
    ])
    df = plan.houseLists["Debts"]
    assert len(df) == 1
    assert df["type"].iloc[0] == "mortgage"
    assert df["amount"].iloc[0] == pytest.approx(350_000)
    assert df["rate"].iloc[0] == pytest.approx(3.5)
    assert df["term"].iloc[0] == 20
    assert df["year"].iloc[0] == THISYEAR


def test_debts_multiple():
    plan = _single(debts=[
        {"label": "mortgage", "type": "mortgage", "balance": 300_000, "rate": 3.5, "years_remaining": 20},
        {"label": "car",      "type": "loan",     "balance":  25_000, "rate": 6.9, "years_remaining":  5},
    ])
    assert len(plan.houseLists["Debts"]) == 2


def test_debts_default_type_is_loan():
    plan = _single(debts=[
        {"label": "personal", "balance": 10_000, "rate": 5.0, "years_remaining": 3}
    ])
    assert plan.houseLists["Debts"]["type"].iloc[0] == "loan"


# ---------------------------------------------------------------------------
# _build_plan_from_params — fixed assets
# ---------------------------------------------------------------------------

def test_fixed_assets_residence():
    sell_yr = THISYEAR + 10
    plan = _single(fixed_assets=[
        {"label": "house", "type": "residence", "value": 800_000, "basis": 400_000,
         "rate": 0.0, "sell_year": sell_yr, "commission": 3.0}
    ])
    df = plan.houseLists["Fixed Assets"]
    assert len(df) == 1
    assert df["type"].iloc[0] == "residence"
    assert df["value"].iloc[0] == pytest.approx(800_000)
    assert df["basis"].iloc[0] == pytest.approx(400_000)
    assert df["yod"].iloc[0] == sell_yr
    assert df["commission"].iloc[0] == pytest.approx(3.0)


def test_fixed_assets_sell_year_zero_sentinel():
    """sell_year=0 means end of plan; passed through as-is to fixedassets module."""
    plan = _single(fixed_assets=[
        {"label": "house", "type": "residence", "value": 500_000, "basis": 200_000,
         "sell_year": 0}
    ])
    assert plan.houseLists["Fixed Assets"]["yod"].iloc[0] == 0


def test_fixed_assets_negative_sell_year():
    """sell_year=-1 means one year before end of plan."""
    plan = _single(fixed_assets=[
        {"label": "brokerage", "type": "stocks", "value": 100_000, "basis": 60_000,
         "sell_year": -1}
    ])
    assert plan.houseLists["Fixed Assets"]["yod"].iloc[0] == -1


def test_fixed_assets_default_commission_zero():
    plan = _single(fixed_assets=[
        {"label": "stocks", "type": "stocks", "value": 50_000, "basis": 30_000,
         "sell_year": THISYEAR + 5}
    ])
    assert plan.houseLists["Fixed Assets"]["commission"].iloc[0] == pytest.approx(0.0)


def test_fixed_assets_multiple():
    plan = _single(fixed_assets=[
        {"label": "house",  "type": "residence", "value": 800_000, "basis": 400_000, "sell_year": THISYEAR + 10},
        {"label": "rental", "type": "real estate", "value": 300_000, "basis": 200_000, "sell_year": THISYEAR + 5},
    ])
    assert len(plan.houseLists["Fixed Assets"]) == 2


# ---------------------------------------------------------------------------
# _build_plan_from_params — SPIAs
# ---------------------------------------------------------------------------

def test_spia_single_registered():
    plan = _single(spias=[
        {"person": 0, "buy_year": THISYEAR, "premium": 200_000, "monthly_income": 1_100}
    ])
    assert len(plan._spia_list) == 1
    s = plan._spia_list[0]
    assert s["individual"] == 0
    assert s["monthly_income"] == pytest.approx(1_100)
    assert s["indexed"] is False
    assert s["survivor_fraction"] == pytest.approx(0.0)


def test_spia_premium_deducted_from_tax_deferred():
    plan = _single(spias=[
        {"person": 0, "buy_year": THISYEAR, "premium": 150_000, "monthly_income": 900}
    ])
    assert plan.spia_premiums_in[0, 0] == pytest.approx(150_000)


def test_spia_indexed_flag():
    plan = _single(spias=[
        {"person": 0, "buy_year": THISYEAR, "premium": 100_000,
         "monthly_income": 600, "indexed": True}
    ])
    assert plan._spia_list[0]["indexed"] is True


def test_spia_joint_survivor():
    plan = _couple(spias=[
        {"person": 0, "buy_year": THISYEAR, "premium": 200_000,
         "monthly_income": 1_100, "survivor_fraction": 0.5}
    ])
    assert plan._spia_list[0]["survivor_fraction"] == pytest.approx(0.5)


def test_spia_already_purchased_no_premium():
    """buy_year before plan start → premium ignored (n_buy < 0), income starts at year 0."""
    plan = _single(spias=[
        {"person": 0, "buy_year": THISYEAR - 3, "premium": 0, "monthly_income": 800}
    ])
    assert len(plan._spia_list) == 1
    assert plan.spia_premiums_in[0, :].sum() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _build_hfp_dataframes
# ---------------------------------------------------------------------------

def test_build_hfp_dataframes_sheets():
    plan = _couple(
        wages=[{"person": 0, "annual_amount": 80_000, "end_year": THISYEAR + 3}],
        contributions=[{"person": 1, "account": "roth", "annual_amount": 7000, "end_year": THISYEAR + 2}],
        debts=[{"label": "mortgage", "type": "mortgage", "balance": 300_000,
                "rate": 3.5, "years_remaining": 20}],
        fixed_assets=[{"label": "house", "type": "residence", "value": 700_000,
                       "basis": 350_000, "sell_year": THISYEAR + 8}],
    )
    tl, hl = _build_hfp_dataframes(plan)
    assert "Alice" in tl
    assert "Bob" in tl
    assert "Debts" in hl
    assert "Fixed Assets" in hl


def test_build_hfp_dataframes_wages_roundtrip():
    plan = _single(wages=[{"person": 0, "annual_amount": 90_000, "end_year": THISYEAR + 4}])
    tl, _ = _build_hfp_dataframes(plan)
    df = tl["Martin"]
    # Row 5 = THISYEAR (offset 5 past the 5 preamble years)
    assert df["anticipated wages"].iloc[5] == pytest.approx(90_000)
    assert df["anticipated wages"].iloc[8] == pytest.approx(90_000)
    assert df["anticipated wages"].iloc[9] == pytest.approx(0)


def test_build_hfp_dataframes_year_column():
    plan = _single()
    tl, _ = _build_hfp_dataframes(plan)
    df = tl["Martin"]
    assert df["year"].iloc[0] == THISYEAR - 5
    assert df["year"].iloc[5] == THISYEAR


# ---------------------------------------------------------------------------
# save_case — TOML + HFP round-trip
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved_single(tmp_path_factory):
    out = str(tmp_path_factory.mktemp("single"))
    save_case(
        names=["Martin"],
        birth_years=[1960],
        life_expectancy=[90],
        taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
        ss_monthly_pias=[2500], ss_ages=[67],
        wages=[{"person": 0, "annual_amount": 90_000, "end_year": THISYEAR + 4}],
        contributions=[{"person": 0, "account": "tax_deferred",
                        "annual_amount": 23_000, "end_year": THISYEAR + 4}],
        state="TX",
        output_dir=out,
    )
    return Path(out)


@pytest.fixture(scope="module")
def saved_couple(tmp_path_factory):
    out = str(tmp_path_factory.mktemp("couple"))
    save_case(
        names=["Alice", "Bob"],
        birth_years=[1963, 1961],
        life_expectancy=[90, 87],
        taxable=[150_000, 150_000], tax_deferred=[600_000, 600_000], roth=[75_000, 75_000],
        ss_monthly_pias=[2333, 2667], ss_ages=[67, 67],
        wages=[{"person": 0, "annual_amount": 90_000, "end_year": THISYEAR + 4}],
        contributions=[{"person": 1, "account": "roth", "annual_amount": 7000,
                        "end_year": THISYEAR + 3}],
        debts=[{"label": "mortgage", "type": "mortgage",
                "balance": 350_000, "rate": 3.5, "years_remaining": 20}],
        fixed_assets=[{"label": "house", "type": "residence", "value": 800_000,
                       "basis": 400_000, "rate": 0.0, "sell_year": THISYEAR + 10,
                       "commission": 3.0}],
        state="TX",
        output_dir=out,
    )
    return Path(out)


def test_save_case_creates_files(saved_single):
    assert (saved_single / "Case_martin.toml").exists()
    assert (saved_single / "HFP_martin.xlsx").exists()


def test_save_case_couple_creates_files(saved_couple):
    assert (saved_couple / "Case_alice+bob.toml").exists()
    assert (saved_couple / "HFP_alice+bob.xlsx").exists()


def test_save_case_hfp_has_correct_sheets(saved_couple):
    xl = pd.ExcelFile(saved_couple / "HFP_alice+bob.xlsx")
    assert "Alice" in xl.sheet_names
    assert "Bob" in xl.sheet_names
    assert "Debts" in xl.sheet_names
    assert "Fixed Assets" in xl.sheet_names


def test_save_case_returns_json():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        result = save_case(
            names=["Martin"], birth_years=[1960], life_expectancy=[88],
            taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
            ss_monthly_pias=[2500], ss_ages=[67],
            output_dir=td,
        )
        data = json.loads(result)
        assert "toml_file" in data
        assert "hfp_file" in data
        assert data["case_name"] == "martin"


def test_save_case_custom_name():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        result = save_case(
            names=["Martin"], birth_years=[1960], life_expectancy=[88],
            taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
            output_dir=td, case_name="test_custom",
        )
        data = json.loads(result)
        assert data["case_name"] == "test_custom"
        assert Path(data["toml_file"]).exists()


@pytest.fixture(scope="module")
def reloaded_single(saved_single):
    from owlplanner.config import load_toml, config_to_plan
    diconf, dirname, _ = load_toml(str(saved_single / "Case_martin.toml"))
    return config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=True)


@pytest.fixture(scope="module")
def reloaded_couple(saved_couple):
    from owlplanner.config import load_toml, config_to_plan
    diconf, dirname, _ = load_toml(str(saved_couple / "Case_alice+bob.toml"))
    return config_to_plan(diconf, dirname, verbose=False, logstreams=[sys.stderr], loadHFP=True)


def test_roundtrip_N_n(reloaded_single):
    assert reloaded_single.N_n == 25  # 1960 + 90 - 2026 + 1


def test_roundtrip_wages(reloaded_single):
    assert reloaded_single.omega_in[0, 0] == pytest.approx(90_000)
    assert reloaded_single.omega_in[0, 3] == pytest.approx(90_000)
    assert reloaded_single.omega_in[0, 4] == pytest.approx(0)


def test_roundtrip_contributions(reloaded_single):
    assert reloaded_single.kappa_ijn[0, 1, 0] == pytest.approx(23_000)
    assert reloaded_single.kappa_ijn[0, 1, 4] == pytest.approx(0)


def test_roundtrip_couple_wages(reloaded_couple):
    assert reloaded_couple.omega_in[0, 0] == pytest.approx(90_000)
    assert reloaded_couple.omega_in[1, 0] == pytest.approx(0)


def test_roundtrip_couple_roth_contributions(reloaded_couple):
    assert reloaded_couple.kappa_ijn[1, 2, 0] == pytest.approx(7000)
    assert reloaded_couple.kappa_ijn[1, 2, 3] == pytest.approx(0)


def test_roundtrip_debts_present(reloaded_couple):
    df = reloaded_couple.houseLists["Debts"]
    assert len(df) == 1
    assert df["amount"].iloc[0] == pytest.approx(350_000)
    assert df["rate"].iloc[0] == pytest.approx(3.5)


def test_roundtrip_fixed_assets_present(reloaded_couple):
    df = reloaded_couple.houseLists["Fixed Assets"]
    assert len(df) == 1
    assert df["type"].iloc[0] == "residence"
    assert df["value"].iloc[0] == pytest.approx(800_000)
    assert df["yod"].iloc[0] == THISYEAR + 10


def test_roundtrip_ss_amounts(reloaded_couple):
    # TOML rounds to nearest dollar ($1 tolerance)
    assert reloaded_couple.ssecAmounts[0] == pytest.approx(2_333, abs=1)
    assert reloaded_couple.ssecAmounts[1] == pytest.approx(2_667, abs=1)


# ---------------------------------------------------------------------------
# run_from_params — end-to-end solves
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


@pytest.mark.toml
def test_run_from_params_single_solves():
    result = _run(run_from_params(
        names=["Martin"], birth_years=[1960], life_expectancy=[88],
        taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
        ss_monthly_pias=[2500], ss_ages=[67],
        state="TX", rate_method="conservative",
    ))
    data = json.loads(result)
    assert data["status"] == "solved"
    assert data["spending_year1_nominal"] > 0


@pytest.mark.toml
def test_run_from_params_couple_solves():
    result = _run(run_from_params(
        names=["Alice", "Bob"],
        birth_years=[1963, 1961],
        life_expectancy=[90, 87],
        taxable=[150_000, 150_000], tax_deferred=[600_000, 600_000], roth=[75_000, 75_000],
        ss_monthly_pias=[2333, 2667], ss_ages=[67, 67],
        state="TX", rate_method="conservative",
    ))
    data = json.loads(result)
    assert data["status"] == "solved"
    assert data["spending_year1_nominal"] > 0


@pytest.mark.toml
def test_run_from_params_with_wages_and_debt():
    result = _run(run_from_params(
        names=["Martin"], birth_years=[1960], life_expectancy=[88],
        taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
        ss_monthly_pias=[2500], ss_ages=[67],
        wages=[{"person": 0, "annual_amount": 80_000, "end_year": THISYEAR + 3}],
        debts=[{"label": "mortgage", "type": "mortgage",
                "balance": 200_000, "rate": 3.5, "years_remaining": 15}],
        state="TX", rate_method="conservative",
    ))
    data = json.loads(result)
    assert data["status"] == "solved"


@pytest.mark.toml
def test_run_from_params_with_fixed_asset():
    result = _run(run_from_params(
        names=["Martin"], birth_years=[1960], life_expectancy=[88],
        taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
        ss_monthly_pias=[2500], ss_ages=[67],
        fixed_assets=[{"label": "house", "type": "residence",
                       "value": 600_000, "basis": 300_000,
                       "sell_year": THISYEAR + 8, "commission": 3.0}],
        state="TX", rate_method="conservative",
    ))
    data = json.loads(result)
    assert data["status"] == "solved"


@pytest.mark.toml
def test_run_from_params_json_structure():
    result = _run(run_from_params(
        names=["Martin"], birth_years=[1960], life_expectancy=[88],
        taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
        ss_monthly_pias=[2500], ss_ages=[67],
        state="TX", rate_method="conservative",
    ))
    data = json.loads(result)
    for key in ("status", "case_name", "objective", "summary",
                "by_year", "time_horizon_years"):
        assert key in data, f"Missing key: {key}"
    assert len(data["by_year"]) == data["time_horizon_years"]


@pytest.mark.toml
def test_run_from_params_error_returns_json():
    """Bad parameters return a JSON error, not an exception."""
    result = _run(run_from_params(
        names=["Martin"], birth_years=[1960], life_expectancy=[88],
        taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
        # Pass a bogus rate method to trigger an error
        ss_monthly_pias=[2500], ss_ages=[67],
        rate_method="nonexistent_rate_method_xyz",
    ))
    data = json.loads(result)
    assert "error" in data


@pytest.mark.toml
def test_run_from_params_max_bequest_net_spending_dollars():
    """net_spending=60_000 (full $) is interpreted as $60k/yr (not $60M/yr) with units='1'."""
    result = _run(run_from_params(
        names=["Martin"], birth_years=[1960], life_expectancy=[88],
        taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
        ss_monthly_pias=[2500], ss_ages=[67],
        state="TX", rate_method="conservative",
        objective="maxBequest", net_spending=60_000,
    ))
    data = json.loads(result)
    assert data["status"] == "solved"
    # With net_spending=60_000 ($/yr), spending in year 1 should be ~$60k
    assert data["by_year"][0]["spending"] == pytest.approx(60_000, rel=0.05)


@pytest.mark.toml
def test_run_from_params_min_taxable_balance_full_dollars():
    """min_taxable_balance=[20_000] keeps $20k safety net; units='1' so no $k scaling."""
    no_floor = _run(run_from_params(
        names=["Martin"], birth_years=[1960], life_expectancy=[88],
        taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
        ss_monthly_pias=[2500], ss_ages=[67],
        state="TX", rate_method="conservative",
    ))
    with_floor = _run(run_from_params(
        names=["Martin"], birth_years=[1960], life_expectancy=[88],
        taxable=[200_000], tax_deferred=[800_000], roth=[100_000],
        ss_monthly_pias=[2500], ss_ages=[67],
        state="TX", rate_method="conservative",
        min_taxable_balance=[20_000],
    ))
    d_no = json.loads(no_floor)
    d_fl = json.loads(with_floor)
    assert d_no["status"] == "solved"
    assert d_fl["status"] == "solved"
    # Imposing a floor constrains the optimizer, so spending can only stay equal or decrease
    assert d_fl["summary"]["spending_basis_today_dollars"] <= d_no["summary"]["spending_basis_today_dollars"] + 1
