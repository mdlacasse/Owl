import pytest
import numpy as np
import pandas as pd

from owlplanner import debts


class TestCalculateMonthlyPayment:
    """Tests for calculate_monthly_payment function."""

    def test_standard_loan(self):
        """Test standard 30-year mortgage calculation."""
        principal = 200000
        rate = 4.5
        term = 30
        payment = debts.calculate_monthly_payment(principal, rate, term)
        # Approximate monthly payment for $200k at 4.5% for 30 years
        assert payment == pytest.approx(1013.37, abs=1.0)

    def test_zero_interest(self):
        """Test loan with zero interest rate."""
        principal = 100000
        rate = 0.0
        term = 10
        payment = debts.calculate_monthly_payment(principal, rate, term)
        # Should be principal divided by number of payments
        expected = principal / (term * 12)
        assert payment == pytest.approx(expected, abs=0.01)

    def test_short_term_loan(self):
        """Test short-term loan (5 years)."""
        principal = 50000
        rate = 5.0
        term = 5
        payment = debts.calculate_monthly_payment(principal, rate, term)
        # Should be higher than long-term loan
        assert payment > principal / (term * 12)

    def test_invalid_inputs(self):
        """Test handling of invalid inputs."""
        assert debts.calculate_monthly_payment(0, 4.5, 30) == 0.0
        assert debts.calculate_monthly_payment(100000, -1, 30) == 0.0
        assert debts.calculate_monthly_payment(100000, 4.5, 0) == 0.0
        assert debts.calculate_monthly_payment(100000, 4.5, -5) == 0.0


class TestCalculateAnnualPayment:
    """Tests for calculate_annual_payment function."""

    def test_annual_from_monthly(self):
        """Test that annual payment is 12 times monthly payment."""
        principal = 200000
        rate = 4.5
        term = 30
        monthly = debts.calculate_monthly_payment(principal, rate, term)
        annual = debts.calculate_annual_payment(principal, rate, term)
        assert annual == pytest.approx(monthly * 12, abs=0.01)

    def test_zero_interest_annual(self):
        """Test annual payment with zero interest."""
        principal = 100000
        rate = 0.0
        term = 10
        annual = debts.calculate_annual_payment(principal, rate, term)
        expected = principal / term
        assert annual == pytest.approx(expected, abs=0.01)


class TestCalculateRemainingBalance:
    """Tests for calculate_remaining_balance function."""

    def test_initial_balance(self):
        """Test that remaining balance equals principal at start."""
        principal = 200000
        rate = 4.5
        term = 30
        balance = debts.calculate_remaining_balance(principal, rate, term, 0)
        assert balance == pytest.approx(principal, abs=1.0)

    def test_final_balance(self):
        """Test that remaining balance is zero at end of term."""
        principal = 200000
        rate = 4.5
        term = 30
        balance = debts.calculate_remaining_balance(principal, rate, term, term)
        assert balance == pytest.approx(0.0, abs=1.0)

    def test_balance_after_half_term(self):
        """Test remaining balance after half the term."""
        principal = 200000
        rate = 4.5
        term = 30
        balance = debts.calculate_remaining_balance(principal, rate, term, 15)
        # Should be less than principal but greater than zero
        assert 0 < balance < principal

    def test_zero_interest_balance(self):
        """Test remaining balance with zero interest."""
        principal = 100000
        rate = 0.0
        term = 10
        balance = debts.calculate_remaining_balance(principal, rate, term, 5)
        expected = principal * 0.5  # Linear reduction
        assert balance == pytest.approx(expected, abs=1.0)

    def test_negative_years_elapsed(self):
        """Test that negative years returns principal."""
        principal = 200000
        rate = 4.5
        term = 30
        balance = debts.calculate_remaining_balance(principal, rate, term, -1)
        assert balance == pytest.approx(principal, abs=1.0)

    def test_years_exceeding_term(self):
        """Test that years exceeding term returns zero."""
        principal = 200000
        rate = 4.5
        term = 30
        balance = debts.calculate_remaining_balance(principal, rate, term, 35)
        assert balance == pytest.approx(0.0, abs=1.0)


