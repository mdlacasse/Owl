"""Where does the exact MILP change regimes relative to the SC-loop fixed point?

For one Case_dana window (maxBequest, netSpending 58k, MOSEK, gap 1e-4), solve the loop and the
all-four MILP on the MILP engine (PYTHONPATH=/Users/mdlacasse/Owl/src). For every year and family,
classify the regime each plan sits in and report the years that flip, with the loop's distance to
the nearest regime boundary (today's $). If flips happen only where the loop was already near a
boundary, a hybrid MILP with binaries restricted to a small neighborhood of the fixed point can
recover the gap; if flips happen far from boundaries, the neighborhood must be defined otherwise.

Usage: PYTHONPATH=/Users/mdlacasse/Owl/src uv run python regime_flips.py YEAR [OUT.json]
"""
import contextlib
import io
import json
import sys
import time

import numpy as np
import owlplanner as owl
from owlplanner import tax_federal as tx

assert "/Users/mdlacasse/Owl/src" in owl.__file__, owl.__file__
YEAR = int(sys.argv[1])
ALL4 = {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize", "withNIIT": "optimize"}


def solve(extra):
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p = owl.readConfig("/Users/mdlacasse/Owl/examples/Case_dana.toml", verbose=False)
        o = dict(p.solverOptions)
        o.update({"solver": __import__("os").environ.get("SOLVER", "MOSEK"), "gap": 1e-4, "maxTime": 1800,
                  "numThreads": 2, **extra})
        o.pop("bequest", None)
        o["netSpending"] = 58.0
        p.setRates("historical", YEAR)
        p.solve("maxBequest", options=o)
    return p, time.time() - t0


def regimes(p):
    Nn = p.N_n
    g = p.gamma_n[:Nn]
    ss = np.sum(p.zetaBar_in, axis=0)
    status = np.full(Nn, p.N_i - 1)
    if p.N_i == 2 and p.n_d < Nn:
        status[p.n_d:] = 0
    out = {}
    # SS: provisional income against lo, hi and the 85% cap point.
    pi = p.MAGI_aca_n - 0.5 * ss
    lo, hi = tx.ssTaxabilityLo[status], tx.ssTaxabilityHi[status]
    cap = hi + ss - (hi - lo) / 1.7
    edges = np.vstack([lo, hi, cap])
    out["SS"] = (np.where(ss > 0, np.sum(pi[None, :] > edges, axis=0), -1), pi, edges)
    # IRMAA: bracket of MAGI two years earlier ($1 tolerance at thresholds).
    magi2 = np.array([p.MAGI_n[n - 2] if n >= 2 else p.prevMAGI[n] for n in range(Nn)])
    thr = np.array([g[n] * np.array(tx.irmaaBrackets[0 if p.N_i == 1 or not (n < p.horizons[0] and n < p.horizons[1]) else 1])[1:]
                    for n in range(Nn)]).T
    out["IRMAA"] = (np.sum(magi2[None, :] > thr + 1.0, axis=0), magi2, thr)
    # LTCG: ordinary taxable income against T15, T20.
    T15 = g * np.array([tx.capGainRates[s][0] for s in status])
    T20 = g * np.array([tx.capGainRates[s][1] for s in status])
    e = np.vstack([T15, T20])
    out["LTCG"] = (np.sum(p.G_n[None, :] > e, axis=0), p.G_n, e)
    return out


pl, tl = solve({})
pm, tm = solve(ALL4)
print(f"{YEAR}: loop {pl.caseStatus} {pl.convergenceType} bequest {pl.bequest:,.2f} ({tl:.1f}s) | "
      f"ALL4 {pm.caseStatus} {pm.convergenceType} bequest {pm.bequest:,.2f} gap {pm.solverGap:.1e} ({tm:.1f}s)")
rl, rm = regimes(pl), regimes(pm)
g = pl.gamma_n[:pl.N_n]
report = {"year": YEAR, "loop_bequest": pl.bequest, "milp_bequest": pm.bequest, "milp_seconds": tm, "families": {}}
for fam in ("SS", "IRMAA", "LTCG"):
    kl, xl, el = rl[fam]
    km, xm, _ = rm[fam]
    flips = np.flatnonzero(kl != km)
    active = np.flatnonzero(kl >= 0)
    dist = np.min(np.abs(xl[None, :] - el), axis=0) / g  # loop's distance to nearest boundary, today's $
    rows = [{"year": int(pl.year_n[n]), "loop_regime": int(kl[n]), "milp_regime": int(km[n]),
             "loop_dist_to_boundary": round(float(dist[n])), "income_change": round(float((xm[n] - xl[n]) / g[n]))}
            for n in flips]
    report["families"][fam] = rows
    print(f"  {fam:5}: {len(flips)} flipped of {len(active)} active years;"
          f" loop distance to boundary in flipped years (today's $): {sorted(r['loop_dist_to_boundary'] for r in rows)}")
    for r in rows:
        print(f"      {r['year']}: regime {r['loop_regime']} -> {r['milp_regime']}, loop {r['loop_dist_to_boundary']:,} from boundary, income change {r['income_change']:+,}")
    nf = np.setdiff1d(active, flips)
    if len(nf):
        print(f"      unflipped years: distance to boundary median {np.median(dist[nf]):,.0f}, min {np.min(dist[nf]):,.0f}")
if len(sys.argv) > 2:
    json.dump(report, open(sys.argv[2], "w"), indent=1)
