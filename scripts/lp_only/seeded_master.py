"""Seed the regime assignment from the SC loop, fix it, and see what the subproblem is worth.

Runs on the MILP engine (PYTHONPATH=/Users/mdlacasse/Owl/src), read-only: no engine changes, the
model is built through solve()'s own setup and then queried directly.

Why: `_benders_solve` builds its first candidate by rounding a big-M LP relaxation family by family.
Each family alone is feasible, but the combination is not (benders_audit.py), and the code has no
feasibility cut, so it stops at iteration 1. The SC loop already produces a consistent set of
regimes; this checks whether that assignment is feasible, what it is worth, and whether the classical
Benders cut taken there is valid.

Regime -> binary mapping, from the constraint builders in plan.py:
  zm[nn,q] = 1 for the IRMAA bracket q of premium year n = nm+nn, from MAGI_n[n-2] (a $1 tolerance
             matches mediCosts' strict >)
  zs[n,0]  = 1 when the 50% tier is full (provisional income >= lo + min(hi-lo, ss))
  zs[n,1]  = 1 when taxable SS is capped at 0.85*ss
  zl[0,n]  = 1 when G_n <= T15 (0% room exists), zl[1,n] = 1 when G_n <= T20
  zj[n]    = 1 when MAGI_n > the NIIT threshold

Usage: PYTHONPATH=/Users/mdlacasse/Owl/src uv run python seeded_master.py YEAR [OUT.json]
"""
import contextlib
import io
import json
import sys
import types

import numpy as np
import owlplanner as owl
from owlplanner import tax_federal as tx

