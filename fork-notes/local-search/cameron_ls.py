import io, sys, json
import numpy as np
from owlplanner.config.plan_bridge import config_to_plan
from owlplanner.config.toml_io import load_toml
case = sys.argv[1] if len(sys.argv) > 1 else "Case_cameron.toml"
def load():
    d, dn, _ = load_toml(case)
    return config_to_plan(d, dn, verbose=False, logstreams=[io.StringIO()], loadHFP=True)
p = load(); o = dict(p.solverOptions)
p.solve(p.objective, o)
g = p.gamma_n[:p.N_n]
res = p._fixedPointResidualByYear(o.get("withMedicare", "loop") == "loop")
print("loop", p.basis if p.objective == "maxSpending" else p.bequest, "convergence", p.convergenceType)
for k, v in res.items():
    if np.abs(v).sum() > 1: print("  ", k, "signed sum", round(v.sum()), "abs", round(np.abs(v).sum()))
p = load(); o2 = dict(o); o2["breakpointMethod"] = "local-search"
p.solve(p.objective, o2)
print("LS used", p.breakpointMethodUsed)
for it, e in enumerate(p.localSearchLog):
    for s in e["steps"]:
        print(it, s["step"][:70], s["ok"], None if s["objective"] is None else round(-s["objective"]))
