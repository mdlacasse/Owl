"""Attribute the base Case_dana LP-vs-MILP gap to tax families, and audit every MILP answer.

Runs against the MILP engine: PYTHONPATH=/Users/mdlacasse/Owl/src.
Setup matches milp_all72.py (MILP_RUN_STATE.md): Case_dana as shipped, maxBequest, netSpending
58k, MOSEK, gap 1e-4, maxTime 1800 (per SC iteration), numThreads 2, 5 workers.

Arms per window: loop, one family optimized at a time (SS, IRMAA, LTCG, NIIT), and all four.
Each solved plan is audited: every tax and premium is recomputed from the plan's own solved
incomes with the pure tax functions, and compared with what the plan charged. A nonzero audit
means the reported objective is not achievable under the tax rules as coded in tax_federal /
the state table, i.e. the model -- not the solver -- is off. Checked families:
  fed_ordinary  : bracket tax on G, with the standard deduction recomputed from the final MAGI
                  (OBBBA senior deduction uses the previous iteration's MAGI inside the LP)
  ss_taxable    : taxable SS vs IRS Pub 915 on the final provisional income (income, not tax)
  ltcg, niit, medicare : recomputed from final G, Q, I, MAGI
  state         : state tax with the SS exclusion taken from the true taxable SS rather than the
                  lagged Psi_n parameter the state row uses in every mode

Usage: PYTHONPATH=/Users/mdlacasse/Owl/src uv run python attribute_dana.py OUT.json [years...]
Checkpoints after every solve and resumes.
"""
import contextlib
import io
import json
import pathlib
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import owlplanner as owl
from owlplanner import tax_federal as tx

assert "/Users/mdlacasse/Owl/src" in owl.__file__, owl.__file__

OUT = pathlib.Path(sys.argv[1])
YEARS = [int(y) for y in sys.argv[2:]] or [1928, 1966, 1982, 1983, 1932]
CASE = "/Users/mdlacasse/Owl/examples/Case_dana.toml"
ARMS = {
    "loop": {},
    "SS": {"withSSTaxability": "optimize"},
    "IRMAA": {"withMedicare": "optimize"},
    "LTCG": {"withLTCG": "optimize"},
    "NIIT": {"withNIIT": "optimize"},
    "ALL4": {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize",
             "withNIIT": "optimize"},
}
lock = threading.Lock()


def bracket_tax(income, rates, widths):
    """Progressive tax: rates (T, N), widths (T, N) nominal, income (N,)."""
    lower = np.vstack([np.zeros(income.shape), np.cumsum(widths, axis=0)[:-1, :]])
    return np.sum(rates * np.clip(income[None, :] - lower, 0.0, widths), axis=0)


