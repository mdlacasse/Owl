"""Assumption ladder: full Owl model, original case vs. progressively 'back-of-envelope' inputs.

L0 original case
L1 + OBBBA never expires (no scheduled bracket change)
L2 + deterministic rates: each asset class at the mean of the case's own rate series
L3 + no inflation: each class at its real mean, inflation 0 (all thresholds constant)
L4 + no gains, no interest, no dividends: every rate 0
L5 like L3 but every class at one common real return r_c = 0.6*stocks + 0.4*bonds, dividends 0
"""
import sys, time, glob, os, io, json
import numpy as np
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "examples"))
from owlplanner.config.toml_io import load_toml  # noqa
from owlplanner.config.plan_bridge import config_to_plan  # noqa


def load(path):
    diconf, dirname, _ = load_toml(path)
    return config_to_plan(diconf, dirname, verbose=False, logstreams=[io.StringIO()], loadHFP=True)


def solve(p, maxTime=120):
    opts = dict(p.solverOptions)
    opts["maxTime"] = maxTime
    t = time.time()
    p.solve(p.objective, opts)
    dt = time.time() - t
    if p.caseStatus != "solved":
        return None, dt
    return (p.basis if p.objective == "maxSpending" else p.bequest), dt


def rungs(path):
    p = load(path)
    tau = np.array(p.tau_kn)  # (4, N) decimals: stocks, corp bonds, T-notes, inflation
    mean = tau.mean(axis=1) * 100
    infl = mean[3]
    real = [(1 + m / 100) / (1 + infl / 100) * 100 - 100 for m in mean[:3]]
    rc = 0.6 * real[0] + 0.4 * real[1]
    out = {"case": os.path.basename(path), "objective": p.objective, "mean": mean.round(2).tolist(),
           "real": np.round(real, 2).tolist(), "rc": round(rc, 2)}
    steps = [
        ("L0", lambda q: None),
        ("L1", lambda q: q.setExpirationYearOBBBA(2099)),
        ("L2", lambda q: (q.setExpirationYearOBBBA(2099), q.setRates("user", values=mean.tolist()))),
        ("L3", lambda q: (q.setExpirationYearOBBBA(2099), q.setRates("user", values=real + [0.0]))),
        ("L4", lambda q: (q.setExpirationYearOBBBA(2099), q.setRates("user", values=[0.0] * 4), q.setDividendRate(0.0))),
        ("L5", lambda q: (q.setExpirationYearOBBBA(2099), q.setRates("user", values=[rc] * 3 + [0.0]), q.setDividendRate(0.0))),
    ]
    for name, fn in steps:
        q = load(path)
        fn(q)
        v, dt = solve(q)
        out[name] = None if v is None else round(v)
        out[name + "_t"] = round(dt, 2)
    return out


if __name__ == "__main__":
    cases = sys.argv[1:] or sorted(glob.glob("Case_*.toml"))
    for c in cases:
        print(json.dumps(rungs(c)), flush=True)
