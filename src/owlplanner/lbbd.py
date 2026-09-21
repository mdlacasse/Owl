"""
Logic-based Benders decomposition over the tax-regime binaries.

The MILP's binaries all select a *regime* for one year of one tax family: an IRMAA bracket, the
Social Security taxability tier, the LTCG bracket, the NIIT side of its threshold, an ACA bracket.
Fix every one of them and what remains is a pure LP. That gives a natural decomposition:

    master      chooses a regime assignment z (the binaries, plus the rows that involve only them)
    subproblem  the LP with z fixed, which returns either a plan and its duals, or infeasibility

and two ways to learn from a subproblem:

    optimality cut   eta >= Q(z*) + beta^T (z - z*),  beta = -A_z^T pi
                     valid because the LP value function is convex in the fixed columns
    feasibility cut  sum_{z*_j = 1} (1 - z_j) + sum_{z*_j = 0} z_j >= 1 over a conflicting subset,
                     which forbids that subset from recurring

Three things make this work where the previous implementation did not:

  * the first assignment comes from the self-consistent loop's own solution, not from rounding an
    LP relaxation family by family -- that rounding is jointly infeasible even when each family is
    feasible alone, and it is what stalled the old code on its first iteration;
  * an infeasible subproblem produces a cut instead of ending the run, and the conflict is narrowed
    by deletion filtering so the cut forbids a few years rather than the whole assignment;
  * the master is kept near the incumbent by a local-branching constraint whose radius grows only
    when the master stops producing new assignments, which is what keeps no-good cuts from having
    to enumerate an astronomical space.

The result is anytime: an incumbent exists from the first subproblem onward, and the bound from the
master certifies it when the two meet. What is certified is optimality *within the model the SC loop
presents at this iteration*: quantities the loop still carries (investment income for NIIT, the
cost-basis gain fractions, the OBBBA deduction's MAGI) are parameters here, as they are for the
monolithic MIP.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import time

import numpy as np

from . import abcapi as abc

# Families whose binaries select a regime; everything else stays in the subproblem.
REGIME_FAMILIES = ("zs", "zj", "zm", "za", "zl")
BIG_ETA = 1e12
DEFAULT_BUDGET = 600.0  # seconds of wall clock spent chasing a certificate
MAX_CONFLICT_PROBES = 12  # LP solves spent narrowing one infeasible assignment


class _Model:
    """The pieces of a built plan that the decomposition needs."""

    def __init__(self, plan, objective, options):
        self.plan = plan
        self.objective = objective
        self.options = options
        lb, ub = plan.B.arrays()
        self.cols = [
            c
            for name in REGIME_FAMILIES
            if name in plan.vm
            for c in range(plan.vm[name].start, plan.vm[name].end)
            if lb[c] < ub[c] - 1e-9
        ]
        self.pos = {c: i for i, c in enumerate(self.cols)}
        # Which columns belong to the same year of the same family: the unit a cut should forbid.
        self.groups = []
        for name in REGIME_FAMILIES:
            if name not in plan.vm:
                continue
            blk = plan.vm[name]
            rows = blk.shape[0] if len(blk.shape) == 2 else blk.size
            for r in range(rows):
                if len(blk.shape) == 2:
                    group = [blk.idx(r, q) for q in range(blk.shape[1])]
                else:
                    group = [blk.start + r]
                group = [c for c in group if c in self.pos]
                if group:
                    self.groups.append(group)
        # Column -> rows, for the optimality-cut coefficients.
        self.col_rows = [[] for _ in range(plan.A.nvars)]
        for i, (inds, vals) in enumerate(zip(plan.A.Aind, plan.A.Aval, strict=True)):
            for j, v in zip(inds, vals, strict=True):
                self.col_rows[j].append((i, float(v)))
        # Rows involving only regime columns (exactly-one, monotonicity): the master keeps them.
        colset = set(self.cols)
        self.master_rows = [
            i for i, inds in enumerate(plan.A.Aind) if inds and all(j in colset for j in inds)
        ]

    def overrides(self, z):
        return {c: (float(z[i]), float(z[i])) for i, c in enumerate(self.cols)}

    def subproblem(self, z, with_duals=True):
        """Solve the LP with the assignment fixed. Returns (obj, x, duals, ok)."""
        p = self.plan
        if with_duals:
            return p._run_lp_with_duals(p.A, p.B, p.c, self.options, col_overrides=self.overrides(z))
        obj, x, ok, _msg, _gap = p._run_mip(
            p.A, p.B, p.c, self.options, col_overrides=self.overrides(z), lp_relax=True, update_warm=False
        )
        return obj, x, None, ok


def assignment_from_plan(model, source):
    """The regime assignment a solved plan implies, read off its own binaries."""
    z = np.zeros(len(model.cols))
    for i, c in enumerate(model.cols):
        z[i] = float(np.round(source[c])) if source is not None else 0.0
    return z


def seed_assignment(model, seed_x):
    """Regimes to start from: the previous solution when there is one, else the LP relaxation.

    A previous SC iteration's plan already satisfies every regime row, so its binaries are a
    consistent assignment. Without one, the relaxation is rounded per year and family (argmax within
    each group, so exactly-one still holds). That rounding can be jointly infeasible -- it is what
    stalled the old Benders code -- but here an infeasible assignment only produces a cut.
    """
    if seed_x is not None:
        return assignment_from_plan(model, seed_x)
    p = model.plan
    _obj, x, ok, _msg, _gap = p._run_mip(
        p.A, p.B, p.c, model.options, lp_relax=True, update_warm=False
    )
    z = np.zeros(len(model.cols))
    if not ok:
        return z
    for group in model.groups:
        best = max(group, key=lambda c: x[c])
        for c in group:
            z[model.pos[c]] = 1.0 if c == best else 0.0
    return z


def optimality_cut(model, z, obj, duals):
    beta = np.array([-sum(duals[r] * v for r, v in model.col_rows[c]) for c in model.cols])
    return float(obj - beta @ z), beta


def conflict_of(model, z, budget_probes=MAX_CONFLICT_PROBES):
    """Narrow an infeasible assignment to a subset that is still infeasible.

    Deletion filtering over year-family groups: release one group at a time (its columns go back to
    [0, 1]); if the LP is still infeasible without it, that group was not part of the conflict.
    """
    kept = list(range(len(model.groups)))
    probes = 0
    for gi in list(kept):
        if probes >= budget_probes or len(kept) <= 1:
            break
        trial = [g for g in kept if g != gi]
        ov = {}
        for g in trial:
            for c in model.groups[g]:
                ov[c] = (float(z[model.pos[c]]), float(z[model.pos[c]]))
        p = model.plan
        _obj, _x, _pi, ok = p._run_lp_with_duals(p.A, p.B, p.c, model.options, col_overrides=ov)
        probes += 1
        if not ok:
            kept = trial  # still infeasible without this group, so it is not the cause
    return [c for g in kept for c in model.groups[g]]


def _master(model, cuts, nogoods, incumbent, radius):
    """Master MILP: min eta over regime binaries, cuts, and a local-branching ball."""
    n = len(model.cols)
    eta = n
    A = abc.ConstraintMatrix(n + 1)
    B = abc.Bounds(n + 1, 0)
    for i in range(n):
        B.setBinary(i)
    B.setRange(eta, -BIG_ETA, BIG_ETA)
    c = abc.Objective(n + 1)
    c.setElem(eta, 1.0)

    plan = model.plan
    for i in model.master_rows:
        row = {model.pos[j]: v for j, v in zip(plan.A.Aind[i], plan.A.Aval[i], strict=True)}
        A.addNewRow(row, plan.A.lb[i], plan.A.ub[i], tag=plan.A.tags[i])
    for alpha, beta in cuts:
        row = {eta: 1.0}
        for i in range(n):
            if beta[i] != 0.0:
                row[i] = -float(beta[i])
        A.addNewRow(row, float(alpha), np.inf, tag=("lbbd_optimality",))
    for cols, zval in nogoods:
        # sum over the conflicting columns of (z != z*) >= 1
        row, rhs = {}, 1.0
        for col in cols:
            i = model.pos[col]
            if zval[i] > 0.5:
                row[i] = row.get(i, 0.0) - 1.0
                rhs -= 1.0
            else:
                row[i] = row.get(i, 0.0) + 1.0
        A.addNewRow(row, rhs, np.inf, tag=("lbbd_feasibility",))
    if incumbent is not None and radius is not None:
        row, rhs = {}, float(radius)
        for i in range(n):
            if incumbent[i] > 0.5:
                row[i] = -1.0
                rhs -= 1.0
            else:
                row[i] = 1.0
        A.addNewRow(row, -np.inf, rhs, tag=("lbbd_local_branching",))
    return A, B, c


def solve(plan, objective, options, seed_x=None):
    """Run the decomposition. Returns the (objfn, x, success, message, gap) contract of a solver."""
    t0 = time.time()
    # decompBudget is a deadline for the whole solve, not for one SC iteration: the loop calls this
    # once per iteration and only the last one is kept, so a per-iteration budget would spend the
    # allowance many times over.
    if getattr(plan, "_lbbd_deadline", None) is None:
        plan._lbbd_deadline = t0 + float(options.get("decompBudget", DEFAULT_BUDGET))
    budget = max(0.0, plan._lbbd_deadline - t0)
    max_iter = int(options.get("decompMaxIter", 100))
    mygap = float(options.get("gap", 1e-4))
    plan._buildConstraints(objective, options)
    model = _Model(plan, objective, options)
    if not model.cols:
        return plan._run_mip(plan.A, plan.B, plan.c, options)

    z = seed_assignment(model, seed_x)
    seed_z = z.copy()
    # The model's own LP relaxation is a valid lower bound, and a far better starting point than
    # eta's artificial bound: the master's cuts only have to close what it leaves open.
    lp_obj, _lx, lp_ok, _lm, _lg = plan._run_mip(plan.A, plan.B, plan.c, options, lp_relax=True, update_warm=False)
    incumbent_x, UB = None, np.inf
    LB = float(lp_obj) if (lp_ok and lp_obj is not None) else -np.inf
    cuts, nogoods = [], []
    radius = max(4, len(model.groups) // 8)
    seen = set()
    msg = "LBBD"

    for it in range(max_iter):
        obj, x, duals, ok = model.subproblem(z)
        if ok:
            if obj < UB:
                UB, incumbent_x = obj, np.array(x)
            cuts.append(optimality_cut(model, z, obj, duals))
        else:
            cols = conflict_of(model, z)
            nogoods.append((cols, z.copy()))
        if UB < np.inf and LB > -np.inf:
            gap = (UB - LB) / max(abs(UB), 1.0)
            if gap <= mygap:
                msg = f"LBBD certified ({it + 1} rounds, {len(cuts)} cuts)"
                return UB, incumbent_x, True, msg, float(max(gap, 0.0))
        if time.time() - t0 > budget:
            msg = f"LBBD budget reached ({it + 1} rounds)"
            break

        # Bound master: every cut, no local-branching ball, so its value is a valid lower bound.
        mp_A, mp_B, mp_c = _master(model, cuts, nogoods, None, None)
        mobj, mx, mok, _m, _g = plan._run_mip(mp_A, mp_B, mp_c, options, update_warm=False)
        if not mok or mobj is None:
            msg = f"LBBD master exhausted ({it + 1} rounds)"
            break
        LB = max(LB, float(mobj))
        if UB < np.inf:
            gap = (UB - LB) / max(abs(UB), 1.0)
            if gap <= mygap:
                msg = f"LBBD certified ({it + 1} rounds, {len(cuts)} cuts, {len(nogoods)} no-goods)"
                return UB, incumbent_x, True, msg, float(max(gap, 0.0))

        z_new = np.round(mx[: len(model.cols)]).astype(float)
        if z_new.tobytes() in seen:
            # The bound master is repeating itself; look elsewhere with a local-branching ball.
            mp_A, mp_B, mp_c = _master(model, cuts, nogoods, z, radius)
            _o2, mx2, ok2, _m2, _g2 = plan._run_mip(mp_A, mp_B, mp_c, options, update_warm=False)
            if ok2 and mx2 is not None:
                z_new = np.round(mx2[: len(model.cols)]).astype(float)
            if z_new.tobytes() in seen:
                radius = min(len(model.groups), radius * 2)
                msg = f"LBBD stalled ({it + 1} rounds)"
                break
        seen.add(z_new.tobytes())
        z = z_new

    if incumbent_x is None:
        return plan._run_mip(plan.A, plan.B, plan.c, options)
    gap = (UB - LB) / max(abs(UB), 1.0) if LB > -np.inf else -1.0

    # The master's own bound comes from the big-M relaxation and closes far too slowly to certify
    # anything. Branch-and-bound closes it because it branches, and it does so much faster when it
    # starts from this incumbent: every node that cannot beat it is pruned. Spend what is left of
    # the budget there, and keep whichever answer is better.
    # Certify only once the loop has settled: while its parameters still move, this iterate is
    # discarded anyway, and branch-and-bound on it is wasted budget.
    settled = seed_x is not None and np.array_equal(seed_z, assignment_from_plan(model, incumbent_x))
    if settled and gap > mygap and time.time() < plan._lbbd_deadline:
        left = plan._lbbd_deadline - time.time()
        certify_options = dict(options)
        certify_options["maxTime"] = min(float(options.get("maxTime", left)), left)
        plan._mip_warm_start = np.asarray(incumbent_x, dtype=float)
        try:
            mono = plan._run_mip(plan.A, plan.B, plan.c, certify_options, update_warm=False)
        finally:
            plan._mip_warm_start = None
        if mono[2] and mono[0] is not None and mono[0] <= UB + abs(UB) * 1e-12:
            rounds = msg
            return mono[0], mono[1], True, f"{rounds} + warm-started MIP", float(mono[4])
    return UB, incumbent_x, True, msg, float(gap)