assert "/Users/mdlacasse/Owl/src" in owl.__file__, owl.__file__
YEAR = int(sys.argv[1])
OUT = sys.argv[2] if len(sys.argv) > 2 else None
ALL4 = {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize", "withNIIT": "optimize"}
REF = json.load(open("/Users/mdlacasse/Owl/pubs/Cost_of_Committing/images/milp_all72.json"))[str(YEAR)]


def build(extra):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p = owl.readConfig("/Users/mdlacasse/Owl/examples/Case_dana.toml", verbose=False)
        o = dict(p.solverOptions)
        o.update({"solver": "MOSEK", "gap": 1e-4, "maxTime": 600, "numThreads": 2, **extra})
        o.pop("bequest", None)
        o["netSpending"] = 58.0
        p.setRates("historical", YEAR)
    return p, o


loop, o_loop = build({})
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    loop.solve("maxBequest", options=o_loop)
print(f"{YEAR}: loop {loop.convergenceType} bequest {loop.bequest:,.2f} | milp_all72 lp_star "
      f"{REF['lp_star']['v']:,.2f} milp_star {REF['milp_star']['v']:,.2f}")

p, o = build(ALL4)


def setup_only(self, objective, options, solverMethod):
    self._computeNLstuff(None, True)
    self._init_gain_fraction()
    self._buildConstraints(objective, options)


p._scSolve = types.MethodType(setup_only, p)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    p.solve("maxBequest", options=o)
p._decomp_use_mosek = True
Lb, Ub = p.B.arrays()
free = lambda c: Lb[c] < Ub[c] - 1e-9  # noqa: E731

# ---- the loop's regimes -> a complete binary assignment -------------------------------------
Nn, g = loop.N_n, loop.gamma_n
ss = np.sum(loop.zetaBar_in, axis=0)
status = np.full(Nn, loop.N_i - 1)
if loop.N_i == 2 and loop.n_d < Nn:
    status[loop.n_d:] = 0
pins = {}

blk = p.vm["zm"]
Nrows, Nq = blk.shape
nmstart = Nn - Nrows
for nn in range(Nrows):
    n = nmstart + nn
    magi2 = loop.MAGI_n[n - 2] if n >= 2 else loop.prevMAGI[n]
    st = 0 if loop.N_i == 1 or not (n < loop.horizons[0] and n < loop.horizons[1]) else 1
    q_sel = int(np.sum(magi2 > g[n] * np.array(tx.irmaaBrackets[st])[1:] + 1.0))
    for q in range(Nq):
        c = blk.idx(nn, q)
        if free(c):
            pins[c] = 1.0 if q == q_sel else 0.0

lo, hi = tx.ssTaxabilityLo[status], tx.ssTaxabilityHi[status]
pi_inc = loop.MAGI_aca_n - 0.5 * ss
psi = tx.compute_social_security_taxability(loop.N_i, loop.MAGI_aca_n, ss, n_d=loop.n_d)
blk = p.vm["zs"]
for n in range(Nn):
    z1 = 1.0 if (ss[n] > 0 and psi[n] >= 0.85 - 1e-9) else 0.0
    z0 = 1.0 if (ss[n] > 0 and pi_inc[n] >= lo[n] + min(hi[n] - lo[n], ss[n])) else 0.0
    for k, v in ((0, z0), (1, z1)):
        c = blk.idx(n, k)
        if free(c):
            pins[c] = v

T15 = g[:Nn] * np.array([tx.capGainRates[s][0] for s in status])
T20 = g[:Nn] * np.array([tx.capGainRates[s][1] for s in status])
blk = p.vm["zl"]
for n in range(Nn):
    for k, v in ((0, 1.0 if loop.G_n[n] <= T15[n] else 0.0), (1, 1.0 if loop.G_n[n] <= T20[n] else 0.0)):
        c = blk.idx(k, n)
        if free(c):
            pins[c] = v

T_niit = np.array([200000.0 if s == 0 else 250000.0 for s in status])
blk = p.vm["zj"]
for n in range(Nn):
    c = blk.idx(n)
    if free(c):
        pins[c] = 1.0 if loop.MAGI_n[n] > T_niit[n] else 0.0

print(f"  seeded assignment: {len(pins)} binaries pinned")
obj, x, pi_dual, ok = p._run_lp_with_duals(p.A, p.B, p.c, o, col_overrides={c: (v, v) for c, v in pins.items()})
rec = {"year": YEAR, "loop": loop.bequest, "milp_star": REF["milp_star"]["v"], "n_pins": len(pins), "feasible": bool(ok)}
if not ok:
    print("  subproblem INFEASIBLE at the loop's own regimes")
else:
    val = -obj / g[-1]
    rec["seeded_value"] = float(val)
    print(f"  subproblem feasible: value {val:,.2f}  (loop {loop.bequest:+,.2f} | milp_star "
          f"{val - REF['milp_star']['v']:+,.2f})")

    # Classical Benders cut taken here: is it a valid lower bound under single-year bracket flips?
    cols = sorted(pins)
    col_rows = [[] for _ in range(p.A.nvars)]
    for i, (inds, vals) in enumerate(zip(p.A.Aind, p.A.Aval, strict=True)):
        for j, v in zip(inds, vals, strict=True):
            col_rows[j].append((i, float(v)))
    z0v = np.array([pins[c] for c in cols])
    beta = np.array([-sum(pi_dual[r] * v for r, v in col_rows[c]) for c in cols])
    alpha = obj - float(beta @ z0v)
    blk = p.vm["zm"]
    tested = viol = infeas = 0
    for nn in range(0, blk.shape[0], max(1, blk.shape[0] // 8)):
        cur = next((q for q in range(blk.shape[1]) if blk.idx(nn, q) in pins and pins[blk.idx(nn, q)] > 0.5), None)
        if cur is None:
            continue
        for newq in (cur + 1, cur - 1):
            if not (0 <= newq < blk.shape[1]) or blk.idx(nn, newq) not in pins:
                continue
            pins2 = dict(pins)
            for q in range(blk.shape[1]):
                c = blk.idx(nn, q)
                if c in pins2:
                    pins2[c] = 1.0 if q == newq else 0.0
            o2, _, _, ok2 = p._run_lp_with_duals(p.A, p.B, p.c, o, col_overrides={c: (v, v) for c, v in pins2.items()})
            if not ok2:
                infeas += 1
                continue
            z1v = np.array([pins2[c] for c in cols])
            pred = alpha + float(beta @ z1v)
            tested += 1
            bad = pred > o2 + 1e-6 * max(1.0, abs(o2))
            viol += bad
            print(f"    premium row {nn}: bracket {cur}->{newq}: true {-o2 / g[-1]:,.2f}  cut says "
                  f"{-pred / g[-1]:,.2f}  {'VIOLATION' if bad else 'valid'}")
    print(f"  cut check: {viol} violations in {tested} feasible flips ({infeas} flips infeasible)")
    rec.update(cut_violations=int(viol), cut_tested=int(tested), flips_infeasible=int(infeas))

if OUT:
    json.dump(rec, open(OUT, "w"), indent=1)
