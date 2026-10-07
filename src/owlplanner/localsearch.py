"""
Local search (fix-and-optimize) for the threshold binaries: mipStrategy="local-search".

When tax families are solved with binary variables (withSSTaxability, withMedicare, withACA,
withLTCG, withNIIT = "optimize"), the default strategy hands the whole mixed-integer program to
branch-and-bound. That is a complete search that stops at a relative gap, and it can take tens of
minutes per solve. Local search replaces it, inside each iteration of the self-consistent loop,
by a sequence of small restricted problems, each solved with most binaries pinned:

1. A feasible starting plan, cheapest first: the previous iteration's binaries (an LP); then a
   repair from the self-consistent loop's plan, with its withdrawals and conversions held in a
   narrow band and the binaries free. Never the full program: if every attempt fails, the
   search stops and the caller keeps the loop's plan.
2. (a) Social Security taxability pinned; the other families freed one at a time.
   (b) The other families pinned; Social Security taxability free within a local-branching
       ball of at most `radius` flips from the current plan.
   (a') When neither moved: the other families freed jointly, once.
   (c)  The binaries of every family freed in the years where the plan's own income implies a
        different cost than the one charged.
   Repeat until no step improves the objective.

Every restricted problem contains the current plan, so it is feasible and can never return a
worse one: the search only descends. It carries no certificate, and it can stop short of the
optimum, chiefly on the unrestricted problem, which has the most freedom.

Each step is capped by branch-and-bound nodes (`STEP_NODES`, so that the answer does not depend on
machine speed or load), with a time backstop (`stepTime`), and solved to a relative gap of at most
`STEP_GAP`, whatever the case's gap; the whole search has a budget (`totalTime`). A capped step
keeps the best plan it found. When the loop rebuilds the problem of the previous iteration, that
iteration's plan is returned without searching again. Withdrawal-ordering gates
(withdrawalOrder="taxable_first") and claiming-age selectors (withSSAges="optimize") are not searched: Plan.solve() hands such cases to
branch-and-bound.

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

import copy
import hashlib
import time

import numpy as np

# Binary families the search moves, and the fixed-point residual family that measures each.
# Fork: "zx", the tier binaries of a state's income-tiered retirement exclusion (NJ), is a family
# too. Left out, the LP start relaxed it to fractional tiers, and no later step could match that
# start, so the search returned a plan claiming part of a tier above its ceiling. It has no
# fixed-point residual: the exclusion is exact within each solve.
FAMILIES = ("zm", "zs", "za", "zl", "zj", "zx")
RESIDUAL_FAMILY = {"zs": "SS", "zm": "IRMAA", "za": "ACA", "zj": "NIIT", "zl": "LTCG"}
FAMILY_LABEL = {"zs": "SS", "zm": "IRMAA", "za": "ACA", "zl": "LTCG", "zj": "NIIT", "zx": "state exclusion"}

STEP_TIME = 60.0  # seconds per restricted solve: a backstop; the node limit below is the real cap
# Branch-and-bound nodes per restricted solve. A node limit, unlike a time limit, gives the same
# answer on any machine and under any load. The solvers count nodes differently; measured on the
# shipped examples at STEP_GAP, finished steps need up to ~3,000 (HiGHS) or ~19,500 (MOSEK). The
# caps favour speed: lifting them changes results by 0.07% at most, for up to 3.3x the time.
STEP_NODES = {"HiGHS": 3000, "MOSEK": 20000}
# Relative MIP gap of each restricted solve. A loose gap suits a full branch-and-bound, where it
# saves real time; here the problems are small and the gap costs nothing, while a loose one stops
# them before small preferences in the objective count (the partial-bequest weight, 0.1%, under
# the 0.3% gap applied when Medicare is solved as MILP) and leaves money the household does not
# need to be spent to no purpose.
STEP_GAP = 1e-4
TOTAL_TIME = 300.0  # seconds for the whole search, per plan solve
RADIUS = 4  # local-branching radius on the SS-taxability binaries
_IMPROVE = 1e-7  # relative objective improvement that counts as a move
# Repairs from a plan: (label, absolute half-band in $, which withdrawals are held).
_REPAIRS = (
    ("withdrawals and conversions +-$1", 1.0, "all"),
    ("withdrawals and conversions +-$1,000", 1000.0, "all"),
    ("tax-deferred withdrawals and conversions +-$1", 1.0, "deferred"),
    ("conversions +-$1", 1.0, "none"),
)


class NoIncumbent(Exception):
    """No feasible starting plan: the caller keeps the self-consistent loop's plan."""


