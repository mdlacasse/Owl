'''

Owl/tax2025
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

Module to handle all tax calculations.

Copyright (C) 2024 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.
'''

import numpy as np
from datetime import date

from owlplanner import utils as u

##############################################################################
# Prepare the data.

taxBracketNames = ['10%', '12/15%', '22/25%', '24/28%', '32/33%', '35%', '37/40%']

rates_2025 = np.array([0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.370])
rates_2026 = np.array([0.10, 0.15, 0.25, 0.28, 0.33, 0.35, 0.396])

# Single [0] and married filing jointly [1].
taxBrackets_2025 = np.array(
    [
        [11925, 48475, 103350, 197300, 250525, 626350, 9999999],
        [23850, 96950, 206700, 394600, 501050, 751700, 9999999],
    ]
)

irmaaBrackets_2025 = np.array(
    [
        [0, 106000, 133000, 167000, 200000, 500000],
        [0, 212000, 266000, 334000, 400000, 750000],
    ]
)

# Use index [0] to store the standard Medicare part B premium.
# Following values are incremental IRMAA part B monthly fees.
# 2024 total monthly fees: [174.70, 244.60, 349.40, 454.20, 559.00, 594.00]
# irmaaFees_2024 = 12 * np.array([174.70, 69.90, 104.80, 104.80, 104.80, 35.00])
irmaaFees_2025 = 12 * np.array([185.00, 74.00, 111.00, 110.90, 111.00, 37.00])

# Compute 2026 from 2017 with 27% increase.
# taxBrackets_2017 = np.array(
#    [ [9325, 37950, 91900, 191650, 416700, 418400, 9999999],
#      [18650, 75900, 153100, 233350, 416700, 470000, 9999999],
#    ])

taxBrackets_2026 = np.array(
    [
        [11850, 48200, 116700, 243400, 529200, 531400, 9999999],
        [23700, 96400, 194400, 296350, 529200, 596900, 9999999],
    ]
)

stdDeduction_2025 = np.array([15000, 30000])
stdDeduction_2026 = np.array([8300, 16600])
extra65Deduction_2025 = np.array([2000, 1600])


##############################################################################


def mediCosts(yobs, horizons, magi, gamma_n, Nn):
    '''
    Compute Medicare costs directly.
    '''
    thisyear = date.today().year
    Ni = len(yobs)
    costs = np.zeros(Nn)
    for n in range(Nn):
        for i in range(Ni):
            if thisyear + n - yobs[i] >= 65 and n < horizons[i]:
                # The standard Medicare part B premium
                costs[n] += gamma_n[n] * irmaaFees_2025[0]
                if n < 2:
                    nn = n
                else:
                    nn = 2
                for q in range(1, 6):
                    if magi[n - nn] > gamma_n[n] * irmaaBrackets_2025[Ni - 1][q]:
                        costs[n] += gamma_n[n] * irmaaFees_2025[q]

    return costs


def taxParams(yobs, i_d, n_d, N_n):
    '''
    Return 3 time series:
    1) Standard deductions at year n (sigma_n).
    2) Tax rate in year n (theta_tn)
    3) Delta from top to bottom of tax brackets (Delta_tn)
    This is pure speculation on future values.
    Returned values are not indexed for inflation.
    '''
    # Compute the deltas in-place between brackets, starting from the end.
    deltaBrackets_2025 = np.array(taxBrackets_2025)
    deltaBrackets_2026 = np.array(taxBrackets_2026)
    for t in range(6, 0, -1):
        for i in range(2):
            deltaBrackets_2025[i, t] -= deltaBrackets_2025[i, t - 1]
            deltaBrackets_2026[i, t] -= deltaBrackets_2026[i, t - 1]

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

        if thisyear + n < 2026:
            sigma[n] = stdDeduction_2025[filingStatus]
            Delta[n, :] = deltaBrackets_2025[filingStatus, :]
        else:
            sigma[n] = stdDeduction_2026[filingStatus]
            Delta[n, :] = deltaBrackets_2026[filingStatus, :]

        # Add 65+ additional exemption(s).
        for i in souls:
            if thisyear + n - yobs[i] >= 65:
                sigma[n] += extra65Deduction_2025[filingStatus]

        # Fill in future tax rates for year n.
        if thisyear + n < 2026:
            theta[n, :] = rates_2025[:]
        else:
            theta[n, :] = rates_2026[:]

    Delta = Delta.transpose()
    theta = theta.transpose()

    # Return series unadjusted for inflation, in STD order.
    return sigma, theta, Delta


def taxBrackets(N_i, n_d, N_n):
    '''
    Return dictionary containing future tax brackets
    unadjusted for inflation for plotting.
    '''
    assert 0 < N_i and N_i <= 2, 'Cannot process %d individuals.' % N_i
    # This 1 is the number of years left in TCJA from 2025.
    ytc = 1
    status = N_i - 1
    n_d = min(n_d, N_n)

    data = {}
    for t in range(len(taxBracketNames) - 1):
        array = np.zeros(N_n)
        array[0:ytc] = taxBrackets_2025[status][t]
        array[ytc:n_d] = taxBrackets_2026[status][t]
        array[n_d:N_n] = taxBrackets_2026[0][t]
        data[taxBracketNames[t]] = array

    return data


def rho_in(yobs, N_n):
    '''
    Return Required Minimum Distribution fractions for each individual.
    This implementation does not support spouses with more than
    10-year difference.
    It starts at age 73 until it goes to 75 in 2033.
    '''
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
        u.xprint('RMD: Unsupported age difference of more than 10 years.')

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
