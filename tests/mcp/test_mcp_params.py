"""
Tests for run_from_params and save_case MCP tools.

Coverage:
  - _build_plan_from_params: array population, SS conversion, unit conventions,
    debts/fixed-assets DataFrame construction, edge cases
  - run_from_params: single and couple end-to-end solve (marked toml)
  - save_case: TOML + HFP round-trip (file reload via config_to_plan)

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
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
    _run_from_params_blocking,
    _ss_ages_opt,
    _swap_roth_converters_value,
    _build_distribution_json,
    convert_ss_benefit,
    list_contribution_limits,
    run_from_params,
    save_case,
    run_historical,
    run_monte_carlo,
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


# ---------------------------------------------------------------------------
# convert_ss_benefit
# ---------------------------------------------------------------------------


def test_convert_ss_benefit_pia_to_actual_early_claim():
    """Born 1961 (FRA=67), claiming at 65 reduces the PIA by the early-claim factor."""
    from owlplanner.socialsecurity import getFRAs, getSelfFactor

    result = json.loads(convert_ss_benefit(birth_year=1961, claiming_age=65, pia=3231.02))
    fra = float(getFRAs([1961], [7], [1])[0])
    expected_factor = getSelfFactor(fra, 65, True)  # default birth_day=1 -> bornOnFirst=True
    assert result["fra"] == pytest.approx(67.0)
    assert result["factor"] == pytest.approx(expected_factor, abs=1e-4)
    assert result["actual_benefit"] == pytest.approx(3231.02 * expected_factor, rel=1e-4)


def test_convert_ss_benefit_birth_day_two_not_treated_as_first():
    """Born on the 2nd does NOT get the +1/12 SSA-age bump (only born-on-1st does, per
    socialsecurity._ssa_age / compute_social_security_benefits' bornOnFirst rule)."""
    from owlplanner.socialsecurity import getFRAs, getSelfFactor

    result = json.loads(convert_ss_benefit(birth_year=1961, claiming_age=65, pia=3231.02, birth_day=2))
    fra = float(getFRAs([1961], [7], [2])[0])
    expected_factor = getSelfFactor(fra, 65, False)  # birth_day=2 -> bornOnFirst=False
    assert result["factor"] == pytest.approx(expected_factor, abs=1e-4)


def test_convert_ss_benefit_actual_to_pia_round_trip():
    """actual_benefit -> pia is the inverse of pia -> actual_benefit."""
    forward = json.loads(convert_ss_benefit(birth_year=1961, claiming_age=65, pia=3231.02))
    back = json.loads(convert_ss_benefit(birth_year=1961, claiming_age=65, actual_benefit=forward["actual_benefit"]))
    assert back["pia"] == pytest.approx(3231.02, rel=1e-3)


def test_convert_ss_benefit_at_fra_factor_near_one():
    """Claiming at conventional age == FRA gives a factor very close to 1.0."""
    result = json.loads(convert_ss_benefit(birth_year=1961, claiming_age=67, pia=2500))
    assert result["factor"] == pytest.approx(1.0, abs=0.01)
    assert result["actual_benefit"] == pytest.approx(2500, rel=0.01)


def test_convert_ss_benefit_delayed_claim_increases_benefit():
    """Delaying past FRA to 70 increases the benefit above the PIA (~8%/yr delayed credit)."""
    result = json.loads(convert_ss_benefit(birth_year=1961, claiming_age=70, pia=2500))
    assert result["factor"] > 1.2
    assert result["actual_benefit"] > 2500


def test_convert_ss_benefit_requires_exactly_one_input():
    assert "error" in json.loads(convert_ss_benefit(birth_year=1961, claiming_age=65))
    assert "error" in json.loads(convert_ss_benefit(birth_year=1961, claiming_age=65, pia=2500, actual_benefit=2500))


def test_convert_ss_benefit_claiming_age_out_of_range():
    result = json.loads(convert_ss_benefit(birth_year=1961, claiming_age=61, pia=2500))
    assert "error" in result


# ---------------------------------------------------------------------------
# list_contribution_limits
# ---------------------------------------------------------------------------


def test_list_contribution_limits_single_under_50():
    result = json.loads(list_contribution_limits(birth_years=[1985], tax_year=2026))
    person = result["persons"][0]
    assert person["birth_year"] == 1985
    assert person["age_in_tax_year"] == 41
    assert person["elective_deferral"] == {"base": 24_500, "catchup": 0, "max": 24_500}
    assert person["ira"] == {"base": 7_500, "catchup": 0, "max": 7_500}
    assert person["hsa_self_only"]["max"] == 4_400
    assert person["hsa_family"]["max"] == 8_750


def test_list_contribution_limits_couple_mixed_catchup_tiers():
    """One spouse in the 60-63 super catch-up window, the other in the 50-59 tier."""
    result = json.loads(list_contribution_limits(birth_years=[1965, 1972], tax_year=2026))
    p60_63, p50_59 = result["persons"]
    assert p60_63["age_in_tax_year"] == 61
    assert p60_63["elective_deferral"]["catchup"] == 11_250
    assert p50_59["age_in_tax_year"] == 54
    assert p50_59["elective_deferral"]["catchup"] == 8_000


def test_list_contribution_limits_default_tax_year_is_current_year():
    result = json.loads(list_contribution_limits(birth_years=[1970]))
    assert result["persons"][0]["tax_year"] == THISYEAR


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
    plan = _single(wages=[{"person": 0, "annual_amount": 90_000, "end_year": THISYEAR + 4}])
    assert plan.omega_in[0, 0] == pytest.approx(90_000)
    assert plan.omega_in[0, 3] == pytest.approx(90_000)
    assert plan.omega_in[0, 4] == pytest.approx(0)


def test_wages_start_year_respected():
    plan = _single(wages=[{"person": 0, "annual_amount": 50_000, "start_year": THISYEAR + 2, "end_year": THISYEAR + 5}])
    assert plan.omega_in[0, 0] == pytest.approx(0)
    assert plan.omega_in[0, 1] == pytest.approx(0)
    assert plan.omega_in[0, 2] == pytest.approx(50_000)
    assert plan.omega_in[0, 5] == pytest.approx(0)


def test_wages_invalid_person_raises():
    with pytest.raises(ValueError, match="person index"):
        _single(wages=[{"person": 5, "annual_amount": 50_000, "end_year": THISYEAR + 2}])


def test_wages_multiple_streams_accumulate():
    plan = _couple(
        wages=[
            {"person": 0, "annual_amount": 80_000, "end_year": THISYEAR + 3},
            {"person": 1, "annual_amount": 60_000, "end_year": THISYEAR + 2},
        ]
    )
    assert plan.omega_in[0, 0] == pytest.approx(80_000)
    assert plan.omega_in[1, 0] == pytest.approx(60_000)
    assert plan.omega_in[1, 2] == pytest.approx(0)


# ---------------------------------------------------------------------------
# _build_plan_from_params — contributions
# ---------------------------------------------------------------------------


def test_contributions_tax_deferred():
    plan = _single(
        contributions=[{"person": 0, "account": "tax_deferred", "annual_amount": 23_000, "end_year": THISYEAR + 3}]
    )
    assert plan.kappa_ijn[0, 1, 0] == pytest.approx(23_000)
    assert plan.kappa_ijn[0, 1, 2] == pytest.approx(23_000)
    assert plan.kappa_ijn[0, 1, 3] == pytest.approx(0)


def test_contributions_roth():
    plan = _single(contributions=[{"person": 0, "account": "roth", "annual_amount": 7000, "end_year": THISYEAR + 2}])
    assert plan.kappa_ijn[0, 2, 0] == pytest.approx(7000)
    assert plan.kappa_ijn[0, 2, 2] == pytest.approx(0)


def test_contributions_per_person():
    plan = _couple(
        contributions=[
            {"person": 0, "account": "tax_deferred", "annual_amount": 23_000, "end_year": THISYEAR + 2},
            {"person": 1, "account": "roth", "annual_amount": 7000, "end_year": THISYEAR + 2},
        ]
    )
    assert plan.kappa_ijn[0, 1, 0] == pytest.approx(23_000)
    assert plan.kappa_ijn[1, 2, 0] == pytest.approx(7000)
    assert plan.kappa_ijn[1, 1, 0] == pytest.approx(0)


# ---------------------------------------------------------------------------
# _build_plan_from_params — big-ticket items
# ---------------------------------------------------------------------------


def test_big_ticket_items_populate_lambda_in():
    plan = _single(
        big_ticket_items=[{"person": 0, "annual_amount": 15_000, "start_year": THISYEAR, "end_year": THISYEAR + 3}]
    )
    assert plan.Lambda_in[0, 0] == pytest.approx(15_000)
    assert plan.Lambda_in[0, 2] == pytest.approx(15_000)
    assert plan.Lambda_in[0, 3] == pytest.approx(0)


def test_big_ticket_items_single_year():
    plan = _single(
        big_ticket_items=[{"person": 0, "annual_amount": 60_000, "start_year": THISYEAR + 5, "end_year": THISYEAR + 6}]
    )
    assert plan.Lambda_in[0, 4] == pytest.approx(0)
    assert plan.Lambda_in[0, 5] == pytest.approx(60_000)
    assert plan.Lambda_in[0, 6] == pytest.approx(0)


# ---------------------------------------------------------------------------
# _build_plan_from_params — roth_conversions (myRothX_in overrides)
# ---------------------------------------------------------------------------


def test_roth_conversions_positive_pins_amount():
    plan = _single(roth_conversions=[{"person": 0, "year": THISYEAR, "amount": 20_000}])
    assert plan.myRothX_in[0, 0] == pytest.approx(20_000)
    assert plan.myRothX_in[0, 1] == pytest.approx(0)


def test_roth_conversions_negative_forces_zero_marker():
    """A negative amount stores the (negative) marker as-is; sign, not magnitude, matters."""
    plan = _single(roth_conversions=[{"person": 0, "year": THISYEAR + 1, "amount": -1}])
    assert plan.myRothX_in[0, 1] < 0


def test_roth_conversions_multi_person():
    plan = _couple(
        roth_conversions=[
            {"person": 0, "year": THISYEAR, "amount": 15_000},
            {"person": 1, "year": THISYEAR, "amount": -1},
        ]
    )
    assert plan.myRothX_in[0, 0] == pytest.approx(15_000)
    assert plan.myRothX_in[1, 0] < 0


def test_roth_conversions_out_of_range_year_ignored():
    """A year outside the plan horizon is silently ignored (same convention as big_ticket_items)."""
    plan = _single(roth_conversions=[{"person": 0, "year": THISYEAR - 5, "amount": 20_000}])
    assert (plan.myRothX_in[0, : plan.N_n] == 0).all()


def test_roth_conversions_invalid_person_raises():
    with pytest.raises(ValueError, match="person index"):
        _single(roth_conversions=[{"person": 5, "year": THISYEAR, "amount": 20_000}])


def test_roth_conversions_alias_fields():
    """Accepts 'value'/'start_year' aliases for 'amount'/'year' via _FIELD_ALIASES."""
    plan = _single(roth_conversions=[{"person": 0, "start_year": THISYEAR, "value": 12_000}])
    assert plan.myRothX_in[0, 0] == pytest.approx(12_000)


# ---------------------------------------------------------------------------
# _build_plan_from_params — debts
# ---------------------------------------------------------------------------


def test_debts_dataframe_created():
    plan = _single(
        debts=[{"label": "mortgage", "type": "mortgage", "balance": 350_000, "rate": 3.5, "years_remaining": 20}]
    )
    df = plan.houseLists["Debts"]
    assert len(df) == 1
    assert df["type"].iloc[0] == "mortgage"
    assert df["amount"].iloc[0] == pytest.approx(350_000)
    assert df["rate"].iloc[0] == pytest.approx(3.5)
    assert df["term"].iloc[0] == 20
    assert df["year"].iloc[0] == THISYEAR


def test_debts_multiple():
    plan = _single(
        debts=[
            {"label": "mortgage", "type": "mortgage", "balance": 300_000, "rate": 3.5, "years_remaining": 20},
            {"label": "car", "type": "loan", "balance": 25_000, "rate": 6.9, "years_remaining": 5},
        ]
    )
    assert len(plan.houseLists["Debts"]) == 2


def test_debts_default_type_is_loan():
    plan = _single(debts=[{"label": "personal", "balance": 10_000, "rate": 5.0, "years_remaining": 3}])
    assert plan.houseLists["Debts"]["type"].iloc[0] == "loan"


# ---------------------------------------------------------------------------
# _build_plan_from_params — fixed assets
# ---------------------------------------------------------------------------


def test_fixed_assets_residence():
    sell_yr = THISYEAR + 10
    plan = _single(
        fixed_assets=[
            {
                "label": "house",
                "type": "residence",
                "value": 800_000,
                "basis": 400_000,
                "rate": 0.0,
                "sell_year": sell_yr,
                "commission": 3.0,
            }
        ]
    )
    df = plan.houseLists["Fixed Assets"]
    assert len(df) == 1
    assert df["type"].iloc[0] == "residence"
    assert df["value"].iloc[0] == pytest.approx(800_000)
    assert df["basis"].iloc[0] == pytest.approx(400_000)
    assert df["yod"].iloc[0] == sell_yr
    assert df["commission"].iloc[0] == pytest.approx(3.0)


def test_fixed_assets_sell_year_zero_sentinel():
    """sell_year=0 means end of plan; passed through as-is to fixedassets module."""
    plan = _single(
        fixed_assets=[{"label": "house", "type": "residence", "value": 500_000, "basis": 200_000, "sell_year": 0}]
    )
    assert plan.houseLists["Fixed Assets"]["yod"].iloc[0] == 0


def test_fixed_assets_negative_sell_year():
    """sell_year=-1 means one year before end of plan."""
    plan = _single(
        fixed_assets=[{"label": "brokerage", "type": "stocks", "value": 100_000, "basis": 60_000, "sell_year": -1}]
    )
    assert plan.houseLists["Fixed Assets"]["yod"].iloc[0] == -1


def test_fixed_assets_default_commission_zero():
    plan = _single(
        fixed_assets=[
            {"label": "stocks", "type": "stocks", "value": 50_000, "basis": 30_000, "sell_year": THISYEAR + 5}
        ]
    )
    assert plan.houseLists["Fixed Assets"]["commission"].iloc[0] == pytest.approx(0.0)


def test_fixed_assets_multiple():
    plan = _single(
        fixed_assets=[
            {"label": "house", "type": "residence", "value": 800_000, "basis": 400_000, "sell_year": THISYEAR + 10},
            {"label": "rental", "type": "real estate", "value": 300_000, "basis": 200_000, "sell_year": THISYEAR + 5},
        ]
    )
    assert len(plan.houseLists["Fixed Assets"]) == 2


# ---------------------------------------------------------------------------
# _build_plan_from_params — SPIAs
# ---------------------------------------------------------------------------


def test_spia_single_registered():
    plan = _single(spias=[{"person": 0, "buy_year": THISYEAR, "premium": 200_000, "monthly_income": 1_100}])
    assert len(plan._spia_list) == 1
    s = plan._spia_list[0]
    assert s["individual"] == 0
    assert s["monthly_income"] == pytest.approx(1_100)
    assert s["indexed"] is False
    assert s["survivor_fraction"] == pytest.approx(0.0)


def test_spia_premium_deducted_from_tax_deferred():
    plan = _single(spias=[{"person": 0, "buy_year": THISYEAR, "premium": 150_000, "monthly_income": 900}])
    assert plan.spia_premiums_in[0, 0] == pytest.approx(150_000)


def test_spia_indexed_flag():
    plan = _single(
        spias=[{"person": 0, "buy_year": THISYEAR, "premium": 100_000, "monthly_income": 600, "indexed": True}]
    )
    assert plan._spia_list[0]["indexed"] is True


def test_spia_joint_survivor():
    plan = _couple(
        spias=[
            {"person": 0, "buy_year": THISYEAR, "premium": 200_000, "monthly_income": 1_100, "survivor_fraction": 0.5}
        ]
    )
    assert plan._spia_list[0]["survivor_fraction"] == pytest.approx(0.5)


def test_spia_already_purchased_no_premium():
    """buy_year before plan start → premium ignored (n_buy < 0), income starts at year 0."""
    plan = _single(spias=[{"person": 0, "buy_year": THISYEAR - 3, "premium": 0, "monthly_income": 800}])
    assert len(plan._spia_list) == 1
    assert plan.spia_premiums_in[0, :].sum() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _build_hfp_dataframes
# ---------------------------------------------------------------------------


def test_build_hfp_dataframes_sheets():
    plan = _couple(
        wages=[{"person": 0, "annual_amount": 80_000, "end_year": THISYEAR + 3}],
        contributions=[{"person": 1, "account": "roth", "annual_amount": 7000, "end_year": THISYEAR + 2}],
        debts=[{"label": "mortgage", "type": "mortgage", "balance": 300_000, "rate": 3.5, "years_remaining": 20}],
        fixed_assets=[
            {"label": "house", "type": "residence", "value": 700_000, "basis": 350_000, "sell_year": THISYEAR + 8}
        ],
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


def test_build_hfp_dataframes_roth_conv_roundtrip():
    plan = _single(
        roth_conversions=[
            {"person": 0, "year": THISYEAR, "amount": 20_000},
            {"person": 0, "year": THISYEAR + 1, "amount": -1},
        ]
    )
    tl, _ = _build_hfp_dataframes(plan)
    df = tl["Martin"]
    # Row 5 = THISYEAR (offset 5 past the 5 preamble years)
    assert df["Roth conv"].iloc[5] == pytest.approx(20_000)
    assert df["Roth conv"].iloc[6] < 0
    assert df["Roth conv"].iloc[7] == pytest.approx(0)


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
        taxable=[200_000],
        tax_deferred=[800_000],
        roth=[100_000],
        ss_monthly_pias=[2500],
        ss_ages=[67],
        wages=[{"person": 0, "annual_amount": 90_000, "end_year": THISYEAR + 4}],
        contributions=[{"person": 0, "account": "tax_deferred", "annual_amount": 23_000, "end_year": THISYEAR + 4}],
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
        taxable=[150_000, 150_000],
        tax_deferred=[600_000, 600_000],
        roth=[75_000, 75_000],
        ss_monthly_pias=[2333, 2667],
        ss_ages=[67, 67],
        wages=[{"person": 0, "annual_amount": 90_000, "end_year": THISYEAR + 4}],
        contributions=[{"person": 1, "account": "roth", "annual_amount": 7000, "end_year": THISYEAR + 3}],
        debts=[{"label": "mortgage", "type": "mortgage", "balance": 350_000, "rate": 3.5, "years_remaining": 20}],
        fixed_assets=[
            {
                "label": "house",
                "type": "residence",
                "value": 800_000,
                "basis": 400_000,
                "rate": 0.0,
                "sell_year": THISYEAR + 10,
                "commission": 3.0,
            }
        ],
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
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
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
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            output_dir=td,
            case_name="test_custom",
        )
        data = json.loads(result)
        assert data["case_name"] == "test_custom"
        assert Path(data["toml_file"]).exists()


# ---------------------------------------------------------------------------
# save_case — useRothConvOverrides / swapRothConverters solver options
# ---------------------------------------------------------------------------


def test_save_case_use_roth_conv_overrides_written():
    import tempfile
    from owlplanner.config import load_toml

    with tempfile.TemporaryDirectory() as td:
        result = save_case(
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            roth_conversions=[{"person": 0, "year": THISYEAR, "amount": 20_000}],
            use_roth_conv_overrides=True,
            output_dir=td,
        )
        data = json.loads(result)
        diconf, _, _ = load_toml(data["toml_file"])
        assert diconf["solver_options"]["useRothConvOverrides"] is True


def test_save_case_swap_roth_converters_first_spouse_positive():
    import tempfile
    from owlplanner.config import load_toml

    swap_year = THISYEAR + 5
    with tempfile.TemporaryDirectory() as td:
        result = save_case(
            names=["Alice", "Bob"],
            birth_years=[1963, 1961],
            life_expectancy=[90, 87],
            taxable=[150_000, 150_000],
            tax_deferred=[600_000, 600_000],
            roth=[75_000, 75_000],
            ss_monthly_pias=[2333, 2667],
            ss_ages=[67, 67],
            swap_roth_converters_first="Alice",
            swap_roth_converters_year=swap_year,
            output_dir=td,
        )
        data = json.loads(result)
        diconf, _, _ = load_toml(data["toml_file"])
        assert diconf["solver_options"]["swapRothConverters"] == swap_year


def test_save_case_swap_roth_converters_second_spouse_negative():
    import tempfile
    from owlplanner.config import load_toml

    swap_year = THISYEAR + 5
    with tempfile.TemporaryDirectory() as td:
        result = save_case(
            names=["Alice", "Bob"],
            birth_years=[1963, 1961],
            life_expectancy=[90, 87],
            taxable=[150_000, 150_000],
            tax_deferred=[600_000, 600_000],
            roth=[75_000, 75_000],
            ss_monthly_pias=[2333, 2667],
            ss_ages=[67, 67],
            swap_roth_converters_first="Bob",
            swap_roth_converters_year=swap_year,
            output_dir=td,
        )
        data = json.loads(result)
        diconf, _, _ = load_toml(data["toml_file"])
        assert diconf["solver_options"]["swapRothConverters"] == -swap_year


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
    result = _run(
        run_from_params(
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
    assert data["status"] == "solved"
    assert data["spending_year1_nominal"] > 0


@pytest.mark.toml
def test_run_from_params_couple_solves():
    result = _run(
        run_from_params(
            names=["Alice", "Bob"],
            birth_years=[1963, 1961],
            life_expectancy=[90, 87],
            taxable=[150_000, 150_000],
            tax_deferred=[600_000, 600_000],
            roth=[75_000, 75_000],
            ss_monthly_pias=[2333, 2667],
            ss_ages=[67, 67],
            state="TX",
            rate_method="conservative",
        )
    )
    data = json.loads(result)
    assert data["status"] == "solved"
    assert data["spending_year1_nominal"] > 0


@pytest.mark.toml
def test_run_from_params_with_wages_and_debt():
    result = _run(
        run_from_params(
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            wages=[{"person": 0, "annual_amount": 80_000, "end_year": THISYEAR + 3}],
            debts=[{"label": "mortgage", "type": "mortgage", "balance": 200_000, "rate": 3.5, "years_remaining": 15}],
            state="TX",
            rate_method="conservative",
        )
    )
    data = json.loads(result)
    assert data["status"] == "solved"


@pytest.mark.toml
def test_run_from_params_with_fixed_asset():
    result = _run(
        run_from_params(
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            fixed_assets=[
                {
                    "label": "house",
                    "type": "residence",
                    "value": 600_000,
                    "basis": 300_000,
                    "sell_year": THISYEAR + 8,
                    "commission": 3.0,
                }
            ],
            state="TX",
            rate_method="conservative",
        )
    )
    data = json.loads(result)
    assert data["status"] == "solved"


@pytest.mark.toml
def test_run_from_params_json_structure():
    result = _run(
        run_from_params(
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
    for key in ("status", "case_name", "objective", "summary", "by_year", "time_horizon_years"):
        assert key in data, f"Missing key: {key}"
    assert len(data["by_year"]) == data["time_horizon_years"]


@pytest.mark.toml
def test_run_from_params_error_returns_json():
    """Bad parameters return a JSON error, not an exception."""
    result = _run(
        run_from_params(
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            # Pass a bogus rate method to trigger an error
            ss_monthly_pias=[2500],
            ss_ages=[67],
            rate_method="nonexistent_rate_method_xyz",
        )
    )
    data = json.loads(result)
    assert "error" in data


@pytest.mark.toml
def test_run_from_params_max_bequest_net_spending_dollars():
    """net_spending=60_000 (full $) is interpreted as $60k/yr (not $60M/yr) with units='1'."""
    result = _run(
        run_from_params(
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
            objective="maxBequest",
            net_spending=60_000,
        )
    )
    data = json.loads(result)
    assert data["status"] == "solved"
    # With net_spending=60_000 ($/yr), spending in year 1 should be ~$60k
    assert data["by_year"][0]["spending"] == pytest.approx(60_000, rel=0.05)


@pytest.mark.toml
def test_run_from_params_min_taxable_balance_full_dollars():
    """min_taxable_balance=[20_000] keeps $20k safety net; units='1' so no $k scaling."""
    no_floor = _run(
        run_from_params(
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
    with_floor = _run(
        run_from_params(
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
            min_taxable_balance=[20_000],
        )
    )
    d_no = json.loads(no_floor)
    d_fl = json.loads(with_floor)
    assert d_no["status"] == "solved"
    assert d_fl["status"] == "solved"
    # Imposing a floor constrains the optimizer, so spending can only stay equal or decrease
    assert d_fl["summary"]["spending_basis_today_dollars"] <= d_no["summary"]["spending_basis_today_dollars"] + 1


# ---------------------------------------------------------------------------
# roth_conversions / use_roth_conv_overrides / swap_roth_converters_* (end-to-end)
# ---------------------------------------------------------------------------

_ROTH_OVERRIDE_PARAMS = dict(
    names=["Martin"],
    birth_years=[1960],
    life_expectancy=[88],
    taxable=[200_000],
    tax_deferred=[800_000],
    roth=[100_000],
    hsa=None,
    cost_basis=None,
    ss_monthly_pias=[2500],
    ss_ages=[67],
    pension_monthly_amounts=None,
    pension_ages=None,
    state="TX",
    rate_method="conservative",
    max_roth_conversion=50_000,
)


@pytest.mark.toml
def test_run_from_params_roth_conversion_pin_positive():
    """A positive roth_conversions entry pins x_in[0,0] to that exact amount when
    use_roth_conv_overrides is true, bypassing max_roth_conversion."""
    plan = _run_from_params_blocking(
        **_ROTH_OVERRIDE_PARAMS,
        roth_conversions=[{"person": 0, "year": THISYEAR, "amount": 20_000}],
        use_roth_conv_overrides=True,
    )
    assert plan.caseStatus == "solved"
    assert plan.x_in[0, 0] == pytest.approx(20_000)


@pytest.mark.toml
def test_run_from_params_roth_conversion_forced_zero():
    """A negative roth_conversions entry forces x_in[0,n] to 0 that year when
    use_roth_conv_overrides is true."""
    plan = _run_from_params_blocking(
        **_ROTH_OVERRIDE_PARAMS,
        roth_conversions=[{"person": 0, "year": THISYEAR, "amount": -1}],
        use_roth_conv_overrides=True,
    )
    assert plan.caseStatus == "solved"
    assert plan.x_in[0, 0] == pytest.approx(0)


@pytest.mark.toml
def test_run_from_params_roth_conversions_ignored_without_override():
    """roth_conversions entries are inert unless use_roth_conv_overrides is true."""
    plan = _run_from_params_blocking(
        **_ROTH_OVERRIDE_PARAMS,
        roth_conversions=[{"person": 0, "year": THISYEAR, "amount": -1}],
    )
    assert plan.caseStatus == "solved"
    assert "useRothConvOverrides" not in plan.solverOptions or not plan.solverOptions["useRothConvOverrides"]


@pytest.mark.toml
def test_run_from_params_swap_roth_converters_couple():
    """swap_roth_converters_first/_year combine into a signed swapRothConverters option
    and the plan solves correctly for a couple."""
    swap_year = THISYEAR + 3
    plan = _run_from_params_blocking(
        names=["Alice", "Bob"],
        birth_years=[1963, 1961],
        life_expectancy=[90, 87],
        taxable=[150_000, 150_000],
        tax_deferred=[600_000, 600_000],
        roth=[75_000, 75_000],
        hsa=None,
        cost_basis=None,
        ss_monthly_pias=[2333, 2667],
        ss_ages=[67, 67],
        pension_monthly_amounts=None,
        pension_ages=None,
        state="TX",
        rate_method="conservative",
        max_roth_conversion=20_000,
        swap_roth_converters_first="Bob",
        swap_roth_converters_year=swap_year,
    )
    assert plan.caseStatus == "solved"
    assert plan.solverOptions["swapRothConverters"] == -swap_year


# ---------------------------------------------------------------------------
# with_aca / aca_start_year
# ---------------------------------------------------------------------------


def test_aca_start_year_sets_plan():
    """_build_plan_from_params passes aca_start_year to plan.setACA."""
    plan = _single(slcsp=18_000, aca_start_year=THISYEAR + 2)
    assert plan.aca_start_year == THISYEAR + 2
    assert plan.slcsp_annual == pytest.approx(18_000)


@pytest.mark.toml
def test_run_from_params_with_aca():
    """with_aca='loop' + slcsp produces non-zero ACA premiums for a pre-65 individual."""
    # Single person age 60 → pre-65 for first 5 years
    result = _run(
        run_from_params(
            names=["Sam"],
            birth_years=[1966],
            life_expectancy=[88],
            taxable=[100_000],
            tax_deferred=[400_000],
            roth=[50_000],
            ss_monthly_pias=[1_800],
            ss_ages=[67],
            state="TX",
            rate_method="conservative",
            slcsp=18_000,
            with_aca="loop",
        )
    )
    data = json.loads(result)
    assert data["status"] == "solved"
    aca_total = data["summary"]["aca_nominal"]
    assert aca_total > 0, f"Expected non-zero ACA premiums with slcsp=18_000, got {aca_total}"


# ---------------------------------------------------------------------------
# _ss_ages_opt helper
# ---------------------------------------------------------------------------


def test_ss_ages_opt_false_returns_none():
    assert _ss_ages_opt(False) is None


def test_ss_ages_opt_none_returns_none():
    assert _ss_ages_opt(None) is None


def test_ss_ages_opt_true_returns_optimize():
    assert _ss_ages_opt(True) == "optimize"


def test_ss_ages_opt_all_returns_optimize():
    assert _ss_ages_opt("all") == "optimize"


def test_ss_ages_opt_name_string_passthrough():
    assert _ss_ages_opt("Alice") == "Alice"


def test_ss_ages_opt_list_passthrough():
    assert _ss_ages_opt(["Alice", "Bob"]) == ["Alice", "Bob"]


def test_ss_ages_opt_single_element_list():
    assert _ss_ages_opt(["Alice"]) == ["Alice"]


# ---------------------------------------------------------------------------
# _swap_roth_converters_value helper
# ---------------------------------------------------------------------------


def test_swap_roth_converters_value_none_year_returns_none():
    assert _swap_roth_converters_value(["Alice", "Bob"], "Alice", None) is None


def test_swap_roth_converters_value_first_matches_inames0_positive():
    assert _swap_roth_converters_value(["Alice", "Bob"], "Alice", 2035) == 2035


def test_swap_roth_converters_value_first_is_other_spouse_negative():
    assert _swap_roth_converters_value(["Alice", "Bob"], "Bob", 2035) == -2035


def test_swap_roth_converters_value_no_first_name_defaults_positive():
    assert _swap_roth_converters_value(["Alice", "Bob"], None, 2035) == 2035


# ---------------------------------------------------------------------------
# optimize_ss_ages per-person via run_from_params (integration)
# ---------------------------------------------------------------------------


@pytest.mark.toml
def test_run_from_params_optimize_ss_ages_single_name():
    """optimize_ss_ages='Alice' optimizes only Alice; Bob is fixed at ss_ages value."""
    result = _run(
        run_from_params(
            names=["Alice", "Bob"],
            birth_years=[1963, 1961],
            life_expectancy=[90, 87],
            taxable=[150_000, 150_000],
            tax_deferred=[600_000, 600_000],
            roth=[75_000, 75_000],
            ss_monthly_pias=[2333, 2667],
            ss_ages=[67, 67],
            state="TX",
            rate_method="conservative",
            optimize_ss_ages="Alice",
        )
    )
    data = json.loads(result)
    assert data["status"] == "solved"
    assert data["spending_year1_nominal"] > 0


@pytest.mark.toml
def test_run_from_params_optimize_ss_ages_all():
    """optimize_ss_ages=True optimizes claiming age for all persons."""
    result = _run(
        run_from_params(
            names=["Alice", "Bob"],
            birth_years=[1963, 1961],
            life_expectancy=[90, 87],
            taxable=[150_000, 150_000],
            tax_deferred=[600_000, 600_000],
            roth=[75_000, 75_000],
            ss_monthly_pias=[2333, 2667],
            ss_ages=[67, 67],
            state="TX",
            rate_method="conservative",
            optimize_ss_ages=True,
        )
    )
    data = json.loads(result)
    assert data["status"] == "solved"
    assert data["spending_year1_nominal"] > 0


@pytest.mark.toml
def test_run_from_params_optimize_ss_ages_already_claimed():
    """A person whose current age >= ss_age is treated as already claimed; plan still solves."""
    # Bob born 1955 → age 71 in 2026, already past any claiming age
    result = _run(
        run_from_params(
            names=["Alice", "Bob"],
            birth_years=[1963, 1955],
            life_expectancy=[90, 87],
            taxable=[150_000, 150_000],
            tax_deferred=[600_000, 600_000],
            roth=[75_000, 75_000],
            ss_monthly_pias=[2333, 2667],
            ss_ages=[67, 70],
            state="TX",
            rate_method="conservative",
            optimize_ss_ages=True,
        )
    )
    data = json.loads(result)
    assert data["status"] == "solved"


# ---------------------------------------------------------------------------
# _build_distribution_json helper
# ---------------------------------------------------------------------------


def test_build_distribution_json_structure():
    """_build_distribution_json produces expected top-level keys."""
    plan = _single()
    import numpy as np

    results = [{"value": float(v)} for v in np.linspace(50_000, 100_000, 20)]
    out = _build_distribution_json(plan, results, "maxSpending", "mc", 20)
    assert out["status"] == "completed"
    assert out["scenario_method"] == "mc"
    assert out["n_scenarios_attempted"] == 20
    assert out["n_scenarios_solved"] == 20
    dist = out["distribution"]["spending_today_dollars"]
    for key in ("min", "p10", "p25", "median", "mean", "p75", "p90", "max"):
        assert key in dist
    assert dist["min"] <= dist["median"] <= dist["max"]


def test_build_distribution_json_historical_by_year():
    """Historical results (with 'year' key) produce by_start_year list."""
    plan = _single()
    results = [{"value": 70_000.0 + i * 1_000, "year": 1928 + i} for i in range(5)]
    out = _build_distribution_json(plan, results, "maxSpending", "historical", 5)
    assert "by_start_year" in out
    years = [r["year"] for r in out["by_start_year"]]
    assert years == [1928, 1929, 1930, 1931, 1932]


def test_build_distribution_json_mc_no_by_year():
    """MC results (no 'year' key) do not include by_start_year."""
    plan = _single()
    results = [{"value": 70_000.0}] * 10
    out = _build_distribution_json(plan, results, "maxSpending", "mc", 10)
    assert "by_start_year" not in out


# ---------------------------------------------------------------------------
# run_historical (integration)
# ---------------------------------------------------------------------------


@pytest.mark.toml
def test_run_historical_from_params_solves():
    """run_historical with flat params runs and returns a distribution."""
    result = _run(
        run_historical(
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            state="TX",
            ystart=1985,
            yend=2000,
        )
    )
    data = json.loads(result)
    assert data["status"] == "completed"
    assert data["scenario_method"] == "historical"
    assert data["n_scenarios_attempted"] >= 1
    assert data["n_scenarios_solved"] >= 1
    dist = data["distribution"]["spending_today_dollars"]
    assert dist["min"] > 0
    assert dist["max"] >= dist["min"]


@pytest.mark.toml
def test_run_historical_from_file_solves():
    """run_historical with filename= loads TOML and runs over a small year window."""
    result = _run(
        run_historical(
            filename="examples/Case_bill.toml",
            overrides=["solver_options.withMedicare=None", "solver_options.withDecomposition=none"],
            ystart=1990,
            yend=2000,
        )
    )
    data = json.loads(result)
    assert data["status"] == "completed"
    assert "by_start_year" in data
    assert len(data["by_start_year"]) >= 1


@pytest.mark.toml
def test_run_historical_by_year_coverage():
    """by_start_year contains one entry per solved year in the window."""
    result = _run(
        run_historical(
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            state="TX",
            ystart=1990,
            yend=1994,
        )
    )
    data = json.loads(result)
    assert data["status"] == "completed"
    years = [e["year"] for e in data["by_start_year"]]
    for y in range(1990, 1995):
        assert y in years, f"Year {y} missing from by_start_year"


# ---------------------------------------------------------------------------
# run_monte_carlo (integration)
# ---------------------------------------------------------------------------


@pytest.mark.toml
def test_run_monte_carlo_solves():
    """run_monte_carlo with gmm (no frm/to needed) returns a distribution."""
    result = _run(
        run_monte_carlo(
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            state="TX",
            rate_method="gmm",
            n_scenarios=20,
            seed=42,
        )
    )
    data = json.loads(result)
    assert data["status"] == "completed"
    assert data["scenario_method"] == "mc"
    assert data["n_scenarios_attempted"] == 20
    dist = data["distribution"]["spending_today_dollars"]
    assert dist["min"] > 0


@pytest.mark.toml
def test_run_monte_carlo_deterministic_method_fails():
    """run_monte_carlo with a deterministic rate method returns an error."""
    result = _run(
        run_monte_carlo(
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
            n_scenarios=5,
        )
    )
    data = json.loads(result)
    assert "error" in data


@pytest.mark.toml
def test_run_monte_carlo_bootstrap():
    """run_monte_carlo with historical_bootstrap and block_size=3 runs correctly."""
    result = _run(
        run_monte_carlo(
            names=["Martin"],
            birth_years=[1960],
            life_expectancy=[88],
            taxable=[200_000],
            tax_deferred=[800_000],
            roth=[100_000],
            ss_monthly_pias=[2500],
            ss_ages=[67],
            state="TX",
            rate_method="historical_bootstrap",
            rate_frm=1970,
            rate_to=2020,
            rate_params={"bootstrap_type": "block", "block_size": 3},
            n_scenarios=15,
            seed=7,
        )
    )
    data = json.loads(result)
    assert data["status"] == "completed"
    assert data["n_scenarios_solved"] > 0


@pytest.mark.toml
def test_run_monte_carlo_from_file_deterministic_toml():
    """run_monte_carlo from a TOML with a deterministic rate method auto-applies gmm."""
    # Case_bill.toml uses rate_method="historical" (deterministic); the tool
    # must override it with a stochastic model so MC can run.
    result = _run(
        run_monte_carlo(
            filename="examples/Case_bill.toml",
            overrides=[
                "solver_options.withMedicare=None",
                "solver_options.withDecomposition=none",
            ],
            rate_method="gmm",
            n_scenarios=15,
            seed=42,
        )
    )
    data = json.loads(result)
    assert data["status"] == "completed", data.get("error", "")
    assert data["rate_method"] == "gmm"
    assert data["n_scenarios_solved"] > 0
    dist = data["distribution"]["spending_today_dollars"]
    assert dist["min"] > 0


# ---------------------------------------------------------------------------
# OBBBA expiration year + SS haircut + dividend rate
# ---------------------------------------------------------------------------

_SCENARIO_PARAMS = dict(
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
    with_medicare=None,
)


@pytest.mark.toml
def test_run_from_params_ss_haircut_lowers_spending():
    """SS benefit reduction (trust fund haircut) reduces optimal spending."""
    r_base = json.loads(_run(run_from_params(**_SCENARIO_PARAMS)))
    r_cut = json.loads(_run(run_from_params(**_SCENARIO_PARAMS, ss_trim_pct=23, ss_trim_year=2033)))
    assert r_base["status"] == "solved"
    assert r_cut["status"] == "solved"
    s_base = r_base["summary"]["spending_basis_today_dollars"]
    s_cut = r_cut["summary"]["spending_basis_today_dollars"]
    assert s_cut < s_base, f"Haircut should lower spending: {s_cut} >= {s_base}"


@pytest.mark.toml
def test_run_from_params_obbba_year_changes_result():
    """Earlier OBBBA expiration changes the optimal plan (tax brackets shift sooner)."""
    r_def = json.loads(_run(run_from_params(**_SCENARIO_PARAMS)))
    r_early = json.loads(_run(run_from_params(**_SCENARIO_PARAMS, obbba_expiration_year=2028)))
    assert r_def["status"] == "solved"
    assert r_early["status"] == "solved"
    s_def = r_def["summary"]["spending_basis_today_dollars"]
    s_early = r_early["summary"]["spending_basis_today_dollars"]
    assert s_early != s_def, "OBBBA 2028 should produce a different result than default 2032"


@pytest.mark.toml
def test_run_from_params_dividend_rate_accepted():
    """dividend_rate parameter is accepted and changes the plan."""
    r = json.loads(_run(run_from_params(**_SCENARIO_PARAMS, dividend_rate=3.0)))
    assert r["status"] == "solved"
    assert r["summary"]["spending_basis_today_dollars"] > 0
