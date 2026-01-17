"""
Fixed assets management and tax calculation module.

This module provides functions for handling fixed assets (such as real estate)
and calculating tax implications when they are sold or disposed of, including
primary residence exclusion rules.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

######################################################################
import numpy as np
import pandas as pd  # noqa: F401
from datetime import date

from . import utils as u


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
        DataFrame with columns: name, type, year, basis, value, rate, yod, commission
        where 'year' is the reference year (this year or after). Basis and
        value are in reference-year dollars.
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

    if u.is_dataframe_empty(fixed_assets_df):
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
        # Skip if active column exists and is False (treat NaN/None as True)
        if not u.is_row_active(asset):
            continue

        asset_type = str(asset["type"]).lower()
        basis = float(asset["basis"])
        value_at_reference = float(asset["value"])  # Value at reference year
        annual_rate = float(asset["rate"])
        # Get reference year, defaulting to thisyear for backward compatibility
        if "year" in asset.index and not pd.isna(asset["year"]):
            reference_year = int(asset["year"])
        else:
            reference_year = thisyear
        yod = int(asset["yod"])  # Year of disposition
        commission_pct = float(asset["commission"]) / 100.0

        end_year = thisyear + N_n - 1  # Last year of the plan

        # Skip if asset reference year is after the plan ends
        if reference_year > end_year:
            continue

        # Account for negative or null yod with reference to end of plan
        if yod <= 0:
            yod = end_year + yod + 1

        # Skip if disposition is before reference year (invalid)
        if yod < reference_year:
            continue

        # Skip if disposition is before the plan starts
        if yod < thisyear:
            continue

        # Only process assets disposed during the plan (yod <= end_year)
        # IMPORTANT: Assets with yod > end_year are NOT processed here to avoid double counting.
        # They are handled separately in get_fixed_assets_bequest_value().
        if yod > end_year:
            continue

        # Disposition at beginning of yod (within plan duration)
        n = yod - thisyear
        # Asset assessed at beginning of reference_year, disposed at beginning of yod
        # Growth period: from start of reference_year to start of yod = (yod - reference_year) years
        years_from_reference_to_disposition = yod - reference_year

        # Calculate future value at disposition
        future_value = calculate_future_value(value_at_reference, annual_rate, years_from_reference_to_disposition)

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
        DataFrame with columns: name, type, year, basis, value, rate, yod, commission
        where 'year' is the reference year (this year or after). Basis and
        value are in reference-year dollars.
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

    if u.is_dataframe_empty(fixed_assets_df):
        return 0.0

    end_year = thisyear + N_n - 1  # Last year of the plan
    total_bequest_value = 0.0

    for _, asset in fixed_assets_df.iterrows():
        # Skip if active column exists and is False (treat NaN/None as True)
        if not u.is_row_active(asset):
            continue

        # Get reference year, defaulting to thisyear for backward compatibility
        if "year" in asset.index and not pd.isna(asset["year"]):
            reference_year = int(asset["year"])
        else:
            reference_year = thisyear
        yod = int(asset["yod"])  # Year of disposition

        # Skip if asset reference year is after the plan ends
        if reference_year > end_year:
            continue

        # Account for negative or null yod with reference to end of plan
        if yod <= 0:
            yod = end_year + yod + 1

        # Skip if disposition is before reference year (invalid)
        if yod < reference_year:
            continue

        # Only consider assets with yod past the end of the plan (not disposed during the plan)
        # IMPORTANT: Assets with yod <= end_year are NOT processed here to avoid double counting.
        # They are handled separately in get_fixed_assets_arrays() where they are disposed during the plan.
        # These assets (yod > end_year) are assumed to be liquidated at the end of the plan and added to the bequest
        if yod > end_year:
            value_at_reference = float(asset["value"])  # Value at reference year
            annual_rate = float(asset["rate"])
            commission_pct = float(asset["commission"]) / 100.0

            # Calculate future value at the end of the plan
            # Asset assessed at beginning of reference_year, liquidated at end of end_year
            # Growth period: from start of reference_year to end of end_year = (end_year - reference_year + 1) years
            years_from_reference_to_end = end_year - reference_year + 1
            future_value = calculate_future_value(value_at_reference, annual_rate, years_from_reference_to_end)

            # Calculate proceeds after commission
            commission_amount = future_value * commission_pct
            proceeds = future_value - commission_amount

            # Add to total bequest value (full proceeds, no tax - step-up in basis for heirs)
            total_bequest_value += proceeds

    return total_bequest_value
