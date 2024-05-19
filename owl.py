'''
Owl

Copyright -- Martin-D. Lacasse (2024)

'''

import numpy as np
from datetime import date
import utils as u
import rates


def gamma_n(tau, N):
    """
    Return time series of inflation multiplier at year n
    with respect to the current year.
    """
    gamma = np.ones(N)

    for n in range(1, N):
        gamma[n] = gamma[n - 1] * (1 + tau[3][n - 1])

    return gamma


def taxParams(yobs, i_d, n_d, gamma, N):
    """
    Return 3 time series:
    1) Standard deductions at year n (sigma_n).
    2) Difference in tax brackets (Delta_tn)
    3) Tax rate in year n (theta_tn)
    This is pure speculation on future values.
    """
    # Prepare the data.
    rates_2024 = np.array([0.10, 0.12, 0.22, 0.24, 0.32, 0.035, 0.370])
    rates_2026 = np.array([0.10, 0.15, 0.25, 0.28, 0.33, 0.035, 0.396])

    # Single [0] and married filing jointly [1].
    brackets_2024 = np.array(
        [11600, 47150, 100525, 191950, 243450, 609350, 10000000],
        [23200, 94300, 201050, 383900, 487450, 731200, 10000000],
    )
    brackets_2026 = np.array(
        [11600, 47150, 100525, 191950, 243450, 609350, 10000000],
        [23200, 94300, 201050, 383900, 487450, 731200, 10000000],
    )
    # Compute the deltas in-place between brackets.
    for t in range(6, 0, -1):
        for i in range(2):
            brackets_2024[i][t] -= brackets_2024[i][t - 1]
            brackets_2026[i][t] -= brackets_2026[i][t - 1]

    stdDeduction_2024 = np.array([14600, 29200])
    stdDeduction_2026 = np.array([8300, 16600])
    extraDeduction_65 = np.array([1950, 1550])

    # Prepare the 3 arrays to return.
    sigma = np.zeros((N))
    Delta = np.zeros((7, N))
    theta = np.zeros((7, N))

    filingStatus = len(yobs) - 1
    souls = list(range(len(yobs)))
    thisyear = date.today().year

    for n in range(N):
        # Check for death in the family.
        if n == n_d + 1:
            souls.remove(i_d)
            filingStatus -= 1

        if thisyear + n < 2026:
            sigma[n] = stdDeduction_2024[filingStatus]
            Delta[:][n] = brackets_2024[filingStatus][:]
        else:
            sigma[n] = stdDeduction_2026[filingStatus]
            Delta[:][n] = brackets_2026[filingStatus][:]

        for i in souls:
            if thisyear + n - yobs[i] >= 65:
                sigma[n] += extraDeduction_65[filingStatus]

        # Fill in future tax rates.
        if thisyear + n < 2026:
            theta[:][n] = rates_2024[:]
        else:
            theta[:][n] = rates_2026[:]

    # Index for inflation.
    sigma = sigma * gamma
    Delta = Delta * gamma

    return sigma, Delta, theta


def rho_in(yobs, N):
    """
    Return RMD fractions for each individual.
    """
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

    icount = len(yobs)
    if icount == 2 and abs(yobs[0] - yobs[1]) > 10:
        u.xprint("RMD: Unsupported age difference of more than 10 years.")

    rho = np.zeros((icount, N))
    thisyear = date.today().year
    for i in range(icount):
        agenow = thisyear - yobs[i]
        for n in range(N):
            year = thisyear + n
            yage = agenow + n

            # Account for increase of RMD age between 2023 and 2032.
            if (yage < 73) or (year > 2032 and yage < 75):
                pass  # rho[i][n] = 0
            else:
                rho[i][n] = 1.0 / rmdTable[yage - 72]

    return rho