class TestGetDebtPaymentsForYear:
    """Tests for get_debt_payments_for_year function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame(columns=["name", "type", "year", "term", "amount", "rate"])
        assert debts.get_debt_payments_for_year(df, 2025) == 0.0
        assert debts.get_debt_payments_for_year(None, 2025) == 0.0

    def test_single_active_loan(self):
        """Test with single active loan."""
        df = pd.DataFrame([{
            "name": "mortgage",
            "type": "mortgage",
            "year": 2020,
            "term": 30,
            "amount": 200000,
            "rate": 4.5
        }])
        payment = debts.get_debt_payments_for_year(df, 2025)
        # Should be positive annual payment
        assert payment > 0

    def test_loan_not_active(self):
        """Test with loan that hasn't started yet."""
        df = pd.DataFrame([{
            "name": "mortgage",
            "type": "mortgage",
            "year": 2030,
            "term": 30,
            "amount": 200000,
            "rate": 4.5
        }])
        payment = debts.get_debt_payments_for_year(df, 2025)
        assert payment == 0.0

    def test_loan_already_paid_off(self):
        """Test with loan that's already paid off."""
        df = pd.DataFrame([{
            "name": "mortgage",
            "type": "mortgage",
            "year": 1990,
            "term": 30,
            "amount": 200000,
            "rate": 4.5
        }])
        payment = debts.get_debt_payments_for_year(df, 2025)
        assert payment == 0.0

    def test_multiple_loans(self):
        """Test with multiple active loans."""
        df = pd.DataFrame([
            {
                "name": "mortgage",
                "type": "mortgage",
                "year": 2020,
                "term": 30,
                "amount": 200000,
                "rate": 4.5
            },
            {
                "name": "car_loan",
                "type": "loan",
                "year": 2023,
                "term": 5,
                "amount": 30000,
                "rate": 6.0
            }
        ])
        payment = debts.get_debt_payments_for_year(df, 2025)
        # Should be sum of both loans
        assert payment > 0


class TestGetDebtBalancesForYear:
    """Tests for get_debt_balances_for_year function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame(columns=["name", "type", "year", "term", "amount", "rate"])
        assert debts.get_debt_balances_for_year(df, 2025) == 0.0
        assert debts.get_debt_balances_for_year(None, 2025) == 0.0

    def test_single_active_loan(self):
        """Test with single active loan."""
        df = pd.DataFrame([{
            "name": "mortgage",
            "type": "mortgage",
            "year": 2020,
            "term": 30,
            "amount": 200000,
            "rate": 4.5
        }])
        balance = debts.get_debt_balances_for_year(df, 2025)
        # Should be positive but less than original principal
        assert 0 < balance < 200000

    def test_loan_not_started(self):
        """Test with loan that hasn't started."""
        df = pd.DataFrame([{
            "name": "mortgage",
            "type": "mortgage",
            "year": 2030,
            "term": 30,
            "amount": 200000,
            "rate": 4.5
        }])
        balance = debts.get_debt_balances_for_year(df, 2025)
        assert balance == 0.0

    def test_loan_paid_off(self):
        """Test with loan that's paid off."""
        df = pd.DataFrame([{
            "name": "mortgage",
            "type": "mortgage",
            "year": 1990,
            "term": 30,
            "amount": 200000,
            "rate": 4.5
        }])
        balance = debts.get_debt_balances_for_year(df, 2025)
        assert balance == 0.0


