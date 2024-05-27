'''

Owl 
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

Copyright -- Martin-D. Lacasse (2024)

Disclaimer: This program comes with no guarantee. Use at your own risk.
'''

###########################################################################
import numpy as np
from scipy import optimize
from datetime import date

import utils as u
import rates
import timelists


def setVerbose(self, state=True):
    '''
    Control verbosity of calculations. True or False for now.
    Return previous state.
    '''
    return u.setVerbose(state)


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
    3) Delta from top to bottom of tax brackets (Delta_tn)
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

    # Return series unindexed for inflation, in STD order.
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


def _xi_n(profile, frac, n_d, N_n, a=15, b=12):
    '''
    Return time series of spending profile.
    Value is reduced by frac starting in year n_d,
    after the passing of shortest-lived spouse.
    Series is unadjusted for inflation.
    '''
    xi = np.ones(N_n)
    if profile == 'flat':
        pass
    elif profile == 'smile':
        x = np.linspace(0, N_n-1, N_n)
        a /= 100
        b /= 100
        # Use a cosine +/- 15% combined with a gentle +12% linear increase.
        xi = xi + a * np.cos((2 * np.pi / (N_n - 1)) * x) + (b / (N_n-1)) * x
        # Normalize to be sum-neutral with respect to a flat profile.
        xi = xi * (N_n / xi.sum())
    else:
        u.xprint('Unknown profile', profile)

    # Reduce income needs after passing of one spouse.
    xi[n_d:] *= frac

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

def _q2(C, l1, l2, N1, N2):
    '''
    Index mapping function.
    '''
    return C + l1 * N2 + l2 

def _q3(C, l1, l2, l3, N1, N2, N3):
    '''
    Index mapping function.
    '''
    return C + l1 * N2 * N3 + l2 * N3 + l3 

