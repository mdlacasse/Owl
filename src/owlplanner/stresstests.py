"""
Stress testing methods for retirement plans and stochastic spending optimization.

Provides ``run_historical_range``, ``run_mc``, and ``run_stochastic_spending``, which take a
:class:`~owlplanner.plan.Plan` instance as the first argument (``Plan`` exposes them as methods
that delegate here). Also includes standalone LP helpers for the efficient frontier.

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

import numpy as np
import pandas as pd
from itertools import product
from scipy.optimize import linprog

from . import progress


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

    c = np.concatenate([[-1.0], np.full(S, lam / S)])

    A_ub = np.zeros((S, 1 + S))
    A_ub[:, 0] = 1.0
    A_ub[np.arange(S), 1 + np.arange(S)] = -1.0
    b_ub = bases

    bounds = [(0.0, float(bases.max()))] + [(0.0, None)] * S

    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
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


def g_for_success_rate(target_success_rate, lambdas, frontier_g, frontier_prob):
    """
    Return (g_opt, lam) for the least conservative lambda that achieves the target success rate.

    Parameters
    ----------
    target_success_rate : float
        Desired fraction of scenarios with no shortfall (e.g. 0.90 for 90%).
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
    target_shortfall_prob = 1.0 - target_success_rate
    candidates = np.where(frontier_prob <= target_shortfall_prob)[0]
    if len(candidates) == 0:
        return float(frontier_g[-1]), float(lambdas[-1])
    idx = candidates[0]
    return float(frontier_g[idx]), float(lambdas[idx])


###############################################################################
# Batch stress tests (Plan delegates from runHistoricalRange / runMC / runStochasticSpending)
###############################################################################


def run_historical_range(plan, objective, options, ystart, yend, *, verbose=False, figure=False,
                         progcall=None, reverse=False, roll=0, augmented=False, log_x=False):
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
        plan.mylog.print(f"Warning: Upper bound for year range re-adjusted to {yend}.")

    if yend < ystart:
        raise ValueError(f"Starting year is too large to support a lifespan of {plan.N_n} years.")

    n_years = yend - ystart + 1
    if augmented:
        reverse_roll_pairs = list(product([False, True], range(plan.N_n)))
        N = n_years * len(reverse_roll_pairs)
        plan.mylog.vprint(f"Running historical range from {ystart} to {yend} (augmented: {len(reverse_roll_pairs)}"
                          f" variants per year, {N} runs).")
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
        objective, df, N, plan.year_n, plan.n_d, plan.N_i, plan.phi_j, log_x=log_x)
    plan.mylog.print(description.getvalue())

    fig2 = None
    if not augmented and len(start_years_list) > 0:
        fig2, _ = plan._plotter.plot_spending_by_year(
            objective, np.array(start_years_list), np.array(values_list), plan.n_d, plan.year_n)

    if figure:
        return fig, description.getvalue(), fig2

    return N, df


def run_mc(plan, objective, options, N, *, verbose=False, figure=False, progcall=None, log_x=False):
    """
    Run Monte Carlo simulations on plan.
    """
    if not hasattr(plan, "rateModel") or plan.rateModel is None \
            or getattr(plan.rateModel, "deterministic", True):
        plan.mylog.print("Monte Carlo simulations require a stochastic rate method.")
        return

    plan.mylog.vprint(f"Running {N} Monte Carlo simulations.")
    plan.mylog.setVerbose(verbose)

    myoptions = options

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

    if plan.reproducibleRates and hasattr(plan.rateModel, '_rng'):
        plan.rateModel._rng = np.random.default_rng(plan.rateModel.seed)

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
        objective, df, N, plan.year_n, plan.n_d, plan.N_i, plan.phi_j, log_x=log_x)
    plan.mylog.print(description.getvalue())

    if figure:
        return fig, description.getvalue()

    return N, df


def run_stochastic_spending(plan, objective, options, scenario_method, *,
                            ystart=None, yend=None, N=None, progcall=None,
                            reverse=False, roll=0):
    """
    Run stochastic spending optimization over a set of scenarios.

    Collects optimal basis or bequest across S scenarios, computes the efficient frontier via the
    stochastic LP, and returns the raw data needed for plotting.

    Parameters
    ----------
    objective : str
        "maxSpending" or "maxBequest".
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
    """
    if objective not in ("maxSpending", "maxBequest"):
        raise ValueError(f"Invalid objective '{objective}'.")

    plan.mylog.setVerbose(False)

    if progcall is None:
        progcall = progress.Progress(plan.mylog)

    bases_list = []
    start_years_list = []
    n_infeasible = 0

    if scenario_method == "historical":
        if ystart is None or yend is None:
            raise ValueError("ystart and yend are required for historical scenario method.")
        if yend + plan.N_n > plan.year_n[0]:
            yend = plan.year_n[0] - plan.N_n
            plan.mylog.print(f"Warning: Upper bound for year range re-adjusted to {yend}.")
        if yend < ystart:
            raise ValueError(f"Starting year too large for lifespan of {plan.N_n} years.")
        total = yend - ystart + 1
        plan.mylog.vprint(f"Stochastic spending: running {total} historical scenarios.")
        progcall.start()
        for step, year in enumerate(range(ystart, yend + 1)):
            plan.setRates("historical", year, reverse=reverse, roll=roll)
            plan.solve(objective, options)
            progcall.show(step + 1, total)
            if plan.caseStatus == "solved":
                val = plan.basis if objective == "maxSpending" else plan.bequest
            else:
                val = 0.0
                n_infeasible += 1
            bases_list.append(val)
            start_years_list.append(year)

    elif scenario_method == "mc":
        if N is None:
            raise ValueError("N is required for Monte Carlo scenario method.")
        if not hasattr(plan, "rateModel") or plan.rateModel is None \
                or getattr(plan.rateModel, "deterministic", True):
            raise ValueError("Monte Carlo requires a stochastic rate method.")
        plan.mylog.vprint(f"Stochastic spending: running {N} Monte Carlo scenarios.")
        if plan.reproducibleRates and hasattr(plan.rateModel, '_rng'):
            plan.rateModel._rng = np.random.default_rng(plan.rateModel.seed)
        progcall.start()
        for n in range(N):
            plan.regenRates(override_reproducible=True)
            plan.solve(objective, options)
            progcall.show(n + 1, N)
            if plan.caseStatus == "solved":
                val = plan.basis if objective == "maxSpending" else plan.bequest
            else:
                val = 0.0
                n_infeasible += 1
            bases_list.append(val)

    else:
        raise ValueError(f"Unknown scenario_method '{scenario_method}'. Use 'historical' or 'mc'.")

    progcall.finish()
    plan.mylog.resetVerbose()

    n_solved = len(bases_list) - n_infeasible
    if n_infeasible:
        plan.mylog.print(f"Warning: {n_infeasible} of {len(bases_list)} scenarios were infeasible"
                         " and are counted as full shortfall.")
    if n_solved < 2:
        raise RuntimeError("Fewer than 2 scenarios solved successfully; cannot compute frontier.")

    bases = np.array(bases_list)
    start_years = np.array(start_years_list) if start_years_list else None

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
        "n_infeasible": n_infeasible,
    }
