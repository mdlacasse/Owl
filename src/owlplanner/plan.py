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
import matplotlib.pyplot as plt
from datetime import date, datetime
from functools import wraps
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import time
import io

from owlplanner import utils as u
from owlplanner import tax2025 as tx
from owlplanner import abcapi as abc
from owlplanner import rates
from owlplanner import config
from owlplanner import timelists
from owlplanner import logging
from owlplanner import progress


# This makes all graphs to have the same height.
plt.rcParams.update({'figure.autolayout': True})


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


def _genXi_n(profile, fraction, n_d, N_n, a, b, c):
    """
    Utility function to generate spending profile.
    Return time series of spending profile.
    Value is reduced to fraction starting in year n_d,
    after the passing of shortest-lived spouse.
    Series is unadjusted for inflation.
    """
    xi = np.ones(N_n)
    if profile == "flat":
        if n_d < N_n:
            xi[n_d:] *= fraction
    elif profile == "smile":
        span = N_n - 1 - c
        x = np.linspace(0, span, N_n - c)
        a /= 100
        b /= 100
        # Use a cosine +/- 15% combined with a gentle +12% linear increase.
        xi[c:] = xi[c:] + a * np.cos((2 * np.pi / span) * x) + (b / (N_n - 1)) * x
        xi[:c] = xi[c]
        # Normalize to be sum-neutral with respect to a flat profile.
        neutralSum = N_n
        # Reduce income needs after passing of one spouse.
        if n_d < N_n:
            neutralSum -= (1 - fraction) * (N_n - n_d)  # Account for flat spousal reduction.
            xi[n_d:] *= fraction
        xi *= neutralSum / xi.sum()
    else:
        raise ValueError(f"Unknown profile type {profile}.")

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


def clone(plan, newname=None, *, verbose=True, logstreams=None):
    """
    Return an almost identical copy of plan: only the name of the plan
    has been modified and appended the string '(copy)',
    unless a new name is provided as an argument.
    """
    import copy

    # Can't deepcopy variables containing file descriptors.
    mylogger = plan.logger()
    plan.setLogger(None)
    newplan = copy.deepcopy(plan)
    plan.setLogger(mylogger)

    if logstreams is None:
        newplan.setLogger(mylogger)
    else:
        newplan.setLogstreams(verbose, logstreams)

    if newname is None:
        newplan.rename(plan._name + " (copy)")
    else:
        newplan.rename(newname)

    return newplan


############################################################################


