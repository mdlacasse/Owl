"""Re-solve the full model on the ORIGINAL case inputs with Owl's exact MILP modes, to check
where the EM beats the default loop mode (orig2_results.jsonl)."""
import sys, os, json, time
import compare  # noqa (chdir to examples)

case = sys.argv[1]
fams = sys.argv[2].split(",")
p = compare.load(case)
if os.environ.get("EM_PHI1") == "1":
    p.setBeneficiaryFractions([1, 1, 1, 1])
opts = dict(p.solverOptions)
opts["maxTime"] = float(sys.argv[3]) if len(sys.argv) > 3 else 300
for f in fams:
    opts[f] = "optimize"
t = time.time()
p.solve(p.objective, opts)
v = (p.basis if p.objective == "maxSpending" else p.bequest) if p.caseStatus == "solved" else None
print(json.dumps({"case": case, "phi1": os.environ.get("EM_PHI1") == "1", "families": fams,
                  "value": None if v is None else round(v), "status": p.caseStatus,
                  "gap": getattr(p, "solverGap", None), "t": round(time.time() - t, 1),
                  "conv": p.convergenceType}), flush=True)
