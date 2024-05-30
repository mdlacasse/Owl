import numpy as np
from datetime import date

##############################################################################
# Prepare the data.

bracketNames = ['10%', '12/15%', '22/25%', '24/28%', '32/33%', '35%', '37/40%']

rates_2024 = np.array([0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.370])
rates_2026 = np.array([0.10, 0.15, 0.25, 0.28, 0.33, 0.35, 0.396])

# Single [0] and married filing jointly [1].
brackets_2024 = np.array(
    [[11600, 47150, 100525, 191950, 243450, 609350, 999999],
     [23200, 94300, 201050, 383900, 487450, 731200, 999999]]
)
# Adjusted from 2017 with 30% increase.
brackets_2026 = np.array(
    [[12100, 49300, 119500, 249100, 541700, 543900, 999999],
     [24200, 98700, 199000, 303350, 541700, 611900, 999999]]
)

stdDeduction_2024 = np.array([14600, 29200])
stdDeduction_2026 = np.array([8300, 16600])
extraDeduction_65 = np.array([1950, 1550])


##############################################################################

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
    mybrackets_2024 = brackets_2024
    mybrackets_2026 = brackets_2026
    for t in range(6, 0, -1):
        for i in range(2):
            mybrackets_2024[i, t] -= brackets_2024[i, t - 1]
            mybrackets_2026[i, t] -= brackets_2026[i, t - 1]

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
            sigma[n] = stdDeduction_2024[filingStatus]
            Delta[n, :] = brackets_2024[filingStatus, :]
        else:
            sigma[n] = stdDeduction_2026[filingStatus]
            Delta[n, :] = brackets_2026[filingStatus, :]

        # Add 65+ additional exemption(s).
        for i in souls:
            if thisyear + n - yobs[i] >= 65:
                sigma[n] += extraDeduction_65[filingStatus]

        # Fill in future tax rates for year n.
        if thisyear + n < 2026:
            theta[n, :] = rates_2024[:]
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
    assert 0 < N_i and N_i <= 2, 'Cannot process %d individuals.'%N_i
    # This 2 is the number of years left in TCJA from 2024.
    ytc = 2
    status = N_i-1
    n_d = min(n_d, N_n)

    data = {}
    for t in range(len(bracketNames)):
        array = np.zeros(N_n)
        array[0:ytc] = brackets_2024[status][t]
        array[ytc:n_d] = brackets_2026[status][t]
        array[n_d:N_n] = brackets_2026[0][t]
        data[bracketNames[t]] = array

    return data


def rho_in(yobs, N_n):
    '''
    Return Required Minimum Distribution fractions for each individual.
    This implementation does not support spouses with more than
    10-year difference.
    '''
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