def _checkCaseStatus(func):
    """
    Decorator to check if problem was solved successfully and
    prevent method from running if not.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.caseStatus != "solved":
            self.mylog.vprint(f"Preventing to run method {func.__name__}() while case is {self.caseStatus}.")
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
            msg = f"You must define a spending profile before calling {func.__name__}()."
            self.mylog.vprint(msg)
            raise RuntimeError(msg)
        if self.alpha_ijkn is None:
            msg = f"You must define an allocation profile before calling {func.__name__}()."
            self.mylog.vprint(msg)
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
        self.mylog.vprint(f"CPU time used: {int(pt / 60)}m{pt % 60:.1f}s, Wall time: {int(rt / 60)}m{rt % 60:.1f}s.")
        return result

    return wrapper


class Plan(object):
    """
    This is the main class of the Owl Project.
    """

    def __init__(self, inames, yobs, expectancy, name, *, startDate=None, verbose=False, logstreams=None):
        """
        Constructor requires three lists: the first
        one contains the name(s) of the individual(s),
        the second one is the year of birth of each individual,
        and the third the life expectancy. Last argument is a name for
        the plan.
        """
        if name == "":
            raise ValueError("Plan must have a name")

        self._name = name
        self.setLogstreams(verbose, logstreams)

        # 7 tax brackets, 3 types of accounts, 4 classes of assets.
        self.N_t = 7
        self.N_j = 3
        self.N_k = 4
        # 2 binary variables.
        self.N_z = 2

        # Default interpolation parameters for allocation ratios.
        self.interpMethod = "linear"
        self._interpolator = self._linInterp
        self.interpCenter = 15
        self.interpWidth = 5

        self._description = ''
        self.defaultPlots = "nominal"
        self.defaultSolver = "HiGHS"

        self.N_i = len(yobs)
        assert 0 < self.N_i and self.N_i <= 2, f"Cannot support {self.N_i} individuals."
        assert self.N_i == len(expectancy), f"Expectancy must have {self.N_i} entries."
        assert self.N_i == len(inames), f"Names for individuals must have {self.N_i} entries."
        assert inames[0] != "" or (self.N_i == 2 and inames[1] == ""), "Name for each individual must be provided."

        self.filingStatus = ["single", "married"][self.N_i - 1]
        # Default year TCJA is speculated to expire.
        self.yTCJA = 2026
        self.inames = inames
        self.yobs = np.array(yobs, dtype=np.int32)
        self.expectancy = np.array(expectancy, dtype=np.int32)

        # Reference time is starting date in the current year and all passings are assumed at the end.
        thisyear = date.today().year
        self.horizons = self.yobs + self.expectancy - thisyear + 1
        # self.horizons = [yobs[i] + expectancy[i] - thisyear + 1 for i in range(self.N_i)]
        self.N_n = np.max(self.horizons)
        self.year_n = np.linspace(thisyear, thisyear + self.N_n - 1, self.N_n, dtype=np.int32)
        # Year in the plan (if any) where individuals turn 59. For 10% withdrawal penalty.
        self.n59 = 59 - thisyear + self.yobs
        self.n59[self.n59 < 0] = 0
        # Handle passing of one spouse before the other.
        if self.N_i == 2 and np.min(self.horizons) != np.max(self.horizons):
            self.n_d = np.min(self.horizons)
            self.i_d = np.argmax(self.horizons == self.n_d)
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
        self.smileDip = 15  # Percent to reduce smile profile
        self.smileIncrease = 12  # Percent to increse profile over time span

        # Default to zero pension and social security.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        self.pensionAmounts = np.zeros(self.N_i)
        self.pensionAges = 65 * np.ones(self.N_i, dtype=np.int32)
        self.pensionIsIndexed = [False, False]
        self.ssecAmounts = np.zeros(self.N_i)
        self.ssecAges = 67 * np.ones(self.N_i, dtype=np.int32)

        # Parameters from timeLists initialized to zero.
        self.omega_in = np.zeros((self.N_i, self.N_n))
        self.Lambda_in = np.zeros((self.N_i, self.N_n))
        self.myRothX_in = np.zeros((self.N_i, self.N_n))
        self.kappa_ijn = np.zeros((self.N_i, self.N_j, self.N_n))

        # Previous 3 years for Medicare.
        self.prevMAGI = np.zeros((3))

        # Default slack on profile.
        self.lambdha = 0

        # Scenario starts at the beginning of this year and ends at the end of the last year.
        s = ["", "s"][self.N_i - 1]
        self.mylog.vprint(f"Preparing scenario of {self.N_n} years for {self.N_i} individual{s}.")
        for i in range(self.N_i):
            endyear = thisyear + self.horizons[i] - 1
            self.mylog.vprint(f"{self.inames[i]:>14}: life horizon from {thisyear} -> {endyear}.")

        # Prepare RMD time series.
        self.rho_in = tx.rho_in(self.yobs, self.N_n)

        # If none was given, default is to begin plan on today's date.
        self._setStartingDate(startDate)

        self._buildOffsetMap()

        # Initialize guardrails to ensure proper configuration.
        self._adjustedParameters = False
        self.timeListsFileName = "None"
        self.timeLists = {}
        self.zeroContributions()
        self.caseStatus = "unsolved"
        self.rateMethod = None

        self.ARCoord = None
        self.objective = "unknown"

        # Placeholders to check if properly configured.
        self.xi_n = None
        self.alpha_ijkn = None

        return None

    def setLogger(self, logger):
        self.mylog = logger

    def setLogstreams(self, verbose, logstreams):
        self.mylog = logging.Logger(verbose, logstreams)
        # self.mylog.vprint(f"Setting logstreams to {logstreams}.")

    def logger(self):
        return self.mylog

    def setVerbose(self, state=True):
        """
        Control verbosity of calculations. True or False for now.
        Return previous state of verbosity.
        -``state``: Boolean selecting verbosity level.
        """
        return self.mylog.setVerbose(state)

    def _setStartingDate(self, mydate):
        """
        Set the date when the plan starts in the current year.
        This is for reproducibility purposes.
        String format of mydate is 'month/day'.
        """
        import calendar

        thisyear = date.today().year

        if isinstance(mydate, date):
            mydate = mydate.strftime("%Y-%m-%d")

        if mydate is None or mydate == "today":
            refdate = date.today()
            self.startDate = refdate.strftime("%Y-%m-%d")
        else:
            mydatelist = mydate.split("-")
            if len(mydatelist) == 2 or len(mydatelist) == 3:
                self.startDate = mydate
                # Ignore the year provided.
                refdate = date(thisyear, int(mydatelist[-2]), int(mydatelist[-1]))
            else:
                raise ValueError('Date must be "MM-DD" or "YYYY-MM-DD".')

        lp = calendar.isleap(thisyear)
        # Take midnight as the reference.
        self.yearFracLeft = 1 - (refdate.timetuple().tm_yday - 1) / (365 + lp)

        self.mylog.vprint(f"Setting 1st-year starting date to {self.startDate}.")

        return None

    def _checkValue(self, value):
        """
        Short utility function to parse and check arguments for plotting.
        """
        if value is None:
            return self.defaultPlots

        opts = ["nominal", "today"]
        if value in opts:
            return value

        raise ValueError(f"Value type must be one of: {opts}")

        return None

    def rename(self, newname):
        """
        Override name of the plan. Plan name is used
        to distinguish graph outputs and as base name for
        saving configurations and workbooks.
        """
        self.mylog.vprint(f"Renaming plan {self._name} -> {newname}.")
        self._name = newname

    def setDescription(self, description):
        """
        Set a text description of the plan.
        """
        self._description = description

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
        assert 0 <= eta and eta <= 1, "Fraction must be between 0 and 1."
        if self.N_i != 2:
            self.mylog.vprint("Deposit fraction can only be 0 for single individuals.")
            eta = 0
        else:
            self.mylog.vprint(f"Setting spousal surplus deposit fraction to {eta:.1f}.")
            self.mylog.vprint(f"\t{self.inames[0]}: {1-eta:.1f}, {self.inames[1]}: {eta:.1f}")
            self.eta = eta

    def setDefaultPlots(self, value):
        """
        Set plots between nominal values or today's $.
        """

        self.defaultPlots = self._checkValue(value)
        self.mylog.vprint(f"Setting plots default value to {value}.")

    def setDividendRate(self, mu):
        """
        Set dividend rate on equities. Rate is in percent. Default 2%.
        """
        assert 0 <= mu and mu <= 100, "Rate must be between 0 and 100."
        mu /= 100
        self.mylog.vprint(f"Dividend return rate on equities set to {u.pc(mu, f=1)}.")
        self.mu = mu
        self.caseStatus = "modified"

    def setExpirationYearTCJA(self, yTCJA):
        """
        Set year at which TCJA is speculated to expire.
        """
        self.mylog.vprint(f"Setting TCJA expiration year to {yTCJA}.")
        self.yTCJA = yTCJA
        self.caseStatus = "modified"
        self._adjustedParameters = False

    def setLongTermCapitalTaxRate(self, psi):
        """
        Set long-term income tax rate. Rate is in percent. Default 15%.
        """
        assert 0 <= psi and psi <= 100, "Rate must be between 0 and 100."
        psi /= 100
        self.mylog.vprint(f"Long-term capital gain income tax set to {u.pc(psi, f=0)}.")
        self.psi = psi
        self.caseStatus = "modified"

    def setBeneficiaryFractions(self, phi):
        """
        Set fractions of savings accounts that is left to surviving spouse.
        Default is [1, 1, 1] for taxable, tax-deferred, adn tax-exempt accounts.
        """
        assert len(phi) == self.N_j, f"Fractions must have {self.N_j} entries."
        for j in range(self.N_j):
            assert 0 <= phi[j] <= 1, "Fractions must be between 0 and 1."

        self.phi_j = np.array(phi, dtype=np.float32)
        self.mylog.vprint("Spousal beneficiary fractions set to",
                          ["{:.2f}".format(self.phi_j[j]) for j in range(self.N_j)])
        self.caseStatus = "modified"

        if np.any(self.phi_j != 1):
            self.mylog.vprint("Consider changing spousal deposit fraction for better convergence.")
            self.mylog.vprint(f"\tRecommended: setSpousalDepositFraction({self.i_d}.)")

    def setHeirsTaxRate(self, nu):
        """
        Set the heirs tax rate on the tax-deferred portion of the estate.
        Rate is in percent. Default is 30%.
        """
        assert 0 <= nu and nu <= 100, "Rate must be between 0 and 100."
        nu /= 100
        self.mylog.vprint(f"Heirs tax rate on tax-deferred portion of estate set to {u.pc(nu, f=0)}.")
        self.nu = nu
        self.caseStatus = "modified"

    def setPension(self, amounts, ages, indexed=[False, False], units="k"):
        """
        Set value of pension for each individual and commencement age.
        Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
        """
        assert len(amounts) == self.N_i, f"Amounts must have {self.N_i} entries."
        assert len(ages) == self.N_i, f"Ages must have {self.N_i} entries."
        assert len(indexed) >= self.N_i, f"Indexed list must have at least {self.N_i} entries."

        fac = u.getUnits(units)
        amounts = u.rescale(amounts, fac)

        self.mylog.vprint("Setting pension of", [u.d(amounts[i]) for i in range(self.N_i)],
                          "at age(s)", [int(ages[i]) for i in range(self.N_i)])

        thisyear = date.today().year
        # Use zero array freshly initialized.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            if amounts[i] != 0:
                ns = max(0, self.yobs[i] + ages[i] - thisyear)
                nd = self.horizons[i]
                self.pi_in[i, ns:nd] = amounts[i]
                # Only include remaining part of current year.
                if ns == 0:
                    self.pi_in[i, 0] *= self.yearFracLeft

        self.pensionAmounts = np.array(amounts)
        self.pensionAges = np.array(ages, dtype=np.int32)
        self.pensionIsIndexed = indexed
        self.caseStatus = "modified"
        self._adjustedParameters = False

    def setSocialSecurity(self, amounts, ages, units="k"):
        """
        Set value of social security for each individual and commencement age.
        Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
        """
        assert len(amounts) == self.N_i, f"Amounts must have {self.N_i} entries."
        assert len(ages) == self.N_i, f"Ages must have {self.N_i} entries."

        fac = u.getUnits(units)
        amounts = u.rescale(amounts, fac)

        self.mylog.vprint(
            "Setting social security benefits of", [u.d(amounts[i]) for i in range(self.N_i)],
            "at age(s)", [int(ages[i]) for i in range(self.N_i)],
        )

        thisyear = date.today().year
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            ns = max(0, self.yobs[i] + ages[i] - thisyear)
            nd = self.horizons[i]
            self.zeta_in[i, ns:nd] = amounts[i]
            # Only include remaining part of current year.
            if ns == 0:
                self.zeta_in[i, 0] *= self.yearFracLeft

        if self.N_i == 2:
            # Approximate calculation for spousal benefit (only valid at FRA).
            self.zeta_in[self.i_s, self.n_d :] = max(amounts[self.i_s], amounts[self.i_d])

        self.ssecAmounts = np.array(amounts)
        self.ssecAges = np.array(ages, dtype=np.int32)
        self.caseStatus = "modified"
        self._adjustedParameters = False

    def setSpendingProfile(self, profile, percent=60, dip=15, increase=12, delay=0):
        """
        Generate time series for spending profile. Surviving spouse fraction can be specified
        as a second argument. Default value is 60%.
        Dip and increase are percent changes in the smile profile.
        """
        assert 0 <= percent and percent <= 100, f"Survivor value {percent} outside range."
        assert 0 <= dip and dip <= 100, f"Dip value {dip} outside range."
        assert -100 <= increase and increase <= 100, f"Increase value {increase} outside range."
        assert 0 <= delay and delay <= self.N_n - 2, f"Delay value {delay} outside year range."

        self.chi = percent / 100

        self.mylog.vprint("Setting", profile, "spending profile.")
        if self.N_i == 2:
            self.mylog.vprint("Securing", u.pc(self.chi, f=0), "of spending amount for surviving spouse.")

        self.xi_n = _genXi_n(profile, self.chi, self.n_d, self.N_n, dip, increase, delay)
        # Account for time elapsed in the current year.
        self.xi_n[0] *= self.yearFracLeft

        self.spendingProfile = profile
        self.smileDip = dip
        self.smileIncrease = increase
        self.smileDelay = delay
        self.caseStatus = "modified"

    def setRates(self, method, frm=None, to=None, values=None, stdev=None, corr=None):
        """
        Generate rates for return and inflation based on the method and
        years selected. Note that last bound is included.

        The following methods are available:
        default, user, realistic, conservative, historical average, stochastic,
        histochastic, and historical.

        - For 'user', fixed rate values must be provided.
        - For 'stochastic', means, stdev, and optional correlation matrix must be provided.
        - For 'historical average', 'histochastic', and 'historical', a starting year
          must be provided, and optionally an ending year.

        Valid year range is from 1928 to last year.
        """
        if frm is not None and to is None:
            to = frm + self.N_n - 1  # 'to' is inclusive.

        dr = rates.Rates(self.mylog)
        self.rateValues, self.rateStdev, self.rateCorr = dr.setMethod(method, frm, to, values, stdev, corr)
        self.rateMethod = method
        self.rateFrm = frm
        self.rateTo = to
        self.tau_kn = dr.genSeries(self.N_n).transpose()
        self.mylog.vprint(f"Generating rate series of {len(self.tau_kn[0])} years using {method} method.")

        # Account for how late we are now in the first year and reduce rate accordingly.
        self.tau_kn[:, 0] *= self.yearFracLeft

        # Once rates are selected, (re)build cumulative inflation multipliers.
        self.gamma_n = _genGamma_n(self.tau_kn)
        self._adjustedParameters = False
        self.caseStatus = "modified"

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
            raise RuntimeError("A rate method needs to be first selected using setRates(...).")

        thisyear = date.today().year
        assert year > thisyear, "Internal error in forwardValue()."
        span = year - thisyear

        return amount * self.gamma_n[span]

    def setAccountBalances(self, *, taxable, taxDeferred, taxFree, units="k"):
        """
        Three lists containing the balance of all assets in each category for
        each spouse.  For single individuals, these lists will contain only
        one entry. Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
        """
        plurals = ["", "y", "ies"][self.N_i]
        assert len(taxable) == self.N_i, f"taxable must have {self.N_i} entr{plurals}."
        assert len(taxDeferred) == self.N_i, f"taxDeferred must have {self.N_i} entr{plurals}."
        assert len(taxFree) == self.N_i, f"taxFree must have {self.N_i} entr{plurals}."

        fac = u.getUnits(units)
        taxable = u.rescale(taxable, fac)
        taxDeferred = u.rescale(taxDeferred, fac)
        taxFree = u.rescale(taxFree, fac)

        self.b_ji = np.zeros((self.N_j, self.N_i))
        self.b_ji[0][:] = taxable
        self.b_ji[1][:] = taxDeferred
        self.b_ji[2][:] = taxFree
        self.beta_ij = self.b_ji.transpose()
        self.caseStatus = "modified"

        self.mylog.vprint("Taxable balances:", *[u.d(taxable[i]) for i in range(self.N_i)])
        self.mylog.vprint("Tax-deferred balances:", *[u.d(taxDeferred[i]) for i in range(self.N_i)])
        self.mylog.vprint("Tax-free balances:", *[u.d(taxFree[i]) for i in range(self.N_i)])
        self.mylog.vprint("Sum of all savings accounts:", u.d(np.sum(taxable) + np.sum(taxDeferred) + np.sum(taxFree)))
        self.mylog.vprint(
            "Post-tax total wealth of approximately",
            u.d(np.sum(taxable) + 0.7 * np.sum(taxDeferred) + np.sum(taxFree)),
        )

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
        if method == "linear":
            self._interpolator = self._linInterp
        elif method == "s-curve":
            self._interpolator = self._tanhInterp
            self.interpCenter = center
            self.interpWidth = width
        else:
            raise ValueError(f"Method {method} not supported.")

        self.interpMethod = method
        self.caseStatus = "modified"

        self.mylog.vprint(f"Asset allocation interpolation method set to {method}.")

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
        if allocType == "account":
            # Make sure we have proper input.
            for item in [taxable, taxDeferred, taxFree]:
                assert len(item) == self.N_i, f"{item} must have one entry per individual."
                for i in range(self.N_i):
                    # Initial and final.
                    assert len(item[i]) == 2, f"{item}[{i}] must have 2 lists (initial and final)."
                    for z in range(2):
                        assert len(item[i][z]) == self.N_k, f"{item}[{i}][{z}] must have {self.N_k} entries."
                        assert abs(sum(item[i][z]) - 100) < 0.01, "Sum of percentages must add to 100."

            for i in range(self.N_i):
                self.mylog.vprint(f"{self.inames[i]}: Setting gliding allocation ratios (%) to {allocType}.")
                self.mylog.vprint(f"      taxable: {taxable[i][0]} -> {taxable[i][1]}")
                self.mylog.vprint(f"  taxDeferred: {taxDeferred[i][0]} -> {taxDeferred[i][1]}")
                self.mylog.vprint(f"      taxFree: {taxFree[i][0]} -> {taxFree[i][1]}")

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

            self.boundsAR["taxable"] = taxable
            self.boundsAR["tax-deferred"] = taxDeferred
            self.boundsAR["tax-free"] = taxFree

        elif allocType == "individual":
            assert len(generic) == self.N_i, "generic must have one list per individual."
            for i in range(self.N_i):
                # Initial and final.
                assert len(generic[i]) == 2, f"generic[{i}] must have 2 lists (initial and final)."
                for z in range(2):
                    assert len(generic[i][z]) == self.N_k, f"generic[{i}][{z}] must have {self.N_k} entries."
                    assert abs(sum(generic[i][z]) - 100) < 0.01, "Sum of percentages must add to 100."

            for i in range(self.N_i):
                self.mylog.vprint(f"{self.inames[i]}: Setting gliding allocation ratios (%) to {allocType}.")
                self.mylog.vprint(f"\t{generic[i][0]} -> {generic[i][1]}")

            for i in range(self.N_i):
                Nin = self.horizons[i] + 1
                for k in range(self.N_k):
                    start = generic[i][0][k] / 100
                    end = generic[i][1][k] / 100
                    dat = self._interpolator(start, end, Nin)
                    for j in range(self.N_j):
                        self.alpha_ijkn[i, j, k, :Nin] = dat[:]

            self.boundsAR["generic"] = generic

        elif allocType == "spouses":
            assert len(generic) == 2, "generic must have 2 entries (initial and final)."
            for z in range(2):
                assert len(generic[z]) == self.N_k, f"generic[{z}] must have {self.N_k} entries."
                assert abs(sum(generic[z]) - 100) < 0.01, "Sum of percentages must add to 100."

            self.mylog.vprint(f"Setting gliding allocation ratios (%) to {allocType}.")
            self.mylog.vprint(f"\t{generic[0]} -> {generic[1]}")

            # Use longest-lived spouse for both time scales.
            Nxn = max(self.horizons) + 1

            for k in range(self.N_k):
                start = generic[0][k] / 100
                end = generic[1][k] / 100
                dat = self._interpolator(start, end, Nxn)
                for i in range(self.N_i):
                    for j in range(self.N_j):
                        self.alpha_ijkn[i, j, k, :Nxn] = dat[:]

            self.boundsAR["generic"] = generic

        self.ARCoord = allocType
        self.caseStatus = "modified"

        self.mylog.vprint(f"Interpolating assets allocation ratios using {self.interpMethod} method.")

    def readContributions(self, filename):
        """
        Provide the name of the file containing the financial events
        over the anticipated life span determined by the
        assumed longevity. File can be an excel, or odt file with one
        tab named after each spouse and must have the following
        column headers:

                'year',
                'anticipated wages',
                'taxable ctrb',
                '401k ctrb',
                'Roth 401k ctrb',
                'IRA ctrb',
                'Roth IRA ctrb',
                'Roth conv',
                'big-ticket items'

        in any order. A template is provided as an example.
        Missing rows (years) are populated with zero values.
        """
        try:
            filename, self.timeLists = timelists.read(filename, self.inames, self.horizons, self.mylog)
        except Exception as e:
            raise Exception(f"Unsuccessful read of contributions: {e}")
            return False

        self.timeListsFileName = filename
        self.setContributions()

        return True

    def setContributions(self, timeLists=None):
        if timeLists is not None:
            timelists.check(timeLists, self.inames, self.horizons)
            self.timeLists = timeLists

        # Now fill in parameters which are in $.
        for i, iname in enumerate(self.inames):
            h = self.horizons[i]
            self.omega_in[i, :h] = self.timeLists[iname]["anticipated wages"].iloc[:h]
            self.kappa_ijn[i, 0, :h] = self.timeLists[iname]["taxable ctrb"].iloc[:h]
            self.kappa_ijn[i, 1, :h] = self.timeLists[iname]["401k ctrb"].iloc[:h]
            self.kappa_ijn[i, 2, :h] = self.timeLists[iname]["Roth 401k ctrb"].iloc[:h]
            self.kappa_ijn[i, 1, :h] += self.timeLists[iname]["IRA ctrb"].iloc[:h]
            self.kappa_ijn[i, 2, :h] += self.timeLists[iname]["Roth IRA ctrb"].iloc[:h]
            self.myRothX_in[i, :h] = self.timeLists[iname]["Roth conv"].iloc[:h]
            self.Lambda_in[i, :h] = self.timeLists[iname]["big-ticket items"].iloc[:h]

        #  In 1st year, reduce wages and contributions depending on starting date.
        self.omega_in[:, 0] *= self.yearFracLeft
        self.kappa_ijn[:, :, 0] *= self.yearFracLeft

        self.caseStatus = "modified"

        return self.timeLists

    def saveContributions(self):
        """
        Return workbook on wages and contributions.
        """
        if self.timeLists is None:
            return None

        self.mylog.vprint("Preparing wages and contributions workbook.")

        def fillsheet(sheet, i):
            sheet.title = self.inames[i]
            df = self.timeLists[self.inames[i]]
            for row in dataframe_to_rows(df, index=False, header=True):
                sheet.append(row)
            _formatSpreadsheet(sheet, "currency")

        wb = Workbook()
        ws = wb.active
        fillsheet(ws, 0)

        if self.N_i == 2:
            ws = wb.create_sheet(self.inames[1])
            fillsheet(ws, 1)

        return wb

    def zeroContributions(self):
        """
        Reset all contributions variables to zero.
        """
        self.mylog.vprint("Resetting wages and contributions to zero.")

        # Reset parameters with zeros.
        self.omega_in[:, :] = 0.0
        self.Lambda_in[:, :] = 0.0
        self.myRothX_in[:, :] = 0.0
        self.kappa_ijn[:, :, :] = 0.0

        cols = [
            "year",
            "anticipated wages",
            "taxable ctrb",
            "401k ctrb",
            "Roth 401k ctrb",
            "IRA ctrb",
            "Roth IRA ctrb",
            "Roth conv",
            "big-ticket items",
        ]
        for i, iname in enumerate(self.inames):
            h = self.horizons[i]
            df = pd.DataFrame(0, index=np.arange(h), columns=cols)
            df["year"] = self.year_n[:h]
            self.timeLists[iname] = df

        self.caseStatus = "modified"

        return self.timeLists

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
        w = self.interpWidth + 0.0001  # Avoid division by zero.
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
            raise RuntimeError("A rate method needs to be first selected using setRates(...).")

        if not self._adjustedParameters:
            self.mylog.vprint("Adjusting parameters for inflation.")
            self.sigma_n, self.theta_tn, self.Delta_tn = tx.taxParams(self.yobs, self.i_d, self.n_d,
                                                                      self.N_n, self.yTCJA)
            self.sigmaBar_n = self.sigma_n * self.gamma_n[:-1]
            self.DeltaBar_tn = self.Delta_tn * self.gamma_n[:-1]
            self.zetaBar_in = self.zeta_in * self.gamma_n[:-1]
            self.xiBar_n = self.xi_n * self.gamma_n[:-1]
            self.piBar_in = np.array(self.pi_in)
            for i in range(self.N_i):
                if self.pensionIsIndexed[i]:
                    self.piBar_in[i] *= self.gamma_n[:-1]

            self._adjustedParameters = True

        return None

    def _buildOffsetMap(self):
        """
        Utility function to map variables to a block vector.
        Refer to companion document for explanations.
        """
        # Stack all variables in a single block vector with all binary variables at the end.
        C = {}
        C["b"] = 0
        C["d"] = _qC(C["b"], self.N_i, self.N_j, self.N_n + 1)
        C["e"] = _qC(C["d"], self.N_i, self.N_n)
        C["F"] = _qC(C["e"], self.N_n)
        C["g"] = _qC(C["F"], self.N_t, self.N_n)
        C["s"] = _qC(C["g"], self.N_n)
        C["w"] = _qC(C["s"], self.N_n)
        C["x"] = _qC(C["w"], self.N_i, self.N_j, self.N_n)
        C["z"] = _qC(C["x"], self.N_i, self.N_n)
        self.nvars = _qC(C["z"], self.N_i, self.N_n, self.N_z)
        self.nbins = self.nvars - C["z"]
        # # self.nvars = _qC(C["x"], self.N_i, self.N_n)
        # # self.nbins = 0

        self.C = C
        self.mylog.vprint(
            f"Problem has {len(C)} distinct series, {self.nvars} decision variables (including {self.nbins} binary).")

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

        Cb = self.C["b"]
        Cd = self.C["d"]
        Ce = self.C["e"]
        CF = self.C["F"]
        Cg = self.C["g"]
        Cs = self.C["s"]
        Cw = self.C["w"]
        Cx = self.C["x"]
        Cz = self.C["z"]

        spLo = 1 - self.lambdha
        spHi = 1 + self.lambdha

        oppCostX = options.get("oppCostX", 0.)
        xnet = 1 - oppCostX/100.

        tau_ijn = np.zeros((Ni, Nj, Nn))
        for i in range(Ni):
            for j in range(Nj):
                for n in range(Nn):
                    tau_ijn[i, j, n] = np.sum(self.alpha_ijkn[i, j, :, n] * self.tau_kn[:, n], axis=0)

        # Weights are normalized on k: sum_k[alpha*(1 + tau)] = 1 + sum_k(alpha*tau).
        Tau1_ijn = 1 + tau_ijn
        Tauh_ijn = 1 + tau_ijn / 2

        units = u.getUnits(options.get("units", "k"))
        # No units for bigM.
        bigM = options.get("bigM", 5e6)
        assert isinstance(bigM, (int, float)), f"bigM {bigM} is not a number."

        ###################################################################
        # Inequality constraint matrix with upper and lower bound vectors.
        A = abc.ConstraintMatrix(self.nvars)
        B = abc.Bounds(self.nvars, self.nbins)

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
                B.setRange(_q2(CF, t, n, Nt, Nn), zero, self.DeltaBar_tn[t, n])

        # Standard exemption range inequalities.
        for n in range(Nn):
            B.setRange(_q1(Ce, n, Nn), zero, self.sigmaBar_n[n])

        # Start with no activities after passing.
        for i in range(Ni):
            for n in range(self.horizons[i], Nn):
                B.setRange(_q2(Cd, i, n, Ni, Nn), zero, zero)
                B.setRange(_q2(Cx, i, n, Ni, Nn), zero, zero)
                for j in range(Nj):
                    B.setRange(_q3(Cw, i, j, n, Ni, Nj, Nn), zero, zero)

        # Roth conversions equalities/inequalities.
        # This condition supercedes everything else.
        if "maxRothConversion" in options and options["maxRothConversion"] == "file":
            # self.mylog.vprint(f"Fixing Roth conversions to those from file {self.timeListsFileName}.")
            for i in range(Ni):
                for n in range(self.horizons[i]):
                    rhs = self.myRothX_in[i][n]
                    B.setRange(_q2(Cx, i, n, Ni, Nn), rhs, rhs)
        else:
            if "maxRothConversion" in options:
                rhsopt = options["maxRothConversion"]
                assert isinstance(rhsopt, (int, float)), "Specified maxRothConversion is not a number."
                rhsopt *= units
                if rhsopt < 0:
                    # self.mylog.vprint('Unlimited Roth conversions (<0)')
                    pass
                else:
                    # self.mylog.vprint('Limiting Roth conversions to:', u.d(rhsopt))
                    for i in range(Ni):
                        for n in range(self.horizons[i]):
                            # MOSEK chokes if completely zero. Add a 1 cent slack.
                            # Should we adjust Roth conversion cap with inflation?
                            B.setRange(_q2(Cx, i, n, Ni, Nn), zero, rhsopt + 0.01)

            # Process startRothConversions option.
            if "startRothConversions" in options:
                rhsopt = options["startRothConversions"]
                assert isinstance(rhsopt, (int, float)), "Specified startRothConversions is not a number."
                thisyear = date.today().year
                yearn = max(rhsopt - thisyear, 0)

                for i in range(Ni):
                    nstart = min(yearn, self.horizons[i])
                    for n in range(0, nstart):
                        B.setRange(_q2(Cx, i, n, Ni, Nn), zero, zero)

            # Process noRothConversions option. Also valid when N_i == 1, why not?
            if "noRothConversions" in options and options["noRothConversions"] != "None":
                rhsopt = options["noRothConversions"]
                try:
                    i_x = self.inames.index(rhsopt)
                except ValueError:
                    raise ValueError(f"Unknown individual {rhsopt} for noRothConversions:")

                for n in range(Nn):
                    B.setRange(_q2(Cx, i_x, n, Ni, Nn), zero, zero)

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
        if objective == "maxSpending":
            # Impose optional constraint on final bequest requested in today's $.
            if "bequest" in options:
                bequest = options["bequest"]
                assert isinstance(bequest, (int, float)), "Desired bequest is not a number."
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
            # self.mylog.vprint('Adding bequest constraint of:', u.d(bequest))
        elif objective == "maxBequest":
            spending = options["netSpending"]
            assert isinstance(spending, (int, float)), "Desired spending provided is not a number."
            # Account for time elapsed in the current year.
            spending *= units * self.yearFracLeft
            # self.mylog.vprint('Maximizing bequest with desired net spending of:', u.d(spending))
            # To allow slack in first year, Cg can be made Nn+1 and store basis in g[Nn].
            # A.addNewRow({_q1(Cg, 0, Nn): 1}, spending, spending)
            B.setRange(_q1(Cg, 0, Nn), spending, spending)

        # Set initial balances through bounds or constraints.
        for i in range(Ni):
            for j in range(Nj):
                rhs = self.beta_ij[i, j]
                # A.addNewRow({_q3(Cb, i, j, 0, Ni, Nj, Nn + 1): 1}, rhs, rhs)
                B.setRange(_q3(Cb, i, j, 0, Ni, Nj, Nn + 1), rhs, rhs)

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
        B.setRange(_q1(Cs, Nn - 1, Nn), zero, zero)

        if Ni == 2:
            # No conversion during last year.
            # B.setRange(_q2(Cx, i_d, nd-1, Ni, Nn), zero, zero)
            # B.setRange(_q2(Cx, i_s, Nn-1, Ni, Nn), zero, zero)

            # No withdrawals or deposits for any i_d-owned accounts after year of passing.
            # Implicit n_d < Nn imposed by for loop.
            for n in range(n_d, Nn):
                B.setRange(_q2(Cd, i_d, n, Ni, Nn), zero, zero)
                B.setRange(_q2(Cx, i_d, n, Ni, Nn), zero, zero)
                for j in range(Nj):
                    B.setRange(_q3(Cw, i_d, j, n, Ni, Nj, Nn), zero, zero)

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
                        -fac1 * (xnet*u.krond(j, 2) - u.krond(j, 1)) * Tau1_ijn[i, j, n],
                    )

                    if Ni == 2 and n_d < Nn and i == i_s and n == n_d - 1:
                        fac2 = self.phi_j[j]
                        rhs += fac2 * self.kappa_ijn[i_d, j, n] * Tauh_ijn[i_d, j, n]
                        row.addElem(_q3(Cb, i_d, j, n, Ni, Nj, Nn + 1), -fac2 * Tau1_ijn[i_d, j, n])
                        row.addElem(_q3(Cw, i_d, j, n, Ni, Nj, Nn), fac2 * Tau1_ijn[i_d, j, n])
                        row.addElem(_q2(Cd, i_d, n, Ni, Nn), -fac2 * u.krond(j, 0) * Tau1_ijn[i_d, 0, n])
                        row.addElem(
                            _q2(Cx, i_d, n, Ni, Nn),
                            -fac2 * (xnet*u.krond(j, 2) - u.krond(j, 1)) * Tau1_ijn[i_d, j, n],
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
                    + self.piBar_in[i, n]
                    + self.Lambda_in[i, n]
                    - 0.5 * fac * self.mu * self.kappa_ijn[i, 0, n]
                )

                row.addElem(_q3(Cb, i, 0, n, Ni, Nj, Nn + 1), fac * self.mu)
                # Minus capital gains on taxable withdrawals using last year's rate if >=0.
                # Plus taxable account withdrawals, and all other withdrawals.
                row.addElem(_q3(Cw, i, 0, n, Ni, Nj, Nn), fac * (tau_0prev[n] - self.mu) - 1)
                penalty = 0.1 if n < self.n59[i] else 0
                row.addElem(_q3(Cw, i, 1, n, Ni, Nj, Nn), -1 + penalty)
                row.addElem(_q3(Cw, i, 2, n, Ni, Nj, Nn), -1 + penalty)
                row.addElem(_q2(Cd, i, n, Ni, Nn), fac * self.mu)

            # Minus tax on ordinary income, T_n.
            for t in range(Nt):
                row.addElem(_q2(CF, t, n, Nt, Nn), self.theta_tn[t, n])

            A.addRow(row, rhs, rhs)

        # Impose income profile.
        for n in range(1, Nn):
            rowDic = {_q1(Cg, 0, Nn): spLo * self.xiBar_n[n], _q1(Cg, n, Nn): -self.xiBar_n[0]}
            A.addNewRow(rowDic, -inf, zero)
            rowDic = {_q1(Cg, 0, Nn): spHi * self.xiBar_n[n], _q1(Cg, n, Nn): -self.xiBar_n[0]}
            A.addNewRow(rowDic, zero, inf)

        # Taxable ordinary income.
        for n in range(Nn):
            rhs = 0
            row = A.newRow()
            row.addElem(_q1(Ce, n, Nn), 1)
            for i in range(Ni):
                rhs += self.omega_in[i, n] + 0.85 * self.zetaBar_in[i, n] + self.piBar_in[i, n]
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
                # for z in range(Nz):
                #     B.setBinary(_q3(Cz, i, n, z, Ni, Nn, Nz))

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

            for n in range(self.horizons[i], Nn):
                B.setRange(_q3(Cz, i, n, 0, Ni, Nn, Nz), zero, zero)
                B.setRange(_q3(Cz, i, n, 1, Ni, Nn, Nz), zero, zero)

        # Now build a solver-neutral objective vector.
        c = abc.Objective(self.nvars)
        if objective == "maxSpending":
            # c.setElem(_q1(Cg, 0, Nn), -1) # Only OK in implemention without slack.
            for n in range(Nn):
                c.setElem(_q1(Cg, n, Nn), -1/self.gamma_n[n])
        elif objective == "maxBequest":
            for i in range(Ni):
                c.setElem(_q3(Cb, i, 0, Nn, Ni, Nj, Nn + 1), -1)
                c.setElem(_q3(Cb, i, 1, Nn, Ni, Nj, Nn + 1), -(1 - self.nu))
                c.setElem(_q3(Cb, i, 2, Nn, Ni, Nj, Nn + 1), -1)
        else:
            raise RuntimeError("Internal error in objective function.")

        self.A = A
        self.B = B
        self.c = c

        return None

    @_timer
    def runHistoricalRange(self, objective, options, ystart, yend, *, verbose=False, figure=False, progcall=None):
        """
        Run historical scenarios on plan over a range of years.
        """
        if yend + self.N_n > self.year_n[0]:
            yend = self.year_n[0] - self.N_n - 1
            self.mylog.vprint(f"Warning: Upper bound for year range re-adjusted to {yend}.")
        N = yend - ystart + 1

        self.mylog.vprint(f"Running historical range from {ystart} to {yend}.")

        self.mylog.setVerbose(verbose)

        if objective == "maxSpending":
            columns = ["partial", objective]
        elif objective == "maxBequest":
            columns = ["partial", "final"]
        else:
            self.mylog.print(f"Invalid objective {objective}.")
            return None

        df = pd.DataFrame(columns=columns)

        if progcall is None:
            progcall = progress.Progress(self.mylog)

        if not verbose:
            progcall.start()

        for year in range(ystart, yend + 1):
            self.setRates("historical", year)
            self.solve(objective, options)
            if not verbose:
                progcall.show((year - ystart + 1) / N)
            if self.caseStatus == "solved":
                if objective == "maxSpending":
                    df.loc[len(df)] = [self.partialBequest, self.basis]
                elif objective == "maxBequest":
                    df.loc[len(df)] = [self.partialBequest, self.bequest]

        progcall.finish()
        self.mylog.resetVerbose()
        fig, description = self._showResults(objective, df, N, figure)
        self.mylog.print(description.getvalue())

        if figure:
            return fig, description.getvalue()

        return N, df

    @_timer
    def runMC(self, objective, options, N, verbose=False, figure=False, progcall=None):
        """
        Run Monte Carlo simulations on plan.
        """
        if self.rateMethod not in ["stochastic", "histochastic"]:
            self.mylog.print("It is pointless to run Monte Carlo simulations with fixed rates.")
            return

        self.mylog.vprint(f"Running {N} Monte Carlo simulations.")
        self.mylog.setVerbose(verbose)

        # Turn off Medicare by default, unless specified in options.
        if "withMedicare" not in options:
            myoptions = dict(options)
            myoptions["withMedicare"] = False
        else:
            myoptions = options

        if objective == "maxSpending":
            columns = ["partial", objective]
        elif objective == "maxBequest":
            columns = ["partial", "final"]
        else:
            self.mylog.print(f"Invalid objective {objective}.")
            return None

        df = pd.DataFrame(columns=columns)

        if progcall is None:
            progcall = progress.Progress(self.mylog)

        if not verbose:
            progcall.start()

        for n in range(N):
            self.regenRates()
            self.solve(objective, myoptions)
            if not verbose:
                progcall.show((n + 1) / N)
            if self.caseStatus == "solved":
                if objective == "maxSpending":
                    df.loc[len(df)] = [self.partialBequest, self.basis]
                elif objective == "maxBequest":
                    df.loc[len(df)] = [self.partialBequest, self.bequest]

        progcall.finish()
        self.mylog.resetVerbose()
        fig, description = self._showResults(objective, df, N, figure)
        self.mylog.print(description.getvalue())

        if figure:
            return fig, description.getvalue()

        return N, df

    def _showResults(self, objective, df, N, figure):
        """
        Show a histogram of values from runMC() and runHistoricalRange().
        """
        import seaborn as sbn

        description = io.StringIO()

        pSuccess = u.pc(len(df) / N)
        print(f"Success rate: {pSuccess} on {N} samples.", file=description)
        title = f"$N$ = {N}, $P$ = {pSuccess}"
        means = df.mean(axis=0, numeric_only=True)
        medians = df.median(axis=0, numeric_only=True)

        my = 2 * [self.year_n[-1]]
        if self.N_i == 2 and self.n_d < self.N_n:
            my[0] = self.year_n[self.n_d - 1]

        # Don't show partial bequest of zero if spouse is full beneficiary,
        # or if solution led to empty accounts at the end of first spouse's life.
        if np.all(self.phi_j == 1) or medians.iloc[0] < 1:
            if medians.iloc[0] < 1:
                print(f"Optimized solutions all have null partial bequest in year {my[0]}.", file=description)
            df.drop("partial", axis=1, inplace=True)
            means = df.mean(axis=0, numeric_only=True)
            medians = df.median(axis=0, numeric_only=True)

        df /= 1000
        if len(df) > 0:
            thisyear = self.year_n[0]
            if objective == "maxBequest":
                fig, axes = plt.subplots()
                # Show both partial and final bequests in the same histogram.
                sbn.histplot(df, multiple="dodge", kde=True, ax=axes)
                legend = []
                # Don't know why but legend is reversed from df.
                for q in range(len(means) - 1, -1, -1):
                    dmedian = u.d(medians.iloc[q], latex=True)
                    dmean = u.d(means.iloc[q], latex=True)
                    legend.append(f"{my[q]}: $M$: {dmedian}, $\\bar{{x}}$: {dmean}")
                plt.legend(legend, shadow=True)
                plt.xlabel(f"{thisyear} $k")
                plt.title(objective)
                leads = [f"partial {my[0]}", f"  final {my[1]}"]
            elif len(means) == 2:
                # Show partial bequest and net spending as two separate histograms.
                fig, axes = plt.subplots(1, 2, figsize=(10, 5))
                cols = ["partial", objective]
                leads = [f"partial {my[0]}", objective]
                for q in range(2):
                    sbn.histplot(df[cols[q]], kde=True, ax=axes[q])
                    dmedian = u.d(medians.iloc[q], latex=True)
                    dmean = u.d(means.iloc[q], latex=True)
                    legend = [f"$M$: {dmedian}, $\\bar{{x}}$: {dmean}"]
                    axes[q].set_label(legend)
                    axes[q].legend(labels=legend)
                    axes[q].set_title(leads[q])
                    axes[q].set_xlabel(f"{thisyear} $k")
            else:
                # Show net spending as single histogram.
                fig, axes = plt.subplots()
                sbn.histplot(df[objective], kde=True, ax=axes)
                dmedian = u.d(medians.iloc[0], latex=True)
                dmean = u.d(means.iloc[0], latex=True)
                legend = [f"$M$: {dmedian}, $\\bar{{x}}$: {dmean}"]
                plt.legend(legend, shadow=True)
                plt.xlabel(f"{thisyear} $k")
                plt.title(objective)
                leads = [objective]

            plt.suptitle(title)
            # plt.show()

        for q in range(len(means)):
            print(f"{leads[q]:>12}: Median ({thisyear} $): {u.d(medians.iloc[q])}", file=description)
            print(f"{leads[q]:>12}:   Mean ({thisyear} $): {u.d(means.iloc[q])}", file=description)
            mmin = 1000 * df.iloc[:, q].min()
            mmax = 1000 * df.iloc[:, q].max()
            print(f"{leads[q]:>12}:           Range: {u.d(mmin)} - {u.d(mmax)}", file=description)
            nzeros = len(df.iloc[:, q][df.iloc[:, q] < 0.001])
            print(f"{leads[q]:>12}:    N zero solns: {nzeros}", file=description)

        return fig, description

    def resolve(self):
        """
        Solve a plan using saved options.
        """
        self.solve(self.objective, self.solverOptions)

        return None

    @_checkConfiguration
    @_timer
    def solve(self, objective, options={}):
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
            raise RuntimeError("Rate method must be selected before solving.")

        # Assume unsuccessful until problem solved.
        self.caseStatus = "unsuccessful"

        # Check objective and required options.
        knownObjectives = ["maxBequest", "maxSpending"]
        knownSolvers = ["HiGHS", "PuLP/CBC", "MOSEK"]

        knownOptions = [
            "bequest",
            "bigM",
            "maxRothConversion",
            "netSpending",
            "noRothConversions",
            "previousMAGIs",
            "solver",
            "spendingSlack",
            "startRothConversions",
            "units",
            "withMedicare",
            "oppCostX",
        ]
        # We might modify options if required.
        myoptions = dict(options)

        for opt in myoptions:
            if opt not in knownOptions:
                raise ValueError(f"Option {opt} is not one of {knownOptions}.")

        if objective not in knownObjectives:
            raise ValueError(f"Objective {objective} is not one of {knownObjectives}.")

        if objective == "maxBequest" and "netSpending" not in myoptions:
            raise RuntimeError(f"Objective {objective} needs netSpending option.")

        if objective == "maxBequest" and "bequest" in myoptions:
            self.mylog.vprint("Ignoring bequest option provided.")
            myoptions.pop("bequest")

        if objective == "maxSpending" and "netSpending" in myoptions:
            self.mylog.vprint("Ignoring netSpending option provided.")
            myoptions.pop("netSpending")

        if objective == "maxSpending" and "bequest" not in myoptions:
            self.mylog.vprint("Using bequest of $1.")

        self.prevMAGI = np.zeros(3)
        if "previousMAGIs" in myoptions:
            magi = myoptions["previousMAGIs"]
            if len(magi) != 3:
                raise ValueError("previousMAGIs must have 3 values.")

            units = u.getUnits(options.get("units", "k"))
            self.prevMAGI = units * np.array(magi)

        lambdha = myoptions.get("spendingSlack", 0)
        if lambdha < 0 or lambdha > 50:
            raise ValueError(f"Slack value out of range {lambdha}.")
        self.lambdha = lambdha / 100

        self._adjustParameters()

        solver = myoptions.get("solver", self.defaultSolver)
        if solver not in knownSolvers:
            raise ValueError(f"Unknown solver {solver}.")

        if solver == "HiGHS":
            solverMethod = self._milpSolve
        elif solver == "PuLP/CBC":
            solverMethod = self._pulpSolve
        elif solver == "MOSEK":
            solverMethod = self._mosekSolve
        else:
            raise RuntimeError("Internal error in defining solverMethod.")

        self._scSolve(objective, options, solverMethod)

        self.objective = objective
        self.solverOptions = myoptions

        return None

    def _scSolve(self, objective, options, solverMethod):
        """
        Self-consistent loop, regardless of solver.
        """
        withMedicare = options.get("withMedicare", True)

        if objective == "maxSpending":
            objFac = -1 / self.xi_n[0]
        else:
            objFac = -1 / self.gamma_n[-1]

        it = 0
        absdiff = np.inf
        old_x = np.zeros(self.nvars)
        old_solutions = [np.inf]
        self._estimateMedicare(None, withMedicare)
        while True:
            solution, xx, solverSuccess, solverMsg = solverMethod(objective, options)

            if not solverSuccess:
                break

            if not withMedicare:
                break

            self._estimateMedicare(xx)

            self.mylog.vprint(f"Iteration: {it} objective: {u.d(solution * objFac, f=2)}")

            delta = xx - old_x
            absdiff = np.sum(np.abs(delta), axis=0)
            if absdiff < 1:
                self.mylog.vprint("Converged on full solution.")
                break

            # Avoid oscillatory solutions. Look only at most recent solutions. Within $10.
            isclosenough = abs(-solution - min(old_solutions[int(it / 2) :])) < 10 * self.xi_n[0]
            if isclosenough:
                self.mylog.vprint("Converged through selecting minimum oscillating objective.")
                break

            if it > 59:
                self.mylog.vprint("WARNING: Exiting loop on maximum iterations.")
                break

            old_solutions.append(-solution)
            old_x = xx

        if solverSuccess:
            self.mylog.vprint(f"Self-consistent Medicare loop returned after {it} iterations.")
            self.mylog.vprint(solverMsg)
            self.mylog.vprint(f"Objective: {u.d(solution * objFac)}")
            # self.mylog.vprint('Upper bound:', u.d(-solution.mip_dual_bound))
            self._aggregateResults(xx)
            self._timestamp = datetime.now().strftime("%Y-%m-%d at %H:%M:%S")
            self.caseStatus = "solved"
        else:
            self.mylog.vprint("WARNING: Optimization failed:", solverMsg, solverSuccess)
            self.caseStatus = "unsuccessful"

        return None

    def _milpSolve(self, objective, options):
        """
        Solve problem using scipy HiGHS solver.
        """
        from scipy import optimize

        # mip_rel_gap smaller than 1e-6 can lead to oscillatory solutions.
        milpOptions = {"disp": False, "mip_rel_gap": 1e-7}

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

        return solution.fun, solution.x, solution.success, solution.message

    def _pulpSolve(self, objective, options):
        """
        Solve problem using scipy PuLP solver.
        """
        import pulp

        self._buildConstraints(objective, options)
        Alu, lbvec, ubvec = self.A.arrays()
        ckeys = self.A.keys()
        Lb, Ub = self.B.arrays()
        vkeys = self.B.keys()
        c = self.c.arrays()
        c_list = c.tolist()

        prob = pulp.LpProblem(self._name.replace(" ", "_"), pulp.LpMinimize)

        x = []
        for i in range(self.nvars - self.nbins):
            if vkeys[i] == "ra":
                x += [pulp.LpVariable(f"x_{i}", cat="Continuous", lowBound=Lb[i], upBound=Ub[i])]
            elif vkeys[i] == "lo":
                x += [pulp.LpVariable(f"x_{i}", cat="Continuous", lowBound=Lb[i], upBound=None)]
            elif vkeys[i] == "up":
                x += [pulp.LpVariable(f"x_{i}", cat="Continuous", lowBound=None, upBound=Ub[i])]
            elif vkeys[i] == "fr":
                x += [pulp.LpVariable(f"x_{i}", cat="Continuous", lowBound=None, upBound=None)]
            elif vkeys[i] == "fx":
                x += [pulp.LpVariable(f"x_{i}", cat="Continuous", lowBound=Lb[i], upBound=Ub[i])]
            else:
                raise RuntimeError(f"Internal error: Variable with wierd bound f{vkeys[i]}.")

        x.extend([pulp.LpVariable(f"z_{i}", cat="Binary") for i in range(self.nbins)])

        prob += pulp.lpDot(c_list, x)

        for r in range(self.A.ncons):
            row = Alu[r].tolist()
            if ckeys[r] in ["lo", "ra"] and lbvec[r] != -np.inf:
                prob += pulp.lpDot(row, x) >= lbvec[r]
            if ckeys[r] in ["up", "ra"] and ubvec[r] != np.inf:
                prob += pulp.lpDot(row, x) <= ubvec[r]
            if ckeys[r] == "fx":
                prob += pulp.lpDot(row, x) == ubvec[r]

        # prob.writeLP("C:\\Users\\marti\\Downloads\\pulp.lp")
        # prob.writeMPS("C:\\Users\\marti\\Downloads\\pulp.mps", rename=True)
        # solver_list = pulp.listSolvers(onlyAvailable=True)
        # print("Available solvers:", solver_list)
        # solver = pulp.getSolver("MOSEK")
        # prob.solve(solver)

        prob.solve(pulp.PULP_CBC_CMD(msg=False))
        # Filter out None values and convert to array.
        xx = np.array([0 if x[i].varValue is None else x[i].varValue for i in range(self.nvars)])
        solution = np.dot(c, xx)
        success = (pulp.LpStatus[prob.status] == "Optimal")

        return solution, xx, success, pulp.LpStatus[prob.status]

    def _mosekSolve(self, objective, options):
        """
        Solve problem using MOSEK solver.
        """
        import mosek

        bdic = {
            "fx": mosek.boundkey.fx,
            "fr": mosek.boundkey.fr,
            "lo": mosek.boundkey.lo,
            "ra": mosek.boundkey.ra,
            "up": mosek.boundkey.up,
        }

        solverMsg = str()

        def _streamPrinter(text, msg=solverMsg):
            msg += text

        self._buildConstraints(objective, options)
        Aind, Aval, clb, cub = self.A.lists()
        ckeys = self.A.keys()
        vlb, vub = self.B.arrays()
        integrality = self.B.integralityList()
        vkeys = self.B.keys()
        cind, cval = self.c.lists()

        task = mosek.Task()
        # task.putdouparam(mosek.dparam.mio_rel_gap_const, 1e-6)
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

        # Problem MUST contain binary variables to make these calls.
        solsta = task.getsolsta(mosek.soltype.itg)
        solverSuccess = (solsta == mosek.solsta.integer_optimal)

        xx = np.array(task.getxx(mosek.soltype.itg))
        solution = task.getprimalobj(mosek.soltype.itg)
        task.set_Stream(mosek.streamtype.wrn, _streamPrinter)
        task.solutionsummary(mosek.streamtype.msg)
        # task.writedata(self._name+'.ptf')

        return solution, xx, solverSuccess, solverMsg

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
            self.F_tn = np.array(x[self.C["F"] : self.C["g"]])
            self.F_tn = self.F_tn.reshape((self.N_t, self.N_n))
            MAGI_n = np.sum(self.F_tn, axis=0) + np.array(x[self.C["e"] : self.C["F"]])

        self.M_n = tx.mediCosts(self.yobs, self.horizons, MAGI_n, self.prevMAGI, self.gamma_n[:-1], self.N_n)

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

        Cb = self.C["b"]
        Cd = self.C["d"]
        Ce = self.C["e"]
        CF = self.C["F"]
        Cg = self.C["g"]
        Cs = self.C["s"]
        Cw = self.C["w"]
        Cx = self.C["x"]
        Cz = self.C["z"]

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
        else:
            self.partialBequest = 0

        self.rmd_in = self.rho_in * self.b_ijn[:, 1, :-1]
        self.dist_in = self.w_ijn[:, 1, :] - self.rmd_in
        self.dist_in[self.dist_in < 0] = 0
        self.G_n = np.sum(self.F_tn, axis=0)
        self.T_tn = self.F_tn * self.theta_tn
        self.T_n = np.sum(self.T_tn, axis=0)
        self.P_n = np.zeros(Nn)
        # Add early withdrawal penalty if any.
        for i in range(Ni):
            self.P_n[0:self.n59[i]] += 0.1*(self.w_ijn[i, 1, 0:self.n59[i]] + self.w_ijn[i, 2, 0:self.n59[i]])

        self.T_n += self.P_n

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
            '+dist',
            'RMD',
            'RothX',
            'wdrwl taxable',
            'wdrwl tax-free',
        ]
        """
        sources = {}
        sources["wages"] = self.omega_in
        sources["ssec"] = self.zetaBar_in
        sources["pension"] = self.piBar_in
        sources["txbl acc wdrwl"] = self.w_ijn[:, 0, :]
        sources["RMD"] = self.rmd_in
        sources["+dist"] = self.dist_in
        sources["RothX"] = self.x_in
        sources["tax-free wdrwl"] = self.w_ijn[:, 2, :]
        sources["BTI"] = self.Lambda_in

        savings = {}
        savings["taxable"] = self.b_ijn[:, 0, :]
        savings["tax-deferred"] = self.b_ijn[:, 1, :]
        savings["tax-free"] = self.b_ijn[:, 2, :]

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
        self.mylog.vprint(f"Estate value of {u.d(sum(_estate))} at the end of year {self.year_n[-1]}.")

        return None

    @_checkCaseStatus
    def summary(self):
        """
        Print summary in logs.
        """
        self.mylog.print("SUMMARY ================================================================")
        dic = self.summaryDic()
        for key, value in dic.items():
            self.mylog.print(f"{key}: {value}")
        self.mylog.print("------------------------------------------------------------------------")

        return None

    def summaryList(self):
        """
        Return summary as a list.
        """
        mylist = []
        dic = self.summaryDic()
        for key, value in dic.items():
            mylist.append(f"{key}: {value}")

        return mylist

    def summaryDf(self):
        """
        Return summary as a dataframe.
        """
        return pd.DataFrame(self.summaryDic(), index=[self._name])

    def summaryString(self):
        """
        Return summary as a string.
        """
        string = "Synopsis\n"
        dic = self.summaryDic()
        for key, value in dic.items():
            string += f"{key:>70}: {value}\n"

        return string

    def summaryDic(self):
        """
        Return dictionary containing summary of values.
        """
        now = self.year_n[0]
        dic = {}
        # Results
        dic["Plan name"] = self._name
        dic["Net yearly spending basis"] = u.d(self.g_n[0] / self.xi_n[0])
        dic[f"Net spending for year {now}"] = u.d(self.g_n[0] / self.yearFracLeft)
        dic[f"Net spending remaining in year {now}"] = u.d(self.g_n[0])

        totIncome = np.sum(self.g_n, axis=0)
        totIncomeNow = np.sum(self.g_n / self.gamma_n[:-1], axis=0)
        dic["Total net spending"] = f"{u.d(totIncomeNow)}"
        dic["[Total net spending]"] = f"{u.d(totIncome)}"

        totRoth = np.sum(self.x_in, axis=(0, 1))
        totRothNow = np.sum(np.sum(self.x_in, axis=0) / self.gamma_n[:-1], axis=0)
        dic["Total Roth conversions"] = f"{u.d(totRothNow)}"
        dic["[Total Roth conversions]"] = f"{u.d(totRoth)}"

        taxPaid = np.sum(self.T_n, axis=0)
        taxPaidNow = np.sum(self.T_n / self.gamma_n[:-1], axis=0)
        dic["Total income tax paid on ordinary income"] = f"{u.d(taxPaidNow)}"
        dic["[Total income tax paid on ordinary income]"] = f"{u.d(taxPaid)}"
        for t in range(self.N_t):
            taxPaid = np.sum(self.T_tn[t], axis=0)
            taxPaidNow = np.sum(self.T_tn[t] / self.gamma_n[:-1], axis=0)
            tname = tx.taxBracketNames[t]
            dic[f"-- Subtotal in tax bracket {tname}"] = f"{u.d(taxPaidNow)}"
            dic[f"-- [Subtotal in tax bracket {tname}]"] = f"{u.d(taxPaid)}"

        penaltyPaid = np.sum(self.P_n, axis=0)
        penaltyPaidNow = np.sum(self.P_n / self.gamma_n[:-1], axis=0)
        dic["-- Subtotal in early withdrawal penalty"] = f"{u.d(penaltyPaidNow)}"
        dic["-- [Subtotal in early withdrawal penalty]"] = f"{u.d(penaltyPaid)}"

        taxPaid = np.sum(self.U_n, axis=0)
        taxPaidNow = np.sum(self.U_n / self.gamma_n[:-1], axis=0)
        dic["Total tax paid on gains and dividends"] = f"{u.d(taxPaidNow)}"
        dic["[Total tax paid on gains and dividends]"] = f"{u.d(taxPaid)}"

        taxPaid = np.sum(self.M_n, axis=0)
        taxPaidNow = np.sum(self.M_n / self.gamma_n[:-1], axis=0)
        dic["Total Medicare premiums paid"] = f"{u.d(taxPaidNow)}"
        dic["[Total Medicare premiums paid]"] = f"{u.d(taxPaid)}"

        if self.N_i == 2 and self.n_d < self.N_n:
            p_j = self.partialEstate_j * (1 - self.phi_j)
            p_j[1] *= 1 - self.nu
            nx = self.n_d - 1
            ynx = self.year_n[nx]
            totOthers = np.sum(p_j)
            totOthersNow = totOthers / self.gamma_n[nx + 1]
            q_j = self.partialEstate_j * self.phi_j
            totSpousal = np.sum(q_j)
            totSpousalNow = totSpousal / self.gamma_n[nx + 1]
            iname_s = self.inames[self.i_s]
            iname_d = self.inames[self.i_d]
            dic[f"Sum of spousal transfer to {iname_s} in year {ynx}"] = (f"{u.d(totSpousalNow)}")
            dic[f"[Sum of spousal transfer to {iname_s} in year {ynx}]"] = (
                f"{u.d(totSpousal)}")
            dic[f"-- [Spousal transfer to {iname_s} in year {ynx} - taxable]"] = (
                f"{u.d(q_j[0])}")
            dic[f"-- [Spousal transfer to {iname_s} in year {ynx} - tax-def]"] = (
                f"{u.d(q_j[1])}")
            dic[f"-- [Spousal transfer to {iname_s} in year {ynx} - tax-free]"] = (
                f"{u.d(q_j[2])}")

            dic[f"Sum of post-tax non-spousal bequests from {iname_d} in year {ynx}"] = (
                f"{u.d(totOthersNow)}")
            dic[f"[Sum of post-tax non-spousal bequests from {iname_d} in year {ynx}]"] = (
                f"{u.d(totOthers)}")
            dic[f"-- [Post-tax non-spousal bequests from {iname_d} in year {ynx} - taxable]"] = (
                f"{u.d(p_j[0])}")
            dic[f"-- [Post-tax non-spousal bequests from {iname_d} in year {ynx} - tax-def]"] = (
                f"{u.d(p_j[1])}")
            dic[f"-- [Post-tax non-spousal bequests from {iname_d} in year {ynx} - tax-free]"] = (
                f"{u.d(p_j[2])}")

        estate = np.sum(self.b_ijn[:, :, self.N_n], axis=0)
        estate[1] *= 1 - self.nu
        lastyear = self.year_n[-1]
        totEstate = np.sum(estate)
        totEstateNow = totEstate / self.gamma_n[-1]
        dic[f"Total estate value at the end of {lastyear}"] = (f"{u.d(totEstateNow)}")
        dic[f"[Total estate value at the end of {lastyear}]"] = (f"{u.d(totEstate)}")
        dic[f"-- [Post-tax account value at the end of {lastyear} - taxable]"] = (f"{u.d(estate[0])}")
        dic[f"-- [Post-tax account value at the end of {lastyear} - tax-def]"] = (f"{u.d(estate[1])}")
        dic[f"-- [Post-tax account value at the end of {lastyear} - tax-free]"] = (f"{u.d(estate[2])}")

        dic["Plan starting date"] = str(self.startDate)
        dic[f"Cumulative inflation factor from start date to end of {lastyear}"] = (f"{self.gamma_n[-1]:.2f}")
        for i in range(self.N_i):
            dic[f"{self.inames[i]:>12}'s {self.horizons[i]:02}-year life horizon"] = (
                f"{now} -> {now + self.horizons[i] - 1}")

        dic["Plan name"] = self._name
        dic["Number of decision variables"] = str(self.A.nvars)
        dic["Number of constraints"] = str(self.A.ncons)
        dic["Case executed on"] = str(self._timestamp)

        return dic

    def showRatesCorrelations(self, tag="", shareRange=False, figure=False):
        """
        Plot correlations between various rates.

        A tag string can be set to add information to the title of the plot.
        """
        import seaborn as sbn

        if self.rateMethod in [None, "user", "historical average", "conservative"]:
            self.mylog.vprint(f"Warning: Cannot plot correlations for {self.rateMethod} rate method.")
            return None

        rateNames = [
            "S&P500 (incl. div.)",
            "Baa Corp. Bonds",
            "10-y T-Notes",
            "Inflation",
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
        g.map_diag(sbn.histplot, color="orange")

        # Put zero axes on off-diagonal plots.
        imod = len(rateNames) + 1
        for i, ax in enumerate(g.axes.flat):
            ax.axvline(x=0, color="grey", linewidth=1, linestyle=":")
            if i % imod != 0:
                ax.axhline(y=0, color="grey", linewidth=1, linestyle=":")
        #    ax.tick_params(axis='both', labelleft=True, labelbottom=True)

        # plt.subplots_adjust(wspace=0.3, hspace=0.3)

        title = self._name + "\n"
        title += f"Rates Correlations (N={self.N_n}) {self.rateMethod}"
        if self.rateMethod in ["historical", "histochastic"]:
            title += " (" + str(self.rateFrm) + "-" + str(self.rateTo) + ")"

        if tag != "":
            title += " - " + tag

        g.fig.suptitle(title, y=1.08)

        if figure:
            return g.fig

        plt.show()
        return None

    def showRates(self, tag="", figure=False):
        """
        Plot rate values used over the time horizon.

        A tag string can be set to add information to the title of the plot.
        """
        import matplotlib.ticker as tk

        if self.rateMethod is None:
            self.mylog.vprint("Warning: Rate method must be selected before plotting.")
            return None

        fig, ax = plt.subplots(figsize=(6, 4))
        plt.grid(visible="both")
        title = self._name + "\nReturn & Inflation Rates (" + str(self.rateMethod)
        if self.rateMethod in ["historical", "histochastic", "historical average"]:
            title += " " + str(self.rateFrm) + "-" + str(self.rateTo)
        title += ")"

        if tag != "":
            title += " - " + tag

        rateName = [
            "S&P500 (incl. div.)",
            "Baa Corp. Bonds",
            "10-y T-Notes",
            "Inflation",
        ]
        ltype = ["-", "-.", ":", "--"]
        for k in range(self.N_k):
            if self.yearFracLeft == 1:
                data = 100 * self.tau_kn[k]
                years = self.year_n
            else:
                data = 100 * self.tau_kn[k, 1:]
                years = self.year_n[1:]

            # Use ddof=1 to match pandas.
            label = (
                rateName[k] + " <" + "{:.1f}".format(np.mean(data)) + " +/- {:.1f}".format(np.std(data, ddof=1)) + "%>"
            )
            ax.plot(years, data, label=label, ls=ltype[k % self.N_k])

        ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
        ax.legend(loc="best", reverse=False, fontsize=8, framealpha=0.7)
        # ax.legend(loc='upper left')
        ax.set_title(title)
        ax.set_xlabel("year")
        ax.set_ylabel("%")

        if figure:
            return fig

        plt.show()
        return None

    def showProfile(self, tag="", figure=False):
        """
        Plot spending profile over time.

        A tag string can be set to add information to the title of the plot.
        """
        if self.xi_n is None:
            self.mylog.vprint("Warning: Profile must be selected before plotting.")
            return None

        title = self._name + "\nSpending Profile"
        if tag != "":
            title += " - " + tag

        # style = {'net': '-', 'target': ':'}
        style = {"profile": "-"}
        series = {"profile": self.xi_n}
        fig, ax = _lineIncomePlot(self.year_n, series, style, title, yformat="$\\xi$")

        if figure:
            return fig

        plt.show()
        return None

    @_checkCaseStatus
    def showNetSpending(self, tag="", value=None, figure=False):
        """
        Plot net available spending and target over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        title = self._name + "\nNet Available Spending"
        if tag != "":
            title += " - " + tag

        style = {"net": "-", "target": ":"}
        if value == "nominal":
            series = {"net": self.g_n, "target": (self.g_n[0] / self.xi_n[0]) * self.xiBar_n}
            yformat = "\\$k (nominal)"
        else:
            series = {
                "net": self.g_n / self.gamma_n[:-1],
                "target": (self.g_n[0] / self.xi_n[0]) * self.xi_n,
            }
            yformat = "\\$k (" + str(self.year_n[0]) + "\\$)"

        fig, ax = _lineIncomePlot(self.year_n, series, style, title, yformat)

        if figure:
            return fig

        plt.show()
        return None

    @_checkCaseStatus
    def showAssetDistribution(self, tag="", value=None, figure=False):
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

        if value == "nominal":
            yformat = "\\$k (nominal)"
            infladjust = 1
        else:
            yformat = "\\$k (" + str(self.year_n[0]) + "\\$)"
            infladjust = self.gamma_n

        years_n = np.array(self.year_n)
        years_n = np.append(years_n, [years_n[-1] + 1])
        y2stack = {}
        jDic = {"taxable": 0, "tax-deferred": 1, "tax-free": 2}
        kDic = {"stocks": 0, "C bonds": 1, "T notes": 2, "common": 3}
        figures = []
        for jkey in jDic:
            stackNames = []
            for kkey in kDic:
                name = kkey + " / " + jkey
                stackNames.append(name)
                y2stack[name] = np.zeros((self.N_i, self.N_n + 1))
                for i in range(self.N_i):
                    y2stack[name][i][:] = self.b_ijkn[i][jDic[jkey]][kDic[kkey]][:] / infladjust

            title = self._name + "\nAssets Distribution - " + jkey
            if tag != "":
                title += " - " + tag

            fig, ax = _stackPlot(
                years_n, self.inames, title, range(self.N_i), y2stack, stackNames, "upper left", yformat
            )
            figures.append(fig)

        if figure:
            return figures

        plt.show()
        return None

    def showAllocations(self, tag="", figure=False):
        """
        Plot desired allocation of savings accounts in percentage
        over simulation time and interpolated by the selected method
        through the interpolateAR() method.

        A tag string can be set to add information to the title of the plot.
        """
        count = self.N_i
        if self.ARCoord == "spouses":
            acList = [self.ARCoord]
            count = 1
        elif self.ARCoord == "individual":
            acList = [self.ARCoord]
        elif self.ARCoord == "account":
            acList = ["taxable", "tax-deferred", "tax-free"]
        else:
            raise ValueError(f"Unknown coordination {self.ARCoord}.")

        figures = []
        assetDic = {"stocks": 0, "C bonds": 1, "T notes": 2, "common": 3}
        for i in range(count):
            y2stack = {}
            for acType in acList:
                stackNames = []
                for key in assetDic:
                    aname = key + " / " + acType
                    stackNames.append(aname)
                    y2stack[aname] = np.zeros((count, self.N_n))
                    y2stack[aname][i][:] = self.alpha_ijkn[i, acList.index(acType), assetDic[key], : self.N_n]

                    title = self._name + "\nAsset Allocation (%) - " + acType
                    if self.ARCoord == "spouses":
                        title += " spouses"
                    else:
                        title += " " + self.inames[i]

                if tag != "":
                    title += " - " + tag

                fig, ax = _stackPlot(self.year_n, self.inames, title, [i], y2stack, stackNames, "upper left", "percent")
                figures.append(fig)

        if figure:
            return figures

        plt.show()
        return None

    @_checkCaseStatus
    def showAccounts(self, tag="", value=None, figure=False):
        """
        Plot values of savings accounts over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        title = self._name + "\nSavings Balance"
        if tag != "":
            title += " - " + tag

        stypes = self.savings_in.keys()
        # Add one year for estate.
        year_n = np.append(self.year_n, [self.year_n[-1] + 1])

        if value == "nominal":
            yformat = "\\$k (nominal)"
            savings_in = self.savings_in
        else:
            yformat = "\\$k (" + str(self.year_n[0]) + "\\$)"
            savings_in = {}
            for key in self.savings_in:
                savings_in[key] = self.savings_in[key] / self.gamma_n

        fig, ax = _stackPlot(year_n, self.inames, title, range(self.N_i), savings_in, stypes, "upper left", yformat)

        if figure:
            return fig

        plt.show()
        return None

    @_checkCaseStatus
    def showSources(self, tag="", value=None, figure=False):
        """
        Plot income over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        title = self._name + "\nRaw Income Sources"
        stypes = self.sources_in.keys()
        # stypes = [item for item in stypes if "RothX" not in item]

        if tag != "":
            title += " - " + tag

        if value == "nominal":
            yformat = "\\$k (nominal)"
            sources_in = self.sources_in
        else:
            yformat = "\\$k (" + str(self.year_n[0]) + "\\$)"
            sources_in = {}
            for key in stypes:
                sources_in[key] = self.sources_in[key] / self.gamma_n[:-1]

        fig, ax = _stackPlot(
            self.year_n, self.inames, title, range(self.N_i), sources_in, stypes, "upper left", yformat
        )

        if figure:
            return fig

        plt.show()
        return None

    @_checkCaseStatus
    def _showFeff(self, tag=""):
        """
        Plot income tax paid over time.

        A tag string can be set to add information to the title of the plot.
        """
        title = self._name + "\nEff f "
        if tag != "":
            title += " - " + tag

        various = ["-", "--", "-.", ":"]
        style = {}
        series = {}
        q = 0
        for t in range(self.N_t):
            key = "f " + str(t)
            series[key] = self.F_tn[t] / self.DeltaBar_tn[t]
            # print(key, series[key])
            style[key] = various[q % len(various)]
            q += 1

        fig, ax = _lineIncomePlot(self.year_n, series, style, title, yformat="")

        plt.show()
        return None

    @_checkCaseStatus
    def showTaxes(self, tag="", value=None, figure=False):
        """
        Plot income tax paid over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        style = {"income taxes": "-", "Medicare": "-."}

        if value == "nominal":
            series = {"income taxes": self.T_n, "Medicare": self.M_n}
            yformat = "\\$k (nominal)"
        else:
            series = {
                "income taxes": self.T_n / self.gamma_n[:-1],
                "Medicare": self.M_n / self.gamma_n[:-1],
            }
            yformat = "\\$k (" + str(self.year_n[0]) + "\\$)"

        title = self._name + "\nIncome Tax"
        if tag != "":
            title += " - " + tag

        fig, ax = _lineIncomePlot(self.year_n, series, style, title, yformat)

        if figure:
            return fig

        plt.show()
        return None

    @_checkCaseStatus
    def showGrossIncome(self, tag="", value=None, figure=False):
        """
        Plot income tax and taxable income over time horizon.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValue(value)

        style = {"taxable income": "-"}

        if value == "nominal":
            series = {"taxable income": self.G_n}
            yformat = "\\$k (nominal)"
            infladjust = self.gamma_n[:-1]
        else:
            series = {"taxable income": self.G_n / self.gamma_n[:-1]}
            yformat = "\\$k (" + str(self.year_n[0]) + "\\$)"
            infladjust = 1

        title = self._name + "\nTaxable Ordinary Income vs. Tax Brackets"
        if tag != "":
            title += " - " + tag

        fig, ax = _lineIncomePlot(self.year_n, series, style, title, yformat)

        data = tx.taxBrackets(self.N_i, self.n_d, self.N_n, self.yTCJA)
        for key in data:
            data_adj = data[key] * infladjust
            ax.plot(self.year_n, data_adj, label=key, ls=":")

        plt.grid(visible="both")
        ax.legend(loc="upper left", reverse=True, fontsize=8, framealpha=0.3)

        if figure:
            return fig

        plt.show()
        return None

    # @_checkCaseStatus
    def saveConfig(self, basename=None):
        """
        Save parameters in a configuration file.
        """
        if basename is None:
            basename = "case_" + self._name

        config.saveConfig(self, basename, self.mylog)

        return None

    @_checkCaseStatus
    def saveWorkbook(self, overwrite=False, *, basename=None, saveToFile=True):
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

        Last worksheet contains summary.
        """

        def fillsheet(sheet, dic, datatype, op=lambda x: x):
            rawData = {}
            rawData["year"] = self.year_n
            if datatype == "currency":
                for key in dic:
                    rawData[key] = u.roundCents(op(dic[key]))
            else:
                for key in dic:
                    rawData[key] = op(dic[key])

            # We need to work by row.
            df = pd.DataFrame(rawData)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)

            _formatSpreadsheet(ws, datatype)

        wb = Workbook()

        # Income.
        ws = wb.active
        ws.title = "Income"

        incomeDic = {
            "net spending": self.g_n,
            "taxable ord. income": self.G_n,
            "taxable gains/divs": self.Q_n,
            "Tax bills + Med.": self.T_n + self.U_n + self.M_n,
        }

        fillsheet(ws, incomeDic, "currency")

        # Cash flow - sum over both individuals for some.
        cashFlowDic = {
            "net spending": self.g_n,
            "all wages": np.sum(self.omega_in, axis=0),
            "all pensions": np.sum(self.piBar_in, axis=0),
            "all soc sec": np.sum(self.zetaBar_in, axis=0),
            "all BTI's": np.sum(self.Lambda_in, axis=0),
            "all wdrwls": np.sum(self.w_ijn, axis=(0, 1)),
            "all deposits": -np.sum(self.d_in, axis=0),
            "ord taxes": -self.T_n,
            "div taxes": -self.U_n,
            "Medicare": -self.M_n,
        }
        sname = "Cash Flow"
        ws = wb.create_sheet(sname)
        fillsheet(ws, cashFlowDic, "currency")

        # Sources are handled separately.
        srcDic = {
            "wages": self.sources_in["wages"],
            "social sec": self.sources_in["ssec"],
            "pension": self.sources_in["pension"],
            "txbl acc wdrwl": self.sources_in["txbl acc wdrwl"],
            "RMDs": self.sources_in["RMD"],
            "+distributions": self.sources_in["+dist"],
            "Roth conv": self.sources_in["RothX"],
            "tax-free wdrwl": self.sources_in["tax-free wdrwl"],
            "big-ticket items": self.sources_in["BTI"],
        }

        for i in range(self.N_i):
            sname = self.inames[i] + "'s Sources"
            ws = wb.create_sheet(sname)
            fillsheet(ws, srcDic, "currency", op=lambda x: x[i])

        # Account balances except final year.
        accDic = {
            "taxable bal": self.b_ijn[:, 0, :-1],
            "taxable ctrb": self.kappa_ijn[:, 0, :],
            "taxable dep": self.d_in,
            "taxable wdrwl": self.w_ijn[:, 0, :],
            "tax-deferred bal": self.b_ijn[:, 1, :-1],
            "tax-deferred ctrb": self.kappa_ijn[:, 1, :],
            "tax-deferred wdrwl": self.w_ijn[:, 1, :],
            "(included RMDs)": self.rmd_in[:, :],
            "Roth conv": self.x_in,
            "tax-free bal": self.b_ijn[:, 2, :-1],
            "tax-free ctrb": self.kappa_ijn[:, 2, :],
            "tax-free wdrwl": self.w_ijn[:, 2, :],
        }
        for i in range(self.N_i):
            sname = self.inames[i] + "'s Accounts"
            ws = wb.create_sheet(sname)
            fillsheet(ws, accDic, "currency", op=lambda x: x[i])
            # Add final balances.
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
                0,
            ]
            ws.append(lastRow)
            _formatSpreadsheet(ws, "currency")

        # Allocations.
        jDic = {"taxable": 0, "tax-deferred": 1, "tax-free": 2}
        kDic = {"stocks": 0, "C bonds": 1, "T notes": 2, "common": 3}

        # Add one year for estate.
        year_n = np.append(self.year_n, [self.year_n[-1] + 1])
        for i in range(self.N_i):
            sname = self.inames[i] + "'s Allocations"
            ws = wb.create_sheet(sname)
            rawData = {}
            rawData["year"] = year_n
            for jkey in jDic:
                for kkey in kDic:
                    rawData[jkey + "/" + kkey] = self.alpha_ijkn[i, jDic[jkey], kDic[kkey], :]
            df = pd.DataFrame(rawData)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)

            _formatSpreadsheet(ws, "percent1")

        # Rates on penultimate sheet.
        ratesDic = {
            "S&P 500": self.tau_kn[0],
            "Corporate Baa": self.tau_kn[1],
            "T Bonds": self.tau_kn[2],
            "inflation": self.tau_kn[3],
        }
        ws = wb.create_sheet("Rates")
        fillsheet(ws, ratesDic, "percent2")

        # Summary on last sheet.
        ws = wb.create_sheet("Summary")
        rawData = {}
        rawData["SUMMARY ==========================================================================="] = (
            self.summaryList()
        )

        df = pd.DataFrame(rawData)
        for row in dataframe_to_rows(df, index=False, header=True):
            ws.append(row)

        _formatSpreadsheet(ws, "summary")

        if saveToFile:
            if basename is None:
                basename = self._name

            _saveWorkbook(wb, basename, overwrite, self.mylog)
            return None

        return wb

    def saveWorkbookCSV(self, basename):
        """
        Function similar to saveWorkbook(), but saving information in csv format
        instead of an Excel worksheet.
        See saveWorkbook() sister function for more information.
        """

        planData = {}
        planData["year"] = self.year_n
        planData["net spending"] = self.g_n
        planData["taxable ord. income"] = self.G_n
        planData["taxable gains/divs"] = self.Q_n
        planData["tax bill"] = self.T_n

        for i in range(self.N_i):
            planData[self.inames[i] + " txbl bal"] = self.b_ijn[i, 0, :-1]
            planData[self.inames[i] + " txbl dep"] = self.d_in[i, :]
            planData[self.inames[i] + " txbl wrdwl"] = self.w_ijn[i, 0, :]
            planData[self.inames[i] + " tx-def bal"] = self.b_ijn[i, 1, :-1]
            planData[self.inames[i] + " tx-def ctrb"] = self.kappa_ijn[i, 1, :]
            planData[self.inames[i] + " tx-def wdrl"] = self.w_ijn[i, 1, :]
            planData[self.inames[i] + " (RMD)"] = self.rmd_in[i, :]
            planData[self.inames[i] + " Roth conv"] = self.x_in[i, :]
            planData[self.inames[i] + " tx-free bal"] = self.b_ijn[i, 2, :-1]
            planData[self.inames[i] + " tx-free ctrb"] = self.kappa_ijn[i, 2, :]
            planData[self.inames[i] + " tax-free wdrwl"] = self.w_ijn[i, 2, :]
            planData[self.inames[i] + " big-ticket items"] = self.Lambda_in[i, :]

        ratesDic = {"S&P 500": 0, "Corporate Baa": 1, "T Bonds": 2, "inflation": 3}
        for key in ratesDic:
            planData[key] = self.tau_kn[ratesDic[key]]

        df = pd.DataFrame(planData)

        while True:
            try:
                fname = "worksheet" + "_" + basename + ".csv"
                df.to_csv(fname)
                break
            except PermissionError:
                self.mylog.print(f'Failed to save "{fname}": Permission denied.')
                key = input("Close file and try again? [Yn] ")
                if key == "n":
                    break
            except Exception as e:
                raise Exception(f"Unanticipated exception: {e}.")

        return None


