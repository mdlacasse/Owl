"""
Tests for config <-> UI flat dict conversion (owlplanner.config.ui_bridge).

Copyright (C) 2025-2026 The Owlplanner Authors
"""

from io import StringIO

import owlplanner as owl
from owlplanner.config import (
    apply_config_to_plan,
    config_to_plan,
    config_to_ui,
    load_toml,
    plan_to_config,
    sanitize_config,
    ui_to_config,
)


def test_sanitize_config_start_roth_past_year():
    """sanitize_config resets startRothConversions to this year when in the past."""
    from datetime import date

    diconf = {"solver_options": {"startRothConversions": 2019}}
    log = StringIO()
    sanitize_config(diconf, log_stream=log)
    thisyear = date.today().year

    assert diconf["solver_options"]["startRothConversions"] == thisyear
    assert "Warning" in log.getvalue()
    assert "reset to" in log.getvalue()


def test_load_toml_start_roth_past_year_reset():
    """startRothConversions in the past is reset when config file is read (via sanitize_config)."""
    from datetime import date

    toml_content = open("examples/Case_joe.toml").read()
    toml_content = toml_content.replace(
        "startRothConversions = 2026",
        "startRothConversions = 2019",  # Past year
    )
    log = StringIO()
    diconf, _, _ = load_toml(StringIO(toml_content), log_stream=log)
    thisyear = date.today().year

    assert diconf["solver_options"]["startRothConversions"] == thisyear
    assert "Warning" in log.getvalue()


def test_config_to_ui_roundtrip():
    """config -> ui -> config preserves structure."""
    diconf, _, _ = load_toml(StringIO(open("examples/Case_joe.toml").read()))
    uidic = config_to_ui(diconf)

    assert uidic["name"] == "joe"
    assert uidic["status"] == "single"
    assert uidic["iname0"] == "Joe"
    assert uidic["allocType"] == "individual"

    back = ui_to_config(uidic)
    assert back["case_name"] == "joe"
    assert back["basic_info"]["names"] == ["Joe"]
    assert back["asset_allocation"]["type"] == "individual"


def test_ui_to_config_to_plan():
    """ui dict -> config -> plan produces valid plan."""
    diconf, _, _ = load_toml(StringIO(open("examples/Case_joe.toml").read()))
    uidic = config_to_ui(diconf)
    back = ui_to_config(uidic)
    plan = config_to_plan(back, verbose=False, loadHFP=False)

    assert plan._name == "joe"
    assert plan.N_i == 1
    assert plan.inames[0] == "Joe"


def test_config_to_ui_dataframe_maps_to_user(caplog):
    """When config has method=dataframe, config_to_ui maps to user and logs warning."""
    import logging
    caplog.set_level(logging.WARNING)

    diconf = {
        "case_name": "test",
        "description": "",
        "basic_info": {
            "status": "single",
            "names": ["Joe"],
            "date_of_birth": ["1961-01-15"],
            "life_expectancy": [89],
            "start_date": "today",
        },
        "savings_assets": {
            "taxable_savings_balances": [100],
            "tax_deferred_savings_balances": [200],
            "tax_free_savings_balances": [50],
        },
        "household_financial_profile": {"HFP_file_name": "None"},
        "fixed_income": {
            "pension_monthly_amounts": [0],
            "pension_ages": [65],
            "pension_indexed": [True],
            "social_security_pia_amounts": [0],
            "social_security_ages": [67],
        },
        "rates_selection": {
            "heirs_rate_on_tax_deferred_estate": 30,
            "dividend_rate": 1.8,
            "obbba_expiration_year": 2032,
            "method": "dataframe",
        },
        "asset_allocation": {
            "interpolation_method": "s-curve",
            "interpolation_center": 15,
            "interpolation_width": 5,
            "type": "individual",
            "generic": [[[60, 40, 0, 0], [70, 30, 0, 0]]],
        },
        "optimization_parameters": {
            "spending_profile": "flat",
            "surviving_spouse_spending_percent": 60,
            "objective": "maxSpending",
        },
        "solver_options": {},
        "results": {"default_plots": "nominal"},
    }
    uidic = config_to_ui(diconf)

    assert uidic["rateType"] == "fixed"
    assert uidic["fixedType"] == "user"
    assert "Dataframe rate method is not supported in UI" in caplog.text


def test_config_roundtrip_social_security_trim():
    """SS trim_pct and trim_year roundtrip through config_to_ui and ui_to_config."""
    diconf = _minimal_config_for_rates()
    diconf["fixed_income"]["social_security_trim_pct"] = 23
    diconf["fixed_income"]["social_security_trim_year"] = 2035

    uidic = config_to_ui(diconf)
    assert uidic["ssTrimPct"] == 23
    assert uidic["ssTrimYear"] == 2035

    out = ui_to_config(uidic)
    assert out["fixed_income"]["social_security_trim_pct"] == 23
    assert out["fixed_income"]["social_security_trim_year"] == 2035


