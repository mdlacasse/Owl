"""

Owl/plan
--------

A retirement planner using linear programming optimization.

See companion PDF document for an explanation of the underlying
mathematical model and a description of all variables and parameters.

Copyright (C) 2024 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.
"""

###########################################################################
import numpy as np
import pandas as pd
from datetime import date, datetime
from functools import wraps
import time

from owlplanner import utils as u
from owlplanner import tax2024 as tx
from owlplanner import abcapi as abc
from owlplanner import rates
from owlplanner import config
from owlplanner import timelists


def setVerbose(state=True):
    """
    Control verbosity of calculations. True or False for now.
    Return previous state of verbosity.
    -``state``: Boolean selecting verbosity level.
    """
    return u._setVerbose(state)


def _genGamma_n(tau):
    """
    Utility function to generate a cumulative inflation multiplier
    at the beginning of a year.
    Return time series of cumulative inflation multiplier
    at year n with respect to the current time reference.
    -``tau``: Time series containing annual rates, the last of which is inflation.
    If there are Nn years in time series, the series will generate Nn + 1,
    as the last year will compound for an extra data point at the beginning of the
    following year.
    """
    N = len(tau[-1]) + 1
    gamma = np.ones(N)

    for n in range(1, N):
        gamma[n] = gamma[n - 1] * (1 + tau[-1, n - 1])

    return gamma


def _genXi_n(profile, fraction, n_d, N_n, a=15, b=12):
    """
    Utility function to generate spending profile.
    Return time series of spending profile.
    Value is reduced to fraction starting in year n_d,
    after the passing of shortest-lived spouse.
    Series is unadjusted for inflation.
    """
    xi = np.ones(N_n)
    if profile == 'flat':
        if n_d < N_n:
            xi[n_d:] *= fraction
    elif profile == 'smile':
        x = np.linspace(0, N_n - 1, N_n)
        a /= 100
        b /= 100
        # Use a cosine +/- 15% combined with a gentle +12% linear increase.
        xi = xi + a * np.cos((2 * np.pi / (N_n - 1)) * x) + (b / (N_n - 1)) * x
        # Normalize to be sum-neutral with respect to a flat profile.
        neutralSum = N_n
        # Reduce income needs after passing of one spouse.
        if n_d < N_n:
            neutralSum -= (1 - fraction) * (N_n - n_d)  # Account for flat spousal reduction.
            xi[n_d:] *= fraction
        xi *= neutralSum / xi.sum()
    else:
        raise ValueError('Unknown profile type %s.' % profile)

    return xi


def _qC(C, N1, N2=1, N3=1, N4=1):
    """
    Index range accumulator.
    """
    return C + N1 * N2 * N3 * N4


def _q1(C, l1, N1=None):
    """
    Index mapping function. 1 argument.
    """
    return C + l1


def _q2(C, l1, l2, N1, N2):
    """
    Index mapping function. 2 arguments.
    """
    return C + l1 * N2 + l2


def _q3(C, l1, l2, l3, N1, N2, N3):
    """
    Index mapping function. 3 arguments.
    """
    return C + l1 * N2 * N3 + l2 * N3 + l3


def _q4(C, l1, l2, l3, l4, N1, N2, N3, N4):
    """
    Index mapping function. 4 arguments.
    """
    return C + l1 * N2 * N3 * N4 + l2 * N3 * N4 + l3 * N4 + l4


def clone(plan, name=None):
    """
    Return an almost identical copy of plan: only the name of the plan
    has been modified and appended the string '(copy)',
    unless a new name is provided as an argument.
    """
    import copy

    newplan = copy.deepcopy(plan)
    if name is None:
        newplan.rename(plan._name + ' (copy)')
    else:
        newplan.rename(name)

    return newplan


############################################################################


def _checkCaseStatus(func):
    """
    Decorator to check if problem was solved successfully and
    prevent method from running if not.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.caseStatus != 'solved':
            u.vprint('Preventing to run method %s() while case is %s.' % (func.__name__, self.caseStatus))
            return None
        return func(self, *args, **kwargs)

    return wrapper


def _checkConfiguration(func):
    """
    Decorator to check if problem was configured successfully and
    prevent method from running if not.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.xi_n is None:
            msg = 'You must define a spending profile before calling %s().' % func.__name__
            u.vprint(msg)
            raise RuntimeError(msg)
        if self.alpha_ijkn is None:
            msg = 'You must define an allocation profile before calling %s().' % func.__name__
            u.vprint(msg)
            raise RuntimeError(msg)
        return func(self, *args, **kwargs)

    return wrapper


