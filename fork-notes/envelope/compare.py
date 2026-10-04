"""Full Owl vs envelope model (em.py) on the same envelope-world inputs.

For each case: build the plan, switch to envelope inputs (OBBBA never expires, inflation 0,
dividends 0, every asset class at one real return r), solve the full model, then the EM on
the inputs read from that same plan.  r = 0 (rung L4) and r = r_c (rung L5, see ladder.py).
"""
import sys, glob, os, io, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(os.environ.get("EM_EXAMPLES", os.path.join(HERE, "..", "..", "examples")))
from owlplanner.config.toml_io import load_toml  # noqa
from owlplanner.config.plan_bridge import config_to_plan  # noqa
from owlplanner import utils as u  # noqa
import em  # noqa


def load(path):
    diconf, dirname, _ = load_toml(path)
    return config_to_plan(diconf, dirname, verbose=False, logstreams=[io.StringIO()], loadHFP=True)


PHI1 = os.environ.get("EM_PHI1") == "1"


def envelope(path, r):
    p = load(path)
    if PHI1:
        p.setBeneficiaryFractions([1, 1, 1, 1])
    p.setExpirationYearOBBBA(2099)
    p.setRates("user", values=[r * 100] * 3 + [0.0])
    p.setDividendRate(0.0)
    opts = dict(p.solverOptions)
    opts["maxTime"] = 120
    t = time.time()
    p.solve(p.objective, opts)
    tf = time.time() - t
    full = None
    if p.caseStatus == "solved":
        full = p.basis if p.objective == "maxSpending" else p.bequest
    return p, opts, full, tf


def run(path, rc):
    out = {"case": os.path.basename(path)[5:-5]}
    for tag, r in (("r0", 0.0), ("rc", rc)):
        p, opts, full, tf = envelope(path, r)
        out[tag] = {"r": round(r * 100, 2), "full": None if full is None else round(full), "t_full": round(tf, 2),
                    "conv": p.convergenceType,
                    "resid": round(sum(v["abs_sum"] for v in getattr(p, "fixedPointResidual", {}).values()))}
        if full is None:
            continue
        inp = em.inputs(p, opts)
        beq = None
        if p.objective == "maxSpending":
            beq = u.get_monetary_option(opts, "bequest", 1) if "bequest" in opts else 1.0
            res = em.solve_dp(inp, r=r, bequest=beq)
        else:
            res = em.solve_dp(inp, r=r, netSpending=u.get_monetary_option(opts, "netSpending", 1))
        full_x = (p.w_ijn[:, 1, :].sum(axis=0) + p.x_in.sum(axis=0))
        out[tag].update({
            "em": round(res["value"]), "err_pct": round(100 * (res["value"] - full) / abs(full), 2) if full else None,
            "t_em": round(res["t_total"], 2), "t_table": round(res["t_table"], 2), "grid": res["grid"],
            "liq_min": round(res["liq_min"]), "rmd_iters": res["iters"],
            "x_em_total": round(float(res["x"].sum())), "x_full_total": round(float(full_x.sum())),
            "tax_em": round(float(res["tau"].sum())),
            "tax_full": round(float((p.T_n + p.U_n + p.J_n + p.st_T_n + p.M_n + p.ACA_n + p.maca_n).sum())),
        })
        # plug the full model's recognition schedule into the EM accounting (same x, EM taxes)
        kw = dict(bequest=beq) if p.objective == "maxSpending" else dict(netSpending=u.get_monetary_option(opts, "netSpending", 1))
        ev = em.evaluate(inp, r, full_x, **kw)
        out[tag]["em_at_full_x"] = round(ev["value"])
        out[tag]["acct_err_pct"] = round(100 * (ev["value"] - full) / abs(full), 2) if full else None
    return out


if __name__ == "__main__":
    ladder = {json.loads(l)["case"]: json.loads(l) for l in open(os.path.join(HERE, "ladder_results.jsonl"))}
    cases = sys.argv[1:] or sorted(glob.glob("Case_*.toml"))
    for c in cases:
        rc = ladder[os.path.basename(c)]["rc"] / 100
        print(json.dumps(run(c, rc)), flush=True)
