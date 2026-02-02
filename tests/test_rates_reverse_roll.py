"""
Tests for setRates reverse and roll sequence options.

Verifies that reverse_sequence and roll_sequence parameters are applied
once in setRates, stored on the plan, and correctly read/written by config.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import numpy as np
from io import StringIO

import owlplanner as owl
import owlplanner.config as config


def _make_plan_with_historical_rates():
    """Create a plan with deterministic historical rates for testing."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    return p


class TestSetRatesReverse:
    """Tests for setRates reverse_sequence option."""

    def test_reverse_default_false(self):
        """Default reverse=False leaves sequence unchanged."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1969, 1969 + 10)  # 11 years
        tau_no_reverse = p.tau_kn.copy()
        assert p.rateReverse is False
        assert p.rateRoll == 0
        # Calling again without reverse should give same result
        p.setRates("historical", 1969, 1969 + 10)
        np.testing.assert_array_almost_equal(p.tau_kn, tau_no_reverse)

    def test_reverse_true_reverses_sequence(self):
        """reverse=True reverses the rate sequence along the time axis."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1969, 1969 + 5)  # 6 years, deterministic
        tau_original = p.tau_kn.copy()
        p.setRates("historical", 1969, 1969 + 5, reverse=True)
        assert p.rateReverse is True
        # First year of reversed should equal last year of original
        np.testing.assert_array_almost_equal(p.tau_kn[:, 0], tau_original[:, -1])
        # Last year of reversed should equal first year of original
        np.testing.assert_array_almost_equal(p.tau_kn[:, -1], tau_original[:, 0])
        # Full reversal check
        np.testing.assert_array_almost_equal(p.tau_kn, tau_original[:, ::-1])

    def test_reverse_stored_on_plan(self):
        """reverse value is stored on plan for config save."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1970, 1980, reverse=True)
        assert p.rateReverse is True
        p.setRates("historical", 1970, 1980, reverse=False)
        assert p.rateReverse is False


class TestSetRatesRoll:
    """Tests for setRates roll_sequence option."""

    def test_roll_default_zero(self):
        """Default roll=0 leaves sequence unchanged."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1969, 1969 + 5)
        tau_no_roll = p.tau_kn.copy()
        assert p.rateRoll == 0
        np.testing.assert_array_almost_equal(p.tau_kn, tau_no_roll)

    def test_roll_positive_shifts_sequence(self):
        """Positive roll shifts the sequence; elements wrap around."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1969, 1969 + 5)  # 6 years
        tau_original = p.tau_kn.copy()
        p.setRates("historical", 1969, 1969 + 5, roll=2)
        assert p.rateRoll == 2
        # roll=2: column 0 should equal original column -2 (last but two)
        np.testing.assert_array_almost_equal(p.tau_kn[:, 0], tau_original[:, -2])
        np.testing.assert_array_almost_equal(p.tau_kn[:, 1], tau_original[:, -1])
        np.testing.assert_array_almost_equal(p.tau_kn[:, 2], tau_original[:, 0])
        np.testing.assert_array_almost_equal(p.tau_kn, np.roll(tau_original, 2, axis=1))

    def test_roll_negative_shifts_sequence(self):
        """Negative roll shifts the sequence in the opposite direction."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1969, 1969 + 5)
        tau_original = p.tau_kn.copy()
        p.setRates("historical", 1969, 1969 + 5, roll=-1)
        assert p.rateRoll == -1
        np.testing.assert_array_almost_equal(p.tau_kn, np.roll(tau_original, -1, axis=1))

    def test_roll_stored_on_plan(self):
        """roll value is stored on plan for config save."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1970, 1980, roll=3)
        assert p.rateRoll == 3


class TestSetRatesReverseAndRoll:
    """Tests for applying reverse and roll together."""

    def test_reverse_then_roll_order(self):
        """Transform is applied: first reverse, then roll (in setRates)."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1969, 1969 + 4)  # 5 years
        tau_base = p.tau_kn.copy()
        expected = np.roll(tau_base[:, ::-1], 1, axis=1)
        p.setRates("historical", 1969, 1969 + 4, reverse=True, roll=1)
        np.testing.assert_array_almost_equal(p.tau_kn, expected)


class TestRegenRatesPreservesReverseRoll:
    """regenRates should pass reverse and roll to setRates."""

    def test_regen_rates_preserves_reverse_roll(self):
        """regenRates (for stochastic) preserves rateReverse and rateRoll."""
        p = _make_plan_with_historical_rates()
        # Use histochastic so regenRates actually does something
        p.setReproducible(False)  # so each regen gives new rates
        p.setRates("histochastic", 1970, 1990, reverse=True, roll=2)
        assert p.rateReverse is True
        assert p.rateRoll == 2
        tau_before = p.tau_kn.copy()
        p.regenRates(override_reproducible=True)
        # reverse and roll should still be set and applied
        assert p.rateReverse is True
        assert p.rateRoll == 2
        # tau_kn will differ (new random draw) but reverse/roll are still applied
        assert p.tau_kn.shape == tau_before.shape


