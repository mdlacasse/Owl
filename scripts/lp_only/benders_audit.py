"""Audit of Plan._benders_solve: is the first master candidate feasible, and are the cuts valid?

Runs on the MILP engine (PYTHONPATH=/Users/mdlacasse/Owl/src), read-only.

Test A -- initialization. `_benders_solve` seeds z* for the IRMAA family from `self.MAGI_n`, which
`solve()` resets to zeros, so on the first SC iteration every year is assigned IRMAA bracket 0.
This rebuilds that assignment and checks whether the subproblem LP is feasible; then it repeats with
z* seeded from the SC loop's own converged regimes.

Test B -- cut validity. For a feasible z*, take the subproblem duals, form the Benders cut exactly as
the code does (beta = -A_col^T pi, alpha = Q(z*) - beta^T z*), then flip one year's bracket to z' and
compare the cut's prediction with the subproblem's true value Q(z'). For a convex value function a
valid cut must satisfy alpha + beta^T z' <= Q(z') for every z'. A violation means the cut cuts off
feasible assignments, i.e. the sign convention or the coefficients are wrong.

Usage: PYTHONPATH=/Users/mdlacasse/Owl/src uv run python benders_audit.py [YEAR]
"""
import contextlib
import io
import sys

import numpy as np
import owlplanner as owl
from owlplanner import tax_federal as tx

