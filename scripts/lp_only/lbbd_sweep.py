"""The 72-window record for the lbbd decomposition, with fixed-point residuals.

Two arms per Case_dana window (maxBequest, netSpending 58k, MOSEK, gap 1e-4):
  loop   the self-consistent loop in loop mode -- the everyday engine
  lbbd   all four tax modes optimized, withDecomposition="lbbd", decompBudget 600 (a deadline for
         the whole solve; certification waits until the loop's regimes settle)

Each arm records its value, time, MIP gap and plan.fixedPointResidual: how far the solved plan sits
from the model its own income implies, per tax family, in today's dollars. Values are compared with
pubs/Cost_of_Committing/images/milp_all72.json, whose lp_star is the loop and whose milp_star is the
monolithic all-four optimum.

Answers two questions: can lbbd certify within the budget, and how large is the residual the word
"certified" is conditional on.

Usage: uv run python lbbd_sweep.py OUT.json [years...]   (checkpoints after every solve, resumes)
"""
import contextlib
import io
import json
import os
import pathlib
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import owlplanner as owl

HERE = pathlib.Path(__file__).resolve().parent
REF = json.load(open("/Users/mdlacasse/Owl/pubs/Cost_of_Committing/images/milp_all72.json"))
OUT = pathlib.Path(sys.argv[1])
YEARS = [int(y) for y in sys.argv[2:]] or list(range(1928, 2000))
ALL4 = {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize", "withNIIT": "optimize"}
BUDGET = 600.0
GAP = 1e-4
WORKERS = int(os.environ.get("WORKERS", "3"))
THREADS = int(os.environ.get("THREADS", "3"))  # MOSEK threads per solve; WORKERS x THREADS ~ cores
lock = threading.Lock()


def run(year, arm):
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p = owl.readConfig("examples/Case_dana.toml", verbose=False)
        o = dict(p.solverOptions)
        o.update({"solver": "MOSEK", "gap": GAP, "maxTime": 1800, "numThreads": THREADS})
        if arm == "lbbd":
            o.update(ALL4)
            o.update({"withDecomposition": "lbbd", "decompBudget": BUDGET})
        o.pop("bequest", None)
        o["netSpending"] = 58.0
        p.setRates("historical", year)
        p.solve("maxBequest", options=o)
    rec = {"status": p.caseStatus, "conv": p.convergenceType, "seconds": round(time.time() - t0, 1),
           "gap": float(getattr(p, "solverGap", -1.0))}
    if p.caseStatus == "solved":
        rec["bequest"] = float(p.bequest)
        rec["residual"] = {k: round(v["abs_sum"], 2) for k, v in p.fixedPointResidual.items()}
        rec["residual_max_year"] = {k: round(v["max_abs"], 2) for k, v in p.fixedPointResidual.items()}
        if arm == "lbbd":
            rec["certified"] = bool(0.0 <= rec["gap"] <= GAP)
    return rec


res = json.loads(OUT.read_text()) if OUT.exists() else {}


def both_arms(year):
    out = {}
    for arm in ("loop", "lbbd"):
        if arm in res.get(str(year), {}):
            out[arm] = res[str(year)][arm]
            continue
        out[arm] = run(year, arm)
    return year, out


todo = [y for y in YEARS if len(res.get(str(y), {})) < 2]
print(f"{len(todo)} windows to run, {WORKERS} workers x {THREADS} threads", flush=True)
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for fut in as_completed([ex.submit(both_arms, y) for y in todo]):
        year, rec = fut.result()
        with lock:
            res[str(year)] = rec
            OUT.write_text(json.dumps(res, indent=1))
        ref = REF.get(str(year), {})
        milp = ref.get("milp_star", {}).get("v", float("nan"))
        lo, lb = rec["loop"], rec["lbbd"]
        print(f"{year}: loop {lo.get('bequest', float('nan')):12,.0f} ({lo['seconds']:6.1f}s) "
              f"| lbbd {lb.get('bequest', float('nan')):12,.0f} gap {lb['gap']:8.1e} "
              f"{'CERTIFIED' if lb.get('certified') else '   --    '} ({lb['seconds']:7.1f}s) "
              f"| milp_all72 {milp:12,.0f} diff {lb.get('bequest', float('nan')) - milp:+10,.0f} "
              f"| worst residual: loop {max(list(lo.get('residual', {}).values()) or [0]):9,.0f} "
              f"lbbd {max(list(lb.get('residual', {}).values()) or [0]):9,.0f}", flush=True)
print("done", flush=True)
