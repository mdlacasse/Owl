"""
Tests for the Pydantic-based configuration system.

Covers round-trip, unknown key preservation, and schema validation.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

from io import StringIO

import pytest
from pydantic import ValidationError

import owlplanner as owl
import owlplanner.config as config


_TOML_WITH_USER_KEYS = """
case_name = "test_preserve"
description = "Test case for user key preservation"

[basic_info]
status = "single"
names = ["Joe"]
date_of_birth = ["1967-01-15"]
life_expectancy = [89]
start_date = "2026-01-01"

[user]
notes = "My custom notes"
version = 2
custom_tag = "important"

[custom_metadata]
created_by = "test"
review_date = "2027-01-01"

[savings_assets]
taxable_savings_balances = [338.5]
tax_deferred_savings_balances = [650.2]
tax_free_savings_balances = [60.6]

[household_financial_profile]
HFP_file_name = "None"

[fixed_income]
pension_monthly_amounts = [0]
pension_ages = [65.0]
pension_indexed = [true]
social_security_pia_amounts = [2360]
social_security_ages = [67.0]

[rates_selection]
heirs_rate_on_tax_deferred_estate = 30.0
dividend_rate = 1.8
obbba_expiration_year = 2032
method = "historical average"
from = 1969
to = 2002

[asset_allocation]
interpolation_method = "s-curve"
interpolation_center = 15.0
interpolation_width = 5.0
type = "individual"
generic = [[[60, 40, 0, 0], [70, 30, 0, 0]]]

[optimization_parameters]
spending_profile = "smile"
surviving_spouse_spending_percent = 60
smile_dip = 15
smile_increase = 12
smile_delay = 0
objective = "maxSpending"

[solver_options]
maxRothConversion = 50
startRothConversions = 2025
bequest = 300
withSCLoop = true
withMedicare = "loop"
solver = "HiGHS"

[results]
default_plots = "nominal"
"""


def test_user_keys_preserved_on_roundtrip():
    """User-defined sections ([user], [custom_metadata], etc.) are preserved across load/save."""
    strio = StringIO(_TOML_WITH_USER_KEYS)
    p = owl.readConfig(strio, verbose=False, loadHFP=False)

    out = StringIO()
    p.saveConfig(out)
    out_str = out.getvalue()

    assert "[user]" in out_str
    assert 'notes = "My custom notes"' in out_str or "notes =" in out_str
    assert "version = 2" in out_str or "version =" in out_str
    assert "[custom_metadata]" in out_str
    assert "created_by" in out_str or "review_date" in out_str


def test_user_keys_survive_second_roundtrip():
    """User keys preserved through multiple load/save cycles."""
    strio = StringIO(_TOML_WITH_USER_KEYS)
    p1 = owl.readConfig(strio, verbose=False, loadHFP=False)

    out1 = StringIO()
    p1.saveConfig(out1)
    out1.seek(0)

    p2 = owl.readConfig(out1, verbose=False, loadHFP=False)
    out2 = StringIO()
    p2.saveConfig(out2)
    out2_str = out2.getvalue()

    assert "[user]" in out2_str
    assert "[custom_metadata]" in out2_str


def test_load_config_returns_dict():
    """load_config (low-level) returns raw dict with all keys."""
    from owlplanner.config import load_toml

    strio = StringIO(_TOML_WITH_USER_KEYS)
    diconf, dirname, filename = load_toml(strio)

    assert "user" in diconf
    assert diconf["user"]["notes"] == "My custom notes"
    assert "custom_metadata" in diconf
    assert diconf["custom_metadata"]["created_by"] == "test"


def test_plan_created_programmatically_has_no_extra():
    """Plans created via API (not from file) have no _config_extra by default."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "api_plan", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("trailing-30")
    if not hasattr(p, "solverOptions"):
        p.solverOptions = {}

    diconf = config.plan_to_config(p)
    # Should not contain user/custom sections
    assert "user" not in diconf or diconf.get("user") is None
    assert "custom_metadata" not in diconf