def _lineIncomePlot(x, series, style, title, yformat="\\$k"):
    """
    Core line plotter function.
    """
    import matplotlib.ticker as tk

    fig, ax = plt.subplots(figsize=(6, 4))
    plt.grid(visible="both")

    for sname in series:
        ax.plot(x, series[sname], label=sname, ls=style[sname])

    ax.legend(loc="upper left", reverse=True, fontsize=8, framealpha=0.3)
    ax.set_title(title)
    ax.set_xlabel("year")
    ax.set_ylabel(yformat)
    ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
    if "k" in yformat:
        ax.get_yaxis().set_major_formatter(tk.FuncFormatter(lambda x, p: format(int(x / 1000), ",")))
        # Give range to y values in unindexed flat profiles.
        ymin, ymax = ax.get_ylim()
        if ymax - ymin < 5000:
            ax.set_ylim((ymin * 0.95, ymax * 1.05))

    return fig, ax


def _stackPlot(x, inames, title, irange, series, snames, location, yformat="\\$k"):
    """
    Core function for stacked plots.
    """
    import matplotlib.ticker as tk

    nonzeroSeries = {}
    for sname in snames:
        for i in irange:
            tmp = series[sname][i]
            if sum(tmp) > 1.0:
                nonzeroSeries[sname + " " + inames[i]] = tmp

    if len(nonzeroSeries) == 0:
        # print('Nothing to plot for', title)
        return None, None

    fig, ax = plt.subplots(figsize=(6, 4))
    plt.grid(visible="both")

    ax.stackplot(x, nonzeroSeries.values(), labels=nonzeroSeries.keys(), alpha=0.6)
    ax.legend(loc=location, reverse=True, fontsize=8, ncol=2, framealpha=0.5)
    ax.set_title(title)
    ax.set_xlabel("year")
    ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
    if "k" in yformat:
        ax.set_ylabel(yformat)
        ax.get_yaxis().set_major_formatter(tk.FuncFormatter(lambda x, p: format(int(x / 1000), ",")))
    elif yformat == "percent":
        ax.set_ylabel("%")
        ax.get_yaxis().set_major_formatter(tk.FuncFormatter(lambda x, p: format(int(100 * x), ",")))
    else:
        raise RuntimeError(f"Unknown yformat: {yformat}.")

    return fig, ax


