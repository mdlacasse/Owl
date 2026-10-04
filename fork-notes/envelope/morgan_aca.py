"""Where Owl's default loop and the EM-pinned loop put morgan's MAGI relative to the ACA's FPL
bands, and what ACA costs each pays (Owl's own MAGI_aca_n and aca_costs_n)."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa  (chdir to examples)
from owlplanner import tax_federal as tx  # noqa
import seed  # noqa

p = compare.load("Case_morgan.toml")
opts = dict(p.solverOptions)
opts["maxTime"] = 300
p.solve(p.objective, opts)
s = seed.em_seed(p, opts)
q = compare.load("Case_morgan.toml")
seed.seeded_pinned_solve(q, dict(opts), s)
for name, P in (("default", p), ("pinned", q)):
    rows = []
    for n in range(P.N_n):
        if P.aca_costs_n[n] <= 0 and P.MAGI_aca_n[n] <= 0:
            continue
        cy = int(P.year_n[n])
        fpl = tx._ACA_FPL[cy if cy in tx._ACA_FPL else max(tx._ACA_FPL)][0] * P.gamma_n[n]
        rows.append({"year": cy, "fpl_pct": round(100 * P.MAGI_aca_n[n] / fpl),
                     "aca_today": round(P.aca_costs_n[n] / P.gamma_n[n])})
    print(json.dumps({"plan": name, "value": round(seed.value(P)), "conv": P.convergenceType,
                      "aca_total_today": round(float((P.aca_costs_n / P.gamma_n[:P.N_n]).sum())), "years": rows}))
