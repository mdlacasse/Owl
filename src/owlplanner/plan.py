"""
Core retirement planning module using linear programming optimization.

This module implements the main Plan class and optimization logic for retirement
financial planning. See companion PDF document for an explanation of the underlying
mathematical model and a description of all variables and parameters.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

###########################################################################
import numpy as np
import pandas as pd
from datetime import date, datetime
from functools import wraps
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import time

from . import utils as u
from . import tax2026 as tx
from . import abcapi as abc
from . import rates
from . import config
from . import timelists
from . import socialsecurity as socsec
from . import debts as debts
from . import fixedassets as fxasst
from . import mylogging as log
from . import progress
from .plotting.factory import PlotFactory


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
    Return an almost identical copy of plan: only the name of the case
    has been modified and appended the string '(copy)',
    unless a new name is provided as an argument.
    """
    import copy

    # logger __deepcopy__ sets the logstreams of new logger to None
    newplan = copy.deepcopy(plan)

    if logstreams is None:
        original_logger = plan.logger()
        newplan.setLogger(original_logger)
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


class Plan:
    """
    This is the main class of the Owl Project.
    """
    # Class-level counter for unique Plan IDs
    _id_counter = 0

    @classmethod
    def get_next_id(cls):
        cls._id_counter += 1
        return cls._id_counter

    @classmethod
    def get_current_id(cls):
        return cls._id_counter

    def __init__(self, inames, dobs, expectancy, name, *, verbose=False, logstreams=None):
        """
        Constructor requires three lists: the first
        one contains the name(s) of the individual(s),
        the second one is the year of birth of each individual,
        and the third the life expectancy. Last argument is a name for
        the case.
        """
        if name == "":
            raise ValueError("Plan must have a name")

        # Generate unique ID for this Plan instance using the class method
        self._id = Plan.get_next_id()

        self._name = name
        self.setLogstreams(verbose, logstreams)

        # 7 tax brackets, 6 Medicare brackets, 3 types of accounts, 4 classes of assets.
        self.N_t = 7
        self.N_q = 6
        self.N_j = 3
        self.N_k = 4
        # 2 binary variables.
        self.N_zx = 2

        # Default interpolation parameters for allocation ratios.
        self.interpMethod = "linear"
        self._interpolator = self._linInterp
        self.interpCenter = 15
        self.interpWidth = 5

        self._description = ''
        self.defaultPlots = "nominal"
        self.defaultSolver = "HiGHS"
        self._plotterName = None
        # Pick a default plotting backend here.
        # self.setPlotBackend("matplotlib")
        self.setPlotBackend("plotly")

        self.N_i = len(dobs)
        if not (0 <= self.N_i <= 2):
            raise ValueError(f"Cannot support {self.N_i} individuals.")
        if self.N_i != len(expectancy):
            raise ValueError(f"Expectancy must have {self.N_i} entries.")
        if self.N_i != len(inames):
            raise ValueError(f"Names for individuals must have {self.N_i} entries.")
        if inames[0] == "" or (self.N_i == 2 and inames[1] == ""):
            raise ValueError("Name for each individual must be provided.")

        self.filingStatus = ("single", "married")[self.N_i - 1]

        # Default year OBBBA speculated to be expired and replaced by pre-TCJA rates.
        self.yOBBBA = 2032
        self.inames = inames
        self.yobs, self.mobs, self.tobs = u.parseDobs(dobs)
        self.dobs = dobs
        self.expectancy = np.array(expectancy, dtype=np.int32)

        # Reference time is starting date in the current year and all passings are assumed at the end.
        thisyear = date.today().year
        self.horizons = self.yobs + self.expectancy - thisyear + 1
        self.N_n = np.max(self.horizons)
        self.year_n = np.linspace(thisyear, thisyear + self.N_n - 1, self.N_n, dtype=np.int32)
        # Year index in the case (if any) where individuals turn 59. For 10% withdrawal penalty.
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
        self.psi_n = np.zeros(self.N_n)  # Long-term income tax rate on capital gains (decimal)
        self.chi = 0.6   # Survivor fraction
        self.mu = 0.018  # Dividend rate (decimal)
        self.nu = 0.30   # Heirs tax rate (decimal)
        self.eta = (self.N_i - 1) / 2  # Spousal deposit ratio (0 or .5)
        self.phi_j = np.array([1, 1, 1])  # Fractions left to other spouse at death
        self.smileDip = 15  # Percent to reduce smile profile
        self.smileIncrease = 12  # Percent to increse profile over time span

        # Default to zero pension and social security.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        self.pensionAmounts = np.zeros(self.N_i, dtype=np.int32)
        self.pensionAges = 65 * np.ones(self.N_i, dtype=np.int32)
        self.pensionIsIndexed = [False] * self.N_i
        self.ssecAmounts = np.zeros(self.N_i, dtype=np.int32)
        self.ssecAges = 67 * np.ones(self.N_i, dtype=np.int32)

        # Parameters from timeLists initialized to zero.
        self.omega_in = np.zeros((self.N_i, self.N_n))
        self.Lambda_in = np.zeros((self.N_i, self.N_n))
        # Go back 5 years for maturation rules on IRA and Roth.
        self.myRothX_in = np.zeros((self.N_i, self.N_n + 5))
        self.kappa_ijn = np.zeros((self.N_i, self.N_j, self.N_n + 5))

        # Debt payments array (length N_n)
        self.debt_payments_n = np.zeros(self.N_n)

        # Fixed assets arrays (length N_n)
        self.fixed_assets_tax_free_n = np.zeros(self.N_n)
        self.fixed_assets_ordinary_income_n = np.zeros(self.N_n)
        self.fixed_assets_capital_gains_n = np.zeros(self.N_n)
        # Fixed assets bequest value (assets with yod past plan end)
        self.fixed_assets_bequest_value = 0.0

        # Remaining debt balance at end of plan
        self.remaining_debt_balance = 0.0

        # File-based rates attributes (for "file" method)
        self.rateFile = None
        self.rateSheetName = None

        # Previous 2 years of MAGI needed for Medicare.
        self.prevMAGI = np.zeros((2))
        self.MAGI_n = np.zeros(self.N_n)

        # Init current balances to none.
        self.beta_ij = None
        self.startDate = None

        # Default slack on profile.
        self.lambdha = 0

        # Scenario starts at the beginning of this year and ends at the end of the last year.
        s = ("", "s")[self.N_i - 1]
        self.mylog.vprint(f"Preparing scenario {self._id} of {self.N_n} years for {self.N_i} individual{s}.")
        for i in range(self.N_i):
            endyear = thisyear + self.horizons[i] - 1
            self.mylog.vprint(f"{self.inames[i]:>14}: life horizon from {thisyear} -> {endyear}.")

        # Prepare RMD time series.
        self.rho_in = tx.rho_in(self.yobs, self.N_n)

        # Initialize guardrails to ensure proper configuration.
        self._adjustedParameters = False
        self.timeListsFileName = "None"
        self.timeLists = {}
        self.houseLists = {}
        self.zeroContributions()
        self.caseStatus = "unsolved"
        self.rateMethod = None
        self.reproducibleRates = False
        self.rateSeed = None

        self.ARCoord = None
        self.objective = "unknown"

        # Placeholders values used to check if properly configured.
        self.xi_n = None
        self.alpha_ijkn = None

        return None

    def setLogger(self, logger):
        self.mylog = logger

    def setLogstreams(self, verbose, logstreams):
        self.mylog = log.Logger(verbose, logstreams)
        self.mylog.vprint(f"Setting logger with logstreams {logstreams}.")

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
        Set the date when the case starts in the current year.
        This is mostly for reproducibility purposes and back projecting known balances to Jan 1st.
        String format of mydate is 'MM/DD', 'MM-DD', 'YYYY-MM-DD', or 'YYYY/MM/DD'. Year is ignored.
        """
        import calendar

        thisyear = date.today().year

        if isinstance(mydate, date):
            mydate = mydate.strftime("%Y-%m-%d")

        if mydate is None or mydate == "today":
            refdate = date.today()
            self.startDate = refdate.strftime("%Y-%m-%d")
        else:
            mydatelist = mydate.replace("/", "-").split("-")
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

    def _checkValueType(self, value):
        """
        Short utility function to parse and check arguments for plotting.
        """
        if value is None:
            return self.defaultPlots

        opts = ("nominal", "today")
        if value not in opts:
            raise ValueError(f"Value type must be one of: {opts}")

        return value

    def rename(self, newname):
        """
        Override name of the case. Case name is used
        to distinguish graph outputs and as base name for
        saving configurations and workbooks.
        """
        self.mylog.vprint(f"Renaming case {self._name} -> {newname}.")
        self._name = newname

    def setDescription(self, description):
        """
        Set a text description of the case.
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
        if not (0 <= eta <= 1):
            raise ValueError("Fraction must be between 0 and 1.")
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

        self.defaultPlots = self._checkValueType(value)
        self.mylog.vprint(f"Setting plots default value to {value}.")

    def setPlotBackend(self, backend: str):
        """
        Set plotting backend.
        """

        if backend not in ("matplotlib", "plotly"):
            raise ValueError(f"Backend {backend} not a valid option.")

        if backend != self._plotterName:
            self._plotter = PlotFactory.createBackend(backend)
            self._plotterName = backend
            self.mylog.vprint(f"Setting plotting backend to {backend}.")

    def setDividendRate(self, mu):
        """
        Set dividend tax rate. Rate is in percent. Default 1.8%.
        """
        if not (0 <= mu <= 5):
            raise ValueError("Rate must be between 0 and 5.")
        mu /= 100
        self.mylog.vprint(f"Dividend tax rate set to {u.pc(mu, f=0)}.")
        self.mu = mu
        self.caseStatus = "modified"

    def setExpirationYearOBBBA(self, yOBBBA):
        """
        Set year at which OBBBA is speculated to expire and rates go back to something like pre-TCJA.
        """
        self.mylog.vprint(f"Setting OBBBA expiration year to {yOBBBA}.")
        self.yOBBBA = yOBBBA
        self.caseStatus = "modified"
        self._adjustedParameters = False

    def setBeneficiaryFractions(self, phi):
        """
        Set fractions of savings accounts that is left to surviving spouse.
        Default is [1, 1, 1] for taxable, tax-deferred, and tax-free accounts.
        """
        if len(phi) != self.N_j:
            raise ValueError(f"Fractions must have {self.N_j} entries.")
        for j in range(self.N_j):
            if not (0 <= phi[j] <= 1):
                raise ValueError("Fractions must be between 0 and 1.")
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
        if not (0 <= nu <= 100):
            raise ValueError("Rate must be between 0 and 100.")
        nu /= 100
        self.mylog.vprint(f"Heirs tax rate on tax-deferred portion of estate set to {u.pc(nu, f=0)}.")
        self.nu = nu
        self.caseStatus = "modified"

    def setPension(self, amounts, ages, indexed=None):
        """
        Set value of pension for each individual and commencement age.
        Units are in $.
        """
        if len(amounts) != self.N_i:
            raise ValueError(f"Amounts must have {self.N_i} entries.")
        if len(ages) != self.N_i:
            raise ValueError(f"Ages must have {self.N_i} entries.")
        if indexed is None:
            indexed = [False] * self.N_i

        self.mylog.vprint("Setting monthly pension of", [u.d(amounts[i]) for i in range(self.N_i)],
                          "at age(s)", [int(ages[i]) for i in range(self.N_i)])

        thisyear = date.today().year
        # Use zero array freshly initialized.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            if amounts[i] != 0:
                # Check if claim age added to birth month falls next year.
                realage = ages[i] + (self.mobs[i] - 1)/12
                iage = int(realage)
                fraction = 1 - (realage % 1.)
                realns = iage - thisyear + self.yobs[i]
                ns = max(0, realns)
                nd = self.horizons[i]
                self.pi_in[i, ns:nd] = amounts[i]
                # Reduce starting year due to birth month. If realns < 0, this has happened already.
                if realns >= 0:
                    self.pi_in[i, ns] *= fraction

        # Convert all to annual numbers.
        self.pi_in *= 12

        self.pensionAmounts = np.array(amounts, dtype=np.int32)
        self.pensionAges = np.array(ages)
        self.pensionIsIndexed = indexed
        self.caseStatus = "modified"
        self._adjustedParameters = False

    def setSocialSecurity(self, pias, ages):
        """
        Set value of social security for each individual and claiming age.

        Note: Social Security benefits are paid in arrears (one month after eligibility).
        The zeta_in array represents when checks actually arrive, not when eligibility starts.
        """
        if len(pias) != self.N_i:
            raise ValueError(f"Principal Insurance Amount must have {self.N_i} entries.")
        if len(ages) != self.N_i:
            raise ValueError(f"Ages must have {self.N_i} entries.")

        # Just make sure we are dealing with arrays if lists were passed.
        pias = np.array(pias, dtype=np.int32)
        ages = np.array(ages)

        fras = socsec.getFRAs(self.yobs)
        spousalBenefits = socsec.getSpousalBenefits(pias)

        self.mylog.vprint(
            "Social security monthly benefits set to", [u.d(pias[i]) for i in range(self.N_i)],
            "at FRAs(s)", [fras[i] for i in range(self.N_i)],
        )
        self.mylog.vprint(
            "Benefits requested to start at age(s)", [ages[i] for i in range(self.N_i)],
        )

        thisyear = date.today().year
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        for i in range(self.N_i):
            # Check if age is in bound.
            bornOnFirstDays = (self.tobs[i] <= 2)

            eligible = 62 if bornOnFirstDays else 62 + 1/12
            if ages[i] < eligible:
                self.mylog.vprint(f"Resetting starting age of {self.inames[i]} to {eligible}.")
                ages[i] = eligible

            # Check if claim age added to birth month falls next year.
            # janage is age with reference to Jan 1 of yob when eligibility starts.
            janage = ages[i] + (self.mobs[i] - 1)/12

            # Social Security benefits are paid in arrears (one month after eligibility).
            # Calculate when payments actually start (checks arrive).
            paymentJanage = janage + 1/12
            paymentIage = int(paymentJanage)
            paymentRealns = self.yobs[i] + paymentIage - thisyear
            ns = max(0, paymentRealns)
            nd = self.horizons[i]
            self.zeta_in[i, ns:nd] = pias[i]
            # Reduce starting year due to month offset. If paymentRealns < 0, this has happened already.
            if paymentRealns >= 0:
                self.zeta_in[i, ns] *= 1 - (paymentJanage % 1.)

            # Increase/decrease PIA due to claiming age.
            self.zeta_in[i, :] *= socsec.getSelfFactor(fras[i], ages[i], bornOnFirstDays)

            # Add spousal benefits if applicable.
            if self.N_i == 2 and spousalBenefits[i] > 0:
                # The latest of the two spouses to claim (eligibility start).
                claimYear = max(self.yobs + (self.mobs - 1)/12 + ages)
                claimAge = claimYear - self.yobs[i] - (self.mobs[i] - 1)/12
                # Spousal benefits are also paid in arrears (one month after eligibility).
                paymentClaimYear = claimYear + 1/12
                ns2 = max(0, int(paymentClaimYear) - thisyear)
                spousalFactor = socsec.getSpousalFactor(fras[i], claimAge, bornOnFirstDays)
                self.zeta_in[i, ns2:nd] += spousalBenefits[i] * spousalFactor
                # Reduce first year of benefit by month offset.
                self.zeta_in[i, ns2] -= spousalBenefits[i] * spousalFactor * (paymentClaimYear % 1.)

        # Switch survivor to spousal survivor benefits.
        # Assumes both deceased and survivor already have claimed last year before passing (at n_d - 1).
        if self.N_i == 2 and self.zeta_in[self.i_d, self.n_d - 1] > self.zeta_in[self.i_s, self.n_d - 1]:
            self.zeta_in[self.i_s, self.n_d : self.horizons[self.i_s]] = self.zeta_in[self.i_d, self.n_d - 1]

        # Convert all to annual numbers.
        self.zeta_in *= 12

        self.ssecAmounts = pias
        self.ssecAges = ages
        self.caseStatus = "modified"
        self._adjustedParameters = False

    def setSpendingProfile(self, profile, percent=60, dip=15, increase=12, delay=0):
        """
        Generate time series for spending profile. Surviving spouse fraction can be specified
        as a second argument. Default value is 60%.
        Dip and increase are percent changes in the smile profile.
        """
        if not (0 <= percent <= 100):
            raise ValueError(f"Survivor value {percent} outside range.")
        if not (0 <= dip <= 100):
            raise ValueError(f"Dip value {dip} outside range.")
        if not (-100 <= increase <= 100):
            raise ValueError(f"Increase value {increase} outside range.")
        if not (0 <= delay <= self.N_n - 2):
            raise ValueError(f"Delay value {delay} outside year range.")

        self.chi = percent / 100

        self.mylog.vprint("Setting", profile, "spending profile.")
        if self.N_i == 2:
            self.mylog.vprint("Securing", u.pc(self.chi, f=0), "of spending amount for surviving spouse.")

        self.xi_n = _genXi_n(profile, self.chi, self.n_d, self.N_n, dip, increase, delay)

        self.spendingProfile = profile
        self.smileDip = dip
        self.smileIncrease = increase
        self.smileDelay = delay
        self.caseStatus = "modified"

    def setReproducible(self, reproducible, seed=None):
        """
        Set whether rates should be reproducible for stochastic methods.
        This should be called before setting rates. It only sets configuration
        and does not regenerate existing rates.

        Args:
            reproducible: Boolean indicating if rates should be reproducible.
            seed: Optional seed value. If None and reproducible is True,
                  generates a new seed from current time. If None and
                  reproducible is False, generates a seed but won't reuse it.
        """
        self.reproducibleRates = bool(reproducible)
        if reproducible:
            if seed is None:
                if self.rateSeed is not None:
                    # Reuse existing seed if available
                    seed = self.rateSeed
                else:
                    # Generate new seed from current time
                    seed = int(time.time() * 1000000) % (2**31)  # Use microseconds, fit in 32-bit int
            self.rateSeed = seed
        else:
            # For non-reproducible rates, clear the seed
            # setRates() will generate a new seed each time it's called
            self.rateSeed = None

    def setRates(self, method, frm=None, to=None, values=None, stdev=None, corr=None, override_reproducible=False):
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

        Note: For stochastic methods, setReproducible() should be called before
        setRates() to set the reproducibility flag and seed. If not called,
        defaults to non-reproducible behavior.

        Args:
            override_reproducible: If True, override reproducibility setting and always generate new rates.
                                 Used by Monte-Carlo runs to ensure different rates each time.
        """
        if frm is not None and to is None:
            to = frm + self.N_n - 1  # 'to' is inclusive.

        # Handle seed for stochastic methods
        if method in ["stochastic", "histochastic"]:
            if self.reproducibleRates and not override_reproducible:
                if self.rateSeed is None:
                    raise RuntimeError("Config error: reproducibleRates is True but rateSeed is None.")

                seed = self.rateSeed
            else:
                # For non-reproducible rates or when overriding reproducibility, generate a new seed from time.
                # This ensures we always have a seed stored in config, but it won't be reused.
                seed = int(time.time() * 1000000) % (2**31)
                if not override_reproducible:
                    self.rateSeed = seed
        else:
            # For non-stochastic methods, seed is not used but we preserve it
            # so that if user switches back to stochastic, their reproducibility settings are maintained.
            seed = None

        dr = rates.Rates(self.mylog, seed=seed)
        self.rateValues, self.rateStdev, self.rateCorr = dr.setMethod(method, frm, to, values, stdev, corr)
        self.rateMethod = method
        self.rateFrm = frm
        self.rateTo = to
        self.tau_kn = dr.genSeries(self.N_n).transpose()
        self.mylog.vprint(f"Generating rate series of {len(self.tau_kn[0])} years using {method} method.")
        if method in ["stochastic", "histochastic"]:
            repro_status = 'reproducible' if self.reproducibleRates else 'non-reproducible'
            self.mylog.vprint(f"Using seed {seed} for {repro_status} rates.")

        # Once rates are selected, (re)build cumulative inflation multipliers.
        self.gamma_n = _genGamma_n(self.tau_kn)
        self._adjustedParameters = False
        self.caseStatus = "modified"

    def regenRates(self, override_reproducible=False):
        """
        Regenerate the rates using the arguments specified during last setRates() call.
        This method is used to regenerate stochastic time series.
        Only stochastic and histochastic methods need regeneration.
        All fixed rate methods (default, optimistic, conservative, user, historical average,
        historical) don't need regeneration as they produce the same values.

        Args:
            override_reproducible: If True, override reproducibility setting and always generate new rates.
                                 Used by Monte-Carlo runs to ensure each run gets different rates.
        """
        # Fixed rate methods don't need regeneration - they produce the same values
        fixed_methods = ["default", "optimistic", "conservative", "user",
                         "historical average", "historical"]
        if self.rateMethod in fixed_methods:
            return

        # Only stochastic methods reach here
        # If reproducibility is enabled and we're not overriding it, don't regenerate
        # (rates should stay the same for reproducibility)
        if self.reproducibleRates and not override_reproducible:
            return

        # Regenerate with new random values
        self.setRates(
            self.rateMethod,
            frm=self.rateFrm,
            to=self.rateTo,
            values=100 * self.rateValues,
            stdev=100 * self.rateStdev,
            corr=self.rateCorr,
            override_reproducible=override_reproducible,
        )

    def setAccountBalances(self, *, taxable, taxDeferred, taxFree, startDate=None, units="k"):
        """
        Three lists containing the balance of all assets in each category for
        each spouse.  For single individuals, these lists will contain only
        one entry. Units are in $k, unless specified otherwise: 'k', 'M', or '1'.
        """
        plurals = ["", "y", "ies"][self.N_i]
        if len(taxable) != self.N_i:
            raise ValueError(f"taxable must have {self.N_i} entr{plurals}.")
        if len(taxDeferred) != self.N_i:
            raise ValueError(f"taxDeferred must have {self.N_i} entr{plurals}.")
        if len(taxFree) != self.N_i:
            raise ValueError(f"taxFree must have {self.N_i} entr{plurals}.")

        fac = u.getUnits(units)
        taxable = u.rescale(taxable, fac)
        taxDeferred = u.rescale(taxDeferred, fac)
        taxFree = u.rescale(taxFree, fac)

        self.bet_ji = np.zeros((self.N_j, self.N_i))
        self.bet_ji[0][:] = taxable
        self.bet_ji[1][:] = taxDeferred
        self.bet_ji[2][:] = taxFree
        self.beta_ij = self.bet_ji.transpose()

        # If none was given, default is to begin plan on today's date.
        self._setStartingDate(startDate)

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
                if len(item) != self.N_i:
                    raise ValueError(f"{item} must have one entry per individual.")
                for i in range(self.N_i):
                    # Initial and final.
                    if len(item[i]) != 2:
                        raise ValueError(f"{item}[{i}] must have 2 lists (initial and final).")
                    for z in range(2):
                        if len(item[i][z]) != self.N_k:
                            raise ValueError(f"{item}[{i}][{z}] must have {self.N_k} entries.")
                        if abs(sum(item[i][z]) - 100) > 0.01:
                            raise ValueError("Sum of percentages must add to 100.")

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
            if len(generic) != self.N_i:
                raise ValueError("generic must have one list per individual.")
            for i in range(self.N_i):
                # Initial and final.
                if len(generic[i]) != 2:
                    raise ValueError(f"generic[{i}] must have 2 lists (initial and final).")
                for z in range(2):
                    if len(generic[i][z]) != self.N_k:
                        raise ValueError(f"generic[{i}][{z}] must have {self.N_k} entries.")
                    if abs(sum(generic[i][z]) - 100) > 0.01:
                        raise ValueError("Sum of percentages must add to 100.")

            for i in range(self.N_i):
                self.mylog.vprint(f"{self.inames[i]}: Setting gliding allocation ratios (%) to {allocType}.")
                self.mylog.vprint(f"\t{generic[i][0]} -> {generic[i][1]}")

            for i in range(self.N_i):
                Nin = self.horizons[i] + 1
                for k in range(self.N_k):
                    start = generic[i][0][k] / 100
                    end = generic[i][1][k] / 100
                    dat = self._interpolator(start, end, Nin)
                    self.alpha_ijkn[i, :, k, :Nin] = dat[:]

            self.boundsAR["generic"] = generic

        elif allocType == "spouses":
            if len(generic) != 2:
                raise ValueError("generic must have 2 entries (initial and final).")
            for z in range(2):
                if len(generic[z]) != self.N_k:
                    raise ValueError(f"generic[{z}] must have {self.N_k} entries.")
                if abs(sum(generic[z]) - 100) > 0.01:
                    raise ValueError("Sum of percentages must add to 100.")

            for i in range(self.N_i):
                Nin = self.horizons[i] + 1
                for k in range(self.N_k):
                    start = generic[0][k] / 100
                    end = generic[1][k] / 100
                    dat = self._interpolator(start, end, Nin)
                    self.alpha_ijkn[i, :, k, :Nin] = dat[:]

            self.boundsAR["generic"] = generic

        self.ARCoord = allocType
        self.caseStatus = "modified"

        self.mylog.vprint(f"Interpolating assets allocation ratios using {self.interpMethod} method.")

    def readContributions(self, filename, filename_for_logging=None):
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

        Parameters
        ----------
        filename : file-like object, str, or dict
            Input file or dictionary of DataFrames
        filename_for_logging : str, optional
            Explicit filename for logging purposes. If provided, this will be used
            in log messages instead of trying to extract it from filename.
        """
        try:
            returned_filename, self.timeLists, self.houseLists = timelists.read(
                filename, self.inames, self.horizons, self.mylog, filename=filename_for_logging
            )
        except Exception as e:
            raise Exception(f"Unsuccessful read of Household Financial Profile: {e}") from e

        # Use filename_for_logging if provided, otherwise use returned filename
        self.timeListsFileName = filename_for_logging if filename_for_logging is not None else returned_filename
        self.setContributions()

        return True

    def setContributions(self, timeLists=None):
        """
        If no argument is given, use the values that have been stored in self.timeLists.
        """
        if timeLists is not None:
            timelists.check(timeLists, self.inames, self.horizons)
            self.timeLists = timeLists

        # Now fill in parameters which are in $.
        for i, iname in enumerate(self.inames):
            h = self.horizons[i]
            self.omega_in[i, :h] = self.timeLists[iname]["anticipated wages"].iloc[5:5+h]
            self.Lambda_in[i, :h] = self.timeLists[iname]["big-ticket items"].iloc[5:5+h]

            # Values for last 5 years of Roth conversion and contributions stored at the end
            # of array and accessed with negative index.
            self.kappa_ijn[i, 0, :h] = self.timeLists[iname]["taxable ctrb"][5:h+5]
            self.kappa_ijn[i, 1, :h] = self.timeLists[iname]["401k ctrb"][5:h+5]
            self.kappa_ijn[i, 1, :h] += self.timeLists[iname]["IRA ctrb"][5:h+5]
            self.kappa_ijn[i, 2, :h] = self.timeLists[iname]["Roth 401k ctrb"][5:h+5]
            self.kappa_ijn[i, 2, :h] += self.timeLists[iname]["Roth IRA ctrb"][5:h+5]
            self.myRothX_in[i, :h] = self.timeLists[iname]["Roth conv"][5:h+5]

            # Last 5 years are at the end of the N_n array.
            self.kappa_ijn[i, 0, -5:] = self.timeLists[iname]["taxable ctrb"][:5]
            self.kappa_ijn[i, 1, -5:] = self.timeLists[iname]["401k ctrb"][:5]
            self.kappa_ijn[i, 1, -5:] += self.timeLists[iname]["IRA ctrb"][:5]
            self.kappa_ijn[i, 2, -5:] = self.timeLists[iname]["Roth 401k ctrb"][:5]
            self.kappa_ijn[i, 2, -5:] += self.timeLists[iname]["Roth IRA ctrb"][:5]
            self.myRothX_in[i, -5:] = self.timeLists[iname]["Roth conv"][:5]

        self.caseStatus = "modified"

        return self.timeLists

    def processDebtsAndFixedAssets(self):
        """
        Process debts and fixed assets from houseLists and populate arrays.
        Should be called after setContributions() and before solve().
        """
        thisyear = date.today().year

        # Process debts
        if "Debts" in self.houseLists and not self.houseLists["Debts"].empty:
            self.debt_payments_n = debts.get_debt_payments_array(
                self.houseLists["Debts"], self.N_n, thisyear
            )
            self.remaining_debt_balance = debts.get_remaining_debt_balance(
                self.houseLists["Debts"], self.N_n, thisyear
            )
        else:
            self.debt_payments_n = np.zeros(self.N_n)
            self.remaining_debt_balance = 0.0

        # Process fixed assets
        if "Fixed Assets" in self.houseLists and not self.houseLists["Fixed Assets"].empty:
            filing_status = "married" if self.N_i == 2 else "single"
            (self.fixed_assets_tax_free_n,
             self.fixed_assets_ordinary_income_n,
             self.fixed_assets_capital_gains_n) = fxasst.get_fixed_assets_arrays(
                self.houseLists["Fixed Assets"], self.N_n, thisyear, filing_status
            )
            # Calculate bequest value for assets with yod past plan end
            self.fixed_assets_bequest_value = fxasst.get_fixed_assets_bequest_value(
                self.houseLists["Fixed Assets"], self.N_n, thisyear
            )
        else:
            self.fixed_assets_tax_free_n = np.zeros(self.N_n)
            self.fixed_assets_ordinary_income_n = np.zeros(self.N_n)
            self.fixed_assets_capital_gains_n = np.zeros(self.N_n)
            self.fixed_assets_bequest_value = 0.0

    def getFixedAssetsBequestValueInTodaysDollars(self):
        """
        Return the fixed assets bequest value in today's dollars.
        This requires rates to be set to calculate gamma_n (inflation factor).

        Returns:
        --------
        float
            Fixed assets bequest value in today's dollars.
            Returns 0.0 if rates not set, gamma_n not calculated, or no fixed assets.
        """
        if self.fixed_assets_bequest_value == 0.0:
            return 0.0

        # Check if we can calculate gamma_n
        if self.rateMethod is None or not hasattr(self, 'tau_kn'):
            # Rates not set yet - return 0
            return 0.0

        # Calculate gamma_n if not already calculated
        if not hasattr(self, 'gamma_n') or self.gamma_n is None:
            self.gamma_n = _genGamma_n(self.tau_kn)

        # Convert: today's dollars = nominal dollars / inflation_factor
        return self.fixed_assets_bequest_value / self.gamma_n[-1]

    def saveContributions(self):
        """
        Return workbook on wages and contributions, including Debts and Fixed Assets.
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

        # Add Debts sheet if available
        if "Debts" in self.houseLists and not self.houseLists["Debts"].empty:
            ws = wb.create_sheet("Debts")
            df = self.houseLists["Debts"]
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)
            _formatDebtsSheet(ws)
        else:
            # Create empty Debts sheet with proper columns
            ws = wb.create_sheet("Debts")
            df = pd.DataFrame(columns=timelists._debtItems)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)
            _formatDebtsSheet(ws)

        # Add Fixed Assets sheet if available
        if "Fixed Assets" in self.houseLists and not self.houseLists["Fixed Assets"].empty:
            ws = wb.create_sheet("Fixed Assets")
            df = self.houseLists["Fixed Assets"]
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)
            _formatFixedAssetsSheet(ws)
        else:
            # Create empty Fixed Assets sheet with proper columns
            ws = wb.create_sheet("Fixed Assets")
            df = pd.DataFrame(columns=timelists._fixedAssetItems)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)
            _formatFixedAssetsSheet(ws)

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
            df = pd.DataFrame(0, index=np.arange(0, h+5), columns=cols)
            df["year"] = np.arange(self.year_n[0] - 5, self.year_n[h-1]+1)
            self.timeLists[iname] = df

        self.caseStatus = "modified"

        return self.timeLists

    def _linInterp(self, a, b, numPoints):
        """
        Utility function to interpolate allocations using
        a linear interpolation.
        """
        # num goes one more year as endpoint=True.
        return np.linspace(a, b, numPoints)

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

    def _adjustParameters(self, gamma_n, MAGI_n):
        """
        Adjust parameters that follow inflation or depend on MAGI.
        Separate variables depending on MAGI (exemptions now depends on MAGI).
        """
        if self.rateMethod is None:
            raise RuntimeError("A rate method needs to be first selected using setRates(...).")

        self.sigmaBar_n, self.theta_tn, self.Delta_tn = tx.taxParams(self.yobs, self.i_d, self.n_d,
                                                                     self.N_n, gamma_n,
                                                                     MAGI_n, self.yOBBBA)

        if not self._adjustedParameters:
            self.mylog.vprint("Adjusting parameters for inflation.")
            self.DeltaBar_tn = self.Delta_tn * gamma_n[:-1]
            self.zetaBar_in = self.zeta_in * gamma_n[:-1]
            self.xiBar_n = self.xi_n * gamma_n[:-1]
            self.piBar_in = np.array(self.pi_in)
            for i in range(self.N_i):
                if self.pensionIsIndexed[i]:
                    self.piBar_in[i] *= gamma_n[:-1]

            self.nm, self.L_nq, self.C_nq = tx.mediVals(self.yobs, self.horizons, gamma_n, self.N_n, self.N_q)

            self._adjustedParameters = True

        # return None

    def _buildOffsetMap(self, options):
        """
        Utility function to map variables to a block vector.
        Refer to companion document for explanations.
        All binary variables must be lumped at the end of the vector.
        """
        medi = options.get("withMedicare", "loop") == "optimize"

        # Stack all variables in a single block vector with all binary variables at the end.
        C = {}
        C["b"] = 0
        C["d"] = _qC(C["b"], self.N_i, self.N_j, self.N_n + 1)
        C["e"] = _qC(C["d"], self.N_i, self.N_n)
        C["f"] = _qC(C["e"], self.N_n)
        C["g"] = _qC(C["f"], self.N_t, self.N_n)
        C["m"] = _qC(C["g"], self.N_n)
        C["s"] = _qC(C["m"], self.N_n)
        C["w"] = _qC(C["s"], self.N_n)
        C["x"] = _qC(C["w"], self.N_i, self.N_j, self.N_n)
        C["zx"] = _qC(C["x"], self.N_i, self.N_n)
        C["zm"] = _qC(C["zx"], self.N_i, self.N_n, self.N_zx)
        self.nvars = _qC(C["zm"], self.N_n - self.nm, self.N_q - 1) if medi else C["zm"]
        self.nbins = self.nvars - C["zx"]

        self.C = C
        self.mylog.vprint(
            f"Problem has {len(C)} distinct series, {self.nvars} decision variables (including {self.nbins} binary).")

    def _buildConstraints(self, objective, options):
        """
        Utility function that builds constraint matrix and vectors.
        Refactored for clarity and maintainability.
        """
        # Ensure parameters are adjusted for inflation and MAGI.
        self._adjustParameters(self.gamma_n, self.MAGI_n)

        self.A = abc.ConstraintMatrix(self.nvars)
        self.B = abc.Bounds(self.nvars, self.nbins)

        self._add_rmd_inequalities()
        self._add_tax_bracket_bounds()
        self._add_standard_exemption_bounds()
        self._add_defunct_constraints()
        self._add_roth_conversion_constraints(options)
        self._add_roth_maturation_constraints()
        self._add_withdrawal_limits()
        self._add_conversion_limits()
        self._add_objective_constraints(objective, options)
        self._add_initial_balances()
        self._add_surplus_deposit_linking()
        self._add_account_balance_carryover()
        self._add_net_cash_flow()
        self._add_income_profile()
        self._add_taxable_income()
        self._configure_Medicare_binary_variables(options)
        self._add_Medicare_costs(options)
        self._configure_exclusion_binary_variables(options)
        self._build_objective_vector(objective)

    def _add_rmd_inequalities(self):
        for i in range(self.N_i):
            if self.beta_ij[i, 1] > 0:
                for n in range(self.horizons[i]):
                    rowDic = {
                        _q3(self.C["w"], i, 1, n, self.N_i, self.N_j, self.N_n): 1,
                        _q3(self.C["b"], i, 1, n, self.N_i, self.N_j, self.N_n + 1): -self.rho_in[i, n],
                    }
                    self.A.addNewRow(rowDic, 0, np.inf)

    def _add_tax_bracket_bounds(self):
        for t in range(self.N_t):
            for n in range(self.N_n):
                self.B.setRange(_q2(self.C["f"], t, n, self.N_t, self.N_n), 0, self.DeltaBar_tn[t, n])

    def _add_standard_exemption_bounds(self):
        for n in range(self.N_n):
            self.B.setRange(_q1(self.C["e"], n, self.N_n), 0, self.sigmaBar_n[n])

    def _add_defunct_constraints(self):
        if self.N_i == 2:
            for n in range(self.n_d, self.N_n):
                self.B.setRange(_q2(self.C["d"], self.i_d, n, self.N_i, self.N_n), 0, 0)
                self.B.setRange(_q2(self.C["x"], self.i_d, n, self.N_i, self.N_n), 0, 0)
                for j in range(self.N_j):
                    self.B.setRange(_q3(self.C["w"], self.i_d, j, n, self.N_i, self.N_j, self.N_n), 0, 0)

    def _add_roth_maturation_constraints(self):
        """
        Withdrawals from Roth accounts are subject to the 5-year rule for conversion.
        Conversions and gains are subject to the 5-year rule since conversion.
        Contributions can be withdrawn at any time (without 59.5 penalty) but
        gains on contributions are subject to the 5-year rule since the opening of the account.
        A retainer is put on all conversions and associated gains, and gains on all recent contributions.
        """
        # Assume 10% per year for contributions and conversions for past 5 years.
        # Future years will use the assumed returns.
        oldTau1 = 1.10
        for i in range(self.N_i):
            h = self.horizons[i]
            for n in range(h):
                rhs = 0
                # To add compounded gains to cumulative amounts. Always keep cgains >= 1.
                cgains = 1
                row = self.A.newRow()
                row.addElem(_q3(self.C["b"], i, 2, n, self.N_i, self.N_j, self.N_n + 1), 1)
                row.addElem(_q3(self.C["w"], i, 2, n, self.N_i, self.N_j, self.N_n), -1)
                for dn in range(1, 6):
                    nn = n - dn
                    if nn >= 0:   # Past of future is now or in the future: use variables or parameters.
                        Tau1 = 1 + np.sum(self.alpha_ijkn[i, 2, :, nn] * self.tau_kn[:, nn], axis=0)
                        # Ignore market downs.
                        cgains *= max(1, Tau1)
                        row.addElem(_q2(self.C["x"], i, nn, self.N_i, self.N_n), -cgains)
                        # If a contribution, it has only penalty on gains, not on deposited amount.
                        rhs += (cgains - 1) * self.kappa_ijn[i, 2, nn]
                    else:  # Past of future is in the past:
                        cgains *= oldTau1
                        # Past years are stored at the end of contributions and conversions arrays.
                        # Use negative index to access tail of array.
                        # Past years are stored at the end of arrays, accessed via negative indexing
                        rhs += (cgains - 1) * self.kappa_ijn[i, 2, nn] + cgains * self.myRothX_in[i, nn]

                self.A.addRow(row, rhs, np.inf)

    def _add_roth_conversion_constraints(self, options):
        if "maxRothConversion" in options and options["maxRothConversion"] == "file":
            for i in range(self.N_i):
                for n in range(self.horizons[i]):
                    rhs = self.myRothX_in[i][n]
                    self.B.setRange(_q2(self.C["x"], i, n, self.N_i, self.N_n), rhs, rhs)
        else:
            if "maxRothConversion" in options:
                rhsopt = options["maxRothConversion"]
                if not isinstance(rhsopt, (int, float)):
                    raise ValueError(f"Specified maxRothConversion {rhsopt} is not a number.")

                if rhsopt >= 0:
                    rhsopt *= self.optionsUnits
                    for i in range(self.N_i):
                        for n in range(self.horizons[i]):
                            self.B.setRange(_q2(self.C["x"], i, n, self.N_i, self.N_n), 0, rhsopt + 0.01)

            if "startRothConversions" in options:
                rhsopt = options["startRothConversions"]
                if not isinstance(rhsopt, (int, float)):
                    raise ValueError(f"Specified startRothConversions {rhsopt} is not a number.")
                thisyear = date.today().year
                yearn = max(rhsopt - thisyear, 0)
                for i in range(self.N_i):
                    nstart = min(yearn, self.horizons[i])
                    for n in range(0, nstart):
                        self.B.setRange(_q2(self.C["x"], i, n, self.N_i, self.N_n), 0, 0)

            if "noRothConversions" in options and options["noRothConversions"] != "None":
                rhsopt = options["noRothConversions"]
                try:
                    i_x = self.inames.index(rhsopt)
                except ValueError as e:
                    raise ValueError(f"Unknown individual {rhsopt} for noRothConversions:") from e
                for n in range(self.N_n):
                    self.B.setRange(_q2(self.C["x"], i_x, n, self.N_i, self.N_n), 0, 0)

    def _add_withdrawal_limits(self):
        for i in range(self.N_i):
            for j in [0, 2]:
                for n in range(self.N_n):
                    rowDic = {_q3(self.C["w"], i, j, n, self.N_i, self.N_j, self.N_n): -1,
                              _q3(self.C["b"], i, j, n, self.N_i, self.N_j, self.N_n + 1): 1}
                    self.A.addNewRow(rowDic, 0, np.inf)

    def _add_conversion_limits(self):
        for i in range(self.N_i):
            for n in range(self.N_n):
                rowDic = {
                    _q2(self.C["x"], i, n, self.N_i, self.N_n): -1,
                    _q3(self.C["w"], i, 1, n, self.N_i, self.N_j, self.N_n): -1,
                    _q3(self.C["b"], i, 1, n, self.N_i, self.N_j, self.N_n + 1): 1,
                }
                self.A.addNewRow(rowDic, 0, np.inf)

    def _add_objective_constraints(self, objective, options):
        if objective == "maxSpending":
            if "bequest" in options:
                bequest = options["bequest"]
                if not isinstance(bequest, (int, float)):
                    raise ValueError(f"Desired bequest {bequest} is not a number.")
                bequest *= self.optionsUnits * self.gamma_n[-1]
            else:
                bequest = 1

            # Bequest constraint now refers only to savings accounts
            # User specifies desired bequest from accounts (fixed assets are separate)
            # Total bequest = accounts - debts + fixed_assets
            # So: accounts >= desired_bequest_from_accounts + debts
            # (fixed_assets are added separately in the total bequest calculation)
            total_bequest_value = bequest + self.remaining_debt_balance

            row = self.A.newRow()
            for i in range(self.N_i):
                row.addElem(_q3(self.C["b"], i, 0, self.N_n, self.N_i, self.N_j, self.N_n + 1), 1)
                row.addElem(_q3(self.C["b"], i, 1, self.N_n, self.N_i, self.N_j, self.N_n + 1), 1 - self.nu)
                row.addElem(_q3(self.C["b"], i, 2, self.N_n, self.N_i, self.N_j, self.N_n + 1), 1)
            self.A.addRow(row, total_bequest_value, total_bequest_value)
        elif objective == "maxBequest":
            spending = options["netSpending"]
            if not isinstance(spending, (int, float)):
                raise ValueError(f"Desired spending provided {spending} is not a number.")
            spending *= self.optionsUnits
            self.B.setRange(_q1(self.C["g"], 0, self.N_n), spending, spending)

    def _add_initial_balances(self):
        # Back project balances to the beginning of the year.
        yearSpent = 1 - self.yearFracLeft

        for i in range(self.N_i):
            for j in range(self.N_j):
                backTau = 1 + yearSpent * np.sum(self.tau_kn[:, 0] * self.alpha_ijkn[i, j, :, 0])
                rhs = self.beta_ij[i, j] / backTau
                self.B.setRange(_q3(self.C["b"], i, j, 0, self.N_i, self.N_j, self.N_n + 1), rhs, rhs)

    def _add_surplus_deposit_linking(self):
        for i in range(self.N_i):
            fac1 = u.krond(i, 0) * (1 - self.eta) + u.krond(i, 1) * self.eta
            for n in range(self.n_d):
                rowDic = {_q2(self.C["d"], i, n, self.N_i, self.N_n): 1, _q1(self.C["s"], n, self.N_n): -fac1}
                self.A.addNewRow(rowDic, 0, 0)
            fac2 = u.krond(self.i_s, i)
            for n in range(self.n_d, self.N_n):
                rowDic = {_q2(self.C["d"], i, n, self.N_i, self.N_n): 1, _q1(self.C["s"], n, self.N_n): -fac2}
                self.A.addNewRow(rowDic, 0, 0)
        # Prevent surplus on last year.
        self.B.setRange(_q1(self.C["s"], self.N_n - 1, self.N_n), 0, 0)

    def _add_account_balance_carryover(self):
        tau_ijn = np.zeros((self.N_i, self.N_j, self.N_n))
        for i in range(self.N_i):
            for j in range(self.N_j):
                for n in range(self.N_n):
                    tau_ijn[i, j, n] = np.sum(self.alpha_ijkn[i, j, :, n] * self.tau_kn[:, n], axis=0)

        # Weights are normalized on k: sum_k[alpha*(1 + tau)] = 1 + sum_k[alpha*tau]
        Tau1_ijn = 1 + tau_ijn
        Tauh_ijn = 1 + tau_ijn / 2

        for i in range(self.N_i):
            for j in range(self.N_j):
                for n in range(self.N_n):
                    if self.N_i == 2 and self.n_d < self.N_n and i == self.i_d and n == self.n_d - 1:
                        fac1 = 0
                    else:
                        fac1 = 1

                    rhs = fac1 * self.kappa_ijn[i, j, n] * Tauh_ijn[i, j, n]

                    row = self.A.newRow()
                    row.addElem(_q3(self.C["b"], i, j, n + 1, self.N_i, self.N_j, self.N_n + 1), 1)
                    row.addElem(_q3(self.C["b"], i, j, n, self.N_i, self.N_j, self.N_n + 1), -fac1 * Tau1_ijn[i, j, n])
                    row.addElem(_q3(self.C["w"], i, j, n, self.N_i, self.N_j, self.N_n), fac1 * Tau1_ijn[i, j, n])
                    row.addElem(_q2(self.C["d"], i, n, self.N_i, self.N_n), -fac1 * u.krond(j, 0) * Tau1_ijn[i, 0, n])
                    row.addElem(
                        _q2(self.C["x"], i, n, self.N_i, self.N_n),
                        -fac1 * (self.xnet * u.krond(j, 2) - u.krond(j, 1)) * Tau1_ijn[i, j, n],
                    )

                    if self.N_i == 2 and self.n_d < self.N_n and i == self.i_s and n == self.n_d - 1:
                        fac2 = self.phi_j[j]
                        rhs += fac2 * self.kappa_ijn[self.i_d, j, n] * Tauh_ijn[self.i_d, j, n]
                        row.addElem(_q3(self.C["b"], self.i_d, j, n, self.N_i, self.N_j, self.N_n + 1),
                                    -fac2 * Tau1_ijn[self.i_d, j, n])
                        row.addElem(_q3(self.C["w"], self.i_d, j, n, self.N_i, self.N_j, self.N_n),
                                    fac2 * Tau1_ijn[self.i_d, j, n])
                        row.addElem(_q2(self.C["d"], self.i_d, n, self.N_i, self.N_n),
                                    -fac2 * u.krond(j, 0) * Tau1_ijn[self.i_d, 0, n])
                        row.addElem(
                            _q2(self.C["x"], self.i_d, n, self.N_i, self.N_n),
                            -fac2 * (self.xnet * u.krond(j, 2) - u.krond(j, 1)) * Tau1_ijn[self.i_d, j, n],
                        )
                    self.A.addRow(row, rhs, rhs)

    def _add_net_cash_flow(self):
        tau_0prev = np.roll(self.tau_kn[0, :], 1)
        tau_0prev[tau_0prev < 0] = 0
        for n in range(self.N_n):
            rhs = -self.M_n[n] - self.J_n[n]
            # Add fixed assets tax-free money (positive cash flow)
            rhs += self.fixed_assets_tax_free_n[n]
            # Subtract debt payments (negative cash flow)
            rhs -= self.debt_payments_n[n]
            row = self.A.newRow({_q1(self.C["g"], n, self.N_n): 1})
            row.addElem(_q1(self.C["s"], n, self.N_n), 1)
            row.addElem(_q1(self.C["m"], n, self.N_n), 1)
            for i in range(self.N_i):
                fac = self.psi_n[n] * self.alpha_ijkn[i, 0, 0, n]
                rhs += (
                    self.omega_in[i, n]
                    + self.zetaBar_in[i, n]
                    + self.piBar_in[i, n]
                    + self.Lambda_in[i, n]
                    - 0.5 * fac * self.mu * self.kappa_ijn[i, 0, n]
                )
                row.addElem(_q3(self.C["b"], i, 0, n, self.N_i, self.N_j, self.N_n + 1), fac * self.mu)
                row.addElem(_q3(self.C["w"], i, 0, n, self.N_i, self.N_j, self.N_n), fac * (tau_0prev[n] - self.mu) - 1)
                penalty = 0.1 if n < self.n59[i] else 0
                row.addElem(_q3(self.C["w"], i, 1, n, self.N_i, self.N_j, self.N_n), -1 + penalty)
                row.addElem(_q3(self.C["w"], i, 2, n, self.N_i, self.N_j, self.N_n), -1 + penalty)
                row.addElem(_q2(self.C["d"], i, n, self.N_i, self.N_n), fac * self.mu)

            for t in range(self.N_t):
                row.addElem(_q2(self.C["f"], t, n, self.N_t, self.N_n), self.theta_tn[t, n])

            self.A.addRow(row, rhs, rhs)

    def _add_income_profile(self):
        spLo = 1 - self.lambdha
        spHi = 1 + self.lambdha
        for n in range(1, self.N_n):
            rowDic = {_q1(self.C["g"], 0, self.N_n): spLo * self.xiBar_n[n],
                      _q1(self.C["g"], n, self.N_n): -self.xiBar_n[0]}
            self.A.addNewRow(rowDic, -np.inf, 0)
            rowDic = {_q1(self.C["g"], 0, self.N_n): spHi * self.xiBar_n[n],
                      _q1(self.C["g"], n, self.N_n): -self.xiBar_n[0]}
            self.A.addNewRow(rowDic, 0, np.inf)

    def _add_taxable_income(self):
        for n in range(self.N_n):
            # Add fixed assets ordinary income
            rhs = self.fixed_assets_ordinary_income_n[n]
            row = self.A.newRow()
            row.addElem(_q1(self.C["e"], n, self.N_n), 1)
            for i in range(self.N_i):
                rhs += self.omega_in[i, n] + 0.85 * self.zetaBar_in[i, n] + self.piBar_in[i, n]
                row.addElem(_q3(self.C["w"], i, 1, n, self.N_i, self.N_j, self.N_n), -1)
                row.addElem(_q2(self.C["x"], i, n, self.N_i, self.N_n), -1)
                fak = np.sum(self.tau_kn[1:self.N_k, n] * self.alpha_ijkn[i, 0, 1:self.N_k, n], axis=0)
                rhs += 0.5 * fak * self.kappa_ijn[i, 0, n]
                row.addElem(_q3(self.C["b"], i, 0, n, self.N_i, self.N_j, self.N_n + 1), -fak)
                row.addElem(_q3(self.C["w"], i, 0, n, self.N_i, self.N_j, self.N_n), fak)
                row.addElem(_q2(self.C["d"], i, n, self.N_i, self.N_n), -fak)
            for t in range(self.N_t):
                row.addElem(_q2(self.C["f"], t, n, self.N_t, self.N_n), 1)
            self.A.addRow(row, rhs, rhs)

    def _configure_exclusion_binary_variables(self, options):
        if not options.get("xorConstraints", True):
            return

        bigM = options.get("bigM", 5e6)
        if not isinstance(bigM, (int, float)):
            raise ValueError(f"bigM {bigM} is not a number.")

        for i in range(self.N_i):
            for n in range(self.horizons[i]):
                self.A.addNewRow(
                    {_q3(self.C["zx"], i, n, 0, self.N_i, self.N_n, self.N_zx): bigM,
                     _q1(self.C["s"], n, self.N_n): -1},
                    0,
                    bigM,
                )
                self.A.addNewRow(
                    {
                        _q3(self.C["zx"], i, n, 0, self.N_i, self.N_n, self.N_zx): bigM,
                        _q3(self.C["w"], i, 0, n, self.N_i, self.N_j, self.N_n): 1,
                        _q3(self.C["w"], i, 2, n, self.N_i, self.N_j, self.N_n): 1,
                    },
                    0,
                    bigM,
                )
                self.A.addNewRow(
                    {_q3(self.C["zx"], i, n, 1, self.N_i, self.N_n, self.N_zx): bigM,
                     _q2(self.C["x"], i, n, self.N_i, self.N_n): -1},
                    0,
                    bigM,
                )
                self.A.addNewRow(
                    {_q3(self.C["zx"], i, n, 1, self.N_i, self.N_n, self.N_zx): bigM,
                     _q3(self.C["w"], i, 2, n, self.N_i, self.N_j, self.N_n): 1},
                    0,
                    bigM,
                )
            for n in range(self.horizons[i], self.N_n):
                self.B.setRange(_q3(self.C["zx"], i, n, 0, self.N_i, self.N_n, self.N_zx), 0, 0)
                self.B.setRange(_q3(self.C["zx"], i, n, 1, self.N_i, self.N_n, self.N_zx), 0, 0)

    def _configure_Medicare_binary_variables(self, options):
        if options.get("withMedicare", "loop") != "optimize":
            return

        bigM = options.get("bigM", 5e6)
        if not isinstance(bigM, (int, float)):
            raise ValueError(f"bigM {bigM} is not a number.")

        Nmed = self.N_n - self.nm
        offset = 0
        if self.nm < 2:
            offset = 2 - self.nm
            for nn in range(offset):
                n = self.nm + nn
                for q in range(self.N_q - 1):
                    self.A.addNewRow({_q2(self.C["zm"], nn, q, Nmed, self.N_q - 1): bigM},
                                     -np.inf, bigM - self.L_nq[nn, q] + self.prevMAGI[n])
                    self.A.addNewRow({_q2(self.C["zm"], nn, q, Nmed, self.N_q - 1): -bigM},
                                     -np.inf, self.L_nq[nn, q] - self.prevMAGI[n])

        for nn in range(offset, Nmed):
            n2 = self.nm + nn - 2  # n - 2
            for q in range(self.N_q - 1):
                rhs1 = bigM - self.L_nq[nn, q]
                rhs2 = self.L_nq[nn, q]
                row1 = self.A.newRow()
                row2 = self.A.newRow()

                row1.addElem(_q2(self.C["zm"], nn, q, Nmed, self.N_q - 1), +bigM)
                row2.addElem(_q2(self.C["zm"], nn, q, Nmed, self.N_q - 1), -bigM)
                for i in range(self.N_i):
                    row1.addElem(_q3(self.C["w"], i, 1, n2, self.N_i, self.N_j, self.N_n), -1)
                    row2.addElem(_q3(self.C["w"], i, 1, n2, self.N_i, self.N_j, self.N_n), +1)

                    row1.addElem(_q2(self.C["x"], i, n2, self.N_i, self.N_n), -1)
                    row2.addElem(_q2(self.C["x"], i, n2, self.N_i, self.N_n), +1)

                    # Dividends and interest gains for year n2.
                    afac = (self.mu*self.alpha_ijkn[i, 0, 0, n2]
                            + np.sum(self.alpha_ijkn[i, 0, 1:, n2]*self.tau_kn[1:, n2]))

                    row1.addElem(_q3(self.C["b"], i, 0, n2, self.N_i, self.N_j, self.N_n + 1), -afac)
                    row2.addElem(_q3(self.C["b"], i, 0, n2, self.N_i, self.N_j, self.N_n + 1), +afac)

                    row1.addElem(_q2(self.C["d"], i, n2, self.N_i, self.N_n), -afac)
                    row2.addElem(_q2(self.C["d"], i, n2, self.N_i, self.N_n), +afac)

                    # Capital gains on stocks sold from taxable account accrued in year n2 - 1.
                    bfac = self.alpha_ijkn[i, 0, 0, n2] * max(0, self.tau_kn[0, max(0, n2-1)])

                    row1.addElem(_q3(self.C["w"], i, 0, n2, self.N_i, self.N_j, self.N_n), +afac - bfac)
                    row2.addElem(_q3(self.C["w"], i, 0, n2, self.N_i, self.N_j, self.N_n), -afac + bfac)

                    sumoni = (self.omega_in[i, n2] + self.psi_n[n2] * self.zetaBar_in[i, n2] + self.piBar_in[i, n2]
                              + 0.5 * self.kappa_ijn[i, 0, n2] * afac)
                    rhs1 += sumoni
                    rhs2 -= sumoni

                self.A.addRow(row1, -np.inf, rhs1)
                self.A.addRow(row2, -np.inf, rhs2)

    def _add_Medicare_costs(self, options):
        if options.get("withMedicare", "loop") != "optimize":
            return

        for n in range(self.nm):
            self.B.setRange(_q1(self.C["m"], n, self.N_n), 0, 0)

        Nmed = self.N_n - self.nm
        for nn in range(Nmed):
            n = self.nm + nn
            row = self.A.newRow()
            row.addElem(_q1(self.C["m"], n, self.N_n), 1)
            for q in range(self.N_q - 1):
                row.addElem(_q2(self.C["zm"], nn, q, Nmed, self.N_q - 1), -self.C_nq[nn, q+1])
            self.A.addRow(row, self.C_nq[nn, 0], self.C_nq[nn, 0])

    def _build_objective_vector(self, objective):
        c = abc.Objective(self.nvars)
        if objective == "maxSpending":
            for n in range(self.N_n):
                c.setElem(_q1(self.C["g"], n, self.N_n), -1/self.gamma_n[n])
        elif objective == "maxBequest":
            for i in range(self.N_i):
                c.setElem(_q3(self.C["b"], i, 0, self.N_n, self.N_i, self.N_j, self.N_n + 1), -1)
                c.setElem(_q3(self.C["b"], i, 1, self.N_n, self.N_i, self.N_j, self.N_n + 1), -(1 - self.nu))
                c.setElem(_q3(self.C["b"], i, 2, self.N_n, self.N_i, self.N_j, self.N_n + 1), -1)
        else:
            raise RuntimeError("Internal error in objective function.")
        self.c = c

    @_timer
    def runHistoricalRange(self, objective, options, ystart, yend, *, verbose=False, figure=False, progcall=None):
        """
        Run historical scenarios on plan over a range of years.
        """

        if yend + self.N_n > self.year_n[0]:
            yend = self.year_n[0] - self.N_n - 1
            self.mylog.vprint(f"Warning: Upper bound for year range re-adjusted to {yend}.")

        if yend < ystart:
            raise ValueError(f"Starting year is too large to support a lifespan of {self.N_n} years.")

        N = yend - ystart + 1
        self.mylog.vprint(f"Running historical range from {ystart} to {yend}.")

        self.mylog.setVerbose(verbose)

        if objective == "maxSpending":
            columns = ["partial", objective]
        elif objective == "maxBequest":
            columns = ["partial", "final"]
        else:
            self.mylog.print(f"Invalid objective {objective}.")
            raise ValueError(f"Invalid objective {objective}.")

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

        fig, description = self._plotter.plot_histogram_results(objective, df, N, self.year_n,
                                                                self.n_d, self.N_i, self.phi_j)
        self.mylog.print(description.getvalue())

        if figure:
            return fig, description.getvalue()

        return N, df

    @_timer
    def runMC(self, objective, options, N, verbose=False, figure=False, progcall=None):
        """
        Run Monte Carlo simulations on plan.
        """
        if self.rateMethod not in ("stochastic", "histochastic"):
            self.mylog.print("It is pointless to run Monte Carlo simulations with fixed rates.")
            return

        self.mylog.vprint(f"Running {N} Monte Carlo simulations.")
        self.mylog.setVerbose(verbose)

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
            self.regenRates(override_reproducible=True)
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

        fig, description = self._plotter.plot_histogram_results(objective, df, N, self.year_n,
                                                                self.n_d, self.N_i, self.phi_j)
        self.mylog.print(description.getvalue())

        if figure:
            return fig, description.getvalue()

        return N, df

    def resolve(self):
        """
        Solve a plan using saved options.
        """
        self.solve(self.objective, self.solverOptions)

        return None

    @_checkConfiguration
    @_timer
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
            raise RuntimeError("Rate method must be selected before solving.")

        # Assume unsuccessful until problem solved.
        self.caseStatus = "unsuccessful"

        # Check objective and required options.
        knownObjectives = ["maxBequest", "maxSpending"]
        knownSolvers = ["HiGHS", "PuLP/CBC", "PuLP/HiGHS", "MOSEK"]

        knownOptions = [
            "bequest",
            "bigM",
            "maxRothConversion",
            "netSpending",
            "noRothConversions",
            "oppCostX",
            "withMedicare",
            "previousMAGIs",
            "solver",
            "spendingSlack",
            "startRothConversions",
            "units",
            "xorConstraints",
            "withSCLoop",
        ]
        # We might modify options if required.
        options = {} if options is None else options
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

        self.optionsUnits = u.getUnits(myoptions.get("units", "k"))

        oppCostX = options.get("oppCostX", 0.)
        self.xnet = 1 - oppCostX / 100.

        self.prevMAGI = np.zeros(2)
        if "previousMAGIs" in myoptions:
            magi = myoptions["previousMAGIs"]
            if len(magi) != 2:
                raise ValueError("previousMAGIs must have 2 values.")

            self.prevMAGI = self.optionsUnits * np.array(magi)

        lambdha = myoptions.get("spendingSlack", 0)
        if not (0 <= lambdha <= 50):
            raise ValueError(f"Slack value out of range {lambdha}.")
        self.lambdha = lambdha / 100

        # Reset long-term capital gain tax rate and MAGI to zero.
        self.psi_n = np.zeros(self.N_n)
        self.MAGI_n = np.zeros(self.N_n)
        self.J_n = np.zeros(self.N_n)
        self.M_n = np.zeros(self.N_n)

        self._adjustParameters(self.gamma_n, self.MAGI_n)
        self._buildOffsetMap(options)

        # Process debts and fixed assets
        self.processDebtsAndFixedAssets()

        solver = myoptions.get("solver", self.defaultSolver)
        if solver not in knownSolvers:
            raise ValueError(f"Unknown solver {solver}.")

        if solver == "HiGHS":
            solverMethod = self._milpSolve
        elif solver == "MOSEK":
            solverMethod = self._mosekSolve
        elif "PuLP" in solver:
            solverMethod = self._pulpSolve
        else:
            raise RuntimeError("Internal error in defining solverMethod.")

        self.mylog.vprint(f"Using {solver} solver.")
        self._scSolve(objective, options, solverMethod)

        self.objective = objective
        self.solverOptions = myoptions

        return None

    def _scSolve(self, objective, options, solverMethod):
        """
        Self-consistent loop, regardless of solver.
        """
        includeMedicare = options.get("withMedicare", "loop") == "loop"
        withSCLoop = options.get("withSCLoop", True)

        if objective == "maxSpending":
            objFac = -1 / self.xi_n[0]
        else:
            objFac = -1 / self.gamma_n[-1]

        it = 0
        old_x = np.zeros(self.nvars)
        old_objfns = [np.inf]
        self._computeNLstuff(None, includeMedicare)
        while True:
            objfn, xx, solverSuccess, solverMsg = solverMethod(objective, options)

            if not solverSuccess or objfn is None:
                self.mylog.vprint("Solver failed:", solverMsg, solverSuccess)
                break

            if not withSCLoop:
                break

            self._computeNLstuff(xx, includeMedicare)

            delta = xx - old_x
            absSolDiff = np.sum(np.abs(delta), axis=0)/100
            absObjDiff = abs(objFac*(objfn + old_objfns[-1]))/100
            self.mylog.vprint(f"Iteration: {it} objective: {u.d(objfn * objFac, f=2)},"
                              f" |dX|: {absSolDiff:.2f}, |df|: {u.d(absObjDiff, f=2)}")

            # 50 cents accuracy.
            if absSolDiff < .5 and absObjDiff < .5:
                self.mylog.vprint("Converged on full solution.")
                break

            # Avoid oscillatory solutions. Look only at most recent solutions. Within $10.
            isclosenough = abs(-objfn - min(old_objfns[int(it / 2) :])) < 10 * self.xi_n[0]
            if isclosenough:
                self.mylog.vprint("Converged through selecting minimum oscillating objective.")
                break

            if it > 59:
                self.mylog.vprint("WARNING: Exiting loop on maximum iterations.")
                break

            it += 1
            old_objfns.append(-objfn)
            old_x = xx

        if solverSuccess:
            self.mylog.vprint(f"Self-consistent loop returned after {it+1} iterations.")
            self.mylog.vprint(solverMsg)
            self.mylog.vprint(f"Objective: {u.d(objfn * objFac)}")
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

        # Optimize solver parameters
        milpOptions = {
            "disp": False,
            "mip_rel_gap": 1e-7,
            "presolve": True,
            "node_limit": 1000000  # Limit search nodes for faster solutions
        }

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
                raise RuntimeError(f"Internal error: Variable with weird bound {vkeys[i]}.")

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

        if "HiGHS" in options["solver"]:
            solver = pulp.getSolver("HiGHS", msg=False)
        else:
            solver = pulp.getSolver("PULP_CBC_CMD", msg=False)

        prob.solve(solver)

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

    def _computeNLstuff(self, x, includeMedicare):
        """
        Compute MAGI, Medicare costs, long-term capital gain tax rate, and
        net investment income tax (NIIT).
        """
        if x is None:
            self.MAGI_n = np.zeros(self.N_n)
            self.J_n = np.zeros(self.N_n)
            self.M_n = np.zeros(self.N_n)
            self.psi_n = np.zeros(self.N_n)
            return

        self._aggregateResults(x, short=True)

        self.J_n = tx.computeNIIT(self.N_i, self.MAGI_n, self.I_n, self.Q_n, self.n_d, self.N_n)
        self.psi_n = tx.capitalGainTaxRate(self.N_i, self.MAGI_n, self.gamma_n[:-1], self.n_d, self.N_n)
        # Compute Medicare through self-consistent loop.
        if includeMedicare:
            self.M_n = tx.mediCosts(self.yobs, self.horizons, self.MAGI_n, self.prevMAGI, self.gamma_n[:-1], self.N_n)

        return None

    def _aggregateResults(self, x, short=False):
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
        # Nzx = self.N_zx
        n_d = self.n_d

        Cb = self.C["b"]
        Cd = self.C["d"]
        Ce = self.C["e"]
        Cf = self.C["f"]
        Cg = self.C["g"]
        Cm = self.C["m"]
        Cs = self.C["s"]
        Cw = self.C["w"]
        Cx = self.C["x"]
        Czx = self.C["zx"]

        x = u.roundCents(x)

        # Allocate, slice in, and reshape variables.
        self.b_ijn = np.array(x[Cb:Cd])
        self.b_ijn = self.b_ijn.reshape((Ni, Nj, Nn + 1))
        self.b_ijkn = np.zeros((Ni, Nj, Nk, Nn + 1))
        for k in range(Nk):
            self.b_ijkn[:, :, k, :] = self.b_ijn[:, :, :] * self.alpha_ijkn[:, :, k, :]

        self.d_in = np.array(x[Cd:Ce])
        self.d_in = self.d_in.reshape((Ni, Nn))

        self.e_n = np.array(x[Ce:Cf])

        self.f_tn = np.array(x[Cf:Cg])
        self.f_tn = self.f_tn.reshape((Nt, Nn))

        self.g_n = np.array(x[Cg:Cm])

        self.m_n = np.array(x[Cm:Cs])

        self.s_n = np.array(x[Cs:Cw])

        self.w_ijn = np.array(x[Cw:Cx])
        self.w_ijn = self.w_ijn.reshape((Ni, Nj, Nn))

        self.x_in = np.array(x[Cx:Czx])
        self.x_in = self.x_in.reshape((Ni, Nn))

        # self.z_inz = np.array(x[Czx:])
        # self.z_inz = self.z_inz.reshape((Ni, Nn, Nzx))
        # print(self.z_inz)

        self.G_n = np.sum(self.f_tn, axis=0)

        tau_0 = np.array(self.tau_kn[0, :])
        tau_0[tau_0 < 0] = 0
        # Last year's rates.
        tau_0prev = np.roll(tau_0, 1)
        self.Q_n = np.sum(
            (
                self.mu
                * (self.b_ijn[:, 0, :Nn] - self.w_ijn[:, 0, :] + self.d_in[:, :] + 0.5 * self.kappa_ijn[:, 0, :Nn])
                + tau_0prev * self.w_ijn[:, 0, :]
            )
            * self.alpha_ijkn[:, 0, 0, :Nn],
            axis=0,
        )
        # Add fixed assets capital gains
        self.Q_n += self.fixed_assets_capital_gains_n
        self.U_n = self.psi_n * self.Q_n

        self.MAGI_n = self.G_n + self.e_n + self.Q_n

        I_in = ((self.b_ijn[:, 0, :-1] + self.d_in - self.w_ijn[:, 0, :])
                * np.sum(self.alpha_ijkn[:, 0, 1:, :Nn] * self.tau_kn[1:, :], axis=1))
        self.I_n = np.sum(I_in, axis=0)

        # Stop after building minimum required for self-consistent loop.
        if short:
            return

        self.T_tn = self.f_tn * self.theta_tn
        self.T_n = np.sum(self.T_tn, axis=0)
        self.P_n = np.zeros(Nn)
        # Add early withdrawal penalty if any.
        for i in range(Ni):
            self.P_n[0:self.n59[i]] += 0.1*(self.w_ijn[i, 1, 0:self.n59[i]] + self.w_ijn[i, 2, 0:self.n59[i]])

        self.T_n += self.P_n
        # Compute partial distribution at the passing of first spouse.
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
        # Debts and fixed assets (debts are negative as expenses)
        # Show as household totals, not split between individuals
        # Reshape to (1, N_n) to indicate household-level source
        sources["FA ord inc"] = self.fixed_assets_ordinary_income_n.reshape(1, -1)
        sources["FA cap gains"] = self.fixed_assets_capital_gains_n.reshape(1, -1)
        sources["FA tax-free"] = self.fixed_assets_tax_free_n.reshape(1, -1)
        sources["debt pmts"] = -self.debt_payments_n.reshape(1, -1)

        savings = {}
        savings["taxable"] = self.b_ijn[:, 0, :]
        savings["tax-deferred"] = self.b_ijn[:, 1, :]
        savings["tax-free"] = self.b_ijn[:, 2, :]

        self.sources_in = sources
        self.savings_in = savings

        estate_j = np.sum(self.b_ijn[:, :, self.N_n], axis=0)
        estate_j[1] *= 1 - self.nu
        # Subtract remaining debt balance from estate
        total_estate = np.sum(estate_j) - self.remaining_debt_balance
        self.bequest = max(0.0, total_estate) / self.gamma_n[-1]

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
        dic["Case name"] = self._name
        dic["Net yearly spending basis" + 26*" ."] = u.d(self.g_n[0] / self.xi_n[0])
        dic[f"Net spending for year {now}"] = u.d(self.g_n[0])
        dic[f"Net spending remaining in year {now}"] = u.d(self.g_n[0] * self.yearFracLeft)

        totSpending = np.sum(self.g_n, axis=0)
        totSpendingNow = np.sum(self.g_n / self.gamma_n[:-1], axis=0)
        dic[" Total net spending"] = f"{u.d(totSpendingNow)}"
        dic["[Total net spending]"] = f"{u.d(totSpending)}"

        totRoth = np.sum(self.x_in, axis=(0, 1))
        totRothNow = np.sum(np.sum(self.x_in, axis=0) / self.gamma_n[:-1], axis=0)
        dic[" Total Roth conversions"] = f"{u.d(totRothNow)}"
        dic["[Total Roth conversions]"] = f"{u.d(totRoth)}"

        taxPaid = np.sum(self.T_n, axis=0)
        taxPaidNow = np.sum(self.T_n / self.gamma_n[:-1], axis=0)
        dic[" Total tax paid on ordinary income"] = f"{u.d(taxPaidNow)}"
        dic["[Total tax paid on ordinary income]"] = f"{u.d(taxPaid)}"
        for t in range(self.N_t):
            taxPaid = np.sum(self.T_tn[t], axis=0)
            taxPaidNow = np.sum(self.T_tn[t] / self.gamma_n[:-1], axis=0)
            if t >= len(tx.taxBracketNames):
                tname = f"Bracket {t}"
            else:
                tname = tx.taxBracketNames[t]
            dic[f"»  Subtotal in tax bracket {tname}"] = f"{u.d(taxPaidNow)}"
            dic[f"» [Subtotal in tax bracket {tname}]"] = f"{u.d(taxPaid)}"

        penaltyPaid = np.sum(self.P_n, axis=0)
        penaltyPaidNow = np.sum(self.P_n / self.gamma_n[:-1], axis=0)
        dic["»  Subtotal in early withdrawal penalty"] = f"{u.d(penaltyPaidNow)}"
        dic["» [Subtotal in early withdrawal penalty]"] = f"{u.d(penaltyPaid)}"

        taxPaid = np.sum(self.U_n, axis=0)
        taxPaidNow = np.sum(self.U_n / self.gamma_n[:-1], axis=0)
        dic[" Total tax paid on gains and dividends"] = f"{u.d(taxPaidNow)}"
        dic["[Total tax paid on gains and dividends]"] = f"{u.d(taxPaid)}"

        taxPaid = np.sum(self.J_n, axis=0)
        taxPaidNow = np.sum(self.J_n / self.gamma_n[:-1], axis=0)
        dic[" Total net investment income tax paid"] = f"{u.d(taxPaidNow)}"
        dic["[Total net investment income tax paid]"] = f"{u.d(taxPaid)}"

        taxPaid = np.sum(self.m_n + self.M_n, axis=0)
        taxPaidNow = np.sum((self.m_n + self.M_n) / self.gamma_n[:-1], axis=0)
        dic[" Total Medicare premiums paid"] = f"{u.d(taxPaidNow)}"
        dic["[Total Medicare premiums paid]"] = f"{u.d(taxPaid)}"

        totDebtPayments = np.sum(self.debt_payments_n, axis=0)
        if totDebtPayments > 0:
            totDebtPaymentsNow = np.sum(self.debt_payments_n / self.gamma_n[:-1], axis=0)
            dic[" Total debt payments"] = f"{u.d(totDebtPaymentsNow)}"
            dic["[Total debt payments]"] = f"{u.d(totDebtPayments)}"

        if self.N_i == 2 and self.n_d < self.N_n:
            p_j = self.partialEstate_j * (1 - self.phi_j)
            p_j[1] *= 1 - self.nu
            nx = self.n_d - 1
            ynx = self.year_n[nx]
            ynxNow = 1./self.gamma_n[nx + 1]
            totOthers = np.sum(p_j)
            q_j = self.partialEstate_j * self.phi_j
            totSpousal = np.sum(q_j)
            iname_s = self.inames[self.i_s]
            iname_d = self.inames[self.i_d]
            dic["Year of partial bequest"] = f"{ynx}"
            dic[f" Sum of spousal transfer to {iname_s}"] = f"{u.d(ynxNow*totSpousal)}"
            dic[f"[Sum of spousal transfer to {iname_s}]"] = f"{u.d(totSpousal)}"
            dic[f"»  Spousal transfer to {iname_s} - taxable"] = f"{u.d(ynxNow*q_j[0])}"
            dic[f"» [Spousal transfer to {iname_s} - taxable]"] = f"{u.d(q_j[0])}"
            dic[f"»  Spousal transfer to {iname_s} - tax-def"] = f"{u.d(ynxNow*q_j[1])}"
            dic[f"» [Spousal transfer to {iname_s} - tax-def]"] = f"{u.d(q_j[1])}"
            dic[f"»  Spousal transfer to {iname_s} - tax-free"] = f"{u.d(ynxNow*q_j[2])}"
            dic[f"» [Spousal transfer to {iname_s} - tax-free]"] = f"{u.d(q_j[2])}"

            dic[f" Sum of post-tax non-spousal bequest from {iname_d}"] = f"{u.d(ynxNow*totOthers)}"
            dic[f"[Sum of post-tax non-spousal bequest from {iname_d}]"] = f"{u.d(totOthers)}"
            dic[f"»  Post-tax non-spousal bequest from {iname_d} - taxable"] = f"{u.d(ynxNow*p_j[0])}"
            dic[f"» [Post-tax non-spousal bequest from {iname_d} - taxable]"] = f"{u.d(p_j[0])}"
            dic[f"»  Post-tax non-spousal bequest from {iname_d} - tax-def"] = f"{u.d(ynxNow*p_j[1])}"
            dic[f"» [Post-tax non-spousal bequest from {iname_d} - tax-def]"] = f"{u.d(p_j[1])}"
            dic[f"»  Post-tax non-spousal bequest from {iname_d} - tax-free"] = f"{u.d(ynxNow*p_j[2])}"
            dic[f"» [Post-tax non-spousal bequest from {iname_d} - tax-free]"] = f"{u.d(p_j[2])}"

        estate = np.sum(self.b_ijn[:, :, self.N_n], axis=0)
        heirsTaxLiability = estate[1] * self.nu
        estate[1] *= 1 - self.nu
        endyear = self.year_n[-1]
        lyNow = 1./self.gamma_n[-1]
        # Add fixed assets bequest value (assets with yod past plan end)
        debts = self.remaining_debt_balance
        savingsEstate = np.sum(estate)
        totEstate = savingsEstate - debts + self.fixed_assets_bequest_value

        dic["Year of final bequest"] = f"{endyear}"
        dic[" Total after-tax value of final bequest"] = f"{u.d(lyNow*totEstate)}"
        dic["» After-tax value of savings assets"] = f"{u.d(lyNow*savingsEstate)}"
        dic["» Fixed assets liquidated at end of plan"] = f"{u.d(lyNow*self.fixed_assets_bequest_value)}"
        dic["» With heirs assuming tax liability of"] = f"{u.d(lyNow*heirsTaxLiability)}"
        dic["» After paying remaining debts of"] = f"{u.d(lyNow*debts)}"

        dic["[Total after-tax value of final bequest]"] = f"{u.d(totEstate)}"
        dic["[» After-tax value of savings assets]"] = f"{u.d(savingsEstate)}"
        dic["[» Fixed assets liquidated at end of plan]"] = f"{u.d(self.fixed_assets_bequest_value)}"
        dic["[» With heirs assuming tax liability of"] = f"{u.d(heirsTaxLiability)}"
        dic["[» After paying remaining debts of]"] = f"{u.d(debts)}"

        dic["»  Post-tax final bequest account value - taxable"] = f"{u.d(lyNow*estate[0])}"
        dic["» [Post-tax final bequest account value - taxable]"] = f"{u.d(estate[0])}"
        dic["»  Post-tax final bequest account value - tax-def"] = f"{u.d(lyNow*estate[1])}"
        dic["» [Post-tax final bequest account value - tax-def]"] = f"{u.d(estate[1])}"
        dic["»  Post-tax final bequest account value - tax-free"] = f"{u.d(lyNow*estate[2])}"
        dic["» [Post-tax final bequest account value - tax-free]"] = f"{u.d(estate[2])}"

        dic["Case starting date"] = str(self.startDate)
        dic["Cumulative inflation factor at end of final year"] = f"{self.gamma_n[-1]:.2f}"
        for i in range(self.N_i):
            dic[f"{self.inames[i]:>14}'s life horizon"] = f"{now} -> {now + self.horizons[i] - 1}"
            dic[f"{self.inames[i]:>14}'s years planned"] = f"{self.horizons[i]}"

        dic["Case name"] = self._name
        dic["Number of decision variables"] = str(self.A.nvars)
        dic["Number of constraints"] = str(self.A.ncons)
        dic["Case executed on"] = str(self._timestamp)

        return dic

    def showRatesCorrelations(self, tag="", shareRange=False, figure=False):
        """
        Plot correlations between various rates.

        A tag string can be set to add information to the title of the plot.
        """
        if self.rateMethod in [None, "user", "historical average", "conservative"]:
            self.mylog.vprint(f"Warning: Cannot plot correlations for {self.rateMethod} rate method.")
            return None

        # Check if rates are constant (all values are the same for each rate type)
        # This can happen with fixed rates
        if self.tau_kn is not None:
            # Check if all rates are constant (no variation)
            rates_are_constant = True
            for k in range(self.N_k):
                # Check if all values in this rate series are (approximately) the same
                rate_std = np.std(self.tau_kn[k])
                # Use a small threshold to account for floating point precision
                if rate_std > 1e-10:  # If standard deviation is non-zero, rates vary
                    rates_are_constant = False
                    break

            if rates_are_constant:
                self.mylog.vprint("Warning: Cannot plot correlations for constant rates (no variation in rate values).")
                return None

        fig = self._plotter.plot_rates_correlations(self._name, self.tau_kn, self.N_n, self.rateMethod,
                                                    self.rateFrm, self.rateTo, tag, shareRange)

        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    def showRatesDistributions(self, frm=rates.FROM, to=rates.TO, figure=False):
        """
        Plot histograms of the rates distributions.
        """
        fig = self._plotter.plot_rates_distributions(frm, to, rates.SP500, rates.BondsBaa,
                                                     rates.TNotes, rates.Inflation, rates.FROM)
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    def showRates(self, tag="", figure=False):
        """
        Plot rate values used over the time horizon.

        A tag string can be set to add information to the title of the plot.
        """
        if self.rateMethod is None:
            self.mylog.vprint("Warning: Rate method must be selected before plotting.")
            return None

        fig = self._plotter.plot_rates(self._name, self.tau_kn, self.year_n,
                                       self.N_k, self.rateMethod, self.rateFrm, self.rateTo, tag)

        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
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
        if tag:
            title += " - " + tag
        fig = self._plotter.plot_profile(self.year_n, self.xi_n, title, self.inames)

        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showNetSpending(self, tag="", value=None, figure=False):
        """
        Plot net available spending and target over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValueType(value)
        title = self._name + "\nNet Available Spending"
        if tag:
            title += " - " + tag
        fig = self._plotter.plot_net_spending(self.year_n, self.g_n, self.xi_n, self.xiBar_n,
                                              self.gamma_n, value, title, self.inames)
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showAssetComposition(self, tag="", value=None, figure=False):
        """
        Plot the composition of each savings account in thousands of dollars
        during the simulation time. This function will generate three
        graphs, one for taxable accounts, one the tax-deferred accounts,
        and one for tax-free accounts.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValueType(value)
        figures = self._plotter.plot_asset_composition(self.year_n, self.inames, self.b_ijkn,
                                                       self.gamma_n, value, self._name, tag)
        if figure:
            return figures

        for fig in figures:
            self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showGrossIncome(self, tag="", value=None, figure=False):
        """
        Plot income tax and taxable income over time horizon.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValueType(value)
        tax_brackets = tx.taxBrackets(self.N_i, self.n_d, self.N_n, self.yOBBBA)
        title = self._name + "\nTaxable Ordinary Income vs. Tax Brackets"
        if tag:
            title += " - " + tag
        fig = self._plotter.plot_gross_income(
            self.year_n, self.G_n, self.gamma_n, value, title, tax_brackets
        )
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    def showAllocations(self, tag="", figure=False):
        """
        Plot desired allocation of savings accounts in percentage
        over simulation time and interpolated by the selected method
        through the interpolateAR() method.

        A tag string can be set to add information to the title of the plot.
        """
        title = self._name + "\nAsset Allocation"
        if tag:
            title += " - " + tag
        figures = self._plotter.plot_allocations(self.year_n, self.inames, self.alpha_ijkn,
                                                 self.ARCoord, title)
        if figure:
            return figures

        for fig in figures:
            self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showAccounts(self, tag="", value=None, figure=False):
        """
        Plot values of savings accounts over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValueType(value)
        title = self._name + "\nSavings Balance"
        if tag:
            title += " - " + tag
        fig = self._plotter.plot_accounts(self.year_n, self.savings_in, self.gamma_n,
                                          value, title, self.inames)
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showSources(self, tag="", value=None, figure=False):
        """
        Plot income over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValueType(value)
        title = self._name + "\nRaw Income Sources"
        if tag:
            title += " - " + tag
        fig = self._plotter.plot_sources(self.year_n, self.sources_in, self.gamma_n,
                                         value, title, self.inames)
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showTaxes(self, tag="", value=None, figure=False):
        """
        Plot income tax paid over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValueType(value)
        title = self._name + "\nFederal Income Tax"
        if tag:
            title += " - " + tag
        # All taxes: ordinary income, dividends, and NIIT.
        allTaxes = self.T_n + self.U_n + self.J_n
        fig = self._plotter.plot_taxes(self.year_n, allTaxes, self.m_n + self.M_n, self.gamma_n,
                                       value, title, self.inames)
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    def saveWorkbook(self, overwrite=False, *, basename=None, saveToFile=True):
        """
        Save instance in an Excel spreadsheet.
        The first worksheet will contain income in the following
        fields in columns:
        - net spending
        - taxable ordinary income
        - taxable dividends
        - tax bills (federal only, including IRMAA)
        for all the years for the time span of the case.

        The second worksheet contains the rates
        used for the case as follows:
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
            "Tax bills + Med.": self.T_n + self.U_n + self.m_n + self.M_n + self.J_n,
        }

        fillsheet(ws, incomeDic, "currency")

        # Cash flow - sum over both individuals for some.
        cashFlowDic = {
            "net spending": self.g_n,
            "all wages": np.sum(self.omega_in, axis=0),
            "all pensions": np.sum(self.piBar_in, axis=0),
            "all soc sec": np.sum(self.zetaBar_in, axis=0),
            "all BTI's": np.sum(self.Lambda_in, axis=0),
            "FA ord inc": self.fixed_assets_ordinary_income_n,
            "FA cap gains": self.fixed_assets_capital_gains_n,
            "FA tax-free": self.fixed_assets_tax_free_n,
            "debt pmts": -self.debt_payments_n,
            "all wdrwls": np.sum(self.w_ijn, axis=(0, 1)),
            "all deposits": -np.sum(self.d_in, axis=0),
            "ord taxes": -self.T_n - self.J_n,
            "div taxes": -self.U_n,
            "Medicare": -self.m_n - self.M_n,
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
            fillsheet(ws, srcDic, "currency", op=lambda x: x[i])   # noqa: B023

        # Household sources (debts and fixed assets)
        householdSrcDic = {
            "FA ord inc": self.sources_in["FA ord inc"],
            "FA cap gains": self.sources_in["FA cap gains"],
            "FA tax-free": self.sources_in["FA tax-free"],
            "debt pmts": self.sources_in["debt pmts"],
        }
        ws = wb.create_sheet("Household Sources")
        fillsheet(ws, householdSrcDic, "currency", op=lambda x: x[0])

        # Account balances except final year.
        accDic = {
            "taxable bal": self.b_ijn[:, 0, :-1],
            "taxable ctrb": self.kappa_ijn[:, 0, :self.N_n],
            "taxable dep": self.d_in,
            "taxable wdrwl": self.w_ijn[:, 0, :],
            "tax-deferred bal": self.b_ijn[:, 1, :-1],
            "tax-deferred ctrb": self.kappa_ijn[:, 1, :self.N_n],
            "tax-deferred wdrwl": self.w_ijn[:, 1, :],
            "(included RMDs)": self.rmd_in[:, :],
            "Roth conv": self.x_in,
            "tax-free bal": self.b_ijn[:, 2, :-1],
            "tax-free ctrb": self.kappa_ijn[:, 2, :self.N_n],
            "tax-free wdrwl": self.w_ijn[:, 2, :],
        }
        for i in range(self.N_i):
            sname = self.inames[i] + "'s Accounts"
            ws = wb.create_sheet(sname)
            fillsheet(ws, accDic, "currency", op=lambda x: x[i])   # noqa: B023
            # Add final balances.
            lastRow = [
                self.year_n[-1] + 1,
                self.b_ijn[i][0][-1],
                0,
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
            _formatSpreadsheet(ws, "currency")

        # Federal income tax brackets.
        TxDic = {}
        for t in range(self.N_t):
            TxDic[tx.taxBracketNames[t]] = self.T_tn[t, :]

        TxDic["total"] = self.T_n
        TxDic["NIIT"] = self.J_n
        TxDic["LTCG"] = self.U_n
        TxDic["10% penalty"] = self.P_n

        sname = "Federal Income Tax"
        ws = wb.create_sheet(sname)
        fillsheet(ws, TxDic, "currency")

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

        # Income data
        planData["net spending"] = self.g_n
        planData["taxable ord. income"] = self.G_n
        planData["taxable gains/divs"] = self.Q_n
        planData["Tax bills + Med."] = self.T_n + self.U_n + self.m_n + self.M_n + self.J_n

        # Cash flow data (matching Cash Flow worksheet)
        planData["all wages"] = np.sum(self.omega_in, axis=0)
        planData["all pensions"] = np.sum(self.piBar_in, axis=0)
        planData["all soc sec"] = np.sum(self.zetaBar_in, axis=0)
        planData["all BTI's"] = np.sum(self.Lambda_in, axis=0)
        planData["FA ord inc"] = self.fixed_assets_ordinary_income_n
        planData["FA cap gains"] = self.fixed_assets_capital_gains_n
        planData["FA tax-free"] = self.fixed_assets_tax_free_n
        planData["debt pmts"] = -self.debt_payments_n
        planData["all wdrwls"] = np.sum(self.w_ijn, axis=(0, 1))
        planData["all deposits"] = -np.sum(self.d_in, axis=0)
        planData["ord taxes"] = -self.T_n - self.J_n
        planData["div taxes"] = -self.U_n
        planData["Medicare"] = -self.m_n - self.M_n

        # Individual account data
        for i in range(self.N_i):
            planData[self.inames[i] + " txbl bal"] = self.b_ijn[i, 0, :-1]
            planData[self.inames[i] + " txbl dep"] = self.d_in[i, :]
            planData[self.inames[i] + " txbl wrdwl"] = self.w_ijn[i, 0, :]
            planData[self.inames[i] + " tx-def bal"] = self.b_ijn[i, 1, :-1]
            planData[self.inames[i] + " tx-def ctrb"] = self.kappa_ijn[i, 1, :self.N_n]
            planData[self.inames[i] + " tx-def wdrl"] = self.w_ijn[i, 1, :]
            planData[self.inames[i] + " (RMD)"] = self.rmd_in[i, :]
            planData[self.inames[i] + " Roth conv"] = self.x_in[i, :]
            planData[self.inames[i] + " tx-free bal"] = self.b_ijn[i, 2, :-1]
            planData[self.inames[i] + " tx-free ctrb"] = self.kappa_ijn[i, 2, :self.N_n]
            planData[self.inames[i] + " tax-free wdrwl"] = self.w_ijn[i, 2, :]
            planData[self.inames[i] + " big-ticket items"] = self.Lambda_in[i, :]

        # Rates
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
                raise Exception(f"Unanticipated exception: {e}.") from e

        return None

    def saveConfig(self, basename=None):
        """
        Save parameters in a configuration file.
        """
        if basename is None:
            basename = "case_" + self._name

        config.saveConfig(self, basename, self.mylog)

        return None


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

    if not overwrite and isfile(fname):
        mylog.print(f'File "{fname}" already exists.')
        key = input("Overwrite? [Ny] ")
        if key != "y":
            mylog.vprint("Skipping save and returning.")
            return None

    for _ in range(3):
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
            raise Exception(f"Unanticipated exception {e}.") from e

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


def _formatDebtsSheet(ws):
    """
    Format Debts sheet with appropriate column formatting.
    """
    from openpyxl.utils import get_column_letter

    # Format header row
    for cell in ws[1]:
        cell.style = "Pandas"

    # Get column mapping from header
    header_row = ws[1]
    col_map = {}
    for idx, cell in enumerate(header_row, start=1):
        col_letter = get_column_letter(idx)
        col_name = str(cell.value).lower() if cell.value else ""
        col_map[col_letter] = col_name
        # Set column width
        width = max(len(str(cell.value)) + 4, 10)
        ws.column_dimensions[col_letter].width = width

    # Apply formatting based on column name
    for col_letter, col_name in col_map.items():
        if col_name in ["year", "term"]:
            # Integer format
            fstring = "#,##0"
        elif col_name in ["rate"]:
            # Number format (2 decimal places for percentages stored as numbers)
            fstring = "#,##0.00"
        elif col_name in ["amount"]:
            # Currency format
            fstring = "$#,##0_);[Red]($#,##0)"
        else:
            # Text columns (name, type) - no number formatting
            continue

        # Apply formatting to all data rows (skip header row 1)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.column_letter == col_letter:
                    cell.number_format = fstring

    return None


def _formatFixedAssetsSheet(ws):
    """
    Format Fixed Assets sheet with appropriate column formatting.
    """
    from openpyxl.utils import get_column_letter

    # Format header row
    for cell in ws[1]:
        cell.style = "Pandas"

    # Get column mapping from header
    header_row = ws[1]
    col_map = {}
    for idx, cell in enumerate(header_row, start=1):
        col_letter = get_column_letter(idx)
        col_name = str(cell.value).lower() if cell.value else ""
        col_map[col_letter] = col_name
        # Set column width
        width = max(len(str(cell.value)) + 4, 10)
        ws.column_dimensions[col_letter].width = width

    # Apply formatting based on column name
    for col_letter, col_name in col_map.items():
        if col_name in ["yod"]:
            # Integer format
            fstring = "#,##0"
        elif col_name in ["rate", "commission"]:
            # Number format (1 decimal place for percentages stored as numbers)
            fstring = "#,##0.00"
        elif col_name in ["basis", "value"]:
            # Currency format
            fstring = "$#,##0_);[Red]($#,##0)"
        else:
            # Text columns (name, type) - no number formatting
            continue

        # Apply formatting to all data rows (skip header row 1)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.column_letter == col_letter:
                    cell.number_format = fstring

    return None