def _saveWorkbook(wb, basename, overwrite, mylog):
    """
    Utility function to save XL workbook.
    """
    from os.path import isfile
    from pathlib import Path

    if Path(basename).suffixes == []:
        fname = "workbook" + "_" + basename + ".xlsx"
    else:
        fname = basename

    if overwrite is False and isfile(fname):
        mylog.print(f'File "{fname}" already exists.')
        key = input("Overwrite? [Ny] ")
        if key != "y":
            mylog.vprint("Skipping save and returning.")
            return None

    while True:
        try:
            mylog.vprint(f'Saving plan as "{fname}".')
            wb.save(fname)
            break
        except PermissionError:
            mylog.print(f'Failed to save "{fname}": Permission denied.')
            key = input("Close file and try again? [Yn] ")
            if key == "n":
                break
        except Exception as e:
            raise Exception(f"Unanticipated exception {e}.")

    return None


def _formatSpreadsheet(ws, ftype):
    """
    Utility function to beautify spreadsheet.
    """
    if ftype == "currency":
        fstring = "$#,##0_);[Red]($#,##0)"
    elif ftype == "percent2":
        fstring = "#.00%"
    elif ftype == "percent1":
        fstring = "#.0%"
    elif ftype == "percent0":
        fstring = "#0%"
    elif ftype == "summary":
        for col in ws.columns:
            column = col[0].column_letter
            width = max(len(str(col[0].value)) + 20, 40)
            ws.column_dimensions[column].width = width
            return None
    else:
        raise RuntimeError(f"Unknown format: {ftype}.")

    for cell in ws[1] + ws["A"]:
        cell.style = "Pandas"
    for col in ws.columns:
        column = col[0].column_letter
        # col[0].style = 'Title'
        width = max(len(str(col[0].value)) + 4, 10)
        ws.column_dimensions[column].width = width
        if column != "A":
            for cell in col:
                cell.number_format = fstring

    return None
