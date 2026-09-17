"""Is Benders decomposition exact and cheap now that the AMO binaries are gone?

`benders-integer-recourse-defect` recorded that `_benders_solve` was not exact because the AMO
binaries `zx` stayed in the subproblem, so optimality cuts came from an LP relaxation of a
subproblem that still had integers. `zx` was removed on 2026-08-11 (e6f9b45); with bracket binaries
in the master and no other integers (no withSSAges="optimize", no withdrawalOrder="taxable_first"),
the subproblem is a pure LP and classical Benders should be exact.

For one Case_dana window (maxBequest, netSpending 58k, MOSEK, gap 1e-4): solve the all-four MILP
monolithically and with withDecomposition="benders", and report value, time, and whether the run
fell back to relax-and-fix (the engine's own log says so). Compares against milp_all72.json.

Usage: PYTHONPATH=/Users/mdlacasse/Owl/src uv run python benders_probe.py YEAR [OUT.json] [--no-mono]
"""
import contextlib
import io
import json
import pathlib
import sys
import time

import numpy as np
import owlplanner as owl

assert "/Users/mdlacasse/Owl/src" in owl.__file__, owl.__file__
YEAR = int(sys.argv[1])
OUT = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
MONO = "--no-mono" not in sys.argv
ALL4 = {"withMedicare": "optimize", "withSSTaxability": "optimize", "withLTCG": "optimize", "withNIIT": "optimize"}
REF = json.load(open("/Users/mdlacasse/Owl/pubs/Cost_of_Committing/images/milp_all72.json"))[str(YEAR)]


def run(extra):
    buf = io.StringIO()
    t0 = time.time()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        p = owl.readConfig("/Users/mdlacasse/Owl/examples/Case_dana.toml", verbose=True)
        o = dict(p.solverOptions)
        o.update({"solver": "MOSEK", "gap": 1e-4, "maxTime": 1800, "numThreads": 2, "verbose": True, **ALL4, **extra})
        o.pop("bequest", None)
        o["netSpending"] = 58.0
        p.setRates("historical", YEAR)
        p.solve("maxBequest", options=o)
    return p, time.time() - t0, buf.getvalue()


rec = {"year": YEAR, "ref_lp_star": REF["lp_star"]["v"], "ref_milp_star": REF["milp_star"]["v"]}
print(f"{YEAR}: milp_all72 lp_star {REF['lp_star']['v']:,.2f}  milp_star {REF['milp_star']['v']:,.2f}")

for name, extra in (("monolithic", {}), ("benders", {"withDecomposition": "benders"})):
    if name == "monolithic" and not MONO:
        continue
    p, t, log = run(extra)
    lines = [ln for ln in log.splitlines() if "Benders" in ln or "Decomp" in ln]
    fell_back = any("relax-and-fix" in ln or "falling back" in ln or "monolithic" in ln for ln in lines)
    rec[name] = {"status": p.caseStatus, "conv": p.convergenceType, "bequest": float(p.bequest),
                 "gap": float(getattr(p, "solverGap", -1)), "seconds": round(t, 1),
                 "vs_ref": float(p.bequest - REF["milp_star"]["v"]), "fell_back": bool(fell_back),
                 "x0": float(p.x_in[0, 0]), "log_tail": lines[-6:]}
    print(f"  {name:11} {p.caseStatus} {p.convergenceType:12} bequest {p.bequest:14,.2f} "
          f"(vs milp_all72 {p.bequest - REF['milp_star']['v']:+,.2f})  gap {rec[name]['gap']:.1e}  {t:8.1f}s  "
          f"fallback {fell_back}")
    for ln in lines[-4:]:
        print(f"      | {ln.strip()[:150]}")

if OUT:
    json.dump(rec, open(OUT, "w"), indent=1)
