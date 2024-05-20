'''
Owl

Copyright -- Martin-D. Lacasse (2024)

'''

###########################################################################
import numpy as np
from datetime import date

import utils as u
import rates


def gamma_n(tau, N_n):
    '''
    Return time series of inflation multiplier at year n
    with respect to the current year.
    '''
    gamma = np.ones(N_n)

    for n in range(1, N_n):
        gamma[n] = gamma[n - 1] * (1 + tau[3][n - 1])

    return gamma


def _taxParams(yobs, i_d, n_d, N_n):
    '''
    Return 3 time series:
    1) Standard deductions at year n (sigma_n).
    2) Difference in tax brackets (Delta_tn)
    3) Tax rate in year n (theta_tn)
    This is pure speculation on future values.
    Returned values are not indexed for inflation.
    '''
    # Prepare the data.
    rates_2024 = np.array([0.10, 0.12, 0.22, 0.24, 0.32, 0.035, 0.370])
    rates_2026 = np.array([0.10, 0.15, 0.25, 0.28, 0.33, 0.035, 0.396])

    # Single [0] and married filing jointly [1].
    brackets_2024 = np.array(
        [[11600, 47150, 100525, 191950, 243450, 609350, 99999999],
         [23200, 94300, 201050, 383900, 487450, 731200, 99999999]]
    )
    # Adjusted from 2017 with 30% increase.
    brackets_2026 = np.array(
        [[12100, 49300, 119500, 249100, 541700, 543900, 99999999],
         [24200, 98700, 199000, 303350, 541700, 611900, 99999999]]
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
    sigma = np.zeros((N_n))
    Delta = np.zeros((N_n, 7))
    theta = np.zeros((N_n, 7))

    filingStatus = len(yobs) - 1
    souls = list(range(len(yobs)))
    thisyear = date.today().year

    for n in range(N_n):
        # Check for death in the family.
        if n == n_d + 1:
            souls.remove(i_d)
            filingStatus -= 1

        if thisyear + n < 2026:
            sigma[n] = stdDeduction_2024[filingStatus]
            Delta[n][:] = brackets_2024[filingStatus][:]
        else:
            sigma[n] = stdDeduction_2026[filingStatus]
            Delta[n][:] = brackets_2026[filingStatus][:]

        for i in souls:
            if thisyear + n - yobs[i] >= 65:
                sigma[n] += extraDeduction_65[filingStatus]

        # Fill in future tax rates.
        if thisyear + n < 2026:
            theta[n][:] = rates_2024[:]
        else:
            theta[n][:] = rates_2026[:]

    Delta = Delta.transpose()
    theta = theta.transpose()
    # Return series unindexed for inflation
    return sigma, theta, Delta


def _rho_in(yobs, N_n):
    '''
    Return RMD fractions for each individual.
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


def _xi_n(profile, frac, n_d, N_n):
    '''
    Return time series of spending profile.
    Series is unadjusted for inflation.
    '''
    xi = np.ones(N_n)
    if profile == 'flat':
        pass
    elif profile == 'smile':
        x = np.linspace(0, N_n, N_n)
        # Use a cosine over a gentle linear increase.
        xi = xi + 0.15 * np.cos((2 * np.pi / N_n) * x) + (0.12 / N_n) * x
        # Normalize sum to be equivalent to a flat profile.
        xi = xi * (N_n / xi.sum())
    else:
        u.xprint('Unknown profile ' + profile)

    # Reduce income at passing of one spouse.
    for n in range(n_d + 1, N_n):
        xi[n] *= frac

    return xi


def _q0(C, N1, N2=1, N3=1, N4=1):
    '''
    Index range accumulator.
    '''
    return C + N1 * N2 * N3 * N4


def _q4(C, l1, l2=0, N2=1, l3=0, N3=1, l4=0, N4=1):
    '''
    Index mapping function.
    '''
    return C + l1 * N2 * N3 * N4 + l2 * N3 * N4 + l3 * N4 + l4


############################################################################


class Owl:
    '''
    This is the main class of the Owl Project.
    '''

    def __init__(self, yobs, expectancy, name):
        '''
        Constructor requires two lists: the first one is
        the year of birth of each spouse, and the second
        the life expectancy. Last argument is a name for
        the plan.
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

        self.horizons = [
            yobs[i] + expectancy[i] - thisyear + 1 for i in range(self.N_i)
        ]
        self.N_n = max(self.horizons)
        # Handle passing of one spouse before the other.
        if self.N_i == 2:
            self.n_d = min(self.horizons)
            self.i_d = self.horizons.index(self.n_d)
        else:
            self.n_d = self.N_n + 1
            self.i_d = 0

        self.survivorFraction = 0.6
        self.heirsTaxRate = 0.3

        u.vprint(
            'Preparing scenario of %d years for %d individual%s'
            % (self.N_n - 1, self.N_i, ['', 's'][self.N_i - 1])
        )

        self.rho_in = _rho_in(self.yobs, self.N_n)
        self.sigma_n, self.theta_tn, self.Delta_tn = _taxParams(
            self.yobs, self.i_d, self.n_d, self.N_n
        )

        # All variables
        self.b_ij0 = np.zeros((self.N_i, self.N_j))
        self.b_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n + 1))
        self.bp_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))
        self.bm_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))
        self.d_ikn = np.zeros((self.N_i, self.N_k, self.N_n))
        self.f_tn = np.zeros((self.N_t, self.N_n))
        self.g_n = np.zeros((self.N_n))
        self.w_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))
        self.x_ikn = np.zeros((self.N_i, self.N_k, self.N_n))

        return

    def setName(self, name):
        '''
        Override name of the plan. This name is used
        to distinguish the output.
        '''
        self._name = name

        return

    def setVerbose(self):
        '''
        Control verbosity of calculations. True or False for now.
        '''
        u.setVerbose(state)

    def setAssetBalances(self):
        pass

    def readContributions(self, filename):
        '''
        Provide the name of the file containing the financial events
        over the anticipated life span determined by the
        assumed longevity. File can be an excel, or odt file with one
        tab named after each spouse and must have the following
        column headers:

                'year',
                'anticipated wages',
                'ctrb taxable',
                'ctrb 401k',
                'ctrb Roth 401k',
                'ctrb IRA',
                'ctrb Roth IRA',
                'Roth X',
                'big ticket items'

        in any order. A template is provided as an example.
        '''
        self.names, self.timeLists = timelists.read(filename, self.N_i)

        timelists.check(self.names, self.timeLists, self.horizons)
        self.timeListsFileName = filename

        return

    def setHeirsTaxRate(self, rate):
        '''
        Set the heirs tax rate on the tax-deferred portion of the estate.
        '''
        assert 0 <= rate and rate <= 100
        rate /= 100
        u.vprint(
            'Heirs tax rate on tax-deferred portion of estate set to', u.pc(rate, f=0)
        )
        self.heirsTaxRate = rate

        return

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

        u.vprint('Setting pension of', amounts, 'at age(s)', ages)

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

    def setSpendingProfile(profile, frac):
        '''
        Generate time series for spending profile.
        '''
        self.survivorFraction = frac
        self.spedingProfile = profile
        self.xi_in = _xin(profile, frac, self.n_d, self.N_n)

        return

    def setDesiredIncome(self):
        pass

    def setRates(self, method, frm=rates.FROM, to=rates.TO, values=None):
        '''
        Generate rates for return and inflation based on the method and
        years selected. Note that last bound is included.

        The following methods are available:
        default, fixed, realistic, conservative, average, stochastic,
        mean, and historical.

        For 'fixed', values must be provided.
        For 'average', 'mean', 'stochastic', and 'historical', a range of
        years can be provided.

        '''
        dr = rates.rates()
        dr.setMethod(method, frm, to, values)
        self.rateMethod = method
        self.rateFrm = frm
        self.rateTo = to
        self.rateValues = values
        self.rates = dr.genSeries(frm, to, self.span)
        # u.vprint('Generated rate series of', len(self.rates))

        return

    def setAssetBalances(
        self, *, taxable, taxDeferred, taxFree, beneficiary, units=None
    ):
        '''
        Four entries must be provided. The first three are lists
        containing the balance of all assets in each category for
        each spouse. The last one is the fraction of assets left to
        the other spouse as a beneficiary. For single individuals,
        these lists will contain only one entry and the beneficiary
        value is not relevant.

        Units of 'k', or 'M'
        '''
        assert len(taxable) == self.N_i
        assert len(taxDeferred) == self.N_i
        assert len(taxFree) == self.N_i
        assert len(beneficiary) == self.N_i

        fac = u.getUnits(units)

        u.rescale(taxable, fac)
        u.rescale(taxDeferred, fac)
        u.rescale(taxFree, fac)

        self.b['taxable'][:] = taxable
        self.n2balances['tax-deferred'][:] = taxDeferred
        self.n2balances['tax-free'][:] = taxFree
        self.beneficiary = beneficiary

        u.vprint('Taxable balances:', taxable)
        u.vprint('Tax-deferred balances:', taxDeferred)
        u.vprint('Tax-free balances:', taxFree)
        u.vprint('Beneficiary:', beneficiary)

        return
