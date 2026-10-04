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
    res = em.solve_dp(inp, r=None, **kw)
    ref = em.solve_dp(inp, r=None, fast=False, **kw)
    fx = p.w_ijn[:, 1, :].sum(axis=0) + p.x_in.sum(axis=0)
    ev = em.evaluate(inp, None, fx, **kw)
    pct = lambda v: round(100 * (v - full) / abs(full), 2)
    return {"full": round(full), "em": round(res["value"]), "err_pct": pct(res["value"]),
            "em_ref": round(ref["value"]), "acct_err_pct": pct(ev["value"]),
            "R_spread_pct": round(100 * inp["R_spread"], 2), "mu": inp["mu"],
            "conv": p.convergenceType,
            "resid": round(sum(v["abs_sum"] for v in getattr(p, "fixedPointResidual", {}).values())),
            "t_full": round(tf, 2), "t_em": round(res["t_total"], 3), "t_em_ref": round(ref["t_total"], 2),
            "liq_min": round(res["liq_min"])}


if __name__ == "__main__":
    cases = sys.argv[1:] or sorted(glob.glob("Case_*.toml"))
    for c in cases:
        out = {"case": os.path.basename(c)[5:-5]}
        if compare.PHI1:
            out["phi1"] = True
        for tag, mu0 in (("orig", False), ("mu0", True)):
            out[tag] = one(c, mu0)
        print(json.dumps(out), flush=True)
