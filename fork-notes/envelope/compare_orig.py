"""EM vs full Owl on the ORIGINAL case inputs: inflation, OBBBA expiry, the case's own rate
sequence and dividends all kept. The EM uses the plan's own per-year returns (balance-weighted
mean across accounts) and leaves out only tax inside the taxable account.

Variant mu0: same, with the dividend rate set to 0 in both models (isolates dividend drag).
"""
import sys, glob, os, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa  (chdir to examples)
from owlplanner import utils as u  # noqa
import em  # noqa

PEN = os.environ.get("EM_PEN", "1") == "1"
TAX = os.environ.get("EM_TAX", "1") == "1"
REF = os.environ.get("EM_REF") == "1"          # also the exact (full-band) DP
VARIANTS = os.environ.get("EM_VARIANTS", "orig").split(",")


def one(path, mu0):
    p = compare.load(path)
    if compare.PHI1:
        p.setBeneficiaryFractions([1, 1, 1, 1])
    if mu0:
        p.setDividendRate(0.0)
    opts = dict(p.solverOptions)
    opts["maxTime"] = 120
    t = time.time()
    p.solve(p.objective, opts)
    tf = time.time() - t
    if p.caseStatus != "solved":
        return {"full": None}
    full = p.basis if p.objective == "maxSpending" else p.bequest
    inp = em.inputs(p, opts)
    kw = (dict(bequest=u.get_monetary_option(opts, "bequest", 1) if "bequest" in opts else 1.0)
          if p.objective == "maxSpending" else dict(netSpending=u.get_monetary_option(opts, "netSpending", 1)))
    res = em.solve_dp(inp, r=None, penalty=PEN, taxable=TAX, **kw)
    ref = em.solve_dp(inp, r=None, fast=False, penalty=PEN, taxable=TAX, **kw) if REF else {"value": np.nan, "t_total": np.nan}
    fx = p.w_ijn[:, 1, :].sum(axis=0) + p.x_in.sum(axis=0)
    ev0 = em.evaluate(inp, None, fx, **kw)
    eo, eq, pen = em.owl_extras(p)
    ev = em.evaluate(inp, None, fx, eo=eo, eq=eq, pen=pen, **kw)
    pct = lambda v: round(100 * (v - full) / abs(full), 2)
    return {"full": round(full), "em": round(res["value"]), "err_pct": pct(res["value"]),
            "em_ref": None if np.isnan(ref["value"]) else round(ref["value"]), "fp_gap": res.get("fp_gap"), "draw_excess": round(res["draw_excess"]), "acct_err_pct": pct(ev["value"]), "acct0_err_pct": pct(ev0["value"]),
            "em_pen": round(res["penalty_total"]), "owl_pen": round(float(pen.sum())),
            "em_drag": round(res["drag_income"]), "owl_drag": round(float((eo + eq).sum())),
            "iters": res["iters"], "converged": res["converged"],
            "R_spread_pct": round(100 * inp["R_spread"], 2), "mu": inp["mu"],
            "conv": p.convergenceType,
            "resid": round(sum(v["abs_sum"] for v in getattr(p, "fixedPointResidual", {}).values())),
            "t_full": round(tf, 2), "t_em": round(res["t_total"], 3), "t_em_ref": None if np.isnan(ref["t_total"]) else round(ref["t_total"], 2),
            "liq_min": round(res["liq_min"])}


if __name__ == "__main__":
    cases = sys.argv[1:] or sorted(glob.glob("Case_*.toml"))
    for c in cases:
        out = {"case": os.path.basename(c)[5:-5]}
        if compare.PHI1:
            out["phi1"] = True
        for tag, mu0 in (("orig", False), ("mu0", True)):
            if tag in VARIANTS:
                out[tag] = one(c, mu0)
        print(json.dumps(out), flush=True)
