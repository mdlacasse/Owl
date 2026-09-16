"""Loop-mode invariant for the lp-only strip.

Solves every example case and a set of Case_dana historical windows with every MILP mode
removed from the options (so the pre-strip code runs in loop mode, and the post-strip code
accepts the same options), MOSEK, and records what the strip must not change.

Usage: uv run python loop_baseline.py OUT.json
"""
import contextlib
import io
import json
import pathlib
import sys

import numpy as np
import owlplanner as owl
from owlplanner.plan import Plan

ROOT = pathlib.Path("/Users/mdlacasse/Owl.dev")
DROP = ("bigMamo", "bigMaca", "bigMss", "bigMltcg", "bigMniit", "bendersMaxIter", "withDecomposition",
        "withMedicare", "withACA", "withLTCG", "withNIIT", "withSSAges", "withdrawalOrder", "gap",
        "withSSTaxability", "withSCLoop", "amoRoth", "amoSurplus", "amoConstraints")

builds = {"n": 0}
_orig = Plan._buildConstraints


def _counting(self, *a, **k):
    builds["n"] += 1
    return _orig(self, *a, **k)


Plan._buildConstraints = _counting


def opts_for(p):
    o = {k: v for k, v in dict(p.solverOptions).items() if k not in DROP}
    o["solver"] = __import__("os").environ.get("SOLVER", "MOSEK")
    return o


def record(p):
    ok = p.caseStatus == "solved"
    return {
        "status": p.caseStatus,
        "conv": getattr(p, "convergenceType", None),
        "builds": builds["n"],
        "bequest": float(p.bequest) if ok else None,
        "basis": float(p.g_n[0]) if ok else None,
        "x0": np.asarray(p.x_in, float)[:, 0].tolist() if ok else None,
        "totalTaxes": float(np.sum(p.T_n)) if ok else None,
    }


def run(label, build, objective, opts):
    builds["n"] = 0
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        p = build()
        p.solve(objective, opts(p))
    r = record(p)
    print(f"{label:<45} {r['status']:<12} {str(r['conv']):<32} builds={r['builds']:<3} "
          f"bequest={r['bequest']} basis={r['basis']}", flush=True)
    return r


out = {}
for f in sorted((ROOT / "examples").glob("Case_*.toml")):
    def build(f=f):
        return owl.readConfig(str(f), verbose=False)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        obj = owl.readConfig(str(f), verbose=False).objective
    out[f.stem] = run(f.stem, build, obj, opts_for)

for year in (1928, 1965, 1966, 1969, 1999):
    for obj in ("maxBequest", "maxSpending"):
        def build(year=year):
            p = owl.readConfig(str(ROOT / "examples" / "Case_dana.toml"), verbose=False)
            p.setRates("historical", year)
            return p

        def opts(p, obj=obj):
            o = opts_for(p)
            if obj == "maxBequest":
                o.pop("bequest", None)
                o["netSpending"] = 58.0
            else:
                o.pop("netSpending", None)
            return o
        out[f"dana_{year}_{obj}"] = run(f"dana_{year}_{obj}", build, obj, opts)

json.dump(out, open(sys.argv[1], "w"), indent=1)
