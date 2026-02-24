"""
Tax calculation module for 2026 tax year rules.

This module handles all tax calculations including income tax brackets,
capital gains tax, and other tax-related computations based on 2026 tax rules.

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
from datetime import date

# Sentinel: used as default yOBBBA meaning "OBBBA never expires / far future".
_YEAR_FAR_FUTURE = 2099

###############################################################################
# Start of section where rates need to be actualized every year.
###############################################################################
# Single [0] and married filing jointly [1].

# OBBBA §1002 — 65+ additional "bonus" deduction expires after this tax year.
OBBBA_BONUS_EXPIRATION_YEAR = 2028

# These are current for 2026 (2025TY).
taxBrackets_OBBBA = np.array(
    [
        [12_400, 50_400, 105_700, 201_775, 256_225, 640_600, 9_999_999],
        [24_800, 100_800, 211_400, 403_550, 512_450, 768_700, 9_999_999],
    ]
)

# These are current for 2026 (2025TY).
irmaaBrackets = np.array(
    [
        [0, 109_000, 137_000, 171_000, 205_000, 500_000],
        [0, 218_000, 274_000, 342_000, 410_000, 750_000],
    ]
)

# These are current for 2026 (2025TY). Source: CMS 2026 Part B premiums and IRMAA.
# Index [0] stores the standard Medicare Part B basic premium (monthly $202.90 for 2026).
# Following values are incremental IRMAA Part B monthly fees; cumulative = total/month.
# Single brackets [0]: ≤$109k, $109–137k, $137–171k, $171–205k, $205–500k, ≥$500k.
irmaaFees = 12 * np.array([202.90, 81.20, 121.70, 121.70, 121.70, 40.70])
irmaaCosts = np.cumsum(irmaaFees)

#########################################################################
# Make projection for pre-TCJA using 2017 to current year.
# taxBrackets_2017 = np.array(
#    [ [9_325, 37_950, 91_900, 191_650, 416_700, 418_400, 9_999_999],
#      [18_650, 75_900, 153_100, 233_350, 416_700, 470_700, 9_999_999],
#    ])
#
# stdDeduction_2017 = [6350, 12700]
#
# COLA from 2017: [2.0, 2.8, 1.6, 1.3, 5.9, 8.7, 3.2, 2.5, 2.8]
# For 2026, I used a 35.1% adjustment from 2017, rounded to closest 10.
#
# These are speculated.
taxBrackets_preTCJA = np.array(
    [
        [12_600, 51_270, 124_160, 258_920, 562_960, 565_260, 9_999_999],   # Single
        [25_200, 102_540, 206_840, 315_260, 562_960, 635_920, 9_999_999],  # MFJ
    ]
)

# These are speculated (adjusted for inflation to 2026).
stdDeduction_preTCJA = np.array([8_580, 17_160])   # Single, MFJ
#########################################################################

# These are current for 2026 (2025TY).
stdDeduction_OBBBA = np.array([16_100, 32_200])    # Single, MFJ

# These are current for 2026  (2025TY) per individual.
extra65Deduction = np.array([2_000, 1_600])        # Single, MFJ

# These are current for 2026 (2025TY).
# Thresholds setting capital gains brackets 0%, 15%, 20%.
capGainRates = np.array(
    [
        [49_450, 545_500],
        [98_900, 613_700],
    ]
)

###############################################################################
# End of section where rates need to be actualized every year.
###############################################################################

###############################################################################
# Data that is unlikely to change.
###############################################################################

# Thresholds for net investment income tax (not adjusted for inflation).
niitThreshold = np.array([200_000, 250_000])
niitRate = 0.038

# Thresholds for 65+ bonus of $6k per individual for circumventing tax
# on social security for low-income households. This expires in 2029.
# These numbers are hard-coded below as the tax code will likely change
# the rules for eligibility and will require a code review.
# Bonus decreases linearly above threshold by 1% / $1k over threshold.
bonusThreshold = np.array([75_000, 150_000])

taxBracketNames = ["10%", "12/15%", "22/25%", "24/28%", "32/33%", "35%", "37/40%"]

rates_OBBBA = np.array([0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.370])
rates_preTCJA = np.array([0.10, 0.15, 0.25, 0.28, 0.33, 0.35, 0.396])

###############################################################################


def mediVals(yobs, horizons, gamma_n, Nn, Nq):
    """
    Return tuple (nm, L, C) of year index when Medicare starts and vectors L, and C
    defining end points of constant piecewise linear functions representing IRMAA fees.
    Costs C include the fact that one or two indivuals have to pay. Eligibility is built-in.
    """
    thisyear = date.today().year
    assert Nq == len(irmaaCosts), f"Inconsistent value of Nq: {Nq}."
    assert Nq == len(irmaaBrackets[0]), "Inconsistent IRMAA brackets array."
    Ni = len(yobs)
    # What index year will Medicare start? 65 - age for each individual.
    nm = yobs + 65 - thisyear
    nm = np.maximum(0, nm)
    nmstart = np.min(nm)
    # Has it already started?
    Nmed = Nn - nmstart

    Lbar = np.zeros((Nmed, Nq-1))
    Cbar = np.zeros((Nmed, Nq))

    # Year starts at offset nmstart in the plan. L and C arrays are shorter.
    for nn in range(Nmed):
        imed = 0
        n = nmstart + nn
        if thisyear + n - yobs[0] >= 65 and n < horizons[0]:
            imed += 1
        if Ni == 2 and thisyear + n - yobs[1] >= 65 and n < horizons[1]:
            imed += 1
        if imed:
            if Ni == 1 or not (n < horizons[0] and n < horizons[1]):
                status = 0   # single or one spouse deceased
            else:
                status = 1   # married filing jointly
            Lbar[nn] = gamma_n[n] * irmaaBrackets[status][1:]
            Cbar[nn] = imed * gamma_n[n] * irmaaCosts
        else:
            raise RuntimeError("mediVals: This should never happen.")

    return nmstart, Lbar, Cbar


def capitalGainTax(Ni, txIncome_n, ltcg_n, gamma_n, nd, Nn):
    """
    Return an array of tax on capital gains.

    Parameters:
    -----------
    Ni : int
        Number of individuals (1 or 2)
    txIncome_n : array
        Array of taxable income for each year (ordinary income + capital gains)
    ltcg_n : array
        Array of long-term capital gains for each year
    gamma_n : array
        Array of inflation adjustment factors for each year
    nd : int
        Index year of first passing of a spouse, if applicable (nd == Nn for single individuals)
    Nn : int
        Total number of years in the plan

    Returns:
    --------
    cgTax_n : array
        Array of tax on capital gains for each year

    Notes:
    ------
    Thresholds are determined by the taxable income which is roughly AGI - (standard/itemized) deductions.
    Taxable income can also be thought of as taxable ordinary income + capital gains.

    Long-term capital gains are taxed at 0%, 15%, or 20% based on total taxable income.
    Capital gains "stack on top" of ordinary income, so the portion of gains that
    pushes total income above each threshold is taxed at the corresponding rate.
    """
    status = Ni - 1
    cgTax_n = np.zeros(Nn)

    for n in range(Nn):
        if status and n == nd:
            status -= 1

        # Calculate ordinary income (taxable income minus capital gains).
        ordIncome = txIncome_n[n] - ltcg_n[n]

        # Get inflation-adjusted thresholds for this year.
        threshold15 = gamma_n[n] * capGainRates[status][0]  # 0% to 15% threshold
        threshold20 = gamma_n[n] * capGainRates[status][1]  # 15% to 20% threshold

        # Calculate how much LTCG falls in the 20% bracket.
        # This is the portion of LTCG that pushes total income above threshold20.
        if txIncome_n[n] > threshold20:
            ltcg20 = min(ltcg_n[n], txIncome_n[n] - threshold20)
        else:
            ltcg20 = 0

        # Calculate how much LTCG falls in the 15% bracket.
        # This is the portion of LTCG in the range [threshold15, threshold20].
        if ordIncome >= threshold20:
            # All LTCG is already in the 20% bracket.
            ltcg15 = 0
        elif txIncome_n[n] > threshold15:
            # Some LTCG falls in the 15% bracket.
            # The 15% bracket spans from threshold15 to threshold20.
            bracket_top = min(threshold20, txIncome_n[n])
            bracket_bottom = max(threshold15, ordIncome)
            ltcg15 = min(ltcg_n[n] - ltcg20, bracket_top - bracket_bottom)
        else:
            # Total income is below the 15% threshold.
            ltcg15 = 0

        # Remaining LTCG is in the 0% bracket (ltcg0 = ltcg_n[n] - ltcg20 - ltcg15).
        # Calculate tax: 20% on ltcg20, 15% on ltcg15, 0% on remainder.
        cgTax_n[n] = 0.20 * ltcg20 + 0.15 * ltcg15

    return cgTax_n


def mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn):
    """
    Compute Medicare costs directly.
    """
    thisyear = date.today().year
    Ni = len(yobs)
    costs = np.zeros(Nn)
    for n in range(Nn):
        status = 0 if Ni == 1 else 1 if n < horizons[0] and n < horizons[1] else 0
        for i in range(Ni):
            if thisyear + n - yobs[i] >= 65 and n < horizons[i]:
                # Start with the (inflation-adjusted) basic Medicare part B premium.
                costs[n] += gamma_n[n] * irmaaFees[0]
                if n < 2:
                    mymagi = prevmagi[n]
                else:
                    mymagi = magi[n - 2]
                for q in range(1, 6):
                    if mymagi > gamma_n[n] * irmaaBrackets[status][q]:
                        costs[n] += gamma_n[n] * irmaaFees[q]

    return costs


def taxParams(yobs, i_d, n_d, N_n, gamma_n, MAGI_n, yOBBBA=_YEAR_FAR_FUTURE):
    """
    Input is year of birth, index of shortest-lived individual,
    lifespan of shortest-lived individual, total number of years
    in the plan, and the year that preTCJA rates might come back.

    It returns 3 time series:
    1) Standard deductions at year n (sigma_n).
    2) Tax rate in year n (theta_tn)
    3) Delta from top to bottom of tax brackets (Delta_tn)
    This is pure speculation on future values.
    Returned values are not indexed for inflation.
    """
    # Compute the deltas in-place between brackets, starting from the end.
    deltaBrackets_OBBBA = np.array(taxBrackets_OBBBA)
    deltaBrackets_preTCJA = np.array(taxBrackets_preTCJA)
    for t in range(6, 0, -1):
        for i in range(2):
            deltaBrackets_OBBBA[i, t] -= deltaBrackets_OBBBA[i, t - 1]
            deltaBrackets_preTCJA[i, t] -= deltaBrackets_preTCJA[i, t - 1]

    # Prepare the 3 arrays to return - use transpose for easy slicing.
    sigmaBar = np.zeros((N_n))
    Delta = np.zeros((N_n, 7))
    theta = np.zeros((N_n, 7))

    filingStatus = len(yobs) - 1
    souls = list(range(len(yobs)))
    thisyear = date.today().year

    for n in range(N_n):
        # First check if shortest-lived individual is still with us.
        if n == n_d:
            souls.remove(i_d)
            filingStatus -= 1

        if thisyear + n < yOBBBA:
            sigmaBar[n] = stdDeduction_OBBBA[filingStatus] * gamma_n[n]
            Delta[n, :] = deltaBrackets_OBBBA[filingStatus, :]
        else:
            sigmaBar[n] = stdDeduction_preTCJA[filingStatus] * gamma_n[n]
            Delta[n, :] = deltaBrackets_preTCJA[filingStatus, :]

        # Add 65+ additional exemption(s) and "bonus" phasing out.
        for i in souls:
            if thisyear + n - yobs[i] >= 65:
                sigmaBar[n] += extra65Deduction[filingStatus] * gamma_n[n]
                if thisyear + n <= OBBBA_BONUS_EXPIRATION_YEAR:
                    sigmaBar[n] += 6000 * max(0, 1 - 0.06*max(0, MAGI_n[n] - bonusThreshold[filingStatus]))

        # Fill in future tax rates for year n.
        if thisyear + n < yOBBBA:
            theta[n, :] = rates_OBBBA[:]
        else:
            theta[n, :] = rates_preTCJA[:]

    Delta = Delta.transpose()
    theta = theta.transpose()

    # Return series unadjusted for inflation, except for sigmaBar, in STD order.
    return sigmaBar, theta, Delta


def taxBrackets(N_i, n_d, N_n, yOBBBA=_YEAR_FAR_FUTURE):
    """
    Return dictionary containing future tax brackets
    unadjusted for inflation for plotting.
    """
    if not (0 < N_i <= 2):
        raise ValueError(f"Cannot process {N_i} individuals.")

    n_d = min(n_d, N_n)
    status = N_i - 1

    # Number of years left in OBBBA from this year.
    thisyear = date.today().year
    if yOBBBA < thisyear:
        raise ValueError(f"OBBBA expiration year {yOBBBA} cannot be in the past.")

    ytc = yOBBBA - thisyear

    data = {}
    for t in range(len(taxBracketNames) - 1):
        array = np.zeros(N_n)
        for n in range(N_n):
            stat = status if n < n_d else 0
            array[n] = taxBrackets_OBBBA[stat][t] if n < ytc else taxBrackets_preTCJA[stat][t]

        data[taxBracketNames[t]] = array

    return data


def computeNIIT(N_i, MAGI_n, I_n, Q_n, n_d, N_n):
    """
    Compute ACA tax on Dividends (Q) and Interests (I).
    For accounting for rent and/or trust income, one can easily add a column
    to the Wages and Contributions file and add yearly amount to Q_n + I_n below.
    """
    J_n = np.zeros(N_n)
    status = N_i - 1

    for n in range(N_n):
        if status and n == n_d:
            status -= 1

        Gmax = niitThreshold[status]
        if MAGI_n[n] > Gmax:
            J_n[n] = niitRate * min(MAGI_n[n] - Gmax, I_n[n] + Q_n[n])

    return J_n


def rho_in(yobs, longevity, N_n):
    """
    Return Required Minimum Distribution fractions for each individual.
    This implementation does not support spouses with more than
    10-year difference.
    It starts at age 73 until it goes to 75 in 2033.
    """
    # Notice that table starts at age 72.
    rmdTable = [
        27.4,
        26.5,
        25.5,
        24.6,
        23.7,
        22.9,
        22.0,
        21.1,
        20.2,
        19.4,
        18.5,
        17.7,
        16.8,
        16.0,
        15.2,
        14.4,
        13.7,
        12.9,
        12.2,
        11.5,
        10.8,
        10.1,
        9.5,
        8.9,
        8.4,
        7.8,
        7.3,
        6.8,
        6.4,
        6.0,
        5.6,
        5.2,
        4.9,
        4.6,
        4.3,
        4.1,
        3.9,
        3.7,
        3.5,
        3.4,
        3.3,
        3.1,
        3.0,
        2.9,
        2.8,
        2.7,
        2.5,
        2.3,
        2.0
    ]

    N_i = len(yobs)
    if N_i == 2 and abs(yobs[0] - yobs[1]) > 10:
        raise RuntimeError("RMD: Unsupported age difference of more than 10 years.")
    if np.any(np.array(longevity) > 120):
        raise RuntimeError(
            "RMD: Unsupported life expectancy over 120 years."
        )

    rho = np.zeros((N_i, N_n))
    thisyear = date.today().year
    for i in range(N_i):
        agenow = thisyear - yobs[i]
        # Account for increase of RMD age between 2023 and 2032.
        yrmd = 70 if yobs[i] < 1949 else 72 if 1949 <= yobs[i] <= 1950 else 73 if 1951 <= yobs[i] <= 1959 else 75
        for n in range(N_n):
            yage = agenow + n

            if yage < yrmd:
                pass  # rho[i][n] = 0
            else:
                rho[i][n] = 1.0 / rmdTable[yage - 72]

    return rho
