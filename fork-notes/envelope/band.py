"""Pinned loop with different bands around the EM's yearly recognition (EM_BAND="below,above" in
EM grid steps; seed.py reads it at import). john+sally: the EM's schedule is infeasible in Owl
unless recognition may exceed it."""
import sys
import os
import json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa  (chdir to examples)
import seed  # noqa

for c in sys.argv[1:]:
    p = compare.load(c)
    opts = dict(p.solverOptions)
    opts["maxTime"] = 300
    p.solve(p.objective, opts)
    s = seed.em_seed(p, opts)
    q = compare.load(c)
    t = seed.seeded_pinned_solve(q, dict(opts), s)
    zero = [int(p.year_n[n]) for n in range(p.N_n) if s["x"][n] == 0]
    print(json.dumps({"case": c, "band": seed.BAND, "default": round(seed.value(p)), "em": round(s["em"]),
                      "pinned": None if q.caseStatus != "solved" else round(seed.value(q)), "status": q.caseStatus,
                      "conv": q.convergenceType, "resid": seed.resid(q), "t": round(t, 2),
                      "em_zero_years": zero, "h_first": round(float(s["h"][0]))}), flush=True)
