"""
Stress testing methods for retirement plans and stochastic spending optimization.

Provides ``run_historical_range``, ``run_mc``, ``run_stochastic_spending``, and
``run_spending_bequest_frontier``, which take a :class:`~owlplanner.plan.Plan` instance as the
first argument (``Plan`` exposes them as methods that delegate here). Also includes standalone
LP helpers for the efficient frontier.

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

import os
import warnings
import numpy as np
import pandas as pd
from itertools import product
from concurrent.futures import ThreadPoolExecutor, as_completed
from scipy.optimize import linprog

from . import mylogging as log
from . import progress
from . import rates
from . import utils as u
from .config.plan_bridge import clone
from .data.mortality_tables import sample_lifespans


###############################################################################
# Parallel scenario worker
###############################################################################


def _reset_scenario_rng(plan):
    """
    Reset the rate-model RNG from the plan's authoritative seed so that repeated
    Monte Carlo runs are reproducible when seeded.

    plan.rateSeed is what setReproducible() maintains and may be updated after
    the rate model was constructed; rateModel.seed is the copy captured at
    setRates() time and can be stale, so it must not be used here.  The model's
    copy is re-synced for anything else that reads it.
    """
    if plan.reproducibleRates and hasattr(plan.rateModel, "_rng"):
        plan.rateModel.seed = plan.rateSeed
        plan.rateModel._rng = np.random.default_rng(plan.rateSeed)


def _year1_snapshot(p):
    """
    Extract the first plan year's primal decisions from a solved plan.

    Year-0 nominal dollars are today's dollars (gamma_n[0] = 1).  Kept as a plain
    dict of floats so the ThreadPool result stays small and pickling-free.
    """
    filled = [t for t in range(p.f_tn.shape[0]) if p.f_tn[t, 0] > 1.0]
    top = max(filled) if filled else None
    return {
        "x": [float(v) for v in p.x_in[:, 0]],
        "w": [[float(v) for v in p.w_ijn[i, :, 0]] for i in range(p.N_i)],
        "g0": float(p.g_n[0]),
        "s0": float(p.s_n[0]),
        "top_bracket_pct": None if top is None else float(np.round(p.theta_tn[top, 0] * 100, 1)),
        "filled_to_boundary": None if top is None else bool((p.DeltaBar_tn[top, 0] - p.f_tn[top, 0]) < 1.0),
    }


def _scenario_worker(args):
    """
    Solve one scenario in a worker thread.

    args tuple:
      plan          — cloned Plan (thread-local copy, already has all data)
      tau_kn_or_year — ndarray (N_k, N_n) pre-generated rates (MC), or int year (historical)
      gamma_n       — unused placeholder for compatibility (None in current calls)
      options       — solver options dict
      label         — name this scenario carries in the log (None to fall back
                      to the worker thread's own name)

    Returns (basis, year1) where year1 is the _year1_snapshot dict, or
    (None, None) on solver failure.
    """
    p, tau_kn_or_year, gamma_n, options, label = args

    # Workers are reused across scenarios, so the thread name alone would say which
    # slot logged a line, not which scenario it was solving.
    with log.threadLabel(label):
        if isinstance(tau_kn_or_year, tuple):
            year, reverse, roll = tau_kn_or_year
            p.setRates("historical", year, reverse=reverse, roll=roll)
        elif isinstance(tau_kn_or_year, int):
            p.setRates("historical", tau_kn_or_year)
        else:
            Nn = p.N_n
            tau_slice = tau_kn_or_year[:, :Nn]
            if tau_slice.shape[1] != Nn:
                raise RuntimeError(
                    f"Precomputed rate path is too short for scenario horizon: have {tau_slice.shape[1]}, need {Nn}."
                )
            p.tau_kn = tau_slice
            p.gamma_n = rates.gen_gamma_n(p.tau_kn)
            p._adjustedParameters = False
            p.caseStatus = "modified"

        p.solve("maxSpending", options)
        if p.caseStatus == "solved":
            # partialBequest is only defined after a solve, and is discarded with p.
            return p.basis, _year1_snapshot(p), float(getattr(p, "partialBequest", 0.0))
        return None, None, None


###############################################################################
# Standalone LP functions (module-level, no Plan dependency)
###############################################################################


def _stochastic_lp(bases, lam):
    """
    Solve the stochastic spending LP for a given risk-aversion parameter lambda.

    Finds the common first-year spending commitment g* that maximizes:
        g - (lambda/S) * sum(sigma_s)
    subject to sigma_s >= g - basis_s, sigma_s >= 0, 0 <= g <= max(bases).

    Parameters
    ----------
    bases : array-like
        Optimal spending basis (today's dollars) for each scenario.
    lam : float
        Risk-aversion parameter. lambda=0 -> risk-neutral (max spending).
        lambda->inf -> maximin (worst-case optimal).

    Returns
    -------
    g_opt : float
        Optimal committed spending (today's dollars).
    expected_shortfall : float
        Mean shortfall across scenarios (today's dollars).
    shortfall_prob : float
        Fraction of scenarios with shortfall > $1.
    """
    bases = np.asarray(bases, dtype=float)
    S = len(bases)
    if S < 1:
        raise ValueError("bases must contain at least one scenario.")

    c = np.concatenate([[-1.0], np.full(S, lam / S)])

    A_ub = np.zeros((S, 1 + S))
    A_ub[:, 0] = 1.0
    A_ub[np.arange(S), 1 + np.arange(S)] = -1.0
    b_ub = bases

    bounds = [(0.0, float(bases.max()))] + [(0.0, None)] * S

    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if result.status != 0:
        raise RuntimeError(f"Stochastic LP failed (lambda={lam}): {result.message}")

    g_opt = result.x[0]
    sigmas = result.x[1:]
    expected_shortfall = float(sigmas.mean())
    shortfall_prob = float((sigmas > 0).mean())
    return g_opt, expected_shortfall, shortfall_prob


def _compute_efficient_frontier(bases, n_points=60):
    """
    Sweep lambda and compute the Pareto frontier between spending and shortfall risk.

    Parameters
    ----------
    bases : array-like
        Optimal spending basis per scenario (today's dollars).
    n_points : int
        Number of lambda values to evaluate.

    Returns
    -------
    lambdas : ndarray, shape (n_points+1,)
    frontier_g : ndarray, shape (n_points+1,)  — committed spending
    frontier_prob : ndarray, shape (n_points+1,) — shortfall probability
    frontier_shortfall : ndarray, shape (n_points+1,) — expected shortfall
    """
    lambdas = np.concatenate([[0.0], np.logspace(-1, 3, n_points)])
    frontier_g, frontier_prob, frontier_shortfall = [], [], []
    for lam in lambdas:
        g, sf, prob = _stochastic_lp(bases, lam)
        frontier_g.append(g)
        frontier_prob.append(prob)
        frontier_shortfall.append(sf)
    return lambdas, np.array(frontier_g), np.array(frontier_prob), np.array(frontier_shortfall)


def _validate_success_rate_pct(target_success_rate_pct):
    """Raise ValueError unless target_success_rate_pct is a percentage in (1, 100]."""
    if not (1 < target_success_rate_pct <= 100):
        hint = ""
        if 0 < target_success_rate_pct <= 1:
            hint = f" Did you mean {target_success_rate_pct * 100:g}?"
        raise ValueError(
            f"target_success_rate_pct must be a percentage in (1, 100] (e.g. 90 for 90%), "
            f"got {target_success_rate_pct}.{hint}"
        )


def g_for_success_rate(target_success_rate_pct, lambdas, frontier_g, frontier_prob):
    """
    Return (g_opt, lam) for the least conservative lambda that achieves the target success rate.

    Parameters
    ----------
    target_success_rate_pct : float
        Desired percentage of scenarios with no shortfall, in (1, 100] (e.g. 90 for 90%).
    lambdas : ndarray
        Lambda values from _compute_efficient_frontier.
    frontier_g : ndarray
        Committed spending at each lambda.
    frontier_prob : ndarray
        Shortfall probability at each lambda (non-increasing).

    Returns
    -------
    g_opt : float
    lam : float
    """
    _validate_success_rate_pct(target_success_rate_pct)
    target_shortfall_prob = 1.0 - target_success_rate_pct / 100.0
    candidates = np.where(frontier_prob <= target_shortfall_prob)[0]
    if len(candidates) == 0:
        return float(frontier_g[-1]), float(lambdas[-1])
    idx = candidates[0]
    return float(frontier_g[idx]), float(lambdas[idx])


def compute_cvar(bases, frontier_g, frontier_prob, floor):
    """
    Floor-capped CVaR at each point on the efficient frontier.

    Each scenario's shortfall contribution is capped at (g* - floor),
    bounding heavy tails in MC ensembles and giving standard CVaR for
    historical runs where floor = HSF = min(bases).

    Parameters
    ----------
    bases : ndarray (S,)    — per-scenario optimal spending basis
    frontier_g : ndarray    — committed spending g* at each frontier point
    frontier_prob : ndarray — shortfall probability at each frontier point
    floor : float           — spending floor (HSF, SSF, or custom)

    Returns
    -------
    frontier_cvar : ndarray — floor-capped CVaR at each frontier point
    """
    bases = np.asarray(bases, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.array(
            [
                float(np.maximum(0.0, g_star - np.maximum(floor, bases)).mean()) / prob if prob > 0 else 0.0
                for g_star, prob in zip(frontier_g, frontier_prob, strict=True)
            ]
        )


def compute_res(frontier_g, frontier_prob, frontier_cvar, floor, target_success_rate_pct):
    """
    Retirement Efficiency Score at each frontier point and summary statistics.

    Parameters
    ----------
    frontier_g : ndarray    — committed spending at each frontier point
    frontier_prob : ndarray — shortfall probability at each frontier point
    frontier_cvar : ndarray — floor-capped CVaR (from compute_cvar)
    floor : float           — spending floor used in CVaR computation
    target_success_rate_pct : float — user-chosen success rate ρ as a percentage in
        (1, 100] (e.g. 85 for 85%)

    Returns
    -------
    dict with keys:
        "res_values"     : ndarray — RES at each frontier point (nan where undefined)
        "rho_star_pct"   : float   — success rate (%) at RES maximum
        "res_star"       : float   — maximum RES value
        "cvar_star"      : float   — CVaR at rho_star_pct
        "cvar_at_target" : float   — CVaR at target_success_rate_pct
    Returns None when no valid RES point exists.
    """
    _validate_success_rate_pct(target_success_rate_pct)
    valid = (frontier_cvar > 0) & (frontier_g > floor)
    safe_cvar = np.where(frontier_cvar > 0, frontier_cvar, 1.0)
    res_values = np.where(valid, (frontier_g - floor) / safe_cvar, np.nan)
    if not np.any(valid):
        return None
    rho_star_idx = int(np.nanargmax(res_values))
    target_idx = int(np.searchsorted(-frontier_prob, -(1.0 - target_success_rate_pct / 100.0)))
    target_idx = min(target_idx, len(frontier_cvar) - 1)
    return {
        "res_values": res_values,
        "rho_star_pct": 100.0 * (1.0 - float(frontier_prob[rho_star_idx])),
        "res_star": float(res_values[rho_star_idx]),
        "cvar_star": float(frontier_cvar[rho_star_idx]),
        "cvar_at_target": float(frontier_cvar[target_idx]),
    }


###############################################################################
# Batch stress tests (Plan delegates from runHistoricalRange / runMC / runStochasticSpending)
###############################################################################


def summarize_year1(year1_list, inames):
    """
    Summarize the distribution of first-year decisions across scenarios.

    Consumes the "year1_decisions" list returned by run_stochastic_spending and
    produces a JSON-ready dict: per-person Roth-conversion and withdrawal
    distributions, household net-spending percentiles, and the modal top tax
    bracket. Only the first plan year is summarized — it holds the only decisions
    that are executed; later years are re-optimized as returns realize.

    Parameters
    ----------
    year1_list : list of dict or None
        Per-scenario first-year snapshots (None = infeasible/short-horizon).
    inames : list of str
        Individuals' names, in plan order.

    Returns
    -------
    dict with keys "n_scenarios", "n_infeasible", "per_person" (list),
    "net_spending", "top_bracket", "share_filled_to_boundary".
    """
    jnames = ("taxable", "tax_deferred", "roth", "hsa")
    feasible = [y for y in year1_list if y is not None]
    out = {
        "n_scenarios": len(year1_list),
        "n_infeasible": len(year1_list) - len(feasible),
        "per_person": [],
    }
    if not feasible:
        return out

    def _pctiles(a, digits=2):
        p10, p25, p50, p75, p90 = (float(np.round(v, digits)) for v in np.percentile(a, [10, 25, 50, 75, 90]))
        return {"p10": p10, "p25": p25, "median": p50, "p75": p75, "p90": p90,
                "mean": float(np.round(np.mean(a), digits))}

    for i, name in enumerate(inames):
        x = np.array([y["x"][i] for y in feasible])
        med = float(np.median(x))
        if med > 1.0:
            agreement = float(np.mean(np.abs(x - med) <= 0.10 * med))
        else:
            agreement = float(np.mean(x <= 1.0))  # agreement on "do not convert"
        n_j = len(feasible[0]["w"][i])
        wd = {}
        for j in range(min(n_j, len(jnames))):
            wj = np.array([y["w"][i][j] for y in feasible])
            wd[jnames[j]] = {
                "median": float(np.round(np.median(wj), 2)),
                "p10": float(np.round(np.percentile(wj, 10), 2)),
                "p90": float(np.round(np.percentile(wj, 90), 2)),
            }
        out["per_person"].append(
            {
                "person": name,
                "roth_conversion": {
                    **_pctiles(x),
                    "share_converting": float(np.round(np.mean(x > 1.0), 4)),
                    "share_within_10pct_of_median": float(np.round(agreement, 4)),
                },
                "withdrawals": wd,
            }
        )

    out["net_spending"] = _pctiles(np.array([y["g0"] for y in feasible]))
    tb = [y["top_bracket_pct"] for y in feasible if y["top_bracket_pct"] is not None]
    if tb:
        vals, counts = np.unique(np.array(tb), return_counts=True)
        k = int(np.argmax(counts))
        out["top_bracket"] = {
            "modal_rate_pct": float(vals[k]),
            "frequency": float(np.round(counts[k] / len(tb), 4)),
        }
    fb = [y["filled_to_boundary"] for y in feasible if y["filled_to_boundary"] is not None]
    if fb:
        out["share_filled_to_boundary"] = float(np.round(np.mean(fb), 4))
    return out


###############################################################################
# Commitment regret sweep
###############################################################################


def _regret_objective_value(p, objective):
    """Scenario outcome in the objective's natural units (today's $).

    maxSpending: the first-year spending basis ($/yr). maxBequest: the after-tax
    value of the final savings estate (excludes fixed assets such as a home,
    which are invariant to the decisions under study).
    """
    if objective == "maxSpending":
        return float(p.basis)
    from .export import plan_metrics  # local import; export pulls heavy deps

    return float(plan_metrics(p)["final_bequest_savings_today"])


# Ceiling on the MIP gap for any regret sweep. See the note in run_conversion_regret_sweep.
REGRET_MAX_GAP = 1e-6

_MILP_TAX_MODES = ("withMedicare", "withACA", "withSSTaxability", "withLTCG", "withNIIT")


def _downgrade_milp_tax_modes(options):
    """
    Flip MILP tax modes to their self-consistent loop equivalents.

    Regret is a difference of two optima computed under the same model, so a loop-mode
    approximation shifts the clairvoyant optimum and the pinned outcome together and the
    difference largely survives. The downgrade must therefore be applied to every solve of
    a sweep or to none of them: a MIP baseline measured against loop-mode pins would put a
    modeling difference into the regret itself.

    withSSAges is deliberately left alone: it selects a claiming age rather than
    linearizing a tax schedule, and has no loop equivalent.

    Returns (options, downgraded) where downgraded names the keys that were changed.
    """
    opts = dict(options)
    downgraded = []
    for key in _MILP_TAX_MODES:
        if str(opts.get(key, "")).lower() == "optimize":
            opts[key] = "loop"
            downgraded.append(key)
    return opts, downgraded


def _regret_baseline_worker(args):
    """
    Phase A: solve one scenario's unconstrained (clairvoyant) baseline.

    The plan clone is mutated in place - its rates are set here and left set - so that
    _regret_pin_worker() can reuse it without re-deriving the scenario.

    args tuple: (clone, year, objective, options, person)

    Returns (year, payload) where payload is None if the baseline failed to solve, else a
    dict with the clairvoyant optimum v_star, that scenario's own first-year conversion
    x_star, and the convergence diagnostics of the solve.
    """
    p, year, objective, options, person = args

    # Workers are reused across windows, so the thread name alone would say which slot
    # logged a line, not which window it was solving.
    with log.threadLabel(year):
        p.setRates("historical", year)
        p.solve(objective, options)
        if p.caseStatus != "solved":
            return year, None
        v_star = _regret_objective_value(p, objective)
        conv = getattr(p, "convergenceType", "undefined")
        return year, {
            "v_star": v_star,
            "x_star": float(p.x_in[person, 0]),
            # Dollar amplitude of this optimum's SC-loop oscillation (0 if monotonic).
            "v_star_osc": abs(v_star) * getattr(p, "oscillationRel", 0.0),
            "v_star_conv": conv,
            "max_gap": getattr(p, "solverGap", -1.0),
            "n_nonmonotonic": int(conv != "monotonic"),
        }


def _regret_pin_worker(args):
    """
    Phase B: pin one scenario's first-year Roth conversion at each grid value, then
    optionally solve it once more with conversions disallowed altogether.

    Expects a clone whose rates were already set by _regret_baseline_worker(), so the
    scenario is not re-derived.

    args tuple: (clone, year, objective, options, grid, person, include_never_convert)

    Returns (year, payload) with v_at (aligned with grid, None where the pinned solve is
    infeasible), v_noconv, and this phase's convergence diagnostics.
    """
    import time as _time

    p, year, objective, options, grid, person, include_never_convert = args

    with log.threadLabel(year):
        _t0 = _time.time()
        # Track SC-loop convergence: monotonic solves land in the interior of the bracket
        # structure (trustworthy, idempotent); non-monotonic solves sit on a tax cliff
        # where the fixed point is ambiguous and the result carries a genuine error bar.
        max_gap = -1.0
        n_nonmonotonic = 0

        def _note():
            nonlocal n_nonmonotonic, max_gap
            max_gap = max(max_gap, getattr(p, "solverGap", -1.0))
            if getattr(p, "convergenceType", "undefined") != "monotonic":
                n_nonmonotonic += 1

        # myRothX_in holds the dollar amount and rothXfixed_in says it binds (see
        # _add_roth_conversion_constraints). A grid value of 0 needs no special case: it
        # pins year 1 to no conversion, leaving every later year free to re-optimize.
        v_at = []
        v_at_osc = []
        p.rothXfixed_in[person, 0] = True
        for x in grid:
            p.myRothX_in[person, 0] = float(x)
            p.solve(objective, options)
            _note()
            if p.caseStatus == "solved":
                val = _regret_objective_value(p, objective)
                v_at.append(val)
                v_at_osc.append(abs(val) * getattr(p, "oscillationRel", 0.0))
            else:
                v_at.append(None)
                v_at_osc.append(None)
        p.myRothX_in[person, 0] = 0.0
        p.rothXfixed_in[person, 0] = False

        v_noconv = None
        if include_never_convert:
            # Pin this person's conversion to zero in every year, rather than passing
            # options["noRothConversions"]. That option names a single individual, so on a
            # case that already excludes the *other* spouse it would replace the existing
            # exclusion instead of adding to it -- freeing that spouse and leaving the two
            # solves un-nested, which shows up as a negative regret. Pinning keeps the
            # never-convert solve a strict restriction of the baseline, so R >= 0 holds.
            p.rothXfixed_in[person, :] = True
            p.myRothX_in[person, :] = 0.0
            p.solve(objective, options)
            _note()
            if p.caseStatus == "solved":
                v_noconv = _regret_objective_value(p, objective)
            p.rothXfixed_in[person, :] = False

        p.mylog.print(
            f"window {year}: {_time.time() - _t0:.1f}s, {n_nonmonotonic} non-monotonic solve(s)"
        )
        return year, {
            "v_at": v_at,
            "v_at_osc": v_at_osc,
            "v_noconv": v_noconv,
            "max_gap": max_gap,
            "n_nonmonotonic": n_nonmonotonic,
        }


def _select_regret_years(years, n_scenarios, seed):
    """
    Choose which historical windows to sweep.

    Subsampling is always a seeded random draw, never a stride. Adjacent windows overlap
    heavily (lag-1 correlation of the regret curve is 0.8-0.92), so a stride lands on a
    correlated subsequence and biases the valley - measured at -$16k on a four-fold
    stride - whereas random draws of the same size are centred on the full-sample answer.
    """
    if n_scenarios is None or n_scenarios >= len(years):
        return list(years), None
    if n_scenarios < 2:
        raise ValueError("n_scenarios must be at least 2.")
    rng = np.random.default_rng(seed)
    picked = rng.choice(np.asarray(years), size=n_scenarios, replace=False)
    return sorted(int(y) for y in picked), seed


def _build_regret_grid(x_star, n_grid, pad):
    """
    Size the commitment grid from the observed distribution of scenario-optimal
    conversions, so no probe sweep is needed.

    The grid runs from zero to the largest scenario-optimal conversion plus `pad`, in
    n_grid equally spaced points. The padding keeps the over-conversion probes on-grid:
    were a probe to fall past the right edge it would be dropped, which silently takes the
    over- and under-conversion means over different scenario subsets.
    """
    finite = x_star[np.isfinite(x_star)]
    top = (float(np.max(finite)) if finite.size else 0.0) + float(pad)
    if top <= 0.0:
        top = float(pad) if pad > 0 else 1.0
    n_grid = max(int(n_grid), 2)
    return [float(round(top * k / (n_grid - 1))) for k in range(n_grid)]


def run_conversion_regret_sweep(
    plan,
    objective,
    options,
    grid,
    ystart,
    yend,
    *,
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

    The sweep runs in two phases. Phase A solves each historical scenario unconstrained,
    giving the clairvoyant benchmark v*_s and that scenario's own first-year conversion
    x*_s. The commitment grid is then sized from the observed spread of x*_s, so no
    separate probe run is needed. Phase B re-solves each scenario with the first-year
    conversion of individual `person` pinned at each grid value, leaving all later
    decisions free to re-optimize within the scenario; the regret of committing to x in
    scenario s is v*_s - v_s(x) >= 0. Optionally a never-convert solve (conversions
    disallowed for `person` in every year) measures the value of the whole conversion
    strategy, which is a different and much larger quantity than pinning year one to zero.

    Outcomes are in the objective's natural units, today's dollars: first-year spending
    basis ($/yr) for maxSpending, after-tax final savings estate for maxBequest (which
    requires options["netSpending"]). For a couple, only `person`'s conversion is pinned;
    the spouse's remains free.

    Cost is n_scenarios x (len(grid) + 2) full-horizon optimizations.

    Args:
      grid: list of committed amounts in dollars, or None to size it automatically from
        the phase-A x*_s distribution using n_grid points and grid_pad of headroom.
      n_scenarios: sweep a seeded random subset of the windows in [ystart, yend] rather
        than all of them. Halving the grid costs about $2k of valley location; halving the
        scenarios costs $10-35k, so cut the grid first.
      seed: seed for that draw; recorded in the result so a run is reproducible.
      milp_downgrade: solve every scenario with the MILP tax modes flipped to loop mode
        (see _downgrade_milp_tax_modes). Must never be combined with a looser `gap`: the
        regret near the valley is of order 1e-3 of the objective, below a loose MIP gap.
      on_scenario: optional callback(phase, completed, total, partial) invoked as
        scenarios complete, where phase is "baseline" or "pinned" and partial carries the
        mean regret curve over the scenarios finished so far. Intended for live preview.

    Returns a dict:
      "grid"        - list of committed amounts ($)
      "start_years" - ndarray (S,) of scenario starting years actually swept
      "v_star"      - ndarray (S,) clairvoyant optima; NaN if the baseline failed
      "x_star"      - ndarray (S,) baseline first-year conversions ($)
      "v_at"        - ndarray (S, X); NaN where the pinned solve was infeasible
      "v_noconv"    - ndarray (S,) or None
      "max_gap"     - ndarray (S,) largest achieved MIP gap per scenario (-1 when no MIP
                      was involved; values above the requested gap flag solves whose
                      certificate was degraded by the time limit)
      "person"      - the pinned individual's index
      "seed", "n_scenarios_requested", "milp_downgraded", "solver_gap" - provenance of
                      the run; solver_gap is the tolerance actually used, which is capped
                      at REGRET_MAX_GAP whatever the caller asked for

    Summarize with summarize_conversion_regret().
    """
    if yend + plan.N_n > plan.year_n[0]:
        yend = plan.year_n[0] - plan.N_n
        plan.mylog.print(f"Upper bound for year range re-adjusted to {yend}.", tag="WARNING")
    if yend < ystart:
        raise ValueError(f"Starting year is too large to support a lifespan of {plan.N_n} years.")
    if not (0 <= person < plan.N_i):
        raise ValueError(f"person={person} out of range for {plan.N_i} individual(s).")
    if grid is not None:
        grid = [float(x) for x in grid]
        if not grid or any(x < 0 for x in grid):
            raise ValueError("grid must be a non-empty list of non-negative dollar amounts.")

    years, used_seed = _select_regret_years(range(ystart, yend + 1), n_scenarios, seed)
    total = len(years)

    options, downgraded = _downgrade_milp_tax_modes(options) if milp_downgrade else (dict(options), [])
    if downgraded:
        plan.mylog.print(f"Regret sweep: {', '.join(downgraded)} solved in loop mode.", tag="INFO")

    # Solver tolerance is never a cost lever here. Regret near the valley is of order 1e-3
    # of the objective - smaller than the MIP gap Owl adopts by default when a tax mode is
    # optimized (30x GAP, and 10x that again for a small conversion cap), and smaller still
    # than a hand-loosened one. At those tolerances the second-order over- and
    # under-conversion regrets are inflated several-fold by slack rather than by the
    # decision under study, so the sweep tightens the gap instead of inheriting it. Inert
    # on a pure LP, where the gap is meaningless.
    prev_gap = u.get_numeric_option(options, "gap", None) if "gap" in options else None
    if prev_gap is None or prev_gap > REGRET_MAX_GAP:
        options["gap"] = REGRET_MAX_GAP
        if prev_gap is not None:
            plan.mylog.print(
                f"Regret sweep: tightening solver gap from {prev_gap:.1e} to {REGRET_MAX_GAP:.1e}; "
                "a looser tolerance would be larger than the regret being measured.",
                tag="WARNING",
            )

    plan.mylog.setVerbose(False)
    if progcall is None:
        progcall = progress.Progress(plan.mylog)

    # Progress spans both phases: S baselines followed by S pinned sweeps.
    nsteps = 2 * total
    completed = 0
    progcall.start()

    def _tick(phase, partial=None):
        nonlocal completed
        completed += 1
        progcall.show(completed, nsteps)
        if on_scenario is not None:
            on_scenario(phase, completed if phase == "baseline" else completed - total, total, partial)

    n_workers = min(os.cpu_count() or 1, total)

    # --- Phase A: clairvoyant baselines -------------------------------------------------
    # Clones are kept alive and reused by phase B, so each scenario's rates are derived once.
    clones = {year: clone(plan, verbose=False) for year in years}
    plan.mylog.print(f"Regret sweep phase 1/2: {total} baselines using {n_workers} worker thread(s).")

    base_map = {}
    with ThreadPoolExecutor(max_workers=n_workers, thread_name_prefix="regret") as executor:
        futures = {
            executor.submit(_regret_baseline_worker, (clones[year], year, objective, options, person)): year
            for year in years
        }
        for fut in as_completed(futures):
            year = futures[fut]
            try:
                base_map[year] = fut.result()[1]
            except Exception as exc:
                plan.mylog.print(
                    f"scenario {year} raised {type(exc).__name__}: {exc}; treating as failed baseline.",
                    tag="WARNING",
                )
                base_map[year] = None
            _tick("baseline")

    S = total
    v_star = np.full(S, np.nan)
    x_star = np.full(S, np.nan)
    max_gap = np.full(S, -1.0)
    n_nonmonotonic = np.zeros(S, dtype=int)
    v_star_conv = ["undefined"] * S
    v_star_osc = np.zeros(S)
    for i, year in enumerate(years):
        r = base_map.get(year)
        if r is None:
            continue
        v_star[i] = r["v_star"]
        x_star[i] = r["x_star"]
        v_star_osc[i] = r["v_star_osc"]
        v_star_conv[i] = r["v_star_conv"]
        max_gap[i] = r["max_gap"]
        n_nonmonotonic[i] = r["n_nonmonotonic"]

    if grid is None:
        grid = _build_regret_grid(x_star, n_grid, grid_pad)
        plan.mylog.print(f"Commitment grid: {len(grid)} points up to ${grid[-1]:,.0f}.")

    X = len(grid)
    v_at = np.full((S, X), np.nan)
    v_at_osc = np.full((S, X), np.nan)
    v_noconv = np.full(S, np.nan) if include_never_convert else None

    # --- Phase B: pinned commitments ----------------------------------------------------
    live = [year for year in years if base_map.get(year) is not None]
    plan.mylog.print(
        f"Regret sweep phase 2/2: {len(live)} scenarios x {X} grid points "
        f"using {n_workers} worker thread(s)."
    )
    index_of = {year: i for i, year in enumerate(years)}
    pin_map = {}
    with ThreadPoolExecutor(max_workers=n_workers, thread_name_prefix="regret") as executor:
        futures = {
            executor.submit(
                _regret_pin_worker,
                (clones[year], year, objective, options, grid, person, include_never_convert),
            ): year
            for year in live
        }
        for fut in as_completed(futures):
            year = futures[fut]
            try:
                pin_map[year] = fut.result()[1]
            except Exception as exc:
                plan.mylog.print(
                    f"scenario {year} raised {type(exc).__name__}: {exc}; dropping its pinned solves.",
                    tag="WARNING",
                )
                pin_map[year] = None
            r = pin_map.get(year)
            if r is not None:
                i = index_of[year]
                for j, v in enumerate(r["v_at"]):
                    if v is not None:
                        v_at[i, j] = v
                for j, o in enumerate(r["v_at_osc"]):
                    if o is not None:
                        v_at_osc[i, j] = o
                if include_never_convert and r["v_noconv"] is not None:
                    v_noconv[i] = r["v_noconv"]
                max_gap[i] = max(max_gap[i], r["max_gap"])
                n_nonmonotonic[i] += r["n_nonmonotonic"]
            # The partial mean is unbiased only because completion order is roughly random;
            # it is labelled "n of S" wherever it is drawn.
            partial = None
            if on_scenario is not None:
                with warnings.catch_warnings():
                    # Columns past the infeasibility onset are all-NaN by design.
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    R = v_star[:, None] - v_at
                    done = ~np.isnan(R).all(axis=1)
                    partial = {
                        "grid": list(grid),
                        "n_done": int(done.sum()),
                        "mean": np.nanmean(R[done], axis=0).tolist() if done.any() else None,
                    }
            _tick("pinned", partial)

    # Scenarios whose baseline failed never entered phase B; skip their progress ticks.
    for _ in range(total - len(live)):
        _tick("pinned")

    progcall.finish()
    plan.mylog.resetVerbose()

    n_failed = int(np.isnan(v_star).sum())
    if n_failed:
        plan.mylog.print(f"{n_failed} of {total} scenario baselines failed to solve.", tag="WARNING")

    return {
        "grid": grid,
        "start_years": np.array(years),
        "v_star": v_star,
        "x_star": x_star,
        "v_at": v_at,
        "v_noconv": v_noconv,
        "max_gap": max_gap,
        "n_nonmonotonic": n_nonmonotonic,
        "v_star_conv": v_star_conv,
        "v_star_osc": v_star_osc,
        "v_at_osc": v_at_osc,
        "person": person,
        "seed": used_seed,
        "n_scenarios_requested": n_scenarios,
        "milp_downgraded": downgraded,
        "solver_gap": options["gap"],
    }


def summarize_conversion_regret(
    result,
    *,
    asymmetry_deltas=(15_000, 30_000, 45_000),
    bootstrap=400,
    bootstrap_seed=12345,
    band_frac=0.02,
):
    """
    Summarize a run_conversion_regret_sweep() result into a JSON-ready dict.

    Reports, per grid point, the distribution of regret R_s(x) = v*_s - v_s(x)
    across scenarios (mean, median, p90, max, and the count of scenarios where
    the commitment is infeasible), the valley (grid argmin of mean regret), the
    value of the entire conversion strategy (regret of never converting), and
    the over/under asymmetry: mean regret of committing delta above vs below
    each scenario's own optimum x*_s, interpolated on the grid.
    """
    grid = np.array(result["grid"])
    v_star = result["v_star"]
    ok = ~np.isnan(v_star)
    R = v_star[ok, None] - result["v_at"][ok, :]
    x_star = result["x_star"][ok]
    n_scenarios = int(ok.sum())

    def _stats(r):
        good = r[~np.isnan(r)]
        if good.size == 0:
            return {"mean": None, "median": None, "p90": None, "max": None,
                    "n_infeasible": int(np.isnan(r).sum())}
        return {
            "mean": float(np.round(good.mean(), 2)),
            "median": float(np.round(np.median(good), 2)),
            "p90": float(np.round(np.percentile(good, 90), 2)),
            "max": float(np.round(good.max(), 2)),
            "n_infeasible": int(np.isnan(r).sum()),
        }

    # Oscillation error bar on the regret at each grid point. R = v* - v(x); both
    # ends oscillate independently under the SC loop, so the per-scenario amplitude
    # is the sum of their dollar amplitudes. Report the mean across scenarios — a
    # genuine intrinsic error bar, distinct from (and invisible to) cross-solver.
    vso = result.get("v_star_osc")
    vao = result.get("v_at_osc")
    by_grid = []
    for j, x in enumerate(grid):
        entry = {"x": float(x), **_stats(R[:, j])}
        if vso is not None and vao is not None:
            amp = np.asarray(vso)[ok] + np.asarray(vao)[ok, j]
            entry["regret_osc_bar"] = float(np.round(np.nanmean(amp), 2))
        by_grid.append(entry)
    means = np.array([g["mean"] if g["mean"] is not None else np.inf for g in by_grid])
    j_valley = int(np.argmin(means))

    # Asymmetry around each scenario's own optimum, via linear interpolation of
    # that scenario's regret curve. Under-conversion is floored at x=0; deltas
    # that fall beyond the grid's right edge are skipped (not extrapolated).
    asymmetry = []
    for delta in asymmetry_deltas:
        over, under = [], []
        for s in range(n_scenarios):
            r = R[s, :]
            if np.isnan(r).any():
                # Interpolate only across the feasible prefix of the curve.
                feas = ~np.isnan(r)
                gr, rr = grid[feas], r[feas]
            else:
                gr, rr = grid, r
            if gr.size < 2:
                continue
            if x_star[s] + delta <= gr[-1]:
                over.append(np.interp(x_star[s] + delta, gr, rr))
            under.append(np.interp(max(x_star[s] - delta, 0.0), gr, rr))
        entry = {"delta": float(delta), "n_over": len(over), "n_under": len(under)}
        entry["mean_regret_over"] = float(np.round(np.mean(over), 2)) if over else None
        entry["mean_regret_under"] = float(np.round(np.mean(under), 2)) if under else None
        if over and under and np.mean(under) > 0:
            entry["over_under_ratio"] = float(np.round(np.mean(over) / np.mean(under), 1))
        else:
            entry["over_under_ratio"] = None
        asymmetry.append(entry)

    gaps = result.get("max_gap")
    nnm = result.get("n_nonmonotonic")
    vsc = result.get("v_star_conv")
    convergence = None
    if nnm is not None and vsc is not None:
        nnm_ok = np.asarray(nnm)[ok]
        vsc_ok = [c for c, k in zip(vsc, ok) if k]
        convergence = {
            # windows whose clairvoyant baseline converged monotonically (interior of
            # the bracket structure — cleanest)
            "n_monotonic_baselines": int(sum(c == "monotonic" for c in vsc_ok)),
            # windows with any non-monotonic-APPROACH solve (wiggled during the loop but
            # may still have settled within tolerance — NOT necessarily an error bar)
            "n_windows_nonmonotonic": int(np.sum(nnm_ok > 0)),
            "share_clean": float(np.round(np.mean([c == "monotonic" for c in vsc_ok]), 4)) if vsc_ok else None,
        }
        # Every window carries a within-run oscillation bar; most are exactly 0 (the loop
        # settled). This counts how many are NON-ZERO (material) and summarizes their size.
        vso = result.get("v_star_osc")
        vao = result.get("v_at_osc")
        if vso is not None:
            osc = np.asarray(vso)[ok]
            nonzero = osc > 1.0
            if vao is not None:
                nonzero = nonzero | (np.nanmax(np.asarray(vao)[ok], axis=1) > 1.0)
            osc_nz = osc[osc > 1.0]
            convergence["n_windows_nonzero_bar"] = int(np.sum(nonzero))
            convergence["v_star_osc_median_nonzero"] = float(np.round(np.median(osc_nz), 2)) if osc_nz.size else 0.0
            convergence["v_star_osc_p90_nonzero"] = (
                float(np.round(np.percentile(osc_nz, 90), 2)) if osc_nz.size else 0.0
            )
            convergence["v_star_osc_max"] = float(np.round(osc.max(), 2))
    out = {
        "n_scenarios": n_scenarios,
        "n_failed_baselines": int((~ok).sum()),
        "max_achieved_gap": None if gaps is None else float(np.max(gaps)),
        "convergence": convergence,
        "x_star": {
            "p10": float(np.round(np.percentile(x_star, 10), 2)),
            "median": float(np.round(np.median(x_star), 2)),
            "p90": float(np.round(np.percentile(x_star, 90), 2)),
            "share_converting": float(np.round(np.mean(x_star > 1.0), 4)),
        },
        "regret_by_grid": by_grid,
        "valley": {"x": float(grid[j_valley]), "mean_regret": by_grid[j_valley]["mean"]},
        "asymmetry": asymmetry,
    }
    if result["v_noconv"] is not None:
        r_nc = v_star[ok] - result["v_noconv"][ok]
        out["never_convert_regret"] = _stats(r_nc)

    # Bootstrap over the scenario axis. Costs no solves: it resamples the (S, X) regret
    # array that has already been computed. Scenario sampling, not solver noise, is the
    # dominant uncertainty here - halving the scenarios moves the valley by $10-35k while
    # the tax-loop oscillation bar is worth tens of dollars - so this is what turns a
    # cheap preset from an approximation into an honest one.
    nc_mean = out.get("never_convert_regret", {}).get("mean")
    out.update(_regret_bootstrap(R, grid, means, j_valley, by_grid, nc_mean, bootstrap, bootstrap_seed, band_frac))
    return out


def _regret_bootstrap(R, grid, means, j_valley, by_grid, nc_mean, n_boot, seed, band_frac):
    """
    Resample the scenario axis of the regret array to put confidence intervals on the
    mean curve and on the valley location, and derive the readouts that depend on them.

    Returns a dict of keys to merge into the summary:
      "valley_ci"        - 80% interval on the argmin location ($)
      "mean_ci_by_grid"  - 80% interval on the mean regret at each grid point
      "resolution_floor" - the height below which curve features are not distinguishable,
                           taken as the larger of the bootstrap half-width at the valley
                           and the worst SC-loop oscillation bar
      "valley_resolvable"- False when the curve is flat within that floor, or when the
                           valley location is no better determined than half the grid
      "commit_band"      - the span of commitments costing no more than band_frac of the
                           value of converting at all; the primary readout, and the most
                           stable statistic in the sweep
      "value_of_converting" / "pct_axis_ok" - the never-convert regret and whether it is
                           large enough to normalize against (it can be ~0 or negative
                           under maxSpending, where dividing by it is meaningless)
    """
    grid = np.asarray(grid, dtype=float)
    n, X = R.shape
    span = float(grid[-1] - grid[0]) if X > 1 else 0.0
    outb = {}

    boot_lo = boot_hi = None
    valley_half = 0.0
    if n >= 2 and n_boot and n_boot > 0:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, n, size=(int(n_boot), n))
        with warnings.catch_warnings():
            # All-NaN columns are expected past the over-conversion infeasibility onset.
            warnings.simplefilter("ignore", category=RuntimeWarning)
            curves = np.nanmean(R[idx], axis=1)
            usable = ~np.isnan(curves).all(axis=1)
            curves = curves[usable]
            if curves.size:
                boot_lo, boot_hi = np.nanpercentile(curves, [10, 90], axis=0)
                vx = grid[np.nanargmin(np.where(np.isnan(curves), np.inf, curves), axis=1)]
                v_lo, v_hi = (float(v) for v in np.percentile(vx, [10, 90]))
                outb["valley_ci"] = {"p10": round(v_lo, 2), "p90": round(v_hi, 2),
                                     "n_boot": int(curves.shape[0])}
                valley_half = 0.5 * float(boot_hi[j_valley] - boot_lo[j_valley])

    if boot_lo is not None:
        outb["mean_ci_by_grid"] = [
            {"x": float(grid[j]),
             "p10": None if np.isnan(boot_lo[j]) else float(np.round(boot_lo[j], 2)),
             "p90": None if np.isnan(boot_hi[j]) else float(np.round(boot_hi[j], 2))}
            for j in range(X)
        ]

    osc_bars = [g.get("regret_osc_bar", 0.0) or 0.0 for g in by_grid]
    floor = max(valley_half, max(osc_bars) if osc_bars else 0.0)

    # Regret is non-negative by construction: pinning the first year is a restriction of the
    # unconstrained problem, so v(x) <= v*. Any negative value is therefore a direct
    # measurement of the method's own error - chiefly the self-consistent tax loop settling on
    # a different fixed point for the constrained and unconstrained solves. It is deterministic
    # and survives an arbitrarily tight solver gap, so it must be read off the data rather than
    # inferred from the solver.
    finite_R = R[np.isfinite(R)]
    if finite_R.size:
        worst_cell = float(min(finite_R.min(), 0.0))
        # Cell-level error averages down across scenarios, so the mean curve carries
        # |worst cell| / sqrt(n). A negative mean is noise at face value.
        n_eff = max(int(np.isfinite(R).any(axis=1).sum()), 1)
        floor = max(floor, abs(worst_cell) / np.sqrt(n_eff))
    finite_means = means[np.isfinite(means)]
    if finite_means.size:
        floor = max(floor, abs(min(float(finite_means.min()), 0.0)))
    outb["resolution_floor"] = float(np.round(floor, 2))

    finite = means[np.isfinite(means)]
    curve_range = float(finite.max() - finite.min()) if finite.size else 0.0
    ci = outb.get("valley_ci")
    well_located = ci is None or span <= 0 or (ci["p90"] - ci["p10"]) <= 0.5 * span

    # A wide curve is not the same as a located minimum. What matters is whether the bottom is
    # a point or a plateau: when many grid values sit within the floor of the lowest, naming one
    # of them as "the" best commitment is false precision, however steeply the curve rises
    # elsewhere.
    n_flat = int(np.sum(finite <= finite.min() + floor)) if finite.size else 0
    plateau_limit = max(2, len(grid) // 3)
    outb["n_within_floor"] = n_flat
    outb["valley_resolvable"] = bool(curve_range > floor and well_located and n_flat <= plateau_limit)

    # A minimum sitting on the last grid point is not bracketed: the curve was still
    # falling where the grid ran out, so the answer is "at least this much", not "this
    # much". The left edge is different -- zero is a real boundary, since a conversion
    # cannot be negative -- so only the right edge is flagged.
    outb["valley_at_grid_edge"] = bool(j_valley == len(grid) - 1 and len(grid) > 1)

    # The percentage axis is normalized by the value of converting at all. That is large
    # and stable under maxBequest but can be ~0 or negative under maxSpending, where the
    # normalization would be meaningless or sign-flipped.
    outb["value_of_converting"] = None if nc_mean is None else float(nc_mean)
    # Normalizing by the value of converting only means something when that value stands clear
    # of the floor; at 2-3x it the percentages carry an error bar as large as the readings.
    outb["pct_axis_ok"] = bool(nc_mean is not None and nc_mean > 0 and nc_mean > 3.0 * max(floor, 0.0))

    if outb["pct_axis_ok"] and np.isfinite(means[j_valley]):
        theta = float(band_frac) * float(nc_mean)
        cutoff = means[j_valley] + theta
        lo = hi = j_valley
        while lo - 1 >= 0 and np.isfinite(means[lo - 1]) and means[lo - 1] <= cutoff:
            lo -= 1
        while hi + 1 < X and np.isfinite(means[hi + 1]) and means[hi + 1] <= cutoff:
            hi += 1
        outb["commit_band"] = {
            "x_lo": float(grid[lo]),
            "x_hi": float(grid[hi]),
            "threshold": float(np.round(theta, 2)),
            "band_frac": float(band_frac),
        }
    return outb


def run_historical_range(
    plan,
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
    """
    Run historical scenarios on plan over a range of years.

    For each year in [ystart, yend], rates are set to the historical sequence
    starting at that year.

    If augmented is False, only (reverse=False, roll=0) is used (one run per year).
    If augmented is True, every (reverse, roll) in {False, True} x {0, ..., N_n-1}
    is run for each year, expanding the sample for the histogram.

    If log_x is True, the result histogram uses log-spaced bins and a log-scale x-axis.

    When not augmented, a bar chart of spending/bequest by historical start year is also
    produced alongside the histogram.
    """
    if yend + plan.N_n > plan.year_n[0]:
        yend = plan.year_n[0] - plan.N_n
        plan.mylog.print(f"Upper bound for year range re-adjusted to {yend}.", tag="WARNING")

    if yend < ystart:
        raise ValueError(f"Starting year is too large to support a lifespan of {plan.N_n} years.")

    n_years = yend - ystart + 1
    if augmented:
        reverse_roll_pairs = list(product([False, True], range(plan.N_n)))
        N = n_years * len(reverse_roll_pairs)
        plan.mylog.vprint(
            f"Running historical range from {ystart} to {yend} (augmented: {len(reverse_roll_pairs)}"
            f" variants per year, {N} runs)."
        )
    else:
        reverse_roll_pairs = [(reverse, roll)]
        N = n_years
        plan.mylog.vprint(f"Running historical range from {ystart} to {yend}.")

    plan.mylog.setVerbose(verbose)

    if objective == "maxSpending":
        columns = ["partial", objective]
    elif objective == "maxBequest":
        columns = ["partial", "final"]
    else:
        plan.mylog.print(f"Invalid objective '{objective}'.")
        raise ValueError(f"Invalid objective '{objective}'.")

    df = pd.DataFrame(columns=columns)

    if progcall is None:
        progcall = progress.Progress(plan.mylog)

    if not verbose:
        progcall.start()

    step = 0
    start_years_list = []
    values_list = []
    for year in range(ystart, yend + 1):
        for rev, rll in reverse_roll_pairs:
            plan.setRates("historical", year, reverse=rev, roll=rll)
            plan.solve(objective, options)
            if not verbose:
                step += 1
                progcall.show(step, N)
            if plan.caseStatus == "solved":
                if objective == "maxSpending":
                    df.loc[len(df)] = [plan.partialBequest, plan.basis]
                    if not augmented:
                        start_years_list.append(year)
                        values_list.append(plan.basis)
                elif objective == "maxBequest":
                    df.loc[len(df)] = [plan.partialBequest, plan.bequest]
                    if not augmented:
                        start_years_list.append(year)
                        values_list.append(plan.bequest)

    progcall.finish()
    plan.mylog.resetVerbose()

    fig, description = plan._plotter.plot_histogram_results(
        objective, df, N, plan.year_n, plan.n_d, plan.N_i, plan.phi_j, log_x=log_x
    )
    _prependObjectiveConstraint(description, objective, options)
    plan.mylog.print(description.getvalue())

    fig2 = None
    if not augmented and len(start_years_list) > 0:
        fig2, _ = plan._plotter.plot_spending_by_year(
            objective, np.array(start_years_list), np.array(values_list), plan.n_d, plan.year_n
        )

    if figure:
        return fig, description.getvalue(), fig2

    return N, df


# The statistics below the constraint line are printed as f"{lead:>12}: {field:>16} {value}",
# which puts every dollar figure at this column. The constraint label is padded to match so
# that all the amounts line up. Keep any new label shorter than this to avoid pushing its
# own value out of the column.
_SUMMARY_VALUE_COLUMN = 31


def _prependObjectiveConstraint(description, objective, options):
    """
    Put the constraint accompanying the objective at the top of the summary.

    Maximizing net spending holds the savings bequest fixed, and maximizing bequest
    holds net spending fixed. The distribution of results across scenarios only reads
    correctly next to the value that was held fixed while producing it.
    """
    if objective == "maxSpending":
        value = u.get_monetary_option(options, "bequest", 0)
        label = "Savings bequest constraint:"
    else:
        value = u.get_monetary_option(options, "netSpending", 0)
        label = "Net spending constraint:"
    line = f"{label:<{_SUMMARY_VALUE_COLUMN}}{u.d(value)}"

    body = description.getvalue()
    description.seek(0)
    description.truncate(0)
    description.write(f"{line}\n{body}")


MC_TIME_LIMIT = 120  # per-scenario solver time limit for MC runs (overrides the single-run default)


def run_mc(plan, objective, options, N, *, verbose=False, figure=False, progcall=None, log_x=False):
    """
    Run Monte Carlo simulations on plan.
    """
    if not hasattr(plan, "rateModel") or plan.rateModel is None or getattr(plan.rateModel, "deterministic", True):
        plan.mylog.print("Monte Carlo simulations require a stochastic rate method.")
        return

    plan.mylog.vprint(f"Running {N} Monte Carlo simulations.")
    plan.mylog.setVerbose(verbose)

    # Use a shorter per-scenario time limit so a single hard MILP instance cannot stall
    # the entire MC run for the full single-run TIME_LIMIT. Callers can override via options.
    myoptions = dict(options)
    if "maxTime" not in myoptions:
        myoptions["maxTime"] = MC_TIME_LIMIT

    if objective == "maxSpending":
        columns = ["partial", objective]
    elif objective == "maxBequest":
        columns = ["partial", "final"]
    else:
        plan.mylog.print(f"Invalid objective '{objective}'.")
        return None

    df = pd.DataFrame(columns=columns)

    if progcall is None:
        progcall = progress.Progress(plan.mylog)

    if not verbose:
        progcall.start()

    _reset_scenario_rng(plan)

    for n in range(N):
        plan.regenRates(override_reproducible=True)
        plan.solve(objective, myoptions)
        if not verbose:
            progcall.show(n + 1, N)
        if plan.caseStatus == "solved":
            if objective == "maxSpending":
                df.loc[len(df)] = [plan.partialBequest, plan.basis]
            elif objective == "maxBequest":
                df.loc[len(df)] = [plan.partialBequest, plan.bequest]

    progcall.finish()
    plan.mylog.resetVerbose()

    fig, description = plan._plotter.plot_histogram_results(
        objective, df, N, plan.year_n, plan.n_d, plan.N_i, plan.phi_j, log_x=log_x
    )
    _prependObjectiveConstraint(description, objective, myoptions)
    plan.mylog.print(description.getvalue())

    if figure:
        return fig, description.getvalue()

    return N, df


def run_stochastic_spending(
    plan,
    options,
    scenario_method,
    *,  # noqa: C901
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
    """
    Run stochastic spending optimization over a set of scenarios.

    Collects optimal spending basis across S scenarios, computes the efficient frontier via the
    stochastic LP, and returns the raw data needed for plotting.

    Parameters
    ----------
    options : dict
        Solver options passed to solve().
    scenario_method : str
        "historical" — sweep ``ystart``..``yend`` like :func:`run_historical_range`.
        "mc"         — ``N`` Monte Carlo draws like :func:`run_mc`.
    ystart, yend : int, optional
        Start/end years for historical mode.
    N : int, optional
        Number of simulations for MC mode.
    progcall : Progress, optional
        Progress callback.
    with_longevity : bool, optional
        If True, draw a random lifespan for each scenario from SSA 2021 period
        life tables before solving.  Each scenario is solved on a fresh clone of
        *plan* with the drawn expectancy.  For couples, lifespans are drawn
        independently and the last-survivor horizon (max of the two draws) is used.
    sexes : list of str, optional
        Sex of each individual for SSA table lookup: 'M' (male) or 'F' (female).
        Required when ``with_longevity=True``.  E.g. ``['M', 'F']`` for a couple.
    seed : int or None, optional
        Random seed for reproducible longevity draws.  Only used when
        ``with_longevity=True``.

    Returns
    -------
    dict with keys:
        "bases"              : ndarray (S,) — per-scenario optimal spending basis
        "start_years"        : ndarray (S,) or None — historical start years (None for MC)
        "lambdas"            : ndarray
        "frontier_g"         : ndarray
        "frontier_prob"      : ndarray
        "frontier_shortfall" : ndarray
        "year_n"             : ndarray — plan calendar years
        "n_d"                : int — death year index (for unit labeling)
        "drawn_lifespans"    : ndarray (S, N_i) or None — drawn ages at death per scenario
        "partial_bequests"   : ndarray (S,) — bequest passing to non-spouse heirs at the first
                               death, today's dollars, net of the heirs' tax; NaN for a
                               scenario that did not solve, and legitimately 0.0 when the
                               surviving spouse is the sole beneficiary
        "year1_decisions"    : list (S,) of dict or None — first-year primal decisions per
                               scenario (see _year1_snapshot); None for infeasible or
                               short-horizon scenarios. Summarize with summarize_year1().
    """
    if with_longevity and scenario_method == "historical":
        raise ValueError(
            "Longevity risk is not supported with historical scenarios "
            "(drawn lifespans can exceed the available historical data range). "
            "Use Monte Carlo ('mc') instead."
        )

    if with_longevity:
        if sexes is None:
            raise ValueError("sexes must be provided when with_longevity=True (e.g. ['M'] or ['M','F']).")
        if len(sexes) != plan.N_i:
            raise ValueError(f"len(sexes)={len(sexes)} must match plan.N_i={plan.N_i}.")
        current_ages = [int(plan.year_n[0] - plan.yobs[i]) for i in range(plan.N_i)]
        mortality_table = getattr(plan, "mortality_table", "SSA2025")
        rng = np.random.default_rng(seed)

    plan.mylog.setVerbose(False)

    if progcall is None:
        progcall = progress.Progress(plan.mylog)

    bases_list = []
    year1_list = []
    partials_list = []
    start_years_list = []
    drawn_lifespans_list = []

    # ------------------------------------------------------------------
    # Build the args list for parallel workers.
    # All random draws and rate generation happen here in the parent so
    # that reproducibility (seed control) is preserved exactly.
    # Each scenario gets its own clone — a full copy that already has
    # all plan data (HFP timeLists, allocations, etc.) without any file I/O.
    # ------------------------------------------------------------------
    if scenario_method == "historical":
        if ystart is None or yend is None:
            raise ValueError("ystart and yend are required for historical scenario method.")
        if not with_longevity:
            if yend + plan.N_n > plan.year_n[0]:
                yend = plan.year_n[0] - plan.N_n
                plan.mylog.print(f"Upper bound for year range re-adjusted to {yend}.", tag="WARNING")
            if yend < ystart:
                raise ValueError(f"Starting year too large for lifespan of {plan.N_n} years.")
        years = list(range(ystart, yend + 1))
        total = len(years)
        plan.mylog.vprint(
            f"Stochastic spending: running {total} historical scenarios"
            + (" (with longevity sampling)." if with_longevity else ".")
        )
        drawn_list = []
        if with_longevity:
            for _ in years:
                drawn = [
                    int(sample_lifespans(sexes[i], current_ages[i], 1, rng, table=mortality_table)[0])
                    for i in range(plan.N_i)
                ]
                drawn_list.append(drawn)
        else:
            drawn_list = [None] * total
        results_map = {}
        n_short_horizon = 0
        args_list = []
        for i, year in enumerate(years):
            if with_longevity:
                horizon = max(drawn_list[i][j] - current_ages[j] + 1 for j in range(plan.N_i))
            else:
                horizon = plan.N_n
            if horizon <= 1:
                results_map[i] = (0.0, None, None)
                n_short_horizon += 1
            else:
                args_list.append(
                    (
                        i,
                        (
                            clone(plan, expectancy=drawn_list[i], verbose=False),
                            (year, reverse, roll),
                            None,
                            options,
                            year,
                        ),
                    )
                )

    elif scenario_method == "mc":
        if N is None:
            raise ValueError("N is required for Monte Carlo scenario method.")
        if not hasattr(plan, "rateModel") or plan.rateModel is None or getattr(plan.rateModel, "deterministic", True):
            raise ValueError("Monte Carlo requires a stochastic rate method.")
        plan.mylog.vprint(
            f"Stochastic spending: running {N} Monte Carlo scenarios"
            + (" (with longevity sampling)." if with_longevity else ".")
        )
        # Reset the rate RNG so repeated calls are reproducible when seeded
        _reset_scenario_rng(plan)

        # Pre-draw longevity
        drawn_list = []
        if with_longevity:
            for _ in range(N):
                drawn = [
                    int(sample_lifespans(sexes[i], current_ages[i], 1, rng, table=mortality_table)[0])
                    for i in range(plan.N_i)
                ]
                drawn_list.append(drawn)
            # Compute each scenario horizon directly from drawn ages-at-death.
            # This avoids creating extra clones just to discover horizons.
            horizons = [max(int(drawn[i] - current_ages[i] + 1) for i in range(plan.N_i)) for drawn in drawn_list]
            N_n_max = max(horizons)
        else:
            drawn_list = [None] * N
            N_n_max = plan.N_n

        # Pre-generate all rate sequences at the maximum required horizon in the parent.
        # Workers only slice deterministic inputs, so results are independent of thread scheduling.
        rate_data = []
        for _ in range(N):
            series = plan.rateModel.generate(N_n_max)
            if series.shape != (N_n_max, 4):
                raise RuntimeError(f"Rate model returned shape {series.shape}, expected ({N_n_max}, 4)")
            tau_kn = series.transpose()
            if not getattr(plan.rateModel, "constant", False):
                tau_kn = rates.apply_rate_sequence_transform(
                    tau_kn,
                    plan.rateReverse,
                    plan.rateRoll,
                )
            rate_data.append(tau_kn)
        total = N
        results_map = {}
        n_short_horizon = 0
        args_list = []
        for n, tau_kn in enumerate(rate_data):
            horizon = horizons[n] if with_longevity else plan.N_n
            if horizon <= 1:
                results_map[n] = (0.0, None, None)
                n_short_horizon += 1
            else:
                args_list.append(
                    (n, (clone(plan, expectancy=drawn_list[n], verbose=False), tau_kn, None, options, f"#{n}"))
                )
    else:
        raise ValueError(f"Unknown scenario_method '{scenario_method}'. Use 'historical' or 'mc'.")

    # ------------------------------------------------------------------
    # Solve all scenarios in parallel using threads.
    # HiGHS releases the GIL during solve, so threads give real parallelism.
    # No pickling needed — clones are plain Python objects.
    # Short-horizon scenarios (both individuals die within <=2 years) are
    # pre-populated in results_map with basis=0 and not submitted to workers.
    # ------------------------------------------------------------------
    n_to_solve = len(args_list)
    n_workers = min(os.cpu_count() or 1, n_to_solve) if n_to_solve > 0 else 1
    plan.mylog.print(f"Solving {total} scenarios using {n_workers} parallel worker thread(s).")
    progcall.start()
    completed = n_short_horizon  # pre-count already-resolved short-horizon scenarios

    with ThreadPoolExecutor(max_workers=n_workers, thread_name_prefix="scenario") as executor:
        futures = {executor.submit(_scenario_worker, args): orig_idx for orig_idx, args in args_list}
        for fut in as_completed(futures):
            orig_idx = futures[fut]
            try:
                results_map[orig_idx] = fut.result()
            except Exception as exc:
                plan.mylog.print(
                    f"scenario {orig_idx} raised {type(exc).__name__}: {exc}; treating as infeasible (basis 0).",
                    tag="WARNING",
                )
                results_map[orig_idx] = None
            completed += 1
            progcall.show(completed, total)

    # Collect results in scenario order (preserves start_years ordering).
    # Infeasible scenarios (None) are kept as basis=0.0 so that S in the LP
    # equals the number of scenarios requested, not just the ones that solved.
    # A basis of 0 means the full committed spending is a shortfall, which is
    # the correct treatment for an infeasible scenario.
    n_infeasible = 0
    for i in sorted(results_map):
        val = results_map[i]
        basis, year1, partial = (None, None, None) if val is None else val
        if basis is None:
            n_infeasible += 1
            basis = 0.0
        bases_list.append(basis)
        year1_list.append(year1)
        # NaN rather than 0 for a scenario that did not solve: zero is a real value
        # here (a spouse who is sole beneficiary), so the two must stay distinguishable.
        partials_list.append(np.nan if partial is None else partial)
        if scenario_method == "historical":
            start_years_list.append(years[i])
        if with_longevity:
            drawn_lifespans_list.append(np.array(drawn_list[i]))

    progcall.finish()
    plan.mylog.resetVerbose()

    if n_short_horizon:
        plan.mylog.print(
            f"Note: {n_short_horizon} of {total} scenarios had a horizon <=1 year"
            " (individual(s) die imminently) and are counted as zero spending."
        )
    n_solved = total - n_infeasible - n_short_horizon
    if n_infeasible:
        plan.mylog.print(
            f"{n_infeasible} of {total} scenarios were infeasible and are counted as full shortfall.", tag="WARNING"
        )
    if n_solved < 2:
        raise RuntimeError("Fewer than 2 scenarios solved successfully; cannot compute frontier.")

    bases = np.array(bases_list)
    start_years = np.array(start_years_list) if start_years_list else None
    drawn_lifespans = np.array(drawn_lifespans_list) if with_longevity else None

    lambdas, frontier_g, frontier_prob, frontier_shortfall = _compute_efficient_frontier(bases)

    return {
        "bases": bases,
        "start_years": start_years,
        "lambdas": lambdas,
        "frontier_g": frontier_g,
        "frontier_prob": frontier_prob,
        "frontier_shortfall": frontier_shortfall,
        "year_n": plan.year_n,
        "n_d": plan.n_d,
        "drawn_lifespans": drawn_lifespans,
        "n_infeasible": n_infeasible,
        "partial_bequests": np.array(partials_list),
        "year1_decisions": year1_list,
    }


###############################################################################
# Spending / bequest efficient frontier
###############################################################################


def _bequest_shadow_price(p):
    """
    Lifetime spending cost, in today's dollars, of one more today's-dollar of bequest.

    Reads the dual of the bequest_floor row, the same quantity the assistant reports
    in explain._explain_bequest_floor. Returns NaN when duals were not computed or
    the floor is slack, the latter meaning the plan leaves that much behind anyway.
    """
    dd = getattr(p, "_dual_data", None)
    if not dd:
        return np.nan
    for i, tag in enumerate(dd["row_tags"]):
        if tag is not None and tag[0] == "bequest_floor":
            sens = dd["row_dual"][i] * dd["objFac"] * p.gamma_n[p.N_n]
            return float(-sens)
    return np.nan


def _frontier_base_solve(plan, options, with_duals):
    """
    Solve the plan on its own configured rates at one bequest level.

    This is the whole answer in deterministic mode. In the stochastic modes it is
    only a probe for the fixed-asset value. Returns (basis, shadow_price, max_gap,
    fixed_assets, partial_bequest), with basis None when the level is infeasible. Fixed assets are
    only known after a solve, and are the same at every level, being set by the
    asset table rather than by the bequest floor.
    """
    p = clone(plan, verbose=False)
    opts = dict(options)
    if with_duals:
        opts["withDuals"] = True
    try:
        p.solve("maxSpending", opts)
    except Exception as exc:
        # Without this the caller sees only "unreachable", which reads as a plan that
        # cannot afford the floor rather than as an option or configuration error.
        plan.mylog.print(
            f"bequest level {opts.get('bequest')}: solve raised {type(exc).__name__}: {exc}.",
            tag="WARNING",
        )
        return None, np.nan, -1.0, np.nan, np.nan
    if p.caseStatus != "solved":
        return None, np.nan, -1.0, np.nan, np.nan
    shadow = _bequest_shadow_price(p) if with_duals else np.nan
    fixed = float(p.getFixedAssetsBequestValueInTodaysDollars())
    # Unlike fixed assets this moves with the floor, so it is read at every level.
    partial = float(getattr(p, "partialBequest", 0.0))
    return float(p.basis), shadow, float(getattr(p, "solverGap", -1.0)), fixed, partial


def run_spending_bequest_frontier(
    plan,
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
    max_time=MC_TIME_LIMIT,
    progcall=None,
):
    """
    Trace the efficient frontier between net spending and the bequest left behind.

    The user-facing surfaces call this the spending-vs-bequest *trade-off*, to keep
    it apart from the spending/shortfall-risk frontier of run_stochastic_spending().
    Both are Pareto frontiers; only that one is a risk/return curve in the Markowitz
    sense, so the plainer word is used where a reader might conflate them.

    Sweeps the ``bequest`` floor under the maxSpending objective. Each point is an
    ordinary solve, so no new optimization structure is involved. Because the floor
    constrains the estate rather than spending, g(0) stays free and the objective
    keeps a nonzero gradient: every point is a genuine optimum, unlike a pinned
    spending level, which leaves the objective constant and the tax variables
    unpriced (issue #140).

    In the stochastic modes each level is additionally solved across the whole
    scenario ensemble, which turns the curve into a surface S(B, p): spending as a
    function of the bequest target B and the probability p of not falling short.
    Reading it down a column gives spending versus bequest at fixed confidence, the
    fan across ``success_rates`` being the sequence-of-returns risk. Reading it
    across a row gives the spending/success curve of run_stochastic_spending().

    Parameters
    ----------
    options : dict
        Solver options passed to solve(). Monetary entries, ``bequest_grid``
        included, are in ``options["units"]`` (default "k").
    bequest_grid : sequence of float
        Bequest floors to trace, in ``options["units"]``. Sorted and deduplicated.
    scenario_method : str
        "deterministic" — one solve per level on the plan's own rates. Fast enough
                          to be interactive, and the direct replacement for pinning
                          a spending level.
        "historical"    — sweep ``ystart``..``yend`` at every level.
        "mc"            — ``N`` Monte Carlo draws at every level.
    success_rates : sequence of float
        Success percentages, each in (1, 100], at which to report spending. Ignored
        in deterministic mode, which has a single scenario.
    seed : int or None
        Seed for the Monte Carlo draws. MC mode pins the rate RNG regardless, so
        that every bequest level meets the same ensemble; without common random
        numbers the surface wanders non-monotonically on sampling noise alone.
    with_duals : bool
        Record the bequest_floor shadow price at each level, and with it the
        reliability flag on each exchange-rate segment. Off by default: it costs an
        extra LP re-solve per level, and the exchange rate is already measured
        directly from the curve, so the dual only cross-checks it -- and being the
        dual of the final LP with the loop's parameters frozen, it runs shallow.
        Deterministic mode only: a dual read off the plan's own rates says nothing about
        an ensemble, so it is not computed in the stochastic modes.
    max_time : float or None
        Per-solver-call time limit, applied unless ``options`` already sets one.
        A sweep multiplies any pathological scenario by the number of levels.

    Returns
    -------
    dict with keys:
        "bequest_grid"         : ndarray (K,) — floors as given, in ``units``
        "bequest_dollars"      : ndarray (K,) — the same floors in dollars
        "base_basis"           : ndarray (K,) — spending on the plan's own rates. Deterministic
                                 mode only; NaN throughout the stochastic modes, where the
                                 answer is the ensemble and a single-scenario basis would
                                 describe none of it
        "bases"                : ndarray (K, S) — per-scenario spending; 0.0 marks an
                                 infeasible scenario, matching run_stochastic_spending
        "g_at_success"         : ndarray (K, R) — spending at each success rate
        "lam_at_success"       : ndarray (K, R)
        "frontier_g"           : ndarray (K, L) or None — full lambda sweep per level
        "frontier_prob"        : ndarray (K, L) or None
        "frontier_shortfall"   : ndarray (K, L) or None
        "n_infeasible"         : ndarray (K,) int
        "level_failed"         : ndarray (K,) bool — level too high to solve at all
        "bequest_shadow_price" : ndarray (K,) — lifetime spending $ per today's-$ of bequest.
                                 Deterministic mode only, and only with ``with_duals``
        "partial_bequest"      : ndarray (K,) — bequest passing to non-spouse heirs at the first
                                 death, today's dollars, net of the heirs' tax. Unlike fixed
                                 assets this is solved, so it moves with the floor. The median
                                 across scenarios in the stochastic modes, the exact value when
                                 deterministic. NaN when no scenario at that level solved; 0.0
                                 when the surviving spouse is the sole beneficiary
        "partial_bequest_lo"   : ndarray (K,) — smallest across scenarios; equals the median
                                 when deterministic
        "partial_bequest_hi"   : ndarray (K,) — largest across scenarios
        "fixed_assets_today_dollars" : float — value of fixed assets still held at the end
                                 of the plan, in today's dollars. Set by the asset table
                                 rather than by the floor, so it is the same at every
                                 level, and it is on top of every bequest figure here
        "max_gap"              : ndarray (K,) — largest achieved MIP gap; -1 when pure LP
        "xi_sum"               : float — sum of the spending profile, converting a basis
                                 difference into the lifetime units of the shadow price
        "success_rates", "scenario_method", "n_scenarios", "start_years", "year_n", "n_d"

    Summarize with summarize_spending_bequest_frontier().
    """
    if scenario_method not in ("deterministic", "historical", "mc"):
        raise ValueError(
            f"scenario_method must be 'deterministic', 'historical' or 'mc', got '{scenario_method}'."
        )
    grid = sorted({float(b) for b in bequest_grid})
    if not grid or grid[0] < 0:
        raise ValueError("bequest_grid must be a non-empty sequence of non-negative amounts.")
    rates_pct = [float(r) for r in success_rates]
    for r in rates_pct:
        _validate_success_rate_pct(r)

    if scenario_method == "historical":
        if ystart is None:
            ystart = rates.FROM
        if yend is None:
            yend = plan.year_n[0] - plan.N_n
        if yend + plan.N_n > plan.year_n[0]:
            yend = plan.year_n[0] - plan.N_n
            plan.mylog.print(f"Upper bound for year range re-adjusted to {yend}.", tag="WARNING")
        if yend < ystart:
            raise ValueError(f"Starting year is too large to support a lifespan of {plan.N_n} years.")

    myoptions = dict(options)
    if max_time is not None and "maxTime" not in myoptions:
        myoptions["maxTime"] = max_time
    unit_fac = u.getUnits(myoptions.get("units", "k"))

    # Both of these are put back in the finally below. Left set, they leak out of the
    # sweep: a caller's later runMC() would come back silently seeded, and an escaping
    # exception would leave the plan's logger muted for good.
    saved_reproducible = (plan.reproducibleRates, plan.rateSeed)
    if scenario_method == "mc":
        # Common random numbers: without them each level meets a different ensemble and
        # the surface is non-monotone in B from sampling noise alone.
        plan.setReproducible(True, seed=0 if seed is None else seed)

    plan.mylog.setVerbose(False)
    if progcall is None:
        progcall = progress.Progress(plan.mylog)
    quiet = progress.Progress(None)  # the inner runs must not each draw their own bar

    K, R = len(grid), len(rates_pct)
    base_basis = np.full(K, np.nan)
    shadow = np.full(K, np.nan)
    max_gap = np.full(K, -1.0)
    n_infeasible = np.zeros(K, dtype=int)
    level_failed = np.zeros(K, dtype=bool)
    g_at_success = np.full((K, R), np.nan)
    lam_at_success = np.full((K, R), np.nan)
    bases_rows, frontier_rows, start_years, n_scenarios = [None] * K, [None] * K, None, 1
    fixed_assets = np.nan
    partial_bequest = np.full(K, np.nan)
    partial_lo = np.full(K, np.nan)
    partial_hi = np.full(K, np.nan)

    plan.mylog.print(f"Spending/bequest frontier: {K} bequest level(s), {scenario_method} scenarios.")
    progcall.start()

    try:
        for k, bequest in enumerate(grid):
            opts = dict(myoptions)
            opts["bequest"] = bequest
            if scenario_method == "deterministic":
                # Here the solve is the answer, so everything it reports is per level.
                basis, dual, gap, fixed, partial = _frontier_base_solve(plan, opts, with_duals)
                shadow[k] = dual
                max_gap[k] = gap
                if np.isfinite(fixed):
                    fixed_assets = fixed
                if np.isfinite(partial):
                    # One scenario, so the median and the range collapse to the value.
                    partial_bequest[k] = partial_lo[k] = partial_hi[k] = partial
                if basis is None:
                    level_failed[k] = True
                    n_infeasible[k] = 1
                    bases_rows[k] = np.array([0.0])
                else:
                    base_basis[k] = basis
                    bases_rows[k] = np.array([basis])
                    g_at_success[k, :] = basis
            else:
                # The answer comes from the ensemble below. The only thing a base solve
                # adds here is the fixed-asset value, which the asset table fixes rather
                # than the floor, so probe for it once -- retrying at the next level should
                # the first prove infeasible -- and record nothing else. A basis, gap or
                # dual read off the plan's own rates describes none of the scenarios.
                if not np.isfinite(fixed_assets):
                    _, _, _, fixed, _ = _frontier_base_solve(plan, opts, with_duals=False)
                    if np.isfinite(fixed):
                        fixed_assets = fixed
                try:
                    res = run_stochastic_spending(
                        plan, opts, scenario_method, ystart=ystart, yend=yend, N=N, progcall=quiet, seed=seed
                    )
                except RuntimeError as exc:
                    plan.mylog.print(
                        f"bequest level {bequest:,.0f}: {exc} Recording the level as unreachable.",
                        tag="WARNING",
                    )
                    level_failed[k] = True
                else:
                    bases_rows[k] = res["bases"]
                    frontier_rows[k] = (res["frontier_g"], res["frontier_prob"], res["frontier_shortfall"])
                    n_infeasible[k] = int(res["n_infeasible"])
                    # The transfer varies by scenario as well as by level, so report the
                    # middle of the distribution and how far it spreads.
                    pb = np.asarray(res["partial_bequests"], float)
                    if np.isfinite(pb).any():
                        partial_bequest[k] = float(np.nanmedian(pb))
                        partial_lo[k] = float(np.nanmin(pb))
                        partial_hi[k] = float(np.nanmax(pb))
                    start_years = res["start_years"]
                    n_scenarios = len(res["bases"])
                    for j, rate in enumerate(rates_pct):
                        g, lam = g_for_success_rate(rate, res["lambdas"], res["frontier_g"], res["frontier_prob"])
                        g_at_success[k, j] = g
                        lam_at_success[k, j] = lam

            progcall.show(k + 1, K)

    finally:
        progcall.finish()
        plan.mylog.resetVerbose()
        # Restored by hand: setReproducible() regenerates a seed rather than
        # simply assigning the one it is given.
        plan.reproducibleRates, plan.rateSeed = saved_reproducible

    n_failed = int(level_failed.sum())
    if n_failed:
        plan.mylog.print(f"{n_failed} of {K} bequest levels could not be reached.", tag="WARNING")

    bases = np.zeros((K, n_scenarios))
    for k, row in enumerate(bases_rows):
        if row is not None and len(row) == n_scenarios:
            bases[k, :] = row

    if scenario_method == "deterministic":
        frontier_g = frontier_prob = frontier_shortfall = None
    else:
        n_pts = max((len(f[0]) for f in frontier_rows if f is not None), default=0)
        frontier_g = np.full((K, n_pts), np.nan)
        frontier_prob = np.full((K, n_pts), np.nan)
        frontier_shortfall = np.full((K, n_pts), np.nan)
        for k, f in enumerate(frontier_rows):
            if f is not None:
                frontier_g[k, :], frontier_prob[k, :], frontier_shortfall[k, :] = f

    return {
        "bequest_grid": np.array(grid),
        "bequest_dollars": np.array(grid) * unit_fac,
        "base_basis": base_basis,
        "bases": bases,
        "g_at_success": g_at_success,
        "lam_at_success": lam_at_success,
        "frontier_g": frontier_g,
        "frontier_prob": frontier_prob,
        "frontier_shortfall": frontier_shortfall,
        "n_infeasible": n_infeasible,
        "level_failed": level_failed,
        "bequest_shadow_price": shadow,
        "fixed_assets_today_dollars": 0.0 if not np.isfinite(fixed_assets) else fixed_assets,
        "partial_bequest": partial_bequest,
        "partial_bequest_lo": partial_lo,
        "partial_bequest_hi": partial_hi,
        "max_gap": max_gap,
        "xi_sum": float(np.sum(plan.xi_n)),
        "success_rates": tuple(rates_pct),
        "scenario_method": scenario_method,
        "n_scenarios": n_scenarios,
        "start_years": start_years,
        "year_n": plan.year_n,
        "n_d": plan.n_d,
    }


def summarize_spending_bequest_frontier(result, *, target_success_rate_pct=90.0):
    """
    Summarize a run_spending_bequest_frontier() result into a JSON-ready dict.

    Reports the curve itself and the measured exchange rate between bequest and
    spending at the requested confidence, segment by segment.

    Deliberately absent are a "free bequest" and a "knee". Both read as properties
    of the plan but are set by the grid: the free bequest, being the largest floor
    that costs no spending, is zero for any curve that slopes at all, and the knee
    lands on the second grid point whenever the second segment differs from the
    first, which on a curved frontier is always. Resolving either honestly needs a
    finer sweep than a caller-supplied handful of levels.

    The shadow price is carried alongside the measured secant as a cross-check. It
    is the dual of the final LP with the self-consistent loop's parameters frozen,
    so it is a partial derivative of a fixed point and runs shallow; a disagreement
    above 20% means the segment is being driven by the loop rather than the LP and
    should not be read as a local slope.

    The largest reachable estate is reported as a bracket, not a value: it lies at
    or above ``max_feasible_bequest_today_dollars`` and below
    ``first_unreachable_bequest_today_dollars``, which is None when every traced
    level was reachable. Both are grid points, so neither is a property of the plan
    on its own — the highest success merely echoes the grid when nothing failed.
    """
    grid = np.asarray(result["bequest_dollars"], float)
    failed = np.asarray(result["level_failed"], bool)
    shadow = np.asarray(result["bequest_shadow_price"], float)
    xi_sum = float(result["xi_sum"])
    rates_pct = list(result["success_rates"])
    deterministic = result["scenario_method"] == "deterministic"
    fixed_assets = float(result.get("fixed_assets_today_dollars", 0.0) or 0.0)
    partial = np.asarray(result.get("partial_bequest", np.full(len(grid), np.nan)), float)
    partial_lo = np.asarray(result.get("partial_bequest_lo", partial), float)
    partial_hi = np.asarray(result.get("partial_bequest_hi", partial), float)

    if deterministic:
        g_col = np.asarray(result["base_basis"], float)
    else:
        if target_success_rate_pct not in rates_pct:
            raise ValueError(
                f"target_success_rate_pct={target_success_rate_pct} is not among the rates traced "
                f"({rates_pct}); re-run the frontier including it."
            )
        g_col = np.asarray(result["g_at_success"], float)[:, rates_pct.index(target_success_rate_pct)]

    rows = []
    for k, bequest in enumerate(grid):
        # Everything that reaches heirs, whether at the first death or at the end.
        pb = 0.0 if np.isnan(partial[k]) else float(partial[k])
        row = {
            "bequest_today_dollars": round(float(bequest), 2),
            "partial_bequest_today_dollars": None if np.isnan(partial[k]) else round(pb, 2),
            "total_estate_today_dollars": round(float(bequest) + fixed_assets + pb, 2),
            "feasible": not bool(failed[k]),
            "n_infeasible_scenarios": int(result["n_infeasible"][k]),
            "shadow_price": None if np.isnan(shadow[k]) else round(float(shadow[k]), 4),
        }
        if not np.isnan(partial[k]) and (partial_hi[k] - partial_lo[k]) > 1.0:
            row["partial_bequest_low"] = round(float(partial_lo[k]), 2)
            row["partial_bequest_high"] = round(float(partial_hi[k]), 2)
        if deterministic:
            row["spending_today_dollars"] = None if np.isnan(g_col[k]) else round(float(g_col[k]), 2)
        else:
            for j, rate in enumerate(rates_pct):
                v = float(result["g_at_success"][k, j])
                row[f"spending_at_{rate:g}pct"] = None if np.isnan(v) else round(v, 2)
        rows.append(row)

    # Exchange rate: how much spending each extra dollar of estate costs, measured.
    #
    # One entry per grid segment, always, so exchange_rate[k - 1] is the segment ending
    # at level k. Skipping unmeasurable segments would shorten the list and silently
    # shift every rate a renderer reads by position.
    exchange = []
    for k in range(1, len(grid)):
        entry = {
            "from_bequest": round(float(grid[k - 1]), 2),
            "to_bequest": round(float(grid[k]), 2),
            "spending_per_dollar_of_bequest": None,
        }
        dB = grid[k] - grid[k - 1]
        if dB > 0 and not np.isnan(g_col[k]) and not np.isnan(g_col[k - 1]):
            secant = (g_col[k] - g_col[k - 1]) / dB
            entry["spending_per_dollar_of_bequest"] = round(float(secant), 6)
            # The dual is a lifetime figure; a basis secant scales by the profile sum.
            d = shadow[k]
            if not np.isnan(d) and abs(secant) > 1e-12:
                implied = -d / xi_sum
                entry["shadow_price_implied"] = round(float(implied), 6)
                entry["dual_secant_disagreement"] = round(abs(implied - secant) / abs(secant), 4)
                entry["reliable"] = bool(abs(implied - secant) / abs(secant) <= 0.2)
        exchange.append(entry)

    # A sweep can only bracket the largest reachable estate: it lies at or above the
    # highest level that solved, and below the lowest that did not. Reporting the
    # highest success alone would just echo the grid back when nothing failed, and
    # would understate the true maximum by a whole grid step when something did.
    #
    # Reachability is level_failed alone. Individual scenarios going infeasible at a
    # high floor is ordinary in the stochastic modes -- that is what the success rates
    # exist to express, an infeasible scenario being recorded as a full shortfall -- so
    # counting those would report a level as out of reach while the table above it
    # showed spending at all three confidences.
    #
    # Failures are not necessarily a suffix of the grid -- a solve can time out at one
    # level and succeed above it -- so the upper end is the lowest failure *above* the
    # highest success. Taking the lowest failure overall reports a backwards bracket.
    ok = ~failed
    reachable = grid[ok]
    lo = float(reachable.max()) if len(reachable) else None
    above = grid[~ok] if lo is None else grid[~ok & (grid > lo)]
    hi = float(above.min()) if len(above) else None
    gaps = np.asarray(result["max_gap"], float)

    return {
        "scenario_method": result["scenario_method"],
        "n_scenarios": int(result["n_scenarios"]),
        "success_rates": rates_pct,
        "target_success_rate_pct": None if deterministic else target_success_rate_pct,
        "frontier": rows,
        "exchange_rate": exchange,
        "max_feasible_bequest_today_dollars": None if lo is None else round(lo, 2),
        "first_unreachable_bequest_today_dollars": None if hi is None else round(hi, 2),
        "fixed_assets_today_dollars": round(fixed_assets, 2),
        # year_n[n_d - 1] is the decedent's last year, matching export.py and the histograms.
        "partial_bequest_year": (
            None
            if not np.isfinite(partial).any() or np.nanmax(partial) <= 0
            else int(result["year_n"][max(0, int(result["n_d"]) - 1)])
        ),
        "n_levels_failed": int(failed.sum()),
        "max_achieved_gap": None if not len(gaps) or gaps.max() < 0 else round(float(gaps.max()), 6),
    }
