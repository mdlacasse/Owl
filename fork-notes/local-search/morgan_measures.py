import io, sys, time
from owlplanner.config.plan_bridge import config_to_plan
from owlplanner.config.toml_io import load_toml
def load():
    d, dn, _ = load_toml("Case_morgan.toml")
    return config_to_plan(d, dn, verbose=False, logstreams=[io.StringIO()], loadHFP=True)
for extra in ({}, {"withACA": "optimize"}):
    p = load(); o = dict(p.solverOptions); o.update(extra)
    t = time.time(); p.solve(p.objective, o); dt = time.time() - t
    g = p.gamma_n[:p.N_n]
    print(extra, p.caseStatus, f"t={dt:.1f}s basis={p.basis:,.0f} g0={p.g_n[0]:,.0f} g0/gamma0={p.g_n[0]/p.gamma_n[0]:,.0f}",
          f"yearFracLeft={p.yearFracLeft:.3f} ACA_today={(p.aca_costs_n/g).sum():,.0f}")
    from owlplanner import export
    d = export.build_summary_dic(p)
    for k, v in d.items():
        if "pending" in k.lower() or "spending" in k.lower():
            print("   ", k, v)
