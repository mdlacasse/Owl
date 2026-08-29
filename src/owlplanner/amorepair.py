"""
Post-processing that restores the two adjacent-mutually-exclusive (AMO) properties
without carrying mutual-exclusion binaries in the model.

Owl used to enforce two exclusions with big-M binaries:

  - a Roth conversion and a Roth withdrawal never happen in the same year
    (relaxed below age 59 1/2, where a conversion ladder needs exactly that overlap);
  - a surplus is never banked in a year that also withdraws from a taxable or
    tax-free account.

Neither exclusion changes the optimum -- both are symmetry breakers that pick the
legible member of a family of equally valued solutions. Enforcing them with binaries
is nevertheless ruinously expensive for households that owe no tax in any year:
with a zero marginal rate on both ordinary income and capital gains, moving a dollar
between accounts is a null operation, so the objective is flat across a combinatorial
set of plans and branch-and-bound has nothing to prune.

This module restores the same two properties after the fact:

  Stage A (:func:`repair_roth_overlap`) rewrites a conversion/withdrawal overlap as a
  larger tax-deferred withdrawal. Every affected constraint row is invariant, so this
  is exact and needs no solve.

  Stage B (:func:`build_polish_overrides` / :func:`build_polish_objective`) sets up a
  churn-minimizing re-solve of the same LP with spending, the terminal balances and the
  conversion schedule pinned. The incumbent is a feasible point of that LP, so it cannot
  be infeasible, cannot change the reported objective, and can only reduce surplus.

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

from dataclasses import dataclass
from typing import Any

import numpy as np

# A flow below this many dollars is treated as zero when counting overlaps.
TOL_DOLLAR = 1.0
# Anything smaller than this is not worth moving.
TOL_CENT = 0.01


@dataclass
class AmoContext:
    """Everything the repair needs from a Plan, without importing it.

    Keeping this a plain dataclass lets the repair be unit-tested against a synthetic
    VarMap, with no solve and no Plan instance.
    """

    vm: Any  # VarMap
    N_i: int
    N_j: int
    N_n: int
    n_d: int  # first year the deceased spouse is gone (== N_n for a single)
    i_s: int  # index of the surviving spouse
    eta: float  # spousal surplus deposit split
    n595: np.ndarray  # (N_i,) first year each individual is past 59 1/2
    horizons: np.ndarray  # (N_i,)
    xnet: float  # 1 - oppCostX/100
    col_lb: np.ndarray  # variable lower bounds, to respect pinned columns
    has_wdorder: bool  # withdrawalOrder == "taxable_first"

    @property
    def roth_repair_blocked(self):
        """Return a reason string when the Roth substitution is not neutral, else None."""
        if self.xnet != 1.0:
            return "oppCostX is non-zero, so a conversion and a withdrawal are not interchangeable"
        if self.has_wdorder:
            # w[i,1,n] is pinned to the RMD until the taxable-exhausted gate opens, so the
            # substitution's larger tax-deferred withdrawal would violate wdorder_txdef_gate.
            return "withdrawalOrder='taxable_first' pins tax-deferred withdrawals to the RMD"
        return None


def deposit_split(ctx, n):
    """Fraction of the year-n surplus deposited into each individual's taxable account.

    Mirrors ``Plan._add_surplus_deposit_linking``: before the first death the surplus is
    split by ``eta``; afterwards it all lands with the survivor.
    """
    fac = np.zeros(ctx.N_i)
    if n < ctx.n_d:
        for i in range(ctx.N_i):
            fac[i] = (1 - ctx.eta) if i == 0 else (ctx.eta if i == 1 else 0.0)
    else:
        fac[ctx.i_s] = 1.0
    return fac


def count_amo_violations(x, ctx, tol=TOL_DOLLAR):
    """Count years violating each exclusion, at the household level the old rows used."""
    vm = ctx.vm
    n595_max = int(np.max(ctx.n595))
    roth = surplus = 0
    for n in range(ctx.N_n):
        if n >= n595_max:
            conv = sum(x[vm["x"].idx(i, n)] for i in range(ctx.N_i))
            wroth = sum(x[vm["w"].idx(i, 2, n)] for i in range(ctx.N_i))
            if conv > tol and wroth > tol:
                roth += 1
        drawn = sum(x[vm["w"].idx(i, j, n)] for i in range(ctx.N_i) for j in (0, 2))
        if x[vm["s"].idx(n)] > tol and drawn > tol:
            surplus += 1
    return {"roth": roth, "surplus": surplus}


def max_row_violation(x, A, col_lb=None, col_ub=None):
    """Largest absolute violation of any constraint row or variable bound.

    Solver feasibility is relative, so a converged solution routinely carries residuals
    of a fraction of a dollar on balances of order 1e7. Callers compare against the
    incumbent's own residual rather than against zero.
    """
    worst = 0.0
    for ii in range(A.ncons):
        ind = A.Aind[ii]
        if not ind:
            continue
        val = float(np.dot(np.asarray(A.Aval[ii]), x[np.asarray(ind)]))
        worst = max(worst, A.lb[ii] - val, val - A.ub[ii])
    if col_lb is not None:
        worst = max(worst, float(np.max(col_lb - x)))
    if col_ub is not None:
        worst = max(worst, float(np.max(x - col_ub)))
    return max(worst, 0.0)


def repair_roth_overlap(x, ctx):
    """Rewrite a same-year Roth conversion and Roth withdrawal as a tax-deferred withdrawal.

    For ``m = min(x_in, w_i2n)``, substituting::

        x[i,n]   -= m        (convert less)
        w[i,2,n] -= m        (withdraw less from the Roth)
        w[i,1,n] += m        (withdraw the same amount from tax-deferred instead)

    leaves every constraint row either invariant or slack:

      - ``account_carryover(i,1,n)`` -- x and w[i,1,n] carry the same coefficient, so the
        tax-deferred balance is unchanged;
      - ``account_carryover(i,2,n)`` -- cancels when ``xnet == 1``;
      - ``taxable_income(n)`` -- a conversion and a tax-deferred withdrawal are both fully
        taxable ordinary income;
      - ``cash_flow(n)`` -- cancels once the 10% early-withdrawal penalty is off, which is
        why the substitution is confined to ``n >= n595[i]``;
      - ``withdrawal_limit(i,1,n)`` = b - w - x -- exactly invariant;
      - the RMD floor, the 5-year Roth retainer and the remaining limits only loosen.

    Returns ``(x_new, n_moves, blocked_reason)``. The input is not modified.
    """
    reason = ctx.roth_repair_blocked
    if reason is not None:
        return x, 0, reason

    y = np.array(x, dtype=float, copy=True)
    vm = ctx.vm
    moves = 0
    for i in range(ctx.N_i):
        for n in range(int(ctx.n595[i]), min(ctx.N_n, int(ctx.horizons[i]))):
            ix, i2, i1 = vm["x"].idx(i, n), vm["w"].idx(i, 2, n), vm["w"].idx(i, 1, n)
            # Never push a variable below its own lower bound: a conversion pinned by
            # the "Roth conv fixed" column has lb == ub.
            m = min(y[ix], y[i2], y[ix] - ctx.col_lb[ix])
            if m <= TOL_CENT:
                continue
            y[ix] -= m
            y[i2] -= m
            y[i1] += m
            moves += 1
    return y, moves, None


def build_polish_overrides(x, ctx, nconts, nvars):
    """Column pins for the churn-minimizing polish LP.

    Pinning spending and the terminal balances is what makes the polish unable to change
    any reported objective; pinning the conversion schedule preserves a headline output
    and locks in whatever Stage A did. Everything else -- surplus, deposits, withdrawals,
    interior balances and the whole tax-accounting block -- stays free so the bracket and
    deduction equalities can re-establish themselves exactly.
    """
    vm = ctx.vm
    pins = {}
    for n in range(ctx.N_n):
        j = vm["g"].idx(n)
        pins[j] = (x[j], x[j])
    for i in range(ctx.N_i):
        for jj in range(ctx.N_j):
            j = vm["b"].idx(i, jj, ctx.N_n)
            pins[j] = (x[j], x[j])
        for n in range(ctx.N_n):
            j = vm["x"].idx(i, n)
            pins[j] = (x[j], x[j])
    # Binaries stay at their incumbent values; the polish is solved as an LP.
    for j in range(nconts, nvars):
        v = float(np.round(x[j]))
        pins[j] = (v, v)
    return pins


def build_polish_objective(ctx, c_orig, gamma_n, nvars, eps=1e-6):
    """Objective vector for the polish LP: minimize deflated surplus, tie-broken by the original.

    The min-surplus face is itself degenerate, so without the second term two solvers would
    report different -- equally optimal -- per-year withdrawal splits. Carrying a small
    multiple of the original objective reproduces the original solve's preferences,
    including the epsilon terms already in ``_build_objective_vector``.
    """
    c = np.zeros(nvars)
    for n in range(ctx.N_n):
        c[ctx.vm["s"].idx(n)] = 1.0 / max(gamma_n[n], 1e-12)
    scale = float(np.max(np.abs(c_orig))) or 1.0
    return c + (eps / scale) * np.asarray(c_orig)
