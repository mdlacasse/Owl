"""Two-stage hybrid across the wealth ladder: SC loop, then the all-four MILP with only IRMAA-coupled
SS binaries free (IRMAA/LTCG/NIIT binaries all free).

Runs on the MILP engine, unmodified (PYTHONPATH=/Users/mdlacasse/Owl/src); behavior is injected by an
instance-level _buildConstraints patch that pins the SS binaries outside the neighborhood.

Rungs, verbatim from pubs/Cost_of_Committing/images/ladders.py CONFIGS and its build(): readConfig
of the base case, setAccountBalances(taxable, tdef, roth, hsa=0, units="k"), setSocialSecurity([pia],
[70]); maxBequest with netSpending = the rung's floor (ladders.log). Dana and Devon are the shipped
cases (PIA 2000 / 4000 at 70) with the manuscript floors 58k / 166k.

Arms:
  loop       SC loop, loop mode
  h:R        hybrid with neighborhood R (today's $): SS binaries of income year n free when the loop's
             MAGI_n lies within R of an IRMAA threshold for premium year n+2
  d1         hybrid, one-step-down SS box: each SS year may take the loop's regime or the next cheaper
             one. Regimes A (z0=0,z1=0) < B (z0=1,z1=0, 85% ramp) < C (z1=1, capped).
             Loop C: pin z0=1, free z1. Loop B: pin z1=0, free z0. Loop A: pin both.
  full       all-four MILP, nothing pinned
Every MILP arm is audited (attribute_dana.audit, with a $1 IRMAA threshold tolerance applied by
re-running mediCosts on MAGI - $1). Checkpoints to OUT after every arm and resumes.

Env: RUNGS (comma list), YEARS (comma list), ARMS (comma list, e.g. loop,h:13000,h:30000,full),
     MAXTIME (seconds per SC iteration, default 1800).
Usage: PYTHONPATH=/Users/mdlacasse/Owl/src uv run python hybrid_ladder.py OUT.json
"""
import contextlib
import io
import json
import os
import pathlib
import sys
import time
import types

import numpy as np
import owlplanner as owl
from owlplanner import tax_federal as tx

