import io, sys, json
import numpy as np
from owlplanner.config.plan_bridge import config_to_plan
from owlplanner.config.toml_io import load_toml
for case in sys.argv[1:]:
    d, dn, _ = load_toml(case)
    p = config_to_plan(d, dn, verbose=False, logstreams=[io.StringIO()], loadHFP=True)
    o = dict(p.solverOptions); o["breakpointMethod"] = "local-search"
    p.solve(p.objective, o)
    log = p.localSearchLog
    sig = [tuple((s["step"], None if s["objective"] is None else round(s["objective"], 2)) for s in e["steps"]) for e in log]
    times = [e["time"] for e in log]
    same_last = len(sig) >= 2 and sig[-1] == sig[-2] and not sig[-1][0][0].startswith("start: repair")
    print(case[5:-5], "iters", len(log), "times", times, "last two identical:", same_last,
          "repeat cost s:", times[-1] if same_last else 0, "total", round(sum(times), 1), flush=True)
