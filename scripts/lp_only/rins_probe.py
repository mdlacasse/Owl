"""Two-stage hybrid probe: SC loop, then the all-four MILP with a RINS-style SS neighborhood.

Runs on the MILP engine without modifying it (PYTHONPATH=/Users/mdlacasse/Owl/src); behavior is
injected by instance-level method patches only.

Stage 1: loop-mode solve (fixed point). Each year's SS regime gives implied binaries
  z1 = 1  <=> taxable SS capped at 0.85*zetaBar (provisional income at or past the cap point)
  z0 = 1  <=> 50% tier saturated (provisional income >= lo + min(Delta, zetaBar))
Stage 2a: LP relaxation of the all-four MILP, built with the loop's SC parameters (MAGI_n, Psi_n,
  I_n, gain fractions). RINS rule: an SS year is pinned when both relaxed binaries agree with the
  loop's implied values; otherwise it is left free.
Stage 2b: the all-four MILP through the normal SC loop, with only the pinned SS binaries fixed;
  IRMAA/LTCG/NIIT binaries all free. Compare with the full all-four MILP.

Usage: PYTHONPATH=/Users/mdlacasse/Owl/src uv run python rins_probe.py YEAR [OUT.json] [--no-stage2]
"""
import contextlib
import io
import json
import pathlib
import sys
import time
import types

import numpy as np
import owlplanner as owl
from owlplanner import tax_federal as tx

