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
import tax2024 as tx
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
    Return time series of cumulative inflation multiplier
    at year n with respect to the current year.
    '''
    gamma = np.ones(N_n)

    for n in range(1, N_n):
        gamma[n] = gamma[n - 1] * (1 + tau[3, n - 1])

    return gamma


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
        neutralSum = N_n
        if (n_d < N_n):
            neutralSum -= (1-frac)*(N_n - n_d) # Account for spousal reduction.
        xi = xi * (neutralSum / xi.sum())
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
        self.year_n = np.linspace(thisyear, thisyear+self.N_n-1, self.N_n, dtype=int)
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
        self.myRothX_in = np.zeros((self.N_i, self.N_n))
        self.kappa_ijn = np.zeros((self.N_i, self.N_j, self.N_n))
        self.kappa_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))

        u.vprint(
            'Preparing scenario of %d years for %d individual%s.'
            % (self.N_n - 1, self.N_i, ['', 's'][self.N_i - 1])
        )
        for i in range(self.N_i):
            u.vprint('%s: life horizon from %d -> %d.'%(self.inames[i], thisyear, thisyear+self.horizons[i]-1))

        # Prepare income tax time series.
        self.rho_in = tx.rho_in(self.yobs, self.N_n)
        self.sigma_n, self.theta_tn, self.Delta_tn = tx.taxParams(
            self.yobs, self.i_d, self.n_d, self.N_n
        )

        self.adjustedParameters = False
        self._buildOffsetMap()
        self.timeListsFileName = None

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

    def setPension(self, amounts, ages, units='k'):
        '''
        Set value of pension for each individual and commencement age.
        Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
        '''
        assert len(amounts) == self.N_i, 'Amounts must have %d entries.'%self.N_i
        assert len(ages) == self.N_i, 'Ages must have %d entries.'%self.N_i

        fac = u.getUnits(units)
        u.rescale(amounts, fac)

        u.vprint('Setting pension of',
                 [u.d(amounts[i]) for i in range(self.N_i)], 'at age(s)', ages)

        thisyear = date.today().year
        # Use zero array freshly initialized.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            ns = max(0, self.yobs[i] + ages[i] - thisyear)
            nd = self.horizons[i]
            self.pi_in[i, ns:nd] = amounts[i]

        return

    def setSocialSecurity(self, amounts, ages, units='k'):
        '''
        Set value of social security for each individual and commencement age.
        Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
        '''
        assert len(amounts) == self.N_i, 'Amounts must have %d entries.'%self.N_i
        assert len(ages) == self.N_i, 'Ages must have %d entries.'%self.N_i

        fac = u.getUnits(units)
        u.rescale(amounts, fac)

        u.vprint('Setting social security benefits of', 
                 [u.d(amounts[i]) for i in range(self.N_i)], 'at age(s)', ages)

        self.adjustedParameters = False
        thisyear = date.today().year
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            ns = max(0, self.yobs[i] + ages[i] - thisyear)
            nd = self.horizons[i]
            self.zeta_in[i, ns:nd] = amounts[i]

        if self.N_i == 2:
            # Approximate calculation for spousal benefit (only valid at FRA).
            self.zeta_in[self.i_s, self.n_d:] = max(amounts[self.i_s], amounts[self.i_d]/2)

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

        self.xi_n = _xi_n(profile, fraction, self.n_d, self.N_n)
        self.spendingProfile = profile

        return

    def setRates(self, method, frm=None, values=None):
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
        if frm == None:
            to = None
        else:
            to = frm + self.N_n - 1     # 'to' is inclusive: subtract 1

        dr = rates.rates()
        dr.setMethod(method, frm, to, values)
        self.rateMethod = method
        self.rateFrm = frm
        self.rateTo = to
        self.rateValues = values
        self.tau_kn = dr.genSeries(self.N_n).transpose()
        u.vprint('Generating rate series of', len(self.tau_kn[0]),
                 'years using', method, 'method.')

        # Once rates are selected, (re)build cumulative inflation multipliers.
        self.gamma_n = gamma_n(self.tau_kn, self.N_n)
        self.adjustParameters = True

        return

    def _adjustParameters(self):
        '''
        Adjust parameters that follow inflation or allocations.
        '''
        if self.adjustedParameters == False:
            u.vprint('Adjusting parameters for inflation.')
            self.DeltaBar_tn = self.Delta_tn * self.gamma_n
            self.zetaBar_in = self.zeta_in * self.gamma_n
            self.sigmaBar_n = self.sigma_n * self.gamma_n
            self.xiBar_n = self.xi_n * self.gamma_n

            for k in range(self.N_k):
                self.kappa_ijkn[:, :, k, :] = self.kappa_ijn[:, :, :]*self.alpha_ijkn[:, :, k, :self.N_n]

            self.adjustedParameters = True

        return

    def setAccountBalances(self, *, taxable, taxDeferred, taxFree, units='k'):
        '''
        Three lists containing the balance of all assets in each category for
        each spouse.  For single individuals, these lists will contain only
        one entry. Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
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

        u.vprint('Taxable balances:', [u.d(taxable[i]) for i in range(self.N_i)])
        u.vprint('Tax-deferred balances:', [u.d(taxDeferred[i]) for i in range(self.N_i)])
        u.vprint('Tax-free balances:', [u.d(taxFree[i]) for i in range(self.N_i)])

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
        self.alpha_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n))
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
                        start = alpha[j][i, 0, k]
                        end = alpha[j][i, 1, k]
                        dat = self._interpolator(start, end, Nn)
                        self.alpha_ijkn[i, j, k, :] = dat[:]

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
                    dat = self._interpolator(start, end, Nn)
                    for j in range(self.N_j):
                        self.alpha_ijkn[i, j, k, :] = dat[:]

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
                dat = self._interpolator(start, end, Nn)
                for i in range(self.N_i):
                    for j in range(self.N_j):
                        self.alpha_ijkn[i, j, k, :] = dat[:]

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
        dat = np.linspace(a, b, numPoints)

        return dat

    def _tanhInterp(self, a, b, numPoints):
        '''
        Utility function to interpolate allocations using a hyperbolic
        tangent interpolation. "c" is the year where the inflection point
        is happening, and "w" is the width of the transition.
        '''
        c = self.interpCenter
        w = self.interpWidth
        t = np.linspace(0, numPoints, numPoints)
        # Solve 2x2 system to match end points exactly.
        th0 = np.tanh((t[0]-c)/w)
        thN = np.tanh((t[numPoints-1]-c)/w)
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
            self.omega_in[i, :h] = self.timeLists[i]['anticipated wages'][:h]
            self.Lambda_in[i, :h] = self.timeLists[i]['big ticket items'][:h]
            self.myRothX_in[i, :h] = self.timeLists[i]['Roth X'][:h]
            self.kappa_ijn[i, 0, :h] = self.timeLists[i]['ctrb taxable'][:h]
            self.kappa_ijn[i, 1, :h] = self.timeLists[i]['ctrb 401k'][:h]
            self.kappa_ijn[i, 1, :h] += self.timeLists[i]['ctrb IRA'][:h]
            self.kappa_ijn[i, 2, :h] = self.timeLists[i]['ctrb Roth 401k'][:h]
            self.kappa_ijn[i, 2, :h] += self.timeLists[i]['ctrb Roth IRA'][:h]

        return

    def _buildOffsetMap(self):
        '''
        Refer to companion document for explanations.
        '''
        # Stack variables in block vector.
        C = {}
        C['b'] = 0
        C['d'] = _qC(C['b'], self.N_i, self.N_j, self.N_n+1)
        C['f'] = _qC(C['d'], self.N_i, self.N_n)
        C['g'] = _qC(C['f'], self.N_t, self.N_n)
        C['w'] = _qC(C['g'], self.N_n)
        C['x'] = _qC(C['w'], self.N_i, self.N_j, self.N_n)
        self.nvars = _qC(C['x'], self.N_i, self.N_n)

        self.C = C
        u.vprint('Problem has', len(C),
            'distinct vectors forming', self.nvars, 'decision variables.')

        return

    def _buildConstraints(self, objective, options):
        '''
        Refer to companion document for notation and detailed explanations.
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
        Cd = self.C['d']
        Cf = self.C['f']
        Cg = self.C['g']
        Cw = self.C['w']
        Cx = self.C['x']
        tau1_kn = 1 + self.tau_kn
        Tau1_ijn = np.zeros((Ni, Nj, Nn))
        Tauh_ijn = np.zeros((Ni, Nj, Nn))
        for i in range(Ni):
            for j in range(Nj):
                for n in range(Nn):
                    Tau1_ijn[i, j, n] = np.sum(self.alpha_ijkn[i, j, :, n] * tau1_kn[:, n], axis=0)
                    Tauh_ijn[i, j, n] = np.sum(self.alpha_ijkn[i, j, :, n] * (1 + self.tau_kn[:, n]/2), axis=0)

        if 'units' in options:
            units = u.getUnits(options['units'])
        else:
            units = 1000

        ###################################################################
        # Inequality constraint matrix and vector.
        Au = []
        uvec = []

        # RMDs inequalities.
        for i in range(Ni):
            for n in range(Nn):
                row = np.zeros(self.nvars)
                rhs = 0
                row[_q3(Cw, i, 1, n, Ni, Nj, Nn)] = -1
                row[_q3(Cb, i, 1, n, Ni, Nj, Nn+1)] = self.rho_in[i, n]
                Au.append(row)
                uvec.append(rhs)

        # Income tax bracket bounds inequalities.
        for t in range(Nt):
            for n in range(Nn):
                row = np.zeros(self.nvars)
                rhs = self.DeltaBar_tn[t, n]
                row[_q2(Cf, t, n, Nt, Nn)] = 1
                Au.append(row)
                uvec.append(rhs)

        # Roth conversions inequalities. Limit amount.
        if 'maxRothConversion' in options:
            rhsopt = options['maxRothConversion']*units
            u.vprint('Limiting Roth conversions to:', u.d(rhsopt))
            for i in range(Ni):
                for n in range(Nn):
                    row1 = np.zeros(self.nvars)
                    row1[_q2(Cx, i, n, Ni, Nn)] = 1
                    rhs1 = rhsopt
                    Au.append(row1)
                    uvec.append(rhs1)

        ###################################################################
        # Equality constraint matrix and vector.
        Ae = []
        vvec = []

        if objective == 'maxIncome':
            if 'netIncome' in options:
                u.vprint('Ignoring netIncome option.')
            # Deposits should be set to zero in that case.
            for i in range(Ni):
                for n in range(Nn):
                    row = np.zeros(self.nvars)
                    rhs = 0
                    row[_q2(Cd, i, n, Ni, Nn)] = 1
                    Ae.append(row)
                    vvec.append(rhs)
            # Impose requested constraint on estate, if any.
            if 'estate' in options:
                estate = np.array(options['estate'], dtype=float)
                assert len(estate) == Ni, 'Estate values must have %d lists.'%Ni
                u.rescale(estate, units)
            else:
                # If not specified, default to $1 per individual.
                estate = np.array([1. for i in Ni])

            u.vprint('Adding estate constraint of:', [u.d(estate[i]) for i in range(Ni)])
            for i in range(Ni):
                assert isinstance(estate[i], (int, float)) == True, 'Estate constraint not a number.'
                rhs = estate[i]
                row = np.zeros(self.nvars)
                row[_q3(Cb, i, 0, Nn, Ni, Nj, Nn+1)] = 1
                row[_q3(Cb, i, 1, Nn, Ni, Nj, Nn+1)] = (1 - self.nu)
                row[_q3(Cb, i, 2, Nn, Ni, Nj, Nn+1)] = 1
                Ae.append(row)
                vvec.append(rhs)

        elif objective == 'maxBequest': 
            if 'estate' in options:
                u.vprint('Ignoring estate option.')
            rhs = options['netIncome']*units
            u.vprint('Maximizing bequest with net income of:', u.d(rhs))
            row = np.zeros(self.nvars)
            row[_q1(Cg, 0)] = 1
            Ae.append(row)
            vvec.append(rhs)
        else:
            u.xprint('Unknown objective function:', objective)

        # Set initial balances.
        for i in range(Ni):
            for j in range(Nj):
                row = np.zeros(self.nvars)
                row[_q3(Cb, i, j, 0, Ni, Nj, Nn+1)] = 1
                rhs = self.beta_ij[i, j]
                Ae.append(row)
                vvec.append(rhs)

        # Account balances carried from year to year.
        # Considering spousal asset transfer.
        # Using hybrid approach with 'if' statements and Kronecker deltas.
        for i in range(Ni):
            for j in range(Nj):
                for n in range(Nn):
                    row = np.zeros(self.nvars)
                    fac1 = (1 - u.krond(n, n_d - 1)*u.krond(i, i_d))
                    rhs = fac1*self.kappa_ijn[i, j, n] * Tauh_ijn[i, j, n]

                    row[_q3(Cb, i, j, n+1, Ni, Nj, Nn+1)] = 1
                    row[_q3(Cb, i, j, n, Ni, Nj, Nn+1)] = -fac1*Tau1_ijn[i, j, n]
                    row[_q2(Cx, i, n, Ni, Nn)] = -fac1*(u.krond(j, 2) - u.krond(j, 1))*Tau1_ijn[i, j, n]
                    row[_q3(Cw, i, j, n, Ni, Nj, Nn)] = fac1
                    row[_q2(Cd, i, n, Ni, Nn)] = -fac1*u.krond(j, 0)
  
                    if Ni == 2 and i == i_s and n == n_d - 1:
                        fac2 = self.phi_j[j]
                        rhs += fac2*self.kappa_ijn[i_d, j, n] * Tauh_ijn[i, j, n]
                        row[_q3(Cb, i_d, j, n, Ni, Nj, Nn+1)] = -fac2*Tau1_ijn[i, j, n]
                        row[_q2(Cx, i_d, i, n, Ni, Nn)] = -fac2*(u.krond(j, 2) - u.krond(j, 1))*Tau1_ijn[i, j, n]
                        row[_q3(Cw, i_d, j, n, Ni, Nj, Nn)] = fac2
                        row[_q2(Cd, i_d, n, Ni, Nn)] = -fac2*u.krond(j, 0)
                    Ae.append(row)
                    vvec.append(rhs)

        # Net income equalities 1/2.
        for n in range(Nn):
            rhs = 0
            row = np.zeros(self.nvars)
            row[_q1(Cg, n, Nn)] = 1
            for i in range(Ni):
                rhs += (self.omega_in[i, n] + self.zetaBar_in[i, n] 
                        + self.pi_in[i, n] + self.Lambda_in[i, n]
                        - 0.5*self.psi*self.mu*self.kappa_ijkn[i, 0, 0, n])
                row[_q3(Cb, i, 0, n, Ni, Nj, Nn+1)] = self.mu*self.psi*self.alpha_ijkn[i, 0, 0, n]
                fac = self.psi*max(0, self.tau_kn[0, n])/(1 + max(0, self.tau_kn[0, n]))
                row[_q3(Cw, i, 0, n, Ni, Nj, Nn)] = fac*self.alpha_ijkn[i, 0, 0, n]
                row[_q2(Cd, i, n, Ni, Nn)] = 1
                for j in range(Nj):
                    row[_q3(Cw, i, j, n, Ni, Nj, Nn)] += -1
            for t in range(Nt):
                row[_q2(Cf, t, n, Nt, Nn)] = self.theta_tn[t, n]
            Ae.append(row)
            vvec.append(rhs)

        # Impose income profile.
        for n in range(1, Nn):
            row = np.zeros(self.nvars)
            rhs = 0
            row[_q1(Cg, 0, Nn)] = -self.xiBar_n[n]
            row[_q1(Cg, n, Nn)] = self.xi_n[0]
            Ae.append(row)
            vvec.append(rhs)

        # Taxable ordinary income.
        for n in range(Nn):
            row = np.zeros(self.nvars)
            rhs = -self.sigmaBar_n[n]
            for i in range(Ni):
                rhs += (self.omega_in[i, n] + 0.85*self.zetaBar_in[i, n] + self.pi_in[i, n])
                row[_q2(Cx, i, n, Ni, Nn)] = -1
                row[_q3(Cw, i, 1, n, Ni, Nj, Nn)] = -1
                for k in range(1, Nk):
                    fak = self.tau_kn[k, n]*self.alpha_ijkn[i, 0, k, n]
                    rhs += 0.5*fak*self.kappa_ijn[i, 0, n]
                    row[_q3(Cb, i, 0, n, Ni, Nj, Nn+1)] += -fak
            for t in range(Nt):
                row[_q2(Cf, t, n, Nt, Nn)] = 1
            Ae.append(row)
            vvec.append(rhs)

        u.vprint('There are', len(vvec),
            'equality constraints and', len(uvec), 'inequality constraints.')

        self.A_ub = np.array(Au)
        self.b_ub = np.array(uvec)
        self.A_eq = np.array(Ae)
        self.b_eq = np.array(vvec)
        
        # Now build objective vector.
        c = np.zeros(self.nvars)
        if objective == 'maxIncome':
            c[_q1(Cg, 0, Nn)] = -1
        elif objective == 'maxBequest':
            for i in range(Ni):
                c[_q3(Cb, i, 0, Nn, Ni, Nj, Nn+1)] = -1
                c[_q3(Cb, i, 1, Nn, Ni, Nj, Nn+1)] = -(1 - self.nu)
                c[_q3(Cb, i, 2, Nn, Ni, Nj, Nn+1)] = -1

        return c

    def solve(self, objective, options={}):
        '''
        Refer to companion document for explanations.
        Units are in $k, unless specified otherwise.
        '''
        knownOptions = ['units', 'maxRothConversion', 'netIncome', 'estate']
        for opt in options:
            if opt not in knownOptions:
                u.xprint('Option', opt, 'not one of', knownOptions)
        knownObjectives = ['maxBequest', 'maxIncome']
        if objective not in knownObjectives: 
            u.xprint('Objective', objective, 'not one of', knownObjectives)
        if objective == 'maxBequest' and 'netIncome' not in options:
            u.xprint('Objective', objective, 'needs netIncome option.')

        self._adjustParameters()
        c = self._buildConstraints(objective, options)

        lpOptions = {'disp':True,
                     'ipm_optimality_tolerance':1e-12,
                     'primal_feasibility_tolerance':1e-10,
                     'dual_feasibility_tolerance':1e-10,
                     }
        solution = optimize.linprog(c, A_ub=self.A_ub, b_ub=self.b_ub, A_eq=self.A_eq, b_eq=self.b_eq,
                                     method='highs-ds', options=lpOptions)
        if solution.success == True:
            u.vprint(solution.message)
        else:
            u.xprint('WARNING: Optimization failed:', solution.message, solution.success)
                
        self.aggregateResults(solution.x)

        return

    def aggregateResults(self, x):
        '''
        Process all results from solution vector.
        '''
        # Define shortcuts.
        Ni = self.N_i
        Nj = self.N_j
        Nk = self.N_k
        Nn = self.N_n
        Nt = self.N_t

        Cb = self.C['b']
        Cd = self.C['d']
        Cf = self.C['f']
        Cg = self.C['g']
        Cw = self.C['w']
        Cx = self.C['x']

        # Allocate, slice in, and reshape variables.
        self.b_ijn = np.array(x[Cb:Cd])
        self.b_ijn = self.b_ijn.reshape((Ni, Nj, Nn + 1))
        self.b_ijkn = np.zeros((Ni, Nj, Nk, Nn+1))
        for i in range(Ni):
            for j in range(Ni):
                for k in range(Ni):
                    for n in range(Ni):
                        self.b_ijkn[i, j, k, n] = self.b_ijn[i, j, n]*self.alpha_ijkn[i, j, k, n]

        self.d_in = np.array(x[Cd:Cf])
        self.d_in = self.d_in.reshape((Ni, Nn))

        self.f_tn = np.array(x[Cf:Cg])
        self.f_tn = self.f_tn.reshape((Nt, Nn))

        self.g_n = np.array(x[Cg:Cw])
        self.g_n = self.g_n.reshape((Nn))

        self.w_ijn = np.array(x[Cw:Cx])
        self.w_ijn = self.w_ijn.reshape((Ni, Nj, Nn))

        self.x_in = np.array(x[Cx:])
        self.x_in = self.x_in.reshape((Ni, Nn))

        print('b:\n', self.b_ijn)
        print('d:\n', self.d_in)
        print('f:\n', self.f_tn)
        print('g:\n', self.g_n)
        print('w:\n', self.w_ijn)
        print('x:\n', self.x_in)

        # Make derivative variables.
        sourcetypes = [
            'wages',
            'ssec',
            'pension',
            'dist',
            'rmd',
            'RothX',
            'div',
            'wdrwl taxable',
            'wdrwl tax-free',
        ]

        # Reroute (Roth conversions + tax-free withdrawals) to distributions.
        new_x_in = self.x_in - self.w_ijn[:,2,:]
        new_x_in[new_x_in < 0] = 0
        delta = (self.x_in - new_x_in)
        self.w_ijn[:, 1, :] += delta
        self.w_ijn[:, 2, :] -= delta
        self.x_in = new_x_in

        self.rmd_in = self.rho_in*self.b_ijn[:, 1, :-1]
        self.dist_in = self.w_ijn[:,1,:] - self.rmd_in
        self.dist_in[self.dist_in < 0] = 0

        # Putting it all together in a dictionary.
        sources = {}
        sources['wages'] = self.omega_in
        sources['ssec'] = self.zetaBar_in
        sources['pension'] = self.pi_in
        sources['wdrwl taxable'] = self.w_ijn[:, 0, :]
        sources['rmd'] = self.rmd_in
        sources['dist'] = self.dist_in
        sources['RothX'] = self.x_in
        sources['wdrwl tax-free'] = self.w_ijn[:, 2, :]

        savings = {}
        savings['taxable'] = self.b_ijn[:, 0, :]
        savings['tax-deferred'] = self.b_ijn[:, 1, :]
        savings['tax-free'] = self.b_ijn[:, 2, :]
        
        self.sources_in = sources
        self.savings_in = savings

        return

    def estate(self):
        '''
        Return final account balances.
        '''
        _estate = np.sum(self.b_ijn[:, :, :, self.N_n], axis=(0,2))
        _estate[1] *= (1 - self.nu)
        u.vprint('Estate value of %s in year %s.'%(u.d(sum(_estate)), self.year_n[-1]))

        return

    def totals(self):
        '''
        Print summary of values.
        '''
        estate = np.sum(self.b_ijn[:, :, self.N_n], axis=(0,1))
        estate[1] *= (1 - self.nu)
        totalEstate = np.sum(estate)/self.gamma_n(N_n-1)
        print('Final estate in %d$: %d'%(self.year_n[0], u.d(totalEstate)))

        taxPaid = np.sum(self.f_tn*self.theta_tn)


        return

    def showRates(self, tag=''):
        '''
        Plot rate values used over the time horizon.

        A tag string can be set to add information to the title of the plot.
        '''
        import matplotlib.pyplot as plt
        import matplotlib.ticker as tk

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

        ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
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
        _lineIncomePlot(self.year_n, series, style, title, yformat='xi')

        return

    def showNetIncome(self, tag=''):
        '''
        Plot net income and target over time.

        A tag string can be set to add information to the title of the plot.
        '''
        title = self._name + '\nNet Income'
        if tag != '':
            title += ' - ' + tag

        style = {'net': '-', 'target': ':'}
        series = {'net': self.g_n, 'target': (self.g_n[0]/self.xi_n[0])*self.xiBar_n}
        _lineIncomePlot(self.year_n, series, style, title)

        return

    def showAssetDistribution(self, tag=''):
        '''
        Plot the distribution of each savings account in thousands of dollars
        during the simulation time. This function will generate three
        graphs, one for taxable accounts, one the tax-deferred accounts,
        and one for tax-free accounts.

        A tag string can be set to add information to the title of the plot.
        '''

        y2stack = {}
        jDic = {'taxable': 0, 'tax-deferred': 1, 'tax-free': 2}
        kDic = {'stocks': 0, 'C bonds': 1, 'T notes': 2, 'common': 3}
        for jkey in jDic:
            stackNames = []
            for kkey in kDic:
                name = kkey + ' / ' + jkey
                stackNames.append(name)
                y2stack[name] = np.zeros((self.N_i, self.N_n+1))
                for i in range(self.N_i):
                    y2stack[name][i][:] = self.b_ijkn[i][jDic[jkey]][kDic[kkey]][:]

            title = self._name + '\nAssets Distribution - ' + jkey
            if tag != '':
                title += ' - ' + tag

            _stackPlot(self.year_n, self.inames, title, range(self.N_i),
                       y2stack, stackNames, 'upper left')

        return

    def showAllocations(self, tag=''):
        '''
        Plot desired allocation of savings accounts in percentage
        over simulation time and interpolated by the selected method
        through the interpolateAR() method.

        A tag string can be set to add information to the title of the plot.
        '''
        count = self.N_i
        if self.coordinatedAR == 'both':
            acList = ['coordinated']
            count = 1
        elif self.coordinatedAR == 'individual':
            acList = ['coordinated']
        else:
            acList = ['taxable', 'tax-deferred', 'tax-free']

        assetDic = {'stocks': 0, 'C bonds': 1, 'T notes': 2, 'common': 3}
        for i in range(count):
            y2stack = {}
            for acType in acList:
                stackNames = []
                for key in assetDic:
                    aname = key + ' / ' + acType
                    stackNames.append(aname)
                    y2stack[aname] = np.zeros((count, self.N_n))
                    y2stack[aname][i][:] = self.y2assetRatios[acType].transpose(
                        1, 2, 0
                    )[i][assetDic[key]][:]
                    y2stack[aname] = y2stack[aname].transpose()

                    title = self._name + '\nAssets Allocations (%) - ' + acType
                    if self.coordinatedAR == 'both':
                        title += ' both'
                    else:
                        title += ' ' + self.names[i]

                if tag != '':
                    title += ' - ' + tag

                _stackPlot(self.year_n, self.inames,
                    title, [i], y2stack, stackNames, 'upper left', 'percent'
                )

        return

    def showAccounts(self, tag=''):
        '''
        Plot values of savings accounts over time.

        A tag string can be set to add information to the title of the plot.
        '''
        title = self._name + '\nSavings Balance'
        if tag != '':
            title += ' - ' + tag
        stypes = self.savings_in.keys()
        # Add one year for estate.
        year_n = np.append(self.year_n, [self.year_n[-1]+1])

        _stackPlot(year_n, self.inames, title, range(self.N_i), self.savings_in, stypes, 'upper left')

        return

    def showSources(self, tag=''):
        '''
        Plot income over time.

        A tag string can be set to add information to the title of the plot.
        '''
        title = self._name + '\nRaw Income Sources'
        if tag != '':
            title += ' - ' + tag
        stypes = self.sources_in.keys()
        _stackPlot(self.year_n, self.inames, title, range(self.N_i), self.sources_in, stypes, 'upper left')

        return

    def showFeff(self, tag=''):
        '''
        Plot income tax paid over time.

        A tag string can be set to add information to the title of the plot.
        '''
        title = self._name + '\nEff f '
        if tag != '':
            title += ' - ' + tag

        various = ['-', '--', '-.', ':']
        style = {}
        series = {}
        q = 0
        for t in range(self.N_t):
            key = 'f '+str(t)
            series[key] = self.f_tn[t]/self.DeltaBar_tn[t]
            style[key] = various[q%len(various)]
            q += 1

        fig, ax = _lineIncomePlot(self.year_n, series, style, title, yformat='')

        return

    def showTaxes(self, tag=''):
        '''
        Plot income tax paid over time.

        A tag string can be set to add information to the title of the plot.
        '''
        title = self._name + '\nIncome Tax'
        if tag != '':
            title += ' - ' + tag

        T_tn = self.f_tn * self.theta_tn
        T_n = np.sum(T_tn, axis=0)
        style = {'income taxes': '-'}
        series = {'income taxes': T_n}

        fig, ax = _lineIncomePlot(self.year_n, series, style, title)

        return

    def showGrossIncome(self, tag=''):
        '''
        Plot income tax and taxable income over time horizon.

        A tag string can be set to add information to the title of the plot.
        '''
        import matplotlib.pyplot as plt

        title = self._name + '\nGross Income vs. Tax Brackets'
        if tag != '':
            title += ' - ' + tag

        tmp1 = np.sum(self.omega_in + 0.85*self.zetaBar_in + self.pi_in, axis=0)
        tmp2 = np.sum(self.w_ijn[:, 1, :] + self.x_in, axis=0)
        tmp3 = np.sum(self.b_ijkn[:, 0, 1:, :-1] + 0.5*self.kappa_ijkn[:, 0, 1:, :], axis=0) * self.tau_kn[1:, :]
        tmp3 = np.sum(tmp3, axis=0)
        otherG_n = tmp1 + tmp2 + tmp3 - self.sigmaBar_n
        G_tn = self.f_tn 
        G_n = np.sum(G_tn, axis=0)
        style = {'gross1': '-', 'gross2': ':'}
        series = {'gross1': G_n, 'gross2': otherG_n}

        fig, ax = _lineIncomePlot(self.year_n, series, style, title)

        data = tx.taxBrackets(self.N_i, self.n_d, self.N_n)

        for key in data:
            data_adj = data[key]*self.gamma_n
            ax.plot(self.year_n, data_adj, label=key, ls=':')

        plt.grid(visible='both')
        ax.legend(loc='upper right', reverse=True, fontsize=8, framealpha=0.3)

        return


def _lineIncomePlot(x, series, style, title, yformat='k$'):
    '''
    Core line plotter function.
    '''
    import matplotlib.pyplot as plt
    import matplotlib.ticker as tk

    fig, ax = plt.subplots(figsize=(6, 4))
    plt.grid(visible='both')

    for sname in series:
        ax.plot(x, series[sname], label=sname, ls=style[sname])

    ax.legend(loc='upper left', reverse=True, fontsize=8, framealpha=0.3)
    ax.set_title(title)
    ax.set_xlabel('year')
    ax.set_ylabel(yformat)
    ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
    if yformat == 'k$':
        ax.get_yaxis().set_major_formatter(
            tk.FuncFormatter(lambda x, p: format(int(x / 1000), ','))
        )

    return fig, ax


def _stackPlot(x, inames, title, irange, series, snames, location, ytype='dollars'):
    '''
    Core function for stacked plots.
    '''
    import matplotlib.pyplot as plt
    import matplotlib.ticker as tk

    nonzeroSeries = {}
    for sname in snames:
        for i in irange:
            tmp = series[sname][i]
            if sum(tmp) > 1.:
                nonzeroSeries[sname + ' ' + inames[i]] = tmp

    if len(nonzeroSeries) == 0:
        print('Nothing to plot for', title)
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    plt.grid(visible='both')

    ax.stackplot(x, nonzeroSeries.values(), labels=nonzeroSeries.keys(), alpha=0.6)
    ax.legend(loc=location, reverse=True, fontsize=8, ncol=2, framealpha=0.6)
    ax.set_title(title)
    ax.set_xlabel('year')
    ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
    if ytype == 'dollars':
        ax.set_ylabel('k$')
        ax.get_yaxis().set_major_formatter(
            tk.FuncFormatter(lambda x, p: format(int(x / 1000), ','))
        )
    elif ytype == 'percent':
        ax.set_ylabel('%')
        ax.get_yaxis().set_major_formatter(
            tk.FuncFormatter(lambda x, p: format(int(100 * x), ','))
        )
    else:
        u.xprint('Unknown ytype:', ytype)

        return fig, ax

