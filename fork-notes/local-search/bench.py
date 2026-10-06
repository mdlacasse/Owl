"""Loop vs local search (breakpointMethod="local-search") on the shipped examples.

Usage: python bench.py [--opts JSON] [--tag NAME] [Case_x.toml ...]   (run from anywhere)
Each case is solved with its own solver options (the loop), then with the same options plus
breakpointMethod="local-search". One JSON line per case and method on stdout.
Objective: spending basis (today's $) for maxSpending, bequest (today's $) for maxBequest.
"""
import argparse
import glob
import io
import json
import os
import sys
import time

from owlplanner.config.plan_bridge import config_to_plan
from owlplanner.config.toml_io import load_toml

EXAMPLES = os.environ.get("OWL_EXAMPLES", os.path.join(os.path.dirname(__file__), "..", "..", "examples"))


def load(path):
    diconf, dirname, _ = load_toml(path)
    return config_to_plan(diconf, dirname, verbose=False, logstreams=[io.StringIO()], loadHFP=True)


def run(path, extra, method):
    p = load(path)
    opts = dict(p.solverOptions)
    opts.update(extra)
    if method != "loop":
        opts["breakpointMethod"] = method
    t = time.time()
    p.solve(p.objective, opts)
    dt = time.time() - t
    out = {"case": os.path.basename(path)[5:-5], "method": method, "status": p.caseStatus, "seconds": round(dt, 1)}
    if p.caseStatus != "solved":
        return out
    obj = p.basis if p.objective == "maxSpending" else p.bequest
    resid = getattr(p, "fixedPointResidual", {}) or {}
    out.update({
        "objective": p.objective,
        "value": round(float(obj)),
        "used": getattr(p, "breakpointMethodUsed", None),
        "resid_abs": round(sum(v["abs_sum"] for v in resid.values())),
        "resid": {k: round(v["abs_sum"]) for k, v in resid.items() if v["abs_sum"] >= 1},
        "aca_today": round(float((p.aca_costs_n / p.gamma_n[:p.N_n]).sum())) if p.slcsp_annual > 0 else None,
        "irmaa_today": round(float((p.medicare_n / p.gamma_n[:p.N_n]).sum())),
        "gap": getattr(p, "solverGap", None),
    })
    log = getattr(p, "localSearchLog", None)
    if method == "local-search" and log:
        out["ls_iters"] = len(log)
        out["ls_steps"] = sum(len(e["steps"]) for e in log)
        out["ls_time"] = round(sum(e["time"] for e in log), 1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--opts", default="{}")
    ap.add_argument("--methods", default="loop,local-search")
    ap.add_argument("--tag", default="")
    ap.add_argument("cases", nargs="*")
    a = ap.parse_args()
    extra = json.loads(a.opts)
    cases = a.cases or sorted(glob.glob(os.path.join(EXAMPLES, "Case_*.toml")))
    os.chdir(EXAMPLES)  # HFP files are found relative to the case
    for c in cases:
        for m in a.methods.split(","):
            r = run(os.path.abspath(c) if os.path.exists(c) else c, extra, m)
            r["tag"] = a.tag
            r["opts"] = extra
            print(json.dumps(r), flush=True)
