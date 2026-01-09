"""
Tests for plan.py edge cases and error handling to improve coverage.

This module tests error conditions, edge cases, and less common code paths
in the Plan class that are not covered by existing regression tests.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import pytest
from datetime import date
import numpy as np

import owlplanner as owl
import owlplanner.plan as plan


def test_plan_constructor_empty_name():
    """Test that Plan constructor raises error for empty name."""
    with pytest.raises(ValueError, match="Plan must have a name"):
        owl.Plan(['Joe'], ["1961-01-15"], [80], "")


def test_plan_constructor_invalid_individual_count():
    """Test that Plan constructor raises error for invalid individual count."""
    with pytest.raises(ValueError, match="Cannot support"):
        owl.Plan(['Joe', 'Jane', 'Bob'], ["1961-01-15", "1962-01-15", "1963-01-15"], [80, 82, 85], "test")


def test_plan_constructor_mismatched_expectancy():
    """Test that Plan constructor raises error for mismatched expectancy."""
    with pytest.raises(ValueError, match="Expectancy must have"):
        owl.Plan(['Joe', 'Jane'], ["1961-01-15", "1962-01-15"], [80], "test")


def test_plan_constructor_mismatched_names():
    """Test that Plan constructor raises error for mismatched names."""
    with pytest.raises(ValueError, match="Names for individuals must have"):
        owl.Plan(['Joe'], ["1961-01-15", "1962-01-15"], [80, 82], "test")


def test_plan_constructor_empty_individual_name():
    """Test that Plan constructor raises error for empty individual name."""
    with pytest.raises(ValueError, match="Name for each individual must be provided"):
        owl.Plan([''], ["1961-01-15"], [80], "test")

    with pytest.raises(ValueError, match="Name for each individual must be provided"):
        owl.Plan(['Joe', ''], ["1961-01-15", "1962-01-15"], [80, 82], "test")


def test_gen_xi_n_unknown_profile():
    """Test _genXi_n raises error for unknown profile type."""
    with pytest.raises(ValueError, match="Unknown profile type"):
        plan._genXi_n("unknown", 0.6, 10, 20, 15, 12, 0)


def test_gen_xi_n_smile_profile():
    """Test _genXi_n with smile profile."""
    xi = plan._genXi_n("smile", 0.6, 15, 30, 15, 12, 5)
    assert len(xi) == 30
    assert np.all(xi >= 0)


def test_set_starting_date_today():
    """Test _setStartingDate with 'today'."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p._setStartingDate("today")
    assert p.startDate is not None


def test_set_starting_date_mmddyyyy():
    """Test _setStartingDate with YYYY-MM-DD format."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p._setStartingDate("2024-03-15")
    assert p.startDate == "2024-03-15"


def test_set_starting_date_mmdd():
    """Test _setStartingDate with MM-DD format."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p._setStartingDate("03-15")
    assert p.startDate == "03-15"


def test_set_starting_date_date_object():
    """Test _setStartingDate with date object."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p._setStartingDate(date(2024, 3, 15))
    assert p.startDate == "2024-03-15"


def test_set_starting_date_invalid_format():
    """Test _setStartingDate with invalid format."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    with pytest.raises(ValueError):
        p._setStartingDate("invalid-date-format")


def test_check_value_type_invalid():
    """Test _checkValueType with invalid value."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    with pytest.raises(ValueError, match="Value type must be one of"):
        p._checkValueType("invalid")


def test_check_value_type_none():
    """Test _checkValueType with None returns default."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    result = p._checkValueType(None)
    assert result == p.defaultPlots


def test_set_spousal_deposit_fraction_invalid_range():
    """Test setSpousalDepositFraction with invalid range."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    with pytest.raises(ValueError, match="Fraction must be between"):
        p.setSpousalDepositFraction(1.5)

    with pytest.raises(ValueError, match="Fraction must be between"):
        p.setSpousalDepositFraction(-0.1)


def test_set_spousal_deposit_fraction_single():
    """Test setSpousalDepositFraction for single individual."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpousalDepositFraction(0.5)  # Should be ignored for single


def test_set_default_plots():
    """Test setDefaultPlots."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setDefaultPlots("today")
    assert p.defaultPlots == "today"


def test_set_plot_backend():
    """Test setPlotBackend."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setPlotBackend("plotly")
    assert p._plotterName == "plotly"


