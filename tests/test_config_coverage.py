"""
Tests for config.py to improve coverage.

This module tests configuration save/load functionality, error handling,
and edge cases that are not covered by existing tests.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import pytest
from io import StringIO, BytesIO

import owlplanner as owl
import owlplanner.config as config


def test_save_config_stringio():
    """Test saveConfig with StringIO."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    if not hasattr(p, 'solverOptions'):
        p.solverOptions = {}

    f = StringIO()
    config.saveConfig(p, f, p.mylog)
    f.seek(0)
    content = f.read()
    assert "case_name" in content
    assert "test" in content


def test_save_config_bytesio():
    """Test saveConfig with BytesIO - BytesIO is not supported, will raise error."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    if not hasattr(p, 'solverOptions'):
        p.solverOptions = {}

    f = BytesIO()
    # BytesIO is not directly supported by saveConfig (only StringIO and file paths)
    with pytest.raises(ValueError, match="unknown type"):
        config.saveConfig(p, f, p.mylog)


def test_save_config_invalid_type():
    """Test saveConfig with invalid file type."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    if not hasattr(p, 'solverOptions'):
        p.solverOptions = {}
    with pytest.raises(ValueError, match="unknown type"):
        config.saveConfig(p, 12345, p.mylog)


def test_read_config_stringio():
    """Test readConfig with StringIO."""
    toml_content = """
case_name = "test"
description = "Test case"

[basic_info]
status = "single"
names = ["Joe"]
date_of_birth = ["1961-01-15"]
life_expectancy = [80]
start_date = "today"

[savings_assets]
taxable_savings_balances = [100.0]
tax_deferred_savings_balances = [200.0]
tax_free_savings_balances = [50.0]

[fixed_income]
pension_monthly_amounts = [0]
pension_ages = [65]
pension_indexed = [false]
social_security_pia_amounts = [0]
social_security_ages = [67]

[rates_selection]
heirs_rate_on_tax_deferred_estate = 35.0
dividend_rate = 2.0
obbba_expiration_year = 2032
method = "default"
from = 1926
to = 2023

[asset_allocation]
interpolation_method = "linear"
interpolation_center = 15.0
interpolation_width = 5.0
type = "individual"
generic = [[[60, 40, 0, 0], [60, 40, 0, 0]]]

[optimization_parameters]
spending_profile = "flat"
surviving_spouse_spending_percent = 60
objective = "maxSpending"

[solver_options]

[results]
default_plots = "nominal"
"""
    f = StringIO(toml_content)
    p = config.readConfig(f, verbose=False)
    assert p._name == "test"
    assert p.inames == ["Joe"]


def test_read_config_bytesio():
    """Test readConfig with BytesIO."""
    toml_content = """
case_name = "test"
description = "Test case"

[basic_info]
status = "single"
names = ["Joe"]
date_of_birth = ["1961-01-15"]
life_expectancy = [80]
start_date = "today"

[savings_assets]
taxable_savings_balances = [100.0]
tax_deferred_savings_balances = [200.0]
tax_free_savings_balances = [50.0]

[fixed_income]
pension_monthly_amounts = [0]
pension_ages = [65]
pension_indexed = [false]
social_security_pia_amounts = [0]
social_security_ages = [67]

[rates_selection]
heirs_rate_on_tax_deferred_estate = 35.0
dividend_rate = 2.0
obbba_expiration_year = 2032
method = "default"
from = 1926
to = 2023

[asset_allocation]
interpolation_method = "linear"
interpolation_center = 15.0
interpolation_width = 5.0
type = "individual"
generic = [[[60, 40, 0, 0], [60, 40, 0, 0]]]

[optimization_parameters]
spending_profile = "flat"
surviving_spouse_spending_percent = 60
objective = "maxSpending"

[solver_options]

[results]
default_plots = "nominal"
"""
    f = BytesIO(toml_content.encode('utf-8'))
    p = config.readConfig(f, verbose=False)
    assert p._name == "test"


def test_read_config_bytesio_decode_error():
    """Test readConfig with BytesIO that can't be decoded."""
    f = BytesIO(b'\xff\xfe\x00\x00')  # Invalid UTF-8
    with pytest.raises(RuntimeError, match="Cannot read from BytesIO"):
        config.readConfig(f, verbose=False)


def test_read_config_stringio_error():
    """Test readConfig with StringIO that has invalid TOML."""
    f = StringIO("invalid toml content {")
    with pytest.raises(RuntimeError, match="Cannot read from StringIO"):
        config.readConfig(f, verbose=False)


def test_read_config_invalid_type():
    """Test readConfig with invalid file type."""
    with pytest.raises(ValueError, match="Type.*not a valid type"):
        config.readConfig(12345, verbose=False)


