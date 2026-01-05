"""
Social Security benefit calculation rules and utilities.

This module implements Social Security rules including full retirement age
calculations, benefit computations, and related retirement planning functions.

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

import numpy as np


def getFRAs(yobs):
    """
    Return full retirement age (FRA) based on birth year.

    The FRA is determined by birth year according to Social Security rules:
    - Birth year >= 1960: FRA is 67
    - Birth year < 1960: FRA increases by 2 months for each year after 1954

    Parameters
    ----------
    yobs : array-like
        Array of birth years, one for each individual.

    Returns
    -------
    numpy.ndarray
        Array of FRA values in fractional years (1/12 increments), one for each individual.
        Ages are returned in Social Security age format. Comparisons to FRA should be
        done using Social Security age (which accounts for birthday-on-first adjustments).
    """
    fras = np.zeros(len(yobs))

    for i in range(len(yobs)):
        if yobs[i] >= 1960:
            fras[i] = 67
        else:
            mo = max(0, 2*(yobs[i] - 1954))
            fras[i] = 66 + mo/12

    return fras


def getSpousalBenefits(pias):
    """
    Compute the maximum spousal benefit amount for each individual.

    The spousal benefit is calculated as 50% of the spouse's Primary Insurance Amount (PIA),
    minus the individual's own PIA. The result is the additional benefit the individual
    would receive as a spouse, which cannot be negative.

    Note: This calculation is not affected by which day of the month is the birthday.

    Parameters
    ----------
    pias : array-like
        Array of Primary Insurance Amounts (monthly benefit at FRA), one for each individual.
        Must have exactly 1 or 2 entries.

    Returns
    -------
    numpy.ndarray
        Array of spousal benefit amounts (monthly), one for each individual.
        For a single individual, returns [0].
        For two individuals, returns the additional spousal benefit each would receive
        (which is max(0, 0.5 * spouse_PIA - own_PIA)).

    Raises
    ------
    ValueError
        If the pias array does not have exactly 1 or 2 entries.
    """
    icount = len(pias)
    benefits = np.zeros(icount)
    if icount == 1:
        return benefits
    elif icount == 2:
        for i in range(2):
            j = (i+1) % 2
            benefits[i] = max(0, 0.5*pias[j] - pias[i])
    else:
        raise ValueError(f"PIAs array cannot have {icount} entries.")

    return benefits


def getSelfFactor(fra, convage, bornOnFirstDays):
    """
    Return the reduction/increase factor to multiply PIA based on claiming age.

    This function calculates the adjustment factor for self benefits based on when
    Social Security benefits start relative to Full Retirement Age (FRA):
    - Before FRA: Benefits are reduced (minimum 70% at age 62)
    - At FRA: Full benefit (100% of PIA)
    - After FRA: Benefits are increased by 8% per year (up to 132% at age 70)

    The function automatically adjusts for Social Security age if the birthday is on
    the 1st or 2nd day of the month (adds 1/12 year to conventional age), consistent
    with SSA rules that treat both days the same for age calculation purposes.

    Parameters
    ----------
    fra : float
        Full Retirement Age in years (can be fractional with 1/12 increments).
    convage : float
        Conventional age when benefits start, in years (can be fractional with 1/12 increments).
        Must be between 62 and 70 inclusive.
    bornOnFirstDays : bool
        True if birthday is on the 1st or 2nd day of the month, False otherwise.
        If True, the function adds 1/12 year to convert to Social Security age.

    Returns
    -------
    float
        Factor to multiply PIA. Examples:
        - 0.75 = 75% of PIA (claiming at 62 with FRA of 66)
        - 1.0 = 100% of PIA (claiming at FRA)
        - 1.32 = 132% of PIA (claiming at 70 with FRA of 66)

    Raises
    ------
    ValueError
        If convage is less than 62 or greater than 70.
    """
    if convage < 62 or convage > 70:
        raise ValueError(f"Age {convage} out of range.")

    # Add a month to conventional age if born on the 1st or 2nd (SSA treats both the same).
    offset = 0 if not bornOnFirstDays else 1/12
    ssage = convage + offset

    diff = fra - ssage
    if diff <= 0:
        return 1. - .08 * diff
    elif diff <= 3:
        # Reduction of 20% over first 36 months.
        return 1. - 0.06666667 * diff
    else:
        # Then 5% per tranche of 12 months.
        return .8 - 0.05 * (diff - 3)


def getSpousalFactor(fra, convage, bornOnFirstDays):
    """
    Return the reduction factor to multiply spousal benefits based on claiming age.

    This function calculates the adjustment factor for spousal benefits based on when
    benefits start relative to Full Retirement Age (FRA):
    - Before FRA: Benefits are reduced (minimum 32.5% at age 62)
    - At or after FRA: Full spousal benefit (50% of spouse's PIA, no increase for delay)

    The function automatically adjusts for Social Security age if the birthday is on
    the 1st or 2nd day of the month (adds 1/12 year to conventional age), consistent
    with SSA rules that treat both days the same for age calculation purposes.

    Parameters
    ----------
    fra : float
        Full Retirement Age in years (can be fractional with 1/12 increments).
    convage : float
        Conventional age when benefits start, in years (can be fractional with 1/12 increments).
        Must be at least 62 (no maximum, but no increase beyond FRA).
    bornOnFirstDays : bool
        True if birthday is on the 1st or 2nd day of the month, False otherwise.
        If True, the function adds 1/12 year to convert to Social Security age.

    Returns
    -------
    float
        Factor to multiply spousal benefit. Examples:
        - 0.325 = 32.5% reduction factor (claiming at 62 with FRA of 66)
        - 1.0 = 100% of spousal benefit (claiming at or after FRA)
        Note: Unlike self benefits, spousal benefits do not increase beyond FRA.

    Raises
    ------
    ValueError
        If convage is less than 62.
    """
    if convage < 62:
        raise ValueError(f"Age {convage} out of range.")

    # Add a month to conventional age if born on the 1st or 2nd (SSA treats both the same).
    offset = 0 if not bornOnFirstDays else 1/12
    ssage = convage + offset

    diff = fra - ssage
    if diff <= 0:
        return 1.
    elif diff <= 3:
        # Reduction of 25% over first 36 months.
        return 1. - 0.08333333 * diff
    else:
        # Then 5% per tranche of 12 months.
        return .75 - 0.05 * (diff - 3)
