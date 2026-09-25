"""Does the lbbd decomposition still earn its place once the big-M bounds are derived?

The earlier lbbd measurements (lbbd_sweep.json, 31a2ab71) were taken against the model whose
bracket rows were relaxed by a flat 5e7, where branch-and-bound was crippled and almost anything
looked good next to it. 963468f5 derives each bound from what its row gates, and the monolithic
MILP got much faster: 56 of 72 windows now finish under 600 s (results/derived_sweep.json). This
re-runs the decomposition on that same model and asks whether it is still worth having.

The reference here is results/derived_sweep.json, not milp_all72.json: same engine, same bounds,
same options, and 71 of its 72 windows are certified at gap <= 1e-4, so a disagreement is
meaningful. milp_all72.json records no gaps and no times and cannot settle anything.

decompBudget is a deadline for the whole solve, so it is set high enough here that lbbd is
measured by when it certifies rather than by when it is cut off; maxTime stays at 1800 per solve,
as in the monolithic run.

Do not trust "lbbd_lines" when WORKERS > 1. contextlib.redirect_stdout swaps sys.stdout for the
whole process, not per thread, so concurrent workers clobber each other's capture: lines land in
another year's record or in none at all, and the .log file loses most of its rows. The values,
times and gaps are read off the returned plan and are unaffected. Run WORKERS=1 to attribute how a
solve ended -- from lbbd's own cuts, or from the warm-started monolithic MIP it hands off to.

Usage: uv run python derived_lbbd.py OUT.json [years...]   (checkpoints, resumes; WORKERS, THREADS)
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
MONO = json.load(open(HERE / "results" / "derived_sweep.json"))
OUT = pathlib.Path(sys.argv[1])
YEARS = [int(y) for y in sys.argv[2:]] or sorted(int(y) for y in MONO)
ALL4 = {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize", "withNIIT": "optimize"}
GAP = 1e-4
BUDGET = float(os.environ.get("BUDGET", "5400"))
WORKERS, THREADS = int(os.environ.get("WORKERS", "3")), int(os.environ.get("THREADS", "3"))
lock = threading.Lock()


def run(year):
    t0 = time.time()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        p = owl.readConfig("examples/Case_dana.toml", verbose=True)
        o = dict(p.solverOptions)
        o.update({"solver": "MOSEK", "gap": GAP, "maxTime": 1800, "numThreads": THREADS, "verbose": True, **ALL4})
        o.update({"withDecomposition": "lbbd", "decompBudget": BUDGET})
        o.pop("bequest", None)
        o["netSpending"] = 58.0
        p.setRates("historical", year)
        p.solve("maxBequest", options=o)
    rec = {"status": p.caseStatus, "conv": p.convergenceType, "seconds": round(time.time() - t0, 1),
           "gap": float(getattr(p, "solverGap", -1.0)),
           "lbbd_lines": [ln.strip()[:160] for ln in buf.getvalue().splitlines() if "LBBD" in ln][-6:]}
    if p.caseStatus == "solved":
        rec["bequest"] = float(p.bequest)
        rec["certified"] = bool(0.0 <= rec["gap"] <= GAP)
        rec["residual"] = {k: round(v["abs_sum"], 2) for k, v in p.fixedPointResidual.items()}
    return year, rec


res = json.loads(OUT.read_text()) if OUT.exists() else {}
todo = [y for y in YEARS if str(y) not in res]
print(f"{len(todo)} windows, {WORKERS}x{THREADS}, budget {BUDGET:.0f}s", flush=True)
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for fut in as_completed([ex.submit(run, y) for y in todo]):
        year, rec = fut.result()
        with lock:
            res[str(year)] = rec
            OUT.write_text(json.dumps(res, indent=1))
        m = MONO[str(year)]
        speed = m["seconds"] / rec["seconds"] if rec["seconds"] > 0 else float("nan")
        print(f"{year}: lbbd {rec.get('bequest', float('nan')):12,.2f} gap {rec['gap']:8.1e} "
              f"{'CERT' if rec.get('certified') else ' -- '} {rec['seconds']:7.1f}s "
              f"| mono {m.get('bequest', float('nan')):12,.2f} gap {m['gap']:8.1e} {m['seconds']:7.1f}s "
              f"| {speed:5.2f}x  diff {rec.get('bequest', float('nan')) - m.get('bequest', float('nan')):+10,.2f}",
              flush=True)
        for ln in rec["lbbd_lines"][-2:]:
            print(f"      | {ln}", flush=True)
print("done", flush=True)
