"""

Owl/debts

This file contains functions for handling debts.

Copyright &copy; 2025 - Martin-D. Lacasse

Disclaimers: This code is for educational purposes only and does not constitute financial advice.

"""

######################################################################
import numpy as np
import pandas as pd
from datetime import date


def calculate_monthly_payment(principal, annual_rate, term_years):
    """
    Calculate monthly payment for an amortizing loan. This is a constant payment amount for a fixed-rate loan.
    monthly payment = principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
    where monthly_rate = annual_rate / 100.0 / 12.0 and num_payments = term_years * 12.0.

    This formula is derived from the formula for the present value of an annuity.

    Parameters:
    -----------
    principal : float
        Original loan amount
    annual_rate : float
        Annual interest rate as a percentage (e.g., 4.5 for 4.5%)
    term_years : int
        Loan term in years

    Returns:
    --------
    float
        Monthly payment amount
    """
    if term_years <= 0 or annual_rate < 0 or principal <= 0:
        return 0.0

    monthly_rate = annual_rate / 100.0 / 12.0
    num_payments = term_years * 12
    fac = (1 + monthly_rate)**num_payments

    if monthly_rate == 0:
        return principal / num_payments

    payment = principal * (monthly_rate * fac) / (fac - 1)

    return payment


def calculate_annual_payment(principal, annual_rate, term_years):
    """
    Calculate annual payment for an amortizing loan.

    Parameters:
    -----------
    principal : float
        Original loan amount
    annual_rate : float
        Annual interest rate as a percentage
    term_years : int
        Loan term in years

    Returns:
    --------
    float
        Annual payment amount
    """
    return 12 * calculate_monthly_payment(principal, annual_rate, term_years)


def calculate_remaining_balance(principal, annual_rate, term_years, years_elapsed):
    """
    Calculate remaining balance on a loan after a given number of years.

    Parameters:
    -----------
    principal : float
        Original loan amount
    annual_rate : float
        Annual interest rate as a percentage
    term_years : int
        Original loan term in years
    years_elapsed : float
        Number of years since loan origination

    Returns:
    --------
    float
        Remaining balance
    """
    if years_elapsed <= 0:
        return principal

    if years_elapsed >= term_years:
        return 0.0

    monthly_rate = annual_rate / 100.0 / 12.0
    fac = 1 + monthly_rate
    num_payments = term_years * 12
    payments_made = int(years_elapsed * 12)

    if monthly_rate == 0:
        return principal * (1 - payments_made / num_payments)

    remaining = principal * (fac**num_payments - fac**payments_made) / (fac**num_payments - 1)

    return max(0.0, remaining)


def get_debt_payments_for_year(debts_df, year):
    """
    Calculate total debt payments (principal + interest) for a given year.

    Parameters:
    -----------
    debts_df : pd.DataFrame
        DataFrame with columns: name, type, year, term, amount, rate
    year : int
        Year for which to calculate payments

    Returns:
    --------
    float
        Total annual debt payments for the year
    """
    if debts_df is None or debts_df.empty:
        return 0.0

    total_payments = 0.0

    for _, debt in debts_df.iterrows():
        start_year = int(debt["year"])
        term = int(debt["term"])
        end_year = start_year + term

        # Check if loan is active in this year
        if start_year <= year < end_year:
            principal = float(debt["amount"])
            rate = float(debt["rate"])

            # Calculate annual payment (payment amount is constant for fixed-rate loans)
            annual_payment = calculate_annual_payment(principal, rate, term)
            total_payments += annual_payment

    return total_payments


def get_debt_balances_for_year(debts_df, year):
    """
    Calculate total remaining debt balances at the end of a given year.

    Parameters:
    -----------
    debts_df : pd.DataFrame
        DataFrame with columns: name, type, year, term, amount, rate
    year : int
        Year for which to calculate balances

    Returns:
    --------
    float
        Total remaining debt balances at end of year
    """
    if debts_df is None or debts_df.empty:
        return 0.0

    total_balance = 0.0

    for _, debt in debts_df.iterrows():
        start_year = int(debt["year"])
        term = int(debt["term"])
        end_year = start_year + term

        # Check if loan is active at end of this year
        if start_year <= year < end_year:
            principal = float(debt["amount"])
            rate = float(debt["rate"])

            # Calculate remaining balance at end of year
            years_elapsed = year - start_year + 1
            remaining_balance = calculate_remaining_balance(principal, rate, term, years_elapsed)
            total_balance += remaining_balance

    return total_balance


def get_debt_payments_array(debts_df, N_n, thisyear=None):
    """
    Process debts_df to provide a single array of length N_n containing
    all annual payments made for each year of the plan.

    Parameters:
    -----------
    debts_df : pd.DataFrame
        DataFrame with columns: name, type, year, term, amount, rate
    N_n : int
        Number of years in the plan (length of output array)
    thisyear : int, optional
        Starting year of the plan (defaults to date.today().year).
        Array index 0 corresponds to thisyear, index 1 to thisyear+1, etc.

    Returns:
    --------
    np.ndarray
        Array of length N_n with annual debt payments for each year.
        payments_n[0] = payments for thisyear,
        payments_n[1] = payments for thisyear+1, etc.
    """
    if thisyear is None:
        thisyear = date.today().year

    if debts_df is None or debts_df.empty:
        return np.zeros(N_n)

    payments_n = np.zeros(N_n)

    for _, debt in debts_df.iterrows():
        start_year = int(debt["year"])
        term = int(debt["term"])
        end_year = start_year + term
        principal = float(debt["amount"])
        rate = float(debt["rate"])

        # Calculate annual payment (payment amount is constant for fixed-rate loans)
        annual_payment = calculate_annual_payment(principal, rate, term)

        # Add payments for each year the loan is active within the plan horizon
        for n in range(N_n):
            year = thisyear + n
            if start_year <= year < end_year:
                payments_n[n] += annual_payment

    return payments_n


def get_remaining_debt_balance(debts_df, N_n, thisyear=None):
    """
    Calculate total remaining debt balance at the end of the plan horizon.
    Returns the sum of all remaining balances for loans that haven't been
    fully paid off by the end of the plan.

    Parameters:
    -----------
    debts_df : pd.DataFrame
        DataFrame with columns: name, type, year, term, amount, rate
    N_n : int
        Number of years in the plan
    thisyear : int, optional
        Starting year of the plan (defaults to date.today().year)

    Returns:
    --------
    float
        Total remaining debt balance at the end of the plan horizon.
        Returns 0.0 if all loans are paid off or if no loans are active.
    """
    if thisyear is None:
        thisyear = date.today().year

    if debts_df is None or debts_df.empty:
        return 0.0

    end_year = thisyear + N_n - 1
    total_balance = 0.0

    for _, debt in debts_df.iterrows():
        start_year = int(debt["year"])
        term = int(debt["term"])
        loan_end_year = start_year + term
        principal = float(debt["amount"])
        rate = float(debt["rate"])

        # Check if loan is still active at the end of the plan
        if start_year <= end_year < loan_end_year:
            # Calculate remaining balance at end of plan horizon
            years_elapsed = end_year - start_year + 1
            remaining_balance = calculate_remaining_balance(principal, rate, term, years_elapsed)
            total_balance += remaining_balance

    return total_balance