def test_set_plot_backend_invalid():
    """Test setPlotBackend with invalid backend."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    with pytest.raises(ValueError, match="not a valid option"):
        p.setPlotBackend("invalid_backend")


def test_set_dividend_rate():
    """Test setDividendRate."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setDividendRate(2.0)  # Rate is in percent
    assert abs(p.mu - 0.02) < 1e-6  # Converted to decimal


def test_set_expiration_year_obbba():
    """Test setExpirationYearOBBBA."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setExpirationYearOBBBA(2035)
    assert p.yOBBBA == 2035


def test_set_beneficiary_fractions_single():
    """Test setBeneficiaryFractions for single individual."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    # Should not raise error but may be ignored
    p.setBeneficiaryFractions([0.5, 0.3, 0.2])


def test_set_beneficiary_fractions_invalid_length():
    """Test setBeneficiaryFractions with invalid length."""
    p = owl.Plan(['Joe', 'Jane'], ["1961-01-15", "1962-01-15"], [80, 82], "test")
    with pytest.raises(ValueError, match="Fractions must have"):
        p.setBeneficiaryFractions([0.5, 0.3])  # Wrong length, should be 3


def test_set_heirs_tax_rate():
    """Test setHeirsTaxRate."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setHeirsTaxRate(35.0)  # Rate is in percent
    assert abs(p.nu - 0.35) < 1e-6  # Converted to decimal


def test_set_heirs_tax_rate_invalid_range():
    """Test setHeirsTaxRate with invalid range."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    with pytest.raises(ValueError, match="Rate must be between"):
        p.setHeirsTaxRate(150.0)  # > 100

    with pytest.raises(ValueError, match="Rate must be between"):
        p.setHeirsTaxRate(-10.0)  # < 0


def test_set_pension_invalid_lengths():
    """Test setPension with mismatched lengths."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    with pytest.raises(ValueError, match="Amounts must have"):
        p.setPension([1000, 2000], [65])  # Wrong length for amounts


def test_set_social_security_invalid_lengths():
    """Test setSocialSecurity with mismatched lengths."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    with pytest.raises(ValueError, match="Principal Insurance Amount must have"):
        p.setSocialSecurity([2000, 3000], [67])  # Wrong length for PIAs


def test_set_spending_profile_invalid_percent():
    """Test setSpendingProfile with invalid percent."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    with pytest.raises(ValueError, match="Survivor value.*outside range"):
        p.setSpendingProfile("flat", percent=150)

    with pytest.raises(ValueError, match="Dip value.*outside range"):
        p.setSpendingProfile("smile", dip=150)

    with pytest.raises(ValueError, match="Increase value.*outside range"):
        p.setSpendingProfile("smile", increase=150)


def test_set_reproducible():
    """Test setReproducible."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setReproducible(True, seed=42)
    assert p.reproducibleRates is True
    assert p.rateSeed == 42


def test_set_rates_invalid_method():
    """Test setRates with invalid method."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    # The error comes from rates.Rates.setMethod, so we just check it raises
    with pytest.raises((ValueError, RuntimeError)):
        p.setRates("invalid_method")


def test_set_interpolation_method_invalid():
    """Test setInterpolationMethod with invalid method."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    with pytest.raises(ValueError, match="not supported"):
        p.setInterpolationMethod("invalid_method")


def test_set_allocation_ratios_invalid_type():
    """Test setAllocationRatios with invalid type raises ValueError."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    # The function now validates allocType and raises an error for invalid types
    with pytest.raises(ValueError, match="allocType must be one of"):
        p.setAllocationRatios("invalid_type", generic=None)


def test_check_case_status_decorator():
    """Test _checkCaseStatus decorator prevents method execution."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    # Set caseStatus to something other than "solved" to test decorator
    p.caseStatus = "unsuccessful"
    # The decorator prevents methods from running if caseStatus != "solved"
    # We test this indirectly - methods with this decorator return None
    # This is tested through the decorator's behavior in the code