def xi_n(profile, frac, n_d, N):
    """
    Return time series of spending profile.
    Series is adjusted for inflation.
    """
    xi = np.ones(N)
    if profile == "flat":
        pass
    elif profile == "smile":
        x = np.linspace(0, N, N)
        # Use a cosine over a gentle linear increase.
        xi = xi + 0.15*np.cos((2*np.pi/N)*x) + (0.12/N)*x
        # Normalize sum to a flat profile.
        xi = xi*(N/xi.sum())
    else:
        u.xprint("Unknown profile " + profile)

    # Reduce income at passing of one spouse.
    for n in range(n_d+1, N):
        xi[n] *= frac

    return xi


def q0(C, N1, N2=1, N3=1, N4=1):
    '''
    Index range accumulator.
    '''
    return C + N1*N2*N3*N4


def q4(C, l1, l2=0, N2=1, l3=0, N3=1, l4=0, N4=1):
    '''
    Index mapping function.
    '''
    return C + l1*N2*N3*N4 + l2*N3*N4 + l3*N4 + l4

class Owl:
    '''
    This is the main class of the Owl Project.
    '''
    def __init__(self, yobs, expectancy, name):
        '''
        Constructor requires two lists: the first one is
        the year of birth of each spouse, and the second
        the life expectancy.
        '''
        self._name = name

        # 7 tax brackets, 3 types of accounts, 4 classes of assets
        self.N_t = 7
        self.N_j = 3
        self.N_k = 4

        self.N_i = len(yobs)
        assert self.N_i == len(expectancy)
        assert 0 < self.N_i and self.N_i <= 2

        self.status = ['single', 'married'][self.N_i - 1]

        self.yobs = yobs
        self.expectancy = expectancy

        thisyear = date.today().year

        self.horizons = [yobs[i] + expectancy[i] - thisyear + 1 for i in range(self.N_i)]
        self.N_n = max(self.horizons)
        if self.N_i == 2:
            self.n_d = min(self.horizons)
        else:
            self.n_d = self.N_n + 1

        u.vprint('Preparing scenario of %d years for %d individual%s'%
                (self.N_n - 1, self.N_i, ['', 's'][self.N_i-1]))

        # All variables
        self.b_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n + 1))
        self.bp_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))
        self.bm_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))
        self.d_ikn = np.zeros((self.N_i, self.N_k, self.N_n))
        self.f_tn = np.zeros((self.N_t, self.N_n))
        self.g_n = np.zeros((self.N_n))
        self.w_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))
        self.x_ikn = np.zeros((self.N_i, self.N_k, self.N_n))

        return

    def setVerbose(self):
        pass
    def setAssetBalances(self):
        pass
    def readContributions(self, filename):
        pass
    def setInitialAR(self):
        pass
    def setFinalAR(self):
        pass
    def interpotlateAR(self):
        pass
    def seCoordinatedAR(self):
        pass
    def setPension(self, amounts, ages, units=None):
        '''
        Set value of pension for each individual and commencement age. 
        '''
        assert len(amounts) == self.N_i
        assert len(ages) == self.N_i

        fac = u.getUnits(units)
        u.rescale(amounts, fac)

        thisyear = date.today().year
        self.pi_in = np.zeros((self.N_i, self.N_n))
        for i in range(N_i):
            ns = max(0, self.yobs[i] + ages[i] - thiyear)
            self.pi_in[i][ns:] = values[i]

        return

    def setSocialSecurity(self, amounts, ages, units=None):
        '''
        Set value of social security for each individual and commencement age. 
        '''
        assert len(amounts) == self.N_i
        assert len(ages) == self.N_i

        fac = u.getUnits(units)
        u.rescale(amounts, fac)

        thisyear = date.today().year
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        for i in range(N_i):
            ns = max(0, self.yobs[i] + ages[i] - thiyear)
            self.zeta_in[i][ns:] = values[i]

        return
    def setDesiredIncome(self):
        pass
    def setRates(self):
        pass
    def setHeirsTaxRate(self):
        pass
        