def _timer(func):
    """
    Decorator to report CPU and Wall time.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        pt0 = time.process_time()
        rt0 = time.time()
        result = func(self, *args, **kwargs)
        pt = time.process_time() - pt0
        rt = time.time() - rt0
        print('CPU time used: %dm%.1fs, Wall time: %dm%.1fs.' % (int(pt / 60), pt % 60, int(rt / 60), rt % 60))
        return result

    return wrapper


class Plan:
    """
    This is the main class of the Owl Project.
    """

    def __init__(self, inames, yobs, expectancy, name, startDate=None):
        """
        Constructor requires three lists: the first
        one contains the name(s) of the individual(s),
        the second one is the year of birth of each individual,
        and the third the life expectancy. Last argument is a name for
        the plan.
        """
        self._name = name

        # 7 tax brackets, 3 types of accounts, 4 classes of assets.
        self.N_t = 7
        self.N_j = 3
        self.N_k = 4
        # 2 binary variables.
        self.N_z = 2

        # Default interpolation parameters for allocation ratios.
        self.interpMethod = 'linear'
        self._interpolator = self._linInterp
        self.interpCenter = 15
        self.interpWidth = 5

        self.defaultPlots = 'nominal'
        self.defaultSolver = 'HiGHS'

        self.N_i = len(yobs)
        assert 0 < self.N_i and self.N_i <= 2, 'Cannot support %d individuals.' % self.N_i
        assert self.N_i == len(expectancy), 'Expectancy must have %d entries.' % self.N_i
        assert self.N_i == len(inames), 'Names for individuals must have %d entries.' % self.N_i

        self.filingStatus = ['single', 'married'][self.N_i - 1]

        self.inames = inames
        self.yobs = yobs
        self.expectancy = expectancy

        # Reference time is starting date in the current year and all passings are assumed at the end.
        thisyear = date.today().year
        self.horizons = [yobs[i] + expectancy[i] - thisyear + 1 for i in range(self.N_i)]
        self.N_n = max(self.horizons)
        self.year_n = np.linspace(thisyear, thisyear + self.N_n - 1, self.N_n, dtype=int)
        # Handle passing of one spouse before the other.
        if self.N_i == 2 and min(self.horizons) != max(self.horizons):
            self.n_d = min(self.horizons)
            self.i_d = self.horizons.index(self.n_d)
            self.i_s = (self.i_d + 1) % 2
        else:
            self.n_d = self.N_n  # Push at upper bound and check for n_d < Nn.
            self.i_d = 0
            self.i_s = -1

        # Default parameters:
        self.psi = 0.15  # Long-term income tax rate on capital gains (decimal)
        self.chi = 0.6  # Survivor fraction
        self.mu = 0.02  # Dividend rate (decimal)
        self.nu = 0.30  # Heirs tax rate (decimal)
        self.eta = (self.N_i - 1) / 2  # Spousal deposit ratio (0 or .5)
        self.phi_j = np.array([1, 1, 1])  # Fractions left to other spouse at death

        # Default to zero pension and social security.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        self.pensionAmounts = np.zeros(self.N_i)
        self.pensionAges = 65 * np.ones(self.N_i, dtype=int)
        self.ssecAmounts = np.zeros(self.N_i)
        self.ssecAges = 67 * np.ones(self.N_i, dtype=int)

        # Parameters from timeLists.
        self.omega_in = np.zeros((self.N_i, self.N_n))
        self.Lambda_in = np.zeros((self.N_i, self.N_n))
        self.myRothX_in = np.zeros((self.N_i, self.N_n))
        self.kappa_ijn = np.zeros((self.N_i, self.N_j, self.N_n))

        # Scenario starts at the beginning of this year and ends at the end of the last year.
        u.vprint('Preparing scenario of %d years for %d individual%s.' % (self.N_n, self.N_i, ['', 's'][self.N_i - 1]))
        for i in range(self.N_i):
            u.vprint('%14s: life horizon from %d -> %d.' % (self.inames[i], thisyear, thisyear + self.horizons[i] - 1))

        # Prepare income tax and RMD time series.
        self.rho_in = tx.rho_in(self.yobs, self.N_n)
        self.sigma_n, self.theta_tn, self.Delta_tn = tx.taxParams(self.yobs, self.i_d, self.n_d, self.N_n)

        # If none was given, default is to begin plan on today's date.
        self._setStartingDate(startDate)

        self._buildOffsetMap()

        # Initialize guardrails to ensure proper configuration.
        self._adjustedParameters = False
        self.timeListsFileName = None
        self.caseStatus = 'unsolved'
        self.rateMethod = None

        # Placeholders to check if properly configured.
        self.xi_n = None
        self.alpha_ijkn = None

        return None

    def _setStartingDate(self, mydate):
        """
        Set the date when the plan starts in the current year.
        This is for reproducibility purposes.
        String format of mydate is 'month/day'.
        """
        import calendar

        thisyear = date.today().year

        if isinstance(mydate, date):
            mydate = mydate.strftime('%Y-%m-%d')
        if mydate is None:
            refdate = date.today()
            self.startDate = refdate.strftime('%Y-%m-%d')
        else:
            mydatelist = mydate.split('-')
            if len(mydatelist) == 2 or len(mydatelist) == 3:
                self.startDate = mydate
                refdate = date(thisyear, int(mydatelist[-2]), int(mydatelist[-1]))
            else:
                raise ValueError('Date must be "MM-DD" or "YYYY-MM-DD".')

        lp = calendar.isleap(thisyear)
        self.yearFracLeft = 1 - (refdate.timetuple().tm_yday - 1) / (365 + lp)

        u.vprint('Setting 1st-year starting date to %s.' % (self.startDate))

        return None

    def _checkValue(self, value):
        """
        Short utility function to parse and check arguments for plotting.
        """
        if value is None:
            return self.defaultPlots

        opts = ['nominal', 'today']
        if value in opts:
            return value

        raise ValueError('Value type must be one of: %r' % opts)

        return None

    def rename(self, name):
        """
        Override name of the plan. Plan name is used
        to distinguish graph outputs and as base name for
        saving configurations and workbooks.
        """
        self._name = name

        return None

    def setSpousalDepositFraction(self, eta):
        """
        Set spousal deposit and withdrawal fraction. Default 0.5.
        Fraction eta is use to split surplus deposits between spouses as
        d_0n = (1 - eta)*s_n,
        and
        d_1n = eta*s_n,
        where s_n is the surplus amount. Here d_0n is the taxable account
        deposit for the first spouse while d_1n is for the second spouse.
        """
        assert 0 <= eta and eta <= 1, 'Fraction must be between 0 and 1.'
        if self.N_i != 2:
            u.vprint('Deposit fraction can only be 0 for single individuals.')
            eta = 0
        else:
            u.vprint('Setting spousal surplus deposit fraction to %.1f.' % eta)
            u.vprint('\t%s: %.1f, %s: %.1f' % (self.inames[0], (1 - eta), self.inames[1], eta))
            self.eta = eta

        return None

    def setDefaultPlots(self, value):
        """
        Set plots between nominal values or today's $.
        """

        self.defaultPlots = self._checkValue(value)

        return None

    def setDividendRate(self, mu):
        """
        Set dividend rate on equities. Rate is in percent. Default 2%.
        """
        assert 0 <= mu and mu <= 100, 'Rate must be between 0 and 100.'
        mu /= 100
        u.vprint('Dividend return rate on equities set to %s.' % u.pc(mu, f=1))
        self.mu = mu
        self.caseStatus = 'modified'

        return None

    def setLongTermCapitalTaxRate(self, psi):
        """
        Set long-term income tax rate. Rate is in percent. Default 15%.
        """
        assert 0 <= psi and psi <= 100, 'Rate must be between 0 and 100.'
        psi /= 100
        u.vprint('Long-term capital gain income tax set to %s.' % u.pc(psi, f=0))
        self.psi = psi
        self.caseStatus = 'modified'

        return None

    def setBeneficiaryFractions(self, phi):
        """
        Set fractions of savings accounts that is left to surviving spouse.
        Default is [1, 1, 1] for taxable, tax-deferred, adn tax-exempt accounts.
        """
        assert len(phi) == self.N_j, 'Fractions must have %d entries.' % self.N_j
        for j in range(self.N_j):
            assert 0 <= phi[j] <= 1, 'Fractions must be between 0 and 1.'

        u.vprint('Spousal beneficiary fractions set to', phi)
        self.phi_j = np.array(phi)
        self.caseStatus = 'modified'

        if np.any(self.phi_j != 1):
            u.vprint('Consider changing spousal deposit fraction for better convergence.')
            u.vprint('\tRecommended: setSpousalDepositFraction(%d)' % self.i_d)

        return None

    def setHeirsTaxRate(self, nu):
        """
        Set the heirs tax rate on the tax-deferred portion of the estate.
        Rate is in percent. Default is 30%.
        """
        assert 0 <= nu and nu <= 100, 'Rate must be between 0 and 100.'
        nu /= 100
        u.vprint('Heirs tax rate on tax-deferred portion of estate set to %s.' % u.pc(nu, f=0))
        self.nu = nu
        self.caseStatus = 'modified'

        return None

    def setPension(self, amounts, ages, units='k'):
        """
        Set value of pension for each individual and commencement age.
        Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
        """
        assert len(amounts) == self.N_i, 'Amounts must have %d entries.' % self.N_i
        assert len(ages) == self.N_i, 'Ages must have %d entries.' % self.N_i

        fac = u.getUnits(units)
        u.rescale(amounts, fac)

        u.vprint('Setting pension of', [u.d(amounts[i]) for i in range(self.N_i)], 'at age(s)', ages)

        thisyear = date.today().year
        # Use zero array freshly initialized.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            if amounts[i] != 0:
                ns = max(0, self.yobs[i] + ages[i] - thisyear)
                nd = self.horizons[i]
                self.pi_in[i, ns:nd] = amounts[i]
                # Only include future part of current year.
                if ns == 0:
                    self.pi_in[i, 0] *= self.yearFracLeft

        self.pensionAmounts = amounts
        self.pensionAges = ages
        self.caseStatus = 'modified'

        return None

    def setSocialSecurity(self, amounts, ages, units='k'):
        """
        Set value of social security for each individual and commencement age.
        Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
        """
        assert len(amounts) == self.N_i, 'Amounts must have %d entries.' % self.N_i
        assert len(ages) == self.N_i, 'Ages must have %d entries.' % self.N_i

        fac = u.getUnits(units)
        u.rescale(amounts, fac)

        u.vprint(
            'Setting social security benefits of',
            [u.d(amounts[i]) for i in range(self.N_i)],
            'at age(s)',
            ages,
        )

        thisyear = date.today().year
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            ns = max(0, self.yobs[i] + ages[i] - thisyear)
            nd = self.horizons[i]
            self.zeta_in[i, ns:nd] = amounts[i]
            # Only include future part of current year.
            if ns == 0:
                self.zeta_in[i, 0] *= self.yearFracLeft

        if self.N_i == 2:
            # Approximate calculation for spousal benefit (only valid at FRA).
            self.zeta_in[self.i_s, self.n_d:] = max(amounts[self.i_s], amounts[self.i_d] / 2)

        self.ssecAmounts = amounts
        self.ssecAges = ages
        self.caseStatus = 'modified'
        self._adjustedParameters = False

        return None

    def setSpendingProfile(self, profile, percent=60):
        """
        Generate time series for spending profile.
        Surviving spouse fraction can be specified
        as a second argument. Default value is 60%.
        """
        self.chi = percent / 100

        u.vprint('Setting', profile, 'spending profile.')
        if self.N_i == 2:
            u.vprint('Securing', u.pc(self.chi, f=0), 'of spending amount for surviving spouse.')

        self.xi_n = _genXi_n(profile, self.chi, self.n_d, self.N_n)
        # Account for time elapsed in the current year.
        self.xi_n[0] *= self.yearFracLeft

        self.spendingProfile = profile
        self.caseStatus = 'modified'

        return None

    def setRates(self, method, frm=None, to=None, values=None, stdev=None, corr=None):
        """
        Generate rates for return and inflation based on the method and
        years selected. Note that last bound is included.

        The following methods are available:
        default, fixed, realistic, conservative, average, stochastic,
        histochastic, and historical.

        - For 'fixed', rate values must be provided.
        - For 'stochastic', means, stdev, and optional correlation matrix must be provided.
        - For 'average', 'histochastic', and 'historical', a starting year
          must be provided, and optionally an ending year.

        Valid year range is from 1928 to last year.
        """
        if frm is not None and to is None:
            to = frm + self.N_n - 1  # 'to' is inclusive.

        dr = rates.Rates()
        self.rateValues, self.rateStdev, self.rateCorr = dr.setMethod(method, frm, to, values, stdev, corr)
        self.rateMethod = method
        self.rateFrm = frm
        self.rateTo = to
        self.tau_kn = dr.genSeries(self.N_n).transpose()
        u.vprint(
            'Generating rate series of',
            len(self.tau_kn[0]),
            'years using',
            method,
            'method.',
        )

        # Account for how late we are now in the first year and reduce rate accordingly.
        self.tau_kn[:, 0] *= self.yearFracLeft

        # Once rates are selected, (re)build cumulative inflation multipliers.
        self.gamma_n = _genGamma_n(self.tau_kn)
        self._adjustedParameters = False
        self.caseStatus = 'modified'

        return None

    def regenRates(self):
        """
        Regenerate the rates using the arguments specified during last setRates() call.
        This method is used to regenerate stochastic time series.
        """
        self.setRates(
            self.rateMethod,
            frm=self.rateFrm,
            to=self.rateTo,
            values=100 * self.rateValues,
            stdev=100 * self.rateStdev,
            corr=self.rateCorr,
        )

        return None

    def value(self, amount, year):
        """
        Return value of amount deflated or inflated at the beginning
        of the year specified.
        If year is in the past, value is made at the beginning of this year.
        If year is in the future, amount is adjusted from a reference time
        aligned with the beginning of the plan to the beginning of the
        year specified.
        """
        thisyear = date.today().year
        if year <= thisyear:
            return rates.historicalValue(amount, year)
        else:
            return self.forwardValue(amount, year)

    def forwardValue(self, amount, year):
        """
        Return the value of amount inflated from beginning of the plan
        to the beginning of the year provided.
        """
        if self.rateMethod is None:
            raise RuntimeError('A rate method needs to be first selected using setRates(...).')

        thisyear = date.today().year
        assert year > thisyear, 'Internal error in forwardValue().'
        span = year - thisyear

        return amount * self.gamma_n[span]

    def setAccountBalances(self, *, taxable, taxDeferred, taxFree, units='k'):
        """
        Three lists containing the balance of all assets in each category for
        each spouse.  For single individuals, these lists will contain only
        one entry. Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
        """
        plurals = ['', 'y', 'ies']
        assert len(taxable) == self.N_i, 'taxable must have %d entr%s.' % (self.N_i, plurals[self.N_i])
        assert len(taxDeferred) == self.N_i, 'taxDeferred must have %d entr%s.' % (self.N_i, plurals[self.N_i])
        assert len(taxFree) == self.N_i, 'taxFree must have %d entr%s.' % (self.N_i, plurals[self.N_i])

        fac = u.getUnits(units)
        u.rescale(taxable, fac)
        u.rescale(taxDeferred, fac)
        u.rescale(taxFree, fac)

        self.b_ji = np.zeros((self.N_j, self.N_i))
        self.b_ji[0][:] = taxable
        self.b_ji[1][:] = taxDeferred
        self.b_ji[2][:] = taxFree
        self.beta_ij = self.b_ji.transpose()
        self.caseStatus = 'modified'

        u.vprint('Taxable balances:', *[u.d(taxable[i]) for i in range(self.N_i)])
        u.vprint('Tax-deferred balances:', *[u.d(taxDeferred[i]) for i in range(self.N_i)])
        u.vprint('Tax-free balances:', *[u.d(taxFree[i]) for i in range(self.N_i)])
        u.vprint('Sum of all savings accounts:', u.d(np.sum(taxable) + np.sum(taxDeferred) + np.sum(taxFree)))
        u.vprint(
            'Post-tax total wealth of approximately',
            u.d(np.sum(taxable) + 0.7 * np.sum(taxDeferred) + np.sum(taxFree)),
        )

        return None

    def setInterpolationMethod(self, method, center=15, width=5):
        """
        Interpolate assets allocation ratios from initial value (today) to
        final value (at the end of horizon).

        Two interpolation methods are supported: linear and s-curve.
        Linear is a straight line between now and the end of the simulation.
        Hyperbolic tangent give a smooth "S" curve centered at point "center"
        with a width "width". Center point defaults to 15 years and width to
        5 years. This means that the transition from initial to final
        will start occuring in 10 years (15-5) and will end in 20 years (15+5).
        """
        if method == 'linear':
            self._interpolator = self._linInterp
        elif method == 's-curve':
            self._interpolator = self._tanhInterp
            self.interpCenter = center
            self.interpWidth = width
        else:
            raise ValueError('Method %s not supported.' % method)

        self.interpMethod = method
        self.caseStatus = 'modified'

        u.vprint('Asset allocation interpolation method set to %s.' % method)

        return None

    def setAllocationRatios(self, allocType, taxable=None, taxDeferred=None, taxFree=None, generic=None):
        """
        Single function for setting all types of asset allocations.
        Allocation types are 'account', 'individual', and 'spouses'.

        For 'account' the three different account types taxable, taxDeferred,
        qand taxFree need to be set to a list. For spouses,
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
        """
        self.boundsAR = {}
        self.alpha_ijkn = np.zeros((self.N_i, self.N_j, self.N_k, self.N_n + 1))
        if allocType == 'account':
            # Make sure we have proper input.
            for item in [taxable, taxDeferred, taxFree]:
                assert len(item) == self.N_i, '%s must one entry per individual.' % (item)
                for i in range(self.N_i):
                    # Initial and final.
                    assert len(item[i]) == 2, '%s[%d] must have 2 lists (initial and final).' % (
                        item,
                        i,
                    )
                    for z in range(2):
                        assert len(item[i][z]) == self.N_k, '%s[%d][%d] must have %d entries.' % (
                            item,
                            i,
                            z,
                            self.N_k,
                        )
                        assert abs(sum(item[i][z]) - 100) < 0.01, 'Sum of percentages must add to 100.'

            for i in range(self.N_i):
                u.vprint(
                    self.inames[i],
                    ': Setting gliding allocation ratios (%) to',
                    allocType,
                )
                u.vprint('      taxable:', taxable[i][0], '->', taxable[i][1])
                u.vprint('  taxDeferred:', taxDeferred[i][0], '->', taxDeferred[i][1])
                u.vprint('      taxFree:', taxFree[i][0], '->', taxFree[i][1])

            # Order in alpha is j, i, 0/1, k.
            alpha = {}
            alpha[0] = np.array(taxable)
            alpha[1] = np.array(taxDeferred)
            alpha[2] = np.array(taxFree)
            for i in range(self.N_i):
                Nin = self.horizons[i] + 1
                for j in range(self.N_j):
                    for k in range(self.N_k):
                        start = alpha[j][i, 0, k] / 100
                        end = alpha[j][i, 1, k] / 100
                        dat = self._interpolator(start, end, Nin)
                        self.alpha_ijkn[i, j, k, :Nin] = dat[:]

            self.boundsAR['taxable'] = taxable
            self.boundsAR['tax-deferred'] = taxDeferred
            self.boundsAR['tax-free'] = taxFree

        elif allocType == 'individual':
            assert len(generic) == self.N_i, 'generic must have one list per individual.'
            for i in range(self.N_i):
                # Initial and final.
                assert len(generic[i]) == 2, 'generic[%d] must have 2 lists (initial and final).' % i
                for z in range(2):
                    assert len(generic[i][z]) == self.N_k, 'generic[%d][%d] must have %d entries.' % (
                        i,
                        z,
                        self.N_k,
                    )
                    assert abs(sum(generic[i][z]) - 100) < 0.01, 'Sum of percentages must add to 100.'

            for i in range(self.N_i):
                u.vprint(
                    self.inames[i],
                    ': Setting gliding allocation ratios (%) to',
                    allocType,
                )
                u.vprint('\t', generic[i][0], '->', generic[i][1])

            for i in range(self.N_i):
                Nin = self.horizons[i] + 1
                for k in range(self.N_k):
                    start = generic[i][0][k] / 100
                    end = generic[i][1][k] / 100
                    dat = self._interpolator(start, end, Nin)
                    for j in range(self.N_j):
                        self.alpha_ijkn[i, j, k, :Nin] = dat[:]

            self.boundsAR['generic'] = generic

        elif allocType == 'spouses':
            assert len(generic) == 2, 'generic must have 2 entries (initial and final).'
            for z in range(2):
                assert len(generic[z]) == self.N_k, 'generic[%d] must have %d entries.' % (
                    z,
                    self.N_k,
                )
                assert abs(sum(generic[z]) - 100) < 0.01, 'Sum of percentages must add to 100.'

            u.vprint('Setting gliding allocation ratios (%) to', allocType)
            u.vprint('\t', generic[0], '->', generic[1])

            # Use longest-lived spouse for both time scales.
            Nxn = max(self.horizons) + 1

            for k in range(self.N_k):
                start = generic[0][k] / 100
                end = generic[1][k] / 100
                dat = self._interpolator(start, end, Nxn)
                for i in range(self.N_i):
                    for j in range(self.N_j):
                        self.alpha_ijkn[i, j, k, :Nxn] = dat[:]

            self.boundsAR['generic'] = generic

        self.ARCoord = allocType
        self.caseStatus = 'modified'

        u.vprint('Interpolating assets allocation ratios using', self.interpMethod, 'method.')

        return None

    def readContributions(self, filename):
        """
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
                'big-ticket items'

        in any order. A template is provided as an example.
        Missing rows (years) are populated with zero values.
        """
        self.timeLists = timelists.read(filename, self.inames, self.horizons)

        timelists.check(self.inames, self.timeLists, self.horizons)
        self.timeListsFileName = filename

        # Now fill in parameters.
        for i in range(self.N_i):
            h = self.horizons[i]
            self.omega_in[i, :h] = self.timeLists[i]['anticipated wages'][:h]
            self.Lambda_in[i, :h] = self.timeLists[i]['big-ticket items'][:h]
            self.myRothX_in[i, :h] = self.timeLists[i]['Roth X'][:h]
            self.kappa_ijn[i, 0, :h] = self.timeLists[i]['ctrb taxable'][:h]
            self.kappa_ijn[i, 1, :h] = self.timeLists[i]['ctrb 401k'][:h]
            self.kappa_ijn[i, 1, :h] += self.timeLists[i]['ctrb IRA'][:h]
            self.kappa_ijn[i, 2, :h] = self.timeLists[i]['ctrb Roth 401k'][:h]
            self.kappa_ijn[i, 2, :h] += self.timeLists[i]['ctrb Roth IRA'][:h]

        #  In 1st year, reduce wages and contribution depending on starting date.
        self.omega_in[:, 0] *= self.yearFracLeft
        self.kappa_ijn[:, :, 0] *= self.yearFracLeft
        if self.yearFracLeft != 1:
            self.Lambda_in[:, 0] = 0
            self.myRothX_in[:, 0] = 0

        self.caseStatus = 'modified'

        return None

    def _linInterp(self, a, b, numPoints):
        """
        Utility function to interpolate allocations using
        a linear interpolation.
        """
        # num goes one more year as endpoint=True.
        dat = np.linspace(a, b, numPoints)

        return dat

    def _tanhInterp(self, a, b, numPoints):
        """
        Utility function to interpolate allocations using a hyperbolic
        tangent interpolation. "c" is the year where the inflection point
        is happening, and "w" is the width of the transition.
        """
        c = self.interpCenter
        w = self.interpWidth
        t = np.linspace(0, numPoints, numPoints)
        # Solve 2x2 system to match end points exactly.
        th0 = np.tanh((t[0] - c) / w)
        thN = np.tanh((t[numPoints - 1] - c) / w)
        k11 = 0.5 - 0.5 * th0
        k21 = 0.5 - 0.5 * thN
        k12 = 0.5 + 0.5 * th0
        k22 = 0.5 + 0.5 * thN
        _b = (b - (k21 / k11) * a) / (k22 - (k21 / k11) * k12)
        _a = (a - k12 * _b) / k11
        dat = _a + 0.5 * (_b - _a) * (1 + np.tanh((t - c) / w))

        return dat

    def _adjustParameters(self):
        """
        Adjust parameters that follow inflation.
        """
        if self.rateMethod is None:
            raise RuntimeError('A rate method needs to be first selected using setRates(...).')

        if not self._adjustedParameters:
            u.vprint('Adjusting parameters for inflation.')
            self.DeltaBar_tn = self.Delta_tn * self.gamma_n[:-1]
            self.zetaBar_in = self.zeta_in * self.gamma_n[:-1]
            self.sigmaBar_n = self.sigma_n * self.gamma_n[:-1]
            self.xiBar_n = self.xi_n * self.gamma_n[:-1]

            self._adjustedParameters = True

        return None

    def _buildOffsetMap(self):
        """
        Utility function to map variables to a block vector.
        Refer to companion document for explanations.
        """
        # Stack all variables in a single block vector.
        C = {}
        C['b'] = 0
        C['d'] = _qC(C['b'], self.N_i, self.N_j, self.N_n + 1)
        C['e'] = _qC(C['d'], self.N_i, self.N_n)
        C['F'] = _qC(C['e'], self.N_n)
        C['g'] = _qC(C['F'], self.N_t, self.N_n)
        C['s'] = _qC(C['g'], self.N_n)
        C['w'] = _qC(C['s'], self.N_n)
        C['x'] = _qC(C['w'], self.N_i, self.N_j, self.N_n)
        C['z'] = _qC(C['x'], self.N_i, self.N_n)
        self.nvars = _qC(C['z'], self.N_i, self.N_n, self.N_z)

        self.C = C
        u.vprint(
            'Problem has',
            len(C),
            'distinct time series forming',
            self.nvars,
            'decision variables.',
        )

        return None

    def _buildConstraints(self, objective, options):
        """
        Utility function that builds constraint matrix and vectors.
        Refer to companion document for notation and detailed explanations.
        """
        # Bounds values.
        zero = 0
        inf = np.inf

        # Simplified notation.
        Ni = self.N_i
        Nj = self.N_j
        Nk = self.N_k
        Nn = self.N_n
        Nt = self.N_t
        Nz = self.N_z
        i_d = self.i_d
        i_s = self.i_s
        n_d = self.n_d

        Cb = self.C['b']
        Cd = self.C['d']
        Ce = self.C['e']
        CF = self.C['F']
        Cg = self.C['g']
        Cs = self.C['s']
        Cw = self.C['w']
        Cx = self.C['x']
        Cz = self.C['z']

        tau_ijn = np.zeros((Ni, Nj, Nn))
        for i in range(Ni):
            for j in range(Nj):
                for n in range(Nn):
                    tau_ijn[i, j, n] = np.sum(self.alpha_ijkn[i, j, :, n] * self.tau_kn[:, n], axis=0)

        # Weights are normalized on k: sum_k[alpha*(1 + tau)] = 1 + sum_k(alpha*tau).
        Tau1_ijn = 1 + tau_ijn
        Tauh_ijn = 1 + tau_ijn / 2

        if 'units' in options:
            units = u.getUnits(options['units'])
        else:
            units = 1000

        bigM = 5e6
        if 'bigM' in options:
            # No units for bigM.
            bigM = options['bigM']

        ###################################################################
        # Inequality constraint matrix with upper and lower bound vectors.
        A = abc.ConstraintMatrix(self.nvars)
        B = abc.Bounds(self.nvars)

        # RMDs inequalities, only if there is an initial balance in tax-deferred account.
        for i in range(Ni):
            if self.beta_ij[i, 1] > 0:
                for n in range(self.horizons[i]):
                    rowDic = {
                        _q3(Cw, i, 1, n, Ni, Nj, Nn): 1,
                        _q3(Cb, i, 1, n, Ni, Nj, Nn + 1): -self.rho_in[i, n],
                    }
                    A.addNewRow(rowDic, zero, inf)

        # Income tax bracket range inequalities.
        for t in range(Nt):
            for n in range(Nn):
                B.set0_Ub(_q2(CF, t, n, Nt, Nn), self.DeltaBar_tn[t, n])

        # Standard exemption range inequalities.
        for n in range(Nn):
            B.set0_Ub(_q1(Ce, n, Nn), self.sigmaBar_n[n])

        # Roth conversions equalities/inequalities.
        if 'maxRothConversion' in options:
            if options['maxRothConversion'] == 'file':
                # u.vprint('Fixing Roth conversions to those from file %s.' % self.timeListsFileName)
                for i in range(Ni):
                    for n in range(self.horizons[i]):
                        rhs = self.myRothX_in[i][n]
                        B.setRange(_q2(Cx, i, n, Ni, Nn), rhs, rhs)
            else:
                rhsopt = options['maxRothConversion']
                assert isinstance(rhsopt, (int, float)), 'Specified maxConversion is not a number.'
                rhsopt *= units
                if rhsopt < 0:
                    # u.vprint('Unlimited Roth conversions (<0)')
                    pass
                else:
                    # u.vprint('Limiting Roth conversions to:', u.d(rhsopt))
                    for i in range(Ni):
                        for n in range(self.horizons[i]):
                            #  Should we adjust Roth conversion cap with inflation?
                            B.set0_Ub(_q2(Cx, i, n, Ni, Nn), rhsopt)

        # Process noRothConversions option. Also valid when N_i == 1, why not?
        if 'noRothConversions' in options:
            rhsopt = options['noRothConversions']
            try:
                i_x = self.inames.index(rhsopt)
            except ValueError:
                raise ValueError('Unknown individual %s for noRothConversions:' % rhsopt)

            for n in range(Nn):
                B.set0_Ub(_q2(Cx, i_x, n, Ni, Nn), zero)

        # Impose withdrawal limits on taxable and tax-exempt accounts.
        for i in range(Ni):
            for j in [0, 2]:
                for n in range(Nn):
                    rowDic = {_q3(Cw, i, j, n, Ni, Nj, Nn): -1, _q3(Cb, i, j, n, Ni, Nj, Nn + 1): 1}
                    A.addNewRow(rowDic, zero, inf)

        # Impose withdrawals and conversion limits on tax-deferred account.
        for i in range(Ni):
            for n in range(Nn):
                rowDic = {
                    _q2(Cx, i, n, Ni, Nn): -1,
                    _q3(Cw, i, 1, n, Ni, Nj, Nn): -1,
                    _q3(Cb, i, 1, n, Ni, Nj, Nn + 1): 1,
                }
                A.addNewRow(rowDic, zero, inf)

        # Constraints depending on objective function.
        if objective == 'maxSpending':
            # Impose optional constraint on final bequest requested in today's $.
            if 'bequest' in options:
                bequest = options['bequest']
                assert isinstance(bequest, (int, float)), 'Desired bequest is not a number.'
                bequest *= units * self.gamma_n[-1]
            else:
                # If not specified, defaults to $1 (nominal $).
                bequest = 1

            row = A.newRow()
            for i in range(Ni):
                row.addElem(_q3(Cb, i, 0, Nn, Ni, Nj, Nn + 1), 1)
                row.addElem(_q3(Cb, i, 1, Nn, Ni, Nj, Nn + 1), 1 - self.nu)
                # Nudge could be added (e.g. 1.02) to artificially favor tax-exempt account
                # as heirs's benefits of 10y tax-free is not weighted in?
                row.addElem(_q3(Cb, i, 2, Nn, Ni, Nj, Nn + 1), 1)
            A.addRow(row, bequest, bequest)
            # u.vprint('Adding bequest constraint of:', u.d(bequest))
        elif objective == 'maxBequest':
            spending = options['netSpending']
            assert isinstance(spending, (int, float)), 'Desired spending provided is not a number.'
            # Account for time elapsed in the current year.
            spending *= units * self.yearFracLeft
            # u.vprint('Maximizing bequest with desired net spending of:', u.d(spending))
            A.addNewRow({_q1(Cg, 0): 1}, spending, spending)

        # Set initial balances through constraints.
        for i in range(Ni):
            for j in range(Nj):
                rhs = self.beta_ij[i, j]
                A.addNewRow({_q3(Cb, i, j, 0, Ni, Nj, Nn + 1): 1}, rhs, rhs)

        # Link surplus and taxable account deposits regardless of Ni.
        for i in range(Ni):
            fac1 = u.krond(i, 0) * (1 - self.eta) + u.krond(i, 1) * self.eta
            for n in range(n_d):
                rowDic = {_q2(Cd, i, n, Ni, Nn): 1, _q1(Cs, n, Nn): -fac1}
                A.addNewRow(rowDic, zero, zero)
            fac2 = u.krond(self.i_s, i)
            for n in range(n_d, Nn):
                rowDic = {_q2(Cd, i, n, Ni, Nn): 1, _q1(Cs, n, Nn): -fac2}
                A.addNewRow(rowDic, zero, zero)

        # No surplus allowed during the last year to be used as a tax loophole.
        B.set0_Ub(_q1(Cs, Nn - 1, Nn), zero)

        if Ni == 2:
            # No conversion during last year.
            # B.set0_Ub(_q2(Cx, i_d, nd-1, Ni, Nn), zero)
            # B.set0_Ub(_q2(Cx, i_s, Nn-1, Ni, Nn), zero)

            # No withdrawals or deposits for any i_d-owned accounts after year of passing.
            # Implicit n_d < Nn imposed by for loop.
            for n in range(n_d, Nn):
                B.set0_Ub(_q2(Cd, i_d, n, Ni, Nn), zero)
                B.set0_Ub(_q2(Cx, i_d, n, Ni, Nn), zero)
                for j in range(Nj):
                    B.set0_Ub(_q3(Cw, i_d, j, n, Ni, Nj, Nn), zero)

        # Account balances carried from year to year.
        # Considering spousal asset transfer at passing of a spouse.
        # Using hybrid approach with 'if' statement and Kronecker deltas.
        for i in range(Ni):
            for j in range(Nj):
                for n in range(Nn):
                    if Ni == 2 and n_d < Nn and i == i_d and n == n_d - 1:
                        # fac1 = 1 - (u.krond(n, n_d - 1) * u.krond(i, i_d))
                        fac1 = 0
                    else:
                        fac1 = 1

                    rhs = fac1 * self.kappa_ijn[i, j, n] * Tauh_ijn[i, j, n]

                    row = A.newRow()
                    row.addElem(_q3(Cb, i, j, n + 1, Ni, Nj, Nn + 1), 1)
                    row.addElem(_q3(Cb, i, j, n, Ni, Nj, Nn + 1), -fac1 * Tau1_ijn[i, j, n])
                    row.addElem(_q3(Cw, i, j, n, Ni, Nj, Nn), fac1 * Tau1_ijn[i, j, n])
                    row.addElem(_q2(Cd, i, n, Ni, Nn), -fac1 * u.krond(j, 0) * Tau1_ijn[i, 0, n])
                    row.addElem(
                        _q2(Cx, i, n, Ni, Nn),
                        -fac1 * (u.krond(j, 2) - u.krond(j, 1)) * Tau1_ijn[i, j, n],
                    )

                    if Ni == 2 and n_d < Nn and i == i_s and n == n_d - 1:
                        fac2 = self.phi_j[j]
                        rhs += fac2 * self.kappa_ijn[i_d, j, n] * Tauh_ijn[i_d, j, n]
                        row.addElem(_q3(Cb, i_d, j, n, Ni, Nj, Nn + 1), -fac2 * Tau1_ijn[i_d, j, n])
                        row.addElem(_q3(Cw, i_d, j, n, Ni, Nj, Nn), fac2 * Tau1_ijn[i_d, j, n])
                        row.addElem(_q2(Cd, i_d, n, Ni, Nn), -fac2 * u.krond(j, 0) * Tau1_ijn[i_d, 0, n])
                        row.addElem(
                            _q2(Cx, i_d, n, Ni, Nn),
                            -fac2 * (u.krond(j, 2) - u.krond(j, 1)) * Tau1_ijn[i_d, j, n],
                        )
                    A.addRow(row, rhs, rhs)

        tau_0prev = np.roll(self.tau_kn[0, :], 1)
        tau_0prev[tau_0prev < 0] = 0

        # Net cash flow.
        for n in range(Nn):
            rhs = -self.M_n[n]
            row = A.newRow({_q1(Cg, n, Nn): 1})
            row.addElem(_q1(Cs, n, Nn), 1)
            for i in range(Ni):
                fac = self.psi * self.alpha_ijkn[i, 0, 0, n]
                rhs += (
                    self.omega_in[i, n]
                    + self.zetaBar_in[i, n]
                    + self.pi_in[i, n]
                    + self.Lambda_in[i, n]
                    - 0.5 * fac * self.mu * self.kappa_ijn[i, 0, n]
                )

                row.addElem(_q3(Cb, i, 0, n, Ni, Nj, Nn + 1), fac * self.mu)
                # Minus capital gains on taxable withdrawals using last year's rate if >=0.
                # Plus taxable account withdrawals, and all other withdrawals.
                row.addElem(_q3(Cw, i, 0, n, Ni, Nj, Nn), fac * (tau_0prev[n] - self.mu) - 1)
                row.addElem(_q3(Cw, i, 1, n, Ni, Nj, Nn), -1)
                row.addElem(_q3(Cw, i, 2, n, Ni, Nj, Nn), -1)
                row.addElem(_q2(Cd, i, n, Ni, Nn), fac * self.mu)

            # Minus tax on ordinary income, T_n.
            for t in range(Nt):
                row.addElem(_q2(CF, t, n, Nt, Nn), self.theta_tn[t, n])

            A.addRow(row, rhs, rhs)

        # Impose income profile.
        for n in range(1, Nn):
            rowDic = {_q1(Cg, 0, Nn): -self.xiBar_n[n], _q1(Cg, n, Nn): self.xiBar_n[0]}
            A.addNewRow(rowDic, zero, zero)

        # Taxable ordinary income.
        for n in range(Nn):
            rhs = 0
            row = A.newRow()
            row.addElem(_q1(Ce, n, Nn), 1)
            for i in range(Ni):
                rhs += self.omega_in[i, n] + 0.85 * self.zetaBar_in[i, n] + self.pi_in[i, n]
                # Taxable income from tax-deferred withdrawals.
                row.addElem(_q3(Cw, i, 1, n, Ni, Nj, Nn), -1)
                row.addElem(_q2(Cx, i, n, Ni, Nn), -1)

                # Taxable returns on securities in taxable account.
                fak = np.sum(self.tau_kn[1:Nk, n] * self.alpha_ijkn[i, 0, 1:Nk, n], axis=0)
                rhs += 0.5 * fak * self.kappa_ijn[i, 0, n]
                row.addElem(_q3(Cb, i, 0, n, Ni, Nj, Nn + 1), -fak)
                row.addElem(_q3(Cw, i, 0, n, Ni, Nj, Nn), fak)
                row.addElem(_q2(Cd, i, n, Ni, Nn), -fak)

            for t in range(Nt):
                row.addElem(_q2(CF, t, n, Nt, Nn), 1)

            A.addRow(row, rhs, rhs)

        # Configure binary variables.
        for i in range(Ni):
            for n in range(self.horizons[i]):
                for z in range(Nz):
                    B.setBinary(_q3(Cz, i, n, z, Ni, Nn, Nz))

                # Exclude simultaneous deposits and withdrawals from taxable or tax-free accounts.
                A.addNewRow(
                    {_q3(Cz, i, n, 0, Ni, Nn, Nz): bigM, _q1(Cs, n, Nn): -1},
                    zero,
                    bigM,
                )

                A.addNewRow(
                    {
                        _q3(Cz, i, n, 0, Ni, Nn, Nz): bigM,
                        _q3(Cw, i, 0, n, Ni, Nj, Nn): 1,
                        _q3(Cw, i, 2, n, Ni, Nj, Nn): 1,
                    },
                    zero,
                    bigM,
                )

                # Exclude simultaneous Roth conversions and tax-exempt withdrawals.
                A.addNewRow(
                    {_q3(Cz, i, n, 1, Ni, Nn, Nz): bigM, _q2(Cx, i, n, Ni, Nn): -1},
                    zero,
                    bigM,
                )

                A.addNewRow(
                    {_q3(Cz, i, n, 1, Ni, Nn, Nz): bigM, _q3(Cw, i, 2, n, Ni, Nj, Nn): 1},
                    zero,
                    bigM,
                )

        # Now build a solver-neutral objective vector.
        c = abc.Objective(self.nvars)
        if objective == 'maxSpending':
            c.setElem(_q1(Cg, 0, Nn), -1)
        elif objective == 'maxBequest':
            for i in range(Ni):
                c.setElem(_q3(Cb, i, 0, Nn, Ni, Nj, Nn + 1), -1)
                c.setElem(_q3(Cb, i, 1, Nn, Ni, Nj, Nn + 1), -(1 - self.nu))
                c.setElem(_q3(Cb, i, 2, Nn, Ni, Nj, Nn + 1), -1)
        else:
            raise RuntimeError('Internal error in objective function.')

        self.A = A
        self.B = B
        self.c = c

        return None

    @_timer
    def runHistoricalRange(self, objective, options, ystart, yend, verbose=False):
        """
        Run historical scenarios on plan over a range of years.
        """
        N = yend - ystart + 1
        if yend + self.N_n > self.year_n[0]:
            yend = self.year_n[0] - self.N_n
            print('Warning: Upper bound for year range re-adjusted to %d.' % yend)

        old_status = setVerbose(verbose)

        if objective == 'maxSpending':
            columns = ['partial', objective]
        elif objective == 'maxBequest':
            columns = ['partial', 'final']

        df = pd.DataFrame(columns=columns)

        if not verbose:
            print('|--- progress ---|')

        for year in range(ystart, yend + 1):
            self.setRates('historical', year)
            self.solve(objective, options)
            if not verbose:
                print('\r\t%s' % u.pc((year - ystart + 1) / N, f=0), end='')
            if self.caseStatus == 'solved':
                if objective == 'maxSpending':
                    df.loc[len(df)] = [self.partialBequest, self.basis]
                elif objective == 'maxBequest':
                    df.loc[len(df)] = [self.partialBequest, self.bequest]

        print()
        setVerbose(old_status)
        self._showResults(objective, df, N)

        return N, df

    @_timer
    def runMC(self, objective, options, N, verbose=False):
        """
        Run Monte Carlo simulations on plan.
        """
        if self.rateMethod not in ['stochastic', 'histochastic']:
            print('It is pointless to run Monte Carlo simulations with fixed rates.')
            return

        old_status = setVerbose(verbose)

        # Turn off Medicare by default, unless specified in options.
        if 'withMedicare' not in options:
            myoptions = dict(options)
            myoptions['withMedicare'] = False
        else:
            myoptions = options

        if objective == 'maxSpending':
            columns = ['partial', objective]
        elif objective == 'maxBequest':
            columns = ['partial', 'final']

        df = pd.DataFrame(columns=columns)

        if not verbose:
            print('|--- progress ---|')

        for n in range(N):
            self.regenRates()
            self.solve(objective, myoptions)
            if not verbose:
                print('\r\t%s' % u.pc((n + 1) / N, f=0), end='')
            if self.caseStatus == 'solved':
                if objective == 'maxSpending':
                    df.loc[len(df)] = [self.partialBequest, self.basis]
                elif objective == 'maxBequest':
                    df.loc[len(df)] = [self.partialBequest, self.bequest]

        print()
        setVerbose(old_status)
        self._showResults(objective, df, N)

        return N, df

    def _showResults(self, objective, df, N):
        """
        Show a histogram of values from runMC() and runRange().
        """
        import seaborn as sbn
        import matplotlib.pyplot as plt

        print('Success rate: %s on %d samples.' % (u.pc(len(df) / N), N))
        title = '$N$ = %d, $P$ = %s' % (N, u.pc(len(df) / N))
        means = df.mean(axis=0, numeric_only=True)
        medians = df.median(axis=0, numeric_only=True)

        my = 2 * [self.year_n[-1]]
        if self.N_i == 2 and self.n_d < self.N_n:
            my[0] = self.year_n[self.n_d - 1]

            # Don't show partial bequest of zero if spouse is full beneficiary,
            # or if solution led to empty accounts at the end of first spouse's life.
            if np.all(self.phi_j == 1) or medians.iloc[0] < 1:
                if medians.iloc[0] < 1:
                    print('Optimized solutions all have null partial bequest in year %d.' % my[0])
                df.drop('partial', axis=1, inplace=True)
                means = df.mean(axis=0, numeric_only=True)
                medians = df.median(axis=0, numeric_only=True)

        df /= 1000
        if len(df) > 0:
            if objective == 'maxBequest':
                # Show both partial and final bequests on the same histogram.
                sbn.histplot(df, multiple='dodge', kde=True)
                legend = []
                # Don't know why but legend is reversed from df.
                for q in range(len(means) - 1, -1, -1):
                    legend.append(
                        '%d: $M$: %s, $\\bar{x}$: %s'
                        % (my[q], u.d(medians.iloc[q], latex=True), u.d(means.iloc[q], latex=True))
                    )
                plt.legend(legend, shadow=True)
                plt.xlabel('%d k$' % self.year_n[0])
                plt.title(objective)
                leads = ['partial %d' % my[0], '  final %d' % my[1]]
            elif len(means) == 2:
                # Show partial bequest and net spending as two separate histograms.
                fig, axes = plt.subplots(1, 2, figsize=(10, 5))
                cols = ['partial', objective]
                leads = ['partial %d' % my[0], objective]
                for q in range(2):
                    sbn.histplot(df[cols[q]], kde=True, ax=axes[q])
                    legend = [
                        ('$M$: %s, $\\bar{x}$: %s' % (u.d(medians.iloc[q], latex=True), u.d(means.iloc[q], latex=True)))
                    ]
                    axes[q].set_label(legend)
                    axes[q].legend(labels=legend)
                    axes[q].set_title(leads[q])
                    axes[q].set_xlabel('%d k$' % self.year_n[0])
            else:
                # Show net spending as single histogram.
                sbn.histplot(df[objective], kde=True)
                legend = [
                    ('$M$: %s, $\\bar{x}$: %s' % (u.d(medians.iloc[0], latex=True), u.d(means.iloc[0], latex=True)))
                ]
                plt.legend(legend, shadow=True)
                plt.xlabel('%d k$' % self.year_n[0])
                plt.title(objective)
                leads = [objective]

            plt.suptitle(title)
            plt.show()

        for q in range(len(means)):
            print('%12s: Median (%d $): %s' % (leads[q], self.year_n[0], u.d(medians.iloc[q])))
            print('%12s:   Mean (%d $): %s' % (leads[q], self.year_n[0], u.d(means.iloc[q])))
            print(
                '%12s:           Range: %s - %s'
                % (leads[q], u.d(1000 * df.iloc[:, q].min()), u.d(1000 * df.iloc[:, q].max()))
            )
            nzeros = len(df.iloc[:, q][df.iloc[:, q] < 0.001])
            print('%12s:  N zero solns: %d' % (leads[q], nzeros))

        return None

    def resolve(self):
        """
        Solve a plan using saved options.
        """
        self.solve(self.objective, self.solverOptions)

        return None

    @_checkConfiguration
    def solve(self, objective, options=None):
        """
        This function builds the necessary constaints and
        runs the optimizer.

        - objective can be 'maxSpending' or 'maxBequest'.

        - options is a dictionary which can include:
            - maxRothConversion: Only allow conversion smaller than amount specified.
            - netSpending: Desired spending amount when optimizing with maxBequest.
            - bequest: Value of bequest in today's $ when optimizing with maxSpending.
            - units: Units to use for amounts (1, k, or M).

        All units are in $k, unless specified otherwise.

        Refer to companion document for implementation details.
        """
        if self.rateMethod is None:
            raise RuntimeError('Rate method must be selected before solving.')

        # Assume unsuccessful until problem solved.
        self.caseStatus = 'unsuccessful'

        # Check objective and required options.
        knownObjectives = ['maxBequest', 'maxSpending']
        knownSolvers = ['HiGHS', 'MOSEK']
        knownOptions = [
            'units',
            'maxRothConversion',
            'netSpending',
            'bequest',
            'bigM',
            'noRothConversions',
            'withMedicare',
            'solver',
        ]
        # We will modify options if required.
        if options is None:
            myoptions = {}
        else:
            myoptions = dict(options)

        for opt in myoptions:
            if opt not in knownOptions:
                raise ValueError('Option %s is not one of %r.' % (opt, knownOptions))

        if objective not in knownObjectives:
            raise ValueError('Objective %s is not one of %r.' % (objective, knownObjectives))

        if objective == 'maxBequest' and 'netSpending' not in myoptions:
            raise RuntimeError('Objective %s needs netSpending option.' % objective)

        if objective == 'maxBequest' and 'bequest' in myoptions:
            u.vprint('Ignoring bequest option provided.')
            myoptions.pop('bequest')

        if objective == 'maxSpending' and 'netSpending' in myoptions:
            u.vprint('Ignoring netSpending option provided.')
            myoptions.pop('netSpending')

        if objective == 'maxSpending' and 'bequest' not in myoptions:
            u.vprint('Using bequest of $1.')

        self._adjustParameters()

        if 'solver' in options:
            solver = myoptions['solver']
            if solver not in knownSolvers:
                raise ValueError('Unknown solver %s.' % solver)
        else:
            solver = self.defaultSolver

        if solver == 'HiGHS':
            self._milpSolve(objective, myoptions)
        elif solver == 'MOSEK':
            self._mosekSolve(objective, myoptions)

        self.objective = objective
        self.solverOptions = myoptions

        return None

    def _milpSolve(self, objective, options):
        """
        Solve problem using scipy HiGHS solver.
        """
        from scipy import optimize

        withMedicare = True
        if 'withMedicare' in options and options['withMedicare'] is False:
            withMedicare = False

        if objective == 'maxSpending':
            objFac = -1 / self.xi_n[0]
        else:
            objFac = -1 / self.gamma_n[-1]

        # mip_rel_gap smaller than 1e-6 can lead to oscillatory solutions.
        milpOptions = {'disp': False, 'mip_rel_gap': 1e-6}

        it = 0
        absdiff = np.inf
        old_x = np.zeros(self.nvars)
        old_solutions = [np.inf]
        self._estimateMedicare(None, withMedicare)
        while True:
            self._buildConstraints(objective, options)
            Alu, lbvec, ubvec = self.A.arrays()
            Lb, Ub = self.B.arrays()
            integrality = self.B.integralityArray()
            c = self.c.arrays()

            bounds = optimize.Bounds(Lb, Ub)
            constraint = optimize.LinearConstraint(Alu, lbvec, ubvec)
            solution = optimize.milp(
                c,
                integrality=integrality,
                constraints=constraint,
                bounds=bounds,
                options=milpOptions,
            )
            it += 1

            if not solution.success:
                break

            if not withMedicare:
                break

            self._estimateMedicare(solution.x)

            u.vprint('Iteration:', it, 'objective:', u.d(solution.fun * objFac, f=2))

            delta = solution.x - old_x
            absdiff = np.sum(np.abs(delta), axis=0)
            if absdiff < 1:
                u.vprint('Converged on full solution.')
                break

            # Avoid oscillatory solutions. Look only at most recent solutions.
            isclosenough = abs(-solution.fun - min(old_solutions[int(it / 2):])) < self.xi_n[0]
            if isclosenough:
                u.vprint('Converged through selecting minimum oscillating objective.')
                break

            if it > 59:
                u.vprint('WARNING: Exiting loop on maximum iterations.')
                break

            old_solutions.append(-solution.fun)
            old_x = solution.x

        if solution.success:
            u.vprint('Self-consistent Medicare loop returned after %d iterations.' % it)
            u.vprint(solution.message)
            u.vprint('Objective:', u.d(solution.fun * objFac))
            # u.vprint('Upper bound:', u.d(-solution.mip_dual_bound))
            self._aggregateResults(solution.x)
            self._timestamp = datetime.now().strftime('%Y-%m-%d at %H:%M:%S')
            self.caseStatus = 'solved'
        else:
            u.vprint('WARNING: Optimization failed:', solution.message, solution.success)
            self.caseStatus = 'unsuccessful'

        return None

    def _mosekSolve(self, objective, options):
        """
        Solve problem using MOSEK solver.
        """
        import mosek

        withMedicare = True
        if 'withMedicare' in options and options['withMedicare'] is False:
            withMedicare = False

        if objective == 'maxSpending':
            objFac = -1 / self.xi_n[0]
        else:
            objFac = -1 / self.gamma_n[-1]

        # mip_rel_gap smaller than 1e-6 can lead to oscillatory solutions.

        bdic = {
            'fx': mosek.boundkey.fx,
            'fr': mosek.boundkey.fr,
            'lo': mosek.boundkey.lo,
            'ra': mosek.boundkey.ra,
            'up': mosek.boundkey.up,
        }

        it = 0
        absdiff = np.inf
        old_x = np.zeros(self.nvars)
        old_solutions = [np.inf]
        self._estimateMedicare(None, withMedicare)
        while True:
            self._buildConstraints(objective, options)
            Aind, Aval, clb, cub = self.A.lists()
            ckeys = self.A.keys()
            vlb, vub = self.B.arrays()
            integrality = self.B.integralityList()
            vkeys = self.B.keys()
            cind, cval = self.c.lists()

            task = mosek.Task()
            # task.putdouparam(mosek.dparam.mio_rel_gap_const, 1e-5)
            # task.putdouparam(mosek.dparam.mio_tol_abs_relax_int, 1e-4)
            # task.set_Stream(mosek.streamtype.msg, _streamPrinter)
            task.appendcons(self.A.ncons)
            task.appendvars(self.A.nvars)

            for ii in range(len(cind)):
                task.putcj(cind[ii], cval[ii])

            for ii in range(self.nvars):
                task.putvarbound(ii, bdic[vkeys[ii]], vlb[ii], vub[ii])

            for ii in range(len(integrality)):
                task.putvartype(integrality[ii], mosek.variabletype.type_int)

            for ii in range(self.A.ncons):
                task.putarow(ii, Aind[ii], Aval[ii])
                task.putconbound(ii, bdic[ckeys[ii]], clb[ii], cub[ii])

            task.putobjsense(mosek.objsense.minimize)
            task.optimize()

            solsta = task.getsolsta(mosek.soltype.itg)
            # prosta = task.getprosta(mosek.soltype.itg)
            it += 1

            if solsta != mosek.solsta.integer_optimal:
                break

            xx = np.array(task.getxx(mosek.soltype.itg))
            solution = task.getprimalobj(mosek.soltype.itg)

            if withMedicare is False:
                break

            self._estimateMedicare(xx)

            u.vprint('Iteration:', it, 'objective:', u.d(solution * objFac, f=2))

            delta = xx - old_x
            absdiff = np.sum(np.abs(delta), axis=0)
            if absdiff < 1:
                u.vprint('Converged on full solution.')
                break

            # Avoid oscillatory solutions. Look only at most recent solutions.
            isclosenough = abs(-solution - min(old_solutions[int(it / 2):])) < self.xi_n[0]
            if isclosenough:
                u.vprint('Converged through selecting minimum oscillating objective.')
                break

            if it > 59:
                u.vprint('WARNING: Exiting loop on maximum iterations.')
                break

            old_solutions.append(-solution)
            old_x = xx

        task.set_Stream(mosek.streamtype.msg, _streamPrinter)
        # task.writedata(self._name+'.ptf')
        if solsta == mosek.solsta.integer_optimal:
            u.vprint('Self-consistent Medicare loop returned after %d iterations.' % it)
            task.solutionsummary(mosek.streamtype.msg)
            u.vprint('Objective:', u.d(solution * objFac))
            self.caseStatus = 'solved'
            # u.vprint('Upper bound:', u.d(-solution.mip_dual_bound))
            self._aggregateResults(xx)
            self._timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        else:
            u.vprint('WARNING: Optimization failed:', 'Infeasible or unbounded.')
            task.solutionsummary(mosek.streamtype.msg)
            self.caseStatus = 'unsuccessful'

        return None

    def _estimateMedicare(self, x=None, withMedicare=True):
        """
        Compute rough MAGI and Medicare costs.
        """
        if withMedicare is False:
            self.M_n = np.zeros(self.N_n)
            return

        if x is None:
            MAGI_n = np.zeros(self.N_n)
        else:
            self.F_tn = np.array(x[self.C['F']:self.C['g']])
            self.F_tn = self.F_tn.reshape((self.N_t, self.N_n))
            MAGI_n = np.sum(self.F_tn, axis=0) + np.array(x[self.C['e']:self.C['F']])

        self.M_n = tx.mediCosts(self.yobs, self.horizons, MAGI_n, self.gamma_n[:-1], self.N_n)

        return None

    def _aggregateResults(self, x):
        """
        Utility function to aggregate results from solver.
        Process all results from solution vector.
        """
        # Define shortcuts.
        Ni = self.N_i
        Nj = self.N_j
        Nk = self.N_k
        Nn = self.N_n
        Nt = self.N_t
        # Nz = self.N_z
        n_d = self.n_d

        Cb = self.C['b']
        Cd = self.C['d']
        Ce = self.C['e']
        CF = self.C['F']
        Cg = self.C['g']
        Cs = self.C['s']
        Cw = self.C['w']
        Cx = self.C['x']
        Cz = self.C['z']

        x = u.roundCents(x)

        # Allocate, slice in, and reshape variables.
        self.b_ijn = np.array(x[Cb:Cd])
        self.b_ijn = self.b_ijn.reshape((Ni, Nj, Nn + 1))
        self.b_ijkn = np.zeros((Ni, Nj, Nk, Nn + 1))
        for k in range(Nk):
            self.b_ijkn[:, :, k, :] = self.b_ijn[:, :, :] * self.alpha_ijkn[:, :, k, :]

        self.d_in = np.array(x[Cd:Ce])
        self.d_in = self.d_in.reshape((Ni, Nn))

        self.e_n = np.array(x[Ce:CF])

        self.F_tn = np.array(x[CF:Cg])
        self.F_tn = self.F_tn.reshape((Nt, Nn))

        self.g_n = np.array(x[Cg:Cs])

        self.s_n = np.array(x[Cs:Cw])

        self.w_ijn = np.array(x[Cw:Cx])
        self.w_ijn = self.w_ijn.reshape((Ni, Nj, Nn))

        self.x_in = np.array(x[Cx:Cz])
        self.x_in = self.x_in.reshape((Ni, Nn))

        # self.z_inz = np.array(x[Cz:])
        # self.z_inz = self.z_inz.reshape((Ni, Nn, Nz))
        # print(self.z_inz)

        # Partial distribution at the passing of first spouse.
        if Ni == 2 and n_d < Nn:
            nx = n_d - 1
            i_d = self.i_d
            part_j = np.zeros(3)
            for j in range(Nj):
                ksumj = np.sum(self.alpha_ijkn[i_d, j, :, nx] * self.tau_kn[:, nx], axis=0)
                Tauh = 1 + 0.5 * ksumj
                Tau1 = 1 + ksumj
                part_j[j] = Tauh * self.kappa_ijn[i_d, j, nx] + Tau1 * (
                    self.b_ijn[i_d, j, nx]
                    - self.w_ijn[i_d, j, nx]
                    + self.d_in[i_d, nx] * u.krond(j, 0)
                    + self.x_in[i_d, nx] * (u.krond(j, 2) - u.krond(j, 1))
                )

            self.partialEstate_j = part_j
            partialBequest_j = part_j * (1 - self.phi_j)
            partialBequest_j[1] *= 1 - self.nu
            self.partialBequest = np.sum(partialBequest_j) / self.gamma_n[n_d]

        self.rmd_in = self.rho_in * self.b_ijn[:, 1, :-1]
        self.dist_in = self.w_ijn[:, 1, :] - self.rmd_in
        self.dist_in[self.dist_in < 0] = 0
        self.G_n = np.sum(self.F_tn, axis=0)
        T_tn = self.F_tn * self.theta_tn
        self.T_n = np.sum(T_tn, axis=0)

        tau_0 = np.array(self.tau_kn[0, :])
        tau_0[tau_0 < 0] = 0
        # Last year's rates.
        tau_0prev = np.roll(tau_0, 1)
        self.Q_n = np.sum(
            (
                self.mu
                * (self.b_ijn[:, 0, :-1] - self.w_ijn[:, 0, :] + self.d_in[:, :] + 0.5 * self.kappa_ijn[:, 0, :])
                + tau_0prev * self.w_ijn[:, 0, :]
            )
            * self.alpha_ijkn[:, 0, 0, :-1],
            axis=0,
        )
        self.U_n = self.psi * self.Q_n

        # Make derivative variables.
        # Putting it all together in a dictionary.
        """
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
        """
        sources = {}
        sources['wages'] = self.omega_in
        sources['ssec'] = self.zetaBar_in
        sources['pension'] = self.pi_in
        sources['wdrwl taxable'] = self.w_ijn[:, 0, :]
        sources['rmd'] = self.rmd_in
        sources['dist'] = self.dist_in
        sources['RothX'] = self.x_in
        sources['wdrwl tax-free'] = self.w_ijn[:, 2, :]
        sources['bti'] = self.Lambda_in

        savings = {}
        savings['taxable'] = self.b_ijn[:, 0, :]
        savings['tax-deferred'] = self.b_ijn[:, 1, :]
        savings['tax-free'] = self.b_ijn[:, 2, :]

        self.sources_in = sources
        self.savings_in = savings

        estate_j = np.sum(self.b_ijn[:, :, self.N_n], axis=0)
        estate_j[1] *= 1 - self.nu
        self.bequest = np.sum(estate_j) / self.gamma_n[-1]

        self.basis = self.g_n[0] / self.xi_n[0]

        return None

    @_checkCaseStatus
    def estate(self):
        """
        Reports final account balances.
        """
        _estate = np.sum(self.b_ijn[:, :, :, self.N_n], axis=(0, 2))
        _estate[1] *= 1 - self.nu
        u.vprint('Estate value of %s at the end of year %s.' % (u.d(sum(_estate)), self.year_n[-1]))

        return None

    @_checkCaseStatus
    def summary(self):
        """
        Print summary of values.
        """
        lines = self._summaryList()
        for line in lines:
            print(line)

        return None

    def _summaryList(self):
        """
        Return string with summary of values.
        """
        now = self.year_n[0]
        lines = []
        lines.append('SUMMARY ================================================================')
        lines.append('Plan name: %s' % self._name)
        for i in range(self.N_i):
            lines.append("%12s's life horizon: %d -> %d" % (self.inames[i], now, now + self.horizons[i] - 1))
        lines.append('Contributions file: %s' % self.timeListsFileName)
        lines.append('Initial balances [taxable, tax-deferred, tax-free]:')
        for i in range(self.N_i):
            lines.append("%12s's accounts: %s" % (self.inames[i], [u.d(self.beta_ij[i][j]) for j in range(self.N_j)]))

        lines.append('Return rates: %s' % self.rateMethod)
        if self.rateMethod in ['historical', 'average', 'histochastic']:
            lines.append('Rates used: from %d to %d' % (self.rateFrm, self.rateTo))
        elif self.rateMethod == 'stochastic':
            lines.append(
                'Mean rates used (%%): %s' % (['{:.1f}'.format(100 * self.rateValues[k]) for k in range(self.N_k)])
            )
            lines.append(
                'Standard deviation used (%%): %s'
                % (['{:.1f}'.format(100 * self.rateStdev[k]) for k in range(self.N_k)])
            )
            lines.append('Correlation matrix used:')
            lines.append('\t\t' + str(self.rateCorr).replace('\n', '\n\t\t'))
        else:
            lines.append('Rates used (%%): %s' % (['{:.1f}'.format(100 * self.rateValues[k]) for k in range(self.N_k)]))
        lines.append("This year's starting date: %s" % self.startDate)
        lines.append('Optimized for: %s' % self.objective)
        lines.append('Solver options: %s' % self.solverOptions)
        lines.append('Number of decision variables: %d' % self.A.nvars)
        lines.append('Number of constraints: %d' % self.A.ncons)
        lines.append('Spending profile: %s' % self.spendingProfile)
        if self.N_i == 2:
            lines.append('Surviving spouse spending needs: %s' % u.pc(self.chi, f=0))

        lines.append('Net yearly spending in year %d: %s' % (now, u.d(self.g_n[0] / self.yearFracLeft)))
        lines.append('Net spending remaining in year %d: %s' % (now, u.d(self.g_n[0])))
        lines.append('Net yearly spending profile basis in %d$: %s' % (now, u.d(self.g_n[0] / self.xi_n[0])))

        lines.append('Assumed heirs tax rate: %s' % u.pc(self.nu, f=0))

        lines.append('Spousal surplus deposit fraction: %s' % self.eta)
        if self.N_i == 2 and self.n_d < self.N_n:
            lines.append('Spousal beneficiary fractions to %s: %s' % (self.inames[self.i_s], self.phi_j.tolist()))
            p_j = self.partialEstate_j * (1 - self.phi_j)
            p_j[1] *= 1 - self.nu
            nx = self.n_d - 1
            totOthers = np.sum(p_j)
            totOthersNow = totOthers / self.gamma_n[nx + 1]
            q_j = self.partialEstate_j * self.phi_j
            totSpousal = np.sum(q_j)
            totSpousalNow = totSpousal / self.gamma_n[nx + 1]
            lines.append(
                'Spousal wealth transfer from %s to %s in year %d (nominal):'
                % (self.inames[self.i_d], self.inames[self.i_s], self.year_n[nx])
            )
            lines.append('    taxable: %s  tax-def: %s  tax-free: %s' % (u.d(q_j[0]), u.d(q_j[1]), u.d(q_j[2])))
            lines.append(
                'Sum of spousal bequests to %s in year %d in %d$: %s (%s nominal)'
                % (self.inames[self.i_s], self.year_n[nx], now, u.d(totSpousalNow), u.d(totSpousal))
            )
            lines.append(
                'Post-tax non-spousal bequests from %s in year %d (nominal):' % (self.inames[self.i_d], self.year_n[nx])
            )
            lines.append('    taxable: %s  tax-def: %s  tax-free: %s' % (u.d(p_j[0]), u.d(p_j[1]), u.d(p_j[2])))
            lines.append(
                'Sum of post-tax non-spousal bequests from %s in year %d in %d$: %s (%s nominal)'
                % (self.inames[self.i_d], self.year_n[nx], now, u.d(totOthersNow), u.d(totOthers))
            )

        totIncome = np.sum(self.g_n, axis=0)
        totIncomeNow = np.sum(self.g_n / self.gamma_n[:-1], axis=0)
        lines.append('Total net spending in %d$: %s (%s nominal)' % (now, u.d(totIncomeNow), u.d(totIncome)))

        totRoth = np.sum(self.x_in, axis=(0, 1))
        totRothNow = np.sum(np.sum(self.x_in, axis=0) / self.gamma_n[:-1], axis=0)
        lines.append('Total Roth conversions in %d$: %s (%s nominal)' % (now, u.d(totRothNow), u.d(totRoth)))

        taxPaid = np.sum(self.T_n, axis=0)
        taxPaidNow = np.sum(self.T_n / self.gamma_n[:-1], axis=0)
        lines.append('Total ordinary income tax paid in %d$: %s (%s nominal)' % (now, u.d(taxPaidNow), u.d(taxPaid)))

        taxPaid = np.sum(self.U_n, axis=0)
        taxPaidNow = np.sum(self.U_n / self.gamma_n[:-1], axis=0)
        lines.append('Total dividend tax paid in %d$: %s (%s nominal)' % (now, u.d(taxPaidNow), u.d(taxPaid)))

        taxPaid = np.sum(self.M_n, axis=0)
        taxPaidNow = np.sum(self.M_n / self.gamma_n[:-1], axis=0)
        lines.append('Total Medicare premiums paid in %d$: %s (%s nominal)' % (now, u.d(taxPaidNow), u.d(taxPaid)))

        estate = np.sum(self.b_ijn[:, :, self.N_n], axis=0)
        estate[1] *= 1 - self.nu
        lines.append('Post-tax account values at the end of final plan year %d: (nominal)' % self.year_n[-1])
        lines.append('    taxable: %s  tax-def: %s  tax-free: %s' % (u.d(estate[0]), u.d(estate[1]), u.d(estate[2])))

        totEstate = np.sum(estate)
        totEstateNow = totEstate / self.gamma_n[-1]
        lines.append(
            'Total estate value at the end of final plan year %d in %d$: %s (%s nominal)'
            % (self.year_n[-1], now, u.d(totEstateNow), u.d(totEstate))
        )
        lines.append(
            "Inflation factor from this year's start date to the end of plan final year: %.2f" % self.gamma_n[-1]
        )

        lines.append('Case executed on: %s' % self._timestamp)
        lines.append('------------------------------------------------------------------------')

        return lines

    def showRatesCorrelations(self, tag='', shareRange=False):
        """
        Plot correlations between various rates.

        A tag string can be set to add information to the title of the plot.
        """
        import seaborn as sbn
        import matplotlib.pyplot as plt

        if self.rateMethod in [None, 'fixed', 'average', 'conservative']:
            u.vprint('Warning: Cannot plot correlations for %s rate method.' % self.rateMethod)
            return None

        rateNames = [
            'S&P500 (incl. div.)',
            'Baa Corp. Bonds',
            '10-y T-Notes',
            'Inflation',
        ]

        df = pd.DataFrame()
        for k, name in enumerate(rateNames):
            data = 100 * self.tau_kn[k]
            df[name] = data

        g = sbn.PairGrid(df, diag_sharey=False, height=1.8, aspect=1)
        if shareRange:
            minval = df.min().min() - 5
            maxval = df.max().max() + 5
            g.set(xlim=(minval, maxval), ylim=(minval, maxval))
        g.map_upper(sbn.scatterplot)
        g.map_lower(sbn.kdeplot)
        # g.map_diag(sbn.kdeplot)
        g.map_diag(sbn.histplot, color='orange')

        # Put zero axes on off-diagonal plots.
        imod = len(rateNames) + 1
        for i, ax in enumerate(g.axes.flat):
            ax.axvline(x=0, color='grey', linewidth=1, linestyle=':')
            if i % imod != 0:
                ax.axhline(y=0, color='grey', linewidth=1, linestyle=':')
        #    ax.tick_params(axis='both', labelleft=True, labelbottom=True)

        # plt.subplots_adjust(wspace=0.3, hspace=0.3)

        title = self._name + '\n'
        title += 'Rates Correlations (N=%d) %s' % (self.N_n, self.rateMethod)
        if self.rateMethod in ['historical', 'histochastic']:
            title += ' (' + str(self.rateFrm) + '-' + str(self.rateTo) + ')'

        if tag != '':
            title += ' - ' + tag

        g.fig.suptitle(title, y=1.08)
        plt.show()

        return None

    def showRates(self, tag=''):
        """
        Plot rate values used over the time horizon.

        A tag string can be set to add information to the title of the plot.
        """
        import matplotlib.pyplot as plt
        import matplotlib.ticker as tk

        if self.rateMethod is None:
            u.vprint('Warning: Rate method must be selected before plotting.')
            return None

        fig, ax = plt.subplots(figsize=(6, 4))
        plt.grid(visible='both')
        title = self._name + '\nReturn & Inflation Rates (' + str(self.rateMethod)
        if self.rateMethod in ['historical', 'histochastic', 'average']:
            title += ' ' + str(self.rateFrm) + '-' + str(self.rateTo)
        title += ')'

        if tag != '':
            title += ' - ' + tag

        rateName = [
            'S&P500 (incl. div.)',
            'Baa Corp. Bonds',
            '10-y T-Notes',
            'Inflation',
        ]
        ltype = ['-', '-.', ':', '--']
        for k in range(self.N_k):
            if self.yearFracLeft == 1:
                data = 100 * self.tau_kn[k]
                years = self.year_n
            else:
                data = 100 * self.tau_kn[k, 1:]
                years = self.year_n[1:]

            label = rateName[k] + ' <' + '{:.1f}'.format(np.mean(data)) + ' +/- {:.1f}'.format(np.std(data)) + '%>'
            ax.plot(years, data, label=label, ls=ltype[k % self.N_k])

        ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
        ax.legend(loc='best', reverse=False, fontsize=8, framealpha=0.7)
        # ax.legend(loc='upper left')
        ax.set_title(title)
        ax.set_xlabel('year')
        ax.set_ylabel('%')

        plt.show()
        # return fig, ax
        return None

    def showProfile(self, tag=''):
        """
        Plot income profile over time.

        A tag string can be set to add information to the title of the plot.
        """
        title = self._name + '\nIncome Profile'
        if tag != '':
            title += ' - ' + tag

        # style = {'net': '-', 'target': ':'}
        style = {'profile': '-'}
        series = {'profile': self.xi_n}
        _lineIncomePlot(self.year_n, series, style, title, yformat='xi', show=True)

        return None

    @_checkCaseStatus
    def showNetSpending(self, tag='', value=None):
        """
        Plot net available spending and target over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        title = self._name + '\nNet Available Spending'
        if tag != '':
            title += ' - ' + tag

        style = {'net': '-', 'target': ':'}
        if value == 'nominal':
            series = {'net': self.g_n, 'target': (self.g_n[0] / self.xi_n[0]) * self.xiBar_n}
            yformat = 'k\\$ (nominal)'
        else:
            series = {
                'net': self.g_n / self.gamma_n[:-1],
                'target': (self.g_n[0] / self.xi_n[0]) * self.xi_n,
            }
            yformat = 'k\\$ (' + str(self.year_n[0]) + '\\$)'

        _lineIncomePlot(self.year_n, series, style, title, yformat, show=True)

        return None

    @_checkCaseStatus
    def showAssetDistribution(self, tag='', value=None):
        """
        Plot the distribution of each savings account in thousands of dollars
        during the simulation time. This function will generate three
        graphs, one for taxable accounts, one the tax-deferred accounts,
        and one for tax-free accounts.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        if value == 'nominal':
            yformat = 'k\\$ (nominal)'
            infladjust = 1
        else:
            yformat = 'k\\$ (' + str(self.year_n[0]) + '\\$)'
            infladjust = self.gamma_n

        years_n = np.array(self.year_n)
        years_n = np.append(years_n, [years_n[-1] + 1])
        y2stack = {}
        jDic = {'taxable': 0, 'tax-deferred': 1, 'tax-free': 2}
        kDic = {'stocks': 0, 'C bonds': 1, 'T notes': 2, 'common': 3}
        for jkey in jDic:
            stackNames = []
            for kkey in kDic:
                name = kkey + ' / ' + jkey
                stackNames.append(name)
                y2stack[name] = np.zeros((self.N_i, self.N_n + 1))
                for i in range(self.N_i):
                    y2stack[name][i][:] = self.b_ijkn[i][jDic[jkey]][kDic[kkey]][:] / infladjust

            title = self._name + '\nAssets Distribution - ' + jkey
            if tag != '':
                title += ' - ' + tag

            _stackPlot(
                years_n,
                self.inames,
                title,
                range(self.N_i),
                y2stack,
                stackNames,
                'upper left',
                yformat,
            )

        return None

    def showAllocations(self, tag=''):
        """
        Plot desired allocation of savings accounts in percentage
        over simulation time and interpolated by the selected method
        through the interpolateAR() method.

        A tag string can be set to add information to the title of the plot.
        """
        count = self.N_i
        if self.ARCoord == 'spouses':
            acList = [self.ARCoord]
            count = 1
        elif self.ARCoord == 'individual':
            acList = [self.ARCoord]
        elif self.ARCoord == 'account':
            acList = ['taxable', 'tax-deferred', 'tax-free']
        else:
            raise ValueError('Unknown coordination %s' % self.ARCoord)

        assetDic = {'stocks': 0, 'C bonds': 1, 'T notes': 2, 'common': 3}
        for i in range(count):
            y2stack = {}
            for acType in acList:
                stackNames = []
                for key in assetDic:
                    aname = key + ' / ' + acType
                    stackNames.append(aname)
                    y2stack[aname] = np.zeros((count, self.N_n))
                    y2stack[aname][i][:] = self.alpha_ijkn[i, acList.index(acType), assetDic[key], : self.N_n]

                    title = self._name + '\nAssets Allocations (%) - ' + acType
                    if self.ARCoord == 'spouses':
                        title += ' spouses'
                    else:
                        title += ' ' + self.inames[i]

                if tag != '':
                    title += ' - ' + tag

                _stackPlot(
                    self.year_n,
                    self.inames,
                    title,
                    [i],
                    y2stack,
                    stackNames,
                    'upper left',
                    'percent',
                )

        return None

    @_checkCaseStatus
    def showAccounts(self, tag='', value=None):
        """
        Plot values of savings accounts over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        title = self._name + '\nSavings Balance'
        if tag != '':
            title += ' - ' + tag

        stypes = self.savings_in.keys()
        # Add one year for estate.
        year_n = np.append(self.year_n, [self.year_n[-1] + 1])

        if value == 'nominal':
            yformat = 'k\\$ (nominal)'
            savings_in = self.savings_in
        else:
            yformat = 'k\\$ (' + str(self.year_n[0]) + '\\$)'
            savings_in = {}
            for key in self.savings_in:
                savings_in[key] = self.savings_in[key] / self.gamma_n

        _stackPlot(year_n, self.inames, title, range(self.N_i), savings_in, stypes, 'upper left', yformat)

        return None

    @_checkCaseStatus
    def showSources(self, tag='', value=None):
        """
        Plot income over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        title = self._name + '\nRaw Income Sources'
        stypes = self.sources_in.keys()

        if tag != '':
            title += ' - ' + tag

        if value == 'nominal':
            yformat = 'k\\$ (nominal)'
            sources_in = self.sources_in
        else:
            yformat = 'k\\$ (' + str(self.year_n[0]) + '\\$)'
            sources_in = {}
            for key in self.sources_in:
                sources_in[key] = self.sources_in[key] / self.gamma_n[:-1]

        _stackPlot(
            self.year_n,
            self.inames,
            title,
            range(self.N_i),
            sources_in,
            stypes,
            'upper left',
            yformat,
        )

        return None

    @_checkCaseStatus
    def _showFeff(self, tag=''):
        """
        Plot income tax paid over time.

        A tag string can be set to add information to the title of the plot.
        """
        title = self._name + '\nEff f '
        if tag != '':
            title += ' - ' + tag

        various = ['-', '--', '-.', ':']
        style = {}
        series = {}
        q = 0
        for t in range(self.N_t):
            key = 'f ' + str(t)
            series[key] = self.F_tn[t] / self.DeltaBar_tn[t]
            print(key, series[key])
            style[key] = various[q % len(various)]
            q += 1

        fig, ax = _lineIncomePlot(self.year_n, series, style, title, yformat='', show=True)

        return None

    @_checkCaseStatus
    def showTaxes(self, tag='', value=None):
        """
        Plot income tax paid over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        style = {'income taxes': '-', 'Medicare': '-.'}

        if value == 'nominal':
            series = {'income taxes': self.T_n, 'Medicare': self.M_n}
            yformat = 'k\\$ (nominal)'
        else:
            series = {
                'income taxes': self.T_n / self.gamma_n[:-1],
                'Medicare': self.M_n / self.gamma_n[:-1],
            }
            yformat = 'k\\$ (' + str(self.year_n[0]) + '\\$)'

        title = self._name + '\nIncome Tax'
        if tag != '':
            title += ' - ' + tag

        fig, ax = _lineIncomePlot(self.year_n, series, style, title, yformat, show=True)

        return None

    @_checkCaseStatus
    def showGrossIncome(self, tag='', value=None):
        """
        Plot income tax and taxable income over time horizon.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        import matplotlib.pyplot as plt

        value = self._checkValue(value)

        style = {'taxable income': '-'}

        if value == 'nominal':
            series = {'taxable income': self.G_n}
            yformat = 'k\\$ (nominal)'
            infladjust = self.gamma_n[:-1]
        else:
            series = {'taxable income': self.G_n / self.gamma_n[:-1]}
            yformat = 'k\\$ (' + str(self.year_n[0]) + '\\$)'
            infladjust = 1

        title = self._name + '\nTaxable Ordinary Income vs. Tax Brackets'
        if tag != '':
            title += ' - ' + tag

        fig, ax = _lineIncomePlot(self.year_n, series, style, title, yformat)

        data = tx.taxBrackets(self.N_i, self.n_d, self.N_n)
        for key in data:
            data_adj = data[key] * infladjust
            ax.plot(self.year_n, data_adj, label=key, ls=':')

        plt.grid(visible='both')
        ax.legend(loc='upper left', reverse=True, fontsize=8, framealpha=0.3)
        plt.show()

        return None

    @_checkCaseStatus
    def saveConfig(self, basename=None):
        """
        Save parameters in a configuration file.
        """
        if basename is None:
            basename = self._name

        config.saveConfig(self, basename)

        return None

    @_checkCaseStatus
    def saveWorkbook(self, overwrite=False, basename=None):
        """
        Save instance in an Excel spreadsheet.
        The first worksheet will contain income in the following
        fields in columns:
        - net spending
        - taxable ordinary income
        - taxable dividends
        - tax bills (federal only, including IRMAA)
        for all the years for the time span of the plan.

        The second worksheet contains the rates
        used for the plan as follows:
        - S&P 500
        - Corporate Baa bonds
        - Treasury notes (10y)
        - Inflation.

        The subsequent worksheets has the sources for each
        spouse as follows:
        - taxable account withdrawals
        - RMDs
        - distributions
        - Roth conversions
        - tax-free withdrawals
        - big-ticket items.

        The subsequent worksheets contains the balances
        and input/ouput to the savings accounts for each spouse:
        - taxable savings account
        - tax-deferred account
        - tax-free account.

        Last worksheet contains cash flow.
        """

        from openpyxl import Workbook
        from openpyxl.utils.dataframe import dataframe_to_rows

        if basename is None:
            basename = self._name

        wb = Workbook()

        # Income.
        ws = wb.active
        ws.title = 'Income'

        incomeDic = {
            'net spending': self.g_n,
            'taxable ord. income': self.G_n,
            'taxable dividends': self.Q_n,
            'Tax bills + Med.': self.T_n + self.U_n + self.M_n,
        }

        rawData = {}
        rawData['year'] = self.year_n
        for key in incomeDic:
            rawData[key] = incomeDic[key]

        # We need to work by row.
        df = pd.DataFrame(rawData)
        for row in dataframe_to_rows(df, index=False, header=True):
            ws.append(row)

        _formatSpreadsheet(ws, 'currency')

        # Cash flow.
        cashFlowDic = {
            'net spending': self.g_n,
            'all wages': np.sum(self.omega_in, axis=0),
            'all pensions': np.sum(self.pi_in, axis=0),
            'all soc sec': np.sum(self.zetaBar_in, axis=0),
            "all bti's": np.sum(self.Lambda_in, axis=0),
            'all wdrwls': np.sum(self.w_ijn, axis=(0, 1)),
            'all deposits': -np.sum(self.d_in, axis=0),
            'ord taxes': -self.T_n,
            'div taxes': -self.U_n,
            'Medicare': -self.M_n,
        }
        sname = 'Cash Flow'
        ws = wb.create_sheet(sname)
        rawData = {}
        rawData['year'] = self.year_n
        for key in cashFlowDic:
            rawData[key] = cashFlowDic[key]
        df = pd.DataFrame(rawData)
        for row in dataframe_to_rows(df, index=False, header=True):
            ws.append(row)

        _formatSpreadsheet(ws, 'currency')

        # Sources.
        srcDic = {
            'wages': 'wages',
            'social sec': 'ssec',
            'pension': 'pension',
            'txbl acc wdrwl': 'wdrwl taxable',
            'RMDs': 'rmd',
            '+distributions': 'dist',
            'Roth conversion': 'RothX',
            'tax-free wdrwl': 'wdrwl tax-free',
            'big-ticket items': 'bti',
        }

        for i in range(self.N_i):
            sname = self.inames[i] + "'s Sources"
            ws = wb.create_sheet(sname)
            rawData = {}
            rawData['year'] = self.year_n
            for key in srcDic:
                rawData[key] = self.sources_in[srcDic[key]][i]

            df = pd.DataFrame(rawData)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)

            _formatSpreadsheet(ws, 'currency')

        # Account balances except final year.
        accDic = {
            'taxable bal': self.b_ijn[:, 0, :-1],
            'taxable dep': self.d_in,
            'taxable wdrwl': self.w_ijn[:, 0, :],
            'tax-deferred bal': self.b_ijn[:, 1, :-1],
            'tax-deferred ctrb': self.kappa_ijn[:, 1, :],
            'tax-deferred wdrwl': self.w_ijn[:, 1, :],
            '(included RMDs)': self.rmd_in[:, :],
            'Roth conversion': self.x_in,
            'tax-free bal': self.b_ijn[:, 2, :-1],
            'tax-free ctrb': self.kappa_ijn[:, 2, :],
            'tax-free wdrwl': self.w_ijn[:, 2, :],
        }
        for i in range(self.N_i):
            sname = self.inames[i] + "'s Accounts"
            ws = wb.create_sheet(sname)
            rawData = {}
            rawData['year'] = self.year_n
            for key in accDic:
                rawData[key] = accDic[key][i]
            df = pd.DataFrame(rawData)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)
            lastRow = [
                self.year_n[-1] + 1,
                self.b_ijn[i][0][-1],
                0,
                0,
                self.b_ijn[i][1][-1],
                0,
                0,
                0,
                0,
                self.b_ijn[i][2][-1],
                0,
                0,
            ]
            ws.append(lastRow)

            _formatSpreadsheet(ws, 'currency')

        # Allocations.
        jDic = {'taxable': 0, 'tax-deferred': 1, 'tax-free': 2}
        kDic = {'stocks': 0, 'C bonds': 1, 'T notes': 2, 'common': 3}

        # Add one year for estate.
        year_n = np.append(self.year_n, [self.year_n[-1] + 1])
        for i in range(self.N_i):
            sname = self.inames[i] + "'s Allocations"
            ws = wb.create_sheet(sname)
            rawData = {}
            rawData['year'] = year_n
            for jkey in jDic:
                for kkey in kDic:
                    rawData[jkey + '/' + kkey] = self.alpha_ijkn[i, jDic[jkey], kDic[kkey], :]
            df = pd.DataFrame(rawData)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)

            _formatSpreadsheet(ws, 'percent1')

        # Rates on penultimate sheet.
        ws = wb.create_sheet('Rates')
        rawData = {}
        rawData['year'] = self.year_n
        ratesDic = {'S&P 500': 0, 'Corporate Baa': 1, 'T Bonds': 2, 'inflation': 3}

        for key in ratesDic:
            rawData[key] = self.tau_kn[ratesDic[key]]

        df = pd.DataFrame(rawData)
        for row in dataframe_to_rows(df, index=False, header=True):
            ws.append(row)

        _formatSpreadsheet(ws, 'percent2')

        # Summary on last sheet.
        ws = wb.create_sheet('Summary')
        rawData = {}
        rawData['SUMMARY ==========================================================================='] = (
            self._summaryList()[1:-1]
        )

        df = pd.DataFrame(rawData)
        for row in dataframe_to_rows(df, index=False, header=True):
            ws.append(row)

        _formatSpreadsheet(ws, 'summary')

        _saveWorkbook(wb, basename, overwrite)

        return None

    def saveWorkbookCSV(self, basename):
        """
        Function similar to saveWorkbook(), but saving information in csv format
        instead of an Excel worksheet.
        See saveWorkbook() sister function for more information.
        """

        planData = {}
        planData['year'] = self.year_n
        planData['net spending'] = self.g_n
        planData['taxable ord. income'] = self.G_n
        planData['taxable dividends'] = self.Q_n
        planData['tax bill'] = self.T_n

        for i in range(self.N_i):
            planData[self.inames[i] + ' txbl bal'] = self.b_ijn[i, 0, :-1]
            planData[self.inames[i] + ' txbl dep'] = self.d_in[i, :]
            planData[self.inames[i] + ' txbl wrdwl'] = self.w_ijn[i, 0, :]
            planData[self.inames[i] + ' tx-def bal'] = self.b_ijn[i, 1, :-1]
            planData[self.inames[i] + ' tx-def ctrb'] = self.kappa_ijn[i, 1, :]
            planData[self.inames[i] + ' tx-def wdrl'] = self.w_ijn[i, 1, :]
            planData[self.inames[i] + ' (RMD)'] = self.rmd_in[i, :]
            planData[self.inames[i] + ' Roth conversion'] = self.x_in[i, :]
            planData[self.inames[i] + ' tx-free bal'] = self.b_ijn[i, 2, :-1]
            planData[self.inames[i] + ' tx-free ctrb'] = self.kappa_ijn[i, 2, :]
            planData[self.inames[i] + ' tax-free wdrwl'] = self.w_ijn[i, 2, :]
            planData[self.inames[i] + ' big-ticket items'] = self.Lambda_in[i, :]

        ratesDic = {'S&P 500': 0, 'Corporate Baa': 1, 'T Bonds': 2, 'inflation': 3}
        for key in ratesDic:
            planData[key] = self.tau_kn[ratesDic[key]]

        df = pd.DataFrame(planData)

        while True:
            try:
                fname = 'worksheet' + '_' + basename + '.csv'
                df.to_csv(fname)
                break
            except PermissionError:
                print('Failed to save "%s": %s.' % (fname, 'Permission denied'))
                key = input('Close file and try again? [Yn] ')
                if key == 'n':
                    break
            except Exception as e:
                raise Exception('Unanticipated exception %r.' % e)

        return None


def _lineIncomePlot(x, series, style, title, yformat='k\\$', show=False):
    """
    Core line plotter function.
    """
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
    if 'k' in yformat:
        ax.get_yaxis().set_major_formatter(tk.FuncFormatter(lambda x, p: format(int(x / 1000), ',')))
        # Give range to y values in unindexed flat profiles.
        ymin, ymax = ax.get_ylim()
        if ymax - ymin < 5000:
            ax.set_ylim((ymin * 0.95, ymax * 1.05))

    if show:
        plt.show()

    return fig, ax


def _stackPlot(x, inames, title, irange, series, snames, location, yformat='k$'):
    """
    Core function for stacked plots.
    """
    import matplotlib.pyplot as plt
    import matplotlib.ticker as tk

    nonzeroSeries = {}
    for sname in snames:
        for i in irange:
            tmp = series[sname][i]
            if sum(tmp) > 1.0:
                nonzeroSeries[sname + ' ' + inames[i]] = tmp

    if len(nonzeroSeries) == 0:
        print('Nothing to plot for', title)
        return None

    fig, ax = plt.subplots(figsize=(6, 4))
    plt.grid(visible='both')

    ax.stackplot(x, nonzeroSeries.values(), labels=nonzeroSeries.keys(), alpha=0.6)
    ax.legend(loc=location, reverse=True, fontsize=8, ncol=2, framealpha=0.5)
    ax.set_title(title)
    ax.set_xlabel('year')
    ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
    if 'k' in yformat:
        ax.set_ylabel(yformat)
        ax.get_yaxis().set_major_formatter(tk.FuncFormatter(lambda x, p: format(int(x / 1000), ',')))
    elif yformat == 'percent':
        ax.set_ylabel('%')
        ax.get_yaxis().set_major_formatter(tk.FuncFormatter(lambda x, p: format(int(100 * x), ',')))
    else:
        raise RuntimeError('Unknown yformat: %s.' % yformat)

    plt.show()

    return fig, ax


def _saveWorkbook(wb, basename, overwrite=False):
    """
    Utility function to save XL workbook.
    """
    from os.path import isfile
    from pathlib import Path

    if Path(basename).suffixes == []:
        fname = 'workbook' + '_' + basename + '.xlsx'
    else:
        fname = basename

    if overwrite is False and isfile(fname):
        print('File "%s" already exists.' % fname)
        key = input('Overwrite? [Ny] ')
        if key != 'y':
            print('Skipping save and returning.')
            return None

    while True:
        try:
            u.vprint('Saving plan as "%s".' % fname)
            wb.save(fname)
            break
        except PermissionError:
            print('Failed to save "%s": %s.' % (fname, 'Permission denied'))
            key = input('Close file and try again? [Yn] ')
            if key == 'n':
                break
        except Exception as e:
            raise Exception('Unanticipated exception %r.' % e)

    return None


def _formatSpreadsheet(ws, ftype):
    """
    Utility function to beautify spreadsheet.
    """
    if ftype == 'currency':
        fstring = '$#,##0_);[Red]($#,##0)'
    elif ftype == 'percent2':
        fstring = '#.00%'
    elif ftype == 'percent1':
        fstring = '#.0%'
    elif ftype == 'percent0':
        fstring = '#0%'
    elif ftype == 'summary':
        for col in ws.columns:
            column = col[0].column_letter
            width = max(len(str(col[0].value)) + 20, 40)
            ws.column_dimensions[column].width = width
            return None
    else:
        raise RuntimeError('Unknown format: %s.' % ftype)

    for cell in ws[1] + ws['A']:
        cell.style = 'Pandas'
    for col in ws.columns:
        column = col[0].column_letter
        # col[0].style = 'Title'
        width = max(len(str(col[0].value)) + 4, 10)
        ws.column_dimensions[column].width = width
        if column != 'A':
            for cell in col:
                cell.number_format = fstring

    return None


def _streamPrinter(text):
    """
    Define a stream printer to grab output from MOSEK.
    """
    import sys

    if not u.verbose:
        return

    sys.stdout.write(text)
    sys.stdout.flush()