class TestGetDebtPaymentsArray:
    """Tests for get_debt_payments_array function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame(columns=["name", "type", "year", "term", "amount", "rate"])
        result = debts.get_debt_payments_array(df, 10)
        assert len(result) == 10
        assert np.all(result == 0)

    def test_single_loan_full_horizon(self):
        """Test with single loan covering full horizon."""
        df = pd.DataFrame([{
            "name": "mortgage",
            "type": "mortgage",
            "year": 2020,
            "term": 30,
            "amount": 200000,
            "rate": 4.5
        }])
        thisyear = 2025
        N_n = 10
        result = debts.get_debt_payments_array(df, N_n, thisyear)
        assert len(result) == N_n
        # All years should have payments (loan started in 2020, ends in 2050)
        assert np.all(result > 0)

    def test_loan_starting_mid_horizon(self):
        """Test with loan starting in middle of horizon."""
        df = pd.DataFrame([{
            "name": "car_loan",
            "type": "loan",
            "year": 2028,
            "term": 5,
            "amount": 30000,
            "rate": 6.0
        }])
        thisyear = 2025
        N_n = 10
        result = debts.get_debt_payments_array(df, N_n, thisyear)
        assert len(result) == N_n
        # First 3 years should be zero, next 5 should have payments
        assert np.all(result[:3] == 0)
        assert np.all(result[3:8] > 0)
        assert np.all(result[8:] == 0)

    def test_loan_ending_mid_horizon(self):
        """Test with loan ending in middle of horizon."""
        df = pd.DataFrame([{
            "name": "car_loan",
            "type": "loan",
            "year": 2020,
            "term": 5,
            "amount": 30000,
            "rate": 6.0
        }])
        thisyear = 2025
        N_n = 10
        result = debts.get_debt_payments_array(df, N_n, thisyear)
        assert len(result) == N_n
        # Loan ends in 2025, so first year might have payment, rest should be zero
        # Actually, if year=2020 and term=5, loan ends in 2025, so year 2025 is not active
        assert result[0] == 0.0
        assert np.all(result[1:] == 0)

    def test_multiple_loans(self):
        """Test with multiple loans."""
        df = pd.DataFrame([
            {
                "name": "mortgage",
                "type": "mortgage",
                "year": 2020,
                "term": 30,
                "amount": 200000,
                "rate": 4.5
            },
            {
                "name": "car_loan",
                "type": "loan",
                "year": 2026,
                "term": 5,
                "amount": 30000,
                "rate": 6.0
            }
        ])
        thisyear = 2025
        N_n = 10
        result = debts.get_debt_payments_array(df, N_n, thisyear)
        assert len(result) == N_n
        # First year should have mortgage payment
        assert result[0] > 0
        # Year 1 (2026) should have both payments
        assert result[1] > result[0]


class TestGetRemainingDebtBalance:
    """Tests for get_remaining_debt_balance function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame(columns=["name", "type", "year", "term", "amount", "rate"])
        assert debts.get_remaining_debt_balance(df, 10) == 0.0
        assert debts.get_remaining_debt_balance(None, 10) == 0.0

    def test_all_loans_paid_off(self):
        """Test when all loans are paid off by end of plan."""
        df = pd.DataFrame([{
            "name": "car_loan",
            "type": "loan",
            "year": 2020,
            "term": 5,
            "amount": 30000,
            "rate": 6.0
        }])
        thisyear = 2025
        N_n = 10
        # Loan ends in 2025, plan ends in 2034, so loan is paid off
        balance = debts.get_remaining_debt_balance(df, N_n, thisyear)
        assert balance == 0.0

    def test_loan_still_active(self):
        """Test when loan is still active at end of plan."""
        df = pd.DataFrame([{
            "name": "mortgage",
            "type": "mortgage",
            "year": 2020,
            "term": 30,
            "amount": 200000,
            "rate": 4.5
        }])
        thisyear = 2025
        N_n = 10
        # Loan ends in 2050, plan ends in 2034, so loan is still active
        balance = debts.get_remaining_debt_balance(df, N_n, thisyear)
        assert balance > 0

    def test_loan_starting_after_plan(self):
        """Test when loan starts after plan ends."""
        df = pd.DataFrame([{
            "name": "mortgage",
            "type": "mortgage",
            "year": 2040,
            "term": 30,
            "amount": 200000,
            "rate": 4.5
        }])
        thisyear = 2025
        N_n = 10
        # Loan starts in 2040, plan ends in 2034, so loan hasn't started
        balance = debts.get_remaining_debt_balance(df, N_n, thisyear)
        assert balance == 0.0

    def test_multiple_loans_mixed(self):
        """Test with multiple loans, some paid off, some active."""
        df = pd.DataFrame([
            {
                "name": "car_loan",
                "type": "loan",
                "year": 2020,
                "term": 5,
                "amount": 30000,
                "rate": 6.0
            },
            {
                "name": "mortgage",
                "type": "mortgage",
                "year": 2020,
                "term": 30,
                "amount": 200000,
                "rate": 4.5
            }
        ])
        thisyear = 2025
        N_n = 10
        balance = debts.get_remaining_debt_balance(df, N_n, thisyear)
        # Only mortgage should have remaining balance
        assert balance > 0
        # Should be less than full mortgage principal
        assert balance < 200000
