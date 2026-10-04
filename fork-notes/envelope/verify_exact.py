"""Re-solve the envelope-world full model with Owl's exact MILP modes, to check EM's gains over loop mode."""
import sys, json, time
import compare
from owlplanner import utils as u

case, r = sys.argv[1], float(sys.argv[2])
fams = sys.argv[3].split(",")
p = compare.load(case)
import os
if os.environ.get("EM_PHI1") == "1":
    p.setBeneficiaryFractions([1, 1, 1, 1])
p.setExpirationYearOBBBA(2099)
p.setRates("user", values=[r * 100] * 3 + [0.0])
p.setDividendRate(0.0)
opts = dict(p.solverOptions)
opts["maxTime"] = float(sys.argv[4]) if len(sys.argv) > 4 else 120
for f in fams:
    opts[f] = "optimize"
t = time.time()
p.solve(p.objective, opts)
v = (p.basis if p.objective == "maxSpending" else p.bequest) if p.caseStatus == "solved" else None
print(json.dumps({"case": case, "r": r, "families": fams, "value": None if v is None else round(v),
                  "t": round(time.time() - t, 1), "conv": p.convergenceType}), flush=True)