class LocalSearch:
    """Fix-and-optimize over the threshold binaries; one instance per Plan.solve()."""

    def __init__(self, plan, seed_w, seed_x, step_time=STEP_TIME, total_time=TOTAL_TIME, radius=RADIUS,
                 step_nodes=None):
        self.plan = plan
        self.seed_w = np.asarray(seed_w, dtype=float)
        self.seed_x = np.asarray(seed_x, dtype=float)
        self.step_time = float(step_time)
        self.radius = int(radius)
        self.step_nodes = int(step_nodes) if step_nodes else 0
        self.deadline = time.time() + float(total_time)
        self.use_mosek = False  # set by Plan.solve() from the solver asked for
        self.prev = None  # the previous loop iteration's plan
        self._last = None  # (problem fingerprint, objective, plan) of the previous loop iteration
        self.iteration = 0
        self.log = []  # one entry per loop iteration: {"steps": [...], "time": s}

    # ----- helpers -----------------------------------------------------------------------------
    def _cols(self, name):
        blk = self.plan.vm._blocks.get(name)
        return np.arange(blk.start, blk.end) if blk is not None else np.arange(0)

    def _families(self):
        return [f for f in FAMILIES if f in self.plan.vm._blocks]

    def _pin(self, x, families):
        """Column overrides holding the binaries of `families` at their values in x."""
        ov = {}
        for f in families:
            for c in self._cols(f):
                v = float(round(x[c]))
                ov[int(c)] = (v, v)
        return ov

    def _band(self, ov, name, src, h0, which="all"):
        cc = self._cols(name).reshape(self.plan.vm[name].shape)
        for idx in np.ndindex(cc.shape):
            if which == "deferred" and idx[1] != 1:
                continue
            v = float(src[idx])
            h = max(h0, 1e-4 * abs(v))
            ov[int(cc[idx])] = (max(0.0, v - h), v + h)

    def _mip(self, options, overrides=None, A=None, warm=None, lp=False):
        p = self.plan
        opts = dict(options)
        opts["maxTime"] = min(float(options.get("maxTime", self.step_time)), self.step_time)
        opts["mipMaxNodes"] = self.step_nodes or STEP_NODES["MOSEK" if self.use_mosek else "HiGHS"]
        opts["gap"] = min(float(options.get("gap", STEP_GAP)), STEP_GAP)
        p._mip_warm_start = warm
        # _scSolve infers the backend from the solve method, which is this search's: say it here.
        p._use_mosek = self.use_mosek
        t = time.time()
        try:
            res = p._run_mip(A if A is not None else p.A, p.B, p.c, opts, lp_relax=lp,
                             col_overrides=overrides, update_warm=False)
        except Exception as e:  # a solver API error is a failed step, not a failed solve
            res = (None, None, False, str(e)[:120], -1.0)
        finally:
            p._mip_warm_start = None
        return res, time.time() - t

    def _fingerprint(self):
        """Digest of the problem as built: equal digests mean the same restricted problems."""
        p = self.plan
        h = hashlib.sha1()
        for arr in (*p.A.to_csr(), np.asarray(p.A.lb, dtype=float), np.asarray(p.A.ub, dtype=float),
                    *p.B.arrays(), p.B.integralityArray(), p.c.arrays()):
            h.update(np.ascontiguousarray(arr).tobytes())
        return h.digest()

    def _step(self, steps, label, res, dt):
        steps.append({"step": label, "ok": bool(res[2]), "objective": res[0] if res[2] else None,
                      "seconds": round(dt, 2), "nodes": getattr(self.plan, "_lastMipNodes", None)})
        msg = f"objective {-res[0]:,.0f}" if res[2] else f"failed ({res[3]})"
        self.plan.mylog.vprint(f"Local search, iteration {self.iteration}: {label}: {msg} in {dt:.2f}s.")

    @staticmethod
    def _better(res, best):
        return res[2] and res[0] < best[0] - _IMPROVE * abs(best[0])

    # ----- the starting plan -------------------------------------------------------------------
    def _incumbent(self, options, steps):
        p = self.plan
        have_prev = self.prev is not None and len(self.prev) == p.nvars
        if have_prev:
            res, dt = self._mip(options, overrides=self._pin(self.prev, self._families()), lp=True)
            self._step(steps, "start: previous binaries (LP)", res, dt)
            if res[2]:
                return res
        sources = []
        if have_prev:
            sources.append(("previous plan", self.prev[self._cols("w")].reshape(p.vm["w"].shape),
                            self.prev[self._cols("x")].reshape(p.vm["x"].shape)))
        sources.append(("loop plan", self.seed_w, self.seed_x))
        for label, src_w, src_x in sources:
            for what, h0, which in _REPAIRS:
                ov = {}
                if which != "none":
                    self._band(ov, "w", src_w, h0, which)
                self._band(ov, "x", src_x, h0)
                res, dt = self._mip(options, overrides=ov)
                self._step(steps, f"start: repair from the {label}, {what}", res, dt)
                if res[2]:
                    return res
        raise NoIncumbent()

    # ----- residual-targeted neighborhood ------------------------------------------------------
    def _inconsistent_columns(self, x):
        """Binary columns of every family in the years where the plan's own income implies a
        different cost than the one charged (Plan._fixedPointResidualByYear)."""
        p = self.plan
        p._aggregateResults(x, short=True)  # the loop aggregates the returned plan again
        res = p._fixedPointResidualByYear(includeMedicare="zm" in p.vm._blocks)
        free, where = set(), {}
        for f in self._families():
            arr = res.get(RESIDUAL_FAMILY.get(f))
            if arr is None:
                continue
            years = np.where(np.abs(arr) > 1.0)[0]
            if len(years):
                where[FAMILY_LABEL[f]] = [int(p.year_n[n]) for n in years]
            free |= self._year_columns(f, years)
        return free, where

    def _year_columns(self, family, years):
        p = self.plan
        blk = p.vm[family]
        out = []
        for n in years:
            if family in ("zs", "zj"):
                rows = [n]
            elif family == "zm":
                rows = [n - p.nm] if 0 <= n - p.nm < blk.shape[0] else []
            elif family == "za":
                rows = [n] if n < blk.shape[0] else []
            else:  # zl is (2, N_n): by column
                out += [blk.idx(r, n) for r in range(blk.shape[0])]
                continue
            for r in rows:
                if len(blk.shape) == 1:
                    out.append(blk.idx(r))
                else:
                    out += [blk.idx(r, q) for q in range(blk.shape[1])]
        return set(int(c) for c in out)

    # ----- one loop iteration ------------------------------------------------------------------
    def solve(self, objective, options):
        """Drop-in for Plan._milpSolve / _mosekSolve: (objective, x, success, message, gap)."""
        p = self.plan
        p._buildConstraints(objective, options)
        steps = []
        t0 = time.time()
        # The loop's last iteration often rebuilds the previous problem: reuse that plan.
        fp = self._fingerprint()
        if self._last is not None and self._last[0] == fp:
            p.mylog.vprint(f"Local search, iteration {self.iteration}: same problem as the last; reusing its plan.")
            self.log.append({"steps": steps, "time": round(time.time() - t0, 2)})
            self.iteration += 1
            _, obj, x = self._last
            p._highs_warm_start = x.copy()
            return obj, x.copy(), True, "Local search", -1.0
        try:
            best = self._incumbent(options, steps)
        except NoIncumbent:
            self.log.append({"steps": steps, "time": round(time.time() - t0, 2)})
            raise

        fams = self._families()
        others = [f for f in fams if f != "zs"]
        for rnd in range(8):
            if time.time() > self.deadline:
                p.mylog.vprint("Local search: time budget spent; keeping the current plan.")
                break
            improved = False
            # (a) SS taxability pinned; the other families freed one at a time.
            for f in others:
                res, dt = self._mip(options, overrides=self._pin(best[1], [g for g in fams if g != f]), warm=best[1])
                self._step(steps, f"round {rnd} (a): {FAMILY_LABEL[f]} free", res, dt)
                if self._better(res, best):
                    best, improved = res, True
            # (b) the others pinned; SS taxability within a local-branching ball.
            if "zs" in fams:
                A = copy.deepcopy(p.A)
                row, ones = {}, 0
                for c in self._cols("zs"):
                    if round(best[1][c]) >= 1:
                        row[int(c)] = -1.0
                        ones += 1
                    else:
                        row[int(c)] = 1.0
                A.addNewRow(row, -np.inf, self.radius - ones, tag=("local_branching", 0))
                res, dt = self._mip(options, overrides=self._pin(best[1], others), A=A, warm=best[1])
                self._step(steps, f"round {rnd} (b): SS within {self.radius} flips", res, dt)
                if self._better(res, best):
                    best, improved = res, True
            if improved:
                continue
            # (a') nothing moved one family at a time: the others jointly, once.
            if len(others) > 1:
                pinned = [f for f in fams if f not in others]
                res, dt = self._mip(options, overrides=self._pin(best[1], pinned), warm=best[1])
                self._step(steps, f"round {rnd} (a'): {', '.join(FAMILY_LABEL[f] for f in others)} free", res, dt)
                if self._better(res, best):
                    best = res
                    continue
            # (c) every family freed in the years where the plan is inconsistent.
            free, where = self._inconsistent_columns(best[1])
            if not free:
                break
            ov = {c: v for c, v in self._pin(best[1], fams).items() if c not in free}
            res, dt = self._mip(options, overrides=ov, warm=best[1])
            desc = "; ".join(f"{k} {v}" for k, v in where.items())
            self._step(steps, f"round {rnd} (c): inconsistent years free [{desc}]", res, dt)
            if self._better(res, best):
                best = res
                continue
            break

        self.prev = best[1].copy()
        p._highs_warm_start = best[1].copy()
        self._last = (fp, best[0], best[1].copy())
        self.log.append({"steps": steps, "time": round(time.time() - t0, 2)})
        self.iteration += 1
        # No certificate: report the gap as unknown.
        return best[0], best[1], True, "Local search", -1.0
