"""Record the AMO-constrained (MIP) optimum for every example case.

Run this from a checkout that still builds the ``zx`` exclusion binaries. The
resulting fixture is the permanent oracle for ``tests/plan/test_amo_postprocess.py``:
it is what lets us assert that post-processing reproduces the MIP optimum after the
binaries themselves have been removed from the model.

    uv run python scripts/capture_amo_reference.py

Writes tests/data/amo_mip_reference.json.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import sys
import time

import numpy as np

import owlplanner as owl

EXDIR = "examples"
OUTFILE = os.path.join("tests", "data", "amo_mip_reference.json")

CASES = [
    "Case_alex+jamie",
    "Case_bill",
    "Case_chris+pat",
    "Case_dana",
    "Case_devon",
    "Case_helen+ruth",
    "Case_jack+jill",
    "Case_joe",
    "Case_john+sally",
    "Case_jon+jane",
    "Case_jordan+taylor",
    "Case_kim+sam-bequest",
    "Case_kim+sam-spending",
    "Case_morgan",
    "Case_robin",
]


def mosek_available():
    try:
        import mosek  # noqa: F401
    except ImportError:
        return False
    return os.path.exists(os.path.expanduser("~/mosek/mosek.lic")) or "MOSEKLM_LICENSE_FILE" in os.environ


def amo_violations(p):
    """Count years where the two AMO exclusions are violated, at household level."""
    roth = surplus = 0
    n595_max = int(np.max(p.n595))
    for n in range(p.N_n):
        if n >= n595_max and np.sum(p.x_in[:, n]) > 1 and np.sum(p.w_ijn[:, 2, n]) > 1:
            roth += 1
        if p.s_n[n] > 1 and np.sum(p.w_ijn[:, 0, n]) + np.sum(p.w_ijn[:, 2, n]) > 1:
            surplus += 1
    return roth, surplus


def capture(case, solver):
    p = owl.readConfig(os.path.join(EXDIR, case), verbose=False)
    p.setVerbose(False)
    p.solverOptions["solver"] = solver
    p.solverOptions["amoConstraints"] = True
    t0 = time.time()
    p.resolve()
    elapsed = time.time() - t0
    roth, surplus = amo_violations(p)
    return {
        "objective": p.objective,
        "basis": round(float(p.basis), 2),
        "bequest": round(float(p.bequest), 2),
        "seconds": round(elapsed, 2),
        "nbins": int(p.nbins),
        "amo_violations": {"roth": roth, "surplus": surplus},
        # Per-year flows: enough to diff a plan's shape, small enough to read in a review.
        "surplus_n": [round(float(v), 2) for v in p.s_n],
        "conversions_n": [round(float(v), 2) for v in np.sum(p.x_in, axis=0)],
        "withdrawals_jn": [[round(float(v), 2) for v in np.sum(p.w_ijn[:, j, :], axis=0)] for j in range(p.N_j)],
    }


def main():
    solvers = ["HiGHS"] + (["MOSEK"] if mosek_available() else [])
    if "MOSEK" not in solvers:
        print("WARNING: MOSEK not available; capturing HiGHS only.", file=sys.stderr)

    out = {"_generated_by": "scripts/capture_amo_reference.py", "_solvers": solvers, "cases": {}}
    for case in CASES:
        out["cases"][case] = {}
        for solver in solvers:
            try:
                rec = capture(case, solver)
            except Exception as e:  # keep going; a missing case is better than no fixture
                print(f"{case:24s} {solver:6s} FAILED: {type(e).__name__}: {e}", file=sys.stderr)
                continue
            out["cases"][case][solver] = rec
            v = rec["amo_violations"]
            print(
                f"{case:24s} {solver:6s} basis={rec['basis']:>14,.2f} bequest={rec['bequest']:>16,.2f} "
                f"t={rec['seconds']:7.2f}s nbins={rec['nbins']:4d} viol(roth={v['roth']},surplus={v['surplus']})",
                flush=True,
            )

    os.makedirs(os.path.dirname(OUTFILE), exist_ok=True)
    with open(OUTFILE, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"\nWrote {OUTFILE}")


if __name__ == "__main__":
    main()
