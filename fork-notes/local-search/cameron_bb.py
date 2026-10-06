import io, sys, time
import numpy as np
from owlplanner.config.plan_bridge import config_to_plan
from owlplanner.config.toml_io import load_toml
def load():
    d, dn, _ = load_toml("Case_cameron.toml")
    return config_to_plan(d, dn, verbose=False, logstreams=[io.StringIO()], loadHFP=True)
p0 = load(); print(p0.objective, dict(p0.solverOptions))
for extra in ({"withSSTaxability": "optimize"}, {"breakpointMethod": "branch-and-bound", "maxTime": 300}):
    p = load(); o = dict(p.solverOptions); o.update(extra)
    t = time.time(); p.solve(p.objective, o); dt = time.time() - t
    r = getattr(p, "fixedPointResidual", {})
    print(extra, p.caseStatus, round(p.basis), f"{dt:.1f}s", "gap", p.solverGap, {k: round(v["abs_sum"]) for k, v in r.items() if v["abs_sum"] > 1}, p.convergenceType)
