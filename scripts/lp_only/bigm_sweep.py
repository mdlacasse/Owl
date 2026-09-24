"""The 72-window record with every bracket bound derived from the quantity it gates.

The SS rows used to gate pmin (<= min(Delta_P, zetaBar), about $12k) and tss (<= 0.85*zetaBar)
with a flat BIGM_AMO = 5e7, as did the IRMAA and ACA bracket shares, through an option still named
bigMamo after the retired AMO exclusions. Those knobs are gone (963468f5): each row's bound is now
derived from what the row itself can reach. This runs the monolithic all-four MILP on that model
and compares value and time with milp_all72.json, whose arms used the old flat constants.

Read before comparing: milp_all72.json stores only {"v", "x0"} per arm -- no times and no gaps --
so a difference against it is a difference against an uncertified reference, not against truth.
Its run used MOSEK, gap 1e-4, maxTime 1800, 5 workers x 2 threads
(pubs/Cost_of_Committing/images/MILP_RUN_STATE.md).

Usage: uv run python bigm_sweep.py OUT.json [years...]   (checkpoints, resumes; WORKERS, THREADS)
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

REF = json.load(open("/Users/mdlacasse/Owl/pubs/Cost_of_Committing/images/milp_all72.json"))
OUT = pathlib.Path(sys.argv[1])
YEARS = [int(y) for y in sys.argv[2:]] or list(range(1928, 2000))
ALL4 = {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize", "withNIIT": "optimize"}
TIGHT = {}  # the bounds are derived from the model now; there are no big-M knobs left
WORKERS, THREADS = int(os.environ.get("WORKERS", "3")), int(os.environ.get("THREADS", "3"))
lock = threading.Lock()


def run(year):
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p = owl.readConfig("examples/Case_dana.toml", verbose=False)
        o = dict(p.solverOptions)
        o.update({"solver": "MOSEK", "gap": 1e-4, "maxTime": 1800, "numThreads": THREADS, **ALL4, **TIGHT})
        o.pop("bequest", None)
        o["netSpending"] = 58.0
        p.setRates("historical", year)
        p.solve("maxBequest", options=o)
    rec = {"status": p.caseStatus, "conv": p.convergenceType, "seconds": round(time.time() - t0, 1),
           "gap": float(getattr(p, "solverGap", -1.0))}
    if p.caseStatus == "solved":
        rec["bequest"] = float(p.bequest)
        rec["residual"] = {k: round(v["abs_sum"], 2) for k, v in p.fixedPointResidual.items()}
    return year, rec


res = json.loads(OUT.read_text()) if OUT.exists() else {}
todo = [y for y in YEARS if str(y) not in res]
print(f"{len(todo)} windows, {WORKERS}x{THREADS}", flush=True)
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for fut in as_completed([ex.submit(run, y) for y in todo]):
        year, rec = fut.result()
        with lock:
            res[str(year)] = rec
            OUT.write_text(json.dumps(res, indent=1))
        milp = REF[str(year)]["milp_star"]["v"]
        print(f"{year}: {rec['status']:9} value {rec.get('bequest', float('nan')):12,.2f} "
              f"vs milp_all72 {rec.get('bequest', float('nan')) - milp:+10,.2f} gap {rec['gap']:8.1e} "
              f"{rec['seconds']:7.1f}s", flush=True)
print("done", flush=True)