def _q4(C, l1, l2, l3, l4, N1, N2, N3, N4):
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

        # Default interpolation parameters for allocation ratios.
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
        self.year_n = np.linspace(thisyear, thisyear+self.N_n-1, self.N_n)
        # Handle passing of one spouse before the other.
        if self.N_i == 2:
            self.n_d = min(self.horizons)
            self.i_d = self.horizons.index(self.n_d)
            self.i_s = (self.i_d+1)%2
        else:
            self.n_d = self.N_n + 2     # Push beyond upper bound.
            self.i_d = 0
            self.i_s = -1

        # Default parameters:
        self.psi = 0.15         # Long-term income tax rate (decimal)
        self.chi = 0.6          # Survivor fraction
        self.mu = 0.02          # Dividend rate (decimal)
        self.nu = 0.30          # Heirs tax rate (decimal)
        self.eta = 0.5          # Spousal withdrawal ratio
        self.phi_j = [1, 1, 1]  # Fraction left to other spouse at death

        # Placeholder for before reading contributions file.
        self.inames = ['Person 1', 'Person 2']

        # Default to zero pension and social security.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        self.zeta_in = np.zeros((self.N_i, self.N_n))

        # Other parameters.
        self.omega_in = np.zeros((self.N_i, self.N_n))
        self.Lambda_in = np.zeros((self.N_i, self.N_n))
        self.kappa_ijn = np.zeros((self.N_i, self.N_j, self.N_n))
        self.kappa_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))

        u.vprint(
            'Preparing scenario of %d years for %d individual%s.'
            % (self.N_n - 1, self.N_i, ['', 's'][self.N_i - 1])
        )
        for i in range(self.N_i):
            u.vprint('%s: from %d -> %d.'%(self.inames[i], thisyear, thisyear+self.horizons[i]-1))

        # Prepare income tax time series.
        self.rho_in = _rho_in(self.yobs, self.N_n)
        self.sigma_n, self.theta_tn, self.Delta_tn = _taxParams(
            self.yobs, self.i_d, self.n_d, self.N_n
        )

        self.adjustParameters = True

        return

    def setName(self, name):
        '''
        Override name of the plan. Name is used
        to distinguish graph outputs.
        '''
        self._name = name

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

        self.adjustParameters = True
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

        u.vprint('Setting', profile, 'spending profile.')
        if self.N_i == 2:
            u.vprint('\tUsing ', fraction, 'survivor fraction.')

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
        to = frm + self.N_n - 1     # 'to' is inclusive: subtract 1
        dr.setMethod(method, frm, to, values)
        self.rateMethod = method
        self.rateFrm = frm
        self.rateTo = to
        self.rateValues = values
        self.tau_kn = dr.genSeries(self.N_n)
        u.vprint('Generating rate series of', len(self.tau_kn[0]),
                 'years using', method, 'method.')

        # Once rates are selected, (re)build inflation multipliers.
        self.gamma_n = gamma_n(self.tau_kn, self.N_n)
        self.adjustParameters = True

        return

    def _adjustParameters(self):
        '''
        Adjust parameters that follow inflation or allocations.
        '''
        if self.adjustParameters == True:
            u.vprint('Adjusting parameters for inflation.')
            self.DeltaBar_tn = self.Delta_tn * self.gamma_n
            self.zetaBar_in = self.zeta_in * self.gamma_n
            self.sigmaBar_n = self.sigma_n * self.gamma_n
            # Partition contributions along chosen allocations.
            for i in range(self.N_i):
                for j in range(self.N_j):
                    for n in range(self.N_n):
                        fac = self.kappa_ijn[i][j][n]
                        for k in range(self.N_k):
                            self.kappa_ijkn[i][j][k][n] = fac*self.alpha_ijkn[i][j][k][n]

            self.adjustParameters = False

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
        self.alpha_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n+1))
        if allocType == 'account':
            # Make sure we have proper input.
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

            # Order now is j, i, 0/1, k.
            alpha = {}
            alpha[0] = np.array(taxable) / 100
            alpha[1] = np.array(taxDeferred) / 100
            alpha[2] = np.array(taxFree) / 100
            for i in range(self.N_i):
                Nn = self.horizons[i]
                for j in range(self.N_j):
                    for k in range(self.N_k):
                        start = alpha[j][i][0][k]
                        end = alpha[j][i][1][k]
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

        u.vprint('Interpolating assets allocation ratios using',
                 self.interpMethod, 'method.')

        return

    def _linInterp(self, a, b, numPoints):
        '''
        Utility function to interpolate allocations using
        a linear interpolation.
        '''
        # num goes one more year as endpoint=True.
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
        # Solve 2x2 system to match end points exactly.
        th0 = np.tanh((t[0]-c)/w)
        thN = np.tanh((t[numPoints]-c)/w)
        k11 = 0.5 - 0.5*th0
        k21 = 0.5 - 0.5*thN
        k12 = 0.5 + 0.5*th0
        k22 = 0.5 + 0.5*thN
        _b = (b - (k21/k11)*a)/(k22 - (k21/k11)*k12)
        _a = (a - k12*_b)/k11
        dat = _a + 0.5 * (_b - _a) * (1 + np.tanh((t - c) / w))

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

        # Now fill in parameters.
        for i in range(self.N_i):
            h = self.horizons[i]
            self.omega_in[i][:h] = self.timeLists[i]['anticipated wages'][:h]
            self.Lambda_in[i][:h] = self.timeLists[i]['big ticket items'][:h]
            self.kappa_ijn[i][0][:h] = self.timeLists[i]['ctrb taxable'][:h]
            self.kappa_ijn[i][1][:h] = self.timeLists[i]['ctrb 401k'][:h]
            self.kappa_ijn[i][1][:h] += self.timeLists[i]['ctrb IRA'][:h]
            self.kappa_ijn[i][2][:h] = self.timeLists[i]['ctrb Roth 401k'][:h]
            self.kappa_ijn[i][2][:h] += self.timeLists[i]['ctrb Roth IRA'][:h]

        return

    def _buildOffsetMap(self):
        '''
        Refer to companion document for explanations.
        '''
        Ni = self.N_i
        Nj = self.N_j
        Nk = self.N_k
        Nn = self.N_n
        Nt = self.N_t

        # Stack variables in block vector.
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

    def _buildConstraints(self, objective, options):
        '''
        Refer to companion document for explanations.
        '''
        Ni = self.N_i
        Nj = self.N_j
        Nk = self.N_k
        Nn = self.N_n
        Nt = self.N_t
        i_d = self.i_d
        i_s = self.i_s
        n_d = self.n_d

        Cb = self.C['b']
        Cbp = self.C['b+']
        Cbm = self.C['b-']
        Cd = self.C['d']
        Cf = self.C['f']
        Cg = self.C['g']
        Cw = self.C['w']
        Cx = self.C['x']
        tau1_kn = 1 + self.tau_kn

        # Matrices and vectors.
        Au = []
        uvec = []
        Ae = []
        vvec = []

        # RMDs inequalities.
        for i in range(Ni):
            for n in range(Nn):
                row = np.zeros(self.nvars)
                rhs = 0
                for k in range(Nk):
                    row[_q4(Cw, i, 1, k, n, Ni, Nj, Nk, Nn)] = -1
                    row[_q4(Cb, i, 1, k, n, Ni, Nj, Nk, Nn+1)] = self.rho_in[i][n]
                Au.append(row)
                uvec.append(rhs)

        # Income tax bracket inequalities.
        for t in range(Nt):
            for n in range(Nn):
                row = np.zeros(self.nvars)
                rhs = 1
                row[_q2(Cf, t, n, Nt, Nn)] = 1
                Au.append(row)
                uvec.append(rhs)

        # Deposits should be zero in that case.
        if objective == 'maxIncome':
            for i in range(Ni):
                for k in range(Nk):
                    for n in range(Nn):
                        row = np.zeros(self.nvars)
                        rhs = 0
                        row[_q3(Cd, i, k, n, Ni, Nk, Nn)] = 1
                        Ae.append(row)
                        vvec.append(rhs)

        # Impose a constraint on estate.
        if 'estate' in options:
            estate = options['estate']
            assert len(estate) == Ni, 'Estate values must have %d lists.'%Ni
            for i in range(Ni):
                assert len(estate[i]) == Nj, 'Sublists of estate values must have %d entries.'%Nj
            u.vprint('Adding estate constraint of:', estate)
        else:
            # Set default values to $1.
            if Ni == 1:
                estate = [[1 for j in range(Nj)]]
            else:
                estate = [[1 for j in range(Nj)], [1 for j in range(Nj)]]

        for i in range(Ni):
            for j in range(Nj):
                row = np.zeros(self.nvars)
                for k in range(Nk):
                    row[_q4(Cb, i, j, k, Nn, Ni, Nj, Nk, Nn+1)] = 1
                Ae.append(row)
                vvec.append(estate[i][j])

        # Limit Roth conversions.
        if 'maxRothConversion' in options:
            rhs = options['maxRothConversion']
            u.vprint('Limiting Roth conversions to:', rhs)
            for i in range(Ni):
                for k in range(Nk):
                    for n in range(Nn):
                        row = np.zeros(self.nvars)
                        row[_q3(Cx, i, k, n, Ni, Nk, Nn)] = 1
                        Au.append(row)
                        uvec.append(rhs)

        # Account balances carried from year to year.
        # Considering spousal asset transfer.
        # Using hybrid approach with 'if' statements and Kronecker deltas.
        for i in range(Ni):
            for j in range(Nj):
                for k in range(Nk):
                    for n in range(Nn):
                        row = np.zeros(self.nvars)
                        fac1 = (1 - np.kron(n, n_d - 1)*np.kron(i, i_d))
                        rhs = (fac1*self.kappa_ijkn[i][j][k][n])*(.5 + tau1_kn[k][n]/2)

                        row[_q4(Cb, i, j, k, n+1, Ni, Nj, Nk, Nn+1)] = 1
                        row[_q4(Cb, i, j, k, n, Ni, Nj, Nk, Nn+1)] = -fac1*tau1_kn[k][n]
                        row[_q3(Cx, i, k, n, Ni, Nk, Nn)] = -fac1*(np.kron(j, 2) - np.kron(j, 1))*tau1_kn[k][n]
                        row[_q4(Cbp, i, j, k, n, Ni, Nj, Nk, Nn)] = -fac1
                        row[_q4(Cbm, i, j, k, n, Ni, Nj, Nk, Nn)] = fac1
                        row[_q4(Cw, i, j, k, n, Ni, Nj, Nk, Nn)] = fac1
                        row[_q3(Cd, i, k, n, Ni, Nk, Nn)] = -fac1*np.kron(j, 0)
  
                        if Ni == 2 and i == i_s and n == n_d - 1:
                            # fac2 = self.phi_j[j]*(np.kron(n, n_d - 1))*np.kron(i, i_s)
                            fac2 = self.phi_j[j]
                            rhs += (fac2*self.kappa_ijkn[i_d][j][k][n])*(.5 + tau1_kn[k][n]/2)
                            row[_q4(Cb, i_d, j, k, n, Ni, Nj, Nk, Nn+1)] = -fac2*tau1_kn[k][n]
                            row[_q3(Cx, i_d, k, n, Ni, Nk, Nn)] = -fac2*(np.kron(j, 2) - np.kron(j, 1))*tau1_kn[k][n]
                            row[_q4(Cbp, i_d, j, k, n, Ni, Nj, Nk, Nn)] = -fac2
                            row[_q4(Cbm, i_d, j, k, n, Ni, Nj, Nk, Nn)] = fac2
                            row[_q4(Cw, i_d, j, k, n, Ni, Nj, Nk, Nn)] = fac2
                            row[_q3(Cd, i_d, k, n, Ni, Nk, Nn)] = -fac2*np.kron(j, 0)
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
                        row[_q4(Cb, i, j, k, n, Ni, Nj, Nk, Nn+1)] = -1
                        row[_q4(Cbm, i, j, k, n, Ni, Nj, Nk, Nn)] = 1
                        Ae.append(row)
                        vvec.append(rhs)

        # Net income equalities 1/2.
        for n in range(Nn):
            row = np.zeros(self.nvars)
            row[_q1(Cg, n, Nn)] = 1
            for t in range(Nt):
                row[_q2(Cf, t, n, Nt, Nn)] = self.DeltaBar_tn[t][n]*self.theta_tn[t][n]
            rhs = 0
            for i in range(Ni):
                rhs += (self.omega_in[i][n] + self.zetaBar_in[i][n] 
                        + self.pi_in[i][n] + self.Lambda_in[i][n]
                        - 0.5*self.psi*self.mu*self.kappa_ijkn[i][0][0][n])
                row[_q4(Cb, i, 0, 0, n, Ni, Nj, Nk, Nn+1)] = self.mu*self.psi
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
            row[_q1(Cg, n, Nn)] = -tau1_kn[3][n]*self.xi_n[n]
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
                    row[_q4(Cb, i, 0, k, n, Ni, Nj, Nk, Nn+1)] = (1 - np.kron(k, 0))*self.tau_kn[k][n]
            Ae.append(row)
            vvec.append(rhs)

        # Set initial balances.
        for i in range(Ni):
            for j in range(Nj):
                for k in range(Nk):
                    row = np.zeros(self.nvars)
                    row[_q4(Cb, i, j, k, 0, Ni, Nj, Nk, Nn+1)] = 1
                    rhs = self.beta_ij[i][j]*self.alpha_ijkn[i][j][k][0]
                    Ae.append(row)
                    vvec.append(rhs)

        # Set asset allocation.
        for k in range(Nk):
            if self.ARCoord == 'accounts':
                for n in range(1, Nn+1):
                    for i in range(Ni):
                        for j in range(Nj):
                            row2 = np.zeros(self.nvars)
                            rhs2 = 0
                            for k2 in range(Nk):
                                row2[_q4(Cb, i, j, k2, n, Ni, Nj, Nk, Nn+1)] = np.kron(k, k2) - self.alpha_ijkn[i][j][k][n]
                            Ae.append(row2)
                            vvec.append(rhs2)

            elif self.ARCoord == 'individual':
                for n in range(1, Nn+1):
                    for i in range(Ni):
                        row2 = np.zeros(self.nvars)
                        rhs2 = 0
                        for j in range(Nj):
                            for k2 in range(Nk):
                                row2[_q4(Cb, i, j, k2, n, Ni, Nj, Nk, Nn+1)] = np.kron(k, k2) - self.alpha_ijkn[i][j][k][n]
                        Ae.append(row2)
                        vvec.append(rhs2)

            elif self.ARCoord == 'spouses':
                for n in range(1, Nn+1):
                    row2 = np.zeros(self.nvars)
                    rhs2 = 0
                    for i in range(Ni):
                        for j in range(Nj):
                            for k2 in range(Nk):
                                row2[_q4(Cb, i, j, k2, n, Ni, Nj, Nk, Nn+1)] = np.kron(k, k2) - self.alpha_ijkn[i][j][k][n]
                    Ae.append(row2)
                    vvec.append(rhs2)

        u.vprint('There are', len(vvec),
            'equality constraints and', len(uvec), 'inequality constraints.')

        self.A_ub = np.array(Au)
        self.b_ub = np.array(uvec)
        self.A_eq = np.array(Ae)
        self.b_eq = np.array(vvec)

        return

    def solve(self, objective='maxIncome', options={}):
        '''
        Refer to companion document for explanations.
        '''
        knownOptions = ['maxRothConversion']
        for opt in options:
            if opt not in knownOptions:
                u.xprint('Uknown option', opt)

        self._adjustParameters()
        self._buildOffsetMap()
        self._buildConstraints(objective, options)

        # Define shortcuts.
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

        c = np.zeros(self.nvars)
        c[_q1(Cg, 0, Nn)] = -1
        # Minimize tax brackets.
        for t in range(Nt):
            for n in range(Nn):
                c[_q2(Cf, t, n, Nt, Nn)] = 2**t

        # Minimize rebalancing variables.
        for i in range(Ni):
            for j in range(Nj):
                for k in range(Nk):
                    for n in range(Nn):
                        c[_q4(Cbp, i, j, k, n, Ni, Nj, Nk, Nn)] = 1
                        c[_q4(Cbm, i, j, k, n, Ni, Nj, Nk, Nn)] = 1

        lpOptions = {'disp':True, 'maxiter':100000}
        solution = optimize.linprog(c, A_ub=self.A_ub, b_ub=self.b_ub, A_eq=self.A_eq, b_eq=self.b_eq,
                                     method='highs-ipm', options=lpOptions)
        if solution.success == True:
            u.vprint(solution.message)
        else:
            u.xprint('WARNING: Optimization failed:', solution.message, solution.success)
                
        # Allocate, slice in, and reshape variables.
        self.b_ijkn = np.array(solution.x[Cb:Cbp])
        self.b_ijkn = self.b_ijkn.reshape((Ni, Nj, Nk, Nn + 1))

        self.bp_ijkn = np.array(solution.x[Cbp:Cbm])
        self.bp_ijkn = self.bp_ijkn.reshape((Ni, Nj, Nk, Nn))

        self.bm_ijkn = np.array(solution.x[Cbm:Cd])
        self.bm_ijkn = self.bm_ijkn.reshape((Ni, Nj, Nk, Nn))

        self.d_ikn = np.array(solution.x[Cd:Cf])
        self.d_ikn = self.d_ikn.reshape((Ni, Nk, Nn))

        self.f_tn = np.array(solution.x[Cf:Cg])
        self.f_tn = self.f_tn.reshape((Nt, Nn))

        self.g_n = np.array(solution.x[Cg:Cw])
        self.g_n = self.g_n.reshape((Nn))

        self.w_ijkn = np.array(solution.x[Cw:Cx])
        self.w_ijkn = self.w_ijkn.reshape((Ni, Nj, Nk, Nn))

        self.x_ikn = np.array(solution.x[Cx:])
        self.x_ikn = self.x_ikn.reshape((Ni, Nk, Nn))

        print('b:\n', self.b_ijkn)
        print('b+:\n', self.bp_ijkn)
        print('b-:\n', self.bm_ijkn)
        print('d:\n', self.d_ikn)
        print('f:\n', self.f_tn)
        print('g:\n', self.g_n)
        print('w:\n', self.w_ijkn)
        print('x:\n', self.x_ikn)

        return

    def estate(self):
        '''
        Return final account balances.
        '''
        _estate = np.zeros((self.N_j))
        for i in range(self.N_i):
            for j in range(self.N_j):
                for k in range(self.N_k):
                    _estate[j] += self.b_ijkn[i][j][k][self.N_n]

        _estate[1] *= (1 - self.nu)
        u.vprint('Estate of', u.d(sum(_estate)))

        return _estate

    def showRates(self, tag=''):
        '''
        Plot rate values used over the time horizon.

        A tag string can be set to add information to the title of the plot.
        '''
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 4))
        plt.grid(visible='both')
        title = self._name + '\nReturn & Inflation Rates (' + str(self.rateMethod)
        if self.rateMethod in ['historical', 'stochastic', 'average']:
            title += ' ' + str(self.rateFrm) + '-' + str(self.rateTo)
        elif self.rateMethod == 'fixed':
            title += str(self.rateMethod)
        title += ')'

        if tag != '':
            title += ' - ' + tag

        rateName = [
            'S&P500 including dividends',
            'Baa Corporate bonds',
            '10-y Treasury notes',
            'Inflation',
        ]
        ltype = ['-', '-.', ':', '--']
        for k in range(self.N_k):
            data = 100 * self.tau_kn[k]
            label = rateName[k] + ' <' + '{:.2f}'.format(np.mean(data)) + '>'
            ax.plot(self.year_n, data, label=label, ls=ltype[k % self.N_k])

        ax.legend(loc='upper left', reverse=False, fontsize=8, framealpha=0.7)
        # ax.legend(loc='upper left')
        ax.set_title(title)
        ax.set_xlabel('year')
        ax.set_ylabel('%')

        # plt.show()
        # return fig, ax
        return

    def showProfile(self, tag=''):
        '''
        Plot income profile over time.

        A tag string can be set to add information to the title of the plot.
        '''
        title = self._name + '\nIncome Profile'
        if tag != '':
            title += ' - ' + tag

        # style = {'net': '-', 'target': ':'}
        style = {'profile': '-'}
        series = {'profile': self.xi_n}
        self._lineIncomePlot(series, style, title, yformat='xi')

        return

    def showNetIncome(self, tag=''):
        '''
        Plot net income and target over time.

        A tag string can be set to add information to the title of the plot.
        '''
        title = self._name + '\nNet Income vs. Target'
        if tag != '':
            title += ' - ' + tag

        # style = {'net': '-', 'target': ':'}
        style = {'net': '-'}
        series = {'net': self.g_n}
        self._lineIncomePlot(series, style, title)

        return

    def _lineIncomePlot(self, series, style, title, yformat='k$'):
        '''
        Core line plotter function.
        '''
        import matplotlib.pyplot as plt
        import matplotlib.ticker as tk

        fig, ax = plt.subplots(figsize=(6, 4))
        plt.grid(visible='both')

        for name in series:
            ax.plot(self.year_n, series[name], label=name, ls=style[name])

        ax.legend(loc='upper left', reverse=True, fontsize=8, framealpha=0.7)
        # ax.legend(loc='upper left')
        ax.set_title(title)
        ax.set_xlabel('year')
        ax.set_ylabel(yformat)
        if yformat == 'k$':
            ax.get_yaxis().set_major_formatter(
                tk.FuncFormatter(lambda x, p: format(int(x / 1000), ','))
            )

        # plt.show()
        return fig, ax
