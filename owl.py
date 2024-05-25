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
from scipy import optimize
from datetime import date

import utils as u
import rates
import timelists


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
        # First check if shortest-lived individual is still with us.
        if n == n_d:
            souls.remove(i_d)
            filingStatus -= 1

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

        # Fill in future tax rates for year n.
        if thisyear + n < 2026:
            theta[n][:] = rates_2024[:]
        else:
            theta[n][:] = rates_2026[:]

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
        # Normalize to be sum-neutral with respect to a flat profile.
        xi = xi * (N_n / xi.sum())
    else:
        u.xprint('Unknown profile ' + profile)

    # Reduce income needs after passing of one spouse.
    for n in range(n_d, N_n):
        xi[n] *= frac

    return xi


def _qC(C, N1, N2=1, N3=1, N4=1):
    '''
    Index range accumulator.
    '''
    return C + N1 * N2 * N3 * N4


def _q1(C, l1, N1=None):
    '''
    Index mapping function.
    '''
    return C + l1

def _q2(C, l1, l2=0, N1=None, N2=1):
    '''
    Index mapping function.
    '''
    return C + l1 * N2 + l2 

def _q3(C, l1, l2=0, l3=0, N1=None, N2=1, N3=1):
    '''
    Index mapping function.
    '''
    return C + l1 * N2 * N3 + l2 * N3 + l3 

