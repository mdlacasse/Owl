"""
Stress testing methods for retirement plans and stochastic spending optimization.

Provides ``run_historical_range``, ``run_mc``, and ``run_stochastic_spending``, which take a
:class:`~owlplanner.plan.Plan` instance as the first argument (``Plan`` exposes them as methods
that delegate here). Also includes standalone LP helpers for the efficient frontier.

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
import numpy as np
import pandas as pd
from itertools import product
from concurrent.futures import ThreadPoolExecutor, as_completed
from scipy.optimize import linprog

from . import progress
from . import rates
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

    Returns (basis, year1) where year1 is the _year1_snapshot dict, or
    (None, None) on solver failure.
    """
    p, tau_kn_or_year, gamma_n, options = args

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
        return p.basis, _year1_snapshot(p)
    return None, None


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


def _regret_worker(args):
    """
    Solve one scenario's baseline, grid, and never-convert solves in a worker thread.

    args tuple: (clone, year, objective, options, grid, person, include_never_convert)

    Returns (year, payload) where payload is None if the unconstrained baseline
    fails, else a dict with:
      v_star   — unconstrained optimum (clairvoyant benchmark)
      x_star   — the baseline's first-year Roth conversion for `person`, $
      v_at     — list aligned with grid; None where the pinned solve is infeasible
      v_noconv — optimum with conversions disallowed for `person` (or None)
      max_gap  — largest achieved MIP gap across this scenario's solves (-1 if
                 no MIP was involved); flags certificates degraded by maxTime
    """
    import time as _time

    p, year, objective, options, grid, person, include_never_convert = args
    p.setRates("historical", year)
    _t0 = _time.time()

    max_gap = -1.0
    # Track SC-loop convergence: monotonic solves land in the interior of the
    # bracket structure (trustworthy, idempotent); non-monotonic (oscillatory /
    # max-iter) solves sit on a tax cliff where the fixed point is ambiguous and
    # the result carries a genuine error bar. n_nonmonotonic counts such solves
    # across the window; v_star_conv is the clairvoyant baseline's own verdict.
    n_nonmonotonic = 0

    def _note_conv():
        nonlocal n_nonmonotonic
        if getattr(p, "convergenceType", "undefined") != "monotonic":
            n_nonmonotonic += 1

    p.solve(objective, options)
    max_gap = max(max_gap, getattr(p, "solverGap", -1.0))
    v_star_conv = getattr(p, "convergenceType", "undefined")
    v_star_rel = getattr(p, "oscillationRel", 0.0)
    _note_conv()
    if p.caseStatus != "solved":
        return year, None
    v_star = _regret_objective_value(p, objective)
    # Dollar amplitude of the clairvoyant optimum's SC-loop oscillation (0 if monotonic).
    v_star_osc = abs(v_star) * v_star_rel
    x_star = float(p.x_in[person, 0])

    # Pin the first-year conversion at each grid value. myRothX_in holds dollar
    # amounts; a positive value pins x[person, 0] exactly, a negative value
    # forces it to zero (see _add_roth_conversion_constraints).
    opts_pin = dict(options)
    opts_pin["useRothConvOverrides"] = True
    v_at = []
    v_at_osc = []
    for x in grid:
        p.myRothX_in[person, 0] = float(x) if x > 0 else -1.0
        p.solve(objective, opts_pin)
        max_gap = max(max_gap, getattr(p, "solverGap", -1.0))
        _note_conv()
        if p.caseStatus == "solved":
            val = _regret_objective_value(p, objective)
            v_at.append(val)
            v_at_osc.append(abs(val) * getattr(p, "oscillationRel", 0.0))
        else:
            v_at.append(None)
            v_at_osc.append(None)
    p.myRothX_in[person, 0] = 0.0

    v_noconv = None
    if include_never_convert:
        opts_nc = dict(options)
        opts_nc.pop("useRothConvOverrides", None)
        opts_nc["noRothConversions"] = p.inames[person]
        p.solve(objective, opts_nc)
        max_gap = max(max_gap, getattr(p, "solverGap", -1.0))
        _note_conv()
        if p.caseStatus == "solved":
            v_noconv = _regret_objective_value(p, objective)

    p.mylog.print(
        f"window {year}: {_time.time() - _t0:.1f}s, {v_star_conv}, "
        f"{n_nonmonotonic} non-monotonic solve(s), osc ${v_star_osc:,.0f}"
    )
    return year, {"v_star": v_star, "x_star": x_star, "v_at": v_at, "v_noconv": v_noconv,
                  "max_gap": max_gap, "v_star_conv": v_star_conv, "n_nonmonotonic": n_nonmonotonic,
                  "v_star_osc": v_star_osc, "v_at_osc": v_at_osc}


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
):
    """
    Measure the regret of committing to a fixed first-year Roth conversion.

    For each historical starting year in [ystart, yend], the plan is first solved
    unconstrained (the clairvoyant benchmark v*_s and its first-year conversion
    x*_s), then re-solved with the first-year conversion of individual `person`
    pinned at each value of `grid` (dollars), leaving all later decisions free to
    re-optimize within the scenario. The regret of committing to x in scenario s
    is v*_s - v_s(x) >= 0. Optionally, a never-convert solve (conversions
    disallowed for `person` in all years) measures the value of the entire
    conversion strategy.

    Outcomes are in the objective's natural units, today's dollars: first-year
    spending basis ($/yr) for maxSpending, after-tax final savings estate for
    maxBequest (which requires options["netSpending"]). For a couple, only
    `person`'s conversion is pinned; the spouse's remains free.

    Returns a dict:
      "grid"        — list of committed amounts ($)
      "start_years" — ndarray (S,) of scenario starting years
      "v_star"      — ndarray (S,) clairvoyant optima; NaN if baseline failed
      "x_star"      — ndarray (S,) baseline first-year conversions ($)
      "v_at"        — ndarray (S, X); NaN where pinned solve was infeasible
      "v_noconv"    — ndarray (S,) or None
      "max_gap"     — ndarray (S,) largest achieved MIP gap per scenario (-1 when
                      no MIP was involved; values above the requested gap flag
                      solves whose certificate was degraded by the time limit)
      "person"      — the pinned individual's index

    Summarize with summarize_conversion_regret().
    """
    if yend + plan.N_n > plan.year_n[0]:
        yend = plan.year_n[0] - plan.N_n
        plan.mylog.print(f"Upper bound for year range re-adjusted to {yend}.", tag="WARNING")
    if yend < ystart:
        raise ValueError(f"Starting year is too large to support a lifespan of {plan.N_n} years.")
    if not (0 <= person < plan.N_i):
        raise ValueError(f"person={person} out of range for {plan.N_i} individual(s).")
    grid = [float(x) for x in grid]
    if not grid or any(x < 0 for x in grid):
        raise ValueError("grid must be a non-empty list of non-negative dollar amounts.")

    plan.mylog.setVerbose(False)
    if progcall is None:
        progcall = progress.Progress(plan.mylog)

    years = list(range(ystart, yend + 1))
    total = len(years)
    args_list = [
        (clone(plan, verbose=False), year, objective, options, grid, person, include_never_convert)
        for year in years
    ]
    n_workers = min(os.cpu_count() or 1, total)
    plan.mylog.print(
        f"Regret sweep: {total} scenarios x {len(grid)} grid points using {n_workers} parallel worker thread(s)."
    )
    progcall.start()

    results_map = {}
    completed = 0
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(_regret_worker, args): args[1] for args in args_list}
        for fut in as_completed(futures):
            year = futures[fut]
            try:
                results_map[year] = fut.result()[1]
            except Exception as exc:
                plan.mylog.print(
                    f"scenario {year} raised {type(exc).__name__}: {exc}; treating as failed baseline.",
                    tag="WARNING",
                )
                results_map[year] = None
            completed += 1
            progcall.show(completed, total)

    progcall.finish()
    plan.mylog.resetVerbose()

    S, X = total, len(grid)
    v_star = np.full(S, np.nan)
    x_star = np.full(S, np.nan)
    v_at = np.full((S, X), np.nan)
    v_noconv = np.full(S, np.nan) if include_never_convert else None
    max_gap = np.full(S, -1.0)
    n_nonmonotonic = np.zeros(S, dtype=int)
    v_star_conv = ["undefined"] * S
    v_star_osc = np.zeros(S)
    v_at_osc = np.full((S, X), np.nan)
    for i, year in enumerate(years):
        r = results_map.get(year)
        if r is None:
            continue
        max_gap[i] = r.get("max_gap", -1.0)
        n_nonmonotonic[i] = r.get("n_nonmonotonic", 0)
        v_star_conv[i] = r.get("v_star_conv", "undefined")
        v_star_osc[i] = r.get("v_star_osc", 0.0)
        v_star[i] = r["v_star"]
        x_star[i] = r["x_star"]
        for j, v in enumerate(r["v_at"]):
            if v is not None:
                v_at[i, j] = v
        for j, o in enumerate(r.get("v_at_osc", [])):
            if o is not None:
                v_at_osc[i, j] = o
        if include_never_convert and r["v_noconv"] is not None:
            v_noconv[i] = r["v_noconv"]

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
    }


def summarize_conversion_regret(result, *, asymmetry_deltas=(15_000, 30_000, 45_000)):
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
    return out


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
    plan.mylog.print(description.getvalue())

    fig2 = None
    if not augmented and len(start_years_list) > 0:
        fig2, _ = plan._plotter.plot_spending_by_year(
            objective, np.array(start_years_list), np.array(values_list), plan.n_d, plan.year_n
        )

    if figure:
        return fig, description.getvalue(), fig2

    return N, df


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
                results_map[i] = (0.0, None)
                n_short_horizon += 1
            else:
                args_list.append(
                    (i, (clone(plan, expectancy=drawn_list[i], verbose=False), (year, reverse, roll), None, options))
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
                results_map[n] = (0.0, None)
                n_short_horizon += 1
            else:
                args_list.append((n, (clone(plan, expectancy=drawn_list[n], verbose=False), tau_kn, None, options)))
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

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
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
        basis, year1 = (None, None) if val is None else val
        if basis is None:
            n_infeasible += 1
            basis = 0.0
        bases_list.append(basis)
        year1_list.append(year1)
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
        "year1_decisions": year1_list,
    }