assert "/Users/mdlacasse/Owl/src" in owl.__file__, owl.__file__
HERE = pathlib.Path(__file__).resolve().parent
EX = pathlib.Path("/Users/mdlacasse/Owl/examples")
OUT = pathlib.Path(sys.argv[1])
ALL4 = {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize", "withNIIT": "optimize"}
RUNG_CFG = {
    "W0.5": {"base": "dana", "bal": (75, 469, 50), "pia": 1400, "floor": 34},
    "dana": {"base": "dana", "bal": None, "pia": None, "floor": 58},
    "W2": {"base": "dana", "bal": (300, 1874, 200), "pia": 3000, "floor": 99},
    "devon": {"base": "devon", "bal": None, "pia": None, "floor": 166},
    "W8": {"base": "devon", "bal": (1200, 7500, 800), "pia": 4152, "floor": 277},
}
RUNGS = os.environ.get("RUNGS", "W0.5,dana,W2,devon,W8").split(",")
YEARS = [int(y) for y in os.environ.get("YEARS", "1928,1932,1966,1973,1983,1999").split(",")]
ARMS = os.environ.get("ARMS", "loop,h:13000").split(",")
MAXTIME = float(os.environ.get("MAXTIME", "1800"))

_src = (HERE / "attribute_dana.py").read_text()
_ns = {"np": np, "tx": tx}
exec(_src[_src.index("def bracket_tax("):_src.index("def run(")], _ns)
audit_raw = _ns["audit"]


def build(rung, year, extra):
    c = RUNG_CFG[rung]
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p = owl.readConfig(str(EX / f"Case_{c['base']}.toml"), verbose=False)
        if c["bal"] is not None:
            p.setAccountBalances(taxable=[float(c["bal"][0])], taxDeferred=[float(c["bal"][1])],
                                 taxFree=[float(c["bal"][2])], hsa=[0.0], units="k")
            p.setSocialSecurity([c["pia"]], [70.0])
        p.setRates("historical", year)
    o = dict(p.solverOptions)
    o.update({"solver": "MOSEK", "gap": 1e-4, "maxTime": MAXTIME, "numThreads": 2, **extra})
    o.pop("bequest", None)
    o["netSpending"] = float(c["floor"])
    return p, o


def solve(p, o):
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p.solve("maxBequest", options=o)
    return time.time() - t0


def occupancy(p):
    """Regime counts at a solution: where in the box this rung lives."""
    Nn, g = p.N_n, p.gamma_n
    ss = np.sum(p.zetaBar_in, axis=0)
    status = np.full(Nn, p.N_i - 1)
    if p.N_i == 2 and p.n_d < Nn:
        status[p.n_d:] = 0
    lo, hi = tx.ssTaxabilityLo[status], tx.ssTaxabilityHi[status]
    cap = hi + ss - (hi - lo) / 1.7
    pi = p.MAGI_aca_n - 0.5 * ss
    ssr = ((pi > lo).astype(int) + (pi > hi) + (pi > cap))[ss > 0]
    irm = []
    for m in range(2, Nn):
        st = 0 if p.N_i == 1 or not (m < p.horizons[0] and m < p.horizons[1]) else 1
        irm.append(int(np.sum(p.MAGI_n[m - 2] > g[m] * np.array(tx.irmaaBrackets[st])[1:] + 1.0)))
    T15 = g[:Nn] * np.array([tx.capGainRates[s][0] for s in status])
    T20 = g[:Nn] * np.array([tx.capGainRates[s][1] for s in status])
    ltcg = (p.G_n > T15).astype(int) + (p.G_n > T20)
    niit_T = np.array([200000.0 if s == 0 else 250000.0 for s in status])
    return {"SS": np.bincount(ssr, minlength=4).tolist(), "IRMAA": np.bincount(irm, minlength=6).tolist(),
            "LTCG": np.bincount(ltcg, minlength=3).tolist(), "NIIT_years": int(np.sum(p.MAGI_n > niit_T))}


def audit(p):
    a = audit_raw(p)
    # $1 tolerance at IRMAA thresholds: the MILP parks MAGI on a threshold and cent rounding bumps it.
    g = p.gamma_n[:p.N_n]
    Mt = tx.mediCosts(p.yobs, p.horizons, p.MAGI_n - 1.0, p.prevMAGI, g, p.N_n,
                      include_part_d=getattr(p, "_include_medicare_part_d", True),
                      part_d_base_annual_per_person=getattr(p, "_medicare_part_d_base_annual_per_person", 0.0))
    v = (p.medicare_n - Mt) / g
    a["medicare_tol1"] = {"sum": float(np.sum(v)), "abs_sum": float(np.sum(np.abs(v))), "max_abs": float(np.max(np.abs(v)))}
    return {k: round(v["abs_sum"], 2) for k, v in a.items()}


def pins_for(loop, R):
    Nn = loop.N_n
    ss = np.sum(loop.zetaBar_in, axis=0)
    status = np.full(Nn, loop.N_i - 1)
    if loop.N_i == 2 and loop.n_d < Nn:
        status[loop.n_d:] = 0
    lo, hi = tx.ssTaxabilityLo[status], tx.ssTaxabilityHi[status]
    pi = loop.MAGI_aca_n - 0.5 * ss
    psi = tx.compute_social_security_taxability(loop.N_i, loop.MAGI_aca_n, ss, n_d=loop.n_d)
    z1 = (psi >= 0.85 - 1e-9).astype(float)
    z0 = (pi >= lo + np.minimum(hi - lo, ss)).astype(float)
    dist = np.full(Nn, np.inf)
    for n in range(Nn - 2):
        m = n + 2
        st = 0 if loop.N_i == 1 or not (m < loop.horizons[0] and m < loop.horizons[1]) else 1
        thr = loop.gamma_n[m] * np.array(tx.irmaaBrackets[st])[1:]
        dist[n] = np.min(np.abs(loop.MAGI_n[n] - thr)) / loop.gamma_n[n]
    active = ss > 0
    free = active & (dist <= R)
    pinned = np.flatnonzero(active & ~free)
    return pinned, z0, z1, int(free.sum()), int(active.sum())


def d1_pins(loop):
    """One-step-down SS box: returns (pin specs [(n, binary k, value)], years with a free binary, active)."""
    _, z0, z1, _, _ = pins_for(loop, -1.0)  # R < 0: every active year pinned; reuse the regime binaries
    ss = np.sum(loop.zetaBar_in, axis=0)
    specs, nfree = [], 0
    for n in np.flatnonzero(ss > 0):
        if z1[n] == 1:            # C: capped -> may drop to B
            specs.append((n, 0, 1.0))
            nfree += 1
        elif z0[n] == 1:          # B: 85% ramp -> may drop to A
            specs.append((n, 1, 0.0))
            nfree += 1
        else:                     # A: nothing cheaper is expressible by the binaries
            specs += [(n, 0, 0.0), (n, 1, 0.0)]
    return specs, nfree, int(np.sum(ss > 0))


res = json.loads(OUT.read_text()) if OUT.exists() else {}


def save():
    OUT.write_text(json.dumps(res, indent=1))


print(f"rungs {RUNGS} years {YEARS} arms {ARMS} maxTime {MAXTIME}", flush=True)
for rung in RUNGS:
    for year in YEARS:
        key = f"{rung}/{year}"
        rec = res.setdefault(key, {})
        loop, o = build(rung, year, {})
        t = solve(loop, o)
        if "loop" not in rec:
            rec["loop"] = {"status": loop.caseStatus, "conv": loop.convergenceType, "seconds": round(t, 2),
                           "bequest": float(loop.bequest) if loop.caseStatus == "solved" else None,
                           "occupancy": occupancy(loop) if loop.caseStatus == "solved" else None}
            save()
            print(f"{key} loop {loop.caseStatus} {loop.convergenceType} bequest {rec['loop']['bequest']} "
                  f"occupancy {rec['loop']['occupancy']}", flush=True)
        if loop.caseStatus != "solved":
            continue
        for arm in ARMS:
            if arm == "loop" or arm in rec:
                continue
            p, o = build(rung, year, ALL4)
            extra = {}
            if arm.startswith("h:") or arm == "d1":
                if arm == "d1":
                    specs, nfree, nact = d1_pins(loop)
                else:
                    pinned, z0, z1, nfree, nact = pins_for(loop, float(arm[2:]))
                    specs = [(n, 0, z0[n]) for n in pinned] + [(n, 1, z1[n]) for n in pinned]
                original = type(p)._buildConstraints

                def patched(self, objective, options, specs=specs, original=original):
                    original(self, objective, options)
                    for n, k, v in specs:
                        self.B.setRange(self.vm["zs"].idx(n, k), v, v)

                p._buildConstraints = types.MethodType(patched, p)
                extra = {"ss_free": nfree, "ss_active": nact, "ss_pins": len(specs)}
            t = solve(p, o)
            r = {"status": p.caseStatus, "conv": p.convergenceType, "seconds": round(t, 1),
                 "gap": float(getattr(p, "solverGap", -1)), **extra}
            if p.caseStatus == "solved":
                r["bequest"] = float(p.bequest)
                r["gain_over_loop"] = float(p.bequest - loop.bequest)
                r["audit"] = audit(p)
                r["occupancy"] = occupancy(p)
            rec[arm] = r
            save()
            aud = {k: v for k, v in r.get("audit", {}).items() if v > 1 and k != "medicare"}
            print(f"{key} {arm} {r['status']} {r['conv']} bequest {r.get('bequest')} gain {r.get('gain_over_loop')} "
                  f"gap {r['gap']:.1e} {r['seconds']}s {extra} audit>1 {aud}", flush=True)
print("done", flush=True)
