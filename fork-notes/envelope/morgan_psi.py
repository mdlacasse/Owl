"""morgan with SS taxability fixed (withSSTaxability=0.85) in both runs, so no loop on SS: default
loop vs pinned loop, and the residuals left in the other loop families (ACA, IRMAA, LTCG, NIIT)."""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa  (chdir to examples)
import seed  # noqa

p = compare.load("Case_morgan.toml")
opts = dict(p.solverOptions)
opts["maxTime"] = 300
opts["withSSTaxability"] = 0.85
t0 = time.time()
p.solve(p.objective, opts)
t = time.time() - t0
s = seed.em_seed(p, opts)
q = compare.load("Case_morgan.toml")
tq = seed.seeded_pinned_solve(q, dict(opts), s)
for name, P, tt in (("default", p, t), ("pinned", q, tq)):
    print(json.dumps({"plan": name, "psi": 0.85, "value": round(seed.value(P)), "conv": P.convergenceType,
                      "resid_nonSS": {k: round(v["abs_sum"]) for k, v in P.fixedPointResidual.items() if k != "SS"},
                      "t": round(tt, 2)}))
