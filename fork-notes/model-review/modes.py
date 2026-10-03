"""Compare loop vs optimize modes on shipped examples; check bracket-fill order and fixed-point residual."""
import sys, time, glob, os, io
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "examples"))
from owlplanner.config.toml_io import load_toml  # noqa
from owlplanner.config.plan_bridge import config_to_plan  # noqa

def run(path, overrides):
    diconf, dirname, _ = load_toml(path)
    p = config_to_plan(diconf, dirname, verbose=False, logstreams=[io.StringIO()], loadHFP=True)
    opts = dict(p.solverOptions)
    opts.update(overrides); opts["maxTime"] = 60
    t = time.time()
    p.solve(p.objective, opts)
    dt = time.time() - t
    if p.caseStatus != "solved":
        return None
    obj = p.basis if p.objective == "maxSpending" else p.bequest
    # federal bracket order violations: some bracket t>0 has income while t-1 not full
    viol = 0
    for n in range(p.N_n):
        for t in range(1, p.N_t):
            if p.f_tn[t, n] > 1 and p.f_tn[t - 1, n] < p.DeltaBar_tn[t - 1, n] - 1:
                viol += 1
                break
    res = getattr(p, "fixedPointResidual", {})
    worst = max(res.items(), key=lambda kv: kv[1]["abs_sum"]) if res else ("-", {"abs_sum": 0})
    return obj, dt, viol, worst[0], worst[1]["abs_sum"], p.convergenceType, p.objective

families = ["withMedicare", "withSSTaxability"]
cases = sys.argv[1:] or sorted(glob.glob("Case_*.toml"))
for c in cases:
    allloop = {f: "loop" for f in families}
    base = run(c, allloop)
    if base is None:
        print(c, "all-loop not solved"); continue
    print(f"{c}: obj={base[6]} all-loop {base[0]:,.0f} t={base[1]:.1f}s orderViol={base[2]} resid[{base[3]}]={base[4]:,.0f} conv={base[5]}")
    for f in families:
        ov = dict(allloop); ov[f] = "optimize"
        r = run(c, ov)
        if r is None:
            print(f"   {f}=optimize: not solved"); continue
        print(f"   {f}=optimize: {r[0]:,.0f} ({r[0]-base[0]:+,.0f}) t={r[1]:.1f}s orderViol={r[2]} resid[{r[3]}]={r[4]:,.0f} conv={r[5]}")
    sys.stdout.flush()