def test_config_schema_can_validate():
    """CaseConfig schema validates a proper config dict."""
    from owlplanner.config import load_toml
    from owlplanner.config.schema import config_dict_to_model

    strio = StringIO(_TOML_WITH_USER_KEYS)
    diconf, _, _ = load_toml(strio)

    case_config, extra = config_dict_to_model(diconf)

    assert case_config.case_name == "test_preserve"
    assert case_config.basic_info.names == ["Joe"]
    assert "user" in extra
    assert extra["user"]["notes"] == "My custom notes"


def test_default_config_validates_and_builds_plan():
    """default_config() produces a valid config that config_to_plan can use."""
    from owlplanner.config import config_to_plan, config_to_ui, default_config
    from owlplanner.config.schema import config_dict_to_model

    for ni in (1, 2):
        diconf = default_config(ni=ni)
        # Schema validation
        case_config, extra = config_dict_to_model(diconf)
        assert len(case_config.basic_info.names) == ni
        assert case_config.basic_info.status == ("single" if ni == 1 else "married")
        # Plan build (use placeholder names and case name for Plan constructor)
        diconf["case_name"] = "test_default"
        diconf["basic_info"]["names"] = ["Joe"] if ni == 1 else ["Joe", "Jill"]
        p = config_to_plan(diconf, verbose=False, loadHFP=False)
        assert p.N_i == ni
        # config_to_ui round-trip
        ui = config_to_ui(diconf)
        assert ui["life0"] == 89
        assert ui["allocType"] == "individual"


def test_asset_allocation_s_curve_requires_center_width():
    """s-curve interpolation requires center and width in the schema."""
    from owlplanner.config.schema import AssetAllocation

    with pytest.raises(ValidationError):
        AssetAllocation.model_validate({"interpolation_method": "s-curve"})


def test_asset_allocation_linear_allows_omitted_center_width():
    """linear interpolation does not require center/width."""
    from owlplanner.config.schema import AssetAllocation

    m = AssetAllocation.model_validate({"interpolation_method": "linear"})
    assert m.interpolation_center is None
    assert m.interpolation_width is None


def test_asset_allocation_rejects_invalid_interpolation_method():
    """AssetAllocation rejects unknown interpolation_method values."""
    from owlplanner.config.schema import AssetAllocation

    with pytest.raises(ValidationError):
        AssetAllocation.model_validate(
            {
                "interpolation_method": "cosine",
                "interpolation_center": 15.0,
                "interpolation_width": 5.0,
            }
        )


def test_config_to_plan_s_curve_requires_interpolation_params():
    """config_to_plan raises when s-curve is set but center/width are missing."""
    from owlplanner.config import config_to_plan, default_config

    diconf = default_config(ni=1)
    diconf["case_name"] = "test"
    diconf["basic_info"]["names"] = ["Joe"]
    del diconf["asset_allocation"]["interpolation_center"]
    del diconf["asset_allocation"]["interpolation_width"]
    with pytest.raises(ValueError, match="interpolation_center"):
        config_to_plan(diconf, verbose=False, loadHFP=False)


def test_config_to_plan_linear_without_interpolation_params():
    """config_to_plan accepts linear with omitted center/width."""
    from owlplanner.config import config_to_plan, default_config

    diconf = default_config(ni=1)
    diconf["case_name"] = "test"
    diconf["basic_info"]["names"] = ["Joe"]
    diconf["asset_allocation"]["interpolation_method"] = "linear"
    del diconf["asset_allocation"]["interpolation_center"]
    del diconf["asset_allocation"]["interpolation_width"]
    p = config_to_plan(diconf, verbose=False, loadHFP=False)
    assert p.interpMethod == "linear"


def test_plan_to_config_linear_omits_interpolation_center_width():
    """plan_to_config omits center/width when interpolation is linear."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("trailing-30")
    if not hasattr(p, "solverOptions"):
        p.solverOptions = {}
    p.setInterpolationMethod("linear")

    out = config.plan_to_config(p)
    assert out["asset_allocation"]["interpolation_method"] == "linear"
    assert "interpolation_center" not in out["asset_allocation"]
    assert "interpolation_width" not in out["asset_allocation"]
