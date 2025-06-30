"""

Owl/tax2025
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

Module to handle all tax calculations.

Copyright &copy; 2024 - Martin-D. Lacasse

Disclaimers: This code is for educatonal purposes only and does not constitute financial advice.

"""

import numpy as np
from datetime import date


##############################################################################
# Prepare the data.

taxBracketNames = ["10%", "12/15%", "22/25%", "24/28%", "32/33%", "35%", "37/40%"]

rates_TCJA = np.array([0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.370])
rates_nonTCJA = np.array([0.10, 0.15, 0.25, 0.28, 0.33, 0.35, 0.396])

###############################################################################
# Start of section where rates need to be actualized every year.
###############################################################################
# Single [0] and married filing jointly [1].

# These are 2025 current.
taxBrackets_TCJA = np.array(
    [
        [11925, 48475, 103350, 197300, 250525, 626350, 9999999],
        [23850, 96950, 206700, 394600, 501050, 751600, 9999999],
    ]
)

irmaaBrackets = np.array(
    [
        [0, 106000, 133000, 167000, 200000, 500000],
        [0, 212000, 266000, 334000, 400000, 750000],
    ]
)

# Index [0] stores the standard Medicare part B premium.
# Following values are incremental IRMAA part B monthly fees.
irmaaFees = 12 * np.array([185.00, 74.00, 111.00, 110.90, 111.00, 37.00])

# Make projection for non-TCJA using 2017 to current year.
# taxBrackets_2017 = np.array(
#    [ [9325, 37950, 91900, 191650, 416700, 418400, 9999999],
#      [18650, 75900, 153100, 233350, 416700, 470700, 9999999],
#    ])
#
# stdDeduction_2017 = [6350, 12700]
#
# For 2025, I used a 30.5% adjustment from 2017, rounded to closest 50.
#
# These are speculated.
taxBrackets_nonTCJA = np.array(
    [
        [12150, 49550, 119950, 250200, 544000, 546200, 9999999],  # Single
        [24350, 99100, 199850, 304600, 543950, 614450, 9999999],  # MFJ
    ]
)

# These are 2025 current (adjusted for inflation).
stdDeduction_TCJA = np.array([15000, 30000])    # Single, MFJ
# These are speculated (adjusted for inflation).
stdDeduction_nonTCJA = np.array([8300, 16600])  # Single, MFJ

# These are current (adjusted for inflation).
extra65Deduction = np.array([2000, 1600])       # Single, MFJ

# Thresholds for capital gains (adjusted for inflation).
capGainRates = np.array(
    [
        [48350, 533400],
        [96700, 600050],
    ]
)

# Thresholds for net investment income tax (not adjusted for inflation).
niitThreshold = np.array([200000, 250000])
niitRate = 0.038

###############################################################################
# End of section where rates need to be actualized every year.
###############################################################################


def capitalGainTaxRate(Ni, magi_n, gamma_n, nd, Nn):
    """
    Return an array of decimal rates for capital gains.
    Parameter nd is the index year of first passing of a spouse, if applicable,
    nd == Nn for single individuals.
    """
    status = Ni - 1
    cgRate_n = np.zeros(Nn)

    for n in range(Nn):
        if n == nd:
            status -= 1

        if magi_n[n] > gamma_n[n] * capGainRates[status][1]:
            cgRate_n[n] = 0.20
        elif magi_n[n] > gamma_n[n] * capGainRates[status][0]:
            cgRate_n[n] = 0.15

    return cgRate_n


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


def taxParams(yobs, i_d, n_d, N_n, y_TCJA=2026):
    """
    Input is year of birth, index of shortest-lived individual,
    lifespan of shortest-lived individual, total number of years
    in the plan, and the year that TCJA might expire.

    It returns 3 time series:
    1) Standard deductions at year n (sigma_n).
    2) Tax rate in year n (theta_tn)
    3) Delta from top to bottom of tax brackets (Delta_tn)
    This is pure speculation on future values.
    Returned values are not indexed for inflation.
    """
    # Compute the deltas in-place between brackets, starting from the end.
    deltaBrackets_TCJA = np.array(taxBrackets_TCJA)
    deltaBrackets_nonTCJA = np.array(taxBrackets_nonTCJA)
    for t in range(6, 0, -1):
        for i in range(2):
            deltaBrackets_TCJA[i, t] -= deltaBrackets_TCJA[i, t - 1]
            deltaBrackets_nonTCJA[i, t] -= deltaBrackets_nonTCJA[i, t - 1]

    # Prepare the 3 arrays to return - use transpose for easy slicing.
    sigma = np.zeros((N_n))
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

        if thisyear + n < y_TCJA:
            sigma[n] = stdDeduction_TCJA[filingStatus]
            Delta[n, :] = deltaBrackets_TCJA[filingStatus, :]
        else:
            sigma[n] = stdDeduction_nonTCJA[filingStatus]
            Delta[n, :] = deltaBrackets_nonTCJA[filingStatus, :]

        # Add 65+ additional exemption(s).
        for i in souls:
            if thisyear + n - yobs[i] >= 65:
                sigma[n] += extra65Deduction[filingStatus]

        # Fill in future tax rates for year n.
        if thisyear + n < y_TCJA:
            theta[n, :] = rates_TCJA[:]
        else:
            theta[n, :] = rates_nonTCJA[:]

    Delta = Delta.transpose()
    theta = theta.transpose()

    # Return series unadjusted for inflation, in STD order.
    return sigma, theta, Delta


def taxBrackets(N_i, n_d, N_n, y_TCJA):
    """
    Return dictionary containing future tax brackets
    unadjusted for inflation for plotting.
    """
    if not (0 < N_i <= 2):
        raise ValueError(f"Cannot process {N_i} individuals.")
    n_d = min(n_d, N_n)
    status = N_i - 1

    # Number of years left in TCJA from this year.
    thisyear = date.today().year
    ytc = y_TCJA - thisyear

    data = {}
    for t in range(len(taxBracketNames) - 1):
        array = np.zeros(N_n)
        for n in range(N_n):
            stat = status if n < n_d else 0
            array[n] = taxBrackets_TCJA[stat][t] if n < ytc else taxBrackets_nonTCJA[stat][t]

        data[taxBracketNames[t]] = array

    return data


def rho_in(yobs, N_n):
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
    ]

    N_i = len(yobs)
    if N_i == 2 and abs(yobs[0] - yobs[1]) > 10:
        raise RuntimeError("RMD: Unsupported age difference of more than 10 years.")

    rho = np.zeros((N_i, N_n))
    thisyear = date.today().year
    for i in range(N_i):
        agenow = thisyear - yobs[i]
        for n in range(N_n):
            year = thisyear + n
            yage = agenow + n

            # Account for increase of RMD age between 2023 and 2032.
            if (yage < 73) or (year > 2032 and yage < 75):
                pass  # rho[i][n] = 0
            else:
                rho[i][n] = 1.0 / rmdTable[yage - 72]

    return rho
