'''

Owl 
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

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
    2) Tax rate in year n (theta_tn)
    3) Difference in tax brackets (Delta_tn)
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
    # Compute the deltas in-place between brackets, starting from the end.
    for t in range(6, 0, -1):
        for i in range(2):
            brackets_2024[i][t] -= brackets_2024[i][t - 1]
            brackets_2026[i][t] -= brackets_2026[i][t - 1]

    stdDeduction_2024 = np.array([14600, 29200])
    stdDeduction_2026 = np.array([8300, 16600])
    extraDeduction_65 = np.array([1950, 1550])

    # Prepare the 3 arrays to return - use transpose for easy slicing.
    sigma = np.zeros((N_n))
    Delta = np.zeros((N_n, 7))
    theta = np.zeros((N_n, 7))

    filingStatus = len(yobs) - 1
    souls = list(range(len(yobs)))
    thisyear = date.today().year

    for n in range(N_n):
        if thisyear + n < 2026:
            sigma[n] = stdDeduction_2024[filingStatus]
            Delta[n][:] = brackets_2024[filingStatus][:]
        else:
            sigma[n] = stdDeduction_2026[filingStatus]
            Delta[n][:] = brackets_2026[filingStatus][:]

        # Add 65+ additional exemption(s).
        for i in souls:
            if thisyear + n - yobs[i] >= 65:
                sigma[n] += extraDeduction_65[filingStatus]

        # Fill in future tax rates.
        if thisyear + n < 2026:
            theta[n][:] = rates_2024[:]
        else:
            theta[n][:] = rates_2026[:]

        # Check for death in the family.
        if n == n_d - 1:
            souls.remove(i_d)
            filingStatus -= 1

    Delta = Delta.transpose()
    theta = theta.transpose()
    # Return series unindexed for inflation.
    return sigma, theta, Delta


def _rho_in(yobs, N_n):
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


def _xi_n(profile, frac, n_d, N_n):
    '''
    Return time series of spending profile.
    Value is reduced by frac at the passing of one spouse in year n_d.
    Series is unadjusted for inflation.
    '''
    xi = np.ones(N_n)
    if profile == 'flat':
        pass
    elif profile == 'smile':
        x = np.linspace(0, N_n, N_n)
        # Use a cosine +/- 15% combined with a gentle +12% linear increase.
        xi = xi + 0.15 * np.cos((2 * np.pi / (N_n - 1)) * x) + (0.12 / (N_n-1)) * x
        # Normalize to be sum neutral with respect to a flat profile.
        xi = xi * (N_n / xi.sum())
    else:
        u.xprint('Unknown profile ' + profile)

    # Reduce income at passing of one spouse.
    for n in range(n_d, N_n):
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

        # Default interpolation parameters.
        self.interpMethod = 'linear'
        self._interpolator = self._linInterp
        self.interpCenter = 15
        self.interpWidth = 5

        self.N_i = len(yobs)
        assert self.N_i == len(expectancy)
        assert 0 < self.N_i and self.N_i <= 2

        self.filingStatus = ['single', 'married'][self.N_i - 1]

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
            self.i_s = (self.i_d+1)%2
        else:
            self.n_d = self.N_n + 1
            self.i_d = 0

        # Default parameters
        self.psi = 0.15         # Long-term income tax
        self.chi = 0.6          # Survivor fraction
        self.mu = 0.02          # Dividend rate
        self.nu = 0.30          # Heirs tax rate
        self.eta = 0.5          # Spousal withdrawal ratio
        self.phi_j = [1, 1, 1]  # Fraction left to other spouse at death

        # Default to zero pension and social security.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        self.zeta_in = np.zeros((self.N_i, self.N_n))

        u.vprint(
            'Preparing scenario of %d years for %d individual%s'
            % (self.N_n - 1, self.N_i, ['', 's'][self.N_i - 1])
        )

        # Prepare tax time series.
        self.rho_in = _rho_in(self.yobs, self.N_n)
        self.sigma_n, self.theta_tn, self.Delta_tn = _taxParams(
            self.yobs, self.i_d, self.n_d, self.N_n
        )

        # Allocate all variables.
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
        Override name of the plan. Name is used
        to distinguish graph outputs.
        '''
        self._name = name

        return

    def setVerbose(self):
        '''
        Control verbosity of calculations. True or False for now.
        '''
        u.setVerbose(state)

        return

    def setSpousalWithdrawalFraction(self, eta):
        '''
        Set spousal withdrawal fraction. Default 0.5.
        '''
        assert 0 <= eta and eta <= 1
        u.vprint('Spousal withdrawal fraction set to', eta)
        self.eta = eta

        return

    def setSurvivorFraction(self, chi):
        '''
        Set survivor net income fraction of full income. Default 0.6.
        '''
        assert 0 <= chi and chi <= 1
        u.vprint('Survivor net income fraction set to', chi)
        self.chi = chi

    def setDividendRate(self, mu):
        '''
        Set dividend rate on equities. Default 2%.
        '''
        assert 0 <= mu and mu <= 100
        mu /= 100
        u.vprint('Dividend return rate on equities set to', u.pc(mu, f=1))
        self.mu = mu

        return

    def setLongTermIncomeTaxRate(self, psi):
        '''
        Set long-term income tax rate. Default 15%.
        '''
        assert 0 <= psi and psi <= 100
        psi /= 100
        u.vprint('Long-term income tax set to', u.pc(psi, f=0))
        self.psi = psi

        return

    def setBeneficiaryFraction(self, phi):
        '''
        Set fractions of accounts that is left to surviving spouse.
        '''
        assert len(phi) == 3
        u.vprint('Beneficiary spousal beneficiary fractions set to', phi)
        self.phi_j = phi

        return

    def setHeirsTaxRate(self, nu):
        '''
        Set the heirs tax rate on the tax-deferred portion of the estate.
        '''
        assert 0 <= nu and nu <= 100
        nu /= 100
        u.vprint(
            'Heirs tax rate on tax-deferred portion of estate set to', u.pc(nu, f=0)
        )
        self.nu = rate

        return

    def setPension(self, amounts, ages, units=None):
        '''
        Set value of pension for each individual and commencement age.
        Units of 'k', or 'M'
        '''
        assert len(amounts) == self.N_i
        assert len(ages) == self.N_i

        fac = u.getUnits(units)
        u.rescale(amounts, fac)

        u.vprint('Setting pension of', amounts, 'at age(s)', ages)

        thisyear = date.today().year
        # Use zero array freshly initialized.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            ns = max(0, self.yobs[i] + ages[i] - thisyear)
            nd = self.horizons[i]
            self.pi_in[i][ns:nd] = amounts[i]

        return

    def setSocialSecurity(self, amounts, ages, units=None):
        '''
        Set value of social security for each individual and commencement age.
        Units of 'k', or 'M'
        '''
        assert len(amounts) == self.N_i
        assert len(ages) == self.N_i

        fac = u.getUnits(units)
        u.rescale(amounts, fac)

        u.vprint('Setting social security benefits of', amounts, 'at age(s)', ages)

        thisyear = date.today().year
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            ns = max(0, self.yobs[i] + ages[i] - thisyear)
            nd = self.horizons[i]
            self.zeta_in[i][ns:nd] = amounts[i]

        if self.N_i == 2:
            # Approximate calculation for spousal benefit.
            nd = self.horizons[self.i_d]
            self.zeta_in[self.i_s][nd:] = max(amounts[self.i_s], amounts[self.i_d]/2)

        return

    def setSpendingProfile(self, profile, fraction=None):
        '''
        Generate time series for spending profile.
        Surviving spouse fraction can be specified or
        previous value can be used.
        '''
        if fraction is None:
            # Use previous or default.
            fraction = self.chi
        else:
            self.chi = fraction

        u.vprint('Setting', profile, 'spending profile with',
                 fraction, 'survivor fraction.')

        self.spendingProfile = profile
        self.xi_n = _xi_n(profile, fraction, self.n_d, self.N_n)

        return

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
        self.tau_kn = dr.genSeries(self.N_n)
        u.vprint('Generated rate series of', len(self.tau_kn),
                 'with method', method)

        # Once rates are selected, adjust values for inflation.
        self.gamma_n = gamma_n(self.tau_kn, self.N_n)
        self.DeltaBar_tn = self.Delta_tn * self.gamma_n
        self.zetaBar_in = self.zeta_in * self.gamma_n
        self.sigmaBar_n = self.sigma_n * self.gamma_n

        return

    def setAccountBalances(self, *, taxable, taxDeferred, taxFree, units=None):
        '''
        Four entries must be provided. The first three are lists
        containing the balance of all assets in each category for
        each spouse. The last one is the fraction of assets left to
        the other spouse as a beneficiary. For single individuals,
        these lists will contain only one entry and the beneficiary
        value is not relevant. Units of 'k', or 'M'
        '''
        assert len(taxable) == self.N_i
        assert len(taxDeferred) == self.N_i
        assert len(taxFree) == self.N_i

        fac = u.getUnits(units)
        u.rescale(taxable, fac)
        u.rescale(taxDeferred, fac)
        u.rescale(taxFree, fac)

        self.b_ji = np.zeros((self.N_j, self.N_i))
        self.b_ji[0][:] = taxable
        self.b_ji[1][:] = taxDeferred
        self.b_ji[2][:] = taxFree
        self.b_ij = self.b_ji.transpose()

        u.vprint('Taxable balances:', taxable)
        u.vprint('Tax-deferred balances:', taxDeferred)
        u.vprint('Tax-free balances:', taxFree)

        return

    def setInterpolationMethod(self, method, center=15, width=5):
        '''
        Interpolate assets allocation ratios from initial value (today) to
        final value (at the end of horizon).

        Two interpolation methods are supported: linear and s-curve.
        Linear is a straight line between now and the end of the simulation.
        Hyperbolic tangent give a smooth "S" curve centered at point "c"
        with a width "w". Center point defaults to 15 years and width to
        5 years. This means that the transition from initial to final
        will start occuring in 10 years (15-5) and will end in 20 years (15+5).
        '''
        if method == 'linear':
            self._interpolator = self._linInterp
        elif method == 's-curve':
            self._interpolator = self._tanhInterp
            self.interpCenter = center
            self.interpWidth = width
        else:
            u.xprint('Method', method, 'not supported.')

        self.interpMethod = method

        u.vprint('Asset allocation interpolation method set to', method)

        return

    def setAllocations(self, allocType, taxable=None, taxDeferred=None,
                       taxFree=None, generic=None):
        '''
        Single function for setting all types of asset allocations.
        Allocation types are 'account', 'individual', and 'spouses'.

        For 'account' the three different account types taxable, taxDeferred,
        and taxFree need to be set to a list. For spouses,
        taxable = [[[ko00, ko01, ko02, ko03], [kf00, kf01, kf02, kf02]],
                   [[ko10, ko11, ko12, ko13], [kf10, kf11, kf12, kf12]]]
        where ko is the initial allocation while kf is the final. 
        The order of [initial, final] pairs is the same as for the birth
        years and longevity provided. Single only provide one pair for each
        type of savings account.

        For 'individual' allocation type only one generic list needs
        to be provided:
        generic = [[[ko00, ko01, ko02, ko03], [kf00, kf01, kf02, kf02]],
                  [[ko10, ko11, ko12, ko13], [kf10, kf11, kf12, kf12]]].
        while for 'spouses' only one pair needs to be given as follows:
        generic = [[[ko00, ko01, ko02, ko03], [kf00, kf01, kf02, kf02]]]
        as assets are coordinated between accounts and spouses.
        '''
        self.alpha = {}
        if allocType == 'account':
            # Make sure we have proper entries.
            for item in [taxable, taxDeferred, taxFree]:
                assert len(item) == self.N_i
                for i in range(self.N_i):
                    # Initial and final.
                    assert len(item[i]) == 2
                    for z in range(2):
                        assert len(item[i][z]) == self.N_k
                        assert abs(sum(item[i][z]) - 100) < 0.01

            for i in range(self.N_i):
                u.vprint(self.names[i], ': Setting allocation ratios (%) to')
                u.vprint('    taxable:', taxable[i][0], '->', taxable[i][1])
                u.vprint('taxDeferred:', taxDeferred[i][0], '->', taxDeferred[i][1])
                u.vprint('    taxFree:', taxFree[i][0], '->', taxFree[i][1])

            accList = ['taxable', 'taxDeferred', 'taxFree']
            self.alpha['taxable'] = np.array(taxable) / 100
            self.alpha['taxDeferred'] = np.array(taxDeferred) / 100
            self.alpha['taxFree'] = np.array(taxFree) / 100
            self.alpha['account'] = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n+1))
            horizons = self.horizons
            nwhos = self.N_i
        elif allocType == 'individual':
            assert len(generic) == self.N_i
            for i in range(self.N_i):
                # Initial and final.
                assert len(generic[i]) == 2
                for z in range(2):
                    assert len(generic[i][z]) == self.N_k
                    assert abs(sum(generic[i][z]) - 100) < 0.01

            for i in range(self.N_i):
                u.vprint(self.names[i], ': Setting allocation ratios (%) to')
                u.vprint('individual:', generic[i][0], '->', generic[i][1])

            accList = ['generic']
            self.alpha['generic'] = np.array(generic) / 100
            self.alpha['individual'] = np.zeros((self.N_i, self.N_k, self.N_n+1))
            horizons = self.horizons
            nwhos = self.N_i
        elif allocType == 'spouses':
            assert len(generic[0]) == 2
            for z in range(2):
                assert len(generic[0][z]) == self.N_k
                assert abs(sum(generic[0][z]) - 100) < 0.01

            u.vprint('Setting allocation ratios (%) to')
            u.vprint('spouses:', generic[0][0], '->', generic[0][1])

            accList = ['generic']
            self.alpha['generic'] = np.array(generic) / 100
            self.alpha['spouses'] = np.zeros((1, self.N_k, self.N_n+1))
            # Use longest-lived spouse for both time scales.
            horizons = np.ones(self.N_i, dtype=int) * max(self.horizons)
            nwhos = 1

        self.ARCoord = allocType
        self._interpolator(accList, nwhos, horizons)

        u.vprint('Interpolated assets allocation ratios using',
                 self.interpMethod, 'method.')

        return

    def _linInterp(self, accList, N_i, numPoints):
        '''
        Utility function to interpolate multiple cases using
        a linear interpolation. Range goes one more year than
        horizon as year passed death includes estate.
        '''
        for accName in accList:
            for i in range(N_i):
                for k in range(self.N_k):
                    dat = np.linspace(
                        self.alpha[accName][i][0][k],
                        self.alpha[accName][i][1][k],
                        numPoints[i] + 1,
                    )
                    if self.ARCoord == 'account':
                        j = ['taxable', 'taxDeferred', 'taxFree'].index(accName)
                        for n in range(numPoints[i] + 1):
                            self.alpha[self.ARCoord][i][j][k][n] = dat[n]
                    else:
                        for n in range(numPoints[i] + 1):
                            self.alpha[self.ARCoord][i][k][n] = dat[n]

        return

    def _tanhInterp(self, accList, N_i, numPoints):
        '''
        Utility function to interpolate multiple cases using hyperbolic
        tangent interpolation. "c" is the center where the inflection point
        is, and "w" is the width of the transition.
        '''
        c = self.interpCenter
        w = self.interpWidth
        for accName in accList:
            for i in range(N_i):
                for k in range(self.N_k):
                    t = np.linspace(0, numPoints[i], numPoints[i] + 1)
                    a = self.alpha[accName][i][0][k]
                    b = self.alpha[accName][i][1][k]
                    dat = a + 0.5 * (b - a) * (1 + np.tanh((t - c) / w))
                    if self.ARCoord == 'account':
                        j = ['taxable', 'taxDeferred', 'taxFree'].index(accName)
                        for n in range(numPoints[i] + 1):
                            self.alpha[self.ARCoord][i][j][k][n] = dat[n]
                    else:
                        for n in range(numPoints[i] + 1):
                            self.alpha[self.ARCoord][i][k][n] = dat[n]

        return

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
        self.inames, self.timeLists = timelists.read(filename, self.N_i, self.horizons)

        timelists.check(self.inames, self.timeLists, self.horizons)
        self.timeListsFileName = filename

        self.omega_in = np.zeros((self.N_i, self.N_n))
        self.Lambda_in = np.zeros((self.N_i, self.N_n))
        self.kappa_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))
        # Now fill in parameters.
        for i in range(self.N_i):
            h = self.horizons[i]
            self.omega_in[i][:h] = self.timeLists[i]['anticipated wages'][:h]
            self.Lambda_in[i][:h] = self.timeLists[i]['big ticket items'][:h]
            self.kappa_ijkn[i][0][0][:h] = self.timeLists[i]['ctrb taxable'][:h]
            self.kappa_ijkn[i][1][0][:h] = self.timeLists[i]['ctrb 401k'][:h]
            self.kappa_ijkn[i][1][0][:h] += self.timeLists[i]['ctrb IRA'][:h]
            self.kappa_ijkn[i][2][0][:h] = self.timeLists[i]['ctrb Roth 401k'][:h]
            self.kappa_ijkn[i][2][0][:h] += self.timeLists[i]['ctrb Roth IRA'][:h]

        return