class TestConfigReverseRoll:
    """Config read/write for reverse_sequence and roll_sequence."""

    def test_save_config_includes_reverse_roll(self):
        """saveConfig writes reverse_sequence and roll_sequence under rates_selection."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1970, 1980, reverse=True, roll=3)
        if not hasattr(p, "solverOptions"):
            p.solverOptions = {}
        f = StringIO()
        config.saveConfig(p, f, p.mylog)
        f.seek(0)
        content = f.read()
        assert "reverse_sequence" in content
        assert "roll_sequence" in content
        assert "true" in content.lower() or "True" in content
        assert "3" in content

    def test_read_config_reverse_roll_defaults(self):
        """readConfig defaults reverse_sequence to False and roll_sequence to 0 when missing."""
        toml_content = """
case_name = "test"
description = ""

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
from = 1928
to = 2025

[asset_allocation]
interpolation_method = "linear"
interpolation_center = 15.0
interpolation_width = 5.0
type = "individual"
generic = [[[60, 40, 0, 0], [60, 40, 0, 0]]]

[optimization_parameters]
spending_profile = "flat"
surviving_spouse_spending_percent = 100
objective = "maxSpending"

[solver_options]
withMedicare = "loop"
withSCLoop = true

[results]
default_plots = "today"
"""
        # No reverse_sequence or roll_sequence keys
        p = config.readConfig(StringIO(toml_content), verbose=False, readContributions=False)
        assert p.rateReverse is False
        assert p.rateRoll == 0

    def test_config_roundtrip_reverse_roll(self):
        """Save plan with reverse/roll and reload; reverse and roll are preserved."""
        p = _make_plan_with_historical_rates()
        p.setRates("historical", 1970, 1980, reverse=True, roll=4)
        if not hasattr(p, "solverOptions"):
            p.solverOptions = {}
        f = StringIO()
        config.saveConfig(p, f, p.mylog)
        f.seek(0)
        p2 = config.readConfig(f, verbose=False, readContributions=False)
        assert p2.rateReverse is True
        assert p2.rateRoll == 4
        np.testing.assert_array_almost_equal(p2.tau_kn, p.tau_kn)


class TestConstantRateReverseRollNoOp:
    """Reverse and roll are no-ops for constant (fixed) rate methods; a warning is logged."""

    def _make_plan_with_log(self):
        """Create a plan with a capture log stream."""
        strio = StringIO()
        p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False, logstreams=[strio])
        p.setSpendingProfile("flat")
        p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
        p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
        return p, strio

    def test_default_with_reverse_logs_warning(self):
        """setRates('default', reverse=True) logs warning and leaves tau_kn unchanged."""
        p, strio = self._make_plan_with_log()
        p.setRates("default")
        tau_no_transform = p.tau_kn.copy()
        p.setRates("default", reverse=True)
        log_output = strio.getvalue()
        assert "reverse and roll are ignored" in log_output or "ignored for constant" in log_output
        # For constant rates all columns are identical; reverse leaves it unchanged
        np.testing.assert_array_almost_equal(p.tau_kn, tau_no_transform)

    def test_default_with_roll_logs_warning(self):
        """setRates('default', roll=2) logs warning and leaves tau_kn unchanged."""
        p, strio = self._make_plan_with_log()
        p.setRates("default")
        tau_no_transform = p.tau_kn.copy()
        p.setRates("default", roll=2)
        log_output = strio.getvalue()
        assert "reverse and roll are ignored" in log_output or "ignored for constant" in log_output
        np.testing.assert_array_almost_equal(p.tau_kn, tau_no_transform)

    def test_user_with_reverse_logs_warning(self):
        """setRates('user', ..., reverse=True) logs warning."""
        p, strio = self._make_plan_with_log()
        p.setRates("user", values=[5.0, 3.0, 2.0, 2.5])
        p.setRates("user", values=[5.0, 3.0, 2.0, 2.5], reverse=True)
        log_output = strio.getvalue()
        assert "reverse and roll are ignored" in log_output or "ignored for constant" in log_output

    def test_historical_average_with_roll_logs_warning(self):
        """setRates('historical average', ..., roll=1) logs warning."""
        p, strio = self._make_plan_with_log()
        p.setRates("historical average", 1990, 2000)
        tau_no_transform = p.tau_kn.copy()
        p.setRates("historical average", 1990, 2000, roll=1)
        log_output = strio.getvalue()
        assert "reverse and roll are ignored" in log_output or "ignored for constant" in log_output
        np.testing.assert_array_almost_equal(p.tau_kn, tau_no_transform)