assert "/Users/mdlacasse/Owl/src" in owl.__file__, owl.__file__
YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 1983
ALL4 = {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize", "withNIIT": "optimize"}


def build(extra):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p = owl.readConfig("/Users/mdlacasse/Owl/examples/Case_dana.toml", verbose=False)
        o = dict(p.solverOptions)
        o.update({"solver": "MOSEK", "gap": 1e-4, "maxTime": 600, "numThreads": 2, **extra})
        o.pop("bequest", None)
        o["netSpending"] = 58.0
        p.setRates("historical", YEAR)
    return p, o


# The SC loop's own answer: its MAGI is what a sane initialization would use.
loop, o_loop = build({})
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    loop.solve("maxBequest", options=o_loop)
print(f"{YEAR}: loop {loop.caseStatus} {loop.convergenceType} bequest {loop.bequest:,.2f}")

p, o = build(ALL4)
# Run solve()'s full setup, then stop where the SC loop would start: the state _benders_solve
# sees on its first call (MAGI_n reset to zeros, gain fractions initialized).
import types


def setup_only(self, objective, options, solverMethod):
    self._computeNLstuff(None, True)
    self._init_gain_fraction()
    self._buildConstraints(objective, options)
    self.caseStatus = "audit-setup"


p._scSolve = types.MethodType(setup_only, p)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    p.solve("maxBequest", options=o)
p._decomp_use_mosek = True
Lb, Ub = p.B.arrays()
master_cols = [c for name in ("zs", "zj", "zm", "za", "zl") if name in p.vm
               for c in range(p.vm[name].start, p.vm[name].end) if Lb[c] < Ub[c] - 1e-9]
pos_of = {c: i for i, c in enumerate(master_cols)}
print(f"  master binaries: {len(master_cols)}  (MAGI_n at this point: max {np.max(p.MAGI_n):.1f})")


# The code's starting point: LP relaxation of the whole model (zs/zl/zj are rounded from it).
lp_obj, lp_x, lp_ok, _, _ = p._run_mip(p.A, p.B, p.c, o, lp_relax=True, update_warm=False)
assert lp_ok, "LP relaxation failed"
print(f"  LP relaxation obj {-lp_obj / p.gamma_n[-1]:,.2f}")


def zstar_from_magi(magi):
    """The code's own initialization, given a MAGI series: zm from MAGI, everything else rounded."""
    z = np.array([float(round(lp_x[c])) for c in master_cols])
    if "za" in p.vm and "haca" in p.vm and p.vm["za"].shape == p.vm["haca"].shape:
        zb, hb = p.vm["za"], p.vm["haca"]
        for nn in range(zb.shape[0]):
            best = int(np.argmax([lp_x[hb.idx(nn, q)] for q in range(zb.shape[1])]))
            for q in range(zb.shape[1]):
                c = zb.idx(nn, q)
                if c in pos_of:
                    z[pos_of[c]] = 1.0 if q == best else 0.0
    blk = p.vm["zm"]
    Nrows, Nq = blk.shape
    nmstart = p.N_n - Nrows
    for nn in range(Nrows):
        n = nmstart + nn
        mymagi = magi[n - 2] if n - 2 >= 0 else 0.0
        status = 0 if p.N_i == 1 or not (n < p.horizons[0] and n < p.horizons[1]) else 1
        best_q = 0
        for q in range(Nq - 1, -1, -1):
            if mymagi > p.gamma_n[n] * tx.irmaaBrackets[status][q]:
                best_q = q
                break
        for q in range(Nq):
            c = blk.idx(nn, q)
            if c in pos_of:
                z[pos_of[c]] = 1.0 if q == best_q else 0.0
    return z


def sp(z):
    ov = {c: (float(z[i]), float(z[i])) for i, c in enumerate(master_cols)}
    obj, x, pi, ok = p._run_lp_with_duals(p.A, p.B, p.c, o, col_overrides=ov)
    return obj, pi, ok


print("\nTest A: is the first master candidate feasible?")
for tag, magi in (("zeros (what the code uses on SC iteration 0)", p.MAGI_n),
                  ("the SC loop's converged MAGI", loop.MAGI_n)):
    z = zstar_from_magi(magi)
    obj, pi, ok = sp(z)
    brackets = [int(round(z[pos_of[p.vm["zm"].idx(nn, q)]])) * q
                for nn in range(p.vm["zm"].shape[0]) for q in range(p.vm["zm"].shape[1])
                if p.vm["zm"].idx(nn, q) in pos_of]
    print(f"  {tag:46} SP LP {'feasible, obj ' + format(-obj / p.gamma_n[-1], ',.2f') if ok else 'INFEASIBLE'}"
          f"   IRMAA brackets selected: max {max(brackets) if brackets else 0}")

print("\nTest B: are the Benders cuts valid?")
z0 = zstar_from_magi(loop.MAGI_n)
obj0, pi0, ok0 = sp(z0)
if not ok0:
    print("  cannot test: the seeded subproblem is infeasible")
    sys.exit(0)
col_rows = [[] for _ in range(p.A.nvars)]
for i, (inds, vals) in enumerate(zip(p.A.Aind, p.A.Aval, strict=True)):
    for j, v in zip(inds, vals, strict=True):
        col_rows[j].append((i, float(v)))
beta = np.array([-sum(pi0[r] * v for r, v in col_rows[c]) for c in master_cols])
alpha = obj0 - float(beta @ z0)
print(f"  Q(z*) = {obj0:,.2f} (internal units); cut: eta >= {alpha:,.2f} + beta^T z, |beta| max {np.max(np.abs(beta)):,.2f}")

blk = p.vm["zm"]
Nrows, Nq = blk.shape
tested = violations = 0
for nn in range(0, Nrows, max(1, Nrows // 6)):
    cur = next((q for q in range(Nq) if blk.idx(nn, q) in pos_of and z0[pos_of[blk.idx(nn, q)]] > 0.5), None)
    if cur is None:
        continue
    for newq in (cur + 1, cur - 1):
        if not (0 <= newq < Nq) or blk.idx(nn, newq) not in pos_of:
            continue
        z1 = z0.copy()
        for q in range(Nq):
            c = blk.idx(nn, q)
            if c in pos_of:
                z1[pos_of[c]] = 1.0 if q == newq else 0.0
        q1, _, ok1 = sp(z1)
        if not ok1:
            print(f"    year row {nn}: bracket {cur}->{newq}: SP infeasible (needs a feasibility cut)")
            continue
        pred = alpha + float(beta @ z1)
        tested += 1
        bad = pred > q1 + 1e-6 * max(1.0, abs(q1))
        violations += bad
        print(f"    year row {nn}: bracket {cur}->{newq}: true Q {q1:,.2f}  cut predicts {pred:,.2f}  "
              f"{'VIOLATION (cut above true value)' if bad else 'ok (cut is a valid lower bound)'}")
print(f"  {violations} violations in {tested} flips tested")