def _q4(C, l1, l2=0, l3=0, l4=0, N1=None, N2=1, N3=1, N4=1):
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
        assert 0 < self.N_i and self.N_i <= 2, 'Cannot support %d individuals.'%self.N_i
        assert self.N_i == len(expectancy), 'Expectancy must have %d entries.'%self.N_i

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

        self.inames = ['Person 1', 'Person 2']

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

        self.indexed = False

        return

    def setName(self, name):
        '''
        Override name of the plan. Name is used
        to distinguish graph outputs.
        '''
        self._name = name

        return

    def setVerbose(self, state=True):
        '''
        Control verbosity of calculations. True or False for now.
        '''
        u.setVerbose(state)

        return

    def setSpousalWithdrawalFraction(self, eta):
        '''
        Set spousal withdrawal fraction. Default 0.5.
        '''
        assert 0 <= eta and eta <= 1, 'Fraction must be between 0 and 1.'
        u.vprint('Spousal withdrawal fraction set to', eta)
        self.eta = eta

        return

    def setDividendRate(self, mu):
        '''
        Set dividend rate on equities. Default 2%.
        '''
        assert 0 <= mu and mu <= 100, 'Rate must be between 0 and 100.'
        mu /= 100
        u.vprint('Dividend return rate on equities set to', u.pc(mu, f=1))
        self.mu = mu

        return

    def setLongTermIncomeTaxRate(self, psi):
        '''
        Set long-term income tax rate. Default 15%.
        '''
        assert 0 <= psi and psi <= 100, 'Rate must be between 0 and 100.'
        psi /= 100
        u.vprint('Long-term income tax set to', u.pc(psi, f=0))
        self.psi = psi

        return

    def setBeneficiaryFraction(self, phi):
        '''
        Set fractions of accounts that is left to surviving spouse.
        '''
        assert len(phi) == self.N_j, 'Fractions must have %d entries.'%self.N_j
        for j in range(self.N_j):
            assert 0<= phi[j] <= 1, 'Fractions must be between 0 and 1.'

        u.vprint('Beneficiary spousal beneficiary fractions set to', phi)
        self.phi_j = phi

        return

    def setHeirsTaxRate(self, nu):
        '''
        Set the heirs tax rate on the tax-deferred portion of the estate.
        '''
        assert 0 <= nu and nu <= 100, 'Rate must be between 0 and 100.'
        nu /= 100
        u.vprint(
            'Heirs tax rate on tax-deferred portion of estate set to', u.pc(nu, f=0)
        )
        self.nu = nu

        return

    def setPension(self, amounts, ages, units=None):
        '''
        Set value of pension for each individual and commencement age.
        Units of 'k', or 'M'
        '''
        assert len(amounts) == self.N_i, 'Amounts must have %d entries.'%self.N_i
        assert len(ages) == self.N_i, 'Ages must have %d entries.'%self.N_i

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
        assert len(amounts) == self.N_i, 'Amounts must have %d entries.'%self.N_i
        assert len(ages) == self.N_i, 'Ages must have %d entries.'%self.N_i

        fac = u.getUnits(units)
        u.rescale(amounts, fac)

        u.vprint('Setting social security benefits of', amounts, 'at age(s)', ages)

        self.indexed = False
        thisyear = date.today().year
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            ns = max(0, self.yobs[i] + ages[i] - thisyear)
            nd = self.horizons[i]
            self.zeta_in[i][ns:nd] = amounts[i]

        if self.N_i == 2:
            # Approximate calculation for spousal benefit (only valid at FRA).
            nd = self.horizons[self.i_d]
            self.zeta_in[self.i_s][nd:] = max(amounts[self.i_s], amounts[self.i_d]/2)

        return

    def setSpendingProfile(self, profile, fraction=0.6):
        '''
        Generate time series for spending profile.
        Surviving spouse fraction can be specified or
        previous value can be used.
        '''
        self.chi = fraction

        u.vprint('Setting', profile, 'spending profile with',
                 fraction, 'survivor fraction.')

        self.spendingProfile = profile
        self.xi_n = _xi_n(profile, fraction, self.n_d, self.N_n)

        return

    def setRates(self, method, frm=rates.FROM, values=None):
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
        to = frm + self.N_n - 1
        dr.setMethod(method, frm, to, values)
        self.rateMethod = method
        self.rateFrm = frm
        self.rateTo = to
        self.rateValues = values
        self.tau_kn = dr.genSeries(self.N_n)
        u.vprint('Generated rate series of', len(self.tau_kn[0]),
                 'years with method', method)

        # Once rates are selected, build inflation factors.
        self.gamma_n = gamma_n(self.tau_kn, self.N_n)
        self.indexed = False

        return

    def _index(self):
        '''
        Adjust parameters that follow inflation.
        '''
        if self.indexed == False:
            u.vprint('Adjusting parameters for inflation.')
            self.DeltaBar_tn = self.Delta_tn * self.gamma_n
            self.zetaBar_in = self.zeta_in * self.gamma_n
            self.sigmaBar_n = self.sigma_n * self.gamma_n
            self.indexed = True

        return

    def setAccountBalances(self, *, taxable, taxDeferred, taxFree, units=None):
        '''
        Three lists containing the balance of all assets in each category for
        each spouse.  For single individuals, these lists will contain only
        one entry. Units are 'k', or 'M'.
        '''
        assert len(taxable) == self.N_i, 'taxable must have %d entries.'%self.N_i
        assert len(taxDeferred) == self.N_i, 'taxDeferred must have %d entries.'%self.N_i
        assert len(taxFree) == self.N_i, 'taxFree must have %d entries.'%self.N_i

        fac = u.getUnits(units)
        u.rescale(taxable, fac)
        u.rescale(taxDeferred, fac)
        u.rescale(taxFree, fac)

        self.b_ji = np.zeros((self.N_j, self.N_i))
        self.b_ji[0][:] = taxable
        self.b_ji[1][:] = taxDeferred
        self.b_ji[2][:] = taxFree
        self.beta_ij = self.b_ji.transpose()

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

    def setAllocationRatios(self, allocType, taxable=None, taxDeferred=None,
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

        For the 'individual' allocation type, only one generic list needs
        to be provided:
        generic = [[[ko00, ko01, ko02, ko03], [kf00, kf01, kf02, kf02]],
                  [[ko10, ko11, ko12, ko13], [kf10, kf11, kf12, kf12]]].
        while for 'spouses' only one pair needs to be given as follows:
        generic = [[ko00, ko01, ko02, ko03], [kf00, kf01, kf02, kf02]]
        as assets are coordinated between accounts and spouses.
        '''
        self.alpha = {}
        self.alpha_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n+1))
        if allocType == 'account':
            # Make sure we have proper entries.
            for item in [taxable, taxDeferred, taxFree]:
                assert len(item) == self.N_i, '%s must one entry per individual.'%(item)
                for i in range(self.N_i):
                    # Initial and final.
                    assert len(item[i]) == 2, '%s[%d] must have 2 lists (initial and final).'%(item, i)
                    for z in range(2):
                        assert len(item[i][z]) == self.N_k, '%s[%d][%d] must have %d entries.'%(item, i, z, self.N_k)
                        assert abs(sum(item[i][z]) - 100) < 0.01, 'Sum of percentages must add to 100.'

            for i in range(self.N_i):
                u.vprint(self.inames[i], ': Setting gliding allocation ratios (%) to')
                u.vprint('    taxable:', taxable[i][0], '->', taxable[i][1])
                u.vprint('taxDeferred:', taxDeferred[i][0], '->', taxDeferred[i][1])
                u.vprint('    taxFree:', taxFree[i][0], '->', taxFree[i][1])

            # Order now j, i, 0/1, k
            self.alpha[0] = np.array(taxable) / 100
            self.alpha[1] = np.array(taxDeferred) / 100
            self.alpha[2] = np.array(taxFree) / 100
            for i in range(self.N_i):
                Nn = self.horizons[i]
                for j in range(self.N_j):
                    for k in range(self.N_k):
                        start = self.alpha[j][i][0][k]
                        end = self.alpha[j][i][1][k]
                        dat = self._interpolator(start, end, Nn)
                        self.alpha_ijkn[i][j][k][:Nn+1] = dat[:Nn+1]

        elif allocType == 'individual':
            assert len(generic) == self.N_i, 'generic must have one list per individual.'
            for i in range(self.N_i):
                # Initial and final.
                assert len(generic[i]) == 2, 'generic[%d] must have 2 lists (initial and final).'%i
                for z in range(2):
                    assert len(generic[i][z]) == self.N_k, 'generic[%d][%d] must have %d entries.'%(i, z, self.N_k)
                    assert abs(sum(generic[i][z]) - 100) < 0.01, 'Sum of percentages must add to 100.'

            for i in range(self.N_i):
                u.vprint(self.inames[i], ': Setting gliding allocation ratios (%) to')
                u.vprint('individual:', generic[i][0], '->', generic[i][1])

            for i in range(self.N_i):
                Nn = self.horizons[i]
                for k in range(self.N_k):
                    start = generic[i][0][k]
                    end = generic[i][1][k]
                    dat = self._interpolator(start, end, Nn+1)
                    for j in range(self.N_j):
                        self.alpha_ijkn[i][j][k][:Nn+1] = dat[:Nn+1]

        elif allocType == 'spouses':
            assert len(generic) == 2, 'generic must have 2 entries (initial and final).'
            for z in range(2):
                assert len(generic[z]) == self.N_k, 'generic[%d] must have %d entries.'%(z, self.N_k)
                assert abs(sum(generic[z]) - 100) < 0.01, 'Sum of percentages must add to 100.'

            u.vprint('Setting gliding allocation ratios (%) to')
            u.vprint('spouses:', generic[0], '->', generic[1])

            # Use longest-lived spouse for both time scales.
            Nn = max(self.horizons)

            for k in range(self.N_k):
                start = generic[0][k]
                end = generic[1][k]
                dat = self._interpolator(start, end, Nn+1)
                for i in range(self.N_i):
                    for j in range(self.N_j):
                        self.alpha_ijkn[i][j][k][:Nn+1] = dat[:Nn+1]

        self.ARCoord = allocType

        u.vprint('Interpolated assets allocation ratios using',
                 self.interpMethod, 'method.')

        return

    def _linInterp(self, a, b, numPoints):
        '''
        Utility function to interpolate allocations using
        a linear interpolation. Range goes one more year than
        horizon as year passed death includes estate.
        '''
        dat = np.linspace(a, b, numPoints + 1)

        return dat

    def _tanhInterp(self, a, b, numPoints):
        '''
        Utility function to interpolate allocations using a hyperbolic
        tangent interpolation. "c" is the year where the inflection point
        is happening, and "w" is the width of the transition.
        '''
        c = self.interpCenter
        w = self.interpWidth
        t = np.linspace(0, numPoints, numPoints + 1)
        dat = a + 0.5 * (b - a) * (1 + np.tanh((t - c) / w))
        x = a/(dat[0] + 1.e-14)
        dat *= x

        return dat

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

    def _buildIndexMap(self):
        '''
        Refer to companion document for explanations.
        '''
        Ni = self.N_i
        Nj = self.N_j
        Nk = self.N_k
        Nn = self.N_n
        Nt = self.N_t

        C = {}
        C['b'] = 0
        C['b+'] = _qC(C['b'], Ni, Nj, Nk, Nn+1)
        C['b-'] = _qC(C['b+'], Ni, Nj, Nk, Nn)
        C['d'] = _qC(C['b-'], Ni, Nj, Nk, Nn)
        C['f'] = _qC(C['d'], Ni, Nk, Nn)
        C['g'] = _qC(C['f'], Nt, Nn)
        C['w'] = _qC(C['g'], Nn)
        C['x'] = _qC(C['w'], Ni, Nj, Nk, Nn)
        C['zzz'] = _qC(C['x'], Ni, Nk, Nn)
        self.nvars = C['zzz']

        self.C = C
        u.vprint('Problem has', len(C) - 1,
            'distinct variables with', self.nvars, 'total dimensions.')

        return

    def _buildConstraints(self):
        '''
        Refer to companion document for explanations.
        '''
        Ni = self.N_i
        Nj = self.N_j
        Nk = self.N_k
        Nn = self.N_n
        Nt = self.N_t

        Cb = self.C['b']
        Cbp = self.C['b+']
        Cbm = self.C['b-']
        Cd = self.C['d']
        Cf = self.C['f']
        Cg = self.C['g']
        Cw = self.C['w']
        Cx = self.C['x']
        tau1 = 1 + self.tau_kn

        Au = []
        uvec = []
        Ae = []
        vvec = []

        # RMDs inequality.
        for i in range(Ni):
            for n in range(Nn):
                row = np.zeros(self.nvars)
                for k in range(Nk):
                    row[_q4(Cw, i, 1, k, n, Ni, Nj, Nk, Nn)] = -1
                    row[_q4(Cb, i, 1, k, n, Ni, Nj, Nk, Nn)] = self.rho_in[i][n]
                Au.append(row)
                uvec.append(0)

        # Income tax bracket inequalities.
        for t in range(Nt):
            for n in range(Nn):
                row = np.zeros(self.nvars)
                row[_q2(Cf, t, n, Nt, Nn)] = 1
                Au.append(row)
                uvec.append(1)

        for i in range(Ni):
            for j in range(Nj):
                for k in range(Nk):
                    for n in range(Nn):
                        row = np.zeros(self.nvars)
                        rhs = self.kappa_ijkn[i][j][k][n]*(.5 + tau1[k][n]/2)
                        row[_q4(Cb, i, j, k, n+1, Ni, Nj, Nk, Nn)] = 1
                        row[_q4(Cb, i, j, k, n, Ni, Nj, Nk, Nn)] = -tau1[k, n]
                        row[_q3(Cx, i, k, n, Ni, Nk, Nn)] = -(np.kron(j, 2) - np.kron(j, 1))*tau1[k, n]
                        row[_q4(Cbp, i, j, k, n, Ni, Nj, Nk, Nn)] = -1
                        row[_q4(Cbm, i, j, k, n, Ni, Nj, Nk, Nn)] = 1
                        row[_q4(Cw, i, j, k, n, Ni, Nj, Nk, Nn)] = 1
                        row[_q3(Cw, i, k, n, Ni, Nk, Nn)] = -np.kron(j, 0)
                        Ae.append(row)
                        vvec.append(rhs)

        # Rebalancing equalities 1/2.
        for i in range(Ni):
            for j in range(Nj):
                for n in range(Nn):
                    row = np.zeros(self.nvars)
                    rhs = 0
                    for k in range(Nk):
                        row[_q4(Cbp, i, j, k, n, Ni, Nj, Nk, Nn)] = 1
                        row[_q4(Cbm, i, j, k, n, Ni, Nj, Nk, Nn)] = -1
                    Ae.append(row)
                    vvec.append(rhs)

        # Rebalancing equalities 2/2.
        for i in range(Ni):
            for j in range(Nj):
                for k in range(Nk):
                    for n in range(Nn):
                        row = np.zeros(self.nvars)
                        rhs = 0
                        row[_q4(Cb, i, j, k, n, Ni, Nj, Nk, Nn)] = -1
                        row[_q4(Cbm, i, j, k, n, Ni, Nj, Nk, Nn)] = 1
                        Ae.append(row)
                        vvec.append(rhs)

        # Net income equalities 1/2.
        for n in range(Nn):
            row = np.zeros(self.nvars)
            rhs = 0
            row[_q1(Cg, n, Nn)] = 1
            for t in range(Nt):
                row[_q2(Cf, t, n, Nt, Nn)] = self.DeltaBar_tn[t][n]*self.theta_tn[t][n]
            for i in range(Ni):
                rhs += (self.omega_in[i][n] + self.zetaBar_in[i][n] 
                        + self.pi_in[i][n] + self.Lambda_in[i][n]
                        - 0.5*self.psi*self.mu*self.kappa_ijkn[i][0][0][n])
                row[_q4(Cb, i, 0, 0, n, Ni, Nj, Nk, Nn)] = self.mu*self.psi
                row[_q4(Cw, i, 0, 0, n, Ni, Nj, Nk, Nn)] = self.psi*max(0, self.tau_kn[0][n])
                row[_q4(Cbm, i, 0, 0, n, Ni, Nj, Nk, Nn)] = self.psi*max(0, self.tau_kn[0][n])
                for k in range(Nk):
                    row[_q3(Cd, i, k, n, Ni, Nk, Nn)] = 1
                    for j in range(Nj):
                        row[_q4(Cw, i, j, k, n, Ni, Nj, Nk, Nn)] = -1
            Ae.append(row)
            vvec.append(rhs)

        # Net income equalities 2/2.
        for n in range(Nn-1):
            row = np.zeros(self.nvars)
            rhs = 0
            row[_q1(Cg, n+1, Nn)] = 1
            row[_q1(Cg, n, Nn)] = -tau1[3][n]*self.xi_n[n]
            Ae.append(row)
            vvec.append(rhs)

        # Taxable ordinary income.
        for n in range(Nn):
            row = np.zeros(self.nvars)
            rhs = -self.sigmaBar_n[n]
            for t in range(Nt):
                row[_q2(Cf, t, n, Nt, Nn)] = self.DeltaBar_tn[t][n]
            for i in range(Ni):
                rhs += (self.omega_in[i][n] + 0.85*self.zetaBar_in[i][n] + self.pi_in[i][n])
                for k in range(Nk):
                    rhs += 0.5*(1 - np.kron(k, 0))*self.tau_kn[k][n]*self.kappa_ijkn[i][0][k][n]
                    row[_q4(Cw, i, 1, k, n, Ni, Nj, Nk, Nn)] = -1
                    row[_q3(Cx, i, k, n, Ni, Nk, Nn)] = -1
                    row[_q4(Cb, i, 0, k, n, Ni, Nj, Nk, Nn)] = (1 - np.kron(k, 0))*self.tau_kn[k][n]
            Ae.append(row)
            vvec.append(rhs)

        # Set initial balances and asset allocation.
        for k in range(Nk):
            if self.ARCoord == 'accounts':
                for i in range(Ni):
                    for j in range(Nj):
                        row = np.zeros(self.nvars)
                        row[_q4(Cb, i, j, k, 0)] = 1
                        rhs = self.beta_ij[i][j]*self.alpha_ijkn[i][j][k][0]
                        Ae.append(row)
                        vvec.append(rhs)

                        for n in range(Nn):
                            row2 = np.zeros(self.nvars)
                            rhs2 = 0
                            for k2 in range(Nk):
                                row2[_q4(Cb, i, j, k2, n)] = np.kron(k, k2) - self.alpha_ijkn[i][j][k][n]
                            Ae.append(row2)
                            vvec.append(rhs2)

            elif self.ARCoord == 'individual':
                for i in range(Ni):
                    row = np.zeros(self.nvars)
                    rhs = self.beta_ij[i][j]*self.alpha_ijkn[i][j][k][0]
                    for j in range(Nj):
                        row[_q4(Cb, i, j, k, 0)] = 1
                    Ae.append(row)
                    vvec.append(rhs)

                    for n in range(Nn):
                        row2 = np.zeros(self.nvars)
                        rhs2 = 0
                        for j in range(Nj):
                            for k2 in range(Nk):
                                row2[_q4(Cb, i, j, k2, n)] = np.kron(k, k2) - self.alpha_ijkn[i][j][k][n]
                        Ae.append(row2)
                        vvec.append(rhs2)

            elif self.ARCoord == 'spouses':
                row = np.zeros(self.nvars)
                rhs = self.beta_ij[i][j]*self.alpha_ijkn[i][j][k][0]
                for i in range(Ni):
                    for j in range(Nj):
                        row[_q4(Cb, i, j, k, 0)] = 1
                Ae.append(row)
                vvec.append(rhs)
                for n in range(Nn):
                    row2 = np.zeros(self.nvars)
                    rhs2 = 0
                    for i in range(Ni):
                        for j in range(Nj):
                            for k2 in range(Nk):
                                row2[_q4(Cb, i, j, k2, n)] = np.kron(k, k2) - self.alpha_ijkn[i][j][k][n]
                    Ae.append(row2)
                    vvec.append(rhs2)

        u.vprint('There are', len(vvec),
            'equality contraints and', len(uvec), 'inequality constraints.')

        self.A_ub = np.array(Au)
        self.b_ub = np.array(uvec)
        self.A_eq = np.array(Ae)
        self.b_eq = np.array(vvec)

        return

    def solve(self):
        '''
        Refer to companion document for explanations.
        '''
        self._index()
        self._buildIndexMap()
        self._buildConstraints()

        c = np.zeros(self.nvars)
        c[_q1(self.C['g'], 0, self.N_n)] = -1
        for t in range(self.N_t):
            for n in range(self.N_n):
                c[_q2(self.C['f'], t, n, self.N_t, self.N_n)] = 2**t

        solution = optimize.linprog(c, A_ub=self.A_ub, b_ub=self.b_ub, A_eq=self.A_eq, b_eq=self.b_eq,
                                     method='highs-ipm', options={'maxiter':10000})
        if solution.success != True:
                print('WARNING: Optimization failed:', solution.message, solution.success)

        print(solution.x)


