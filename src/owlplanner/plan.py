"""
Core retirement planning module using linear programming optimization.

This module implements the main Plan class and optimization logic for retirement
financial planning. See companion PDF document for an explanation of the underlying
mathematical model and a description of all variables and parameters.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

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
import copy
import numpy as np
import pandas as pd
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import time
import textwrap

from . import amorepair
from . import localsearch
from . import utils as u
from . import tax_federal as tx
from . import tax_state
from . import tax_local
from . import residency
from . import abcapi as abc
from . import rates
from .version import __version__, engine_commit
from . import config
from . import hfp_io
from . import export
from . import pension
from . import socialsecurity as socsec
from . import spending
from . import debts as debts
from . import fixedassets as fxasst
from . import mylogging as log
from .config.plan_bridge import clone  # noqa: F401
from .config.schema import REMOVED_OPTIONS
from .plotting.factory import PlotFactory
from .rate_models.constants import CONSTRAIN_MEAN_METHODS, HISTORICAL_RANGE_METHODS
from .stresstests import (
    run_conversion_regret_sweep,
    run_historical_range,
    run_mc,
    run_spending_bequest_frontier,
    run_stochastic_spending,
)
from .varmap import VarMap


def _mosek_available():
    import importlib.util
    import os

    return importlib.util.find_spec("mosek") is not None and os.environ.get("MOSEKLM_LICENSE_FILE") is not None


# Solver options that no longer do anything, and why. A case file saved earlier still
# carries them, so they are accepted and reported as deprecated rather than rejected as
# unknown, each with the reason a reader would need.
_AMO_RETIRED = (
    "the exclusions it selected are restored after the solve now, so nothing needs constraining"
)
_BIGM_RETIRED = (
    "each big-M is now derived per year from what its own row gates -- the portfolio ceiling plus "
    "that year's fixed income, or the benefit share the row switches on -- so there is nothing left "
    "to tune. The flat constants these keys set were hundreds to thousands of times too large"
)
_DECOMP_RETIRED = (
    "the only mode it offered, 'sequential', never once worked: it rounded all five bracket "
    "families at once from a single LP relaxation, which is jointly infeasible even when each "
    "family is feasible alone, so every solve fell back to the monolithic MIP it was meant to "
    "avoid. Measured over 8 windows it cost a discarded LP per iteration and returned the "
    "monolithic answer every time"
)
_SCLOOP_RETIRED = (
    "no mode can solve without the self-consistent loop -- the standard exemption's OBBBA "
    "phaseout and the cost-basis gain fractions are nonlinear in the solution -- and turning "
    "it off left Medicare out of the budget, overstating spending. Use maxIter to shorten it"
)
RETIRED_OPTIONS = {
    "amoConstraints": _AMO_RETIRED,
    "amoRoth": _AMO_RETIRED,
    "amoSurplus": _AMO_RETIRED,
    "bigMamo": _BIGM_RETIRED,
    "bigMaca": _BIGM_RETIRED,
    "bigMss": _BIGM_RETIRED,
    "bigMltcg": _BIGM_RETIRED,
    "bigMniit": _BIGM_RETIRED,
    "withDecomposition": _DECOMP_RETIRED,
    "withSCLoop": _SCLOOP_RETIRED,
}

# Sentinel distinguishing "argument omitted" from an explicit None, which callers use to
# mean "today". Needed wherever None is already a meaningful value rather than a placeholder.
_UNCHANGED = object()

# Default values
GAP = 1e-4
_PSI_DAMP = 0.3  # SC-loop damping weight for new Psi_n estimate (blend 30% new / 70% old)
MILP_GAP = 30 * GAP
MAX_ITERATIONS = 29
STAGNATION_WINDOW = 8  # SC iterations without improvement before early-exit check
STAGNATION_TIMEOUTS = 3  # min gap=inf MILP timeouts in window to trigger stagnation exit
ABS_TOL = 100
REL_TOL = 5e-5
# Largest disagreement, in today's dollars PER YEAR, between a quantity the LP was built with and
# the value the resulting plan implies, before the loop may call itself converged. Per year, not
# per plan: the underlying measure sums over the horizon, so a flat figure would be three times
# stricter on a 33-year plan than on an 11-year one and would mean different things to different
# households. Calibrated over the shipped cases -- anything from $25 to $200 a year behaves the
# same on all seventeen, so this sits in the middle of a flat region rather than on an edge.
RESIDUAL_TOL = 50.0
# IRMAA and ACA brackets apply above their thresholds, not at them: in the binary formulations each
# higher bracket starts this many dollars above its threshold, so a MAGI on a threshold cannot be
# charged the higher bracket. More than the residual's $1 of slack at a threshold.
BRACKET_MARGIN = 2.0
TIME_LIMIT = 900
# The NJ exclusion's tier binaries are free only in years whose state income, in the previous
# iterate, was at most this multiple of the top tier ceiling; elsewhere the exclusion is off.
RX_WINDOW = 1.5
# Default cap, in branch-and-bound nodes, on a HiGHS MILP that carries free exclusion tier binaries,
# when neither maxTime nor mipMaxNodes is given: large-balance cases can take far longer to prove
# optimal, so the plan is returned with its gap. A node cap, like upstream's local search steps,
# gives the same plan on any machine; it replaced a 60 s time cap (2026-10-06), which the $1.5M+$1.0M
# couple reached at 20,809 nodes on the 4-core container. TIME_LIMIT stays the backstop.
RX_NODE_LIMIT = 20_000
# MOSEK counts nodes differently and was not recalibrated: it keeps the former 60 s time cap.
RX_MOSEK_TIME_LIMIT = 60
# Lexicographic weight on Roth conversions, and the loop's main conditioning term. At 1e-8 it
# breaks ties only nominally: the conversion schedule stays free to migrate between near-equivalent
# years, and since a conversion moves provisional income directly, each move can flip a Social
# Security tier or an IRMAA bracket -- the loop ends up chasing its own schedule. Case_chris+pat
# converts in 5 years but 16 different years see its schedule move during the search.
#
# Measured over the shipped cases. 2e-7 fixes nothing; 5e-7 and 1e-6 both eliminate every
# max-iteration case, so the threshold lies between. 5e-7 is the cheaper side of it and needs
# fewer iterations overall (171 against 175, and 222 undamped). The cost is real, not an artifact
# of convergence: chris+pat's exact answer is above every epsilon result, so the penalty distorts
# rather than corrects -- about 0.1-0.25% on the four cases that move, and nothing at all on the
# nine that are already well behaved. Larger values start eating the economics: at 1e-3 the
# measured Roth conversion regret falls 23%, which is the conditioning consuming the quantity
# being measured, and at 1e-2 conversion years are deleted outright.
EPSILON = 5e-7
# Tie-break for degenerate directions inside a MIP. EPSILON is sized for the simplex, which
# resolves ties exactly; a branch-and-bound gap swallows anything smaller than the optimality
# tolerance, so a MIP tie-break has to be visible above it while staying far below any real
# cost in the objective. See the t^sigma_n preference in _buildObjective.
MIP_TIEBREAK = 1e-4
# Tie-break on the tax a year's brackets charge, per today's dollar of tax. The bracket variables are
# a relaxation, tight only while the year's cash has a price: where it has none (late surplus that
# can only swell a bequest above its floor), any split of income across brackets is optimal and the
# solver can fill the top one first, reporting tax the plan does not owe. The self-consistent
# loop switches tax pricing this size on from the first iterate that fills a year out of order (the
# degenerate fill also stalls convergence, through the LTCG residual), and _repairBracketOrder
# re-solves an accepted LP that first goes out of order in the final iterate. It stays off otherwise:
# always on, it moved the fixed point the loop settles on in cases that were never out of order
# (morgan +1.5% spending, john+sally -4% bequest). EPSILON (5e-7) is too small: the reduced costs it
# makes sit at HiGHS's dual feasibility tolerance and the fill stays.
TAX_TIEBREAK = MIP_TIEBREAK
# Value of a dollar left to non-spouse heirs at the first death, in final-objective dollars. Default
# max(PARTIAL_BEQUEST_WEIGHT, 2 x gap): below the gap that money is invisible to the solver, which
# can then spend it on taxes not owed.
PARTIAL_BEQUEST_WEIGHT = 0.01
# Retries when HiGHS reports a MIP infeasible, cheapest first. Presolve rule bit 12 is HiGHS's own
# numbering and may change between versions; presolve off is the backstop.
_HIGHS_INFEASIBLE_RETRIES = (
    ("presolve_rule_off", 1 << 12, "presolve rule 12 off"),
    ("presolve", "off", "presolve off"),
)
LTCG_CONSISTENCY_MAX_PASSES = 5  # max monolithic re-solves to clear stale LTCG bracket room
LTCG_CONSISTENCY_TOL = 1.0  # allowed U_n - 0.20*Q_n slack ($) before a re-solve is needed


############################################################################


def _checkCaseStatus(func):
    """
    Decorator to check if problem was solved successfully and
    prevent method from running if not.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.caseStatus != "solved":
            self.mylog.print(f"Preventing to run method {func.__name__}() while case is {self.caseStatus}.")
            return None
        return func(self, *args, **kwargs)

    return wrapper


def _mosekIsInfeasible(task, soltype, mosek):
    """
    Whether MOSEK certified that no solution exists.

    An infeasible MIP reports its solution status as merely "unknown" and declares the
    infeasibility on the problem status, so both have to be consulted.
    """
    return (
        task.getsolsta(soltype) == mosek.solsta.prim_infeas_cer
        or task.getprosta(soltype) == mosek.prosta.prim_infeas
    )


def _failureMessage(infeasible, solverName, solverMsg):
    """
    Explain a solve that produced no plan.

    The distinction is the point: an infeasible problem is the user's to fix, while a
    solver that failed says nothing about whether the plan is achievable -- issue #139
    is a case HiGHS abandons with status 'Unknown' and MOSEK solves to optimality.
    """
    if infeasible:
        return (
            "No plan satisfies all the constraints. An input has to give: most often a bequest "
            "or a spending floor set higher than the assets can support."
        )
    return (
        f"Solver error: {solverName} could not complete this model (status '{solverMsg}'). "
        "This is a failure of the optimizer, not an infeasible plan -- the same case may well "
        "solve with the other solver, or after a small change to the inputs."
    )


def _checkConfiguration(func=None, *, requireRates=True):
    """
    Decorator refusing to start when the plan is not ready, so that a partially configured
    plan fails at the entry point with an actionable message instead of somewhere deep in
    matrix assembly - or, for the multi-scenario runners, inside a worker thread after the
    pool has already been spawned.

    Every check lives in Plan._preflight(); this only decides where they are enforced.

    requireRates=False for the runners that select a rate method per scenario themselves
    (run_historical_range and the sweeps call setRates() on each clone), where demanding one
    up front would reject legitimate use. Their inner solve() still enforces it.

    Usable bare (@_checkConfiguration) or with arguments
    (@_checkConfiguration(requireRates=False)).
    """

    def decorate(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            self._preflight(f.__name__, requireRates=requireRates)
            return f(self, *args, **kwargs)

        return wrapper

    return decorate if func is None else decorate(func)


def _fixedAcrossIterations(builder):
    """
    Decorator for a constraint builder whose rows are the same on every iteration of
    the self-consistent loop: the rows and bounds it adds on the first build of a solve
    are replayed on the later ones instead of being rebuilt.

    Only for builders that read nothing the loop updates between iterations: M_n, ACA_n,
    J_n, Psi_n, G_n, Q_n, I_n, the gain fraction, and sigmaBar_n (which follows MAGI).
    Rebuilding those rows was most of the cost of each iteration's LP.
    """

    @wraps(builder)
    def wrapper(self, *args):
        saved = self._fixedRows.get(builder.__name__)
        if saved is None:
            ncons, nranges = self.A.ncons, len(self.B.ind)
            builder(self, *args)
            self._fixedRows[builder.__name__] = (self.A.rowsSince(ncons), self.B.rangesSince(nranges))
        else:
            self.A.extendRows(saved[0])
            self.B.extendRanges(saved[1])

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
        # Kept so callers can size a sweep from this case's own measured cost: per-solve
        # time varies by more than an order of magnitude between cases, so a solve count
        # alone says very little about how long a run will take. Only solve() records it -
        # the multi-solve runners share this decorator and would otherwise overwrite the
        # per-solve figure with their own total.
        if func.__name__ == "solve":
            self.lastSolveWallTime = rt
            # CPU time of the whole process, solver threads included: with MOSEK on several
            # threads it can be several times the wall time.
            self.lastSolveCPUTime = pt
        self.mylog.vprint(
            f"CPU time used: {int(pt / 60)}m{pt % 60:.1f}s, Wall time: {int(rt / 60)}m{rt % 60:.1f}s.", tag="INFO"
        )
        return result

    return wrapper


class Plan:
    """
    This is the main class of the Owl Project.
    """

    # SC-loop parameters: the NL quantities the loop feeds back into each LP solve.
    # Adding a new loop-fed cost means adding its attribute name here;
    # snapshot/restore/blend and the iteration trace pick it up automatically.
    _SC_PARAMS = ("M_n", "ACA_n", "J_n", "Psi_n", "STR_n", "RXF_n")

    def _snapshot_sc(self):
        "Copy the current SC-loop parameters into a dict."
        return {name: getattr(self, name).copy() for name in self._SC_PARAMS}

    def _restore_sc(self, d):
        "Restore SC-loop parameters from a dict produced by _snapshot_sc."
        for name in self._SC_PARAMS:
            setattr(self, name, d[name])

    def _blend_sc(self, prev, target, frac):
        "Move SC-loop parameters frac of the way from prev to target."
        for name in self._SC_PARAMS:
            p0, p1 = prev[name], target[name]
            setattr(self, name, p0 + frac * (p1 - p0))

    def _sc_trace_entry(self, trace, idx=None):
        "Return the SC-loop parameter dict from the trace at idx (last if None)."
        i = -1 if idx is None else idx
        return {name: trace[f"{name}_lp"][i] for name in self._SC_PARAMS}

    def _sc_trace_append(self, trace, sc_lp):
        "Append an SC-loop parameter snapshot to the trace."
        for name in self._SC_PARAMS:
            trace[f"{name}_lp"].append(sc_lp[name])

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

        # 7 tax brackets, 6 IRMAA (Medicare) brackets, 3 LTCG brackets,
        # 4 types of accounts (j=3 is HSA), 4 classes of assets.
        self.N_t = 7
        self.N_irmaa = 6
        self.N_p = 3
        self.N_j = 4
        self.N_k = 4

        # Default interpolation parameters for allocation ratios.
        self.interpMethod = "linear"
        self._interpolator = self._linInterp
        self.interpCenter = 15
        self.interpWidth = 5

        self._description = ""
        self._config_extra = None
        self.defaultPlots = "nominal"
        self.worksheetShowAges = False
        self.worksheetHideZeroColumns = False
        self.worksheetRealDollars = False
        self.defaultSolver = "default"
        self._plotterName = None
        # Pick a default plotting backend here.
        # self.setPlotBackend("matplotlib")
        self.setPlotBackend("plotly")

        u.require_list(dobs, "dobs")
        self.N_i = len(dobs)
        if not (0 <= self.N_i <= 2):
            raise ValueError(f"Cannot support {self.N_i} individuals.")
        u.require_list(expectancy, "expectancy", self.N_i)
        u.require_list(inames, "inames", self.N_i)
        if inames[0] == "" or (self.N_i == 2 and inames[1] == ""):
            raise ValueError("Name for each individual must be provided.")

        self.filingStatus = ("single", "married")[self.N_i - 1]

        # Default year OBBBA speculated to be expired and replaced by pre-TCJA rates.
        self.yOBBBA = 2032
        self.inames = inames
        self.yobs, self.mobs, self.tobs = u.parseDobs(dobs)
        self.dobs = dobs
        self.expectancy = np.array(expectancy, dtype=np.int32)
        self.sexes = ["M", "F"] if self.N_i == 2 else ["F"]  # default; overridden by setSexes()
        self.mortality_table = "SSA2025"  # default; overridden by setMortalityTable()

        # Reference time is starting date in the current year and all passings are assumed at the end.
        thisyear = date.today().year
        self.horizons = self.yobs + self.expectancy - thisyear + 1
        self.N_n = np.max(self.horizons)
        if self.N_n <= 1:
            raise ValueError(f"Plan needs more than {self.N_n} years.")

        self.year_n = np.linspace(thisyear, thisyear + self.N_n - 1, self.N_n, dtype=np.int32)
        # Year index when each individual turns 59½ (IRS threshold). Born Jul–Dec: +1 year.
        self.n595 = 59 - thisyear + self.yobs + (self.mobs > 6).astype(np.int32)
        self.n595[self.n595 < 0] = 0
        # Year index when each individual turns 70½, the QCD eligibility threshold.
        # Same half-year convention as n595; unrelated to the RMD start age.
        self.n_qcd_i = 70 - thisyear + self.yobs + (self.mobs > 6).astype(np.int32)
        self.n_qcd_i[self.n_qcd_i < 0] = 0
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
        # Fraction of SS benefits subject to federal income tax (initial: 0.85).
        # Refined each SC-loop iteration by _update_Psi_n() using the IRS provisional income formula.
        self.Psi_n = np.ones(self.N_n) * 0.85
        self.chi = 0.60  # Survivor fraction
        self.mu = 0.0172  # Dividend rate (decimal)
        self.taxable_basis_i = None  # Per-person initial cost basis (N_i,); None = legacy cap-gain approx
        self.gain_fraction_in = None  # (N_i, N_n) unrealized gain fraction; updated each SC iteration
        self._fixedRows = {}  # Rows of the loop-invariant constraint builders; reset by solve()
        self.nu = 0.300  # Heirs tax rate (decimal)
        self.liquidationTaxRate = 0.240  # Assumed ordinary tax rate on tax-deferred/HSA if liquidated (decimal)
        self.liquidationCapGainsRate = 0.150  # Assumed capital-gains tax rate on fixed-asset disposition (decimal)
        self.bequest = 0.0  # After-tax bequest in today's dollars (set after full solve)
        self.heir_tax_liability = 0.0  # Heir taxes on final bequest (IRA+HSA), today's $
        self.partial_heir_tax_liability = 0.0  # Heir taxes on partial bequest, today's $
        self.eta = (self.N_i - 1) / 2  # Spousal deposit ratio (0 or .5)
        self.phi_j = np.array([1, 1, 1, 1])  # Fractions left to other spouse at death (j=3: HSA)
        self.n_hsa_i = np.full(self.N_i, self.N_n, dtype=int)  # Year HSA contributions stop (default: never)
        self.slcsp_annual = 0.0  # Today-dollar annual ACA benchmark Silver plan premium ($)
        self.aca_start_year = 0  # Calendar year ACA coverage begins (0 = plan start)
        self.ACA_n = np.zeros(self.N_n)  # Net ACA cost (after subsidy) per year (plan $)
        self._aca_lp = False  # True when withACA="optimize" is active
        self.maca_n = np.zeros(self.N_n)  # ACA LP cost variable extraction result
        self.state = ""  # Two-letter US state for state income tax ("" = none)
        self.locality = ""  # Locality within the state, e.g. "NYC" ("" = none)
        self.state_moves = []  # Later moves, as residency.Residence(year, state, locality)
        self.N_lt = 0  # Number of local tax brackets (0 when no locality has a bracket schedule)
        self.lt_surcharge_n = np.zeros(self.N_n)  # Local surcharge as a fraction of net state tax
        self.lt_T_n = np.zeros(self.N_n)  # Local income tax per year (included in st_T_n)
        self.STR_n = np.zeros(self.N_n)  # State benefit recapture per year (SC-loop parameter; in st_T_n)
        self.st_recap_n = np.zeros(self.N_n)  # Recapture charged in the solved plan (part of st_T_n)
        self._str_active = False  # True when the state recaptures the benefit of its lower brackets
        self.st_rx_n = np.zeros(self.N_n)  # Income-tiered retirement exclusion claimed (NJ line 28c)
        self.RXF_n = np.zeros(self.N_n)  # 1 where the exclusion's tier binaries are free (SC-loop parameter)
        self._rx_active = False  # True when a state in the plan has an income-tiered retirement exclusion
        self.st_T_n = np.zeros(self.N_n)  # State income tax per year (N_n,)
        self.st_credit_n = np.zeros(self.N_n)  # State personal credit available per year (N_n,)
        self.st_c_n = np.zeros(self.N_n)  # State personal credit used per year (N_n,)
        self._st_lp = False  # True when state income tax LP is active
        self.N_st = 0  # Number of state tax brackets (0 when no state set)
        self.st_re_cap_in = np.zeros((self.N_i, self.N_n))  # State retirement income exemption caps
        # Per-year state flags (the state of residence can differ by year; see tax_state.st_schedule).
        self.st_conv_ok_n = np.ones(self.N_n, dtype=bool)  # Roth conversions count toward the exemption
        self.st_tax_ss_n = np.zeros(self.N_n, dtype=bool)  # The state taxes Social Security
        self.st_fed_sd_n = np.zeros(self.N_n, dtype=bool)  # The state follows the federal standard deduction
        self.st_senior_bonus_n = np.zeros(self.N_n, dtype=bool)  # ...including the OBBBA senior bonus
        self.st_pension_eligible_n = np.ones(self.N_n, dtype=bool)  # Pensions share the retirement exemption
        self.st_re_in = np.zeros((self.N_i, self.N_n))  # State retirement exemption claimed per person
        self.n_aca = 0  # Number of ACA-eligible plan years (LP mode)
        self.other_medical_k = 0.0  # Annual non-Medicare QMEs in today's dollars ($)
        self.other_medical_n = np.zeros(self.N_n)  # Inflation-adjusted per-year version (nominal $)
        self.smileDip = 15  # Percent to reduce smile profile
        self.smileIncrease = 12  # Percent to increse profile over time span

        # Default to zero pension and social security.
        self.pi_in = np.zeros((self.N_i, self.N_n))
        self.piBar_in = np.zeros((self.N_i, self.N_n))
        self.zeta_in = np.zeros((self.N_i, self.N_n))
        self.zetaBar_in = np.zeros((self.N_i, self.N_n))
        self.pensionAmounts = np.zeros(self.N_i, dtype=np.int32)
        self.pensionAges = 65 * np.ones(self.N_i, dtype=np.int32)
        self.pensionIsIndexed = [False] * self.N_i
        self.pensionSurvivorFraction = np.zeros(self.N_i)
        self.ssecAmounts = np.zeros(self.N_i, dtype=np.int32)
        self.ssecAges = 67 * np.ones(self.N_i, dtype=np.int32)
        self.ssecTrimPct = 0
        self.ssecTrimYear = None
        self.ssecSurvivorClaimAge = "immediate"

        # Parameters from timeLists initialized to zero.
        self.omega_in = np.zeros((self.N_i, self.N_n))
        self.other_inc_in = np.zeros((self.N_i, self.N_n))
        self.netinv_in = np.zeros((self.N_i, self.N_n))
        self.Lambda_in = np.zeros((self.N_i, self.N_n))
        # Qualified Charitable Distributions: leave the tax-deferred account for
        # charity, so they are excluded from AGI and are not spendable cash.
        self.qcd_in = np.zeros((self.N_i, self.N_n))
        # Go back 5 years for maturation rules on IRA and Roth.
        self.myRothX_in = np.zeros((self.N_i, self.N_n + 5))
        # Which of those conversion amounts are held fixed rather than optimized.
        # Only the plan years [0, N_n) are read: the 5 lead-in years are conversions
        # already performed, and those always count.
        self.rothXfixed_in = np.zeros((self.N_i, self.N_n + 5), dtype=bool)
        self.kappa_ijn = np.zeros((self.N_i, self.N_j, self.N_n + 5))

        # Debt payments array (length N_n)
        self.debt_payments_n = np.zeros(self.N_n)
        # Remaining debt balance at the start of each year (length N_n)
        self.fixed_assets_debt_balances_remaining_n = np.zeros(self.N_n)

        # SPIA arrays.
        self.spiaBar_in = np.zeros((self.N_i, self.N_n))
        self.spia_premiums_in = np.zeros((self.N_i, self.N_n))
        self._spia_list = []

        # Fixed assets arrays (length N_n)
        self.fixed_assets_tax_free_n = np.zeros(self.N_n)
        self.fixed_assets_ordinary_income_n = np.zeros(self.N_n)
        self.fixed_assets_capital_gains_n = np.zeros(self.N_n)
        # Current market value of fixed assets still held at the start of each year (length N_n)
        self.fixed_assets_current_asset_values_n = np.zeros(self.N_n)
        # Disposition cost (commission + capital-gains tax) of fixed assets still held (length N_n)
        self.fixed_assets_disposition_costs_n = np.zeros(self.N_n)
        # Fixed assets bequest value (assets with yod past plan end)
        self.fixed_assets_bequest_value = 0.0

        # Remaining debt balance at end of plan
        self.remaining_debt_balance = 0.0

        # Previous 2 years of MAGI needed for Medicare.
        self.prevMAGI = np.zeros((2))
        # MAGI_n is the canonical AGI-basis MAGI (AGI + tax-exempt interest, i.e. taxable SS
        # only): used by IRMAA, NIIT (IRC §1411), and the OBBBA 65+ senior-deduction phaseout.
        # MAGI_aca_n is the full-SS variant (adds back non-taxable SS): used by ACA (§36B) and
        # SS-taxability provisional income (PI = MAGI_aca - 0.5*SS). See _aggregateResults.
        self.MAGI_n = np.zeros(self.N_n)
        self.MAGI_aca_n = np.zeros(self.N_n)
        self.solverOptions = {}

        # Init current balances to none.
        self.beta_ij = None
        self.startDate = None

        # Default slack on profile.
        self.lambdha = 0

        # Scenario starts at the beginning of this year and ends at the end of the last year.
        s = ("", "s")[self.N_i - 1]
        self.mylog.vprint(f"Preparing scenario '{self._id}' of {self.N_n} years for {self.N_i} individual{s}.")
        for i in range(self.N_i):
            endyear = thisyear + self.horizons[i] - 1
            self.mylog.vprint(f"{self.inames[i]:>14}: life horizon from {thisyear} -> {endyear}.")

        # Prepare RMD time series.
        self.rho_in = tx.rho_in(self.yobs, self.expectancy, self.N_n)

        # Initialize guardrails to ensure proper configuration.
        self._adjustedParameters = False
        self.hfpFileName = "None"
        self.timeLists = {}
        self.houseLists = {}
        self.rawHFP = {}  # raw dict of DataFrames from the HFP xlsx (horizon-independent)
        # Optional HFP columns absent from each individual's sheet and filled with zeros.
        self.hfpAbsentCols = {}
        self.zeroWagesAndContributions()
        self.caseStatus = "unsolved"
        # Wall time of the most recent solve(), in seconds; None until one has run.
        # Used to turn a solve count into an estimated duration for this specific case.
        self.lastSolveWallTime = None
        self.lastSolveCPUTime = None
        # Why the last solve produced no plan, in words; empty when it succeeded.
        self.solverMessage = ""
        # Whether the solver certified that no solution exists, as opposed to failing.
        self._infeasible = False
        # "monotonic", "oscillatory", "max iteration", or "undefined" - how solution was obtained
        self.convergenceType = "undefined"
        self._residual_tol = RESIDUAL_TOL
        # Per-family distance between the model solved and the model this plan's own income
        # implies, today's dollars; set by _computeFixedPointResidual after a successful solve.
        self.fixedPointResidual = {}
        # How the last solve treated the tax thresholds ("loop", "branch-and-bound (...)",
        # "local search (...)"), and the local search's step log when it ran.
        self.breakpointMethodUsed = "loop"
        self.localSearchLog = []
        self._localSearch = None
        self.bracketOrderExcess = 0.0
        # Whether the objective prices tax (TAX_TIEBREAK); switched on by _scSolve when needed.
        self._tax_tiebreak_on = False
        # Achieved MIP gap of the accepted solution (0 when solved to optimality,
        # larger when a time limit truncated the search; -1 before any solve)
        self.solverGap = -1.0
        # Relative amplitude (max-min)/max of the SC-loop oscillation cycle; 0 when
        # the loop converged monotonically (no fixed-point ambiguity)
        self.oscillationRel = 0.0
        # Absolute amplitude (max-min) of the same cycle, in the units of the final
        # modified objective (today's dollars: spending basis or bequest); 0 when
        # the loop converged. This is the error bar reported in the summary.
        self.oscillationAbs = 0.0
        self.rateMethod = None
        self.reproducibleRates = False
        self.rateSeed = None
        self.rateReverse = False
        self.rateRoll = 0

        # for plugins and core models
        self.rateModel = None
        self.rateMethodFile = None

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
        n = len(self.mylog._logstreams) if self.mylog._logstreams is not None else 0
        self.mylog.vprint(f"Setting logger with {n} logstream(s), verbose={verbose}.")

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

    def _readiness(self, *, requireRates=True):
        """
        Every "is this plan ready?" check, in one place. Returns the first unmet
        requirement as a message, or None when the plan is fully configured.

        Ordered cheapest-to-explain first, and each message names the setter that fixes it.
        Balances are the check that was missing: without them yearFracLeft is never created,
        and the plan died with a bare AttributeError inside _add_initial_balances rather
        than saying what the user had forgotten.

        The message carries a {caller} placeholder that _preflight() fills in; nothing here
        logs or raises, so isConfigured() can ask the same question without side effects.
        """
        if self.xi_n is None:
            return "You must define a spending profile before calling {caller}()."
        if self.alpha_ijkn is None:
            return "You must define an allocation profile before calling {caller}()."
        if self.beta_ij is None:
            return "You must set account balances before calling {caller}()."
        if requireRates and self.rateMethod is None:
            return "Rate method must be selected before calling {caller}()."
        return None

    def isConfigured(self, *, requireRates=True):
        """
        Non-raising twin of _preflight(): True when every setter the plan needs has run.

        Lets a caller skip an operation on a half-built plan instead of catching its
        failure - the UI builds a Plan long before it pushes any values onto it, and asking
        deliberately must not write noise into the case log.
        """
        return self._readiness(requireRates=requireRates) is None

    def _preflight(self, caller, *, requireRates=True):
        """
        Refuse to start when the plan is not ready, naming the setter that fixes it.
        """
        template = self._readiness(requireRates=requireRates)
        if template is None:
            return
        msg = template.format(caller=caller)
        self.mylog.print(msg)
        raise RuntimeError(msg)

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
        self.mylog.vprint(f"Renaming case '{self._name}' -> '{newname}'.")
        self._name = newname

    def setDescription(self, description):
        """
        Set a text description of the case.
        """
        self._description = description

    def setSexes(self, sexes):
        """
        Set the biological sex for each individual, used for SSA mortality table lookups.

        Parameters
        ----------
        sexes : list of str or None
            'M' (male) or 'F' (female) for each individual.  If None, defaults
            are preserved ('M' for all).  Must have N_i entries.
        """
        if sexes is None:
            return
        u.require_list(sexes, "sexes", self.N_i)
        for s in sexes:
            if s not in ("M", "F"):
                raise ValueError(f"Each sex must be 'M' or 'F', got {s!r}.")
        self.sexes = list(sexes)

    def setMortalityTable(self, table):
        """
        Select the actuarial mortality table used for longevity risk sampling.

        Parameters
        ----------
        table : str
            One of "SSA2025", "RP2014", "IAM2012", "VBT2015-NS", "VBT2015-SM".
        """
        from .data.mortality_tables import MORTALITY_TABLE_KEYS

        if table not in MORTALITY_TABLE_KEYS:
            raise ValueError(f"Unknown mortality table {table!r}. Valid: {MORTALITY_TABLE_KEYS}.")
        self.mortality_table = table

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
            self.mylog.print("Deposit fraction can only be 0 for single individuals.")
            eta = 0
        else:
            self.mylog.vprint(f"Setting spousal surplus deposit fraction to {eta:.1f}.")
            self.mylog.vprint(f"\t{self.inames[0]}: {1 - eta:.1f}, {self.inames[1]}: {eta:.1f}")
            self.eta = eta

    def setDefaultPlots(self, value):
        """
        Set plots between nominal values or today's $.
        """

        self.defaultPlots = self._checkValueType(value)
        self.mylog.vprint(f"Setting plots default value to '{value}'.")

    def setWorksheetShowAges(self, value):
        """Enable or disable age columns in Streamlit worksheet tables."""
        self.worksheetShowAges = bool(value)
        self.mylog.vprint(f"Setting worksheet show ages to {self.worksheetShowAges}.")

    def setWorksheetHideZeroColumns(self, value):
        """Enable or hide all-zero numeric columns in Streamlit worksheet tables."""
        self.worksheetHideZeroColumns = bool(value)
        self.mylog.vprint(f"Setting worksheet hide zero columns to {self.worksheetHideZeroColumns}.")

    def setWorksheetRealDollars(self, value):
        """Enable or disable real-dollar (inflation-adjusted) worksheet display and save."""
        self.worksheetRealDollars = bool(value)
        self.mylog.vprint(f"Setting worksheet real dollars to {self.worksheetRealDollars}.")

    def setPlotBackend(self, backend: str):
        """
        Set plotting backend.
        """

        if backend not in ("matplotlib", "plotly"):
            raise ValueError(f"Backend '{backend}' not a valid option.")

        if backend != self._plotterName:
            self._plotter = PlotFactory.createBackend(backend)
            self._plotterName = backend
            self.mylog.vprint(f"Setting plotting backend to '{backend}'.")

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

    def setCostBasis(self, amounts, units="k"):
        """
        Set the current cost basis of the taxable account for each individual.
        When provided, capital gains on withdrawals are computed from the actual
        unrealized-gain fraction instead of only this year's price appreciation.
        Units are in $k by default; pass units='M' or units='1' to override.
        """
        u.require_list(amounts, "amounts", self.N_i)
        fac = u.getUnits(units)
        scaled = [v * fac for v in amounts]
        if any(v < 0 for v in scaled):
            raise ValueError("Cost basis amounts must be non-negative.")
        txbl = self.bet_ji[0] if hasattr(self, "bet_ji") else None
        if txbl is None or all(b == 0 for b in txbl):
            self.mylog.vprint(
                "Call setAccountBalances() before setCostBasis() to enable basis validation.", tag="WARNING"
            )
        else:
            for i in range(self.N_i):
                if scaled[i] > txbl[i]:
                    self.mylog.vprint(
                        f"Cost basis ({u.d(scaled[i])}) exceeds taxable balance ({u.d(txbl[i])}) for {self.inames[i]}."
                        f" Is this intentional?",
                        tag="WARNING",
                    )
        self.taxable_basis_i = np.array(scaled, dtype=float)
        self.gain_fraction_in = None
        self.mylog.vprint("Taxable cost basis:", *[u.d(self.taxable_basis_i[i]) for i in range(self.N_i)])
        self.caseStatus = "modified"

    @staticmethod
    def _gain_fraction_from_basis(basis, balance):
        """Unrealized gain fraction in [0, 1] from average-cost basis and account balance."""
        return min(1.0, max(0.0, 1.0 - float(basis) / max(1.0, float(balance))))

    @staticmethod
    def _equity_gain_fraction(basis, balance, alpha0):
        """Unrealized gain fraction of the equity share of a taxable account, in [0, 1].

        The model taxes bond and cash returns every year, so those holdings sit at their basis and
        the account's whole unrealized gain, balance - basis, is in the equities. The gain fraction
        is applied to the equity share of each withdrawal (alpha0 * w), so it is the whole-account
        fraction divided by alpha0; realized gains are then (1 - basis/balance) * w.
        """
        if alpha0 <= 0:
            return 0.0
        return min(1.0, Plan._gain_fraction_from_basis(basis, balance) / float(alpha0))

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
        Default is [1, 1, 1, 1] for taxable, tax-deferred, tax-free, and HSA accounts.
        A 3-element list (legacy) is auto-extended with 1.0 for the HSA account.
        """
        u.require_list(phi, "phi")
        if len(phi) == self.N_j - 1:
            phi = list(phi) + [1.0]
        if len(phi) != self.N_j:
            raise ValueError(f"Fractions must have {self.N_j} entries.")
        for j in range(self.N_j):
            if not (0 <= phi[j] <= 1):
                raise ValueError("Fractions must be between 0 and 1.")
        self.phi_j = np.array(phi, dtype=np.float32)
        self.mylog.vprint(
            "Spousal beneficiary fractions set to", ["{:.2f}".format(self.phi_j[j]) for j in range(self.N_j)]
        )
        self.caseStatus = "modified"

        if np.any(self.phi_j != 1):
            self.mylog.print("Consider changing spousal deposit fraction for better convergence.")
            self.mylog.print(f"\tRecommended: setSpousalDepositFraction({self.i_d}.)")

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

    def setLiquidationTaxRate(self, rate):
        """
        Set the assumed ordinary income tax rate applied to tax-deferred and HSA
        balances on the liquid balance sheet (the tax owed if those accounts were
        liquidated). Rate is in percent. Default is 24%.
        """
        if not (0 <= rate <= 100):
            raise ValueError("Rate must be between 0 and 100.")
        rate /= 100
        self.mylog.vprint(f"Liquidation tax rate on tax-deferred/HSA set to {u.pc(rate, f=0)}.")
        self.liquidationTaxRate = rate
        self.caseStatus = "modified"

    def setLiquidationCapGainsRate(self, rate):
        """
        Set the assumed capital-gains tax rate applied to fixed-asset disposition
        on the liquid balance sheet (commission plus this rate on the gain).
        Rate is in percent. Default is 15%.
        """
        if not (0 <= rate <= 100):
            raise ValueError("Rate must be between 0 and 100.")
        rate /= 100
        self.mylog.vprint(f"Liquidation capital-gains rate on fixed assets set to {u.pc(rate, f=0)}.")
        self.liquidationCapGainsRate = rate
        self.caseStatus = "modified"

    def _actual_effective_tax_rate(self):
        """Return actual ETR from LP solution: (T + U + J) / (G + Q). Returns 0 if no taxable income."""
        total_income = np.sum(self.G_n + self.Q_n)
        if total_income <= 0:
            return 0.0
        return float(np.sum(self.T_n + self.U_n + self.J_n) / total_income)

    def lifetime_allocation(self):
        """
        Return lifetime cash flow breakdown in today's dollars as two dicts.

        Returns a dict with keys:
          'outflows'  — {living, taxes, state_taxes, healthcare, debt, bequest}
          'income'    — {portfolio, ss, pension, wages, spia, other}
          'total'     — total lifetime outflows (today's $)

        The portfolio slice = total_outflows - sum(guaranteed income).
        Both dicts sum to 'total'.
        """
        inv_g = 1.0 / self.gamma_n[: self.N_n]
        Lambda_n = np.sum(self.Lambda_in, axis=0)
        bti_out = float(np.sum(np.maximum(0.0, -Lambda_n) * inv_g))
        bti_in = float(np.sum(np.maximum(0.0, Lambda_n) * inv_g))
        fa = float(
            np.sum(
                (self.fixed_assets_ordinary_income_n + self.fixed_assets_capital_gains_n + self.fixed_assets_tax_free_n)
                * inv_g
            )
        )
        outflows = {
            "living": float(np.sum(self.g_n * inv_g)),
            "taxes": float(np.sum((self.T_n + self.U_n + self.J_n) * inv_g)),
            "state_taxes": float(np.sum(self.st_T_n * inv_g)),
            "healthcare": float(np.sum((self.medicare_n + self.aca_costs_n) * inv_g)),
            "debt": float(np.sum(self.debt_payments_n * inv_g)),
            "bti": bti_out,
            # QCDs leave the portfolio for charity without passing through the budget.
            # Counting them here makes the gift visible; the portfolio slice below is a
            # residual, so it absorbs the same amount and both sides still balance.
            "charity": float(np.sum(np.sum(self.qcd_in, axis=0) * inv_g)),
            "bequest": self.bequest + self.partialBequest,
            "heirtax": self.heir_tax_liability + self.partial_heir_tax_liability,
        }
        guaranteed = {
            "ss": float(np.sum(np.sum(self.zetaBar_in, axis=0) * inv_g)),
            "pension": float(np.sum(np.sum(self.piBar_in, axis=0) * inv_g)),
            "wages": float(np.sum(np.sum(self.omega_in, axis=0) * inv_g)),
            "spia": float(np.sum(np.sum(self.spiaBar_in, axis=0) * inv_g)),
            "fixedassets": fa,
            "other": float(np.sum(np.sum(self.other_inc_in + self.netinv_in, axis=0) * inv_g)),
            "bti": bti_in,
        }
        total_outflows = sum(outflows.values())
        total_guaranteed = sum(guaranteed.values())
        income = dict(guaranteed)
        income["portfolio"] = max(0.0, total_outflows - total_guaranteed)
        return {
            "outflows": outflows,
            "income": income,
            "total": total_outflows,
            "fa_bequest": self.fixed_assets_bequest_value / self.gamma_n[-1],
        }

    def annual_cashflow_mix(self):
        """
        Return year-by-year cash flow breakdown in today's dollars.

        Returns a dict with keys:
          'outflows' — {living, taxes, state_taxes, healthcare, debt}  (arrays of length N_n)
          'income'   — {ss, pension, wages, spia, other, portfolio}  (arrays of length N_n)
          'year_n'   — calendar year array

        Bequest is excluded (it is a lump sum, not an annual flow).
        Normalization to percentages is done in the backends.
        """
        inv_g = 1.0 / self.gamma_n[: self.N_n]
        Lambda_n = np.sum(self.Lambda_in, axis=0) * inv_g
        fa_n = (
            self.fixed_assets_ordinary_income_n + self.fixed_assets_capital_gains_n + self.fixed_assets_tax_free_n
        ) * inv_g
        outflows = {
            "living": self.g_n * inv_g,
            "taxes": (self.T_n + self.U_n + self.J_n) * inv_g,
            "state_taxes": self.st_T_n * inv_g,
            "healthcare": (self.medicare_n + self.aca_costs_n) * inv_g,
            "debt": self.debt_payments_n * inv_g,
            "bti": np.maximum(0.0, -Lambda_n),
            # See lifetime_allocation: charity is funded from the portfolio residual.
            "charity": np.sum(self.qcd_in, axis=0) * inv_g,
        }
        guaranteed = {
            "ss": np.sum(self.zetaBar_in, axis=0) * inv_g,
            "pension": np.sum(self.piBar_in, axis=0) * inv_g,
            "wages": np.sum(self.omega_in, axis=0) * inv_g,
            "spia": np.sum(self.spiaBar_in, axis=0) * inv_g,
            "fixedassets": fa_n,
            "other": np.sum(self.other_inc_in + self.netinv_in, axis=0) * inv_g,
            "bti": np.maximum(0.0, Lambda_n),
        }
        total_out_n = sum(outflows.values())
        income = dict(guaranteed)
        income["portfolio"] = np.maximum(0.0, total_out_n - sum(guaranteed.values()))
        return {"outflows": outflows, "income": income, "year_n": self.year_n}

    def setPension(self, amounts, ages, indexed=None, survivor_fraction=None):
        """
        Set value of pension for each individual and commencement age.
        Units are in $.

        Parameters
        ----------
        amounts : array-like
            Monthly pension amounts per individual ($)
        ages : array-like
            Commencement ages per individual
        indexed : list of bool, optional
            Whether each pension is inflation-indexed
        survivor_fraction : list of float, optional
            Fraction of pension continuing to surviving spouse (0-1).
            Default: [0] * N_i (single-life, no survivor).
        """
        u.require_list(amounts, "amounts", self.N_i)
        u.require_list(ages, "ages", self.N_i)
        if indexed is None:
            indexed = [False] * self.N_i
        u.require_list(indexed, "indexed", self.N_i)
        if survivor_fraction is None:
            survivor_fraction = [0.0] * self.N_i
        u.require_list(survivor_fraction, "survivor_fraction", self.N_i)

        self.mylog.vprint(
            "Setting monthly pension of",
            [u.d(amounts[i]) for i in range(self.N_i)],
            "at age(s)",
            [int(ages[i]) for i in range(self.N_i)],
        )

        # Snap commencement ages to whole months (1/12-year granularity), for the
        # same reason as SS claiming ages: keep TOML round-trips consistent with
        # the UI's years+months input and avoid MILP-amplified precision drift.
        ages = np.round(np.asarray(ages, dtype=float) * 12.0) / 12.0

        thisyear = date.today().year
        self.pi_in = pension.compute_pension_benefits(
            amounts, ages, self.yobs, self.mobs, self.horizons, self.N_i, self.N_n, thisyear=thisyear
        )

        self.pensionAmounts = np.array(amounts, dtype=np.int32)
        self.pensionAges = np.array(ages)
        self.pensionIsIndexed = indexed
        self.pensionSurvivorFraction = np.array(survivor_fraction, dtype=np.float64)
        self.caseStatus = "modified"
        self._adjustedParameters = False

    def addSPIA(self, individual, buy_year, premium, monthly_income, indexed=False, survivor_fraction=0.0):
        """
        Add a qualified Single Premium Immediate Annuity (life-only).

        Parameters
        ----------
        individual : int
            Annuitant index (0 or 1).
        buy_year : int
            Calendar year of purchase; income begins same year. May be before the plan
            start year (already-purchased SPIA) — premium is ignored, income starts at year 0.
        premium : float
            Lump-sum cost in nominal dollars. Deducted from the individual's tax-deferred
            account (IRA rollover, non-taxable transfer). Ignored if buy_year < plan start.
        monthly_income : float
            Monthly benefit in nominal dollars at time of purchase.
        indexed : bool, optional
            False (default) = fixed nominal payments; True = CPI-linked.
        survivor_fraction : float, optional
            Fraction (0–1) of income continuing to the other individual after the annuitant
            dies. 0 = single-life (default).
        """
        n_buy = buy_year - self.year_n[0]
        if n_buy >= self.N_n:
            raise ValueError(f"buy_year {buy_year} is after the plan horizon end.")
        if not (0 <= individual < self.N_i):
            raise ValueError(f"individual {individual} out of range (0–{self.N_i - 1}).")
        self._spia_list.append(
            dict(
                individual=individual,
                buy_year=buy_year,
                premium=premium,
                monthly_income=monthly_income,
                indexed=indexed,
                survivor_fraction=survivor_fraction,
            )
        )
        # Past purchases have already been settled; only future/current ones affect the balance.
        if n_buy >= 0:
            self.spia_premiums_in[individual, n_buy] += premium
        self.caseStatus = "modified"
        self._adjustedParameters = False

    def setSocialSecurity(self, pias, ages, trim_pct=0, trim_year=None, survivor_claim_age="immediate"):
        """
        Set value of social security for each individual and claiming age.

        Note: Social Security benefits are paid in arrears (one month after eligibility).
        The zeta_in array represents when checks actually arrive, not when eligibility starts.

        The taxable fraction of benefits (Psi_n) is computed by the self-consistent loop
        from provisional income. To pin it instead, pass a numeric ``withSSTaxability``
        in the solver options; see :meth:`solve`.

        Parameters
        ----------
        survivor_claim_age : str or float, optional
            For a couple, when the surviving spouse claims the survivor benefit:
            ``"immediate"`` (default) as soon as eligible, ``"FRA"`` at the survivor
            full retirement age, or an explicit age in [60, 70]. The survivor's own
            benefit keeps the claiming age given in ``ages``, and each year the survivor
            receives the greater of the two, as SSA pays them.
        """
        u.require_list(pias, "pias", self.N_i)
        u.require_list(ages, "ages", self.N_i)
        survivor_claim_age = socsec.validate_survivor_claim_age(survivor_claim_age)

        if trim_pct != 0:
            if not (0 <= trim_pct <= 100):
                raise ValueError(f"trim_pct {trim_pct} outside range [0, 100].")
            if trim_year is None:
                raise ValueError("trim_year required when trim_pct > 0.")
            if not isinstance(trim_year, int):
                raise ValueError("trim_year must be an integer.")

        pias = np.array(pias, dtype=np.int32)
        ages = np.array(ages)
        # Snap claiming ages to whole months (1/12-year granularity). Claiming ages
        # carry month precision (e.g. 62 y 1 m = 62 + 1/12); a value that has
        # round-tripped through TOML as 62.083333 must resolve to the exact
        # 62 + 1/12 used everywhere else (e.g. the UI's years+months input),
        # otherwise a sub-cent benefit difference is amplified by the MILP.
        ages = np.round(np.asarray(ages, dtype=float) * 12.0) / 12.0
        ages_orig = ages.copy()

        fras = socsec.getFRAs(self.yobs, self.mobs, self.tobs)
        self.mylog.vprint("SS monthly PIAs set to", [u.d(pias[i]) for i in range(self.N_i)])
        self.mylog.vprint("SS FRAs(s)", [fras[i] for i in range(self.N_i)])

        thisyear = date.today().year
        self.zeta_in, ages = socsec.compute_social_security_benefits(
            pias,
            ages,
            self.yobs,
            self.mobs,
            self.tobs,
            self.horizons,
            self.N_i,
            self.N_n,
            trim_pct=trim_pct,
            trim_year=trim_year,
            thisyear=thisyear,
            survivor_claim_age=survivor_claim_age,
        )

        for i in range(self.N_i):
            if ages[i] != ages_orig[i]:
                eligible = 62 if (self.tobs[i] <= 2) else 62 + 1 / 12
                self.mylog.print(f"Resetting SS claiming age of {self.inames[i]} to {eligible}.")

        self.mylog.vprint("SS benefits claimed at age(s)", [ages[i] for i in range(self.N_i)])

        if trim_pct > 0:
            self.mylog.print(f"Reducing Social Security by {trim_pct}% starting in year {trim_year}.")

        survivor = socsec.compute_survivor_stream(
            pias,
            ages,
            self.yobs,
            self.mobs,
            self.tobs,
            self.horizons,
            self.N_i,
            self.N_n,
            survivor_claim_age=survivor_claim_age,
            trim_pct=trim_pct,
            trim_year=trim_year,
            thisyear=thisyear,
        )
        if survivor.survivor_idx >= 0:
            self._reportSurvivorClaimAge(survivor)

        self.ssecAmounts = pias
        self.ssecAges = ages
        self.ssecTrimPct = trim_pct
        self.ssecTrimYear = trim_year
        self.ssecSurvivorClaimAge = survivor_claim_age
        self.caseStatus = "modified"
        self._adjustedParameters = False

    def _reportSurvivorClaimAge(self, survivor):
        """
        Log the survivor's resolved claiming age, and say so whenever it was overridden.

        Three constraints can move the requested age: a survivor benefit cannot start
        before age 60, nor before the first passing, and it earns no delayed retirement
        credits past the survivor FRA. A permanent reduction is also worth flagging even
        when nothing was overridden, since the user may not have chosen it deliberately.
        """
        iname = self.inames[survivor.survivor_idx]
        requested = survivor.requested_age
        claim_age, fra, at_death = survivor.claim_age, survivor.survivor_fra, survivor.age_at_death
        self.mylog.vprint(f"SS survivor benefit for {iname} claimed at age {claim_age:.2f}.")

        if not isinstance(requested, str) and abs(claim_age - requested) > 1e-9:
            reasons = []
            if requested > fra + 1e-9:
                reasons.append(f"survivor benefits earn no delayed credits past their survivor FRA of {fra:.2f}")
            if requested < at_death - 1e-9:
                reasons.append(f"they are already {at_death:.2f} at the first passing")
            self.mylog.print(
                f"Survivor claiming age {requested} for {iname} ignored, using {claim_age:.2f}: "
                + "; ".join(reasons)
                + ".",
                tag="WARNING",
            )

        if claim_age < fra - 1e-9:
            pct = 100 * socsec._survivor_factor(fra, claim_age)
            self.mylog.print(
                f"Survivor benefit for {iname} starts at age {claim_age:.2f}, below their survivor FRA of "
                f"{fra:.2f}, so it is permanently reduced to {pct:.1f}% of the full amount. "
                f"Set the survivor claiming age to 'FRA' to defer it instead."
            )

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

        self.xi_n = spending.gen_spending_profile(
            profile, self.chi, self.n_d, self.N_n, dip=dip, increase=increase, delay=delay
        )

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
                    seed = int(time.time() * 1_000_000)  # Use microseconds
            else:
                seed = int(seed)
            self.rateSeed = seed
        else:
            # For non-reproducible rates, clear the seed
            # setRates() will generate a new seed each time it's called
            self.rateSeed = None

    def setRates(
        self,
        method,
        frm=None,
        to=None,
        values=None,
        stdev=None,
        corr=None,
        df=None,
        method_file=None,
        override_reproducible=False,
        reverse=False,
        roll=0,
        **kwargs,
    ):
        """
        Generate rates using pluggable rate model architecture.

        Fully metadata-driven:
            - No method-specific filtering
            - Validation handled inside each RateModel
            - Supports built-in and plugin models

        Unit convention:
            values: rates in percent (e.g. 7.0 = 7%), matching the format
                returned by getRatesDistributions() and consistent with
                setDividendRate/setHeirsTaxRate.
            stdev: standard deviations in percent (e.g. 17.0 = 17%).
        """

        # --------------------------------------------------
        # Determine seed handling
        # --------------------------------------------------

        if self.reproducibleRates and not override_reproducible:
            seed = self.rateSeed
        elif override_reproducible:
            seed = int(time.time() * 1_000_000)
        else:
            seed = None

        # --------------------------------------------------
        # Legacy compatibility: historical shorthand
        # --------------------------------------------------

        if method in HISTORICAL_RANGE_METHODS:
            if frm is not None and to is None:
                to = frm + self.N_n - 1

        # --------------------------------------------------
        # Build model configuration dictionary
        # --------------------------------------------------

        model_config = {"method": method}

        # Only include parameters that are not None
        base_args = {
            "frm": frm,
            "to": to,
            "values": values,
            "stdev": stdev,
            "corr": corr,
            "df": df,
        }

        for k, v in base_args.items():
            if v is not None:
                model_config[k] = v

        # Include any additional keyword arguments
        model_config.update(kwargs)

        if model_config.get("constrain_mean") and method not in CONSTRAIN_MEAN_METHODS:
            self.mylog.print(
                f"constrain_mean=True has no effect for rate method '{method}'. "
                f"Supported methods: {', '.join(CONSTRAIN_MEAN_METHODS)}.",
                tag="WARNING",
            )

        if method == "dataframe":
            model_config["n_years"] = self.N_n

        # --------------------------------------------------
        # Load rate model class
        # --------------------------------------------------

        from owlplanner.rate_models.loader import load_rate_model

        ModelClass = load_rate_model(method, method_file)

        model = ModelClass(
            config=model_config,
            seed=seed,
            logger=self.mylog,
        )

        # --------------------------------------------------
        # Generate series
        # --------------------------------------------------

        series = model.generate(self.N_n)

        if series.shape != (self.N_n, 4):
            raise RuntimeError(f"Rate model returned shape {series.shape}, expected ({self.N_n}, 4)")

        # --------------------------------------------------
        # Store model + metadata
        # --------------------------------------------------

        self.rateModel = model
        self.rateMethod = method
        self.rateMethodFile = method_file
        self.rateReverse = bool(reverse)
        self.rateRoll = int(roll)

        # Store frm/to if present in model config
        self.rateFrm = model.config.get("frm")
        self.rateTo = model.config.get("to")

        # Backward compatibility fields (for built-in stochastic/user)
        self.rateValues = model.params.get("values")
        self.rateStdev = model.params.get("stdev")
        self.rateCorr = model.params.get("corr")

        if self.rateValues is not None:
            self.rateValues = np.array(self.rateValues)

        if self.rateStdev is not None:
            self.rateStdev = np.array(self.rateStdev)

        if self.rateCorr is not None:
            self.rateCorr = np.array(self.rateCorr)

        # --------------------------------------------------
        # Apply reverse / roll
        # --------------------------------------------------

        # model.generate returns (N, 4)
        # tau_kn must be (4, N)
        series_kn = series.transpose()

        if getattr(model, "constant", False):
            if reverse or roll != 0:
                self.mylog.print("reverse and roll are ignored for constant (fixed) rate methods.", tag="WARNING")
        else:
            series_kn = rates.apply_rate_sequence_transform(
                series_kn,
                reverse,
                roll,
            )

        self.tau_kn = series_kn

        # --------------------------------------------------
        # Inflation multiplier
        # --------------------------------------------------

        self.gamma_n = rates.gen_gamma_n(self.tau_kn)

        self._adjustedParameters = False
        self.caseStatus = "modified"

        self.mylog.vprint(f"Generated {self.N_n} years of rates using model '{method}'.")

    def regenRates(self, override_reproducible=False):
        """
        Regenerate stochastic rate series using stored model.
        """

        if not hasattr(self, "rateModel") or self.rateModel is None:
            return

        # Do not regenerate deterministic models
        if getattr(self.rateModel, "deterministic", False):
            return

        # Respect reproducibility setting
        if self.reproducibleRates and not override_reproducible:
            return

        # Generate new series
        series = self.rateModel.generate(self.N_n)

        if series.shape != (self.N_n, 4):
            raise RuntimeError(f"Rate model returned shape {series.shape}, expected ({self.N_n}, 4)")

        series_kn = series.transpose()

        if not getattr(self.rateModel, "constant", False):
            series_kn = rates.apply_rate_sequence_transform(
                series_kn,
                self.rateReverse,
                self.rateRoll,
            )

        self.tau_kn = series_kn
        self.gamma_n = rates.gen_gamma_n(self.tau_kn)

        self.mylog.vprint("Regenerated stochastic rate series.")

    def setAccountBalances(self, *, taxable, taxDeferred, taxFree, hsa=None, startDate=_UNCHANGED, units="k"):
        """
        Three lists (plus optional HSA) containing the balance of all assets in each category
        for each spouse.  For single individuals, these lists will contain only one entry.
        Units are in $k, unless specified otherwise: 'k', 'M', or '1'.

        startDate is the date at which these balances are known; they are back projected to
        January 1st from it, so the plan itself still starts at the beginning of the year.
        Omit it to keep the date already on the plan - re-stating balances is not a statement
        about when they were measured. Pass None or "today" to mean today explicitly, or a
        date in any format _setStartingDate() accepts.
        """
        u.require_list(taxable, "taxable", self.N_i)
        u.require_list(taxDeferred, "taxDeferred", self.N_i)
        u.require_list(taxFree, "taxFree", self.N_i)

        fac = u.getUnits(units)
        taxable = u.rescale(taxable, fac)
        taxDeferred = u.rescale(taxDeferred, fac)
        taxFree = u.rescale(taxFree, fac)

        self.bet_ji = np.zeros((self.N_j, self.N_i))
        self.bet_ji[0][:] = taxable
        self.bet_ji[1][:] = taxDeferred
        self.bet_ji[2][:] = taxFree
        if hsa is not None:
            u.require_list(hsa, "hsa", self.N_i)
            self.bet_ji[3][:] = [v * fac for v in hsa]
        self.beta_ij = self.bet_ji.transpose()

        # An omitted date keeps whatever the plan already had, so that re-stating balances
        # (setHSA does exactly that, and so does any caller adjusting one account) cannot
        # silently re-date them to today and shift every opening balance through
        # yearFracLeft. On a plan that has no date yet, fall back to today as before.
        if startDate is _UNCHANGED:
            startDate = self.startDate
        self._setStartingDate(startDate)

        self.caseStatus = "modified"

        self.mylog.vprint("Taxable balances:", *[u.d(taxable[i]) for i in range(self.N_i)])
        self.mylog.vprint("Tax-deferred balances:", *[u.d(taxDeferred[i]) for i in range(self.N_i)])
        self.mylog.vprint("Tax-free balances:", *[u.d(taxFree[i]) for i in range(self.N_i)])
        if hsa is not None:
            hsa_arr = self.bet_ji[3]
            self.mylog.vprint("HSA balances:", *[u.d(hsa_arr[i]) for i in range(self.N_i)])
        self.mylog.vprint("Sum of all savings accounts:", u.d(np.sum(taxable) + np.sum(taxDeferred) + np.sum(taxFree)))
        self.mylog.vprint(
            "Post-tax total wealth of approximately",
            u.d(np.sum(taxable) + 0.7 * np.sum(taxDeferred) + np.sum(taxFree)),
        )

    def setHSA(self, balances, medicare_ages=None, units="k"):
        """
        Set HSA (Health Savings Account) initial balances and Medicare enrollment ages.
        HSA contributions stop when Medicare enrollment begins (~age 65).

        Parameters
        ----------
        balances : list
            Initial HSA balance per individual (in $k by default).
        medicare_ages : list, optional
            Age at which HSA contributions stop for each individual (default: 65).
        units : str, optional
            Units for balances: 'k' (default), 'M', or '1'.
        """
        self.setAccountBalances(
            taxable=list(self.bet_ji[0]),
            taxDeferred=list(self.bet_ji[1]),
            taxFree=list(self.bet_ji[2]),
            hsa=balances,
            units=units,
        )
        thisyear = date.today().year
        ages = medicare_ages if medicare_ages is not None else [65] * self.N_i
        for i in range(self.N_i):
            n_hsa = self.yobs[i] + ages[i] - thisyear
            self.n_hsa_i[i] = min(max(0, n_hsa), self.N_n)
        self.mylog.vprint("HSA contribution stop years:", [int(self.n_hsa_i[i]) for i in range(self.N_i)])

    def setMedicalExpenses(self, amount, units="k"):
        """
        Set annual non-Medicare qualified medical expenses used to cap HSA withdrawals.

        HSA withdrawals are tax-free only up to total qualified medical expenses (QMEs).
        Pre-Medicare years: only this amount is eligible (Medicare costs are zero then).
        Post-Medicare years: this amount plus Medicare costs are both eligible.
        Without this call, HSA withdrawals in pre-Medicare years are capped at zero.

        The amount is in today's dollars and is inflation-adjusted each plan year.

        Parameters
        ----------
        amount : float
            Annual non-Medicare medical expenses in today's dollars (default unit: $k).
        units : str
            Unit of amount: 'k' ($k), 'M' ($M), or '$' (dollars).
        """
        fac = u.getUnits(units)
        self.other_medical_k = float(amount) * fac
        self.mylog.vprint(f"Annual non-Medicare medical expenses set to ${float(amount):.1f}{units}/year (today's $).")

    def setACA(self, slcsp, units="k", start_year=None):
        """
        Configure ACA marketplace health insurance premium for pre-Medicare years.

        Sets the annual benchmark Silver plan (SLCSP) premium for this household.
        The Premium Tax Credit reduces this by the amount that household income exceeds
        the required self-contribution (a piecewise-linear % of MAGI keyed to FPL).
        ACA costs are only assessed in years where at least one individual is under 65
        and within their planning horizon.

        Parameters
        ----------
        slcsp : float or list of float
            Annual benchmark Silver plan premium in today's dollars (default units: $k).
            For couples, set this to the combined household plan premium; when one
            partner transitions to Medicare the code automatically scales it down to
            the remaining partner's individual plan using the CMS age rating curve.
            If a scalar, applied uniformly across all plan years (inflation-adjusted).
            If a list of length N_n, used as-is (each entry inflated for that year).
        units : str
            Unit multiplier: 'k' ($k, default), 'M' ($M), '1' (dollars).
        start_year : int, optional
            Calendar year when ACA coverage begins. Years before this are treated as
            employer-covered (zero ACA cost). Default None (or 0) = from plan start.
        """
        fac = u.getUnits(units)
        if np.isscalar(slcsp):
            self.slcsp_annual = float(slcsp) * fac
            self.mylog.vprint(f"ACA benchmark premium set to ${self.slcsp_annual / 1000:.1f}k/year (today's $).")
        else:
            raise ValueError(
                "setACA: slcsp must be a scalar (today's $). For per-year amounts use a list "
                "with a future per-year API."
            )
        if start_year is not None and int(start_year) > 0:
            sy = int(start_year)
            if sy < 2000:
                raise ValueError(
                    f"setACA: start_year={sy} looks like an offset rather than a calendar year. "
                    f"Use a 4-digit calendar year (e.g. {date.today().year + sy})."
                )
            self.aca_start_year = sy
            self.mylog.vprint(f"ACA coverage starts in calendar year {self.aca_start_year}.")
        self.caseStatus = "modified"

    def setStateTax(self, state, moves=None, locality=""):
        """
        Set two-letter US state abbreviation for state income tax modeling.

        When set, state income tax brackets are embedded directly in the LP using
        graduated state marginal rates, standard deduction, and optional retirement
        income exemptions. Leave blank or call with "" to model federal taxes only.

        Supported states: all 50 states + DC. No-income-tax states (AK, FL, NV, etc.)
        are accepted and simply contribute zero state tax.

        Parameters
        ----------
        state : str
            Two-letter state abbreviation (e.g. 'MN', 'CA', 'TX'). Case-insensitive.
            This is the state of residence in the first plan year.
        moves : list, optional
            Later changes of residence, as ``[{"year": 2031, "state": "FL"}]`` (or
            ``[(2031, "FL")]``); an entry may also name a ``locality`` (third tuple item).
            From that calendar year to the next move or the end of the plan, the household
            lives in the new state ("" for none) and locality: the residence on December 31
            taxes the whole year, so the year of the move is taxed by the new residence.
            Each year must fall after the first plan year and within the plan. Upstream Owl
            takes at most one move; this fork takes several. Omitted or empty, the household
            stays in ``state`` throughout.
        locality : str
            City or county whose income tax applies on top of the state's, e.g. 'NYC' or
            'Yonkers' for NY (see data/taxes_local.toml). Blank for none.
        """
        state, locality = residency.normalize(state, locality)
        moves = sorted(residency.as_residence(m) for m in (moves or []))
        residency.residence_by_year(state, locality, moves, int(self.year_n[0]), self.N_n)  # validates
        self.state = state
        self.locality = locality
        self.state_moves = moves
        for m in moves:
            where = f"'{m.state}'" + (f", {m.locality}" if m.locality else "")
            self.mylog.vprint(f"Residence from {m.year}: {where}.")
        self.caseStatus = "modified"

    def _residence_by_year(self):
        "(state, locality) in force in each plan year."
        return residency.residence_by_year(
            self.state, self.locality, self.state_moves, int(self.year_n[0]), self.N_n
        )

    def _states_n(self):
        """State of residence in each plan year ("" for none)."""
        return [state for state, _ in self._residence_by_year()]

    def setInterpolationMethod(self, method, center=15, width=5):
        """
        Interpolate asset allocation ratios from initial value (today) to
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
            raise ValueError(f"Method '{method}' not supported.")

        self.interpMethod = method
        self.caseStatus = "modified"

        self.mylog.vprint(f"Asset allocation interpolation method set to '{method}'.")

    def setAllocationRatios(
        self,
        allocType,
        taxable=None,
        taxDeferred=None,  # noqa: C901
        taxFree=None,
        hsa=None,
        generic=None,
    ):
        """
        Single function for setting all types of asset allocations.
        Allocation types are 'account', 'individual', and 'spouses'.

        Each allocation is an [initial, final] pair of percentages over the N_k
        asset classes, e.g., [[ko0, ko1, ko2, ko3], [kf0, kf1, kf2, kf3]], where
        ko is the initial allocation and kf the final one. Each individual glides
        from initial to final over their own horizon, so individuals with different
        life expectancies follow different glide paths even when given the same pair.
        Per-individual lists follow the order of the names provided.

        For 'account', each savings account type gets one pair per individual:
        taxable = [[[ko00, ko01, ko02, ko03], [kf00, kf01, kf02, kf03]],
                   [[ko10, ko11, ko12, ko13], [kf10, kf11, kf12, kf13]]]
        and likewise for taxDeferred and taxFree. hsa is optional and defaults to taxFree.

        For 'individual', one pair per individual is applied to all of that
        individual's accounts:
        generic = [[[ko00, ko01, ko02, ko03], [kf00, kf01, kf02, kf03]],
                   [[ko10, ko11, ko12, ko13], [kf10, kf11, kf12, kf13]]]

        'spouses' is an input shorthand for 'individual' where the same pair applies
        to every individual, so only that one pair is given:
        generic = [[ko0, ko1, ko2, ko3], [kf0, kf1, kf2, kf3]]
        It is expanded on input and the plan records the allocation as 'individual'.
        """
        # Validate allocType parameter
        validTypes = ["account", "individual", "spouses"]
        if allocType not in validTypes:
            raise ValueError(f"allocType must be one of {validTypes}, got '{allocType}'.")

        if allocType == "spouses":
            if generic is None or len(generic) != 2:
                raise ValueError("generic must have 2 entries (initial and final).")
            generic = [[np.asarray(generic[0]).tolist(), np.asarray(generic[1]).tolist()] for _ in range(self.N_i)]
            allocType = "individual"

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
                self.mylog.vprint(f"{self.inames[i]}: Setting gliding allocation ratios (%) to '{allocType}'.")
                self.mylog.vprint(f"      taxable: {taxable[i][0]} -> {taxable[i][1]}")
                self.mylog.vprint(f"  taxDeferred: {taxDeferred[i][0]} -> {taxDeferred[i][1]}")
                self.mylog.vprint(f"      taxFree: {taxFree[i][0]} -> {taxFree[i][1]}")

            # Order in alpha is j, i, 0/1, k.
            alpha = {}
            alpha[0] = np.array(taxable)
            alpha[1] = np.array(taxDeferred)
            alpha[2] = np.array(taxFree)
            alpha[3] = np.array(hsa) if hsa is not None else np.array(taxFree)  # HSA inherits tax-free by default
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
            self.boundsAR["hsa"] = hsa if hsa is not None else taxFree

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
                self.mylog.vprint(f"{self.inames[i]}: Setting gliding allocation ratios (%) to '{allocType}'.")
                self.mylog.vprint(f"\t{generic[i][0]} -> {generic[i][1]}")

            for i in range(self.N_i):
                Nin = self.horizons[i] + 1
                for k in range(self.N_k):
                    start = generic[i][0][k] / 100
                    end = generic[i][1][k] / 100
                    dat = self._interpolator(start, end, Nin)
                    self.alpha_ijkn[i, :, k, :Nin] = dat[:]

            self.boundsAR["generic"] = generic

        self.ARCoord = allocType
        self.caseStatus = "modified"

        self.mylog.vprint(f"Interpolating asset allocation ratios using '{self.interpMethod}' method.")

    def readHFP(self, filename, filename_for_logging=None, houseTables=True):
        """
        Load the Household Financial Profile (HFP) from file.

        The HFP file contains wages, contributions, Roth conversions,
        big-ticket items (per individual), and optionally Debts and Fixed Assets.
        File can be an excel, or odt file with one tab named after each
        spouse and recognizing the following column headers:

                'year',
                'anticipated wages',
                'other inc',
                'net inv',
                'taxable ctrb',
                '401k ctrb',
                'Roth 401k ctrb',
                'IRA ctrb',
                'Roth IRA ctrb',
                'HSA ctrb',
                'Roth conv',
                'QCD',
                'big-ticket items'

        in any order. Only 'year' is required: list the columns your household
        actually uses, and any other column that is absent is treated as zero
        for every year. A header differing from a recognized one only by case,
        spacing, or punctuation is rejected as a typo rather than dropped.
        Legacy header 'other inc.' is read as 'other inc'.
        Optional workbook sheets 'Debts' and 'Fixed Assets' follow HFP formats.
        A template is provided as an example.
        Missing rows (years) are populated with zero values.

        Convention: 'anticipated wages' must be entered net of all
        contribution columns. Contributions are deposited into their
        accounts and are not subtracted from the annual cash flow.

        Parameters
        ----------
        filename : file-like object, str, or dict
            Input file or dictionary of DataFrames
        filename_for_logging : str, optional
            Explicit filename for logging purposes. If provided, this will be used
            in log messages instead of trying to extract it from filename.
        houseTables : bool, optional
            False reads the per-person sheets only and leaves the Debts and Fixed Assets
            tables, and their raw sheets, as they are.
        """
        try:
            returned_filename, self.timeLists, houseLists, rawHFP, self.hfpAbsentCols = hfp_io.read(
                filename, self.inames, self.horizons, self.mylog, filename=filename_for_logging,
                houseTables=houseTables,
            )
        except Exception as e:
            raise Exception(f"Unsuccessful read of Household Financial Profile: {e}") from e
        if houseTables:
            self.houseLists = houseLists
            self.rawHFP = rawHFP
        else:
            # Keep the household sheets already held; replace the per-person ones.
            kept = {k: v for k, v in (self.rawHFP or {}).items() if k in ("Debts", "Fixed Assets")}
            self.rawHFP = {**kept, **rawHFP}

        # Use filename_for_logging if provided, otherwise use returned filename
        self.hfpFileName = filename_for_logging if filename_for_logging is not None else returned_filename
        self.setContributions()

        return True

    def validateRothConversions(self):
        """
        Check that every "Roth conv" amount is non-negative.

        A negative amount used to mean "force no conversion this year". That mode now
        lives in the "Roth conv fixed" flag, so the sign carries no meaning and a
        negative figure is an input error rather than an instruction.
        """
        for iname in self.inames:
            df = self.timeLists[iname]
            if "Roth conv" not in df.columns:
                continue
            bad = df.loc[df["Roth conv"] < 0, "year"]
            if len(bad):
                years = ", ".join(str(int(y)) for y in bad)
                raise ValueError(
                    f"Negative 'Roth conv' amount for {iname} in year(s) {years}. To hold a year "
                    "at no conversion, enter 0 and tick 'Roth conv fixed' for that year."
                )

    def setContributions(self, timeLists=None):
        """
        If no argument is given, use the values that have been stored in self.timeLists.
        """
        if timeLists is not None:
            self.timeLists = timeLists
            # These tables carry every column, so none is absent (see readHFP).
            self.hfpAbsentCols = {iname: [] for iname in self.inames}

        # Staged, not assigned: validateQCD() below rejects the whole table on a bad
        # cell, and self.qcd_in must not be left holding values that were refused.
        qcd_in = np.zeros((self.N_i, self.N_n))

        # Reject a negative amount here as well as on the file-read path: a table can
        # also arrive from the UI editor or from a caller writing it directly.
        self.validateRothConversions()

        # Now fill in parameters which are in $.
        for i, iname in enumerate(self.inames):
            h = self.horizons[i]
            self.omega_in[i, :h] = self.timeLists[iname]["anticipated wages"].iloc[5 : 5 + h]
            self.other_inc_in[i, :h] = self.timeLists[iname]["other inc"].iloc[5 : 5 + h]
            self.netinv_in[i, :h] = self.timeLists[iname]["net inv"].iloc[5 : 5 + h]
            self.Lambda_in[i, :h] = self.timeLists[iname]["big-ticket items"].iloc[5 : 5 + h]
            qcd_in[i, :h] = self.timeLists[iname]["QCD"].iloc[5 : 5 + h]

            # Values for last 5 years of Roth conversion and contributions stored at the end
            # of array and accessed with negative index.
            self.kappa_ijn[i, 0, :h] = self.timeLists[iname]["taxable ctrb"][5 : h + 5]
            self.kappa_ijn[i, 1, :h] = self.timeLists[iname]["401k ctrb"][5 : h + 5]
            self.kappa_ijn[i, 1, :h] += self.timeLists[iname]["IRA ctrb"][5 : h + 5]
            self.kappa_ijn[i, 2, :h] = self.timeLists[iname]["Roth 401k ctrb"][5 : h + 5]
            self.kappa_ijn[i, 2, :h] += self.timeLists[iname]["Roth IRA ctrb"][5 : h + 5]
            self.kappa_ijn[i, 3, :h] = self.timeLists[iname]["HSA ctrb"][5 : h + 5]
            # Zero HSA contributions after Medicare enrollment year.
            # If n_hsa_i was never set (still at default N_n), initialize from yobs and age 65
            # so programmatic plans that bypass config still get correct Medicare cutoff.
            if self.n_hsa_i[i] >= self.N_n:
                thisyear = date.today().year
                n_hsa = self.yobs[i] + 65 - thisyear
                self.n_hsa_i[i] = min(max(0, n_hsa), self.N_n)
            n_stop = self.n_hsa_i[i]
            if n_stop < h:
                self.kappa_ijn[i, 3, n_stop:h] = 0.0
            self.myRothX_in[i, :h] = self.timeLists[iname]["Roth conv"][5 : h + 5]
            self.rothXfixed_in[i, :h] = np.asarray(
                self.timeLists[iname]["Roth conv fixed"][5 : h + 5], dtype=bool
            )

            # Last 5 years are at the end of the N_n array.
            self.kappa_ijn[i, 0, -5:] = self.timeLists[iname]["taxable ctrb"][:5]
            self.kappa_ijn[i, 1, -5:] = self.timeLists[iname]["401k ctrb"][:5]
            self.kappa_ijn[i, 1, -5:] += self.timeLists[iname]["IRA ctrb"][:5]
            self.kappa_ijn[i, 2, -5:] = self.timeLists[iname]["Roth 401k ctrb"][:5]
            self.kappa_ijn[i, 2, -5:] += self.timeLists[iname]["Roth IRA ctrb"][:5]
            self.kappa_ijn[i, 3, -5:] = self.timeLists[iname]["HSA ctrb"][:5]
            self.myRothX_in[i, -5:] = self.timeLists[iname]["Roth conv"][:5]

        self.validateQCD(qcd_in=qcd_in)
        self.qcd_in[:, :] = qcd_in

        self.caseStatus = "modified"

        return self.timeLists

    def validateQCD(self, qcd_in=None, inames=None):
        """
        Check Qualified Charitable Distributions against the two statutory rules Owl
        can verify: the age-70½ threshold and the annual per-person exclusion limit.

        Raises ValueError on a violation. Pass qcd_in to check candidate values
        without touching the plan -- editors use this to reject a bad cell at entry
        rather than at solve time.

        The limit is published a year at a time, so beyond the table it is carried
        forward at a fixed assumed inflation (tx.qcdLimitForYear). Projecting rather
        than holding the last published figure flat matters: giving indexed to
        inflation, the natural way to express a constant real gift, crosses a flat
        cap within a few years and would otherwise be rejected wholesale.
        """
        qcd_in = self.qcd_in if qcd_in is None else np.atleast_2d(qcd_in)
        inames = self.inames if inames is None else inames

        thisyear = date.today().year
        last_published = max(tx.qcdLimit)
        for i, iname in enumerate(inames):
            for n in range(min(self.horizons[i], qcd_in.shape[1])):
                amount = qcd_in[i, n]
                if amount <= 0:
                    continue
                year = thisyear + n
                if n < self.n_qcd_i[i]:
                    age = year - self.yobs[i]
                    raise ValueError(
                        f"QCD of ${amount:,.0f} for {iname} in {year}: a Qualified Charitable "
                        f"Distribution requires age 70½, and {iname} turns {age} that year."
                    )
                cap = tx.qcdLimitForYear(year)
                if amount > cap:
                    basis = (
                        "the annual per-person exclusion limit"
                        if year <= last_published
                        else (
                            f"the projected annual per-person exclusion limit "
                            f"({last_published}'s ${tx.qcdLimit[last_published]:,.0f} carried forward at "
                            f"{100 * tx.QCD_LIMIT_INFLATION:.1f}% inflation)"
                        )
                    )
                    raise ValueError(
                        f"QCD of ${amount:,.0f} for {iname} in {year} exceeds {basis} of ${cap:,.0f}."
                    )

    def processDebtsAndFixedAssets(self):
        """
        Process debts and fixed assets from houseLists and populate arrays.
        Should be called after setContributions() and before solve().
        """
        thisyear = date.today().year

        # Process debts
        if "Debts" in self.houseLists and not u.is_dataframe_empty(self.houseLists["Debts"]):
            self.debt_payments_n = debts.get_debt_payments_array(self.houseLists["Debts"], self.N_n, thisyear)
            self.remaining_debt_balance = debts.get_remaining_debt_balance(self.houseLists["Debts"], self.N_n, thisyear)
            self.fixed_assets_debt_balances_remaining_n = debts.get_debt_balances_array(
                self.houseLists["Debts"], self.N_n, thisyear
            )
        else:
            self.debt_payments_n = np.zeros(self.N_n)
            self.remaining_debt_balance = 0.0
            self.fixed_assets_debt_balances_remaining_n = np.zeros(self.N_n)

        # Process fixed assets
        if "Fixed Assets" in self.houseLists and not u.is_dataframe_empty(self.houseLists["Fixed Assets"]):
            filing_status = "married" if self.N_i == 2 else "single"
            gamma_n = getattr(self, "gamma_n", None)
            (self.fixed_assets_tax_free_n, self.fixed_assets_ordinary_income_n, self.fixed_assets_capital_gains_n) = (
                fxasst.get_fixed_assets_arrays(
                    self.houseLists["Fixed Assets"], self.N_n, gamma_n, thisyear, filing_status
                )
            )
            # Calculate bequest value for assets with yod past plan end
            self.fixed_assets_bequest_value = fxasst.get_fixed_assets_bequest_value(
                self.houseLists["Fixed Assets"], self.N_n, gamma_n, thisyear
            )
            # Current market value of fixed assets still held at the start of each year
            self.fixed_assets_current_asset_values_n = fxasst.get_fixed_assets_current_values_array(
                self.houseLists["Fixed Assets"], self.N_n, gamma_n, thisyear
            )
            # Disposition cost (commission + capital-gains tax) of assets still held each year
            self.fixed_assets_disposition_costs_n = fxasst.get_fixed_assets_disposition_costs_array(
                self.houseLists["Fixed Assets"],
                self.N_n,
                gamma_n,
                self.liquidationCapGainsRate,
                thisyear,
                filing_status,
            )
        else:
            self.fixed_assets_tax_free_n = np.zeros(self.N_n)
            self.fixed_assets_ordinary_income_n = np.zeros(self.N_n)
            self.fixed_assets_capital_gains_n = np.zeros(self.N_n)
            self.fixed_assets_bequest_value = 0.0
            self.fixed_assets_current_asset_values_n = np.zeros(self.N_n)
            self.fixed_assets_disposition_costs_n = np.zeros(self.N_n)

    def getFixedAssetsBequestValueInTodaysDollars(self):
        """
        Return the fixed assets bequest value in today's dollars.
        This requires rates to be set to calculate gamma_n (inflation factor).

        Returns:
        --------
        float
            Fixed assets bequest value in today's dollars. HFP monetary values
            (basis, value) are stored in dollars; the UI divides by 1000 for k$ display.
            Returns 0.0 if rates not set, gamma_n not calculated, or no fixed assets.
        """
        if self.fixed_assets_bequest_value == 0.0:
            return 0.0

        # Check if we can calculate gamma_n
        if self.rateMethod is None or not hasattr(self, "tau_kn"):
            # Rates not set yet - return 0
            return 0.0

        # Calculate gamma_n if not already calculated
        if not hasattr(self, "gamma_n") or self.gamma_n is None:
            self.gamma_n = rates.gen_gamma_n(self.tau_kn)

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
            export._format_spreadsheet(sheet, "currency")

        wb = Workbook()
        ws = wb.active
        fillsheet(ws, 0)

        if self.N_i == 2:
            ws = wb.create_sheet(self.inames[1])
            fillsheet(ws, 1)

        # Add Debts sheet if available
        if "Debts" in self.houseLists and not u.is_dataframe_empty(self.houseLists["Debts"]):
            ws = wb.create_sheet("Debts")
            df = self.houseLists["Debts"]
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)
            export._format_debts_sheet(ws)
        else:
            # Create empty Debts sheet with proper columns
            ws = wb.create_sheet("Debts")
            df = pd.DataFrame(columns=hfp_io._debtItems)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)
            export._format_debts_sheet(ws)

        # Add Fixed Assets sheet if available
        if "Fixed Assets" in self.houseLists and not u.is_dataframe_empty(self.houseLists["Fixed Assets"]):
            ws = wb.create_sheet("Fixed Assets")
            df = self.houseLists["Fixed Assets"]
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)
            export._format_fixed_assets_sheet(ws)
        else:
            # Create empty Fixed Assets sheet with proper columns
            ws = wb.create_sheet("Fixed Assets")
            df = pd.DataFrame(columns=hfp_io._fixedAssetItems)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)
            export._format_fixed_assets_sheet(ws)

        return wb

    def saveHFP(self, basename=None, overwrite=False):
        """
        Save the Household Financial Profile (HFP) as an Excel workbook.

        This is the write counterpart of readHFP(): the workbook contains one
        sheet per individual (wages, contributions, Roth conversions,
        big-ticket items) plus the Debts and Fixed Assets sheets, and can be
        read back with readHFP().

        If the plan's time lists are stale with respect to its internal
        arrays (e.g., the plan was populated programmatically by writing
        directly into omega_in, kappa_ijn, etc.), the time lists are first
        reconstructed from the arrays and stored on the plan. This
        reconstruction writes tax-deferred contributions to the '401k ctrb'
        column and tax-free contributions to the 'Roth IRA ctrb' column, as
        the original column split is not retained internally.

        On success, hfpFileName is updated so that a subsequent saveConfig()
        references the saved workbook.

        Parameters
        ----------
        basename : str, optional
            Base name for the file. Defaults to the plan name. The file is
            saved as 'HFP_<basename>.xlsx' unless basename already contains
            a file extension, in which case it is used verbatim.
        overwrite : bool, default False
            When False, prompt for confirmation before overwriting an
            existing file.

        Returns
        -------
        str or None
            The name of the file saved, or None if saving was skipped.
        """
        # Time lists are stale when the plan was populated by writing directly
        # into the arrays. Keep them when they still agree with the arrays, as
        # they preserve the 401k/IRA column split that the arrays merge.
        rebuilt, _ = hfp_io.build_hfp_dataframes(self)
        compare = self.timeLists
        if compare and all(iname in compare for iname in self.inames):
            # setContributions() zeroes HSA contributions past Medicare enrollment
            # in the arrays only; apply the same clip to a comparison copy so such
            # rows do not flag the time lists as stale.
            compare = {iname: compare[iname].copy() for iname in self.inames}
            for i, iname in enumerate(self.inames):
                df = compare[iname]
                n_stop, h = self.n_hsa_i[i], self.horizons[i]
                if "HSA ctrb" in df.columns and n_stop < h:
                    df.iloc[5 + n_stop : 5 + h, df.columns.get_loc("HSA ctrb")] = 0.0
        if not hfp_io.time_lists_agree(compare, rebuilt):
            self.timeLists = rebuilt

        wb = self.saveContributions()

        if basename is None:
            basename = self._name

        if Path(basename).suffixes == []:
            if not basename.startswith("HFP_"):
                basename = "HFP_" + basename
            fname = basename + ".xlsx"
        else:
            fname = basename

        fname = export._save_workbook(wb, fname, overwrite, self.mylog)
        if fname is not None:
            self.hfpFileName = fname

        return fname

    def zeroWagesAndContributions(self):
        """
        Zero wages, contributions, Roth conversions, and big-ticket items.
        Resets timeLists; does not modify Debts or Fixed Assets.
        """
        self.mylog.vprint("Resetting wages and contributions to zero.")

        # Reset parameters with zeros.
        self.omega_in[:, :] = 0.0
        self.other_inc_in[:, :] = 0.0
        self.netinv_in[:, :] = 0.0
        self.Lambda_in[:, :] = 0.0
        self.qcd_in[:, :] = 0.0
        self.myRothX_in[:, :] = 0.0
        self.rothXfixed_in[:, :] = False
        self.kappa_ijn[:, :, :] = 0.0

        # Single source of truth: adding an HFP column must not require editing this.
        cols = list(hfp_io.timeHorizonItems())
        # The tables built below carry every column, so none is absent any more.
        self.hfpAbsentCols = {iname: [] for iname in self.inames}
        for i, iname in enumerate(self.inames):
            h = self.horizons[i]
            df = pd.DataFrame(0, index=np.arange(0, h + 5), columns=cols)
            df["year"] = np.arange(self.year_n[0] - 5, self.year_n[h - 1] + 1)
            # Flags are checkboxes, not amounts, so they must not start life as ints.
            df[hfp_io.booleanTimeHorizonItems()] = False
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

        self.sigmaBar_n, self.theta_tn, self.Delta_tn = tx.taxParams(
            self.yobs, self.i_d, self.n_d, self.N_n, gamma_n, MAGI_n, self.yOBBBA
        )

        # In a year whose state follows the federal standard deduction, the state deduction is
        # this year's federal amount, age-65 additions included; the OBBBA senior bonus only where
        # the state conforms. Other years keep the state's own deduction and exemptions.
        if any(self._states_n()) and np.any(self.st_fed_sd_n):
            fed_bonus = self.st_fed_sd_n & self.st_senior_bonus_n
            fed_no_bonus = self.st_fed_sd_n & ~self.st_senior_bonus_n
            st_sigma = self._st_sigma_own_n.copy()
            st_sigma[fed_bonus] = self.sigmaBar_n[fed_bonus]
            if np.any(fed_no_bonus):
                # Infinite MAGI phases the senior bonus out entirely.
                no_bonus = np.full(self.N_n, np.inf)
                sigma_nb = tx.taxParams(self.yobs, self.i_d, self.n_d, self.N_n, gamma_n, no_bonus, self.yOBBBA)[0]
                st_sigma[fed_no_bonus] = sigma_nb[fed_no_bonus]
            self.st_sigmaBar_n = st_sigma

        if not self._adjustedParameters:
            self.mylog.vprint("Adjusting parameters for inflation.")
            self.DeltaBar_tn = self.Delta_tn * gamma_n[:-1]
            self.zetaBar_in = self.zeta_in * gamma_n[:-1]
            self.xiBar_n = self.xi_n * gamma_n[:-1]
            self.piBar_in = pension.compute_piBar_in(
                self.pi_in,
                gamma_n[:-1],
                self.pensionIsIndexed,
                self.pensionSurvivorFraction,
                self.n_d,
                self.i_d,
                self.i_s,
                self.horizons,
                self.N_i,
                self.N_n,
            )

            self.spiaBar_in = np.zeros((self.N_i, self.N_n))
            for spia in self._spia_list:
                ind = spia["individual"]
                buy_age = spia["buy_year"] - self.yobs[ind]
                amounts = np.zeros(self.N_i)
                amounts[ind] = spia["monthly_income"]
                ages = np.full(self.N_i, 999.0)
                # Subtract birth-month offset so compute_pension_benefits yields age_with_month
                # = buy_age exactly (integer), giving first_year_fraction = 1.0.
                # SPIA income starts immediately on purchase, not on the annuitant's birthday.
                ages[ind] = float(buy_age) - (self.mobs[ind] - 1) / 12
                surv = np.zeros(self.N_i)
                surv[ind] = spia["survivor_fraction"]
                indexed_flags = [False] * self.N_i
                indexed_flags[ind] = spia["indexed"]
                pi_spia = pension.compute_pension_benefits(
                    amounts,
                    ages,
                    self.yobs,
                    self.mobs,
                    self.horizons,
                    self.N_i,
                    self.N_n,
                    self.year_n[0],
                )
                self.spiaBar_in += pension.compute_piBar_in(
                    pi_spia,
                    gamma_n[:-1],
                    indexed_flags,
                    surv,
                    self.n_d,
                    self.i_d,
                    self.i_s,
                    self.horizons,
                    self.N_i,
                    self.N_n,
                )

            # Part D: include by default; base premium optional (monthly -> annual).
            self._include_medicare_part_d = self.solverOptions.get("includeMedicarePartD", True)
            part_d_base_monthly = self.solverOptions.get("medicarePartDBasePremium")
            self._medicare_part_d_base_annual_per_person = (
                float(part_d_base_monthly) * 12 if part_d_base_monthly is not None else 0.0
            )

            self.nm, self.Lbar_nq, self.Cbar_nq = tx.mediVals(
                self.yobs,
                self.horizons,
                gamma_n,
                self.N_n,
                self.N_irmaa,
                include_part_d=self._include_medicare_part_d,
                part_d_base_annual_per_person=self._medicare_part_d_base_annual_per_person,
            )

            if self.slcsp_annual > 0:
                n_aca_start = max(0, self.aca_start_year - int(self.year_n[0])) if self.aca_start_year > 0 else 0
                self.n_aca, self.Lbar_aca_nr, self.tangents_aca_nrk, self.slcsp_aca_n = tx.acaVals(
                    self.yobs, self.horizons, gamma_n, self.slcsp_annual, self.N_n, n_aca_start=n_aca_start
                )
            else:
                self.n_aca = 0

            self._adjustedParameters = True

        # return None

    def _buildOffsetMap(self, options):
        """
        Utility function to map variables to a block vector.
        Refer to companion document for explanations.
        All binary variables must be lumped at the end of the vector.
        """
        medi = options.get("withMedicare", "loop") == "optimize"
        ss_lp = options.get("withSSTaxability", "loop") == "optimize"
        aca_lp = options.get("withACA", "loop") == "optimize"
        ltcg_lp = options.get("withLTCG", "loop") == "optimize"
        niit_lp = options.get("withNIIT", "loop") == "optimize"
        ordering = options.get("withdrawalOrder", "optimal") == "taxable_first"
        # withSSAges: "fixed"/"none" → no opt; "optimize" → all;
        # individual name or list of names → optimize only those individuals.
        _ssa_opt = options.get("withSSAges", "fixed")
        if isinstance(_ssa_opt, (list, tuple)):
            _ssa_optimize_set = set()
            for name in _ssa_opt:
                try:
                    _ssa_optimize_set.add(self.inames.index(name))
                except ValueError as e:
                    raise ValueError(f"Unknown individual '{name}' for withSSAges:") from e
            self._ssa_optimize_set = _ssa_optimize_set
        elif _ssa_opt == "optimize":
            self._ssa_optimize_set = set(range(self.N_i))
        elif _ssa_opt not in ("fixed", "none"):
            # Single name string (e.g. "Jack").
            try:
                self._ssa_optimize_set = {self.inames.index(_ssa_opt)}
            except ValueError as e:
                raise ValueError(f"Unknown individual '{_ssa_opt}' for withSSAges:") from e
        else:
            self._ssa_optimize_set = set()
        ssa_lp = bool(self._ssa_optimize_set)
        self._aca_lp = aca_lp and self.slcsp_annual > 0 and self.n_aca > 0
        self._ltcg_lp = ltcg_lp
        self._niit_lp = niit_lp
        Nmed = self.N_n - self.nm

        # SS claiming-age optimization: precompute benefit table and initialize SC offset.
        pias = getattr(self, "ssecAmounts", None)
        ssa_lp = ssa_lp and pias is not None and bool(np.any(pias > 0))
        self._ssa_lp = ssa_lp
        self._ssa_N_K = 97  # monthly grid from 62.0 to 70.0 (inclusive)
        if ssa_lp:
            fras = socsec.getFRAs(self.yobs, self.mobs, self.tobs)
            trim_pct = getattr(self, "ssecTrimPct", 0) or 0
            trim_year = getattr(self, "ssecTrimYear", None)
            self._ssa_B_own, self._ssa_ages_k = socsec.build_own_benefit_table(
                pias,
                fras,
                self.yobs,
                self.mobs,
                self.tobs,
                self.horizons,
                self.N_i,
                self.N_n,
                self.gamma_n[:-1],
                trim_pct=trim_pct,
                trim_year=trim_year,
                N_K=self._ssa_N_K,
                thisyear=None,
            )
            # Fold the survivor benefit into the survivor's rows of the benefit table when
            # the deceased's own claiming age is not itself a decision variable. The survivor
            # amount is then a genuine constant, so max(own_k, survivor) is exact for every
            # candidate k and the post-death offset below vanishes. When the deceased's age
            # is also optimized, the survivor amount depends on their chosen k -- unknown at
            # matrix-build time, since the SC loop updates parameters but never rebuilds A --
            # so the survivor benefit is carried in the offset instead and is only exact at
            # convergence.
            survivor = socsec.compute_survivor_stream(
                pias,
                self.ssecAges,
                self.yobs,
                self.mobs,
                self.tobs,
                self.horizons,
                self.N_i,
                self.N_n,
                survivor_claim_age=getattr(self, "ssecSurvivorClaimAge", "immediate"),
                trim_pct=trim_pct,
                trim_year=trim_year,
                thisyear=None,
            )
            self._ssa_fold_survivor = survivor.survivor_idx >= 0 and self._ssaAgeIsFixed(survivor.deceased_idx)
            if self._ssa_fold_survivor:
                self._ssa_B_own = socsec.apply_survivor_to_benefit_table(
                    self._ssa_B_own, survivor, self.gamma_n[:-1]
                )

            # Initialize spousal/survivor offset from initial claiming ages.
            # B_own at initial claiming age k_init; offset = total zetaBar - own benefit.
            # With the fold applied the post-death terms cancel and the offset is exactly the
            # spousal add-on; otherwise it also carries the excess survivor benefit,
            # max(0, survivor - own), which is non-negative by construction.
            self._ssa_spousal_offset = np.zeros((self.N_i, self.N_n))
            for i in range(self.N_i):
                k_init = int(round((float(self.ssecAges[i]) - 62.0) * 12))
                k_init = max(0, min(self._ssa_N_K - 1, k_init))
                self._ssa_spousal_offset[i, :] = self.zetaBar_in[i, :] - self._ssa_B_own[i, k_init, :]

        # Stack all variables in a single block vector with all binary variables at the end.
        vm = VarMap()
        vm.add("b", self.N_i, self.N_j, self.N_n + 1)
        vm.add("d", self.N_i, self.N_n)
        vm.add("e", self.N_n)
        vm.add("f", self.N_t, self.N_n)
        vm.add("g", self.N_n)
        vm.add_if(medi, "h", Nmed, self.N_irmaa)  # IRMAA bracket portions (Medicare optimize)
        vm.add_if(self._aca_lp, "haca", self.n_aca, tx.N_ACA_R)  # ACA MAGI bracket portions (optimize)
        vm.add_if(self._aca_lp, "maca", self.N_n)  # ACA LP cost variable (optimize mode only)
        vm.add("m", self.N_n)
        vm.add("q", self.N_p, self.N_n)  # q_{pn}: LTCG bracket allocations (p=0,1,2)
        vm.add("s", self.N_n)
        vm.add("w", self.N_i, self.N_j, self.N_n)
        vm.add("x", self.N_i, self.N_n)
        # SS taxability LP variables (continuous) must precede the binary block.
        vm.add_if(ss_lp, "plo", self.N_n)  # p^lo_n = max(0, Π_n − 𝒫^lo)
        vm.add_if(ss_lp, "phi", self.N_n)  # p^hi_n = max(0, Π_n − 𝒫^hi)
        vm.add_if(ss_lp, "pmin", self.N_n)  # p^{σ,min}_n = min(𝒫^hi−𝒫^lo, p^lo_n)
        vm.add_if(ss_lp, "tss", self.N_n)  # t^σ_n  = min(0.85·ζ̄_n, 0.5·p^{σ,min}_n + 0.85·p^hi_n)
        vm.add_if(ltcg_lp, "gn", self.N_n)  # G_n: ordinary taxable income (LTCG MILP)
        vm.add_if(niit_lp, "magi", self.N_n)  # MAGI_n LP variable (NIIT MILP)
        vm.add_if(niit_lp, "Jn", self.N_n)  # J_n: NIIT tax LP variable (NIIT MILP)
        vm.add_if(ssa_lp, "ssb", self.N_i, self.N_n)  # SS own-benefit LP var (SS age optimize)
        # State income tax LP variables (continuous, before binary block).
        # No-income-tax states (FL, TX, AK, ...) have all-zero brackets, so st_T_n is
        # identically zero regardless of st_f/st_e/st_re — skip these vars entirely.
        st_lp = any(self._states_n()) and bool(np.any(self.st_theta_tn > 0))
        self._st_lp = st_lp
        st_re_lp = st_lp and np.any(self.st_re_cap_in > 0)
        vm.add_if(st_lp, "st_f", self.N_st, self.N_n)  # state bracket allocations
        vm.add_if(st_lp, "st_e", self.N_n)  # state standard deduction headroom
        vm.add_if(st_re_lp, "st_re", self.N_i, self.N_n)  # retirement income exemption (per person)
        rx_lp = st_lp and self._rx_active
        N_rx = self.st_rx_limit_kn.shape[0] + 1 if rx_lp else 0  # tiers plus "above the last ceiling"
        vm.add_if(rx_lp, "st_rx", self.N_n)  # income-tiered retirement exclusion
        vm.add_if(rx_lp, "rxl", self.N_n, N_rx)  # state total income, split by tier (zero outside it)
        vm.add_if(rx_lp, "rxb", self.N_n, N_rx)  # eligible income, split the same way
        lt_lp = st_lp and self.N_lt > 0 and bool(np.any(self.lt_theta_tn > 0))
        vm.add_if(lt_lp, "lt_f", self.N_lt, self.N_n)  # local bracket allocations
        st_c_lp = st_lp and bool(np.any(self.st_credit_n > 0))
        vm.add_if(st_c_lp, "st_c", self.N_n)  # state personal credit used (<= credit, <= state tax)
        vm.mark_binary_start()
        vm.add_if(medi, "zm", Nmed, self.N_irmaa)  # IRMAA bracket selection binaries
        vm.add_if(ss_lp, "zs", self.N_n, 2)  # z^σ family (2 per year) for SS min() ops
        vm.add_if(self._aca_lp, "za", self.n_aca, tx.N_ACA_R)  # ACA bracket selection binaries
        vm.add_if(ltcg_lp, "zl", 2, self.N_n)  # 2×N_n regime binaries (LTCG MILP)
        vm.add_if(niit_lp, "zj", self.N_n)  # N_n NIIT threshold binaries
        vm.add_if(ssa_lp, "zssa", self.N_i, self._ssa_N_K)  # claiming-month selectors (SS age)
        vm.add_if(ordering, "zo", 2, self.N_n)  # withdrawal-ordering gates (taxable_first)
        vm.add_if(rx_lp, "zx", self.N_n, N_rx)  # exclusion tier selectors
        self.vm = vm

        self.nvars = vm.nvars
        self.nbins = vm.nbins
        self.nconts = vm.nconts
        self.nbals = vm.nbals

        nseries = len(vm._blocks)
        self.mylog.vprint(
            f"Problem has {nseries} distinct series, {self.nvars} decision variables (including {self.nbins} binary)."
        )

    def _buildConstraints(self, objective, options):
        """
        Utility function that builds constraint matrix and vectors.
        Refactored for clarity and maintainability.
        """
        # Ensure parameters are adjusted for inflation and MAGI.
        # OBBBA 65+ senior-deduction phaseout uses the AGI-basis MAGI (taxable SS only).
        self._adjustParameters(self.gamma_n, self.MAGI_n)
        self.other_medical_n = self.other_medical_k * self.gamma_n[:-1]

        self.A = abc.ConstraintMatrix(self.nvars)
        self.B = abc.Bounds(self.nvars, self.nbins)
        self._ceiling_n = self._incomeCeiling()

        self._add_rmd_inequalities()
        self._add_tax_bracket_bounds()
        self._add_standard_exemption_bounds()
        if self._st_lp:
            self._add_state_tax_bounds()
        self._add_defunct_constraints()
        self._add_roth_conversion_constraints(options)
        self._add_safety_net(options)
        self._add_roth_maturation_constraints()
        self._add_withdrawal_limits()
        self._add_hsa_medical_cap()
        self._add_withdrawal_ordering(options)
        self._add_objective_constraints(objective, options)
        self._add_initial_balances()
        self._add_surplus_deposit_linking(options)
        self._add_account_balance_carryover()
        self._add_net_cash_flow(options)
        self._add_income_profile(objective)
        self._add_taxable_income(options)
        if self._st_lp:
            self._add_state_taxable_income()
            self._add_local_taxable_income()
        self._configure_ss_taxability_lp(options)
        self._configure_ss_age_variables()
        self._configure_ltcg_constraints()
        self._configure_Medicare_binary_variables(options)
        self._add_Medicare_costs(options)
        self._configure_ACA_binary_variables(options)
        self._add_ACA_costs(options)
        self._add_magi_lp(options)
        self._configure_NIIT_binary_variables(options)
        self._build_objective_vector(objective, options)

    @_fixedAcrossIterations
    def _add_rmd_inequalities(self):
        """
        Enforce Required Minimum Distributions (RMDs) on tax-deferred accounts (j=1) only.

        RMD rules:
        - Traditional IRA, SEP-IRA, and 401(k) balances (aggregated in j=1) are subject to RMDs
          starting at the age specified by rho_in() (SECURE 1.0/2.0 birth-year cohorts).
        - Roth IRA accounts (j=2) are exempt from RMDs during the original owner's lifetime
          (IRC §408A(c)(5)).
        - Roth 401(k) accounts were subject to RMDs prior to 2024, but SECURE 2.0 Act §325
          eliminated Roth 401(k) RMDs effective for tax years beginning after December 31, 2023.
          Since plans modeled here start in 2024 or later, treating all Roth (j=2) as exempt
          from RMDs is correct for all currently supported scenarios.
        - Inherited IRA / beneficiary RMDs are not modeled.
        """
        for i in range(self.N_i):
            if self.beta_ij[i, 1] > 0:
                for n in range(self.horizons[i]):
                    rowDic = {
                        self.vm["w"].idx(i, 1, n): 1,
                        self.vm["b"].idx(i, 1, n): -self.rho_in[i, n],
                    }
                    # A QCD counts toward the RMD dollar-for-dollar, so it lowers the
                    # floor on the withdrawal that has to be taken as taxable income.
                    self.A.addNewRow(rowDic, -self.qcd_in[i, n], np.inf, tag=("rmd", i, n))

    @_fixedAcrossIterations
    def _add_tax_bracket_bounds(self):
        for t in range(self.N_t):
            for n in range(self.N_n):
                self.B.setRange(self.vm["f"].idx(t, n), 0, self.DeltaBar_tn[t, n])

    def _add_standard_exemption_bounds(self):
        for n in range(self.N_n):
            self.B.setRange(self.vm["e"].idx(n), 0, self.sigmaBar_n[n])

    def _add_state_tax_bounds(self):
        """Set variable bounds for state income tax LP variables.

        Not cached across iterations: st_sigmaBar_n follows MAGI where the state conforms
        to the federal standard deduction with the OBBBA senior bonus.
        """
        vm = self.vm
        for t in range(self.N_st):
            for n in range(self.N_n):
                self.B.setRange(vm["st_f"].idx(t, n), 0, self.st_DeltaBar_tn[t, n])
        for n in range(self.N_n):
            self.B.setRange(vm["st_e"].idx(n), 0, self.st_sigmaBar_n[n])
        if "st_c" in vm:
            for n in range(self.N_n):
                self.B.setRange(vm["st_c"].idx(n), 0, self.st_credit_n[n])
        if "st_re" in vm:
            for i in range(self.N_i):
                for n in range(self.N_n):
                    cap = self.st_re_cap_in[i, n]
                    self.B.setRange(vm["st_re"].idx(i, n), 0, cap if np.isfinite(cap) else 1e9)
        if "st_rx" in vm:
            # Years without an eligible filer, or outside the free set (RXF_n), keep every tier variable
            # at zero and claim nothing; their rows are skipped, so income there is unconstrained.
            N_rx = self.st_rx_limit_kn.shape[0] + 1
            for n in range(self.N_n):
                claimable = bool(self.st_rx_elig_in[:, n].any()) and self.RXF_n[n] >= 0.5
                self.B.setRange(vm["st_rx"].idx(n), 0, self.st_rx_cap_n[n] if claimable else 0)
                fixed = self._rx_fixed is not None and self._rx_fixed[1][n]
                for k in range(N_rx):
                    live = claimable and (k == N_rx - 1 or np.isfinite(self.st_rx_limit_kn[k, n]))
                    if live and fixed:
                        z = float(self._rx_fixed[0][n, k])
                        self.B.setRange(vm["zx"].idx(n, k), z, z)
                    else:
                        self.B.setRange(vm["zx"].idx(n, k), 0, 1 if live else 0)
                    self.B.setRange(vm["rxl"].idx(n, k), 0, np.inf if live else 0)
                    self.B.setRange(vm["rxb"].idx(n, k), 0, np.inf if live else 0)

    def _add_local_taxable_income(self):
        """Local bracket allocations add up to the state taxable income, in years with a local schedule."""
        vm = self.vm
        if "lt_f" not in vm:
            return
        for n in range(self.N_n):
            for t in range(self.N_lt):
                self.B.setRange(vm["lt_f"].idx(t, n), 0, self.lt_DeltaBar_tn[t, n])
            if not np.any(self.lt_DeltaBar_tn[:, n] > 0):
                continue
            row = self.A.newRow()
            for t in range(self.N_lt):
                row.addElem(vm["lt_f"].idx(t, n), 1)
            for t in range(self.N_st):
                row.addElem(vm["st_f"].idx(t, n), -1)
            self.A.addRow(row, 0, 0, tag=("local_taxable_income", n))

    def _add_state_taxable_income(self):
        """Equality constraint: state bracket allocations = state AGI - deductions.

        State AGI = gross ordinary income (G_n + e_n: federal brackets f[t,n] plus the
                    federal standard deduction e_n, so the federal deduction is not
                    also taken against the state base)
                  + capital gains (Q_n via q[p,n], taxed as ordinary by most states)
                  - SS exclusion (when state does not tax SS: subtract the taxable SS that
                    G_n carries -- the tss_n variable under withSSTaxability="optimize",
                    the Psi_n * zetaBar_n parameter otherwise)
                  - pension exemption cap (parameter)

        The LP then subtracts the state standard deduction (st_e) and retirement income
        exemption (st_re), with st_e and st_re bounded to prevent negative state tax.
        The exemption is per person: each individual's st_re is capped by the state amount
        and by that individual's own eligible income (tax-deferred withdrawals, Roth
        conversions when the state allows it, and pensions when the state has no separate
        pension exemption). Unused amounts do not transfer between spouses.
        """
        vm = self.vm
        # Under withSSTaxability="optimize", taxable SS is the tss variable, so exclude it
        # through tss: Psi_n there lags the LP by one self-consistent iteration.
        ss_lp = "tss" in vm
        # SS adjustment: federal G_n contains taxable SS; remove it in years whose state excludes SS.
        # With withSSAges="optimize" the own benefit is the ssb variable (added to the row below),
        # and only the spousal/survivor offset is a parameter.
        ssb_lp = not ss_lp and "ssb" in vm
        if ss_lp:
            ss_excl_n = np.zeros(self.N_n)
        else:
            ss_par_n = np.sum(self._ssa_spousal_offset if ssb_lp else self.zetaBar_in, axis=0)
            ss_excl_n = np.where(self.st_tax_ss_n, 0.0, self.Psi_n * ss_par_n)
        # Pension exemption (parameter): each person's pension up to their own cap.
        pe_adj_n = np.sum(np.minimum(self.piBar_in, self.st_pe_cap_in), axis=0)
        rhs_n = -ss_excl_n - pe_adj_n
        for n in range(self.N_n):
            rhs = float(rhs_n[n])

            row = self.A.newRow()
            for t in range(self.N_st):
                row.addElem(vm["st_f"].idx(t, n), 1)  # state brackets (sum = state taxable income)
            row.addElem(vm["st_e"].idx(n), 1)  # state standard deduction
            if "st_re" in vm:
                for i in range(self.N_i):
                    row.addElem(vm["st_re"].idx(i, n), 1)  # retirement income exemption
            if "st_rx" in vm:
                row.addElem(vm["st_rx"].idx(n), 1)  # income-tiered retirement exclusion
            for t in range(self.N_t):
                row.addElem(vm["f"].idx(t, n), -1)  # subtract G_n (federal taxable ordinary income)
            row.addElem(vm["e"].idx(n), -1)  # add back the federal standard deduction
            for p in range(self.N_p):
                row.addElem(vm["q"].idx(p, n), -1)  # subtract Q_n (capital gains)
            if ss_lp and not self.st_tax_ss_n[n]:
                row.addElem(vm["tss"].idx(n), 1)  # exclude taxable SS (LP variable)
            elif ssb_lp and not self.st_tax_ss_n[n]:
                for i in range(self.N_i):
                    row.addElem(vm["ssb"].idx(i, n), self.Psi_n[n])  # exclude Psi_n * own benefit
            self.A.addRow(row, rhs, rhs, tag=("state_taxable_income", n))

        # A personal credit only offsets tax: the credit used stays below the year's state tax,
        # which includes any benefit recapture (STR_n, a loop parameter).
        if "st_c" in vm:
            for n in range(self.N_n):
                row = self.A.newRow({vm["st_c"].idx(n): 1})
                for t in range(self.N_st):
                    row.addElem(vm["st_f"].idx(t, n), -self.st_theta_tn[t, n])
                self.A.addRow(row, -np.inf, float(self.STR_n[n]), tag=("state_credit_cap", n))

        # Eligible-income cap: each person can't exempt more than their own retirement income.
        if "st_re" in vm:
            # Pensions share the retirement exemption unless that year's state has a separate one.
            for i in range(self.N_i):
                for n in range(self.N_n):
                    row = self.A.newRow({vm["st_re"].idx(i, n): 1})
                    row.addElem(vm["w"].idx(i, 1, n), -1)
                    if self.st_conv_ok_n[n]:
                        row.addElem(vm["x"].idx(i, n), -1)
                    rhs = self.piBar_in[i, n] if self.st_pension_eligible_n[n] else 0
                    self.A.addRow(row, -np.inf, rhs, tag=("state_ret_exempt_cap", i, n))

        if "st_rx" in vm:
            self._add_state_tiered_exclusion()

    def _add_state_tiered_exclusion(self):
        """Income-tiered retirement exclusion (NJ-1040 lines 28a-28c), exact, one binary per tier.

        Total income (line 27) is the state taxable income plus its deductions and exclusions, so the
        rows stay in state terms: L = sum(st_f) + st_e + sum(st_re) + st_rx. The base is what the
        share applies to:

        - tax-deferred withdrawals + Roth conversions + pensions + annuities of the filers old enough
          (line 28a); or
        - L itself, when wages are within the earned-income limit and every filer is old enough: the
          unused cap then covers other income too (line 28b, Worksheet D).

        The tier is a disjunction, written in its disaggregated (convex-hull) form rather than with a
        big-M on L: L and the base are split into per-tier copies rxl[k] and rxb[k], each zero unless
        zx[k] = 1, with lim[k-1] zx[k] <= rxl[k] <= lim[k] zx[k] and rxb[k] <= rxl[k]. Then
        st_rx <= sum_k share[k] rxb[k], and in the first (100%) tier also st_rx <= cap. The last copy
        is income above the last ceiling, where nothing is excluded; only it needs a bound from the
        income ceiling. Inside the ceilings the relaxation is the concave envelope of the staircase,
        which a big-M on L would give up.

        The rows exist only in the free years (RXF_n, see _tiered_exclusion_free); elsewhere the
        exclusion is off. Above the top ceiling the relaxation can still claim nearly the whole cap,
        which left a $2.5M case unproven after ten minutes, so years far above it are left out.
        """
        vm = self.vm
        K = self.st_rx_limit_kn.shape[0]  # tiers with a ceiling; copy K is above the last one

        for n in range(self.N_n):
            elig = np.flatnonzero(self.st_rx_elig_in[:, n])
            cap = float(self.st_rx_cap_n[n])
            if elig.size == 0 or cap <= 0 or self.RXF_n[n] < 0.5:
                continue
            limits = self.st_rx_limit_kn[:, n]
            shares = self.st_rx_share_kn[:, n]
            tiers = [k for k in range(K) if np.isfinite(limits[k])]
            last = float(limits[tiers[-1]])
            top = max(float(self._ceiling_n[n]), 2 * last)
            zx, rxl, rxb = vm["zx"], vm["rxl"], vm["rxb"]

            # Exactly one tier.
            self.A.addNewRow({zx.idx(n, k): 1 for k in tiers + [K]}, 1, 1, tag=("state_exclusion_one", n))

            # L = sum of its copies.
            row = self.A.newRow()
            for t in range(self.N_st):
                row.addElem(vm["st_f"].idx(t, n), 1)
            row.addElem(vm["st_e"].idx(n), 1)
            if "st_re" in vm:
                for i in range(self.N_i):
                    row.addElem(vm["st_re"].idx(i, n), 1)
            row.addElem(vm["st_rx"].idx(n), 1)
            for k in tiers + [K]:
                row.addElem(rxl.idx(n, k), -1)
            self.A.addRow(row, 0, 0, tag=("state_exclusion_income", n))

            # Each copy lies in its tier's range when selected, and is zero otherwise.
            lower = 0.0
            for k in tiers + [K]:
                upper = float(limits[k]) if k < K else top
                self.A.addNewRow({rxl.idx(n, k): 1, zx.idx(n, k): -upper}, -np.inf, 0, tag=("state_excl_hi", n, k))
                if lower > 0:
                    self.A.addNewRow({rxl.idx(n, k): 1, zx.idx(n, k): -lower}, 0, np.inf, tag=("state_excl_lo", n, k))
                lower = upper
                self.A.addNewRow({rxb.idx(n, k): 1, rxl.idx(n, k): -1}, -np.inf, 0, tag=("state_exclusion_base", n, k))

            # The copies of the base add up to no more than the base (line 20a); with the other-income
            # extension the base is L, which rxb[k] <= rxl[k] already says. An inequality, so a year
            # whose eligible income exceeds L (a capital loss) stays feasible: the base is then L.
            if not self.st_rx_other_n[n]:
                row = self.A.newRow({rxb.idx(n, k): 1 for k in tiers + [K]})
                for i in elig:
                    row.addElem(vm["w"].idx(i, 1, n), -1)
                    row.addElem(vm["x"].idx(i, n), -1)
                fixed = float(np.sum(self.piBar_in[elig, n] + self.spiaBar_in[elig, n]))
                self.A.addRow(row, -np.inf, fixed, tag=("state_exclusion_split", n))

            # st_rx <= sum_k share[k] rxb[k]; in a tier excluding 100%, also no more than the cap.
            row = self.A.newRow({vm["st_rx"].idx(n): 1})
            for k in tiers:
                row.addElem(rxb.idx(n, k), -float(shares[k]))
            self.A.addRow(row, -np.inf, 0, tag=("state_exclusion_share", n))
            full = [k for k in tiers if shares[k] >= 1 and cap < limits[k]]
            if full:
                row = self.A.newRow({vm["st_rx"].idx(n): 1})
                for k in tiers:
                    if k in full:
                        row.addElem(zx.idx(n, k), -cap)
                    else:
                        row.addElem(rxb.idx(n, k), -float(shares[k]))
                self.A.addRow(row, -np.inf, 0, tag=("state_exclusion_cap", n))

    @_fixedAcrossIterations
    def _add_defunct_constraints(self):
        if self.N_i == 2:
            for n in range(self.n_d, self.N_n):
                self.B.setRange(self.vm["d"].idx(self.i_d, n), 0, 0)
                self.B.setRange(self.vm["x"].idx(self.i_d, n), 0, 0)
                for j in range(self.N_j):
                    self.B.setRange(self.vm["w"].idx(self.i_d, j, n), 0, 0)

    @_fixedAcrossIterations
    def _add_roth_maturation_constraints(self):
        """
        Enforce the Roth 5-year seasoning rule for conversions and contribution gains.

        IRS rules (simplified here):
        - Roth contribution *principal* can be withdrawn tax- and penalty-free at any time.
        - Roth *earnings* on contributions require both (a) account age ≥ 5 years AND
          (b) age ≥ 59½ (or other exception) to be penalty-free.
        - Each Roth *conversion* carries its own 5-year clock; conversion principal converted
          before age 59½ is subject to the 10% penalty if withdrawn within 5 years of conversion.

        Simplification: This implementation applies a single unified 5-year lookback that retains
        all recent conversions (at compounded value) and the gains-only portion of recent
        contributions as a minimum balance floor. Contribution *principal* is not separately tracked
        and freed — the constraint treats it as part of the 5-year retainer, making it intentionally
        conservative (preventing some valid early withdrawals of contribution principal). This never
        allows a withdrawal that would violate IRS rules; it only restricts some withdrawals that
        would technically be permitted. Exact per-dollar basis tracking is out of scope for an LP.
        """
        # Assume 10% per year for contributions and conversions for past 5 years.
        # Future years will use the assumed returns.
        oldTau1 = 1.10
        Tau1_in = 1 + np.sum(self.alpha_ijkn[:, 2, :, : self.N_n] * self.tau_kn, axis=1)
        for i in range(self.N_i):
            h = self.horizons[i]
            for n in range(h):
                rhs = 0
                # To add compounded gains to cumulative amounts. Always keep cgains >= 1.
                cgains = 1
                row = self.A.newRow()
                row.addElem(self.vm["b"].idx(i, 2, n), 1)
                row.addElem(self.vm["w"].idx(i, 2, n), -1)
                for dn in range(1, 6):
                    nn = n - dn
                    if nn >= 0:  # Past of future is now or in the future: use variables or parameters.
                        # Ignore market downs.
                        cgains *= max(1, Tau1_in[i, nn])
                        row.addElem(self.vm["x"].idx(i, nn), -cgains)
                        # If a contribution, it has only penalty on gains, not on deposited amount.
                        rhs += (cgains - 1) * self.kappa_ijn[i, 2, nn]
                    else:  # Past of future is in the past:
                        cgains *= oldTau1
                        # Past years are stored at the end of contributions and conversions arrays.
                        # Use negative index to access tail of array.
                        # Past years are stored at the end of arrays, accessed via negative indexing
                        rhs += (cgains - 1) * self.kappa_ijn[i, 2, nn] + cgains * self.myRothX_in[i, nn]

                self.A.addRow(row, rhs, np.inf, tag=("roth_maturation", i, n))

    @_fixedAcrossIterations
    def _add_roth_conversion_constraints(self, options):
        """
        Enforce Roth conversion limits and add converted amounts to taxable income.

        Tax treatment: Roth conversions are fully taxable as ordinary income (IRC §408A(d)(3)).

        Pro-rata rule (not modeled): If the tax-deferred account (j=1) contains a mix of
        pre-tax and after-tax (nondeductible) contributions, IRS Form 8606 requires the taxable
        fraction of each conversion to be computed pro-rata across all IRA balances. This tool
        assumes 100% of the j=1 balance is pre-tax (no cost basis from nondeductible contributions),
        so all conversions are treated as fully taxable. Users with significant IRA basis should
        be aware of this limitation and consult a tax professional.
        """
        # Don't exclude anyone by default.
        i_xcluded = -1
        if "noRothConversions" in options and options["noRothConversions"] not in ("none", "None"):
            rhsopt = options["noRothConversions"]
            try:
                i_xcluded = self.inames.index(rhsopt)
            except ValueError as e:
                raise ValueError(f"Unknown individual '{rhsopt}' for noRothConversions:") from e
            for n in range(self.horizons[i_xcluded]):
                self.B.setRange(self.vm["x"].idx(i_xcluded, n), 0, 0)

        if "maxRothConversion" in options:
            rhsopt = u.get_monetary_option(options, "maxRothConversion", 0)

            if rhsopt >= 0:
                for i in range(self.N_i):
                    if i == i_xcluded:
                        continue
                    for n in range(self.horizons[i]):
                        # Apply the cap per individual.
                        self.B.setRange(self.vm["x"].idx(i, n), 0, rhsopt)

        if "startRothConversions" in options:
            rhsopt = int(u.get_numeric_option(options, "startRothConversions", 0))
            thisyear = date.today().year
            yearn = max(rhsopt - thisyear, 0)
            for i in range(self.N_i):
                if i == i_xcluded:
                    continue
                nstart = min(yearn, self.horizons[i])
                for n in range(0, nstart):
                    self.B.setRange(self.vm["x"].idx(i, n), 0, 0)

        if "stopRothConversions" in options:
            rhsopt = int(u.get_numeric_option(options, "stopRothConversions", 0))
            thisyear = date.today().year
            yearn = max(rhsopt - thisyear, 0)
            for i in range(self.N_i):
                if i == i_xcluded:
                    continue
                nstop = min(yearn, self.horizons[i])
                for n in range(nstop, self.horizons[i]):
                    self.B.setRange(self.vm["x"].idx(i, n), 0, 0)

        if "swapRothConverters" in options and i_xcluded == -1:
            rhsopt = int(u.get_numeric_option(options, "swapRothConverters", 0))
            if self.N_i == 2 and rhsopt != 0:
                thisyear = date.today().year
                absrhsopt = abs(rhsopt)
                yearn = max(absrhsopt - thisyear, 0)
                i_x = 0 if rhsopt > 0 else 1
                i_y = (i_x + 1) % 2

                transy = min(yearn, self.horizons[i_y])
                for n in range(0, transy):
                    self.B.setRange(self.vm["x"].idx(i_y, n), 0, 0)

                transx = min(yearn, self.horizons[i_x])
                for n in range(transx, self.horizons[i_x]):
                    self.B.setRange(self.vm["x"].idx(i_x, n), 0, 0)

        # Disallow Roth conversions in last two years alive.
        for i in range(self.N_i):
            if i == i_xcluded:
                continue
            for n in range(max(0, self.horizons[i] - 2), self.horizons[i]):
                self.B.setRange(self.vm["x"].idx(i, n), 0, 0)

        # Years flagged in the "Roth conv fixed" column are held at the amount given in
        # "Roth conv", taking precedence over every policy constraint above: a pinned
        # year bypasses the cap, the start/stop years, swapRothConverters, and the
        # last-two-years zeroing. An amount of 0 is a pin like any other -- it holds that
        # year at no conversion.
        #
        # noRothConversions is the one that refuses instead of yielding, a few lines down.
        # It is a categorical statement about a person, so a pin against it is a
        # contradiction; a swap is only a schedule, so a pin simply overrides it.
        for i in range(self.N_i):
            pinned = np.flatnonzero(self.rothXfixed_in[i, : self.horizons[i]])
            if i == i_xcluded:
                if pinned.size:
                    years = ", ".join(str(int(self.year_n[n])) for n in pinned)
                    verb = "is" if pinned.size == 1 else "are"
                    raise ValueError(
                        f"Contradictory Roth conversion settings for '{self.inames[i]}': "
                        f"noRothConversions excludes them entirely, but {years} "
                        f"{verb} flagged in the 'Roth conv fixed' column. Remove one of the two."
                    )
                continue
            for n in pinned:
                v = self.myRothX_in[i][n]
                self.B.setRange(self.vm["x"].idx(i, n), v, v)

    @_fixedAcrossIterations
    def _add_safety_net(self, options):
        """
        Enforce minimum taxable account balances (safety net) for each individual.
        Amounts are in today's $ and indexed for inflation. Constraints apply
        from year 2 onward through each individual's life horizon (not year 1).
        """
        if "minTaxableBalance" not in options:
            return
        min_bal = u.get_monetary_list_option(options, "minTaxableBalance", self.N_i, min_value=0)
        for i in range(self.N_i):
            min_dollar = min_bal[i]
            if min_dollar <= 0:
                continue
            # From year 2 onward; last year = min(horizons[i], N_n) for survivor,
            # horizons[i]-1 for deceased (last year alive)
            for n in range(1, self.horizons[i]):
                rhs = min_dollar * self.gamma_n[n]
                self.B.setRange(self.vm["b"].idx(i, 0, n), rhs, np.inf)

    @_fixedAcrossIterations
    def _add_withdrawal_limits(self):
        for i in range(self.N_i):
            # Wierdly enough, setting horizons causes a effects on HiGHS and MOSEK
            # for n in range(self.N_n):
            for n in range(self.horizons[i]):
                rowDic = {self.vm["w"].idx(i, 1, n): -1, self.vm["x"].idx(i, n): -1, self.vm["b"].idx(i, 1, n): 1}
                # A QCD is drawn from the same account and consumes its capacity.
                self.A.addNewRow(rowDic, self.qcd_in[i, n], np.inf, tag=("withdrawal_limit", i, 1, n))
                for j in [0, 2, 3]:
                    rowDic = {self.vm["w"].idx(i, j, n): -1, self.vm["b"].idx(i, j, n): 1}
                    self.A.addNewRow(rowDic, 0, np.inf, tag=("withdrawal_limit", i, j, n))

    def _add_hsa_medical_cap(self):
        # HSA qualified medical expense cap: sum_i w[i,3,n] - m_n <= M_n[n] + other_medical_n[n]
        # m_n is the Medicare LP variable; fixed to loop-computed value in SC-loop mode.
        # Pre-Medicare years: M_n = m_n = 0, so cap = other_medical_n[n] only.
        # Guard: skip entirely when no HSA exists — redundant constraints change LP duals
        # even when trivially satisfied, interfering with the LTCG SC-loop.
        has_hsa = np.any(self.beta_ij[:, 3] > 0) or np.any(self.kappa_ijn[:, 3, :] > 0)
        if has_hsa:
            for n in range(self.N_n):
                cap = self.M_n[n] + self.other_medical_n[n]
                rowDic = {self.vm["w"].idx(i, 3, n): 1 for i in range(self.N_i)}
                rowDic[self.vm["m"].idx(n)] = -1
                self.A.addNewRow(rowDic, -np.inf, cap, tag=("hsa_medical_cap", n))

    def _portfolioCeiling(self):
        """Upper bound on total savings in each year, for big-M constraint families.

        Nothing is withdrawn, held or deposited that exceeds the whole portfolio, and the
        portfolio cannot outgrow starting balances plus contributions compounded at the
        best return any account sees. Returns an array of length N_n + 1, generous by a
        factor of two so that it stays a bound and never a constraint.
        """
        growth = 1.0 + np.max(
            np.einsum("ijkn,kn->ijn", self.alpha_ijkn[:, :, :, : self.N_n], self.tau_kn[:, : self.N_n]),
            axis=(0, 1),
        )
        growth = np.maximum(growth, 1.0)
        ceiling = np.empty(self.N_n + 1)
        wealth = float(np.sum(self.beta_ij)) + float(np.sum(self.kappa_ijn))
        for n in range(self.N_n):
            ceiling[n] = wealth
            wealth *= growth[n]
        ceiling[self.N_n] = wealth
        return 2.0 * np.maximum(ceiling, 1.0)

    @_fixedAcrossIterations
    def _add_withdrawal_ordering(self, options):
        """
        Enforce the conventional withdrawal order — taxable first, then tax-deferred,
        then Roth — when options["withdrawalOrder"] == "taxable_first". Models the
        naive strategy a hand-managed plan would follow (used as a baseline policy by
        compare_to_baseline); the default "optimal" leaves withdrawal order free.

        Household-level gates, one pair of binaries per year:
          zo[0,n] = 1  iff household taxable is exhausted at end of year n
                       (tax-deferred withdrawals beyond the RMD become allowed)
          zo[1,n] = 1  iff household tax-deferred is also exhausted at end of year n
                       (Roth withdrawals become allowed)
        RMDs remain forced by the RMD floor rows regardless of the gates, so when
        zo[0,n] = 0 the tax-deferred withdrawal is pinned to exactly the RMD.
        HSA withdrawals (qualified medical) are not gated. Surplus deposits land in
        taxable at year end, so a year cannot both deposit a surplus and claim the
        taxable-exhausted gate — closing the drain-and-redeposit loophole.
        """
        if "zo" not in self.vm:
            return
        # Every quantity these gates switch off is a balance or a withdrawal, so the
        # portfolio ceiling bounds them all. Sizing M to what the row actually gates keeps
        # the gates honest: a solver's integer tolerance buys slack in proportion to M, so
        # an oversized constant is hundreds of dollars of balance slipping past a closed gate.
        ceiling_n = self._portfolioCeiling()
        for n in range(self.N_n):
            Mn = ceiling_n[n]
            z1 = self.vm["zo"].idx(0, n)
            z2 = self.vm["zo"].idx(1, n)
            for i in range(self.N_i):
                if n >= self.horizons[i]:
                    continue
                # Tax-deferred beyond the RMD only once taxable is exhausted:
                # w[i,1,n] - rho*b[i,1,n] - M*z1 <= 0  (mirrors the RMD floor row).
                # Deliberately NOT credited with the QCD the way the RMD row is. The
                # true cash floor is max(rho*b - qcd, 0), and rho*b is an expression, so
                # subtracting qcd here would demand w <= rho*b - qcd — infeasible for any
                # household whose QCD exceeds its gross RMD while taxable is not yet
                # exhausted. This keeps the gate loose by at most the QCD amount, which
                # only ever permits (never forces) an extra withdrawal under a policy
                # that exists to model a naive baseline.
                self.A.addNewRow(
                    {
                        self.vm["w"].idx(i, 1, n): 1,
                        self.vm["b"].idx(i, 1, n): -self.rho_in[i, n],
                        z1: -Mn,
                    },
                    -np.inf,
                    0,
                    tag=("wdorder_txdef_gate", i, n),
                )
                # Roth withdrawals only once tax-deferred is also exhausted.
                self.A.addNewRow({self.vm["w"].idx(i, 2, n): 1, z2: -Mn}, -np.inf, 0, tag=("wdorder_roth_gate", i, n))
            # Gate activation: sum_i b[i,j,n+1] + M*z <= M  (z=1 forces end balance ~ 0).
            rowDic = {self.vm["b"].idx(i, 0, n + 1): 1 for i in range(self.N_i)}
            rowDic[z1] = Mn
            self.A.addNewRow(rowDic, -np.inf, Mn, tag=("wdorder_taxable_exhausted", n))
            rowDic = {self.vm["b"].idx(i, 1, n + 1): 1 for i in range(self.N_i)}
            rowDic[z2] = Mn
            self.A.addNewRow(rowDic, -np.inf, Mn, tag=("wdorder_txdef_exhausted", n))
            # Full ordering: the Roth gate implies the tax-deferred gate.
            self.A.addNewRow({z2: 1, z1: -1}, -np.inf, 0, tag=("wdorder_gate_monotone", n))

    def _incomeCeiling(self):
        """Per-year upper bound on income, for the bracket-selector constraints.

        Every big-M in the model gates one of: provisional income, AGI-basis MAGI, ordinary taxable
        income, or a share of one of them. All are bounded by what the household could possibly
        receive in a year -- its whole portfolio, plus that year's fixed income -- so the bound is
        the portfolio ceiling plus the known flows. _portfolioCeiling already carries a factor of
        two, so this stays a bound and never a constraint.

        A single flat constant cannot do this job: it is thousands of times too large where it gates
        the taxable Social Security tiers (at most 0.85 of the benefit) and can be too small where it
        gates MAGI in a late, inflated year. Too large slows branch-and-bound to a crawl; too small
        removes feasible plans silently.
        """
        Nn = self.N_n
        ss_in = self.zetaBar_in
        if "ssb" in self.vm:
            # The MAGI rows carry the own benefit of whichever claiming age the MILP picks, which can
            # exceed the previous iterate's: bound it by the largest candidate.
            ss_in = np.maximum(ss_in, self._ssa_spousal_offset + np.max(self._ssa_B_own[:, :, :Nn], axis=1))
        fixed = (
            np.sum(self.omega_in + self.other_inc_in + self.netinv_in, axis=0)
            + np.sum(self.piBar_in + self.spiaBar_in + ss_in + self.Lambda_in, axis=0)
            + self.fixed_assets_ordinary_income_n
            + np.maximum(self.fixed_assets_capital_gains_n, 0.0)
            + self.fixed_assets_tax_free_n
        )
        return self._portfolioCeiling()[:Nn] + fixed

    @_fixedAcrossIterations
    def _add_objective_constraints(self, objective, options):
        if objective == "maxSpending":
            if "bequest" in options:
                bequest = u.get_monetary_option(options, "bequest", 1) * self.gamma_n[-1]
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
                row.addElem(self.vm["b"].idx(i, 0, self.N_n), 1)
                row.addElem(self.vm["b"].idx(i, 1, self.N_n), 1 - self.nu)
                row.addElem(self.vm["b"].idx(i, 2, self.N_n), 1)
                row.addElem(self.vm["b"].idx(i, 3, self.N_n), 1 - self.nu)  # HSA: heirs pay ordinary income tax
            self.A.addRow(row, total_bequest_value, np.inf, tag=("bequest_floor",))
        elif objective == "maxBequest":
            spending = u.get_monetary_option(options, "netSpending", 1)
            self.B.setRange(self.vm["g"].idx(0), spending, spending)

    @_fixedAcrossIterations
    def _add_initial_balances(self):
        # Back project balances to the beginning of the year.
        yearSpent = 1 - self.yearFracLeft

        for i in range(self.N_i):
            for j in range(self.N_j):
                backTau = 1 + yearSpent * np.sum(self.tau_kn[:, 0] * self.alpha_ijkn[i, j, :, 0])
                rhs = self.beta_ij[i, j] / backTau
                self.B.setRange(self.vm["b"].idx(i, j, 0), rhs, rhs)

    @_fixedAcrossIterations
    def _add_surplus_deposit_linking(self, options):
        for i in range(self.N_i):
            fac1 = u.krond(i, 0) * (1 - self.eta) + u.krond(i, 1) * self.eta
            for n in range(self.n_d):
                rowDic = {self.vm["d"].idx(i, n): 1, self.vm["s"].idx(n): -fac1}
                self.A.addNewRow(rowDic, 0, 0, tag=("surplus_deposit", i, n))
            fac2 = u.krond(self.i_s, i)
            for n in range(self.n_d, self.N_n):
                rowDic = {self.vm["d"].idx(i, n): 1, self.vm["s"].idx(n): -fac2}
                self.A.addNewRow(rowDic, 0, 0, tag=("surplus_deposit", i, n))

        # Prevent surplus on two last year as they have little tax and/or growth consequence.
        disallow = options.get("noLateSurplus", False)
        if disallow:
            self.B.setRange(self.vm["s"].idx(self.N_n - 2), 0, 0)
            self.B.setRange(self.vm["s"].idx(self.N_n - 1), 0, 0)

    @_fixedAcrossIterations
    def _add_account_balance_carryover(self):
        tau_ijn = np.sum(self.alpha_ijkn[:, :, :, : self.N_n] * self.tau_kn, axis=2)

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
                    # SPIA premium: non-taxable IRA rollover — reduces tax-deferred balance directly.
                    if j == 1:
                        rhs -= self.spia_premiums_in[i, n]
                        # QCD leaves the tax-deferred account for charity.
                        rhs -= fac1 * Tau1_ijn[i, 1, n] * self.qcd_in[i, n]

                    row = self.A.newRow()
                    row.addElem(self.vm["b"].idx(i, j, n + 1), 1)
                    row.addElem(self.vm["b"].idx(i, j, n), -fac1 * Tau1_ijn[i, j, n])
                    row.addElem(self.vm["w"].idx(i, j, n), fac1 * Tau1_ijn[i, j, n])
                    row.addElem(self.vm["d"].idx(i, n), -fac1 * u.krond(j, 0) * Tau1_ijn[i, 0, n])
                    row.addElem(
                        self.vm["x"].idx(i, n),
                        -fac1 * (self.xnet * u.krond(j, 2) - u.krond(j, 1)) * Tau1_ijn[i, j, n],
                    )

                    if self.N_i == 2 and self.n_d < self.N_n and i == self.i_s and n == self.n_d - 1:
                        fac2 = self.phi_j[j]
                        rhs += fac2 * self.kappa_ijn[self.i_d, j, n] * Tauh_ijn[self.i_d, j, n]
                        if j == 1:
                            # fac1 == 0 zeroed the deceased's own row, so their final-year
                            # QCD has to be accounted for here, in the inherited balance.
                            rhs -= fac2 * Tau1_ijn[self.i_d, 1, n] * self.qcd_in[self.i_d, n]
                        row.addElem(self.vm["b"].idx(self.i_d, j, n), -fac2 * Tau1_ijn[self.i_d, j, n])
                        row.addElem(self.vm["w"].idx(self.i_d, j, n), fac2 * Tau1_ijn[self.i_d, j, n])
                        row.addElem(self.vm["d"].idx(self.i_d, n), -fac2 * u.krond(j, 0) * Tau1_ijn[self.i_d, 0, n])
                        row.addElem(
                            self.vm["x"].idx(self.i_d, n),
                            -fac2 * (self.xnet * u.krond(j, 2) - u.krond(j, 1)) * Tau1_ijn[self.i_d, j, n],
                        )
                    self.A.addRow(row, rhs, rhs, tag=("account_carryover", i, j, n))

    def _add_net_cash_flow(self, options=None):
        tau_0prev = np.roll(self.tau_kn[0, :], 1)
        tau_0prev[tau_0prev < 0] = 0
        for n in range(self.N_n):
            rhs = -self.M_n[n] - self.ACA_n[n]
            if not getattr(self, "_niit_lp", False):
                rhs -= self.J_n[n]
            # State recapture is part of the state tax, so a local surcharge applies to it too.
            rhs -= self.STR_n[n] * (1 + self.lt_surcharge_n[n])
            # Add fixed assets proceeds (positive cash flow)
            rhs += (
                self.fixed_assets_tax_free_n[n]
                + self.fixed_assets_ordinary_income_n[n]
                + self.fixed_assets_capital_gains_n[n]
            )
            # Subtract debt payments (negative cash flow)
            rhs -= self.debt_payments_n[n]
            row = self.A.newRow({self.vm["g"].idx(n): 1})
            row.addElem(self.vm["s"].idx(n), 1)
            row.addElem(self.vm["m"].idx(n), 1)
            if "maca" in self.vm:
                row.addElem(self.vm["maca"].idx(n), 1)
            for i in range(self.N_i):
                if "ssb" in self.vm:
                    # SS own-benefit is an LP variable; spousal/survivor is a parameter offset.
                    ss_income = self._ssa_spousal_offset[i, n]
                    row.addElem(self.vm["ssb"].idx(i, n), -1)
                else:
                    ss_income = self.zetaBar_in[i, n]
                rhs += (
                    self.omega_in[i, n]
                    + self.other_inc_in[i, n]
                    + self.netinv_in[i, n]
                    + ss_income
                    + self.piBar_in[i, n]
                    + self.spiaBar_in[i, n]
                    + self.Lambda_in[i, n]
                )
                row.addElem(self.vm["w"].idx(i, 0, n), -1)
                penalty = 0.1 if n < self.n595[i] else 0
                row.addElem(self.vm["w"].idx(i, 1, n), -1 + penalty)
                # maturation constraints govern; no 10% penalty
                row.addElem(self.vm["w"].idx(i, 2, n), -1)
                # HSA: qualified medical withdrawals are tax-free (simplified model)
                row.addElem(self.vm["w"].idx(i, 3, n), -1)

            for t in range(self.N_t):
                row.addElem(self.vm["f"].idx(t, n), self.theta_tn[t, n])

            # LTCG tax from bracket variables q[1,n] and q[2,n] directly.
            row.addElem(self.vm["q"].idx(1, n), 0.15)
            row.addElem(self.vm["q"].idx(2, n), 0.20)

            # State income tax from state bracket variables.
            if "st_f" in self.vm:
                for t in range(self.N_st):
                    # A local surcharge is a share of the state's own tax.
                    row.addElem(self.vm["st_f"].idx(t, n), self.st_theta_tn[t, n] * (1 + self.lt_surcharge_n[n]))
                if "st_c" in self.vm:
                    # A personal credit reduces the state tax paid, and with it any surcharge on that tax.
                    row.addElem(self.vm["st_c"].idx(n), -(1 + self.lt_surcharge_n[n]))
            if "lt_f" in self.vm:
                for t in range(self.N_lt):
                    row.addElem(self.vm["lt_f"].idx(t, n), self.lt_theta_tn[t, n])

            # NIIT: when optimize mode, use LP variable Jn; otherwise already in rhs.
            if getattr(self, "_niit_lp", False):
                row.addElem(self.vm["Jn"].idx(n), 1)

            self.A.addRow(row, rhs, rhs, tag=("cash_flow", n))

    @_fixedAcrossIterations
    def _add_income_profile(self, objective):
        spLo = 1 - self.lambdha
        spHi = 1 + self.lambdha
        for n in range(1, self.N_n):
            rowDic = {self.vm["g"].idx(0): spLo * self.xiBar_n[n], self.vm["g"].idx(n): -self.xiBar_n[0]}
            self.A.addNewRow(rowDic, -np.inf, 0, tag=("profile_lo", n))
            rowDic = {self.vm["g"].idx(0): spHi * self.xiBar_n[n], self.vm["g"].idx(n): -self.xiBar_n[0]}
            self.A.addNewRow(rowDic, 0, np.inf, tag=("profile_hi", n))

    def _add_taxable_income(self, options=None):
        ss_lp = options is not None and options.get("withSSTaxability", "loop") == "optimize"
        # Only positive returns are taxable (interest/dividends); losses don't reduce income.
        fak_in = np.sum(np.maximum(0, self.tau_kn[1:, :]) * self.alpha_ijkn[:, 0, 1:, : self.N_n], axis=1)
        for n in range(self.N_n):
            # Add fixed assets ordinary income
            rhs = self.fixed_assets_ordinary_income_n[n]
            row = self.A.newRow()
            row.addElem(self.vm["e"].idx(n), 1)
            for i in range(self.N_i):
                if ss_lp:
                    # Taxable SS is an LP variable (tss_n); omit the Psi_n*zetaBar parameter.
                    rhs += (
                        self.omega_in[i, n]
                        + self.other_inc_in[i, n]
                        + self.netinv_in[i, n]
                        + self.piBar_in[i, n]
                        + self.spiaBar_in[i, n]
                    )
                else:
                    ss_const, ssb_idx = self._ss_benefit_terms(i, n)
                    rhs += (
                        self.omega_in[i, n]
                        + self.other_inc_in[i, n]
                        + self.netinv_in[i, n]
                        + self.Psi_n[n] * ss_const
                        + self.piBar_in[i, n]
                        + self.spiaBar_in[i, n]
                    )
                    if ssb_idx is not None:
                        # Taxable SS follows the claiming age the MILP picks (Psi_n lags).
                        row.addElem(ssb_idx, -self.Psi_n[n])
                row.addElem(self.vm["w"].idx(i, 1, n), -1)
                row.addElem(self.vm["x"].idx(i, n), -1)
                fak = fak_in[i, n]
                rhs += 0.5 * fak * self.kappa_ijn[i, 0, n]
                row.addElem(self.vm["b"].idx(i, 0, n), -fak)
                row.addElem(self.vm["w"].idx(i, 0, n), fak)
                row.addElem(self.vm["d"].idx(i, n), -fak)
            for t in range(self.N_t):
                row.addElem(self.vm["f"].idx(t, n), 1)
            if ss_lp:
                # t^σ_n = taxable SS LP variable replaces Psi_n*zetaBar_n in the constraint:
                # e_n - t^σ_n + sum_t(f_tn) = non_SS_ordinary_income
                row.addElem(self.vm["tss"].idx(n), -1)
            self.A.addRow(row, rhs, rhs, tag=("taxable_income", n))

    def _configure_ss_taxability_lp(self, options):
        """
        Configure SS taxability using the MIP approach (alternative to the SC loop).

        Introduces per-year LP variables p^lo_n, p^hi_n, q_n, t^σ_n and binary variables
        z^σ_{0n}, z^σ_{1n} to compute taxable Social Security exactly within the LP,
        eliminating the need to update Psi_n in the self-consistent loop for SS.

        Filing status is per-year: for a couple, status switches from MFJ to Single
        in year n_d when the first spouse dies. The 50% tier uses q_n ≤ min(Δ𝒫_n, ζ̄_n, p^lo_n),
        matching the IRS formula exactly.

        Provisional income Π_n = (non-SS ordinary income) + Q_n + 0.5·ζ̄_n is built using
        the same coefficient structure as the Medicare MAGI constraint, adjusted for the
        current year n and using 0.5·ζ̄_n instead of the full ζ̄_n.
        """
        if options.get("withSSTaxability", "loop") != "optimize":
            return

        for n in range(self.N_n):
            zetaBar_n = np.sum(self.zetaBar_in[:, n])

            # No SS income this year: fix variables to 0 and skip all 8 constraints.
            # tss_n MUST be fixed (it appears in taxable income with -1 coefficient).
            # z0_n, z1_n should be fixed to remove them from MIP branching.
            if zetaBar_n == 0:
                self.B.setRange(self.vm["tss"].idx(n), 0, 0)
                self.B.setRange(self.vm["zs"].idx(n, 0), 0, 0)
                self.B.setRange(self.vm["zs"].idx(n, 1), 0, 0)
                continue

            # Per-year filing status: for couple, switch to Single at n_d.
            status_n = 0 if (self.N_i == 2 and n >= self.n_d) else self.N_i - 1
            ss_lo_n = tx.ssTaxabilityLo[status_n]
            ss_hi_n = tx.ssTaxabilityHi[status_n]
            delta_p_n = ss_hi_n - ss_lo_n

            # === Build Π_n LP coefficients ===
            # Π_n = B_n + Q_n + 0.5·ζ̄_n, where B_n is non-SS ordinary income before the
            # standard exemption. The LP income terms below mirror the ACA MAGI constraint
            # exactly — same year n, same coefficients — and carry 0.5·ζ̄_n instead of the
            # full ζ̄_n. Those terms already are B_n + Q_n: neither e_n nor t^σ_n belongs
            # here. Adding e_n would count the exemption a second time, and subtracting
            # t^σ_n would remove taxable SS that the terms never included.

            rhs_pi = (
                self.fixed_assets_ordinary_income_n[n] + self.fixed_assets_capital_gains_n[n] + 0.5 * zetaBar_n
            )  # 0.5·SS for provisional income (not full SS)

            pi_row = {}

            for i in range(self.N_i):
                # Combined dividend + interest yield for taxable account (equity + bonds/notes/cash).
                afac = self.mu * self.alpha_ijkn[i, 0, 0, n] + np.sum(
                    self.alpha_ijkn[i, 0, 1:, n] * np.maximum(0, self.tau_kn[1:, n])
                )
                # Capital gains on taxable account withdrawal (uses tracked basis if available).
                bfac = self.alpha_ijkn[i, 0, 0, n] * self._effective_cap_gain_coef(i, n)

                w1_idx = self.vm["w"].idx(i, 1, n)
                x_idx = self.vm["x"].idx(i, n)
                b_idx = self.vm["b"].idx(i, 0, n)
                d_idx = self.vm["d"].idx(i, n)
                w0_idx = self.vm["w"].idx(i, 0, n)

                pi_row[w1_idx] = pi_row.get(w1_idx, 0) - 1  # IRA withdrawals (income)
                pi_row[x_idx] = pi_row.get(x_idx, 0) - 1  # Roth conversions (income)
                pi_row[b_idx] = pi_row.get(b_idx, 0) - afac  # beginning balance × yield
                pi_row[d_idx] = pi_row.get(d_idx, 0) - afac  # contributions × yield
                pi_row[w0_idx] = pi_row.get(w0_idx, 0) + (afac - bfac)  # withdrawals (net)

                rhs_pi += (
                    self.omega_in[i, n]
                    + self.other_inc_in[i, n]
                    + self.netinv_in[i, n]
                    + self.piBar_in[i, n]
                    + self.spiaBar_in[i, n]
                    + 0.5 * self.kappa_ijn[i, 0, n] * afac
                )  # half-period contribution yield

            # Variable index shorthands.
            plo_idx = self.vm["plo"].idx(n)
            phi_idx = self.vm["phi"].idx(n)
            pmin_idx = self.vm["pmin"].idx(n)
            tss_idx = self.vm["tss"].idx(n)
            z0_idx = self.vm["zs"].idx(n, 0)
            z1_idx = self.vm["zs"].idx(n, 1)
            # === p^lo_n = max(0, Π_n − 𝒫^lo) ===
            # Lower bound ≥ 0 from default variable bounds; explicit inequality enforces the max.
            # Row: p^lo_n + pi_row_coeffs ≥ rhs_pi − ss_lo_n
            row_plo = dict(pi_row)
            row_plo[plo_idx] = row_plo.get(plo_idx, 0) + 1
            self.A.addNewRow(row_plo, rhs_pi - ss_lo_n, np.inf, tag=("ss_tax_plo", n))

            # === p^hi_n = max(0, Π_n − 𝒫^hi) ===
            row_phi = dict(pi_row)
            row_phi[phi_idx] = row_phi.get(phi_idx, 0) + 1
            self.A.addNewRow(row_phi, rhs_pi - ss_hi_n, np.inf, tag=("ss_tax_phi", n))

            # === p^{σ,min}_n = min(Δ𝒫_n, ζ̄_n, p^lo_n) via binary z^σ_{0n} ===
            # Upper bounds: p^{σ,min}_n ≤ min(Δ𝒫_n, ζ̄_n) (setRange) and ≤ p^lo_n (constraint).
            # When ζ̄_n < Δ𝒫_n, the effective upper bound on pmin is ζ̄_n; using Δ𝒫_n in the big-M
            # lower bound of constraint (3b) would force pmin ≥ Δ𝒫_n > ζ̄_n, causing infeasibility.
            p_ub = min(delta_p_n, zetaBar_n)
            # Each row is relaxed by exactly what it gates: the 50% tier's cap, the excess of
            # provisional income over a threshold, or 0.85 of the benefit. A flat constant here was
            # thousands of times larger than any of them.
            ceiling_n = self._ceiling_n[n]
            m_pmin_cap = p_ub
            m_pmin_plo = max(0.0, ceiling_n - ss_lo_n)
            m_tss_cap = 0.85 * zetaBar_n
            m_tss_formula = 0.5 * p_ub + 0.85 * max(0.0, ceiling_n - ss_hi_n)

            self.A.addNewRow({pmin_idx: 1, plo_idx: -1}, -np.inf, 0, tag=("ss_tax_pmin_ub", n))  # pmin ≤ p^lo
            # p^{σ,min}_n ≥ min(Δ𝒫_n, ζ̄_n) − M·(1 − z0)  →  pmin − M·z0 ≥ p_ub − M
            self.A.addNewRow(
                {pmin_idx: 1, z0_idx: -m_pmin_cap}, p_ub - m_pmin_cap, np.inf, tag=("ss_tax_pmin_lb_cap", n)
            )
            # p^{σ,min}_n ≥ p^lo_n − M·z0  →  pmin − p^lo + M·z0 ≥ 0
            self.A.addNewRow(
                {pmin_idx: 1, plo_idx: -1, z0_idx: m_pmin_plo}, 0, np.inf, tag=("ss_tax_pmin_lb_plo", n)
            )
            self.B.setRange(pmin_idx, 0, p_ub)  # pmin ≤ min(Δ𝒫_n, ζ̄_n)

            # === t^σ_n = min(0.85·ζ̄_n, 0.5·p^{σ,min}_n + 0.85·p^hi_n) via binary z^σ_{1n} ===
            # Upper bound t^σ_n ≤ 0.5·p^{σ,min}_n + 0.85·p^hi_n.
            self.A.addNewRow({tss_idx: 1, pmin_idx: -0.5, phi_idx: -0.85}, -np.inf, 0, tag=("ss_tax_tss_ub", n))
            # t^σ_n ≥ 0.85·ζ̄_n − M·(1 − z1)  →  t^σ_n − M·z1 ≥ 0.85·ζ̄_n − M
            self.A.addNewRow(
                {tss_idx: 1, z1_idx: -m_tss_cap}, 0.85 * zetaBar_n - m_tss_cap, np.inf, tag=("ss_tax_tss_lb_cap", n)
            )
            # t^σ_n ≥ 0.5·p^{σ,min}_n + 0.85·p^hi_n − M·z1  →  tss − 0.5·pmin − 0.85·phi + M·z1 ≥ 0
            self.A.addNewRow(
                {tss_idx: 1, pmin_idx: -0.5, phi_idx: -0.85, z1_idx: m_tss_formula},
                0,
                np.inf,
                tag=("ss_tax_tss_lb_formula", n),
            )
            self.B.setRange(tss_idx, 0, 0.85 * zetaBar_n)  # t^σ ≤ 0.85·ζ̄

    def _ss_benefit_terms(self, i, n):
        """Person i's SS income in year n as (constant part, ssb column index or None).

        With withSSAges="optimize" the own benefit is the LP variable ssb[i, n] and only the
        spousal/survivor offset is a parameter, so every row that charges tax or premiums on SS
        sees the benefit of the claiming age the MILP picks. Otherwise all of it is zetaBar.
        """
        if "ssb" in self.vm:
            return self._ssa_spousal_offset[i, n], self.vm["ssb"].idx(i, n)
        return self.zetaBar_in[i, n], None

    def _ssaAgeIsFixed(self, i):
        """
        Return True if individual i's SS claiming age is not a free decision variable.

        An age is fixed when the individual has no PIA, has already claimed (their current
        age is at or past the stored claiming age), or was not selected by withSSAges.
        """
        pia_i = int(self.ssecAmounts[i]) if hasattr(self, "ssecAmounts") else 0
        current_age = date.today().year - self.yobs[i] - (self.mobs[i] - 1) / 12
        already_claimed = current_age >= float(self.ssecAges[i])
        not_selected = i not in getattr(self, "_ssa_optimize_set", set(range(self.N_i)))
        return pia_i == 0 or already_claimed or not_selected

    @_fixedAcrossIterations
    def _configure_ss_age_variables(self):
        """
        Add SS claiming-age optimization constraints (withSSAges='optimize' mode).

        Two constraint groups per individual i:
          a) AMO (exactly-one claiming month): sum_k zssa[i,k] = 1
          b) Benefit definition: ssb[i,n] = sum_k B_own[i,k,n] * zssa[i,k]  for each n

        For already-claimed individuals (current age >= stored claiming age), all zssa[i,k]
        are fixed to 0/1 via bounds so the optimizer leaves them at the recorded age.
        For individuals with zero PIA, zssa[i,0] is fixed to 1 (irrelevant, B_own=0).

        Notes
        -----
        ssb[i,n] = own SS benefit only; spousal/survivor offsets are added as parameters
        (_ssa_spousal_offset[i,n]) in the cash-flow constraint and updated each SC iteration.
        """
        if not self._ssa_lp:
            return

        vm = self.vm
        N_K = self._ssa_N_K
        B_own = self._ssa_B_own

        for i in range(self.N_i):
            pia_i = int(self.ssecAmounts[i]) if hasattr(self, "ssecAmounts") else 0

            if self._ssaAgeIsFixed(i):
                # Fix to the known/current claiming age (or age 62 if no SS).
                if pia_i == 0:
                    k_fixed = 0  # Arbitrary; B_own is all-zero anyway.
                else:
                    k_fixed = int(round((float(self.ssecAges[i]) - 62.0) * 12))
                    k_fixed = max(0, min(N_K - 1, k_fixed))
                for k in range(N_K):
                    lb = 1 if k == k_fixed else 0
                    self.B.setRange(vm["zssa"].idx(i, k), lb, lb)
            else:
                # Free individual: fix ineligible claiming ages to 0.
                bornOnFirstDays = self.tobs[i] <= 2
                eligible = 62.0 if bornOnFirstDays else 62.0 + 1.0 / 12
                for k in range(N_K):
                    if self._ssa_ages_k[k] < eligible:
                        self.B.setRange(vm["zssa"].idx(i, k), 0, 0)

            # a) AMO: exactly one claiming month per individual.
            amo_row = {vm["zssa"].idx(i, k): 1 for k in range(N_K)}
            self.A.addNewRow(amo_row, 1, 1, tag=("ss_age_amo", i))

            # b) Benefit definition: ssb[i,n] = sum_k B_own[i,k,n] * zssa[i,k]
            for n in range(self.N_n):
                ssb_idx = vm["ssb"].idx(i, n)
                row = {ssb_idx: 1}
                for k in range(N_K):
                    b_val = float(B_own[i, k, n])
                    if b_val != 0.0:
                        row[vm["zssa"].idx(i, k)] = row.get(vm["zssa"].idx(i, k), 0) - b_val
                # equality: ssb[i,n] - sum_k B_own * zssa = 0
                self.A.addNewRow(row, 0, 0, tag=("ss_age_benefit", i, n))

    def _configure_ltcg_constraints(self):
        """
        Configure LTCG tax using LP bracket-allocation variables.

        When self._ltcg_lp is False (default, 'loop' mode):
          Pure LP, no binaries. Uses SC-loop G_n parameter for bracket room.

        When self._ltcg_lp is True ('optimize' mode):
          MILP big-M formulation with G_n as a continuous LP variable and zl binaries
          to select which LTCG bracket applies. Globally optimal within gap.

        Introduces per-year variables q_{pn} (p=0,1,2) partitioning total LTCG across the
        0%, 15%, and 20% capital-gains brackets. Because the LTCG cost function is convex
        (0 < 0.15 < 0.20), the LP naturally minimises tax without binary variables.

        T15_n and T20_n are thresholds on TOTAL taxable income (ordinary + LTCG, after the
        standard deduction). Capital gains are "stacked" on top of ordinary taxable income G_n.
        The bracket constraints are:

        LP mode constraints per year n:
          (1) q[0,n] ≤ max(0, T15_n − G_n)               (cap on 0% allocation)
          (2) q[0,n] + q[1,n] ≤ max(0, T20_n − G_n)      (cap on 0%+15% allocation)
          (3) q[0,n] + q[1,n] + q[2,n] ≥ Q_n             (partition lower bound)

        MILP mode replaces (1) and (2) with big-M binary constraints using gn and zl.

        U_n = 0.15*q[1,n] + 0.20*q[2,n] is computed as a derived quantity after solving.
        """
        for n in range(self.N_n):
            # Per-year filing status: couple switches to Single at n_d.
            status_n = 0 if (self.N_i == 2 and n >= self.n_d) else self.N_i - 1

            # Inflation-adjusted bracket thresholds.
            T15_n = self.gamma_n[n] * tx.capGainRates[status_n][0]
            T20_n = self.gamma_n[n] * tx.capGainRates[status_n][1]

            q0_idx = self.vm["q"].idx(0, n)  # p=0: 0% bracket
            q1_idx = self.vm["q"].idx(1, n)  # p=1: 15% bracket
            q2_idx = self.vm["q"].idx(2, n)  # p=2: 20% bracket

            if self._ltcg_lp:
                # =========================================================
                # MILP mode: G_n is a continuous LP variable (gn), bracket
                # room is encoded via big-M binary constraints with zl.
                # =========================================================
                gn_idx = self.vm["gn"].idx(n)
                zl15_idx = self.vm["zl"].idx(0, n)  # regime binary: G_n < T15
                zl20_idx = self.vm["zl"].idx(1, n)  # regime binary: G_n < T20

                # The link rows must reach from a threshold to whatever ordinary income can be,
                # in either direction; the shutoff rows only have to cover the gains themselves.
                ceiling_n = self._ceiling_n[n]
                M_ltcg = max(T20_n, ceiling_n - T15_n)

                # G_n equality: gn = sum_t f_tn  (ordinary taxable income)
                row_gn = {gn_idx: 1}
                for t in range(self.N_t):
                    row_gn[self.vm["f"].idx(t, n)] = row_gn.get(self.vm["f"].idx(t, n), 0) - 1
                self.A.addNewRow(row_gn, 0, 0, tag=("ltcg_gn_def", n))

                # Big-M link for zl15: G_n + M*zl15 in [T15, T15+M]
                # Equivalent to: if zl15=0 then G_n = T15 (exactly), if zl15=1 then G_n <= T15+M
                # More precisely: T15 <= G_n + M*zl15 <= T15+M
                # When zl15=0: T15 <= G_n <= T15 → G_n=T15 (at threshold)
                # When zl15=1: T15 <= G_n+M <= T15+M → G_n >= T15-M (always true), G_n <= T15
                # Actually we want: zl15=1 iff G_n >= T15
                # Use: G_n - M*(1-zl15) <= T15  and  G_n >= T15 - M*zl15
                # Simplified: G_n + M*zl15 >= T15  (if zl15=0 → G_n >= T15)
                #             G_n + M*zl15 <= T15+M (always feasible)
                # Better: addNewRow({gn_idx:1, zl15_idx:M_ltcg}, T15_n, T15_n+M_ltcg)
                self.A.addNewRow({gn_idx: 1, zl15_idx: M_ltcg}, T15_n, T15_n + M_ltcg, tag=("ltcg_zl15_link", n))
                self.A.addNewRow({gn_idx: 1, zl20_idx: M_ltcg}, T20_n, T20_n + M_ltcg, tag=("ltcg_zl20_link", n))

                # q[0] room15 upper bound: q0 + G_n + M*zl15 <= T15 + M
                # → q0 <= T15 - G_n + M*(1-zl15) (unlimited when zl15=1, i.e. G_n>=T15)
                self.A.addNewRow(
                    {q0_idx: 1, gn_idx: 1, zl15_idx: M_ltcg}, -np.inf, T15_n + M_ltcg, tag=("ltcg_room15_mip", n)
                )
                # q[0] forced zero when G_n >= T15 (zl15=1): q0 - M*zl15 <= 0
                self.A.addNewRow({q0_idx: 1, zl15_idx: -M_ltcg}, -np.inf, 0, tag=("ltcg_q0_zero", n))

                # q[0]+q[1] room20 upper bound: q0+q1 + G_n + M*zl20 <= T20 + M
                self.A.addNewRow(
                    {q0_idx: 1, q1_idx: 1, gn_idx: 1, zl20_idx: M_ltcg},
                    -np.inf,
                    T20_n + M_ltcg,
                    tag=("ltcg_room20_mip", n),
                )
                # q[0]+q[1] forced zero when G_n >= T20 (zl20=1): q0+q1 - M*zl20 <= 0
                self.A.addNewRow({q0_idx: 1, q1_idx: 1, zl20_idx: -M_ltcg}, -np.inf, 0, tag=("ltcg_q01_zero", n))

                # Monotonicity: zl15 <= zl20 (if G_n <= T15 then G_n <= T20, so room for 0% implies room for 15%)
                # zl15 - zl20 <= 0  →  addNewRow({zl15:1, zl20:-1}, -inf, 0)
                self.A.addNewRow({zl15_idx: 1, zl20_idx: -1}, -np.inf, 0, tag=("ltcg_zl_monotone", n))

            else:
                # =========================================================
                # LP (loop) mode: use SC-loop G_n parameter for bracket room.
                # =========================================================
                # LTCG is stacked on top of ordinary taxable income G_n (from previous SC iteration).
                # G_n is initialised to 0 for the first iteration (zero ordinary income assumption).
                # room15_n / room20_n = T15/T20 threshold minus ordinary income already filling the bracket.
                room15_n = max(0.0, T15_n - self.G_n[n])
                room20_n = max(0.0, T20_n - self.G_n[n])
                # (1) q[0,n] ≤ room15_n (enforced via variable upper bound)
                self.B.setRange(q0_idx, 0, room15_n)
                # (2) q[0,n] + q[1,n] ≤ room20_n
                self.A.addNewRow({q0_idx: 1, q1_idx: 1}, -np.inf, room20_n, tag=("ltcg_room20", n))
                # q[1] upper bound = remaining 15% bracket width after stacking ordinary income.
                self.B.setRange(q1_idx, 0, max(0.0, room20_n - room15_n))
                # q[2] is unbounded above (the 20% bracket has no cap).

            # === Partition lower-bound constraint (both modes): q[0]+q[1]+q[2] ≥ Q_n ===
            # Q_portfolio_n = sum_i alpha_i00n * [mu*(b_i0n + d_in - w_i0n) + cap_rate*w_i0n
            #                                     + 0.5*mu*kappa_i0n]
            # Rearranged: sum_i alpha_i00n * [mu*b_i0n + (cap_rate-mu)*w_i0n + mu*d_in]
            # The kappa half-period correction goes to the RHS.
            rhs_q = self.fixed_assets_capital_gains_n[n]
            row_q = {q0_idx: 1, q1_idx: 1, q2_idx: 1}
            for i in range(self.N_i):
                alpha = self.alpha_ijkn[i, 0, 0, n]
                if alpha == 0:
                    continue
                b_idx = self.vm["b"].idx(i, 0, n)
                w_idx = self.vm["w"].idx(i, 0, n)
                d_idx = self.vm["d"].idx(i, n)
                gf = self._effective_cap_gain_coef(i, n)
                row_q[b_idx] = row_q.get(b_idx, 0) - alpha * self.mu
                row_q[w_idx] = row_q.get(w_idx, 0) - alpha * (gf - self.mu)
                row_q[d_idx] = row_q.get(d_idx, 0) - alpha * self.mu
                rhs_q += alpha * 0.5 * self.mu * self.kappa_ijn[i, 0, n]

            # (3) q[0]+q[1]+q[2] − Q_portfolio_LP_vars ≥ Q_fixed + kappa_correction
            self.A.addNewRow(row_q, rhs_q, np.inf, tag=("ltcg_partition_lo", n))

            # (3') Companion upper bound on the same row: prevents q[1,n]/q[2,n] from being
            # inflated along the flat direction shared with f_tn's per-bracket split (q[2,n]
            # is otherwise unbounded above in loop mode). Without a loss the two rows make the
            # partition an equality: the brackets hold exactly the year's gains. loss_buf widens
            # the bound only so a capital-loss year (Q_n < 0) stays feasible, since q >= 0:
            #   - fixed-asset capital loss for year n is a known parameter, so cover it
            #     directly (this keeps iteration 0, where prevQ is None, safe);
            #   - any portfolio loss surfaces in the previous iteration's realized Q_n.
            # prevQ[n] already includes the fixed-asset component, so take the larger.
            # No further tolerance: a dollar of room was taken whenever it cost nothing (gains in
            # the 0% bracket) and inflated the MAGI built from the partition (niit_magi_def), so
            # the reported MAGI sat a dollar above the income the ACA and IRMAA rows had priced.
            fixed_loss = max(0.0, -float(self.fixed_assets_capital_gains_n[n]))
            prevQ = getattr(self, "Q_n", None)
            prev_loss = 0.0 if prevQ is None else max(0.0, -float(prevQ[n]))
            loss_buf = max(fixed_loss, prev_loss)
            self.A.addNewRow(row_q, -np.inf, rhs_q + loss_buf, tag=("ltcg_partition_hi", n))

    @_fixedAcrossIterations
    def _add_magi_lp(self, options):
        """
        Add MAGI equality constraints when withNIIT='optimize'.

        The "magi" LP variable is the AGI-basis MAGI used by NIIT (IRC §1411): taxable SS
        only, NOT the full-SS ACA MAGI. Since e_n + G_n already include the taxable SS
        portion (via _add_taxable_income), AGI = e_n + G_n + Q_n with NO extra SS term:

          magi_n = G_n + e_n + Q_n
        where:
          - G_n = sum_t f_tn  (ordinary taxable income, via gn LP var or direct f_tn sum)
          - e_n = standard deduction headroom (carries the taxable SS already)
          - Q_n = q[0]+q[1]+q[2]  (LTCG bracket allocation variables; equals Q_n at partition minimum)

        Rewritten as equality constraint with all LP vars on LHS:
          magi_n - gn_n - e_n - q[0] - q[1] - q[2] = 0
        """
        if not self._niit_lp:
            return

        for n in range(self.N_n):
            magi_idx = self.vm["magi"].idx(n)
            e_idx = self.vm["e"].idx(n)

            # Build MAGI equality row: magi_n = G_n + e_n + Q_n
            row = {magi_idx: 1, e_idx: -1}

            # G_n contribution: either via gn LP var or directly from f_tn vars
            if "gn" in self.vm:
                row[self.vm["gn"].idx(n)] = row.get(self.vm["gn"].idx(n), 0) - 1
            else:
                for t in range(self.N_t):
                    f_idx = self.vm["f"].idx(t, n)
                    row[f_idx] = row.get(f_idx, 0) - 1

            # Q_n contribution: use q bracket variables directly.
            # The LTCG partition constraint enforces q[0]+q[1]+q[2] >= Q_n, so at the
            # partition minimum the sum equals Q_n. Do NOT substitute the portfolio LP
            # expression for Q_n: those portfolio terms (b, w, d) cancel q_total at the
            # partition minimum, removing Q_n from MAGI entirely (the root-cause bug).
            q0_idx = self.vm["q"].idx(0, n)
            q1_idx = self.vm["q"].idx(1, n)
            q2_idx = self.vm["q"].idx(2, n)
            row[q0_idx] = row.get(q0_idx, 0) - 1
            row[q1_idx] = row.get(q1_idx, 0) - 1
            row[q2_idx] = row.get(q2_idx, 0) - 1

            # No SS term: taxable SS is already embedded in e_n + G_n (AGI basis).
            self.A.addNewRow(row, 0.0, 0.0, tag=("niit_magi_def", n))

    def _configure_NIIT_binary_variables(self, options):
        """
        Add NIIT big-M binary constraints when withNIIT='optimize'.

        IRS formula: J_n = 0.038 * max(0, min(MAGI_n - T, NII_n))
        where NII_n = I_n + Q_n (net investment income: interest/divs + capital gains).

        J_n is a cost the optimizer minimizes, so it settles on the largest of its lower bounds.
        One binary zj_n chooses which term of the min() bounds it:

          (1) J_n >= 0.038*(MAGI_n - T) - M*zj      [zj=0: the excess over the threshold]
          (2) J_n >= 0.038*NII_n - M*(1-zj)         [zj=1: the investment income]
          (3) J_n >= 0                              [column bound]
          (4) J_n <= 0.038*NII_n                    [cap: never more than 3.8% of NII]

        Choosing the smaller branch gives J_n = 0.038*max(0, min(MAGI_n - T, NII_n)) over every
        income range, including T < MAGI_n < T + NII_n. With the AGI-basis MAGI = G_n + e_n + Q_n,
        NII_n = I_n + Q_n = I_n + MAGI_n - G_n - e_n, so row (2) needs no capital-gains term.
        I_n (interest and the taxed bond/cash returns of the taxable account, plus rent and trust
        income) enters as the same LP expression _aggregateResults evaluates, not as the previous
        iteration's value: sum_i fak_in*(b_i0n + d_in - w_i0n) + netinv_n.
        """
        if not self._niit_lp:
            return

        fak_in = np.sum(np.maximum(0, self.tau_kn[1:, :]) * self.alpha_ijkn[:, 0, 1:, : self.N_n], axis=1)

        for n in range(self.N_n):
            # Per-year filing status: couple switches to Single at n_d.
            status_n = 0 if (self.N_i == 2 and n >= self.n_d) else self.N_i - 1
            T_niit = 200000.0 if status_n == 0 else 250000.0  # NOT inflation-adjusted

            # Each row is relaxed by at most 3.8% of the year's income: MAGI and NII are both
            # bounded by the income ceiling.
            M_niit = 0.038 * max(self._ceiling_n[n], T_niit)

            Jn_idx = self.vm["Jn"].idx(n)
            magi_idx = self.vm["magi"].idx(n)
            zj_idx = self.vm["zj"].idx(n)
            e_idx = self.vm["e"].idx(n)

            # Bounds
            self.B.setRange(Jn_idx, 0, 0.038 * self._ceiling_n[n])
            self.B.setRange(magi_idx, 0, max(self._ceiling_n[n], T_niit))

            # (1) J_n >= 0.038*(MAGI_n - T) - M*zj  →  J_n - 0.038*magi_n + M*zj >= -0.038*T
            self.A.addNewRow(
                {Jn_idx: 1, magi_idx: -0.038, zj_idx: M_niit},
                -0.038 * T_niit,
                np.inf,
                tag=("niit_excess", n),
            )

            # (2) J_n >= 0.038*(I_n + MAGI_n - G_n - e_n) - M*(1-zj), with I_n as an LP expression
            #   →  J_n - 0.038*magi_n + 0.038*G_n + 0.038*e_n - 0.038*I_portfolio_n - M*zj
            #        >= 0.038*netinv_n - M
            row2 = {Jn_idx: 1, magi_idx: -0.038, e_idx: 0.038, zj_idx: -M_niit}
            for i in range(self.N_i):
                fak = fak_in[i, n]
                if fak == 0:
                    continue
                for idx, coef in ((self.vm["b"].idx(i, 0, n), -0.038 * fak),
                                  (self.vm["d"].idx(i, n), -0.038 * fak),
                                  (self.vm["w"].idx(i, 0, n), 0.038 * fak)):
                    row2[idx] = row2.get(idx, 0) + coef
            if "gn" in self.vm:
                g_idx = self.vm["gn"].idx(n)
                row2[g_idx] = row2.get(g_idx, 0) + 0.038
            else:
                for t in range(self.N_t):
                    f_idx = self.vm["f"].idx(t, n)
                    row2[f_idx] = row2.get(f_idx, 0) + 0.038
            netinv_n = float(np.sum(self.netinv_in[:, n]))
            self.A.addNewRow(row2, 0.038 * netinv_n - M_niit, np.inf, tag=("niit_nii", n))

            # (4) J_n <= 0.038*NII_n: the tax can never exceed 3.8% of investment income, whichever
            # branch applies. Rows (1)-(3) only bound J_n from below and rely on its being minimized;
            # where the plan's money is worth nothing to the objective (e.g. a first spouse's
            # assets left to non-spouse heirs, when only the final bequest counts) the solver was
            # free to overpay, and charged $190k-290k a year on under $3,000 of NII.
            # Same terms as row (2), J_n - 0.038*(I_portfolio + MAGI - G - e), without the switch.
            row4 = {k: v for k, v in row2.items() if k != zj_idx}
            self.A.addNewRow(row4, -np.inf, 0.038 * netinv_n, tag=("niit_nii_cap", n))

    def _configure_Medicare_binary_variables(self, options):
        if options.get("withMedicare", "loop") != "optimize":
            return

        Nmed = self.N_n - self.nm
        # Select exactly one IRMAA bracket per year (SOS1 behavior).
        for nn in range(Nmed):
            row = self.A.newRow()
            for q in range(self.N_irmaa):
                row.addElem(self.vm["zm"].idx(nn, q), 1)
            self.A.addRow(row, 1, 1, tag=("irmaa_amo", nn))

        # MAGI decomposition into bracket portions: sum_q h_{q} = MAGI.
        for nn in range(Nmed):
            n = self.nm + nn
            row = self.A.newRow()
            for q in range(self.N_irmaa):
                row.addElem(self.vm["h"].idx(nn, q), 1)

            if n < 2:
                # MAGI for the first two plan years is known (prevMAGI from user-supplied data).
                self.A.addRow(row, self.prevMAGI[n], self.prevMAGI[n], tag=("irmaa_magi_def", nn))
                # Pre-fix the bracket to match the known MAGI in all solver modes, including
                # a decomposition.  The correct bracket is deterministic, so pre-fixing (Lb == Ub)
                # settles it. Without pre-fixing, the LP relaxation pushes h-values toward low-premium
                # brackets (maximizer behaviour) so argmax(h) picks the wrong bracket for these
                # years.
                magi = self.prevMAGI[n]
                qsel = 0
                for q in range(1, self.N_irmaa):
                    if magi > self.Lbar_nq[nn, q - 1]:
                        qsel = q

                for q in range(self.N_irmaa):
                    idx = self.vm["zm"].idx(nn, q)
                    val = 1 if q == qsel else 0
                    self.B.setRange(idx, val, val)
                continue

            n2 = n - 2
            rhs = self.fixed_assets_ordinary_income_n[n2] + self.fixed_assets_capital_gains_n[n2]

            # IRMAA MAGI is AGI-basis: include only the *taxable* portion of SS. When SS
            # taxability is optimized, taxable SS is the LP var tss[n2] (added once, below);
            # otherwise it is the SC-loop parameter Psi_n[n2]*zetaBar_in[i,n2].
            ss_lp = "tss" in self.vm
            # The terms below are income before the standard exemption, which is what AGI
            # is: G_(n-2) + e_(n-2). Subtracting e here as well would add it a second time.
            for i in range(self.N_i):
                row.addElem(self.vm["w"].idx(i, 1, n2), -1)
                row.addElem(self.vm["x"].idx(i, n2), -1)

                # Dividends and interest gains for year n2. Only positive returns are taxable.
                afac = self.mu * self.alpha_ijkn[i, 0, 0, n2] + np.sum(
                    self.alpha_ijkn[i, 0, 1:, n2] * np.maximum(0, self.tau_kn[1:, n2])
                )

                row.addElem(self.vm["b"].idx(i, 0, n2), -afac)
                row.addElem(self.vm["d"].idx(i, n2), -afac)

                # Capital gains on taxable account withdrawal (uses tracked basis if available).
                bfac = self.alpha_ijkn[i, 0, 0, n2] * self._effective_cap_gain_coef(i, n2)
                row.addElem(self.vm["w"].idx(i, 0, n2), afac - bfac)

                sumoni = (
                    self.omega_in[i, n2]
                    + self.other_inc_in[i, n2]
                    + self.netinv_in[i, n2]
                    + self.piBar_in[i, n2]
                    + self.spiaBar_in[i, n2]
                    + 0.5 * self.kappa_ijn[i, 0, n2] * afac
                )
                if not ss_lp:
                    ss_const, ssb_idx = self._ss_benefit_terms(i, n2)
                    sumoni += self.Psi_n[n2] * ss_const  # taxable SS (SC-loop param)
                    if ssb_idx is not None:
                        row.addElem(ssb_idx, -self.Psi_n[n2])
                rhs += sumoni

            if ss_lp:
                row.addElem(self.vm["tss"].idx(n2), -1)  # taxable SS (LP var) on LHS

            self.A.addRow(row, rhs, rhs, tag=("irmaa_magi_def", nn))

        # Bracket bounds: L_{q-1} z_q <= mg_q <= L_q z_q, the lower one raised by BRACKET_MARGIN
        # except in the first two years, whose bracket is pinned from the known MAGI above.
        for nn in range(Nmed):
            margin = BRACKET_MARGIN if self.nm + nn >= 2 else 0.0
            for q in range(self.N_irmaa):
                mg_idx = self.vm["h"].idx(nn, q)
                zm_idx = self.vm["zm"].idx(nn, q)

                lower = 0 if q == 0 else self.Lbar_nq[nn, q - 1] + margin
                if lower > 0:
                    self.A.addNewRow({mg_idx: 1, zm_idx: -lower}, 0, np.inf, tag=("irmaa_bracket_lb", nn, q))

                if q < self.N_irmaa - 1:
                    upper = self.Lbar_nq[nn, q]
                else:
                    # Upper bound for last bracket so h_qn = 0 when z_q = 0.
                    upper = self._ceiling_n[self.nm + nn]  # the year's MAGI ceiling
                self.A.addNewRow({mg_idx: 1, zm_idx: -upper}, -np.inf, 0, tag=("irmaa_bracket_ub", nn, q))

    @_fixedAcrossIterations
    def _add_Medicare_costs(self, options):
        if options.get("withMedicare", "loop") != "optimize":
            # In loop mode, Medicare costs are computed outside the solver (M_n).
            # Ensure the in-model Medicare variable (m_n) stays at zero.
            for n in range(self.N_n):
                self.B.setRange(self.vm["m"].idx(n), 0, 0)
            return

        for n in range(self.nm):
            self.B.setRange(self.vm["m"].idx(n), 0, 0)

        Nmed = self.N_n - self.nm
        for nn in range(Nmed):
            n = self.nm + nn
            row = self.A.newRow()
            row.addElem(self.vm["m"].idx(n), 1)
            for q in range(self.N_irmaa):
                row.addElem(self.vm["zm"].idx(nn, q), -self.Cbar_nq[nn, q])
            self.A.addRow(row, 0, 0, tag=("irmaa_cost_def", nn))

    def _configure_ACA_binary_variables(self, options):
        """
        Build ACA MIP constraints (withACA="optimize" mode only).

        Three constraint groups:
          a) SOS1: exactly one ACA bracket selected per year.
          b) MAGI decomposition: sum_q haca[nn, q] = MAGI_n (current year, no 2-year lag).
          c) Bracket bounds (Big-M): MAGI portion in bracket q is within its FPL thresholds.

        Note: ACA uses current-year MAGI (no 2-year lag like Medicare IRMAA).
        Note: MAGI below 138% FPL is bracket 0, Medicaid at no premium, as in loop mode.
        """
        if not self._aca_lp:
            return

        # a) SOS1: exactly one bracket selected per year.
        for nn in range(self.n_aca):
            row = self.A.newRow()
            for r in range(tx.N_ACA_R):
                row.addElem(self.vm["za"].idx(nn, r), 1)
            self.A.addRow(row, 1, 1, tag=("aca_amo", nn))

        # b) MAGI decomposition: sum_r haca[nn, r] = current-year MAGI.
        for nn in range(self.n_aca):
            n = nn  # ACA uses current year (no lag)
            rhs_magi = self.fixed_assets_ordinary_income_n[n] + self.fixed_assets_capital_gains_n[n]

            # As for IRMAA: these terms are income before the standard exemption, so the
            # exemption is already in them and must not be subtracted a second time.
            row_magi = {}

            for i in range(self.N_i):
                afac = self.mu * self.alpha_ijkn[i, 0, 0, n] + np.sum(
                    self.alpha_ijkn[i, 0, 1:, n] * np.maximum(0, self.tau_kn[1:, n])
                )
                bfac = self.alpha_ijkn[i, 0, 0, n] * self._effective_cap_gain_coef(i, n)

                w1_idx = self.vm["w"].idx(i, 1, n)
                x_idx = self.vm["x"].idx(i, n)
                b_idx = self.vm["b"].idx(i, 0, n)
                d_idx = self.vm["d"].idx(i, n)
                w0_idx = self.vm["w"].idx(i, 0, n)

                row_magi[w1_idx] = row_magi.get(w1_idx, 0) - 1
                row_magi[x_idx] = row_magi.get(x_idx, 0) - 1
                row_magi[b_idx] = row_magi.get(b_idx, 0) - afac
                row_magi[d_idx] = row_magi.get(d_idx, 0) - afac
                row_magi[w0_idx] = row_magi.get(w0_idx, 0) + (afac - bfac)

                ss_const, ssb_idx = self._ss_benefit_terms(i, n)
                if ssb_idx is not None:
                    row_magi[ssb_idx] = row_magi.get(ssb_idx, 0) - 1
                rhs_magi += (
                    self.omega_in[i, n]
                    + self.other_inc_in[i, n]
                    + self.netinv_in[i, n]
                    + ss_const  # full SS (not 0.5×SS; ACA uses MAGI)
                    + self.piBar_in[i, n]
                    + self.spiaBar_in[i, n]
                    + 0.5 * self.kappa_ijn[i, 0, n] * afac
                )

            for r in range(tx.N_ACA_R):
                haca_idx = self.vm["haca"].idx(nn, r)
                row_magi[haca_idx] = row_magi.get(haca_idx, 0) + 1

            self.A.addNewRow(row_magi, rhs_magi, rhs_magi, tag=("aca_magi_def", nn))

        # c) Bracket bounds: Lbar[nn, r-1]*za[r] <= haca[r] <= Lbar[nn, r]*za[r], the lower one
        # raised by BRACKET_MARGIN.
        for nn in range(self.n_aca):
            for r in range(tx.N_ACA_R):
                haca_idx = self.vm["haca"].idx(nn, r)
                za_idx = self.vm["za"].idx(nn, r)

                lower = 0 if r == 0 else self.Lbar_aca_nr[nn, r - 1] + BRACKET_MARGIN
                if lower > 0:
                    self.A.addNewRow({haca_idx: 1, za_idx: -lower}, 0, np.inf, tag=("aca_bracket_lb", nn, r))

                if r < tx.N_ACA_R - 1:
                    upper = self.Lbar_aca_nr[nn, r]
                    if upper <= lower:
                        # Above the MAGI where the contribution reaches the SLCSP (see
                        # tx._aca_capped_limits): such incomes belong to the full-premium bracket.
                        self.B.setRange(za_idx, 0, 0)
                else:
                    # Last bracket (full SLCSP, from 400% FPL or the cap crossing): BigM upper bound
                    # so haca = 0 when za = 0.
                    upper = self._ceiling_n[nn]  # the year's MAGI ceiling
                self.A.addNewRow({haca_idx: 1, za_idx: -upper}, -np.inf, 0, tag=("aca_bracket_ub", nn, r))

    @_fixedAcrossIterations
    def _add_ACA_costs(self, options):
        """
        Add ACA cost constraints for the LP/MIP formulation (optimize mode only).

        In optimize mode, for each tangent k:
            maca_n >= sum_{r=1}^{5} (slope_rk * haca[nn,r] + intercept_rk * za[nn,r]) + slcsp_aca_n[nn] * za[nn,6].
        Only the selected bracket's terms are nonzero, so row k is that bracket's k-th tangent under
        its sliding-scale cost pct(MAGI) * MAGI, and maca is their maximum. Bracket 0 (below 138% FPL)
        is Medicaid, at no cost; bracket 6 (400% and up) pays the full SLCSP. maca is priced slightly
        in the objective (MIP_TIEBREAK) so it never rises above that maximum where cash has no value.
        In loop mode: maca variable does not exist; ACA_n (SC loop) goes in the cash-flow RHS.
        """
        if not self._aca_lp:
            return  # Loop mode: no maca variable; ACA_n from SC loop is in the cash-flow RHS.

        # Pin post-ACA years to zero (individual is on Medicare; no ACA cost).
        for n in range(self.n_aca, self.N_n):
            self.B.setRange(self.vm["maca"].idx(n), 0, 0)

        # Cost: maca_n >= each tangent of the selected bracket (sliding scale), or the full SLCSP in
        # bracket 6 (>400% FPL: no PTC under 2026 rules). Bracket 0 (Medicaid) adds nothing.
        for nn in range(self.n_aca):
            for k in range(self.tangents_aca_nrk.shape[2]):
                row = self.A.newRow({self.vm["maca"].idx(nn): 1})
                for r in range(1, tx.N_ACA_R - 1):
                    slope, intercept = self.tangents_aca_nrk[nn, r, k]
                    row.addElem(self.vm["haca"].idx(nn, r), -slope)
                    row.addElem(self.vm["za"].idx(nn, r), -intercept)
                row.addElem(self.vm["za"].idx(nn, tx.N_ACA_R - 1), -self.slcsp_aca_n[nn])
                self.A.addRow(row, 0, np.inf, tag=("aca_cost_def", nn, k))
            self.B.setRange(self.vm["maca"].idx(nn), 0, self.slcsp_aca_n[nn])

    def _build_objective_vector(self, objective, options):
        c_arr = np.zeros(self.nvars)

        # Time preference discount: ρ > 0 increases the relative value of near-term spending,
        # counteracting the optimizer's tendency to back-load spending. Has no effect on maxBequest.
        rho = u.get_numeric_option(options, "timePreference", 0.0, min_value=0) / 100.0
        discount_n = np.array([(1.0 / (1.0 + rho)) ** n for n in range(self.N_n)])

        if objective == "maxSpending":
            for n in range(self.N_n):
                c_arr[self.vm["g"].idx(n)] = -discount_n[n] / self.gamma_n[n]
        elif objective == "maxBequest":
            for i in range(self.N_i):
                c_arr[self.vm["b"].idx(i, 0, self.N_n)] = -1
                c_arr[self.vm["b"].idx(i, 1, self.N_n)] = -(1 - self.nu)
                c_arr[self.vm["b"].idx(i, 2, self.N_n)] = -1
                c_arr[self.vm["b"].idx(i, 3, self.N_n)] = -(1 - self.nu)  # HSA: heirs pay ordinary income tax
        else:
            raise RuntimeError("Internal error in objective function.")

        self._add_partial_bequest_weight(c_arr, objective, options)

        if self._tax_tiebreak_on:
            c_arr += TAX_TIEBREAK * self._tax_cost_vector()

        # The ACA cost in optimize mode is only bounded below (by its tangents), so price it slightly:
        # in a year whose cash has no value it would otherwise be free to rise (see TAX_TIEBREAK).
        if "maca" in self.vm:
            for n in range(self.N_n):
                c_arr[self.vm["maca"].idx(n)] += MIP_TIEBREAK / self.gamma_n[n]

        # Turn on epsilon by default to reduce churn and frontload Roth conversions.
        default_epsilon = EPSILON
        epsilon = u.get_numeric_option(options, "epsilon", default_epsilon, min_value=0)
        if epsilon > 0:
            # Penalize Roth conversions to reduce churn.
            for i in range(self.N_i):
                for n in range(self.N_n):
                    c_arr[self.vm["x"].idx(i, n)] += epsilon * (1 + n)

            # Prefer leaving a dollar where it is never taxed again. A household with no
            # tax to pay -- income under the standard deduction and gains inside the 0%
            # bracket -- gets nothing from the distinction between a tax-free account and
            # a taxable one, so without a tie-break the optimizer is free to empty the
            # tax-free account into the taxable one and often does. The preference is far
            # too small to outweigh any real reason to draw on the account.
            for i in range(self.N_i):
                for n in range(self.N_n):
                    c_arr[self.vm["w"].idx(i, 2, n)] += epsilon

            # Prefer not to withdraw money only to bank it again. The round trip is free
            # whenever it happens, so nothing else rules it out, and it is not harmless:
            # a taxable withdrawal resets cost basis, which feeds back through the
            # self-consistent loop and can settle the plan on a worse fixed point.
            for n in range(self.N_n):
                c_arr[self.vm["s"].idx(n)] += epsilon

            if self.N_i == 2:
                # Favor withdrawals from spouse 0 by penalizing spouse 1 withdrawals.
                for j in range(self.N_j):
                    for n in range(self.N_n):
                        c_arr[self.vm["w"].idx(1, j, n)] += epsilon

            # Take the full state deduction and exemptions even where a personal credit already
            # cancels the year's state tax: nothing else then prices state taxable income, so the
            # solver could leave the deduction unused and report a larger taxable income.
            if "st_c" in self.vm:
                for t in range(self.N_st):
                    for n in range(self.N_n):
                        c_arr[self.vm["st_f"].idx(t, n)] += epsilon

            # Pin taxable Social Security in the years where it costs nothing. Nothing in
            # the formulation selects between the two z^σ_0 branches when the year owes no
            # tax on the benefit, and the branch that sets z^σ_0 = 1 forces
            # p^{σ,min}_n up to min(ΔP, ζ̄_n) rather than down to max(0, Π_n - P^lo), so the
            # solver can report half the benefit as taxable in a year whose provisional
            # income is below P^lo entirely. Preferring the smaller share recovers the IRS
            # formula and cannot outweigh a real cost: a taxable dollar of benefit is worth
            # at least the lowest bracket rate, five orders of magnitude more than this.
            #
            # EPSILON is sized for tie-breaks between vertices of an LP, where the simplex
            # resolves them exactly. It is too small to be seen through a MIP gap: at 1e-8
            # against a few thousand dollars of benefit it moves the objective by ~1e-5,
            # below the solver's own optimality tolerance, and the branch stays arbitrary.
            # Measured on an earlier, much lower-benefit configuration of Case_cameron, years
            # reported wrong out of 23: all of them at 1e-7, 16 at 1e-6, one at 1e-5, none at
            # 1e-4, and the objective is identical from 1e-4 through 1e-3. That case now keeps
            # provisional income under P^lo in every year and no longer exercises this, so the
            # figures above are not reproducible from a shipped example.
            # A case that settles on a cycle can still report a wrong share:
            # it is answered from a best-of-cycle iterate, and raising the preference far
            # enough to pin that starts to move the objective instead.
            if "tss" in self.vm:
                for n in range(self.N_n):
                    c_arr[self.vm["tss"].idx(n)] += MIP_TIEBREAK

        c = abc.Objective(self.nvars)
        for idx in np.flatnonzero(c_arr):
            c.setElem(idx, c_arr[idx])
        self.c = c

    def _add_partial_bequest_weight(self, c_arr, objective, options):
        """Value what the first spouse leaves to non-spouse heirs: w today's dollars per dollar.

        With beneficiary fractions below 1, part of the first spouse's accounts leaves the
        household at the first death. Neither objective counts it, so wherever that money is not
        needed the solver is indifferent to how much of it remains, and the partial bequest is
        arbitrary. The weight makes leaving it preferable to spending it to no purpose. The
        partial bequest is the expression Plan._aggregateResults reports (after the heirs' tax on
        tax-deferred and HSA money), in today's dollars of the year of the first death.
        """
        gap = u.get_numeric_option(options, "gap", GAP, min_value=0)
        w = u.get_numeric_option(options, "partialBequestWeight", max(PARTIAL_BEQUEST_WEIGHT, 2 * gap), min_value=0)
        if w == 0 or self.N_i != 2 or self.n_d >= self.N_n or np.all(self.phi_j >= 1):
            return
        n_d, nx, i = self.n_d, self.n_d - 1, self.i_d
        # Both objectives in the units of their own value: maxBequest maximizes final nominal
        # balances, maxSpending today's-dollar spending.
        scale = self.gamma_n[self.N_n] / self.gamma_n[n_d] if objective == "maxBequest" else 1.0 / self.gamma_n[n_d]
        vm = self.vm
        for j in range(self.N_j):
            frac = (1 - self.phi_j[j]) * ((1 - self.nu) if j in (1, 3) else 1.0)
            if frac <= 0:
                continue
            Tau1 = 1 + np.sum(self.alpha_ijkn[i, j, :, nx] * self.tau_kn[:, nx])
            coef = -w * scale * frac * Tau1  # objective is minimized
            c_arr[vm["b"].idx(i, j, nx)] += coef
            c_arr[vm["w"].idx(i, j, nx)] -= coef
            if j == 0:
                c_arr[vm["d"].idx(i, nx)] += coef
            elif j == 1:
                c_arr[vm["x"].idx(i, nx)] -= coef
            elif j == 2:
                c_arr[vm["x"].idx(i, nx)] += coef

    def _tax_cost_vector(self):
        """Tax each bracket variable charges per dollar, in today's dollars, as a dense vector.

        Federal ordinary and capital-gains brackets, state brackets (with any local surcharge on
        them) and local brackets: the terms the cash-flow row charges on these columns.
        """
        cost = np.zeros(self.nvars)
        vm = self.vm
        for n in range(self.N_n):
            deflate = 1.0 / self.gamma_n[n]
            for t in range(self.N_t):
                cost[vm["f"].idx(t, n)] = self.theta_tn[t, n] * deflate
            cost[vm["q"].idx(1, n)] = 0.15 * deflate
            cost[vm["q"].idx(2, n)] = 0.20 * deflate
            if "st_f" in vm:
                for t in range(self.N_st):
                    cost[vm["st_f"].idx(t, n)] = self.st_theta_tn[t, n] * (1 + self.lt_surcharge_n[n]) * deflate
            if "lt_f" in vm:
                for t in range(self.N_lt):
                    cost[vm["lt_f"].idx(t, n)] = self.lt_theta_tn[t, n] * deflate
        return cost

    def _bracket_order_excess(self, x=None):
        """Tax the solution charges beyond what its own income owes with brackets filled bottom-up.

        Returns (years, excess): the plan years whose federal, state or local brackets are filled
        out of order, and the overcharge summed over the horizon in today's dollars. Zero when the
        relaxation is tight, which it is wherever the year's cash has a price. Reads the solution
        vector x when given, the aggregated results otherwise.
        """
        vm = self.vm
        if x is None:
            f_tn, st_f_tn, lt_f_tn = self.f_tn, self.st_f_tn, self.lt_f_tn
        else:
            f_tn = vm["f"].extract(x)
            st_f_tn = vm["st_f"].extract(x) if "st_f" in vm else np.zeros((self.N_st, self.N_n))
            lt_f_tn = vm["lt_f"].extract(x) if "lt_f" in vm else np.zeros((self.N_lt, self.N_n))

        def ordered_tax(total, width, rate):
            tax = 0.0
            for t in range(len(width)):
                part = min(max(total, 0.0), width[t])
                tax += part * rate[t]
                total -= part
            return tax

        years = []
        excess = 0.0
        schedules = [(f_tn, self.DeltaBar_tn, self.theta_tn)]
        if self.N_st > 0 and np.any(st_f_tn):
            schedules.append((st_f_tn, self.st_DeltaBar_tn, self.st_theta_tn))
        if self.N_lt > 0 and np.any(lt_f_tn):
            schedules.append((lt_f_tn, self.lt_DeltaBar_tn, self.lt_theta_tn))
        for n in range(self.N_n):
            over = 0.0
            for f, width, rate in schedules:
                charged = float(np.dot(f[:, n], rate[:, n]))
                over += charged - ordered_tax(float(np.sum(f[:, n])), width[:, n], rate[:, n])
            if over > 1.0:
                years.append(int(self.year_n[n]))
                excess += over / self.gamma_n[n]
        return years, excess

    def _repairBracketOrder(self, xx, objfn, objective, options, matricesMatch):
        """Re-fill out-of-order tax brackets by re-solving the accepted LP with tax priced (TAX_TIEBREAK).

        Spending is pinned (it is the objective, or fixed by netSpending), and so are the binaries;
        everything else is free, so the tax no longer charged lands where the plan's cash goes,
        usually a larger bequest. The incumbent stays feasible, so the re-solve cannot fail for want
        of a solution. Returns the (possibly repaired) vector and its objective value; any failure
        keeps the solver's own answer, which _check_bracket_order then reports.
        """
        years, excess = self._bracket_order_excess(xx)
        if not years:
            return xx, objfn
        if not matricesMatch:
            self.mylog.vprint(
                "Leaving the tax brackets as solved: an earlier iterate was accepted, so the "
                "constraint matrices no longer describe this solution."
            )
            return xx, objfn

        c_orig = self.c.arrays()
        col_lb, col_ub = self.B.arrays()
        res0 = amorepair.max_row_violation(xx, self.A, col_lb, col_ub)
        overrides = {}
        for n in range(self.N_n):
            j = self.vm["g"].idx(n)
            overrides[j] = (xx[j], xx[j])
        for j in range(self.vm.nconts, self.nvars):
            v = float(np.round(xx[j]))
            overrides[j] = (v, v)
        c_tie = np.asarray(c_orig) + TAX_TIEBREAK * self._tax_cost_vector()
        obj = abc.Objective(self.nvars)
        for j in np.flatnonzero(c_tie):
            obj.setElem(int(j), float(c_tie[j]))
        repair_options = dict(options)
        repair_options["maxTime"] = min(u.get_numeric_option(options, "maxTime", TIME_LIMIT, min_value=0), 60)

        _, yy, ok, msg, _ = self._run_mip(
            self.A, self.B, obj, repair_options, col_overrides=overrides, lp_relax=True, update_warm=False
        )
        if not ok or yy is None:
            self.mylog.vprint(f"Bracket-order repair did not solve ({msg}); keeping the original solution.")
            return xx, objfn
        yy = np.array(yy)
        res = amorepair.max_row_violation(yy, self.A, col_lb, col_ub)
        if res > max(res0, 1.0):
            self.mylog.print(
                f"Bracket-order repair rejected: residual {res:.2e} exceeds {max(res0, 1.0):.2e}.", tag="WARNING"
            )
            return xx, objfn
        new_years, new_excess = self._bracket_order_excess(yy)
        if new_excess >= excess:
            return xx, objfn
        self.mylog.vprint(
            f"Tax brackets re-filled bottom-up in {len(years) - len(new_years)} of {len(years)} year(s); "
            f"{u.d(excess - new_excess)} of tax the income did not owe removed (today's $)."
        )
        return yy, float(np.dot(c_orig, yy))

    def _check_bracket_order(self):
        """Warn when the solved brackets are filled out of order (see TAX_TIEBREAK)."""
        years, excess = self._bracket_order_excess()
        self.bracketOrderExcess = excess
        if years:
            self.mylog.print(
                f"Tax brackets filled out of order in {len(years)} year(s) ({years[0]}-{years[-1]}): "
                f"reported taxes exceed what this income owes by {u.d(excess)} over the horizon "
                "(today's $). The objective is unaffected; taxes and bequest are not.",
                tag="WARNING",
            )

    @_checkConfiguration(requireRates=False)
    @_timer
    def runHistoricalRange(
        self,
        objective,
        options,
        ystart,
        yend,
        *,
        verbose=False,
        figure=False,
        progcall=None,
        reverse=False,
        roll=0,
        augmented=False,
        log_x=False,
    ):
        return run_historical_range(
            self,
            objective,
            options,
            ystart,
            yend,
            verbose=verbose,
            figure=figure,
            progcall=progcall,
            reverse=reverse,
            roll=roll,
            augmented=augmented,
            log_x=log_x,
        )

    @_checkConfiguration(requireRates=False)
    @_timer
    def runMC(self, objective, options, N, verbose=False, figure=False, progcall=None, log_x=False):
        return run_mc(self, objective, options, N, verbose=verbose, figure=figure, progcall=progcall, log_x=log_x)

    @_checkConfiguration(requireRates=False)
    @_timer
    def runStochasticSpending(
        self,
        options,
        scenario_method,
        *,
        ystart=None,
        yend=None,
        N=None,
        progcall=None,
        reverse=False,
        roll=0,
        with_longevity=False,
        sexes=None,
        seed=None,
    ):
        return run_stochastic_spending(
            self,
            options,
            scenario_method,
            ystart=ystart,
            yend=yend,
            N=N,
            progcall=progcall,
            reverse=reverse,
            roll=roll,
            with_longevity=with_longevity,
            sexes=sexes,
            seed=seed,
        )

    @_checkConfiguration(requireRates=False)
    @_timer
    def runConversionRegret(
        self,
        objective,
        options,
        ystart,
        yend,
        *,
        grid=None,
        person=0,
        include_never_convert=True,
        progcall=None,
        n_grid=19,
        grid_pad=45_000.0,
        n_scenarios=None,
        seed=None,
        milp_downgrade=False,
        on_scenario=None,
    ):
        """
        Measure the regret of committing to a fixed first-year Roth conversion.

        See stresstests.run_conversion_regret_sweep for the full contract. Pass the
        result to stresstests.summarize_conversion_regret to obtain a JSON-ready summary.
        """
        return run_conversion_regret_sweep(
            self,
            objective,
            options,
            grid,
            ystart,
            yend,
            person=person,
            include_never_convert=include_never_convert,
            progcall=progcall,
            n_grid=n_grid,
            grid_pad=grid_pad,
            n_scenarios=n_scenarios,
            seed=seed,
            milp_downgrade=milp_downgrade,
            on_scenario=on_scenario,
        )

    @_checkConfiguration(requireRates=False)
    @_timer
    def runSpendingBequestFrontier(
        self,
        options,
        bequest_grid,
        *,
        scenario_method="historical",
        ystart=None,
        yend=None,
        N=None,
        success_rates=(50.0, 75.0, 90.0),
        seed=None,
        with_duals=False,
        progcall=None,
    ):
        """
        Trace the efficient frontier between net spending and bequest.

        Sweeps the bequest floor under maxSpending. See
        stresstests.run_spending_bequest_frontier for the full contract.
        """
        return run_spending_bequest_frontier(
            self,
            options,
            bequest_grid,
            scenario_method=scenario_method,
            ystart=ystart,
            yend=yend,
            N=N,
            success_rates=success_rates,
            seed=seed,
            with_duals=with_duals,
            progcall=progcall,
        )

    @_checkConfiguration(requireRates=False)
    @_timer
    def runSpendingFrontier(
        self,
        scenario_method,
        *,
        ystart=None,
        yend=None,
        N=None,
        progcall=None,
        reverse=False,
        roll=0,
        with_longevity=False,
        sexes=None,
        seed=None,
        **kwargs,
    ):
        """
        Run the spending efficient frontier over historical or Monte Carlo scenarios.

        Accepts the same solver options as solve() via keyword arguments.  The
        objective is always maxSpending; passing ``netSpending`` raises an error.

        Parameters
        ----------
        scenario_method : str
            "historical" — sweep ``ystart``..``yend``.
            "mc"         — ``N`` Monte Carlo draws.
        ystart, yend : int, optional
            Start/end years for historical mode.
        N : int, optional
            Number of simulations for Monte Carlo mode.
        progcall : Progress, optional
            Progress callback.
        with_longevity : bool, optional
            Draw random lifespans from SSA tables for each scenario.
        sexes : list of str, optional
            Sex of each individual ('M' or 'F').  Required when with_longevity=True.
        seed : int or None, optional
            Random seed for reproducible longevity draws.
        **kwargs
            Solver options forwarded to solve() (e.g. bequest, maxRothConversion,
            withMedicare, solver, withSSTaxability, previousMAGIs).

        Returns
        -------
        dict — see runStochasticSpending for keys.
        """
        if kwargs.get("objective", "maxSpending") != "maxSpending":
            raise ValueError(f"runSpendingFrontier only supports 'maxSpending'; got objective='{kwargs['objective']}'.")
        if "netSpending" in kwargs:
            self.mylog.print("'netSpending' is ignored by runSpendingFrontier (maxSpending objective).", tag="WARNING")
            kwargs.pop("netSpending")
        return run_stochastic_spending(
            self,
            kwargs,
            scenario_method,
            ystart=ystart,
            yend=yend,
            N=N,
            progcall=progcall,
            reverse=reverse,
            roll=roll,
            with_longevity=with_longevity,
            sexes=sexes,
            seed=seed,
        )

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

        # Assume unsuccessful until problem solved.
        self.caseStatus = "unsuccessful"
        self.solverMessage = ""
        self._infeasible = False
        self.convergenceType = "undefined"
        self.solverGap = -1.0
        self.oscillationRel = 0.0
        self.oscillationAbs = 0.0

        # Check objective and required options.
        knownObjectives = ["maxBequest", "maxSpending"]
        knownSolvers = ["default", "HiGHS", "MOSEK"]

        knownOptions = [
            "absTol",
            "bequest",
            "epsilon",
            "gap",
            "maxIter",
            "maxRothConversion",
            "minTaxableBalance",
            "netSpending",
            "noLateSurplus",
            "noRothConversions",
            "oppCostX",
            "previousMAGIs",
            "relTol",
            "residualTol",  # dollars of parameter movement still allowed at convergence
            "solver",
            "spendingSlack",
            "timePreference",  # Subjective time discount rate (%/year) to front-load spending
            "startRothConversions",
            "stopRothConversions",
            "swapRothConverters",
            "maxTime",
            "includeMedicarePartD",  # False drops Part D (and its IRMAA surcharge) from Medicare costs
            "medicarePartDBasePremium",  # Part D base premium, $/month per person (default 0)
            "numThreads",  # cap MOSEK threads/solve (0=all cores) for matched parallelism
            "units",
            "verbose",
            "withACA",  # ACA handling: "loop" (default) or "optimize"
            "withLTCG",  # LTCG handling: "loop" (default) or "optimize"
            "withNIIT",  # NIIT handling: "loop" (default) or "optimize"
            "withMedicare",
            "withSSTaxability",
            "withSSAges",  # SS claiming age: "fixed" (default) or "optimize"
            "withDuals",  # Re-solve final LP with binaries fixed to extract shadow prices
            "withdrawalOrder",  # "optimal" (default) or "taxable_first" (naive ordering gates)
            "mipStrategy",  # "branch-and-bound" (default) or "local-search" for the optimize modes
            "breakpointMethod",  # preset: "loop" (default), "branch-and-bound" or "local-search"
            "localSearchTime",  # local search: total time budget per solve (s)
            "localSearchStepTime",  # local search: time cap per restricted solve (s)
            "localSearchRadius",  # local search: flips allowed on the SS-taxability binaries
            "localSearchStepNodes",  # local search: node limit per restricted solve
            "partialBequestWeight",  # value of a dollar left at the first death (fraction of a dollar)
        ]
        options = {} if options is None else options

        # We might modify options if required.
        myoptions = dict(options)

        for opt in list(myoptions.keys()):
            if opt in REMOVED_OPTIONS:
                raise ValueError(f"Solver option '{opt}' has been removed: {REMOVED_OPTIONS[opt]}.")
            elif opt in RETIRED_OPTIONS:
                self.mylog.print(
                    f"Ignoring deprecated solver option '{opt}': {RETIRED_OPTIONS[opt]}.",
                    tag="WARNING",
                )
                myoptions.pop(opt)
            elif opt not in knownOptions:
                # raise ValueError(f"Option '{opt}' is not one of {knownOptions}.")
                self.mylog.print(f"Ignoring unknown solver option '{opt}'.")
                myoptions.pop(opt)

        if objective not in knownObjectives:
            raise ValueError(f"Objective '{objective}' is not one of {knownObjectives}.")

        self._applyBreakpointOptions(myoptions)
        if self._useLocalSearch(myoptions):
            return self._localSearchSolve(objective, myoptions)

        if objective == "maxBequest" and "netSpending" not in myoptions:
            raise RuntimeError(f"Objective '{objective}' needs netSpending option.")

        if objective == "maxBequest" and "bequest" in myoptions:
            self.mylog.print("Ignoring bequest option provided.")
            myoptions.pop("bequest")

        if objective == "maxSpending" and "netSpending" in myoptions:
            self.mylog.print("Ignoring netSpending option provided.")
            myoptions.pop("netSpending")

        if objective == "maxSpending" and "bequest" not in myoptions:
            self.mylog.vprint("Using bequest of $1.")

        _worder = myoptions.get("withdrawalOrder", "optimal")
        if _worder not in ("optimal", "taxable_first"):
            raise ValueError(f"withdrawalOrder '{_worder}' must be 'optimal' or 'taxable_first'.")

        oppCostX = myoptions.get("oppCostX", 0.0)
        self.xnet = 1 - oppCostX / 100.0

        if int(u.get_numeric_option(myoptions, "swapRothConverters", 0)) != 0 and "noRothConversions" in myoptions:
            self.mylog.print("Ignoring 'noRothConversions' as 'swapRothConverters' option present.", tag="WARNING")
            myoptions.pop("noRothConversions")

        # Go easy on MILP - auto gap somehow.
        if "gap" not in myoptions and myoptions.get("withMedicare", "loop") == "optimize":
            fac = 1
            maxRoth = myoptions.get("maxRothConversion", 100)
            if maxRoth <= 15:
                fac = 10
            # Loosen default MIP gap when Medicare is optimized. Even more if rothX == 0
            gap = fac * MILP_GAP
            myoptions["gap"] = gap
            self.mylog.vprint(f"Using restricted gap of {gap:.1e}.")

        self.prevMAGI = np.zeros(2)
        if "previousMAGIs" in myoptions:
            self.prevMAGI = np.array(u.get_monetary_list_option(myoptions, "previousMAGIs", 2))

        lambdha = myoptions.get("spendingSlack", 0)
        if not (0 <= lambdha <= 50):
            raise ValueError(f"Slack value {lambdha} out of range.")
        self.lambdha = lambdha / 100

        # Reset MAGI to zero.
        self.MAGI_aca_n = np.zeros(self.N_n)
        self.MAGI_n = np.zeros(self.N_n)
        self.J_n = np.zeros(self.N_n)
        self.M_n = np.zeros(self.N_n)
        self.ACA_n = np.zeros(self.N_n)
        self.maca_n = np.zeros(self.N_n)
        self.st_T_n = np.zeros(self.N_n)
        self._aca_lp = False  # Will be set to True in _buildOffsetMap when withACA="optimize"
        self._ltcg_lp = False  # Will be set to True in _buildOffsetMap when withLTCG="optimize"
        self._niit_lp = False  # Will be set to True in _buildOffsetMap when withNIIT="optimize"
        self._ssa_lp = False  # Will be set to True in _buildOffsetMap when withSSAges="optimize"
        self._st_lp = False  # Will be set to True in _buildOffsetMap when state is set
        self._adjustedParameters = False  # Force fresh parameter setup for each solve()
        self._highs_warm_start = None  # MIP warm-start hint; reset each solve(), updated each SC iter
        self._rx_fixed = None  # (tiers zx, free set) kept from a MILP that hit its time limit; see _run_highs
        self._rx_refixed_n = np.zeros(self.N_n, dtype=bool)  # kept tiers moved this iterate
        self._fixedRows = {}  # Rows of the loop-invariant builders, built on the first iteration
        self._dual_data = None  # Shadow prices from binaries-fixed LP re-solve; set when withDuals=True

        # Compute state tax parameters when a state is configured.
        # Note: st_ss_thresh_n (AGI threshold for SS exemption, e.g. KS $75k, MO $100k) is
        # returned but not yet used in the LP — those states are currently treated as binary
        # (SS fully exempt or fully taxed). Full threshold modeling is a known limitation.
        self.N_st = 0
        self.N_lt = 0
        self.lt_surcharge_n = np.zeros(self.N_n)
        self.st_fed_sd_n = np.zeros(self.N_n, dtype=bool)
        self.st_credit_n = np.zeros(self.N_n)
        self.st_recap = None
        self._str_active = False
        self._rx_active = False
        if any(self._states_n()):
            residence_n = self._residence_by_year()
            sp = tax_state.st_schedule(
                [state for state, _ in residence_n],
                self.N_i, self.n_d, self.N_n, self.gamma_n, self.yobs, mobs=self.mobs, i_d=self.i_d,
            )
            lp = tax_local.local_taxParams_schedule(residence_n, self.N_i, self.n_d, self.N_n, self.gamma_n)
            self.N_lt = lp.N_lt
            self.lt_theta_tn = lp.theta_tn
            self.lt_DeltaBar_tn = lp.DeltaBar_tn
            self.lt_surcharge_n = lp.surcharge_n
            self.N_st = sp.N_st
            self.st_theta_tn = sp.theta_tn
            self.st_DeltaBar_tn = sp.DeltaBar_tn
            self._st_sigma_own_n = sp.sigmaBar_n  # before federal-deduction conformity
            self.st_sigmaBar_n = sp.sigmaBar_n.copy()
            self.st_re_cap_in = sp.re_cap_in
            self.st_pe_cap_in = sp.pe_cap_in
            self.st_credit_n = sp.credit_n
            self.st_conv_ok_n = sp.conv_ok_n
            self.st_tax_ss_n = sp.tax_ss_n
            self.st_fed_sd_n = sp.fed_sd_n
            self.st_senior_bonus_n = sp.senior_bonus_n
            self.st_pension_eligible_n = sp.pension_eligible_n
            self.st_recap = (sp.recap_start_n, sp.recap_width_n, sp.recap_until_n)
            self._str_active = bool(np.any(np.isfinite(sp.recap_start_n)))
            self._set_tiered_exclusion(sp)

        # _adjustParameters reads the Part D options from solverOptions: give it this solve's
        # options, not the previous solve's (or those loaded with the case).
        self.solverOptions = myoptions

        # OBBBA 65+ senior-deduction phaseout uses the AGI-basis MAGI (taxable SS only).
        self._adjustParameters(self.gamma_n, self.MAGI_n)
        self._buildOffsetMap(myoptions)

        # Process debts and fixed assets
        self.processDebtsAndFixedAssets()

        solver = myoptions.get("solver", self.defaultSolver)
        if solver == "default":
            solver = "MOSEK" if _mosek_available() else "HiGHS"
        if solver not in knownSolvers:
            raise ValueError(f"Unknown solver '{solver}'.")

        if solver == "HiGHS":
            solverMethod = self._milpSolve
        elif solver == "MOSEK":
            solverMethod = self._mosekSolve
        else:
            raise RuntimeError("Internal error in defining solverMethod.")

        search = getattr(self, "_localSearch", None)
        if search is not None:
            search.use_mosek = solverMethod == self._mosekSolve
            solverMethod = search.solve

        self.mylog.vprint(f"Using '{solver}' solver for optimizing {objective}.")
        myoptions_txt = textwrap.fill(f"{myoptions}", initial_indent="\t", subsequent_indent="\t", width=100)
        self.mylog.vprint(f"Solver options:\n{myoptions_txt}.")
        self._scSolve(objective, myoptions, solverMethod)

        self.objective = objective
        self.solverOptions = myoptions
        self.breakpointMethodUsed = self._breakpointMethodLabel(myoptions)

        return None

    def _breakpointFamilies(self, options):
        """Labels of the tax families this solve carries as binary variables."""
        fams = []
        if options.get("withSSTaxability", "loop") == "optimize":
            fams.append("SS")
        if options.get("withMedicare", "loop") == "optimize":
            fams.append("IRMAA")
        if options.get("withACA", "loop") == "optimize" and self.slcsp_annual > 0:
            fams.append("ACA")
        if options.get("withLTCG", "loop") == "optimize":
            fams.append("LTCG")
        if options.get("withNIIT", "loop") == "optimize":
            fams.append("NIIT")
        return fams

    def _breakpointMethodLabel(self, options, fallback=False):
        """How this solve treated the tax thresholds, for the Summary (always present)."""
        fams = self._breakpointFamilies(options)
        if not fams:
            return "loop"
        if fallback:
            return "local search -> loop"
        method = "local search" if options.get("mipStrategy") == "local-search" else "branch-and-bound"
        return f"{method} ({', '.join(fams)})"

    def _applyBreakpointOptions(self, options):
        """Validate mipStrategy and expand the breakpointMethod preset in place.

        breakpointMethod="branch-and-bound" or "local-search" sets every applicable family to
        "optimize" (Medicare unless it is off, ACA when a benchmark premium is set) and mipStrategy
        to the same value; "loop" changes nothing.
        """
        preset = options.get("breakpointMethod", "loop")
        if preset not in ("loop", "branch-and-bound", "local-search"):
            raise ValueError(f"breakpointMethod '{preset}' must be 'loop', 'branch-and-bound' or 'local-search'.")
        if preset != "loop":
            pinned = options.get("withSSTaxability", "loop")
            if isinstance(pinned, (int, float)) and not isinstance(pinned, bool):
                self.mylog.print(
                    f"breakpointMethod='{preset}' overrides the pinned taxable fraction of Social Security "
                    f"({float(pinned):.2f}): it is now set by the IRS formula.",
                    tag="WARNING",
                )
            options["withSSTaxability"] = "optimize"
            options["withLTCG"] = "optimize"
            options["withNIIT"] = "optimize"
            if options.get("withMedicare", "loop") not in ("none", "None", False):
                options["withMedicare"] = "optimize"
            if self.slcsp_annual > 0:
                options["withACA"] = "optimize"
            options["mipStrategy"] = preset
        strategy = options.get("mipStrategy", "branch-and-bound")
        if strategy not in ("branch-and-bound", "local-search"):
            raise ValueError(f"mipStrategy '{strategy}' must be 'branch-and-bound' or 'local-search'.")

    def _useLocalSearch(self, options):
        """True when this solve should run the local search (not from inside one)."""
        if getattr(self, "_localSearchSeeding", False) or options.get("mipStrategy") != "local-search":
            return False
        if not self._breakpointFamilies(options):
            return False
        blockers = []
        if options.get("withSSAges", "fixed") == "optimize":
            blockers.append('withSSAges="optimize"')
        if options.get("withdrawalOrder", "optimal") == "taxable_first":
            blockers.append('withdrawalOrder="taxable_first"')
        if blockers:
            self.mylog.print(
                f"Local search does not cover {' and '.join(blockers)}: using branch-and-bound.", tag="WARNING"
            )
            options["mipStrategy"] = "branch-and-bound"
            return False
        return True

    def _objectiveValue(self, objective):
        return float(self.g_n[0]) if objective == "maxSpending" else float(self.bequest)

    def _fixedPointResidualTotal(self):
        """Sum over families of the plan's absolute fixed-point residual (today's $)."""
        return sum(v["abs_sum"] for v in (getattr(self, "fixedPointResidual", None) or {}).values())

    def _localSearchSolve(self, objective, myoptions):
        """mipStrategy="local-search": solve the loop first, search from its plan, keep the better.

        The loop's plan is both the seed and the floor: the search starts from it and the
        result is kept only if it beats it. With no feasible starting plan, or no better plan,
        the loop's plan is what the solve returns, and the Summary says so.
        """
        from .localsearch import NoIncumbent

        loop_opts = {k: v for k, v in myoptions.items()
                     if k not in ("mipStrategy", "breakpointMethod", "localSearchTime",
                                  "localSearchStepTime", "localSearchRadius", "localSearchStepNodes")}
        for opt in ("withSSTaxability", "withLTCG", "withNIIT", "withACA"):
            if loop_opts.get(opt) == "optimize":
                loop_opts[opt] = "loop"
        if loop_opts.get("withMedicare") == "optimize":
            loop_opts["withMedicare"] = "loop"

        def run_loop():
            self._localSearchSeeding = True
            try:
                self.solve(objective, options=dict(loop_opts))
            finally:
                self._localSearchSeeding = False

        run_loop()
        if self.caseStatus != "solved":
            self.mylog.print("Local search: the self-consistent loop found no plan to start from.", tag="WARNING")
            self.solverOptions = myoptions
            self.breakpointMethodUsed = self._breakpointMethodLabel(myoptions, fallback=True)
            return None
        floor = self._objectiveValue(objective)
        floor_resid = self._fixedPointResidualTotal()
        # The loop's plan is the floor. Keep it as solved, rather than re-solving on fallback: a
        # second solve starts from state the first one left behind and can settle elsewhere.
        skip = ("mylog",)
        loop_state = copy.deepcopy({k: v for k, v in self.__dict__.items() if k not in skip})
        self.mylog.vprint(f"Local search: the loop's plan is worth {u.d(floor)}; searching from it.")

        self._localSearch = localsearch.LocalSearch(
            self, self.w_ijn.copy(), self.x_in.copy(),
            step_time=u.get_numeric_option(myoptions, "localSearchStepTime", localsearch.STEP_TIME, min_value=0),
            total_time=u.get_numeric_option(myoptions, "localSearchTime", localsearch.TOTAL_TIME, min_value=0),
            radius=int(u.get_numeric_option(myoptions, "localSearchRadius", localsearch.RADIUS, min_value=0)),
            step_nodes=int(u.get_numeric_option(myoptions, "localSearchStepNodes", 0, min_value=0)) or None,
        )
        found = False
        self._localSearchSeeding = True  # the search itself must not recurse
        try:
            self.solve(objective, options=dict(myoptions))
            # On a tie, keep the more consistent plan (smaller fixed-point residual).
            value = self._objectiveValue(objective)
            consistent_tie = value >= floor * (1 - 1e-9) and self._fixedPointResidualTotal() < floor_resid - 1.0
            found = self.caseStatus == "solved" and (value > floor * (1 + 1e-9) or consistent_tie)
        except NoIncumbent:
            self.mylog.print("Local search: no feasible starting plan; keeping the loop's plan.")
        finally:
            self._localSearchSeeding = False
            self.localSearchLog = self._localSearch.log
            self._localSearch = None

        if not found:
            self.mylog.vprint("Local search: no better plan than the loop's; keeping the loop's plan.")
            log = self.localSearchLog
            self.__dict__.update(loop_state)
            self.localSearchLog = log
        self.solverOptions = myoptions
        self.breakpointMethodUsed = self._breakpointMethodLabel(myoptions, fallback=not found)
        return None

    def _build_sc_loop_policy(self, options):
        include_medicare = options.get("withMedicare", "loop") == "loop"
        ss_val = options.get("withSSTaxability", "loop")
        fixed_psi = float(ss_val) if isinstance(ss_val, (int, float)) else None

        # Convergence uses a relative tolerance tied to MILP gap,
        # with an absolute floor to avoid zero/near-zero objectives.
        gap = u.get_numeric_option(options, "gap", GAP, min_value=0)
        abs_tol = u.get_numeric_option(options, "absTol", ABS_TOL, min_value=0)
        rel_default = max(REL_TOL, gap / 300)
        rel_tol = u.get_numeric_option(options, "relTol", rel_default, min_value=0)
        max_iterations = int(u.get_numeric_option(options, "maxIter", MAX_ITERATIONS, min_value=1))
        residual_tol = u.get_numeric_option(options, "residualTol", RESIDUAL_TOL, min_value=0)
        self._residual_tol = residual_tol
        # The version belongs in the log because results move between versions and a captured
        # log is often all that survives: derived big-M bounds changed values, residualTol became
        # a per-year bar and changed where the loop stops, and a retried step changed which cases
        # solve at all -- none of which a saved run says about itself otherwise.
        self.mylog.print(
            f"Owl {__version__} ({engine_commit() or 'no git'}) using relTol={rel_tol:.1e}, "
            f"absTol={abs_tol:.1e}, gap={gap:.1e}, and residualTol={u.d(residual_tol)}/yr."
        )

        return {
            "includeMedicare": include_medicare,
            "fixedPsi": fixed_psi,
            "residualTol": residual_tol,
            "gap": gap,
            "absTol": abs_tol,
            "relTol": rel_tol,
            "maxIter": max_iterations,
        }

    def _new_iteration_trace(self):
        trace = {
            "scaledObjectives": [],
            "solutions": [],
            "objectives": [],
            "gaps": [],
        }
        for name in self._SC_PARAMS:
            trace[f"{name}_lp"] = []
        return trace

    def _valid_history_start(self, includeMedicare):
        # Iteration 0 is built from initial guesses (no premiums, LTCG bracket room with no
        # ordinary income, ...), so it undercharges and its objective looks best.
        return 1

    def _pick_best_valid_index(self, scaled_obj_history, includeMedicare):
        start = self._valid_history_start(includeMedicare)
        valid = scaled_obj_history[start:]
        if not valid:
            # Only iteration 0 solved: a plan still, unless it was built without Medicare premiums.
            return 0 if scaled_obj_history and not includeMedicare else None
        return start + int(np.argmax(valid))

    def _check_obj_convergence(self, it, abs_obj_diff, tol, includeMedicare, scaled_obj_history, residual=0.0):
        """Converged when the objective has settled AND the quantities the loop feeds back have too.

        The objective alone is not enough: the LP is built from the previous iterate's Medicare
        premiums, SS taxable fraction, NIIT, ACA costs and LTCG bracket room, so an iterate whose
        own income implies different values is not a fixed point, however still the objective looks. `residual` is the
        largest of those disagreements, summed over the horizon in today's dollars; residualTol is
        the bar it must clear, expressed per year so that it means the same thing on a short plan
        as on a long one.
        """
        if abs_obj_diff > tol or (includeMedicare and it < 1):
            return None
        if residual / self.N_n > self._residual_tol:
            return None

        is_monotonic = all(
            scaled_obj_history[i] <= scaled_obj_history[i - 1] + tol for i in range(1, len(scaled_obj_history))
        )
        convergence_type = "monotonic" if is_monotonic else "oscillatory"
        return {
            "reason": "converged",
            "convergenceType": convergence_type,
            "message": f"Converged on full solution with {convergence_type} behavior.",
        }

    def _check_cycle(self, it, scaled_obj_history, tol):
        # Need at least 4 iterations to detect a 2-cycle.
        if it < 3:
            return None
        cycle_len = u.detect_oscillation(scaled_obj_history, tol)
        if cycle_len is None:
            return None
        cycle_values = scaled_obj_history[-cycle_len:]
        best_idx = int(np.argmax(cycle_values))
        return {
            "reason": "cycle",
            "cycleLength": cycle_len,
            "cycleOffset": best_idx,
            "bestScaledObjective": cycle_values[best_idx],
            "convergenceType": f"oscillatory (cycle length {cycle_len})",
        }

    def _check_stagnation(self, it, scaled_obj_history, gap_history, includeMedicare):
        if it < 3:
            return None
        start = self._valid_history_start(includeMedicare)
        valid = scaled_obj_history[start:]
        valid_gaps = gap_history[start:]
        if len(valid) <= STAGNATION_WINDOW:
            return None
        recent_gaps = valid_gaps[-STAGNATION_WINDOW:]
        n_timeouts = sum(1 for g in recent_gaps if not np.isfinite(g))
        if n_timeouts < STAGNATION_TIMEOUTS:
            return None
        best_before_window = max(valid[:-STAGNATION_WINDOW])
        recent_best = max(valid[-STAGNATION_WINDOW:])
        if recent_best > best_before_window:
            return None
        return {
            "reason": "stagnation",
            "timeoutCount": n_timeouts,
            "convergenceType": "oscillatory (stagnation)",
            "message": (
                f"Stagnation detected: {n_timeouts}/{STAGNATION_WINDOW} solver timeouts "
                "with no improvement. Accepting best solution."
            ),
            "tag": "WARNING",
        }

    def _check_max_iterations(self, it, max_iterations):
        if it < max_iterations:
            return None
        return {
            "reason": "max_iter",
            "convergenceType": "max iteration",
            "message": "Exiting loop on maximum iterations.",
            "tag": "WARNING",
        }

    def _netSurplusRoundTrip(self):
        """Report the surplus and the taxable withdrawal net of the round-trip between them.

        A surplus is deposited straight back into the taxable account it may have just been
        withdrawn from, so the gross figures describe a movement that never happens. When
        the optimizer is indifferent to that round-trip — which is precisely when it occurs,
        since a round-trip that costs anything is never chosen — it can leave an arbitrary
        amount of it in the solution. Reporting the net is both truthful and stable.

        The cash flow identity is unaffected: the surplus sits on its left-hand side and the
        deposit is part of the withdrawals on its right, so cancelling the two removes the
        same amount from both. Balances, taxes, spending and the bequest are untouched.

        Years whose capital gains reach a taxed bracket are left gross, so that a displayed
        withdrawal always explains the capital-gains tax displayed beside it.
        """
        taxed_gains_n = self.q_pn[1, :] + self.q_pn[2, :]
        for n in range(self.N_n):
            if self.s_n[n] <= 0.01 or taxed_gains_n[n] > 1.0:
                continue
            for i in range(self.N_i):
                delta = min(self.d_in[i, n], self.w_ijn[i, 0, n], self.s_n[n])
                if delta <= 0.01:
                    continue
                self.w_ijn[i, 0, n] -= delta
                self.d_in[i, n] -= delta
                self.s_n[n] -= delta

    def _check_cashflow_balance(self, atol=1.0):
        """Verify the LP cash flow identity holds on the aggregated post-solve arrays.

        Any residual larger than atol (dollars) indicates a term is missing or
        double-counted in _aggregateResults — logged as a warning, never raised.
        """
        lhs = (
            self.g_n
            + self.s_n
            + self.T_n
            + self.U_n
            + self.J_n
            + self.st_T_n
            + self.medicare_n
            + self.aca_costs_n
            + self.debt_payments_n
        )
        rhs = (
            np.sum(self.omega_in, axis=0)
            + np.sum(self.other_inc_in, axis=0)
            + np.sum(self.netinv_in, axis=0)
            + np.sum(self.zetaBar_in, axis=0)
            + np.sum(self.piBar_in, axis=0)
            + np.sum(self.spiaBar_in, axis=0)
            + np.sum(self.Lambda_in, axis=0)
            + self.fixed_assets_ordinary_income_n
            + self.fixed_assets_capital_gains_n
            + self.fixed_assets_tax_free_n
            + np.sum(self.w_ijn, axis=(0, 1))
        )
        residual = np.max(np.abs(lhs - rhs))
        if residual > atol:
            self.mylog.print(
                f"Cash flow balance off by ${residual:,.0f} (max over all years). "
                "A term may be missing or double-counted in the post-solve output.",
                tag="WARNING",
            )

    def _effective_cap_gain_coef(self, i, n):
        """Gain fraction for w[i,0,n]: uses tracked basis if available, else current-year appreciation.
        For n=0, n-1 wraps to -1 (Python semantics), matching the np.roll(tau_0,1) convention used
        in _configure_ltcg_constraints and _aggregateResults."""
        if self.gain_fraction_in is not None and not np.isnan(self.gain_fraction_in[i, n]):
            return self.gain_fraction_in[i, n]
        tau_prev = self.tau_kn[0, n - 1]  # n=0 → tau_kn[0,-1] (last rate), matches roll convention
        return max(0.0, tau_prev - self.mu)

    def _init_gain_fraction(self):
        """Initialize gain_fraction_in from user-supplied cost basis before first LP solve.
        Zero basis for an individual means 'use legacy approximation for that person' (NaN sentinel).
        """
        if self.taxable_basis_i is None:
            self.gain_fraction_in = None
            return
        self.gain_fraction_in = np.full((self.N_i, self.N_n), np.nan)
        for i in range(self.N_i):
            if self.taxable_basis_i[i] == 0:
                continue  # NaN → legacy fallback for this person
            b0 = self.beta_ij[i, 0]
            alpha0 = self.alpha_ijkn[i, 0, 0, 0]
            self.gain_fraction_in[i, :] = self._equity_gain_fraction(self.taxable_basis_i[i], b0, alpha0)

    def _update_gain_fraction(self):
        """Update gain_fraction_in using last SC-iteration balances and withdrawals.
        Both fixed contributions (kappa) and LP surplus deposits (d_in) add to basis at full value
        because they are new purchases at the current market price. So do the dividends and the
        bond/cash returns taxed each year, which stay in the account and are reinvested: leaving
        them out would tax them a second time on sale.
        Persons with zero basis are skipped (their NaN entries mean legacy fallback)."""
        if self.gain_fraction_in is None:
            return
        # Same yield the model taxes each year as dividends and interest (see _add_taxable_income).
        fak_in = np.sum(np.maximum(0, self.tau_kn[1:, :]) * self.alpha_ijkn[:, 0, 1:, : self.N_n], axis=1)
        for i in range(self.N_i):
            if self.taxable_basis_i[i] == 0:
                continue  # stays NaN → legacy
            basis = float(self.taxable_basis_i[i])
            for n in range(self.N_n):
                b_n = self.b_ijn[i, 0, n]
                w_n = self.w_ijn[i, 0, n]
                d_n = self.d_in[i, n]
                kappa_n = self.kappa_ijn[i, 0, n]
                alpha0 = self.alpha_ijkn[i, 0, 0, n]
                # New purchases: fixed HFP contributions + LP-decided surplus deposits (both at full basis).
                c_n = kappa_n + d_n
                # Reinvested income taxed this year: dividends on equities, all positive returns on the rest.
                taxed_n = (self.mu * alpha0 + fak_in[i, n]) * (b_n - w_n + d_n + 0.5 * kappa_n)
                self.gain_fraction_in[i, n] = self._equity_gain_fraction(basis, b_n, alpha0)
                if b_n > 0:
                    basis = basis * (1.0 - w_n / b_n) + c_n + max(0.0, taxed_n)
                else:
                    basis = c_n + max(0.0, taxed_n)

    def _scSolve(self, objective, options, solverMethod):
        """
        Self-consistent loop, regardless of solver.
        """
        policy = self._build_sc_loop_policy(options)
        includeMedicare = policy["includeMedicare"]
        fixed_psi = policy["fixedPsi"]
        abs_tol = policy["absTol"]
        rel_tol = policy["relTol"]
        max_iterations = policy["maxIter"]

        # Objective reporting scale; zero deflators would divide by zero.
        _tiny = 1e-30
        if objective == "maxSpending":
            den = float(self.xi_n[0])
            if abs(den) < _tiny:
                raise ValueError(
                    "maxSpending objective scaling failed: xi_n[0] (first-year nominal discount) is "
                    "effectively zero. Check plan horizon and inflation series."
                )
            objFac = -1.0 / den
        else:
            den = float(self.gamma_n[-1])
            if abs(den) < _tiny:
                raise ValueError(
                    "Objective scaling failed: gamma_n[-1] (terminal nominal discount) is effectively "
                    "zero. Check plan horizon and inflation series."
                )
            objFac = -1.0 / den

        it = 0
        old_x = np.zeros(self.nvars)
        trace = self._new_iteration_trace()
        # Which backend the helper solves (_run_mip, _run_lp_with_duals) should use. Compare on
        # __func__ so a bound method's identity does not matter.
        is_mosek = getattr(solverMethod, "__func__", None) is Plan._mosekSolve
        solverName = "MOSEK" if is_mosek else "HiGHS"
        self._use_mosek = is_mosek

        self._computeNLstuff(None, includeMedicare, fixedPsi=fixed_psi)
        self._init_gain_fraction()
        self._tax_tiebreak_on = False
        sc_lp = self._snapshot_sc()
        while True:
            # Snapshot the NL parameters actually embedded in this iteration's LP constraints.
            # _buildConstraints runs inside the solver call below, so these are the values it
            # embeds. Psi_n belongs here for the same reason as the other three: the taxable
            # income row carries Psi_n * zetaBar as a parameter.
            sc_lp = self._snapshot_sc()
            objfn, xx, solverSuccess, solverMsg, solgap = solverMethod(objective, options)
            # self.A/B/c now describe the LP that produced this xx. Accepting an earlier
            # iterate below breaks that correspondence, which post-processing relies on.
            matricesMatchSolution = True
            # Achieved MIP gap of the accepted solution (-1 for pure LP solves);
            # corrected below when a best-of-cycle iterate is accepted instead.
            self.solverGap = solgap

            if (not solverSuccess or objfn is None) and trace["solutions"]:
                # Before giving up, walk the parameter step back. The quantities the loop feeds
                # back are costs, and the first one is a jump from nothing to the full amount:
                # on a tight case that step alone can put the next LP outside the feasible
                # region, so the loop reports that no plan exists when one does. Retrying with a
                # shorter move recovers it. Damping every step by a fixed weight does not: the
                # outcome is chaotic in the weight (0.4 and 0.7 break a case that 0.3, 0.5, 0.6
                # and 0.8 all solve), because a weight only changes which cases land in the hole.
                # Retrying only on failure costs nothing on the cases that never fail.
                prev = self._sc_trace_entry(trace)
                target = self._snapshot_sc()
                for frac in (0.5, 0.25, 0.125, 0.0625):
                    self._blend_sc(prev, target, frac)
                    sc_lp = self._snapshot_sc()
                    objfn, xx, solverSuccess, solverMsg, solgap = solverMethod(objective, options)
                    if solverSuccess and objfn is not None:
                        self.solverGap = solgap
                        self._infeasible = False
                        self.mylog.vprint(
                            f"Iteration {it} was unsolvable; recovered with {frac:.3g} of the "
                            "parameter step."
                        )
                        break
                else:
                    self._restore_sc(target)

            if not solverSuccess or objfn is None:
                # A parameter update can hand the solver a problem it cannot take - most often
                # a MAGI that crossed an IRMAA threshold, so the premiums jump and a spending
                # floor no longer fits. The earlier iterates are still valid plans, so falling
                # back to the best of them beats discarding the run: the alternative reports a
                # feasible case as infeasible, which is what a converging sequence
                # (|df| shrinking to a few hundred dollars) followed by one bad step used to do.
                # Mirrors the cycle and stagnation exits, which accept an earlier iterate the
                # same way.
                best_idx = self._pick_best_valid_index(trace["scaledObjectives"], includeMedicare)
                if best_idx is None:
                    # Nothing ever solved, so the case really is infeasible.
                    self.caseStatus = "infeasible" if self._infeasible else "solver error"
                    self.solverMessage = _failureMessage(self._infeasible, solverName, solverMsg)
                    self.mylog.print(self.solverMessage, tag="WARNING" if self._infeasible else "ERROR")
                    break
                self.mylog.print(
                    f"Iteration {it} could not be solved ({'infeasible' if self._infeasible else 'solver error'}); "
                    f"accepting the best of the {len(trace['solutions'])} iterate(s) before it.",
                    tag="WARNING",
                )
                xx = trace["solutions"][best_idx]
                objfn = trace["objectives"][best_idx]
                sc_lp = self._sc_trace_entry(trace, best_idx)
                self.solverGap = trace["gaps"][best_idx]
                matricesMatchSolution = False
                self.convergenceType = "unsolvable iterate"
                solverSuccess = True
                solverMsg = ""
                self._infeasible = False
                break

            if self._tax_tiebreak_on:
                # Report the objective without the tie-break, so iterates compare on the same terms.
                objfn -= TAX_TIEBREAK * float(np.dot(self._tax_cost_vector(), xx))
            elif self._bracket_order_excess(xx)[0]:
                self._tax_tiebreak_on = True
                self.mylog.vprint(f"Iteration {it} filled tax brackets out of order; pricing tax from now on.")

            self._computeNLstuff(xx, includeMedicare, fixedPsi=fixed_psi)
            self._update_gain_fraction()

            delta = xx - old_x
            # Only consider account balances in dX.
            absSolDiff = np.sum(np.abs(delta[: self.nbals]), axis=0) / self.nbals
            scaled_obj = objfn * objFac
            trace["scaledObjectives"].append(scaled_obj)
            trace["solutions"].append(xx)
            trace["objectives"].append(objfn)
            trace["gaps"].append(solgap)
            self._sc_trace_append(trace, sc_lp)

            # How far this iterate's own income moves the quantities its LP was built with. The
            # parameters were snapshotted before the solve; _computeNLstuff has just recomputed them.
            g_today = self.gamma_n[: self.N_n]
            ss_n = np.sum(self.zetaBar_in, axis=0)
            # Psi_n carries a damping blend, so it understates the disagreement; the IRS formula on
            # this iterate's own provisional income is what the next LP would have to charge.
            psi_implied = (
                self.Psi_n
                if fixed_psi is not None or "tss" in self.vm
                else tx.compute_social_security_taxability(self.N_i, self.MAGI_aca_n, ss_n, n_d=self.n_d)
            )
            moves = [np.sum(np.abs(psi_implied - sc_lp["Psi_n"]) * ss_n / g_today)]
            for _name, _active in (
                ("J_n", True), ("M_n", includeMedicare), ("ACA_n", self.slcsp_annual > 0), ("STR_n", self._str_active)
            ):
                if _active:
                    moves.append(np.sum(np.abs(getattr(self, _name) - sc_lp[_name]) / g_today))
            # LTCG bracket room is set from the previous iterate's ordinary income, so the LP's
            # gains tax can disagree with the tax this iterate's own income implies.
            moves.append(np.sum(np.abs(self.U_n - self._ltcg_tax_implied()) / g_today))
            # Years newly admitted to the exclusion's free set: the next LP can claim up to the cap there.
            if self._rx_active:
                added = (self.RXF_n >= 0.5) & (sc_lp["RXF_n"] < 0.5)
                moves.append(np.sum(self.st_rx_cap_n[added] / g_today[added]))
                # Years whose kept tier moved down to the statute's (_refix_boundary_tiers): the next LP
                # can claim more there, so this iterate is not a fixed point.
                refixed = self._rx_refixed_n
                moves.append(np.sum(self.st_rx_cap_n[refixed] / g_today[refixed]))
            scResidual = float(max(moves))

            has_prev_obj = len(trace["scaledObjectives"]) > 1
            prev_scaled_obj = trace["scaledObjectives"][-2] if has_prev_obj else scaled_obj
            absObjDiff = abs(scaled_obj - prev_scaled_obj) if has_prev_obj else np.inf
            self.mylog.vprint(
                f"Iter: {it:02}; f: {u.d(scaled_obj, f=0)}; gap: {solgap:.1e};"
                f" |dX|: {absSolDiff:.0f}; |df|: {u.d(absObjDiff, f=0)}; residual: {u.d(scResidual, f=0)}"
            )

            # Solution difference is calculated and reported but not used for convergence
            # since it scales with problem size and can prevent convergence for large cases.
            scale = max(1.0, abs(scaled_obj), abs(prev_scaled_obj))
            tol = max(abs_tol, rel_tol * scale)
            decision = self._check_obj_convergence(
                it, absObjDiff, tol, includeMedicare, trace["scaledObjectives"], scResidual
            )
            if decision is None:
                decision = self._check_cycle(it, trace["scaledObjectives"], tol)
            if decision is None:
                decision = self._check_stagnation(it, trace["scaledObjectives"], trace["gaps"], includeMedicare)
            if decision is None:
                decision = self._check_max_iterations(it, max_iterations)

            if decision is not None:
                self.convergenceType = decision["convergenceType"]
                # Oscillation amplitude for the error bar: relative spread (max-min)/max of
                # the recent scaled objectives when the loop did NOT converge — i.e. it is
                # genuinely stuck cycling (reason "cycle") or never settled ("stagnation"/
                # "max_iter"). A "converged" result (monotonic OR oscillatory-approach) has
                # settled within tolerance, so its amplitude is ~0; only unresolved fixed-
                # point ambiguity gets an error bar. Cross-solver cannot see this within-run
                # source. Uses the detected cycle length when available.
                if decision["reason"] != "converged":
                    _win = max(int(decision.get("cycleLength", 4)), 2)
                    _recent = trace["scaledObjectives"][-_win:]
                    _lo, _hi = float(min(_recent)), float(max(_recent))
                    # scaledObjectives are objfn*objFac, i.e. the modified objective in
                    # today's dollars; the raw spread is the error bar in those units.
                    self.oscillationAbs = _hi - _lo
                    self.oscillationRel = self.oscillationAbs / max(abs(_hi), 1e-9)
                best_idx = None
                if decision["reason"] == "cycle":
                    cycle_len = decision["cycleLength"]
                    best_obj = decision["bestScaledObjective"]
                    cycle_offset = decision["cycleOffset"]
                    self.mylog.print(f"Oscillation detected: {cycle_len}-cycle pattern identified.")
                    self.mylog.print(f"Best objective in cycle: {u.d(best_obj, f=2)}")
                    best_idx = len(trace["scaledObjectives"]) - cycle_len + cycle_offset
                    xx = trace["solutions"][best_idx]
                    objfn = trace["objectives"][best_idx]
                    sc_lp = self._sc_trace_entry(trace, best_idx)
                    self.solverGap = trace["gaps"][best_idx]
                    matricesMatchSolution = False
                    self.mylog.print("Accepting best solution from cycle and terminating.")
                elif decision["reason"] in ("stagnation", "max_iter"):
                    self.mylog.print(decision["message"], tag=decision.get("tag", "INFO"))
                    best_idx = self._pick_best_valid_index(trace["scaledObjectives"], includeMedicare)
                    if best_idx is not None:
                        xx = trace["solutions"][best_idx]
                        objfn = trace["objectives"][best_idx]
                        sc_lp = self._sc_trace_entry(trace, best_idx)
                        self.solverGap = trace["gaps"][best_idx]
                        matricesMatchSolution = False
                else:
                    self.mylog.print(decision["message"], tag=decision.get("tag", "INFO"))
                # Consistency solve: LTCG bracket room (room15_n, room20_n) is built from the
                # *previous* iteration's G_n (one-step lag). Re-solve until U_n <= 20% * Q_n or
                # passes are exhausted; any residual degeneracy still surfaces via the
                # "may be degenerate" warning in _aggregateResults.
                if not getattr(self, "_ltcg_lp", False):
                    max_passes = LTCG_CONSISTENCY_MAX_PASSES
                    _ltcg_passes = 0
                    for _ltcg_pass in range(max_passes):
                        self._computeNLstuff(xx, includeMedicare=False, fixedPsi=fixed_psi)
                        max_excess = float(np.max(self.U_n - 0.20 * np.maximum(self.Q_n, 0)))
                        if max_excess <= LTCG_CONSISTENCY_TOL:
                            break
                        sc_lp = self._snapshot_sc()
                        _, xx_fix, fix_ok, _, _ = solverMethod(objective, options)
                        if not fix_ok or xx_fix is None:
                            break
                        xx = xx_fix
                        matricesMatchSolution = True
                        _ltcg_passes += 1
                    if _ltcg_passes:
                        self.mylog.vprint(f"Performed LTCG consistency solve ({_ltcg_passes} pass(es)).")
                break

            it += 1
            old_x = xx

        if solverSuccess:
            self.mylog.print(f"Self-consistent loop returned after {it + 1} iterations.")
            if solverMsg:
                self.mylog.print(solverMsg)
            # The free set the accepted iterate was built with, before anything rebuilds the LP.
            self.RXF_n = sc_lp["RXF_n"]
            if self._rx_fixed is not None:
                # The tiers came from a MILP stopped at its time limit; later solves only kept them, so
                # that MILP's gap is the one that says how far the plan may be from optimal.
                self.solverGap = max(self.solverGap, self._rx_fixed[2])
            xx, objfn = self._repairBracketOrder(xx, objfn, objective, options, matricesMatchSolution)
            xx, objfn = self._restoreExclusions(xx, objfn, objective, options, matricesMatchSolution)
            self.mylog.print(f"Objective: {u.d(objfn * objFac)}")
            # Psi_n is restored BEFORE aggregation, unlike the three below: MAGI_aca_n is
            # defined as MAGI_n + (1 - Psi_n) * zetaBar, and MAGI_n already carries the
            # taxable share the LP charged. The two cancel only when both use the same
            # Psi_n, so aggregating with a Psi_n the loop had already advanced left
            # MAGI_aca_n wrong by exactly that step. In optimize mode Psi_n is derived from
            # the tss variable during aggregation and is consistent already, so leave it.
            if "tss" not in self.vm:
                self.Psi_n = sc_lp["Psi_n"]
            self._aggregateResults(xx)
            # Restore the NL parameters to what was actually embedded in the final LP
            # constraints. _computeNLstuff runs after every LP solve (for convergence
            # checking), so self.M_n / J_n / ACA_n hold values derived from the final
            # solution's MAGI — one step ahead of what the LP was built with. Restoring
            # them makes the plan's attributes LP-consistent: the cash flow balance holds
            # exactly on p.M_n / p.J_n / p.ACA_n without any post-hoc correction.
            # Only applies to loop-mode quantities (LP-mode variants are already extracted
            # from solver variables and are always consistent).
            if includeMedicare:
                self.M_n = sc_lp["M_n"]
                hsa_total = np.sum(self.w_ijn[:, 3, :], axis=0)
                self.hsa_medicare_n = np.minimum(hsa_total, self.medicare_n)
            if not getattr(self, "_niit_lp", False):
                self.J_n = sc_lp["J_n"]
            if self.slcsp_annual > 0 and not self._aca_lp:
                self.ACA_n = sc_lp["ACA_n"]
            self.STR_n = sc_lp["STR_n"]
            self._finalize_state_tax()
            self._check_cashflow_balance()
            self._check_bracket_order()
            self._computeFixedPointResidual(includeMedicare)
            if options.get("withDuals", False):
                self._computeDuals(xx, options)
            self._timestamp = datetime.now().strftime("%Y-%m-%d at %H:%M:%S")
            self.caseStatus = "solved"
        else:
            # caseStatus and solverMessage were set where the loop gave up, which is the
            # only place that knows what the solver said.
            self.mylog.print(f"Optimization failed: case is {self.caseStatus}.", tag="WARNING")

        return None

    def _state_agi_and_ti(self):
        """State AGI and taxable income of the current solution, per year.

        AGI is federal AGI less the Social Security the state exempts, the pension exemption
        and the retirement exclusion claimed: the same terms the state_taxable_income row uses.
        The income-tiered exclusion (st_rx) is not subtracted: its tiers are set on this amount.
        """
        if self.N_st == 0:
            return np.zeros(self.N_n), np.zeros(self.N_n)
        ti = np.sum(self.st_f_tn, axis=0)
        ss_excl = np.where(self.st_tax_ss_n, 0.0, self.Psi_n * np.sum(self.zetaBar_in, axis=0))
        pe_adj = np.sum(np.minimum(self.piBar_in, self.st_pe_cap_in), axis=0)
        agi = self.G_n + self.e_n + self.Q_n - ss_excl - pe_adj - np.sum(self.st_re_in, axis=0)
        return agi, ti

    def _set_tiered_exclusion(self, sp):
        """Per-year eligibility for the income-tiered retirement exclusion (NJ-1040 line 28).

        A filer's income is eligible from the year they reach the age by December 31, while alive.
        The other-income extension needs every living filer eligible and wages within the limit;
        with one spouse too young only line 28a is taken, which understates the exclusion.
        """
        Ni, Nn = self.N_i, self.N_n
        self.st_rx_limit_kn = sp.rx_limit_kn
        self.st_rx_share_kn = sp.rx_share_kn
        self.st_rx_cap_n = sp.rx_cap_n
        self._rx_active = bool(np.any(sp.rx_cap_n > 0))
        alive_in = np.array([[n < self.horizons[i] for n in range(Nn)] for i in range(Ni)])
        age_in = self.year_n[np.newaxis, :] - np.asarray(self.yobs)[:, np.newaxis]
        self.st_rx_elig_in = alive_in & (age_in >= sp.rx_age_n[np.newaxis, :]) & (sp.rx_cap_n > 0)
        wages_n = np.sum(self.omega_in, axis=0)
        all_elig_n = np.all(self.st_rx_elig_in | ~alive_in, axis=0) & self.st_rx_elig_in.any(axis=0)
        self.st_rx_other_n = all_elig_n & (sp.rx_earned_n >= 0) & (wages_n <= sp.rx_earned_n)

    def _tiered_exclusion_free(self):
        """Free set for the next iterate: the current one plus the eligible years whose state income is
        at most RX_WINDOW times the top tier ceiling. It only grows, so the previous iterate stays
        feasible; the loop does not converge while it changes (see _scSolve), so at convergence every
        year left out has income far above the last ceiling, where the statute excludes nothing.
        """
        if not self._rx_active:
            return self.RXF_n
        top_n = np.max(np.where(np.isfinite(self.st_rx_limit_kn), self.st_rx_limit_kn, 0.0), axis=0)
        near = self.st_rx_elig_in.any(axis=0) & (self.st_agi_n <= RX_WINDOW * top_n) & (top_n > 0)
        return np.where(near, 1.0, np.where(self.RXF_n >= 0.5, 1.0, 0.0))

    def _refix_boundary_tiers(self):
        """Move a kept exclusion tier down to the statute's tier when income sits on its floor.

        Tiers kept from a MILP stopped at its time limit (_rx_fixed) pin the tier binaries, and a pinned
        tier bounds income from below as well as above. A later iterate that wants less income stops on
        the floor of its tier, which is the ceiling of the tier below, and the statute ("income of the
        ceiling or less") puts exactly that income in the tier below, with the larger share. Left alone,
        the plan claims the smaller share there and is held at that income for it.

        Only downward moves at the same income are made: the iterate stays feasible, a larger share can
        only lower tax, and a tier never moves back up, so this cannot cycle. Returns the years moved.
        """
        moved = np.zeros(self.N_n, dtype=bool)
        if self._rx_fixed is None or not self._rx_active:
            return moved
        zx_kept, kept_n = self._rx_fixed[0], self._rx_fixed[1]
        K = self.st_rx_limit_kn.shape[0]
        total_n = np.round(self.st_agi_n)  # line 27, in the whole dollars of the return
        for n in range(self.N_n):
            if not kept_n[n] or not zx_kept[n].any():
                continue
            k_kept = int(np.argmax(zx_kept[n]))
            k_statute = K
            for k in range(K):
                if np.isfinite(self.st_rx_limit_kn[k, n]) and total_n[n] <= self.st_rx_limit_kn[k, n]:
                    k_statute = k
                    break
            if k_statute < k_kept:
                zx_kept[n, :] = 0.0
                zx_kept[n, k_statute] = 1.0
                moved[n] = True
        if moved.any():
            years = ", ".join(str(int(y)) for y in self.year_n[moved])
            self.mylog.vprint(f"Kept exclusion tier moved down to the statute's for income on its floor: {years}.")
        return moved

    def _tiered_exclusion_implied(self):
        """Share and amount of the tiered exclusion that the solution's own income implies (a check).

        Returns (share_n, amount_n). The amount is what the return would claim: the share of eligible
        income (or of total income, with the other-income extension), up to the cap and the income.
        """
        Nn = self.N_n
        share = np.zeros(Nn)
        amount = np.zeros(Nn)
        if not self._rx_active:
            return share, amount
        total_n = np.round(self.st_agi_n)  # line 27, in the whole dollars of the return
        for n in range(Nn):
            if self.st_rx_cap_n[n] <= 0:
                continue
            share[n] = tax_state.exclusion_share(total_n[n], self.st_rx_limit_kn[:, n], self.st_rx_share_kn[:, n])
            elig = self.st_rx_elig_in[:, n]
            if self.st_rx_other_n[n]:
                base = total_n[n]
            else:
                base = float(np.sum((self.w_ijn[:, 1, n] + self.x_in[:, n] + self.piBar_in[:, n]
                                     + self.spiaBar_in[:, n])[elig]))
            amount[n] = min(self.st_rx_cap_n[n], share[n] * base, max(0.0, total_n[n]))
        return share, amount

    def _state_recapture_implied(self):
        "Benefit recapture the current solution's own state AGI and taxable income imply."
        STR = np.zeros(self.N_n)
        if not self._str_active:
            return STR
        start, width, until = self.st_recap
        for n in range(self.N_n):
            if np.isfinite(start[n]):
                STR[n] = tax_state.state_recapture(
                    self.st_agi_n[n], self.st_ti_n[n], self.st_theta_tn[:, n], self.st_DeltaBar_tn[:, n],
                    start[n], width[n], until[n],
                )
        return STR

    def _finalize_state_tax(self):
        """Assemble state, recapture and local tax from the pieces of the last aggregation.

        st_T_n is the total sub-federal income tax, so cash-flow identities hold without knowing
        about recapture or localities; st_recap_n and lt_T_n are its parts. A local surcharge is a
        share of the state tax including the recapture.
        """
        Nn = self.N_n
        if self.N_st > 0:
            self.st_T_tn = self.st_f_tn * self.st_theta_tn
            # Personal credits (st_c) come off the state tax, recapture included, down to zero.
            state = np.sum(self.st_T_tn, axis=0) + self.STR_n - self.st_c_n
        else:
            state = np.zeros(Nn)
        self.st_recap_n = self.STR_n.copy() if self.N_st > 0 else np.zeros(Nn)
        self.lt_T_n = self.lt_surcharge_n * state
        if self.N_lt > 0:
            self.lt_T_n = self.lt_T_n + np.sum(self.lt_f_tn * self.lt_theta_tn, axis=0)
        self.st_T_n = state + self.lt_T_n

    def _ltcg_tax_implied(self):
        """Capital-gains tax the plan's own ordinary income and gains imply, stacked exactly."""
        Nn = self.N_n
        return tx.capitalGainTax(self.N_i, self.G_n + self.Q_n, self.Q_n, self.gamma_n[:Nn], self.n_d, Nn)

    def _fixedPointResidualByYear(self, includeMedicare):
        """Per-year disagreements behind _computeFixedPointResidual: {family: array (today's $)}."""
        Nn = self.N_n
        g = self.gamma_n[:Nn]
        ss = np.sum(self.zetaBar_in, axis=0)
        res = {}

        psi_true = tx.compute_social_security_taxability(self.N_i, self.MAGI_aca_n, ss, n_d=self.n_d)
        res["SS"] = (self.Psi_n - psi_true) * ss / g

        if includeMedicare or np.any(self.medicare_n > 0):
            # A dollar of slack at the thresholds: the optimizer parks income exactly there, and
            # cent-level rounding would otherwise flip a bracket and show a phantom residual.
            M_true = tx.mediCosts(
                self.yobs, self.horizons, self.MAGI_n - 1.0, self.prevMAGI, g, Nn,
                include_part_d=getattr(self, "_include_medicare_part_d", True),
                part_d_base_annual_per_person=getattr(self, "_medicare_part_d_base_annual_per_person", 0.0),
            )
            res["IRMAA"] = (self.medicare_n - M_true) / g

        if self.slcsp_annual > 0:
            # Same dollar of slack: an optimizer parks income at the 400% cliff or the 138% line.
            n_aca_start = max(0, self.aca_start_year - int(self.year_n[0])) if self.aca_start_year > 0 else 0
            ACA_true = tx.acaCosts(self.yobs, self.horizons, self.MAGI_aca_n - 1.0, g, self.slcsp_annual, Nn,
                                   n_aca_start=n_aca_start)
            res["ACA"] = (self.aca_costs_n - ACA_true) / g

        res["NIIT"] = (self.J_n - tx.computeNIIT(self.N_i, self.MAGI_n, self.I_n, self.Q_n, self.n_d, Nn)) / g

        sigma_true = tx.taxParams(self.yobs, self.i_d, self.n_d, Nn, self.gamma_n, self.MAGI_n, self.yOBBBA)[0]
        res["deduction"] = (self.sigmaBar_n - sigma_true) / g

        res["LTCG"] = (self.U_n - self._ltcg_tax_implied()) / g
        if self._str_active:
            res["state recapture"] = (self.STR_n - self._state_recapture_implied()) / g
        return res

    def _computeFixedPointResidual(self, includeMedicare):
        """Measure how far the solved plan sits from the model its own income implies.

        Every quantity the self-consistent loop carries enters the LP as a constant taken from the
        previous iterate. The loop stops on the objective, not on those constants, so a plan can be
        reported while its own income would still move them -- and an "optimal" answer is only
        optimal for the model that was built. This recomputes each of them from the returned plan
        and records the difference, in today's dollars, as self.fixedPointResidual:
        {family: {"sum", "abs_sum", "max_abs"}}. Purely diagnostic: nothing here changes a solution.
        """
        res = self._fixedPointResidualByYear(includeMedicare)

        self.fixedPointResidual = {
            k: {"sum": float(np.sum(v)), "abs_sum": float(np.sum(np.abs(v))), "max_abs": float(np.max(np.abs(v)))}
            for k, v in res.items()
        }
        worst = max(self.fixedPointResidual.items(), key=lambda kv: kv[1]["abs_sum"])
        if worst[1]["abs_sum"] > 1.0:
            self.mylog.vprint(
                f"Fixed-point residual: {worst[0]} off by {u.d(worst[1]['abs_sum'])} over the horizon "
                f"({u.d(worst[1]['max_abs'])} in one year); the plan's own income implies a slightly "
                "different model than the one solved."
            )

    def _amoContext(self, options):
        """Bundle what amorepair needs from this plan."""
        col_lb, _ = self.B.arrays()
        return amorepair.AmoContext(
            vm=self.vm,
            N_i=self.N_i,
            N_j=self.N_j,
            N_n=self.N_n,
            n_d=self.n_d,
            i_s=self.i_s,
            eta=self.eta,
            n595=self.n595,
            horizons=self.horizons,
            xnet=self.xnet,
            col_lb=col_lb,
            has_wdorder=("zo" in self.vm),
        )

    def _restoreExclusions(self, xx, objfn, objective, options, matricesMatch):
        """Re-establish the two AMO exclusions on a solved vector.

        Owl no longer carries mutual-exclusion binaries: enforcing them cost orders of
        magnitude in solve time for households that owe no tax, while never changing the
        optimum. They are restored here instead — first by an exact algebraic substitution
        for the Roth overlap, then by a churn-minimizing re-solve that leaves spending, the
        terminal balances and the conversion schedule pinned so the objective cannot move.

        Returns the (possibly repaired) vector and its objective value. Any failure keeps
        the solver's own answer: this pass is presentational and must never cost a result.
        """
        c_orig = self.c.arrays()
        col_lb, col_ub = self.B.arrays()

        ctx = self._amoContext(options)
        before = amorepair.count_amo_violations(xx, ctx)
        if before["roth"] == 0 and before["surplus"] == 0:
            return xx, objfn

        # Residual of the solver's own answer: feasibility is relative, so this is the
        # bar a repaired vector has to meet, not zero.
        res0 = amorepair.max_row_violation(xx, self.A, col_lb, col_ub)

        # Surplus first: it needs a re-solve, which is free to move the Roth withdrawals
        # that the substitution below then has to clean up. The re-solve is only sound
        # while the matrices still describe this solution, which stops being true when the
        # loop settles on an earlier iterate.
        yy = xx
        if before["surplus"]:
            if matricesMatch:
                yy = self._polishSurplus(yy, c_orig, ctx, options, res0, col_lb, col_ub)
            else:
                self.mylog.vprint(
                    "Leaving the surplus as solved: an earlier iterate was accepted, so the "
                    "constraint matrices no longer describe this solution."
                )

        # Then the exact substitution, which needs no solve and cannot be undone by one.
        # Its neutrality rests on the carryover, income and cash-flow coefficients, none of
        # which vary between iterations of the loop, so it stays valid on an earlier iterate.
        zz, moves, blocked = amorepair.repair_roth_overlap(yy, ctx)
        if blocked and before["roth"]:
            self.mylog.vprint(f"Roth overlap left in place: {blocked}.")
        if moves:
            res = amorepair.max_row_violation(zz, self.A, col_lb, col_ub)
            if matricesMatch and res > max(res0, 1.0):
                self.mylog.print(
                    f"Roth overlap repair rejected: residual {res:.2e} exceeds {max(res0, 1.0):.2e}.",
                    tag="WARNING",
                )
            else:
                yy = zz

        after = amorepair.count_amo_violations(yy, ctx)

        if after != before:
            self.mylog.vprint(
                f"Exclusion post-processing: Roth overlap {before['roth']} -> {after['roth']} year(s), "
                f"surplus overlap {before['surplus']} -> {after['surplus']} year(s)."
            )
        if after["roth"] or after["surplus"]:
            self.mylog.vprint(
                f"{after['roth'] + after['surplus']} year(s) still combine flows that would "
                "normally be kept apart; these are equivalent to the reported plan."
            )

        return yy, float(np.dot(c_orig, yy))

    def _polishSurplus(self, xx, c_orig, ctx, options, res0, col_lb, col_ub):
        """Re-solve for the same plan with as little surplus churn as possible.

        Spending, the terminal balances, the conversion schedule and any binaries are
        pinned, so the reported objective is unchanged by construction and the incumbent
        is itself a feasible point — the re-solve cannot fail for want of a solution.
        Everything else, in particular the bracket and deduction variables, is free to
        re-establish its own equalities exactly.
        """
        overrides = amorepair.build_polish_overrides(xx, ctx, self.vm.nconts, self.nvars)
        c_polish = amorepair.build_polish_objective(ctx, c_orig, self.gamma_n, self.nvars)
        # With spending and the terminal balances pinned, a dollar of tax lowers the surplus by a
        # dollar, so minimizing the surplus alone would pay tax to shed it -- by filling the top
        # brackets first. Charging tax at twice a surplus dollar rules that trade out.
        c_polish = c_polish + 2.0 * self._tax_cost_vector()
        polish_options = dict(options)
        polish_options["maxTime"] = min(u.get_numeric_option(options, "maxTime", TIME_LIMIT, min_value=0), 60)

        obj = abc.Objective(self.nvars)
        for j in np.nonzero(c_polish)[0]:
            obj.setElem(int(j), float(c_polish[j]))

        _, yy, ok, msg, _ = self._run_mip(
            self.A, self.B, obj, polish_options, col_overrides=overrides, lp_relax=True, update_warm=False
        )
        if not ok or yy is None:
            self.mylog.vprint(f"Surplus polish did not solve ({msg}); keeping the original flows.")
            return xx
        yy = np.array(yy)

        res = amorepair.max_row_violation(yy, self.A, col_lb, col_ub)
        if res > max(res0, 1.0):
            self.mylog.print(
                f"Surplus polish rejected: residual {res:.2e} exceeds {max(res0, 1.0):.2e}.", tag="WARNING"
            )
            return xx

        # The pins should make these exact; check anyway, cheaply, against an index slip.
        drift = 0.0
        for n in range(self.N_n):
            drift = max(drift, abs(yy[self.vm["g"].idx(n)] - xx[self.vm["g"].idx(n)]))
        for i in range(self.N_i):
            for j in range(self.N_j):
                k = self.vm["b"].idx(i, j, self.N_n)
                drift = max(drift, abs(yy[k] - xx[k]))
        if drift > 0.01:
            self.mylog.print(f"Surplus polish rejected: objective drifted by {u.d(drift)}.", tag="WARNING")
            return xx

        before = amorepair.count_amo_violations(xx, ctx)
        after = amorepair.count_amo_violations(yy, ctx)
        if after["surplus"] + after["roth"] > before["surplus"] + before["roth"]:
            return xx
        return yy

    def _run_highs(self, c, Lb, Ub, lbvec, ubvec, a_start, a_index, a_value, integrality, options, warm_x=None):
        """
        Run one HiGHS MIP (or LP when integrality is all-zero) solve directly via highspy.

        Parameters mirror the arrays produced by self.A.to_csr() / self.B.arrays():
          c          — objective coefficients (nvars,)
          Lb, Ub     — variable lower/upper bounds (nvars,)
          lbvec, ubvec — constraint lower/upper bounds (ncons,)
          a_start    — CSR row-starts, length ncons
          a_index    — CSR column indices
          a_value    — CSR non-zero values
          integrality — 0=continuous, 1=integer, per variable (nvars,)
          warm_x     — optional prior solution vector for MIP warm-starting

        Returns (objfn, xx, success, msg, gap) matching the _milpSolve contract.
        """
        import highspy

        time_limit = self._time_limit(options)
        mygap = u.get_numeric_option(options, "gap", GAP, min_value=0)
        verbose = options.get("verbose", False)

        h = highspy.Highs()
        h.setOptionValue("output_flag", bool(verbose))
        h.setOptionValue("mip_rel_gap", float(mygap))
        h.setOptionValue("time_limit", float(time_limit))
        # mipMaxNodes is internal: local search caps each restricted solve by nodes, not time,
        # so that its answer does not depend on machine speed or load (fork: so does RX_NODE_LIMIT).
        node_limit = self._node_limit(options)
        h.setOptionValue("mip_max_nodes", node_limit)
        h.setOptionValue("presolve", "on")

        inf = highspy.kHighsInf
        col_lb = np.where(np.isneginf(Lb), -inf, Lb).astype(np.float64)
        col_ub = np.where(np.isposinf(Ub), inf, Ub).astype(np.float64)
        row_lb = np.where(np.isneginf(lbvec), -inf, lbvec).astype(np.float64)
        row_ub = np.where(np.isposinf(ubvec), inf, ubvec).astype(np.float64)

        h.passModel(
            len(c),
            len(lbvec),
            len(a_value),
            int(highspy.MatrixFormat.kRowwise),  # 2 — NOT 1 (kColwise)
            int(highspy.ObjSense.kMinimize),  # 1
            0.0,  # offset
            c.astype(np.float64),
            col_lb,
            col_ub,
            row_lb,
            row_ub,
            a_start.astype(np.int32),
            a_index.astype(np.int32),
            a_value.astype(np.float64),
            integrality.astype(np.int32),
        )

        if warm_x is not None:
            all_idx = np.arange(len(c), dtype=np.int32)
            h.setSolution(len(c), all_idx, warm_x.astype(np.float64))

        h.run()
        ms = h.getModelStatus()
        # HiGHS's MIP presolve can call a feasible model infeasible when big-M coefficients are
        # large. Retry before believing it.
        if ms == highspy.HighsModelStatus.kInfeasible and integrality.any():
            for option, value, label in _HIGHS_INFEASIBLE_RETRIES:
                self.mylog.vprint(f"HiGHS reported the MIP infeasible; retrying with {label}.")
                h.clearSolver()
                h.setOptionValue(option, value)
                if warm_x is not None:
                    h.setSolution(len(c), np.arange(len(c), dtype=np.int32), warm_x.astype(np.float64))
                h.run()
                ms = h.getModelStatus()
                if ms != highspy.HighsModelStatus.kInfeasible:
                    break
        self._lastMipNodes = int(h.getInfoValue("mip_node_count")[1] or 0)

        _, pstatus = h.getInfoValue("primal_solution_status")
        success = (
            ms in (highspy.HighsModelStatus.kOptimal, highspy.HighsModelStatus.kObjectiveBound)
            or pstatus == highspy.kSolutionStatusFeasible
        )
        # Only kInfeasible means no plan exists. Anything else that failed (kUnknown from a
        # postsolve breakdown, an error, a limit) is the solver giving up on a model that
        # may well be solvable, and must not be reported as an impossible plan.
        self._infeasible = ms == highspy.HighsModelStatus.kInfeasible
        timed_out = success and ms == highspy.HighsModelStatus.kTimeLimit
        node_capped = success and integrality.any() and self._lastMipNodes >= node_limit
        if timed_out:
            self._warn_time_limit(time_limit, h.getInfoValue("mip_gap")[1], mygap)
        elif node_capped and "mipMaxNodes" not in options:
            self._warn_node_limit(node_limit, h.getInfoValue("mip_gap")[1], mygap)

        if success:
            sol = h.getSolution()
            xx = np.array(sol.col_value, dtype=np.float64)
            obj_val = float(h.getObjectiveValue())
            if (timed_out or node_capped) and "zx" in self.vm and self._rx_fixed is None and not self._localSearch:
                # Later iterations keep these exclusion tiers instead of paying the limit again: the loop
                # then re-solves only the continuous part, and the tax stays statutory for the tiers.
                # Not inside local search, whose steps are capped by design and pin or search the tiers.
                gap_capped = float(h.getInfoValue("mip_gap")[1])
                self._rx_fixed = (np.round(self.vm["zx"].extract(xx)), self.RXF_n >= 0.5, gap_capped)
                self.mylog.vprint("Keeping the exclusion tiers of this MILP for the remaining iterations.")
            # mip_gap is meaningless on a pure LP; -1 is the convention for those solves.
            gap = h.getInfoValue("mip_gap")[1] if integrality.any() else -1.0
        else:
            xx = np.zeros(len(c))
            obj_val = None
            gap = -1.0

        return obj_val, xx, success, h.modelStatusToString(ms), float(gap)

    def _run_highs_lp_with_duals(self, A, B, c_obj, options, col_overrides=None, return_col_duals=False):
        """
        Solve LP (no integrality) via HiGHS and return primal + row dual variables.
        Used by _computeDuals for shadow-price reporting.

        A, B, c_obj are abcapi objects (ConstraintMatrix, Bounds, Objective).
        col_overrides: optional dict {col_idx: (lb, ub)} to pin specific columns.

        Returns (obj, x, row_dual, success) where row_dual[i] is the dual variable
        for row i (positive = lower bound active, negative = upper bound active).
        With return_col_duals=True, returns (obj, x, row_dual, col_dual, success)
        where col_dual[j] is the reduced cost of column j.
        Returns (None, zeros, zeros, False) on failure.
        """
        import highspy

        time_limit = u.get_numeric_option(options, "maxTime", TIME_LIMIT, min_value=0)
        verbose = options.get("verbose", False)

        a_start, a_index, a_value = A.to_csr()
        Lb, Ub = B.arrays()
        if col_overrides:
            for col, (lb, ub) in col_overrides.items():
                Lb[col] = lb
                Ub[col] = ub
        lbvec = np.array(A.lb)
        ubvec = np.array(A.ub)
        c = c_obj.arrays()

        h = highspy.Highs()
        h.setOptionValue("output_flag", bool(verbose))
        h.setOptionValue("time_limit", float(time_limit))

        inf = highspy.kHighsInf
        h.passModel(
            len(c),
            len(lbvec),
            len(a_value),
            int(highspy.MatrixFormat.kRowwise),
            int(highspy.ObjSense.kMinimize),
            0.0,
            c.astype(np.float64),
            np.where(np.isneginf(Lb), -inf, Lb).astype(np.float64),
            np.where(np.isposinf(Ub), inf, Ub).astype(np.float64),
            np.where(np.isneginf(lbvec), -inf, lbvec).astype(np.float64),
            np.where(np.isposinf(ubvec), inf, ubvec).astype(np.float64),
            a_start.astype(np.int32),
            a_index.astype(np.int32),
            a_value.astype(np.float64),
            np.zeros(len(c), dtype=np.int32),  # LP: all continuous
        )
        h.run()

        ms = h.getModelStatus()
        if ms == highspy.HighsModelStatus.kOptimal:
            sol = h.getSolution()
            if return_col_duals:
                return (
                    float(h.getObjectiveValue()),
                    np.array(sol.col_value, dtype=np.float64),
                    np.array(sol.row_dual, dtype=np.float64),
                    np.array(sol.col_dual, dtype=np.float64),
                    True,
                )
            return (
                float(h.getObjectiveValue()),
                np.array(sol.col_value, dtype=np.float64),
                np.array(sol.row_dual, dtype=np.float64),
                True,
            )
        if return_col_duals:
            return None, np.zeros(len(c)), np.zeros(len(lbvec)), np.zeros(len(c)), False
        return None, np.zeros(len(c)), np.zeros(len(lbvec)), False

    def _build_mosek_task(self, A, B, c_obj, col_overrides=None, int_vars=None, verbose=False):
        """
        Build and populate a MOSEK task from abcapi objects.
        Configures the objective, variable/constraint bounds, and constraint matrix.
        Caller is responsible for setting solver parameters before calling task.optimize().
        Returns (task, ncons, nvars).
        """
        import mosek

        bdic = {
            "fx": mosek.boundkey.fx,
            "fr": mosek.boundkey.fr,
            "lo": mosek.boundkey.lo,
            "ra": mosek.boundkey.ra,
            "up": mosek.boundkey.up,
        }

        Aind, Aval, clb, cub = A.lists()
        ckeys = A.keys()
        vlb, vub = B.arrays()
        vkeys = list(B.keys())  # copy so overrides don't mutate B
        cind, cval = c_obj.lists()
        ncons = A.ncons
        nvars = A.nvars

        if col_overrides:
            for col, (lb, ub) in col_overrides.items():
                key = abc._bound_key(lb, ub)
                if key == "fx" and lb != ub:
                    # Within the fixed-bound tolerance but not equal: MOSEK rejects a "fixed"
                    # variable whose bounds differ, so give it one value.
                    lb = ub = 0.5 * (lb + ub)
                vlb[col] = lb
                vub[col] = ub
                vkeys[col] = key

        task = mosek.Task()
        task.set_Stream(mosek.streamtype.err, lambda t: self.mylog.vprint(t.strip()))
        if verbose:
            task.set_Stream(mosek.streamtype.msg, lambda t: self.mylog.vprint(t.strip()))
        task.appendcons(ncons)
        task.appendvars(nvars)

        for ii in range(len(cind)):
            task.putcj(cind[ii], cval[ii])
        for ii in range(nvars):
            task.putvarbound(ii, bdic[vkeys[ii]], float(vlb[ii]), float(vub[ii]))
        if int_vars:
            for ii in int_vars:
                task.putvartype(int(ii), mosek.variabletype.type_int)
        for i in range(ncons):
            task.putarow(i, Aind[i], Aval[i])
            task.putconbound(i, bdic[ckeys[i]], float(clb[i]), float(cub[i]))
        task.putobjsense(mosek.objsense.minimize)

        return task, ncons, nvars

    @staticmethod
    def _apply_mosek_threads(task, options):
        """Cap MOSEK's thread count when the 'numThreads' option is set.

        MOSEK's MIP optimizer is internally multi-threaded and grabs all cores by
        default (numThreads=0). Setting a small positive value lets several solves
        run in parallel without oversubscribing the machine (e.g. 5 solves x 2
        threads on 10 cores), which otherwise causes heavy contention. Unset/0
        preserves the default all-core behavior.
        """
        import mosek

        nthreads = int(u.get_numeric_option(options, "numThreads", 0, min_value=0))
        if nthreads > 0:
            task.putintparam(mosek.iparam.num_threads, nthreads)

    def _run_mosek_lp_with_duals(self, A, B, c_obj, options, col_overrides=None):
        """
        Solve LP via MOSEK using abcapi objects; return primal + row dual variables.
        Same return signature as _run_highs_lp_with_duals: (obj, x, row_dual, success).

        A, B, c_obj are abcapi objects (ConstraintMatrix, Bounds, Objective).
        col_overrides: optional dict {col_idx: (lb, ub)} to pin specific columns.
        """
        import mosek

        time_limit = u.get_numeric_option(options, "maxTime", TIME_LIMIT, min_value=0)
        task, ncons, nvars = self._build_mosek_task(A, B, c_obj, col_overrides=col_overrides)
        task.putdouparam(mosek.dparam.optimizer_max_time, float(time_limit))
        self._apply_mosek_threads(task, options)

        try:
            task.optimize()
        except mosek.Error:
            return None, np.zeros(nvars), np.zeros(ncons), False

        solsta = task.getsolsta(mosek.soltype.bas)
        if solsta == mosek.solsta.optimal:
            return (
                float(task.getprimalobj(mosek.soltype.bas)),
                np.array(task.getxx(mosek.soltype.bas)),
                np.array(task.gety(mosek.soltype.bas)),
                True,
            )
        return None, np.zeros(nvars), np.zeros(ncons), False

    def _run_mosek_mip(self, A, B, c_obj, options, lp_relax=False, col_overrides=None):
        """
        Solve MIP (or LP when lp_relax=True) via MOSEK using abcapi objects.
        Same return signature as _run_highs: (obj, x, success, msg, gap).

        A, B, c_obj are abcapi objects (ConstraintMatrix, Bounds, Objective).
        lp_relax: if True, treat all variables as continuous (LP solve).
        col_overrides: optional dict {col_idx: (lb, ub)} to pin specific columns.
        """
        import mosek

        time_limit = u.get_numeric_option(options, "maxTime", TIME_LIMIT, min_value=0)
        mygap = u.get_numeric_option(options, "gap", GAP, min_value=0)
        verbose = options.get("verbose", False)
        int_vars = [] if lp_relax else B.integralityList()
        task, ncons, nvars = self._build_mosek_task(
            A, B, c_obj, col_overrides=col_overrides, int_vars=int_vars, verbose=verbose
        )
        task.putdouparam(mosek.dparam.mio_max_time, float(time_limit))
        task.putdouparam(mosek.dparam.mio_tol_rel_gap, float(mygap))
        if "mipMaxNodes" in options:  # internal: see _run_highs
            task.putintparam(mosek.iparam.mio_max_num_branches, int(options["mipMaxNodes"]))
        self._apply_mosek_threads(task, options)

        # Warm start: an incumbent lets branch-and-bound prune every node that cannot beat it.
        warm = getattr(self, "_mip_warm_start", None)
        if int_vars and warm is not None and len(warm) == nvars:
            task.putxxslice(mosek.soltype.itg, 0, nvars, np.asarray(warm, dtype=float))
            task.putintparam(mosek.iparam.mio_construct_sol, mosek.onoffkey.on)

        try:
            task.optimize()
        except mosek.Error as e:
            self._infeasible = False
            return None, np.zeros(nvars), False, f"MOSEK: {e.msg}", -1.0
        self._lastMipNodes = int(task.getintinf(mosek.iinfitem.mio_num_branch)) if int_vars else 0

        if int_vars:
            sol = mosek.soltype.itg
            solsta = task.getsolsta(sol)
            success = solsta in (mosek.solsta.integer_optimal, mosek.solsta.prim_feas)
            gap = task.getdouinf(mosek.dinfitem.mio_obj_rel_gap) if success else -1.0
        else:
            sol = mosek.soltype.bas
            solsta = task.getsolsta(sol)
            success = solsta == mosek.solsta.optimal
            gap = 0.0
        self._infeasible = _mosekIsInfeasible(task, sol, mosek)

        if success:
            return (
                float(task.getprimalobj(sol)),
                np.array(task.getxx(sol)),
                True,
                f"MOSEK: {solsta}",
                float(gap),
            )
        return None, np.zeros(nvars), False, f"MOSEK: {solsta}", -1.0

    def _run_lp_with_duals(self, A, B, c_obj, options, col_overrides=None):
        """Dispatcher: LP solve with dual extraction (HiGHS or MOSEK)."""
        if getattr(self, "_use_mosek", False):
            return self._run_mosek_lp_with_duals(A, B, c_obj, options, col_overrides)
        return self._run_highs_lp_with_duals(A, B, c_obj, options, col_overrides)

    def _computeDuals(self, xx, options):
        """
        Fix binary variables at their solved values and re-solve the final LP to
        obtain constraint duals (shadow prices) and reduced costs.

        Always solved with HiGHS (the abcapi objects are solver-neutral), so it
        works regardless of the solver used for the main MIP. Results reflect
        marginal values with the self-consistent quantities (SS taxability,
        IRMAA brackets, LTCG bounds, ...) held at their converged values and the
        discrete bracket/exclusion choices held fixed.

        Stores results in self._dual_data, consumed by owlplanner.assistant.explain.
        Row duals are in raw (minimized) objective units; multiply by
        _dual_data["objFac"] to express sensitivities in reported-objective units
        (profile-normalized today's-$ lifetime spending for maxSpending,
        nominal final-year $ of bequest for maxBequest).
        """
        nb = int(getattr(self.vm, "nconts", self.nvars))
        col_overrides = {j: (float(round(xx[j])), float(round(xx[j]))) for j in range(nb, self.nvars)}
        obj, x_lp, row_dual, col_dual, ok = self._run_highs_lp_with_duals(
            self.A, self.B, self.c, options, col_overrides=col_overrides, return_col_duals=True
        )
        if not ok:
            self.mylog.vprint("Dual LP re-solve failed; no shadow prices available.", tag="WARNING")
            self._dual_data = None
            return

        activity = np.array([float(np.dot(vals, xx[inds]))
                            for inds, vals in zip(self.A.Aind, self.A.Aval, strict=True)])
        if self.objective == "maxSpending":
            objFac = -1.0 / float(self.xi_n[0])
        else:
            objFac = -1.0 / float(self.gamma_n[-1])
        Lb, Ub = self.B.arrays()
        self._dual_data = {
            "row_dual": row_dual,
            "col_dual": col_dual,
            "row_activity": activity,
            "row_lb": np.array(self.A.lb, dtype=float),
            "row_ub": np.array(self.A.ub, dtype=float),
            "row_tags": list(self.A.tags),
            "col_lb": Lb,
            "col_ub": Ub,
            "col_value": np.array(xx, dtype=float),
            "objFac": objFac,
            "lp_obj": obj,
        }
        self.mylog.vprint("Computed constraint duals from binaries-fixed LP re-solve.")

    def _run_mip(self, A, B, c_obj, options, lp_relax=False, col_overrides=None, update_warm=True):
        """
        Dispatcher: MIP (or LP when lp_relax=True) solve for decomposition methods.
        A, B, c_obj are abcapi objects (ConstraintMatrix, Bounds, Objective).
        For HiGHS, uses and optionally updates self._highs_warm_start.
        For MOSEK, delegates to _run_mosek_mip (no warm-start management needed).
        """
        if getattr(self, "_use_mosek", False):
            return self._run_mosek_mip(A, B, c_obj, options, lp_relax=lp_relax, col_overrides=col_overrides)
        # HiGHS path: extract CSR arrays from abcapi objects.
        a_start, a_index, a_value = A.to_csr()
        Lb, Ub = B.arrays()
        if col_overrides:
            for col, (lb, ub) in col_overrides.items():
                Lb[col] = lb
                Ub[col] = ub
        lbvec = np.array(A.lb)
        ubvec = np.array(A.ub)
        integrality = np.zeros(A.nvars, dtype=np.int32) if lp_relax else B.integralityArray()
        c = c_obj.arrays()
        warm = getattr(self, "_mip_warm_start", None)
        if warm is None or len(warm) != A.nvars:
            warm = self._highs_warm_start if update_warm else None
        result = self._run_highs(c, Lb, Ub, lbvec, ubvec, a_start, a_index, a_value, integrality, options, warm_x=warm)
        if result[2] and update_warm:
            self._highs_warm_start = result[1].copy()
        return result

    def _time_limit(self, options):
        """Solver time limit: maxTime when given, else TIME_LIMIT."""
        return u.get_numeric_option(options, "maxTime", TIME_LIMIT, min_value=0)

    def _node_limit(self, options):
        """HiGHS node limit: mipMaxNodes when given (local search); otherwise RX_NODE_LIMIT when the
        MILP carries free tier binaries of the income-tiered exclusion and no maxTime is given (see
        RX_NODE_LIMIT); else none in practice."""
        if "mipMaxNodes" in options:
            return int(options["mipMaxNodes"])
        if "maxTime" not in options and "zx" in self.vm and np.any(self.RXF_n >= 0.5):
            return RX_NODE_LIMIT
        return 1_000_000

    def _warn_node_limit(self, node_limit, gap, target):
        """Say that a MILP stopped at its node limit and how far its plan may be from optimal."""
        if gap > target:
            self.mylog.print(
                f"MILP stopped at its {node_limit:,} node limit with a gap of {100 * gap:.2f}% "
                f"(target {100 * target:.2g}%): the plan is feasible but may not be optimal. "
                "Set maxTime to search longer.",
                tag="WARNING",
            )

    def _warn_time_limit(self, time_limit, gap, target):
        """Say that a MILP stopped on its time limit and how far its plan may be from optimal."""
        if gap > target:
            self.mylog.print(
                f"MILP stopped at its {time_limit:.0f} s time limit with a gap of {100 * gap:.2f}% "
                f"(target {100 * target:.2g}%): the plan is feasible but may not be optimal. "
                "Set maxTime to allow more time.",
                tag="WARNING",
            )

    def _milpSolve(self, objective, options):
        """
        Solve using HiGHS directly via highspy, with MIP warm-start between SC iterations.
        The solution from each successful iteration is stored in self._highs_warm_start and
        passed as a hint to the next iteration, reducing branch-and-bound nodes when bracket
        assignments are stable across iterations.
        """
        self._buildConstraints(objective, options)
        a_start, a_index, a_value = self.A.to_csr()
        Lb, Ub = self.B.arrays()
        lbvec = np.array(self.A.lb)
        ubvec = np.array(self.A.ub)
        integrality = self.B.integralityArray()
        c = self.c.arrays()

        result = self._run_highs(
            c, Lb, Ub, lbvec, ubvec, a_start, a_index, a_value, integrality, options, warm_x=self._highs_warm_start
        )
        if result[2]:  # success — store for next SC iteration
            self._highs_warm_start = result[1].copy()
        return result

    def _mosekSolve(self, objective, options):
        """
        Solve problem using MOSEK solver.
        """
        import mosek

        self._buildConstraints(objective, options)
        time_limit = self._time_limit(options)
        if "maxTime" not in options and "zx" in self.vm and np.any(self.RXF_n >= 0.5):
            time_limit = RX_MOSEK_TIME_LIMIT
        mygap = u.get_numeric_option(options, "gap", GAP, min_value=0)
        verbose = options.get("verbose", False)
        int_vars = self.B.integralityList()

        task, ncons, nvars = self._build_mosek_task(self.A, self.B, self.c, int_vars=int_vars, verbose=verbose)
        task.putdouparam(mosek.dparam.mio_max_time, time_limit)  # Default -1
        # task.putdouparam(mosek.dparam.mio_rel_gap_const, 1e-6)       # Default 1e-10
        task.putdouparam(mosek.dparam.mio_tol_rel_gap, mygap)  # Default 1e-4
        self._apply_mosek_threads(task, options)
        # task.putdouparam(mosek.dparam.mio_tol_abs_relax_int, 2e-5)   # Default 1e-5
        # task.putdouparam(mosek.iparam.mio_heuristic_level, 3)        # Default -1

        try:
            trmcode = task.optimize()
        except mosek.Error as e:
            self._infeasible = False
            return 0.0, np.zeros(nvars), False, f"MOSEK: {e.msg}", -1

        # The integer solution slot only exists when the problem actually has integer
        # variables. With every tax mode in loop mode the problem is a pure LP, so read
        # the basic solution instead (same branch as _run_mosek_mip).
        if int_vars:
            soltype = mosek.soltype.itg
            solsta = task.getsolsta(soltype)
            solverSuccess = solsta in (mosek.solsta.integer_optimal, mosek.solsta.prim_feas)
            rel_gap = task.getdouinf(mosek.dinfitem.mio_obj_rel_gap) if solverSuccess else -1
        else:
            soltype = mosek.soltype.bas
            solsta = task.getsolsta(soltype)
            solverSuccess = solsta == mosek.solsta.optimal
            rel_gap = 0.0 if solverSuccess else -1

        if solsta == mosek.solsta.integer_optimal:
            solverMsg = "MOSEK: Optimal integer solution found"
        elif solsta == mosek.solsta.optimal:
            solverMsg = "MOSEK: Optimal solution found"
        elif solsta == mosek.solsta.prim_feas:
            solverMsg = "MOSEK: Feasible integer solution (not proven optimal)"
        elif solsta == mosek.solsta.unknown:
            symname, desc = mosek.Env.getcodedesc(trmcode)
            solverMsg = f"MOSEK: {symname} - {desc}"
        else:
            solverMsg = f"MOSEK: Solution status {solsta}"

        self._infeasible = _mosekIsInfeasible(task, soltype, mosek)

        xx = np.array(task.getxx(soltype))
        solution = task.getprimalobj(soltype)
        task.solutionsummary(mosek.streamtype.msg)
        # task.writedata(self._name+'.ptf')

        return solution, xx, solverSuccess, solverMsg, rel_gap

    def _update_Psi_n(self):
        """
        Recompute SS taxability fractions using the IRS provisional income (PI) formula.

        Delegates to tax_federal.compute_social_security_taxability() for the pure tax
        computation. A 30% damping blend is applied here to damp potential oscillation
        near threshold boundaries and ensure SC-loop convergence.

        When a numeric ``withSSTaxability`` is supplied, Psi_n is pinned on reset in
        _computeNLstuff() and this method is not called, so no override check is needed here.
        """
        ss_n = np.sum(self.zetaBar_in, axis=0)
        new_Psi_n = tx.compute_social_security_taxability(
            self.N_i, self.MAGI_aca_n, ss_n, ssec_tax_fraction=None, n_d=self.n_d
        )

        # 30% damping blend: damp oscillation near threshold boundaries.
        blended = _PSI_DAMP * new_Psi_n + (1.0 - _PSI_DAMP) * self.Psi_n
        if np.max(np.abs(blended - self.Psi_n)) > 1e-3:
            self.Psi_n = blended

    def _computeNLstuff(self, x, includeMedicare, fixedPsi=None):
        """
        Compute MAGI, Medicare costs, ACA costs, long-term capital gain tax rate, and
        net investment income tax (NIIT).
        """
        if x is None:
            # Reset all nonlinear quantities to their starting values for a fresh solve.
            self.Psi_n = np.ones(self.N_n) * (fixedPsi if fixedPsi is not None else 0.85)
            self.MAGI_aca_n = np.zeros(self.N_n)
            self.MAGI_n = np.zeros(self.N_n)
            self.G_n = np.zeros(self.N_n)
            self.J_n = np.zeros(self.N_n)
            self.STR_n = np.zeros(self.N_n)
            self.RXF_n = np.zeros(self.N_n)  # the first iterate is solved without the exclusion
            self.M_n = np.zeros(self.N_n)
            self.ACA_n = np.zeros(self.N_n)
            # Seed I_n for first NIIT LP iteration: portfolio part is zero before first solve.
            if getattr(self, "_niit_lp", False) and not hasattr(self, "I_n"):
                self.I_n = np.sum(self.netinv_in, axis=0)
            return

        self._aggregateResults(x, short=True)
        # Uses the Psi_n the LP was built with, so it has to come before _update_Psi_n.
        self.STR_n = self._state_recapture_implied()
        self.RXF_n = self._tiered_exclusion_free()
        self._rx_refixed_n = self._refix_boundary_tiers()
        # Psi_n is derived directly from the tss_n LP variable in _aggregateResults
        # when withSSTaxability=="optimize"; skip the SC-loop update in that case.
        # Also skip when fixedPsi is set (numeric withSSTaxability).
        if "tss" not in self.vm and fixedPsi is None:
            self._update_Psi_n()

        # SS claiming-age LP: update zetaBar_in from optimal zssa solution each SC iteration.
        # _ssa_spousal_offset is updated here so next iteration's cash-flow constraint is correct.
        if getattr(self, "_ssa_lp", False) and "zssa" in self.vm:
            zssa_vals = self.vm["zssa"].extract(x)
            new_ages = np.array(self.ssecAges, dtype=float)
            for i in range(self.N_i):
                k_opt = int(np.argmax(zssa_vals[i, :]))
                new_ages[i] = float(self._ssa_ages_k[k_opt])
            new_zeta_in, _ = socsec.compute_social_security_benefits(
                self.ssecAmounts,
                new_ages,
                self.yobs,
                self.mobs,
                self.tobs,
                self.horizons,
                self.N_i,
                self.N_n,
                trim_pct=getattr(self, "ssecTrimPct", 0) or 0,
                trim_year=getattr(self, "ssecTrimYear", None),
                thisyear=date.today().year,
                survivor_claim_age=getattr(self, "ssecSurvivorClaimAge", "immediate"),
            )
            new_zetaBar_in = new_zeta_in * self.gamma_n[:-1]
            for i in range(self.N_i):
                k_opt = int(np.argmax(zssa_vals[i, :]))
                self._ssa_spousal_offset[i, :] = new_zetaBar_in[i, :] - self._ssa_B_own[i, k_opt, :]
            self.zetaBar_in = new_zetaBar_in

        # NIIT (IRC §1411) and IRMAA use the AGI-basis MAGI_n (taxable SS only). ACA (below)
        # uses the full-SS MAGI_aca_n (§36B adds back non-taxable SS).
        if not getattr(self, "_niit_lp", False):
            self.J_n = tx.computeNIIT(self.N_i, self.MAGI_n, self.I_n, self.Q_n, self.n_d, self.N_n)
        # LTCG tax is in the LP via q bracket variables; U_n is set by _aggregateResults.
        # Compute Medicare through self-consistent loop.
        if includeMedicare:
            include_part_d = getattr(self, "_include_medicare_part_d", True)
            part_d_base = getattr(self, "_medicare_part_d_base_annual_per_person", 0.0)
            self.M_n = tx.mediCosts(
                self.yobs,
                self.horizons,
                self.MAGI_n,
                self.prevMAGI,
                self.gamma_n[:-1],
                self.N_n,
                include_part_d=include_part_d,
                part_d_base_annual_per_person=part_d_base,
            )
        # Compute ACA costs through self-consistent loop (uses current-year MAGI, no 2-year lag).
        # In optimize mode (withACA="optimize"), ACA_n stays zero; maca_n carries the cost.
        if self.slcsp_annual > 0 and not self._aca_lp:
            n_aca_start = max(0, self.aca_start_year - int(self.year_n[0])) if self.aca_start_year > 0 else 0
            self.ACA_n = tx.acaCosts(
                self.yobs,
                self.horizons,
                self.MAGI_aca_n,
                self.gamma_n[:-1],
                self.slcsp_annual,
                self.N_n,
                n_aca_start=n_aca_start,
            )

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
        n_d = self.n_d
        vm = self.vm

        x = u.roundCents(x)

        # Allocate, slice in, and reshape variables.
        self.b_ijn = vm["b"].extract(x)
        self.b_ijkn = np.zeros((Ni, Nj, Nk, Nn + 1))
        for k in range(Nk):
            self.b_ijkn[:, :, k, :] = self.b_ijn[:, :, :] * self.alpha_ijkn[:, :, k, :]

        self.d_in = vm["d"].extract(x)
        self.e_n = vm["e"].extract(x)
        self.f_tn = vm["f"].extract(x)
        self.g_n = vm["g"].extract(x)
        if "h" in vm:
            self.h_qn = vm["h"].extract(x)
        if "haca" in vm:
            self.haca_qn = vm["haca"].extract(x)
        self.m_n = vm["m"].extract(x)
        self.maca_n = vm["maca"].extract(x) if "maca" in vm else np.zeros(self.N_n)
        self.s_n = vm["s"].extract(x)
        self.w_ijn = vm["w"].extract(x)
        self.x_in = vm["x"].extract(x)
        hsa_total = np.sum(self.w_ijn[:, 3, :], axis=0)
        self.hsa_medicare_n = np.minimum(hsa_total, self.medicare_n)

        # Extract SS taxability LP variables and update Psi_n from the LP solution.
        if "tss" in vm:
            self.tss_n = vm["tss"].extract(x)
            ss_n = np.sum(self.zetaBar_in, axis=0)
            mask = ss_n > 0
            self.Psi_n = np.zeros(Nn)
            self.Psi_n[mask] = np.minimum(self.tss_n[mask] / ss_n[mask], 0.85)

        # Extract optimal SS claiming ages from zssa binaries (full aggregation only).
        if "zssa" in vm and not short:
            zssa_vals = vm["zssa"].extract(x)
            for i in range(Ni):
                k_opt = int(np.argmax(zssa_vals[i, :]))
                self.ssecAges[i] = float(self._ssa_ages_k[k_opt])

        self.G_n = np.sum(self.f_tn, axis=0)

        tau_0 = np.array(self.tau_kn[0, :])
        # Last year's rates.
        tau_0prev = np.roll(tau_0, 1)
        # Capital gain coefficient per withdrawal: tracked gain fraction when basis is known,
        # otherwise current-year price appreciation only (tau_0 - mu).
        if self.gain_fraction_in is not None:
            cgr = self.gain_fraction_in[:, :Nn].copy()  # shape (N_i, N_n)
            nan_mask = np.isnan(cgr)
            if nan_mask.any():  # mixed: some persons use legacy
                legacy = np.maximum(0, tau_0prev - self.mu)
                cgr[nan_mask] = np.broadcast_to(legacy, cgr.shape)[nan_mask]
        else:
            cgr = np.maximum(0, tau_0prev - self.mu)[np.newaxis, :]  # broadcast to (1, N_n)
        self.Q_n = np.sum(
            (
                self.mu
                * (self.b_ijn[:, 0, :Nn] - self.w_ijn[:, 0, :] + self.d_in[:, :] + 0.5 * self.kappa_ijn[:, 0, :Nn])
                + cgr * self.w_ijn[:, 0, :]
            )
            * self.alpha_ijkn[:, 0, 0, :Nn],
            axis=0,
        )
        # Add fixed assets capital gains.
        self.Q_n += self.fixed_assets_capital_gains_n
        # Extract LTCG bracket variables and compute derived quantities.
        self.q_pn = vm["q"].extract(x)  # shape (N_p=3, N_n); p=0/1/2 → 0%/15%/20% brackets
        self.U_n = 0.15 * self.q_pn[1, :] + 0.20 * self.q_pn[2, :]
        # When Q_n < T15 the LP may set q[0,n] > Q_n (free 0% bucket), clip for clean reporting.
        total_ltcg = np.maximum(self.Q_n, 0)
        excess = np.maximum(0, self.q_pn[0, :] - total_ltcg)
        self.q_pn[0, :] = np.maximum(0, self.q_pn[0, :] - excess)
        # Sanity check: U_n > 20% × Q_n is mathematically impossible — warn when q bracket
        # variables are inflated well beyond actual LTCG income (degenerate SC-loop solution).
        _bad = np.where(self.U_n > 0.20 * total_ltcg + 1.0)[0]
        for n in _bad:
            self.mylog.print(
                f"year {self.year_n[n]}: LTCG tax ${self.U_n[n]:,.0f} "
                f"exceeds 20% of taxable gains ${self.Q_n[n]:,.0f} — "
                "SC-loop solution may be degenerate.",
                tag="WARNING",
            )

        # Extract NIIT LP variable when in optimize mode.
        if "Jn" in vm:
            self.J_n = vm["Jn"].extract(x)

        # Two MAGI flavors. e_n + G_n already include the *taxable* SS portion (via
        # _add_taxable_income), so AGI = e_n + G_n + Q_n. The NIIT "magi" LP variable, when
        # present, is the AGI-basis MAGI (see _add_magi_lp).
        if "magi" in vm:
            self.MAGI_n = vm["magi"].extract(x)
        else:
            self.MAGI_n = self.G_n + self.e_n + self.Q_n
        # Full-SS MAGI adds back the non-taxable SS portion (for ACA §36B and SS-taxability
        # provisional income). Equals AGI + (1-Psi)*zetaBar = AGI + (zetaBar - taxable SS).
        self.MAGI_aca_n = self.MAGI_n + np.sum((1 - self.Psi_n) * self.zetaBar_in, axis=0)

        # Only positive returns count as interest/dividend income (matches _add_taxable_income).
        I_in = (self.b_ijn[:, 0, :-1] + self.d_in - self.w_ijn[:, 0, :]) * np.sum(
            self.alpha_ijkn[:, 0, 1:, :Nn] * np.maximum(0, self.tau_kn[1:, :]), axis=1
        )
        # Sum over individuals to share losses across spouses; clamp to non-negative.
        # Also add net investment income from rent/trust (netinv_in) for NIIT purposes.
        self.I_n = np.maximum(0, np.sum(I_in, axis=0)) + np.sum(self.netinv_in, axis=0)

        # State taxable income and AGI, which the benefit recapture is a function of.
        self.st_f_tn = vm["st_f"].extract(x) if "st_f" in vm else np.zeros((self.N_st, Nn))
        self.st_re_in = vm["st_re"].extract(x) if "st_re" in vm else np.zeros((Ni, Nn))
        self.st_rx_n = vm["st_rx"].extract(x) if "st_rx" in vm else np.zeros(Nn)
        self.st_agi_n, self.st_ti_n = self._state_agi_and_ti()

        # Stop after building minimum required for self-consistent loop.
        if short:
            return

        self.lt_f_tn = vm["lt_f"].extract(x) if "lt_f" in vm else np.zeros((self.N_lt, Nn))
        self.st_c_n = vm["st_c"].extract(x) if "st_c" in vm else np.zeros(Nn)
        self._finalize_state_tax()

        self.T_tn = self.f_tn * self.theta_tn
        self.T_n = np.sum(self.T_tn, axis=0)
        self.P_n = np.zeros(Nn)
        # Add early withdrawal penalty if any.
        for i in range(Ni):
            self.P_n[0 : self.n595[i]] += 0.1 * self.w_ijn[i, 1, 0 : self.n595[i]]

        self.T_n += self.P_n
        # Compute partial distribution at the passing of first spouse.
        if Ni == 2 and n_d < Nn:
            nx = n_d - 1
            i_d = self.i_d
            part_j = np.zeros(Nj)
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
            # Capture heir tax liability BEFORE applying (1-nu)
            self.partial_heir_tax_liability = (partialBequest_j[1] + partialBequest_j[3]) * self.nu / self.gamma_n[n_d]
            partialBequest_j[1] *= 1 - self.nu  # tax-deferred: heirs pay ordinary income tax
            partialBequest_j[3] *= 1 - self.nu  # HSA: non-spouse heirs include full balance in ordinary income
            self.partialBequest = np.sum(partialBequest_j) / self.gamma_n[n_d]
        else:
            self.partialBequest = 0
            self.partial_heir_tax_liability = 0.0

        self._netSurplusRoundTrip()

        # Split the tax-deferred withdrawal into the part the RMD forced and the
        # discretionary remainder. A QCD satisfies the RMD without being a withdrawal,
        # so w can legitimately fall below the gross RMD; clamping keeps the reported
        # halves non-negative and, critically, still summing exactly to w[:,1,:] —
        # the sources decomposition is a cash identity and must not gain or lose a dollar.
        gross_rmd_in = self.rho_in * self.b_ijn[:, 1, :-1]
        self.qcd_rmd_in = np.minimum(self.qcd_in, gross_rmd_in)
        self.rmd_in = np.minimum(np.maximum(gross_rmd_in - self.qcd_in, 0), self.w_ijn[:, 1, :])
        self.dist_in = self.w_ijn[:, 1, :] - self.rmd_in

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
        sources["other inc"] = self.other_inc_in
        sources["net inv"] = self.netinv_in
        sources["ssec"] = self.zetaBar_in
        sources["pension"] = self.piBar_in
        sources["spia"] = self.spiaBar_in
        sources["txbl acc wdrwl"] = self.w_ijn[:, 0, :]
        sources["RMD"] = self.rmd_in
        sources["+dist"] = self.dist_in
        sources["RothX"] = self.x_in
        sources["tax-free wdrwl"] = self.w_ijn[:, 2, :]
        sources["HSA wdrwl"] = self.w_ijn[:, 3, :]
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
        savings["hsa"] = self.b_ijn[:, 3, :]

        self.sources_in = sources
        self.savings_in = savings

        estate_j = np.sum(self.b_ijn[:, :, self.N_n], axis=0)
        # Capture heir tax liability BEFORE applying (1-nu)
        self.heir_tax_liability = (estate_j[1] + estate_j[3]) * self.nu / self.gamma_n[-1]
        estate_j[1] *= 1 - self.nu  # tax-deferred: heirs pay ordinary income tax
        estate_j[3] *= 1 - self.nu  # HSA: non-spouse heirs include full balance in ordinary income
        # Subtract remaining debt balance from estate
        total_estate = np.sum(estate_j) - self.remaining_debt_balance
        self.bequest = max(0.0, total_estate) / self.gamma_n[-1]

        self.basis = self.g_n[0] / self.xi_n[0]

        return None

    @property
    def aca_costs_n(self):
        """ACA net premium costs per year: LP result (optimize mode) or SC-loop result (loop mode)."""
        return self.maca_n if self._aca_lp else self.ACA_n

    @property
    def medicare_n(self):
        """Total Medicare premiums per year, Part B and Part D including IRMAA.

        Which array carries the cost depends on how Medicare was solved: withMedicare='optimize'
        puts it in the LP variable m_n and leaves M_n at zero, while loop mode computes M_n
        outside the solver and pins m_n to zero. Read the total here rather than from either
        array, which is only ever half the answer.
        """
        return self.m_n + self.M_n

    @_checkCaseStatus
    def estate(self):
        """
        Reports final account balances.
        """
        _estate = np.sum(self.b_ijn[:, :, self.N_n], axis=0)
        _estate[1] *= 1 - self.nu
        self.mylog.vprint(f"Estate value of {u.d(sum(_estate))} at the end of year {self.year_n[-1]}.")

        return None

    @_checkCaseStatus
    def summary(self, N=None):
        """
        Print summary in logs.
        """
        self.mylog.print("SUMMARY ================================================================")
        dic = self.summaryDic(N)
        for key, value in dic.items():
            self.mylog.print(f"{key}: {value}")
        self.mylog.print("------------------------------------------------------------------------")

        return None

    def summaryList(self, N=None):
        """Return summary as a list."""
        return export.build_summary_list(self, N)

    def summaryDf(self, N=None):
        """Return summary as a dataframe."""
        return pd.DataFrame(export.build_summary_dic(self, N), index=[self._name])

    def summaryString(self, N=None):
        """Return summary as a string."""
        return export.build_summary_string(self, N)

    def summaryDic(self, N=None):
        """Return dictionary containing summary of values."""
        return export.build_summary_dic(self, N)

    def metricsDict(self, N=None):
        """Return key metrics as a dict of plain floats (stable snake_case keys)."""
        return export.plan_metrics(self, N)

    def showRatesCorrelations(self, tag="", shareRange=False, figure=False):
        """
        Plot correlations between various rates.

        A tag string can be set to add information to the title of the plot.
        """
        if self.rateMethod in [None, "user", "historical_average", "conservative", "trailing_30", "optimistic"]:
            self.mylog.print(f"Cannot plot correlations for {self.rateMethod} rate method.", tag="WARNING")
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
                self.mylog.print(
                    "Cannot plot correlations for constant rates (no variation in rate values).", tag="WARNING"
                )
                return None

        # For stochastic models, build a large representative sample so that
        # the histograms and scatter plots reflect the method's distribution
        # rather than the properties of the single N_n-year realization.
        # Deterministic models (historical, constant) already have the correct
        # data in tau_kn.
        _N_REPR = 2000
        rateModel = getattr(self, "rateModel", None)
        if rateModel is not None and not rateModel.deterministic:
            repr_series = rateModel.representative_sample(_N_REPR)  # (M, 4) decimal
            display_tau_kn = repr_series.transpose()  # (4, M)
        else:
            display_tau_kn = self.tau_kn

        fig = self._plotter.plot_rates_correlations(
            self._name, display_tau_kn, self.rateMethod, self.rateFrm, self.rateTo, tag, shareRange
        )

        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    def showRatesCDF(self, tag="", figure=False):
        """
        Plot empirical CDFs of rate distributions used in this plan.

        For historical methods, the empirical CDF of the selected historical
        window is overlaid for comparison. Not available for constant-rate methods.
        A tag string can be set to add information to the title of the plot.
        """
        if self.rateMethod in [None, "user", "historical_average", "conservative", "trailing_30", "optimistic"]:
            self.mylog.print(f"Cannot plot CDF for {self.rateMethod} rate method.", tag="WARNING")
            return None

        _N_REPR = 2000
        rateModel = getattr(self, "rateModel", None)
        if rateModel is not None and not rateModel.deterministic:
            repr_series = rateModel.representative_sample(_N_REPR)  # (M, 4) decimal
            display_tau_kn = repr_series.transpose()  # (4, M)
        else:
            display_tau_kn = self.tau_kn

        fig = self._plotter.plot_rates_cdf(
            self._name,
            display_tau_kn,
            self.rateMethod,
            rates.SP500,
            rates.BondsBaa,
            rates.TNotes,
            rates.Inflation,
            rates.FROM,
            self.rateFrm,
            self.rateTo,
            tag,
        )

        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    def showRatesDistributions(self, frm=rates.FROM, to=rates.TO, figure=False):
        """
        Plot histograms of the rates distributions.
        """
        fig = self._plotter.plot_rates_distributions(
            frm, to, rates.SP500, rates.BondsBaa, rates.TNotes, rates.Inflation, rates.FROM
        )
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
            self.mylog.print("Rate method must be selected before plotting.", tag="WARNING")
            return None

        fig = self._plotter.plot_rates(
            self._name, self.tau_kn, self.year_n, self.N_k, self.rateMethod, self.rateFrm, self.rateTo, tag
        )

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
            self.mylog.print("Profile must be selected before plotting.", tag="WARNING")
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
        fig = self._plotter.plot_net_spending(
            self.year_n, self.g_n, self.xi_n, self.xiBar_n, self.gamma_n, value, title, self.inames
        )
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    def retentionMargin(self):
        """
        Return the annual savings retention margin, in percentage points (N_n,).

        Margin = retention − sustainability. Zero is real-wealth-neutral; positive
        means real wealth is growing that year, negative that it is shrinking.

        Retention is 1 − (net draw / balances). The net draw counts every dollar
        leaving the portfolio, which is more than w_ijn: deposits and contributions
        come back off it, while qualified charitable distributions and SPIA premiums
        are added, since both are paid straight out of the tax-deferred account
        without passing through a withdrawal. Leaving them out would shrink the
        balances in the denominator while omitting them from the numerator, making
        the margin read healthier in exactly the years they occur.
        """
        net_w = self.w_ijn.copy()
        net_w[:, 0, :] -= self.d_in
        net_w[:, 1:, :] -= self.kappa_ijn[:, 1:, : self.N_n]
        net_draw_n = np.sum(net_w, axis=(0, 1)) + np.sum(self.qcd_in, axis=0) + np.sum(self.spia_premiums_in, axis=0)
        b_n = np.sum(self.b_ijn[:, :, :-1], axis=(0, 1))
        with np.errstate(invalid="ignore", divide="ignore"):
            rate = np.where(b_n > 0, (1 - net_draw_n / b_n) * 100, 0.0)
        num_n = np.einsum(
            "ijn,ijkn,kn->n",
            self.b_ijn[:, :, : self.N_n],
            self.alpha_ijkn[:, :, :, : self.N_n],
            self.tau_kn[:, : self.N_n],
        )
        with np.errstate(invalid="ignore", divide="ignore"):
            r_n = np.where(b_n > 0, num_n / b_n, 0.0)
        inflation_n = self.gamma_n[1 : self.N_n + 1] / self.gamma_n[: self.N_n]
        sustainability_n = inflation_n / (1.0 + r_n) * 100.0
        return rate - sustainability_n

    @_checkCaseStatus
    def showRetentionMargin(self, tag="", figure=False):
        """
        Plot savings retention margin over time: annual excess above the real break-even rate.

        Margin = retention − sustainability (in percentage points). Zero = real-wealth-neutral;
        blue bars = real wealth growing; red bars = real wealth shrinking.
        """
        margin_n = self.retentionMargin()
        title = self._name + "\nSavings Retention Margin"
        if self.bequest > 0:
            title += f"\n(Note: bequest of {u.d(self.bequest, f=0)} included in balance)"
        if tag:
            title += " - " + tag
        fig = self._plotter.plot_retention_margin(self.year_n, margin_n, title)
        if figure:
            return fig
        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showAssetComposition(self, tag="", value=None, figure=False):
        """
        Plot the composition of each savings account in thousands of dollars
        during the simulation time. This function will generate four
        graphs, one for taxable accounts, one for tax-deferred accounts,
        one for tax-free accounts, and one for HSA accounts.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValueType(value)
        figures = self._plotter.plot_asset_composition(
            self.year_n, self.inames, self.b_ijkn, self.gamma_n, value, self._name, tag
        )
        if all(f is None for f in figures):
            return None
        if figure:
            return figures

        for fig in figures:
            if fig is not None:
                self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showLifetimeAllocation(self, figure=False):
        """
        Plot two pie charts showing the lifetime cash flow allocation in today's dollars:
        - Left pie: how money is spent (living, taxes, healthcare, debt, bequest)
        - Right pie: where money comes from (portfolio, SS, pension, wages, SPIA, other)
        Returns a list of two figures (one per pie).
        """
        alloc = self.lifetime_allocation()
        fig = self._plotter.plot_lifetime_allocation(alloc, self._name)
        if fig is None:
            return None
        if figure:
            return fig
        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showCashFlowMix(self, figure=False):
        """
        Plot annual cash flow breakdown as normalized stacked-area charts (%).

        Left panel: how outflows are composed year by year (living, taxes, healthcare, debt).
        Right panel: how income is sourced year by year (portfolio, SS, pension, wages, SPIA, other).
        Bequest is excluded (lump sum — see showLifetimeAllocation for the lifetime total).
        """
        mix = self.annual_cashflow_mix()
        fig = self._plotter.plot_cashflow_mix(mix, self._name)
        if fig is None:
            return None
        if figure:
            return fig
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
        fig = self._plotter.plot_gross_income(self.year_n, self.G_n, self.gamma_n, value, title, tax_brackets)
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
        figures = self._plotter.plot_allocations(self.year_n, self.inames, self.alpha_ijkn, self.ARCoord, title)
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
        fig = self._plotter.plot_accounts(self.year_n, self.savings_in, self.gamma_n, value, title, self.inames)
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showBalanceSheet(self, tag="", value=None, figure=False):
        """
        Plot the combined balance sheet over time: assets stacked above zero,
        liabilities below zero, with the traditional and liquid net-worth lines.

        Returns None if the balance sheet is empty (all components zero).

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        # Beginning-of-year snapshots plus a final end-of-plan (bequest) row,
        # mirroring the balance-sheet worksheets in export.py.
        taxable = np.sum(self.b_ijn[:, 0, :], axis=0)
        taxdef = np.sum(self.b_ijn[:, 1, :], axis=0)
        taxfree = np.sum(self.b_ijn[:, 2, :], axis=0)
        hsa = np.sum(self.b_ijn[:, 3, :], axis=0)
        fixed = np.append(self.fixed_assets_current_asset_values_n, self.fixed_assets_bequest_value)
        debt = np.append(self.fixed_assets_debt_balances_remaining_n, self.remaining_debt_balance)
        dispo = np.append(self.fixed_assets_disposition_costs_n, 0.0)

        total_assets = taxable + taxdef + taxfree + hsa + fixed
        deferred_tax = (taxdef + hsa) * self.liquidationTaxRate
        total_liab = debt + deferred_tax + dispo

        if np.max(np.abs(total_assets)) + np.max(np.abs(total_liab)) < 1.0:
            return None

        bs_data = {
            "assets": {
                "taxable": taxable,
                "tax-deferred": taxdef,
                "tax-free": taxfree,
                "HSA": hsa,
                "fixed assets": fixed,
            },
            "liabilities": {
                "debt": debt,
                "deferred income tax": deferred_tax,
                "disposition costs": dispo,
            },
            "net worth": total_assets - debt,
            "liquid net worth": total_assets - total_liab,
        }

        value = self._checkValueType(value)
        title = self._name + "\nBalance Sheet"
        if tag:
            title += " - " + tag
        fig = self._plotter.plot_balance_sheet(self.year_n, bs_data, self.gamma_n, value, title)
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showHSA(self, tag="", value=None, figure=False):
        """
        Plot HSA activity (balance, contributions, withdrawals) over time.

        Returns None if all HSA balances, contributions, and withdrawals are zero.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        hsa_bal = self.b_ijn[:, 3, :]
        hsa_ctrb = self.kappa_ijn[:, 3, : self.N_n]
        hsa_wdrwl = self.w_ijn[:, 3, :]
        if (np.abs(hsa_bal).sum() + np.abs(hsa_ctrb).sum() + np.abs(hsa_wdrwl).sum()) < 1.0:
            return None
        value = self._checkValueType(value)
        title = self._name + "\nHSA Activity"
        if tag:
            title += " - " + tag
        # Split household-level Medicare withdrawals into per-individual proportional shares.
        hsa_total_n = np.sum(hsa_wdrwl, axis=0)
        safe_total_n = np.where(hsa_total_n > 0, hsa_total_n, 1.0)
        frac_in = hsa_wdrwl / safe_total_n[np.newaxis, :]
        medicare_in = frac_in * self.hsa_medicare_n[np.newaxis, :]
        hsa_data = {
            "balance": hsa_bal,
            "contributions": hsa_ctrb,
            "withdrawals": hsa_wdrwl,
            "medicare_withdrawals": medicare_in,
        }
        fig = self._plotter.plot_hsa(self.year_n, hsa_data, self.gamma_n, value, title, self.inames)
        if figure:
            return fig
        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showCharitableGiving(self, tag="", value=None, figure=False):
        """
        Plot qualified charitable distributions over time, split into the part that
        satisfies the required minimum distribution and the part beyond it, against
        the gross RMD for context.

        Returns None if the household makes no QCDs, so the plot costs nothing to
        anyone who does not give this way.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        if np.abs(self.qcd_in).sum() < 1.0:
            return None
        value = self._checkValueType(value)
        title = self._name + "\nCharitable Giving (QCD)"
        if tag:
            title += " - " + tag
        qcd_data = {
            "giving": self.qcd_in,
            # The RMD-satisfying part is capped by the gross RMD, so the remainder is
            # giving beyond what was required. Together they add back to the full gift.
            "satisfying_rmd": self.qcd_rmd_in,
            "gross_rmd": self.rho_in * self.b_ijn[:, 1, :-1],
        }
        fig = self._plotter.plot_charitable_giving(self.year_n, qcd_data, self.gamma_n, value, title, self.inames)
        if figure:
            return fig
        self._plotter.jupyter_renderer(fig)
        return None

    @_checkCaseStatus
    def showSources(self, tag="", value=None, figure=False):
        """
        Plot income, big-ticket items, and debt payments over time.

        A tag string can be set to add information to the title of the plot.

        The value parameter can be set to *nominal* or *today*, overriding
        the default behavior of setDefaultPlots().
        """
        value = self._checkValueType(value)
        title = self._name + "\nIncome, Big-Ticket Items, and Debts"
        if tag:
            title += " - " + tag
        fig = self._plotter.plot_sources(self.year_n, self.sources_in, self.gamma_n, value, title, self.inames)
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
        title = self._name + "\nIncome Tax"
        if tag:
            title += " - " + tag
        # All taxes: ordinary income, dividends, NIIT, and state income tax.
        allTaxes = self.T_n + self.U_n + self.J_n
        aca_n = self.aca_costs_n if self.slcsp_annual > 0 else None
        st_n = self.st_T_n if any(self._states_n()) else None
        fig = self._plotter.plot_taxes(
            self.year_n, allTaxes, self.medicare_n, self.gamma_n, value, title, self.inames, A_n=aca_n, ST_n=st_n
        )
        if figure:
            return fig

        self._plotter.jupyter_renderer(fig)
        return None

    def saveWorkbook(self, overwrite=False, *, basename=None, saveToFile=True, with_config="no"):
        """
        Save instance in an Excel spreadsheet.
        See export.plan_to_excel for sheet structure and with_config options.
        """
        return export.plan_to_excel(
            self, overwrite=overwrite, basename=basename, saveToFile=saveToFile, with_config=with_config
        )

    def saveWorkbookCSV(self, basename):
        """
        Save plan data in CSV format. See saveWorkbook() for related structure.
        """
        return export.plan_to_csv(self, basename, self.mylog)

    @_checkConfiguration
    def saveConfig(self, basename=None):
        """
        Save parameters in a configuration file.
        """
        if basename is None:
            basename = self._name if self._name.lower().startswith("case_") else "case_" + self._name

        config.saveConfig(self, basename, self.mylog)

        return None
