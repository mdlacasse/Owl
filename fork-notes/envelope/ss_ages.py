"""SS claiming ages as an outer enumeration around the EM, vs Owl's withSSAges="optimize" MILP.

Claiming ages only change the exogenous SS series, so for each candidate pair of ages the EM
is re-solved (cost table + DP). Search: every whole-year age 62..70 per person (81 pairs for a
couple), then a monthly coordinate refinement around the best pair.
Both models use the case's original inputs (the EM keeps returns and inflation; it leaves out
tax inside the taxable account).
"""
import sys, os, json, time, itertools
from datetime import date
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa
from owlplanner import utils as u  # noqa
from owlplanner import socialsecurity as socsec  # noqa
import em  # noqa


def ss_series(p, ages):
    z, _ = socsec.compute_social_security_benefits(
        p.ssecAmounts, np.array(ages, dtype=float), p.yobs, p.mobs, p.tobs, p.horizons, p.N_i, p.N_n,
        trim_pct=getattr(p, "ssecTrimPct", 0) or 0, trim_year=getattr(p, "ssecTrimYear", None),
        thisyear=date.today().year, survivor_claim_age=getattr(p, "ssecSurvivorClaimAge", "immediate"))
    return (z * p.gamma_n[:-1]).sum(axis=0)


def em_value(p, inp, base_ss, ages, kw):
    ss = ss_series(p, ages)
    inp["ss"] = ss
    inp["cash"] = inp["cash0"] + ss
    return em.solve_dp(inp, r=None, **kw)["value"]


def run(path):
    p = compare.load(path)
    opts = dict(p.solverOptions)
    opts["maxTime"] = 120
    p.solve(p.objective, opts)
    base_full = p.basis if p.objective == "maxSpending" else p.bequest
    inp = em.inputs(p, opts)
    kw = (dict(bequest=u.get_monetary_option(opts, "bequest", 1) if "bequest" in opts else 1.0)
          if p.objective == "maxSpending" else dict(netSpending=u.get_monetary_option(opts, "netSpending", 1)))
    inp["cash0"] = inp["cash"] - inp["ss"]
    ages0 = list(p.ssecAges)
    t = time.time()
    base_em = em_value(p, inp, None, ages0, kw)
    # ages already past cannot be changed: keep anyone whose claiming age is behind them
    now_age = [date.today().year - y for y in p.yobs]
    grids = [[a0] if a0 <= now_age[i] else list(range(max(62, int(np.ceil(now_age[i]))), 71))
             for i, a0 in enumerate(ages0)]
    best = (-np.inf, None)
    n_eval = 0
    for ages in itertools.product(*grids):
        v = em_value(p, inp, None, ages, kw)
        n_eval += 1
        if v > best[0]:
            best = (v, list(ages))
    # monthly refinement, one person at a time
    improved = True
    while improved:
        improved = False
        for i in range(p.N_i):
            if len(grids[i]) == 1:
                continue
            for dm in range(-11, 12):
                a = best[1][i] + dm / 12
                if a < max(62, now_age[i]) or a > 70:
                    continue
                cand = list(best[1])
                cand[i] = round(a, 4)
                v = em_value(p, inp, None, cand, kw)
                n_eval += 1
                if v > best[0] + 1e-6:
                    best, improved = (v, cand), True
    t_em = time.time() - t
    # Owl's MILP over claiming ages
    q = compare.load(path)
    o2 = dict(q.solverOptions)
    o2["maxTime"] = 120
    o2["withSSAges"] = "optimize"
    t = time.time()
    q.solve(q.objective, o2)
    t_owl = time.time() - t
    owl = (q.basis if q.objective == "maxSpending" else q.bequest) if q.caseStatus == "solved" else None
    # Owl's full model at the EM's ages
    r = compare.load(path)
    r.setSocialSecurity(list(r.ssecAmounts), best[1]) if hasattr(r, "setSocialSecurity") else None
    o3 = dict(r.solverOptions)
    o3["maxTime"] = 120
    r.solve(r.objective, o3)
    full_at_em = (r.basis if r.objective == "maxSpending" else r.bequest) if r.caseStatus == "solved" else None
    return {"case": os.path.basename(path)[5:-5], "ages0": ages0, "full_at_ages0": round(base_full),
            "em_at_ages0": round(base_em), "em_best_ages": best[1], "em_best": round(best[0]),
            "em_evals": n_eval, "t_em": round(t_em, 1),
            "owl_opt_ages": [float(a) for a in getattr(q, "ssecAges", [])], "owl_opt": None if owl is None else round(owl),
            "t_owl": round(t_owl, 1), "conv_owl": q.convergenceType,
            "full_at_em_ages": None if full_at_em is None else round(full_at_em)}


if __name__ == "__main__":
    for c in sys.argv[1:]:
        print(json.dumps(run(c)), flush=True)