def test_read_config_file_not_found():
    """Test readConfig with non-existent file."""
    with pytest.raises(FileNotFoundError):
        config.readConfig("nonexistent_file_12345", verbose=False)


def test_translate_old_keys():
    """Test translate_old_keys function."""
    old_config = {
        "Plan Name": "test",
        "Basic Info": {
            "Status": "single",
            "Names": ["Joe"]
        }
    }
    translated = config.translate_old_keys(old_config)
    assert "case_name" in translated
    assert "basic_info" in translated
    assert translated["basic_info"]["status"] == "single"


def test_translate_old_keys_nested():
    """Test translate_old_keys with nested dictionaries."""
    old_config = {
        "Assets": {
            "taxable savings balances": [100.0]
        }
    }
    translated = config.translate_old_keys(old_config)
    assert "savings_assets" in translated
    assert "taxable_savings_balances" in translated["savings_assets"]


def test_translate_old_keys_non_dict():
    """Test translate_old_keys with non-dict input."""
    result = config.translate_old_keys("not a dict")
    assert result == "not a dict"

    result = config.translate_old_keys(123)
    assert result == 123


def test_save_config_with_smile_profile():
    """Test saveConfig with smile spending profile."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("smile", percent=60, dip=15, increase=12, delay=5)
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    if not hasattr(p, 'solverOptions'):
        p.solverOptions = {}

    f = StringIO()
    config.saveConfig(p, f, p.mylog)
    f.seek(0)
    content = f.read()
    assert "smile_dip" in content
    assert "smile_increase" in content


def test_save_config_with_stochastic_rates():
    """Test saveConfig with stochastic rate method."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("stochastic", values=[0.05, 0.03, 0.02, 0.01], stdev=[0.15, 0.10, 0.05, 0.02])
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    if not hasattr(p, 'solverOptions'):
        p.solverOptions = {}

    f = StringIO()
    config.saveConfig(p, f, p.mylog)
    f.seek(0)
    content = f.read()
    assert "standard_deviations" in content
    assert "correlations" in content


def test_save_config_with_historical_rates():
    """Test saveConfig with historical rate method."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("historical", frm=1950, to=2000)
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    if not hasattr(p, 'solverOptions'):
        p.solverOptions = {}

    f = StringIO()
    config.saveConfig(p, f, p.mylog)
    f.seek(0)
    content = f.read()
    # Check that "from" field is present (format: "from = 1950" or "from=1950")
    assert 'from' in content and '1950' in content


def test_save_config_married_couple():
    """Test saveConfig with married couple."""
    p = owl.Plan(['Joe', 'Jane'], ["1961-01-15", "1962-01-15"], [80, 82], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]], [[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100, 50], taxDeferred=[200, 100], taxFree=[50, 25])
    p.setBeneficiaryFractions([0.5, 0.3, 0.2])
    if not hasattr(p, 'solverOptions'):
        p.solverOptions = {}

    f = StringIO()
    config.saveConfig(p, f, p.mylog)
    f.seek(0)
    content = f.read()
    assert "beneficiary_fractions" in content
    assert "spousal_surplus_deposit_fraction" in content


def test_save_config_account_allocation():
    """Test saveConfig with account-based allocation."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("account", taxable=[[[70, 30, 0, 0], [70, 30, 0, 0]]],
                          taxDeferred=[[[60, 40, 0, 0], [60, 40, 0, 0]]],
                          taxFree=[[[50, 50, 0, 0], [50, 50, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    # Need to set solverOptions attribute for saveConfig
    if not hasattr(p, 'solverOptions'):
        p.solverOptions = {}

    f = StringIO()
    config.saveConfig(p, f, p.mylog)
    f.seek(0)
    content = f.read()
    assert "taxable" in content or '"taxable"' in content


def test_save_config_file_error():
    """Test saveConfig file write error handling."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])

    # Use a path that should cause an error (invalid directory)
    with pytest.raises((RuntimeError, OSError), match="Failed to save case file|No such file"):
        config.saveConfig(p, "/invalid/path/that/does/not/exist/test", p.mylog)


def test_save_config_no_double_case_prefix(tmp_path):
    """Regression test for issue #96: filenames starting with 'Case_' must not
    get a spurious 'case_' prefix, producing 'case_Case_...' filenames."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "joe")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])

    for name in ("Case_joe", "case_joe", "CASE_joe"):
        target = tmp_path / f"{name}.toml"
        config.saveConfig(p, str(target.with_suffix("")), p.mylog)
        assert target.exists(), f"Expected {target} to be created"
        bad = tmp_path / f"case_{name}.toml"
        assert not bad.exists(), f"Double-prefix file {bad} must not be created"
        target.unlink()  # clean up for next iteration