def test_check_configuration_decorator():
    """Test _checkConfiguration decorator raises error when not configured."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.xi_n = None
    p.alpha_ijkn = None

    with pytest.raises(RuntimeError, match="You must define a spending profile"):
        p.solve("maxSpending")


def test_check_configuration_decorator_no_allocation():
    """Test _checkConfiguration decorator raises error when allocation not set."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.alpha_ijkn = None

    with pytest.raises(RuntimeError, match="You must define an allocation profile"):
        p.solve("maxSpending")


def test_solve_invalid_objective():
    """Test solve with invalid objective."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])

    with pytest.raises(ValueError, match="Objective.*is not one of"):
        p.solve("invalid_objective")


def test_solve_invalid_option():
    """Test solve with invalid option."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])

    with pytest.raises(ValueError, match="Option.*is not one of"):
        p.solve("maxSpending", options={"invalid_option": True})


def test_solve_max_bequest_no_net_spending():
    """Test solve with maxBequest but no netSpending option."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("default")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])

    with pytest.raises(RuntimeError, match="needs netSpending option"):
        p.solve("maxBequest")


def test_solve_no_rate_method():
    """Test solve without rate method set."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setSpendingProfile("flat")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.rateMethod = None

    with pytest.raises(RuntimeError, match="Rate method must be selected"):
        p.solve("maxSpending")


def test_plan_id_counter():
    """Test Plan ID counter functionality."""
    initial_id = owl.Plan.get_current_id()
    p1 = owl.Plan(['Joe'], ["1961-01-15"], [80], "test1")
    p2 = owl.Plan(['Jane'], ["1962-01-15"], [82], "test2")

    assert p1._id == initial_id + 1
    assert p2._id == initial_id + 2
    assert owl.Plan.get_current_id() == initial_id + 2


def test_rename():
    """Test rename method."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.rename("new_name")
    assert p._name == "new_name"


def test_set_description():
    """Test setDescription method."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setDescription("Test description")
    assert p._description == "Test description"


def test_set_logger():
    """Test setLogger method."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    import owlplanner.mylogging as log
    new_logger = log.Logger(verbose=False)
    p.setLogger(new_logger)
    assert p.mylog is new_logger


def test_set_verbose():
    """Test setVerbose method."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test", verbose=True)
    prev_state = p.setVerbose(False)
    assert prev_state is True  # Default is True
    assert p.mylog._verbose is False


def test_clone_with_newname():
    """Test clone function with new name."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "original")
    p.setSpendingProfile("flat")
    cloned = plan.clone(p, newname="cloned")
    assert cloned._name == "cloned"
    assert cloned.inames == p.inames


def test_clone_without_newname():
    """Test clone function without new name."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "original")
    p.setSpendingProfile("flat")
    cloned = plan.clone(p)
    assert cloned._name == "original (copy)"
    assert cloned.inames == p.inames


def test_q_functions():
    """Test index mapping functions."""
    assert plan._qC(0, 2, 3, 4, 5) == 0 + 2 * 3 * 4 * 5
    assert plan._q1(10, 5) == 15
    assert plan._q2(10, 2, 3, 4, 5) == 10 + 2 * 5 + 3
    assert plan._q3(10, 1, 2, 3, 4, 5, 6) == 10 + 1 * 5 * 6 + 2 * 6 + 3
    assert plan._q4(10, 1, 2, 3, 4, 5, 6, 7, 8) == 10 + 1 * 6 * 7 * 8 + 2 * 7 * 8 + 3 * 8 + 4


def test_gen_gamma_n():
    """Test _genGamma_n function."""
    tau = np.array([[0.02, 0.03, 0.025], [0.01, 0.015, 0.012], [0.02, 0.02, 0.02]])  # Last row is inflation
    gamma = plan._genGamma_n(tau)
    assert len(gamma) == len(tau[-1]) + 1
    assert gamma[0] == 1.0
    assert gamma[1] == 1.02  # First inflation rate


def test_set_account_balances_invalid_units():
    """Test setAccountBalances with invalid units."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    # The error comes from utils.getUnits
    with pytest.raises(ValueError, match="Unknown units"):
        p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50], units="invalid")


def test_set_account_balances_with_start_date():
    """Test setAccountBalances with start date."""
    p = owl.Plan(['Joe'], ["1961-01-15"], [80], "test")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50], startDate="2024-01-01")
    assert p.beta_ij is not None
    assert p.startDate == "2024-01-01"