def test_apply_config_to_plan():
    """apply_config_to_plan syncs config to existing plan."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("default")
    if not hasattr(p, "solverOptions"):
        p.solverOptions = {}

    diconf = plan_to_config(p)
    diconf["savings_assets"]["taxable_savings_balances"] = [150.0]  # Change

    apply_config_to_plan(p, diconf)
    assert p.beta_ij[0, 0] == 150000  # 150 * 1000


def test_config_to_ui_rates_in_valid_range():
    """
    Regression: config_to_ui must produce rate values in valid widget range.

    Bug (StreamlitValueAboveMaxError): config stored rates in percent (7 = 7%),
    but config_to_ui incorrectly multiplied by 100, producing fxRate0=700 which
    exceeded st.number_input max_value=100. Returns and volatility use percent;
    correlations use Pearson coefficient (-1 to 1).
    """
    diconf = _minimal_config_for_rates()
    diconf["rates_selection"]["method"] = "user"
    diconf["rates_selection"]["values"] = [7.0, 4.0, 3.3, 2.8]

    uidic = config_to_ui(diconf)

    # Returns: percent (e.g., 7 for 7%). Must be in [-100, 100] for widget.
    for k in range(4):
        val = uidic[f"fxRate{k}"]
        assert -100 <= val <= 100, f"fxRate{k}={val} out of widget range [-100, 100]"
    assert uidic["fxRate0"] == 7.0
    assert uidic["fxRate1"] == 4.0


def test_config_to_ui_stochastic_rates_in_valid_range():
    """
    Regression: stochastic rates (means, stdev, corr) in valid ranges after config_to_ui.

    Means and stdev: percent. Correlations: Pearson coefficient (-1 to 1).
    """
    diconf = _minimal_config_for_rates()
    diconf["rates_selection"]["method"] = "stochastic"
    diconf["rates_selection"]["values"] = [8.0, 5.0, 3.5, 2.5]
    diconf["rates_selection"]["standard_deviations"] = [17.0, 8.0, 10.0, 3.0]
    diconf["rates_selection"]["correlations"] = [0.4, 0.26, -0.22, 0.84, -0.39, -0.39]

    uidic = config_to_ui(diconf)

    # Means: percent, in [-100, 100]
    for k in range(4):
        assert -100 <= uidic[f"mean{k}"] <= 100, f"mean{k} out of range"
    assert uidic["mean0"] == 8.0

    # Stdev: percent, non-negative
    for k in range(4):
        assert 0 <= uidic[f"stdev{k}"] <= 100, f"stdev{k} out of range"
    assert uidic["stdev0"] == 17.0

    # Correlations: coefficient (-1 to 1), not percent
    for q in range(1, 7):
        assert -1 <= uidic[f"corr{q}"] <= 1, f"corr{q} must be coefficient in [-1, 1]"
    assert abs(uidic["corr1"] - 0.4) < 1e-9


def test_plan_to_config_to_ui_rates_roundtrip():
    """
    Regression: plan -> config -> ui preserves rate representation.
    plan_to_config saves percent for returns/stdev, coefficient for corr.
    config_to_ui must not double-convert (e.g., multiply percent by 100 again).
    """
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("stochastic", values=[7.0, 4.0, 3.3, 2.8], stdev=[17.0, 8.0, 10.0, 3.0])

    diconf = plan_to_config(p)
    uidic = config_to_ui(diconf)

    # Plan had 7% etc.; config and UI should show 7, not 700
    assert uidic["mean0"] == 7.0
    assert uidic["stdev0"] == 17.0
    assert all(-100 <= uidic[f"mean{k}"] <= 100 for k in range(4))
    assert all(0 <= uidic[f"stdev{k}"] <= 100 for k in range(4))


def _minimal_config_for_rates():
    """Minimal config dict with rates_selection section."""
    return {
        "case_name": "test",
        "basic_info": {
            "status": "single",
            "names": ["Joe"],
            "date_of_birth": ["1961-01-15"],
            "life_expectancy": [89],
            "start_date": "today",
        },
        "savings_assets": {
            "taxable_savings_balances": [100],
            "tax_deferred_savings_balances": [200],
            "tax_free_savings_balances": [50],
        },
        "household_financial_profile": {"HFP_file_name": "None"},
        "fixed_income": {
            "pension_monthly_amounts": [0],
            "pension_ages": [65],
            "pension_indexed": [True],
            "social_security_pia_amounts": [0],
            "social_security_ages": [67],
        },
        "rates_selection": {
            "heirs_rate_on_tax_deferred_estate": 30,
            "dividend_rate": 1.8,
            "obbba_expiration_year": 2032,
            "method": "user",
        },
        "asset_allocation": {
            "interpolation_method": "s-curve",
            "interpolation_center": 15,
            "interpolation_width": 5,
            "type": "individual",
            "generic": [[[60, 40, 0, 0], [70, 30, 0, 0]]],
        },
        "optimization_parameters": {
            "spending_profile": "flat",
            "surviving_spouse_spending_percent": 60,
            "objective": "maxSpending",
        },
        "solver_options": {},
        "results": {"default_plots": "nominal"},
    }