assert "/Users/mdlacasse/Owl/src" in owl.__file__, owl.__file__
YEAR = int(sys.argv[1])
OUT = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
STAGE2 = "--no-stage2" not in sys.argv
ALL4 = {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize", "withNIIT": "optimize"}
TOL = float(__import__("os").environ.get("RINS_TOL", "1e-6"))
# NEIGHBORHOOD="rins" (default) or "irmaa:R": free the SS binaries of income year n when the loop's
# MAGI_n lies within R (today's $) of an IRMAA threshold for premium year n+2; pin all other SS years.
NEIGHBORHOOD = __import__("os").environ.get("NEIGHBORHOOD", "rins")


def fresh(extra):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p = owl.readConfig("/Users/mdlacasse/Owl/examples/Case_dana.toml", verbose=False)
        o = dict(p.solverOptions)
        o.update({"solver": "MOSEK", "gap": 1e-4, "maxTime": 1800, "numThreads": 2, **extra})
        o.pop("bequest", None)
        o["netSpending"] = 58.0
        p.setRates("historical", YEAR)
    return p, o


def quiet_solve(p, o):
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p.solve("maxBequest", options=o)
    return time.time() - t0


# ---- Stage 1: loop ---------------------------------------------------------------------------
loop, o_loop = fresh({})
t_loop = quiet_solve(loop, o_loop)
Nn = loop.N_n
ss = np.sum(loop.zetaBar_in, axis=0)
status = np.full(Nn, loop.N_i - 1)
if loop.N_i == 2 and loop.n_d < Nn:
    status[loop.n_d:] = 0
lo, hi = tx.ssTaxabilityLo[status], tx.ssTaxabilityHi[status]
pi = loop.MAGI_aca_n - 0.5 * ss
psi_true = tx.compute_social_security_taxability(loop.N_i, loop.MAGI_aca_n, ss, n_d=loop.n_d)
z1_loop = (psi_true >= 0.85 - 1e-9).astype(float)
z0_loop = (pi >= lo + np.minimum(hi - lo, ss)).astype(float)
active = ss > 0
print(f"{YEAR} stage 1 loop: {loop.caseStatus} {loop.convergenceType} bequest {loop.bequest:,.2f} ({t_loop:.1f}s); "
      f"SS years {int(active.sum())}: capped {int((z1_loop * active).sum())}, 50%-tier saturated {int((z0_loop * active).sum())}")

# ---- Stage 2a: LP relaxation of the all-four model at the loop's parameters -------------------
relax = {}


def relaxation_only(self, objective, options, solverMethod):
    self.MAGI_n = loop.MAGI_n.copy()
    self.MAGI_aca_n = loop.MAGI_aca_n.copy()
    self.Psi_n = loop.Psi_n.copy()
    self.I_n = loop.I_n.copy()
    self.gain_fraction_in = None if loop.gain_fraction_in is None else loop.gain_fraction_in.copy()
    self._decomp_use_mosek = True
    self._highs_warm_start = None
    t0 = time.time()
    self._buildConstraints(objective, options)
    obj, x, ok, msg, _ = self._run_mip(self.A, self.B, self.c, options, lp_relax=True, update_warm=False)
    relax.update(ok=ok, msg=msg, x=x, seconds=time.time() - t0,
                 zs=self.vm["zs"].extract(x) if ok else None, nbins=int(self.nbins))
    self.caseStatus = "relaxation-probe"


pr, o_all = fresh(ALL4)
pr._scSolve = types.MethodType(relaxation_only, pr)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    pr.solve("maxBequest", options=o_all)
assert relax.get("ok"), relax.get("msg")
zs = relax["zs"]  # shape (N_n, 2): column 0 = z0, column 1 = z1
agree0 = np.abs(zs[:, 0] - z0_loop) <= TOL
agree1 = np.abs(zs[:, 1] - z1_loop) <= TOL
pin = active & agree0 & agree1
if NEIGHBORHOOD.startswith("irmaa:"):
    R = float(NEIGHBORHOOD.split(":")[1])
    dist = np.full(Nn, np.inf)
    for n in range(Nn - 2):
        m = n + 2
        st = 0 if loop.N_i == 1 or not (m < loop.horizons[0] and m < loop.horizons[1]) else 1
        thr = loop.gamma_n[m] * np.array(tx.irmaaBrackets[st])[1:]
        dist[n] = np.min(np.abs(loop.MAGI_n[n] - thr)) / loop.gamma_n[n]
    pin = active & ~(dist <= R)
free = active & ~pin
frac = active & ((np.minimum(zs[:, 0], 1 - zs[:, 0]) > TOL) | (np.minimum(zs[:, 1], 1 - zs[:, 1]) > TOL))
years = loop.year_n
print(f"  stage 2a relaxation ({relax['seconds']:.1f}s, {relax['nbins']} binaries): SS years fractional {int(frac.sum())}, "
      f"z0 agrees {int((active & agree0).sum())}, z1 agrees {int((active & agree1).sum())}, "
      f"pinned {int(pin.sum())}, free {int(free.sum())}")
print(f"  free SS years: {[int(y) for y in years[free]]}")
for n in np.flatnonzero(free):
    print(f"      {years[n]}: loop z0={int(z0_loop[n])} z1={int(z1_loop[n])}  relaxed z0={zs[n, 0]:.3f} z1={zs[n, 1]:.3f}")

report = {"year": YEAR, "neighborhood": NEIGHBORHOOD, "loop_bequest": loop.bequest, "loop_conv": loop.convergenceType,
          "relaxation_seconds": relax["seconds"], "n_ss_years": int(active.sum()),
          "n_fractional": int(frac.sum()), "pinned_years": [int(y) for y in years[pin]],
          "free_years": [int(y) for y in years[free]]}

# ---- Stage 2b: all-four MILP with the pinned SS binaries fixed -------------------------------
if STAGE2:
    ph, o_h = fresh(ALL4)
    original_build = type(ph)._buildConstraints
    pinned = np.flatnonzero(pin)

    def build_with_pins(self, objective, options):
        original_build(self, objective, options)
        for n in pinned:
            self.B.setRange(self.vm["zs"].idx(n, 0), z0_loop[n], z0_loop[n])
            self.B.setRange(self.vm["zs"].idx(n, 1), z1_loop[n], z1_loop[n])

    ph._buildConstraints = types.MethodType(build_with_pins, ph)
    t_h = quiet_solve(ph, o_h)
    print(f"  stage 2b hybrid MILP: {ph.caseStatus} {ph.convergenceType} bequest {ph.bequest:,.2f} gap {ph.solverGap:.1e} "
          f"({t_h:.1f}s)  gain over loop {ph.bequest - loop.bequest:+,.2f}")
    report.update(hybrid_status=ph.caseStatus, hybrid_conv=ph.convergenceType, hybrid_bequest=ph.bequest,
                  hybrid_gap=ph.solverGap, hybrid_seconds=t_h)
    # Audit the hybrid answer with the same recomputation as attribute_dana.py.
    src = (pathlib.Path(__file__).resolve().parent / "attribute_dana.py").read_text()
    ns = {"np": np, "tx": tx}
    exec(src[src.index("def bracket_tax("):src.index("def run(")], ns)
    aud = ns["audit"](ph)
    report["hybrid_audit"] = aud
    print("  audit (reported minus recomputed, today's $, abs_sum > 1):",
          {k: round(v["abs_sum"]) for k, v in aud.items() if v["abs_sum"] > 1})

if OUT:
    json.dump(report, open(OUT, "w"), indent=1)
