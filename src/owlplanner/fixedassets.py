"""

Owl/fixed_assets

This file contains functions for handling fixed assets and calculating
tax implications when they are sold or disposed of.

Copyright &copy; 2025 - Martin-D. Lacasse

Disclaimers: This code is for educational purposes only and does not constitute financial advice.

"""

######################################################################
import numpy as np
import pandas as pd  # noqa: F401
from datetime import date


# Primary residence exclusion limits (2025 tax year)
RESIDENCE_EXCLUSION_SINGLE = 250000
RESIDENCE_EXCLUSION_MARRIED = 500000


def calculate_future_value(current_value, annual_rate, years):
    """
    Calculate future value of an asset after a given number of years.

    Parameters:
    -----------
    current_value : float
        Current value of the asset
    annual_rate : float
        Annual growth rate as a percentage
    years : float
        Number of years to grow

    Returns:
    --------
    float
        Future value of the asset
    """
    if years <= 0:
        return current_value

    growth_factor = (1 + annual_rate / 100.0) ** years
    return current_value * growth_factor


def get_fixed_assets_arrays(fixed_assets_df, N_n, thisyear=None, filing_status="single"):
    """
    Process fixed_assets_df to provide three arrays of length N_n containing:
    1) tax-free money, 2) ordinary income money, and 3) capital gains.

    Parameters:
    -----------
    fixed_assets_df : pd.DataFrame
        DataFrame with columns: name, type, basis, value, rate, yod, commission
    N_n : int
        Number of years in the plan (length of output arrays)
    thisyear : int, optional
        Starting year of the plan (defaults to date.today().year).
        Array index 0 corresponds to thisyear, index 1 to thisyear+1, etc.
    filing_status : str, optional
        Filing status: "single" or "married" (defaults to "single").
        Affects primary residence exclusion limits.

    Returns:
    --------
    tuple of np.ndarray
        Three arrays of length N_n:
        - tax_free_n: Tax-free proceeds from asset sales
        - ordinary_income_n: Ordinary income from asset sales (e.g., annuities)
        - capital_gains_n: Capital gains from asset sales
    """
    if thisyear is None:
        thisyear = date.today().year

    if fixed_assets_df is None or fixed_assets_df.empty:
        return np.zeros(N_n), np.zeros(N_n), np.zeros(N_n)

    tax_free_n = np.zeros(N_n)
    ordinary_income_n = np.zeros(N_n)
    capital_gains_n = np.zeros(N_n)

    # Determine residence exclusion limit
    if filing_status == "married":
        residence_exclusion = RESIDENCE_EXCLUSION_MARRIED
    else:
        residence_exclusion = RESIDENCE_EXCLUSION_SINGLE

    for _, asset in fixed_assets_df.iterrows():
        asset_type = str(asset["type"]).lower()
        basis = float(asset["basis"])
        current_value = float(asset["value"])
        annual_rate = float(asset["rate"])
        yod = int(asset["yod"])  # Year of disposition
        commission_pct = float(asset["commission"]) / 100.0

        # Find the year index in the plan
        if yod < thisyear or yod >= thisyear + N_n:
            # Asset disposition is outside the plan horizon
            continue

        n = yod - thisyear

        # Calculate future value at disposition
        years_to_disposition = yod - thisyear
        future_value = calculate_future_value(current_value, annual_rate, years_to_disposition)

        # Calculate proceeds after commission
        commission_amount = future_value * commission_pct
        proceeds = future_value - commission_amount

        # Calculate gain (or loss)
        gain = proceeds - basis

        if asset_type == "fixed annuity":
            # Annuities are taxed as ordinary income
            if gain > 0:
                ordinary_income_n[n] += gain
            # Basis is returned tax-free (even if there's a loss)
            tax_free_n[n] += basis
        elif asset_type == "residence":
            # Primary residence: exclusion up to $250k/$500k
            if gain > 0:
                taxable_gain = max(0, gain - residence_exclusion)
                if taxable_gain > 0:
                    capital_gains_n[n] += taxable_gain
                # Excluded gain is tax-free
                tax_free_n[n] += basis + min(gain, residence_exclusion)
            else:
                # Loss or no gain: proceeds are tax-free
                tax_free_n[n] += proceeds
        elif asset_type in ["collectibles", "precious metals"]:
            # Collectibles and precious metals: special capital gains treatment
            # (28% max rate, but we just report as capital gains here)
            if gain > 0:
                capital_gains_n[n] += gain
                tax_free_n[n] += basis
            else:
                # Loss: only proceeds are tax-free
                tax_free_n[n] += proceeds
        elif asset_type in ["real estate", "stocks"]:
            # Real estate and stocks: standard capital gains
            if gain > 0:
                capital_gains_n[n] += gain
                tax_free_n[n] += basis
            else:
                # Loss: only proceeds are tax-free
                tax_free_n[n] += proceeds
        else:
            # Unknown type: treat as capital gains
            if gain > 0:
                capital_gains_n[n] += gain
                tax_free_n[n] += basis
            else:
                # Loss: only proceeds are tax-free
                tax_free_n[n] += proceeds

    return tax_free_n, ordinary_income_n, capital_gains_n


def get_fixed_assets_bequest_value(fixed_assets_df, N_n, thisyear=None):
    """
    Calculate the total bequest value from fixed assets that have a yod
    (year of disposition) past the end of the plan. These assets are assumed
    to be liquidated at the end of the plan and added to the bequest.

    Parameters:
    -----------
    fixed_assets_df : pd.DataFrame
        DataFrame with columns: name, type, basis, value, rate, yod, commission
    N_n : int
        Number of years in the plan
    thisyear : int, optional
        Starting year of the plan (defaults to date.today().year)

    Returns:
    --------
    float
        Total proceeds (after commission) from assets liquidated at end of plan.
        This represents the total value added to the bequest. No taxes are applied
        as assets are assumed to pass to heirs with step-up in basis.
    """
    if thisyear is None:
        thisyear = date.today().year

    if fixed_assets_df is None or fixed_assets_df.empty:
        return 0.0

    years_to_end = N_n - 1  # Years from start to end of plan
    total_bequest_value = 0.0

    for _, asset in fixed_assets_df.iterrows():
        yod = int(asset["yod"])  # Year of disposition

        # Only consider assets with yod past the end of the plan
        if yod >= thisyear + N_n:
            current_value = float(asset["value"])
            annual_rate = float(asset["rate"])
            commission_pct = float(asset["commission"]) / 100.0

            # Calculate future value at the end of the plan
            future_value = calculate_future_value(current_value, annual_rate, years_to_end)

            # Calculate proceeds after commission
            commission_amount = future_value * commission_pct
            proceeds = future_value - commission_amount

            # Add to total bequest value (full proceeds, no tax)
            total_bequest_value += proceeds

    return total_bequest_value
