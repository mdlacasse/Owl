"""Do the exact MILP's regimes lie inside the box of regimes the SC recursion visited?

Families have ordered regimes. For every iterate of the loop (lp-only branch, plan.scTrace), each
year's regime is recorded; per year the recursion "illuminates" the interval [min, max] of regimes
seen. The product of these intervals is the ordered bounding box of the recursion. A full MILP
restricted to that box can only reach the exact optimum if every MILP regime lies inside it.

Regimes (same definitions as regime_flips.py, which produced the MILP side):
  SS    : income year n, count of provisional income above (lo, hi, cap point) -> 0..3
  IRMAA : premium year m, count of MAGI[m-2] above the IRMAA thresholds (+$1)  -> 0..
  LTCG  : income year n, count of ordinary taxable income above (T15, T20)     -> 0..2

Usage (lp-only engine): uv run python illuminated_box.py YEAR
Reads results/regime_flips_YEAR.json for the MILP's flipped years (all other years keep the loop's
final regime, which the box contains by construction only if the accepted iterate is in the trace).
"""
import contextlib
import io
import json
import pathlib
import sys

import numpy as np
import owlplanner as owl
from owlplanner import tax_federal as tx

assert "Owl.dev" in owl.__file__, owl.__file__
YEAR = int(sys.argv[1])
HERE = pathlib.Path(__file__).resolve().parent

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    p = owl.readConfig("/Users/mdlacasse/Owl.dev/examples/Case_dana.toml", verbose=False)
    o = {k: v for k, v in dict(p.solverOptions).items()
         if k not in ("withMedicare", "withACA", "withLTCG", "withNIIT", "withSSAges", "withDecomposition",
                      "withSSTaxability", "gap")}
    o.update({"solver": "MOSEK"})
    o.pop("bequest", None)
    o["netSpending"] = 58.0
    p.setRates("historical", YEAR)
    p.solve("maxBequest", options=o)
tr = p.scTrace
Nn, g = p.N_n, p.gamma_n
ss = np.sum(p.zetaBar_in, axis=0)
status = np.full(Nn, p.N_i - 1)
if p.N_i == 2 and p.n_d < Nn:
    status[p.n_d:] = 0
lo, hi = tx.ssTaxabilityLo[status], tx.ssTaxabilityHi[status]
cap = hi + ss - (hi - lo) / 1.7
T15 = g[:Nn] * np.array([tx.capGainRates[s][0] for s in status])
T20 = g[:Nn] * np.array([tx.capGainRates[s][1] for s in status])
n_it = len(tr["solutions"])


def irmaa_regime(magi, m):
    st = 0 if p.N_i == 1 or not (m < p.horizons[0] and m < p.horizons[1]) else 1
    thr = g[m] * np.array(tx.irmaaBrackets[st])[1:]
    return int(np.sum(magi > thr + 1.0))


reg = {"SS": np.zeros((n_it, Nn), int), "IRMAA": np.zeros((n_it, Nn), int), "LTCG": np.zeros((n_it, Nn), int)}
for i in range(n_it):
    pi = tr["MAGI_aca_n"][i] - 0.5 * ss
    reg["SS"][i] = np.where(ss > 0, (pi > lo).astype(int) + (pi > hi) + (pi > cap), -1)
    G = tr["G_n_next"][i]
    reg["LTCG"][i] = (G > T15).astype(int) + (G > T20)
    for m in range(Nn):
        reg["IRMAA"][i, m] = irmaa_regime(tr["MAGI_n"][i][m - 2], m) if m >= 2 else -1

print(f"{YEAR}: loop {p.caseStatus} {p.convergenceType} bequest {p.bequest:,.2f}; iterates {n_it}, accepted {tr['accepted']}")
flips = json.load(open(HERE / "results" / f"regime_flips_{YEAR}.json"))
assert abs(flips["loop_bequest"] - p.bequest) < 0.01, (flips["loop_bequest"], p.bequest)
years = [int(y) for y in p.year_n]
for fam in ("SS", "IRMAA", "LTCG"):
    R = reg[fam]
    valid = R[0] >= 0
    lo_b, hi_b = R.min(axis=0), R.max(axis=0)
    width = hi_b - lo_b
    # Iterates 0-1 carry zero-initialized premiums/room; report the box with and without them.
    R2 = R[2:] if n_it > 2 else R
    lo2, hi2 = R2.min(axis=0), R2.max(axis=0)
    print(f"  {fam:5}: years with >1 regime visited: {int(np.sum(valid & (width > 0)))} of {int(valid.sum())} "
          f"(excluding iterates 0-1: {int(np.sum(valid & (hi2 > lo2)))})")
    for row in flips["families"].get(fam, []):
        n = years.index(row["year"])
        inside = lo_b[n] <= row["milp_regime"] <= hi_b[n]
        inside2 = lo2[n] <= row["milp_regime"] <= hi2[n]
        seq = "".join(str(v) for v in R[:, n])
        print(f"      MILP flip {row['year']}: {row['loop_regime']} -> {row['milp_regime']}; box [{lo_b[n]},{hi_b[n]}] "
              f"{'INSIDE' if inside else 'OUTSIDE'} (w/o iter 0-1 [{lo2[n]},{hi2[n]}] {'inside' if inside2 else 'outside'}); "
              f"regime by iterate {seq}")