def audit(p):
    Nn, Ni = p.N_n, p.N_i
    g = p.gamma_n[:Nn]
    ss = np.sum(p.zetaBar_in, axis=0)
    status = np.full(Nn, Ni - 1)
    if Ni == 2 and p.n_d < Nn:
        status[p.n_d:] = 0
    out = {}

    # Taxable SS: what the plan charged vs Pub 915 on its own provisional income.
    tss_rep = p.Psi_n * ss
    tss_true = tx.compute_social_security_taxability(Ni, p.MAGI_aca_n, ss, n_d=p.n_d) * ss
    out["ss_taxable_income"] = (tss_rep - tss_true) / g

    # Federal ordinary tax. B = income before the standard deduction, as the LP built it.
    B = p.G_n + p.e_n
    sigma_true = tx.taxParams(p.yobs, p.i_d, p.n_d, Nn, p.gamma_n, p.MAGI_n, p.yOBBBA)[0]
    B_true = B - tss_rep + tss_true
    G_true = np.maximum(0.0, B_true - sigma_true)
    T_rep = np.sum(p.theta_tn * np.clip(p.G_n[None, :] - np.vstack([np.zeros(Nn), np.cumsum(p.DeltaBar_tn, 0)[:-1]]),
                                        0.0, p.DeltaBar_tn), axis=0)
    T_true = bracket_tax(G_true, p.theta_tn, p.DeltaBar_tn)
    out["fed_ordinary"] = (T_rep - T_true) / g
    out["std_deduction_used_minus_true"] = (p.sigmaBar_n - sigma_true) / g

    # LTCG on Q stacked on true G.
    T15 = g * np.array([tx.capGainRates[s][0] for s in status])
    T20 = g * np.array([tx.capGainRates[s][1] for s in status])

    def ltcg(Q, G):
        lo, hi = G, G + np.maximum(Q, 0)
        return 0.15 * np.maximum(0, np.minimum(hi, T20) - np.maximum(lo, T15)) + 0.20 * np.maximum(0, hi - np.maximum(lo, T20))

    out["ltcg"] = (p.U_n - ltcg(p.Q_n, G_true)) / g

    # AGI-basis MAGI = G + e + Q with the true taxable SS: shift by the SS correction only.
    MAGI_true = p.MAGI_n - tss_rep + tss_true
    out["niit"] = (p.J_n - tx.computeNIIT(Ni, MAGI_true, p.I_n, p.Q_n, p.n_d, Nn)) / g
    M_true = tx.mediCosts(p.yobs, p.horizons, MAGI_true, p.prevMAGI, g, Nn,
                          include_part_d=getattr(p, "_include_medicare_part_d", True),
                          part_d_base_annual_per_person=getattr(p, "_medicare_part_d_base_annual_per_person", 0.0))
    out["medicare"] = (p.medicare_n - M_true) / g

    if getattr(p, "_st_lp", False):
        pe_total = np.sum(p.piBar_in, axis=0)
        pe_cap = np.where(np.isfinite(p.st_pe_cap_n), p.st_pe_cap_n * Ni, pe_total)
        pe_adj = np.minimum(pe_total, pe_cap)
        excl = 0.0 if p.st_tax_ss else tss_true
        income = G_true + np.maximum(p.Q_n, 0) - excl - pe_adj
        income -= np.minimum(np.maximum(income, 0), p.st_sigmaBar_n)
        if np.any(p.st_re_cap_n > 0):
            w1 = np.sum(p.w_ijn[:, 1, :], axis=0)
            income -= np.minimum(np.maximum(income, 0), np.minimum(np.where(np.isfinite(p.st_re_cap_n), p.st_re_cap_n, 1e18), w1))
        st_true = bracket_tax(np.maximum(income, 0), p.st_theta_tn, p.st_DeltaBar_tn)
        out["state"] = (p.st_T_n - st_true) / g

    return {k: {"sum": float(np.sum(v)), "abs_sum": float(np.sum(np.abs(v))), "max_abs": float(np.max(np.abs(v)))}
            for k, v in out.items()}


def run(year, arm):
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p = owl.readConfig(CASE, verbose=False)
        p.mylog.setVerbose(False)
        o = dict(p.solverOptions)
        o.update({"solver": __import__("os").environ.get("SOLVER", "MOSEK"), "gap": 1e-4, "maxTime": 1800,
                  "numThreads": 2})
        o.pop("bequest", None)
        o["netSpending"] = 58.0
        o.update(ARMS[arm])
        p.setRates("historical", year)
        p.solve("maxBequest", options=o)
    rec = {"status": p.caseStatus, "conv": p.convergenceType, "gap": float(getattr(p, "solverGap", -1)),
           "seconds": round(time.time() - t0, 1)}
    if p.caseStatus == "solved":
        rec["bequest"] = float(p.bequest)
        rec["x0"] = float(p.x_in[0, 0])
        rec["audit"] = audit(p)
    return year, arm, rec


res = json.loads(OUT.read_text()) if OUT.exists() else {}
jobs = [(y, a) for a in ARMS if a != "ALL4" for y in YEARS] + [(y, "ALL4") for y in YEARS]
jobs = [(y, a) for y, a in jobs if a not in res.get(str(y), {})]
_only = __import__("os").environ.get("ARMS_ONLY")
if _only:
    jobs = [(y, a) for y, a in jobs if a in _only.split(",")]
print(f"{len(jobs)} solves queued", flush=True)
WORKERS = int(__import__("os").environ.get("WORKERS", "2"))
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = {ex.submit(run, y, a): (y, a) for y, a in jobs}
    for f in as_completed(futs):
        y, a = futs[f]
        try:
            y, a, rec = f.result()
        except Exception as exc:
            rec = {"status": f"raised {type(exc).__name__}: {exc}"}
        with lock:
            res.setdefault(str(y), {})[a] = rec
            OUT.write_text(json.dumps(res, indent=1))
        worst = ""
        if "audit" in rec:
            worst = max(rec["audit"].items(), key=lambda kv: kv[1]["abs_sum"])
            worst = f"worst audit {worst[0]} abs_sum {worst[1]['abs_sum']:,.0f}"
        print(f"{y} {a:<5} {rec.get('status')} {rec.get('conv', '')} bequest {rec.get('bequest', float('nan')):,.0f} "
              f"gap {rec.get('gap', -1):.1e} {rec.get('seconds', 0)}s {worst}", flush=True)
print("done", flush=True)
