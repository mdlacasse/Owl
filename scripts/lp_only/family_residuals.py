"""Which discontinuity keeps the SC loop from a fixed point?

For every historical window of a configuration, solve in loop mode (lp-only branch), then read the
iteration trace kept on the plan. At the accepted iterate a, each family's fixed-point residual is
the difference between the parameter the LP was built with and the value implied by that LP's own
solution. At a true fixed point every residual is zero.

Residuals are reported in today's dollars summed over the horizon:
  SS    : taxable Social Security income, (Psi_implied - Psi_lp) * zetaBar   (undamped implied Psi)
  IRMAA : Medicare premiums,              M_next - M_lp
  NIIT  : NIIT dollars,                   J_next - J_lp
  ACA   : ACA net premiums,               ACA_next - ACA_lp
  LTCG  : LTCG tax on Q stacked on G_next minus on G_lp (same Q)

Also recorded: which families still move over the last K iterates (the cycle or approach), and the
objective history. Usage: uv run python family_residuals.py CONFIG OUT.json [workers]
CONFIG in {dana, p12}.
"""
import contextlib
import io
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import owlplanner as owl
from owlplanner import tax_federal as tx

EXAMPLES = pathlib.Path("/Users/mdlacasse/Owl.dev/examples")
CONFIG, OUT = sys.argv[1], sys.argv[2]
WORKERS = int(sys.argv[3]) if len(sys.argv) > 3 else 5
YEARS = list(range(1928, 2000))


def build(year):
    with contextlib.redirect_stdout(io.StringIO()):
        p = owl.readConfig(str(EXAMPLES / "Case_dana.toml"), verbose=False)
        if CONFIG == "p12":
            # pia_ladder.py LADDERS[0] + sweep(): balances (150, 937, 100) $k, hsa 0, PIA 4152 at 70.
            p.setAccountBalances(taxable=[150.0], taxDeferred=[937.0], taxFree=[100.0], hsa=[0.0], units="k")
            p.setSocialSecurity([4152], [70.0])
        p.setRates("historical", year)
    o = {k: v for k, v in dict(p.solverOptions).items()}
    o.update({"solver": "MOSEK", "numThreads": 2})
    o.pop("bequest", None)
    o["netSpending"] = 58.0
    return p, o


def ltcg_tax(Q, G, T15, T20):
    """Tax on gains Q stacked on ordinary taxable income G (0/15/20%)."""
    lo, hi = G, G + np.maximum(Q, 0)
    in15 = np.maximum(0, np.minimum(hi, T20) - np.maximum(lo, T15))
    in20 = np.maximum(0, hi - np.maximum(lo, T20))
    return 0.15 * in15 + 0.20 * in20


def analyze(p, tr):
    a = tr["accepted"]
    g = p.gamma_n[:-1]
    ss_n = np.sum(p.zetaBar_in, axis=0)
    status_n = np.full(p.N_n, p.N_i - 1)
    if p.N_i == 2 and p.n_d < p.N_n:
        status_n[p.n_d:] = 0
    T15 = p.gamma_n[:-1] * tx.capGainRates[status_n, 0]
    T20 = p.gamma_n[:-1] * tx.capGainRates[status_n, 1]

    def implied_psi(i):
        return tx.compute_social_security_taxability(p.N_i, tr["MAGI_aca_n"][i], ss_n, n_d=p.n_d)

    def residuals(i):
        return {
            "SS": (implied_psi(i) - tr["Psi_n_lp"][i]) * ss_n / g,
            "IRMAA": (tr["M_n_next"][i] - tr["M_n_lp"][i]) / g,
            "NIIT": (tr["J_n_next"][i] - tr["J_n_lp"][i]) / g,
            "ACA": (tr["ACA_n_next"][i] - tr["ACA_n_lp"][i]) / g,
            "LTCG": (ltcg_tax(tr["Q_n"][i], tr["G_n_next"][i], T15, T20)
                     - ltcg_tax(tr["Q_n"][i], tr["G_n_lp"][i], T15, T20)) / g,
        }

    res = residuals(a)
    out = {
        "accepted": a,
        "n_iter": len(tr["solutions"]),
        "ltcg_passes": tr.get("ltcg_passes", 0),
        "objective_history": [float(v) for v in tr["scaledObjectives"]],
        "residual_abs_sum": {k: float(np.sum(np.abs(v))) for k, v in res.items()},
        "residual_signed_sum": {k: float(np.sum(v)) for k, v in res.items()},
        "residual_years": {k: [int(n) for n in np.flatnonzero(np.abs(v) > 10.0)] for k, v in res.items()},
    }
    # Movement of each LP parameter over the last K iterates (today's $, max over pairs and years).
    # Iterations 0 and 1 carry the zero initialization of M_n and G_n, so they are excluded.
    n_it = len(tr["solutions"])
    idx = list(range(max(2, n_it - 4), n_it))
    K = len(idx)
    move = {}
    for fam, key, scale in (("SS", "Psi_n_lp", ss_n), ("IRMAA", "M_n_lp", 1.0), ("NIIT", "J_n_lp", 1.0),
                            ("ACA", "ACA_n_lp", 1.0), ("LTCG-room", "G_n_lp", 1.0)):
        arr = np.array([np.asarray(tr[key][i]) * scale / g for i in idx])
        move[fam] = float(np.max(np.abs(arr[:, None, :] - arr[None, :, :]))) if K > 1 else None
    out["last_k_movement"] = move
    # Proximity of provisional income to the SS thresholds, at the accepted iterate.
    pi = tr["MAGI_aca_n"][a] - 0.5 * ss_n
    lo = tx.ssTaxabilityLo[status_n]
    hi = tx.ssTaxabilityHi[status_n]
    cap = hi + ss_n - (hi - lo) / 1.7  # PI where 0.5*dP + 0.85*(PI-hi) reaches 0.85*ss (when ss >= dP)
    out["ss_regime_counts"] = {
        "below_lo": int(np.sum((ss_n > 0) & (pi < lo))),
        "ramp50": int(np.sum((ss_n > 0) & (pi >= lo) & (pi < hi))),
        "ramp85": int(np.sum((ss_n > 0) & (pi >= hi) & (pi < cap))),
        "capped": int(np.sum((ss_n > 0) & (pi >= cap))),
    }
    return out


def run(year):
    p, o = build(year)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p.solve("maxBequest", o)
    rec = {"status": p.caseStatus, "conv": p.convergenceType}
    if p.caseStatus == "solved":
        rec["bequest"] = float(p.bequest)
        rec.update(analyze(p, p.scTrace))
    return year, rec


results = {}
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for fut in as_completed([ex.submit(run, y) for y in YEARS]):
        y, rec = fut.result()
        results[str(y)] = rec
json.dump(results, open(OUT, "w"), indent=1)
print(f"{CONFIG}: {len(results)} windows written to {OUT}")
