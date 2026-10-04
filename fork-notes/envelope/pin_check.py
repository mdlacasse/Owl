"""Run the one-state EM's schedule through Owl and account for the difference.

For each case: Owl's default plan; the EM's optimum (value em) and its schedule; Owl pinned to
that schedule, loop seeded from it (pinned: Owl's exact accounting of it, every Owl constraint kept); the EM's
accounting of the pinned plan, without (acct0) and with (acct) the taxable-account income and
penalties Owl booked for it. em - acct0 is how much the EM's own schedule is worth less once
Owl's constraints bind; acct0 - acct is the tax inside the taxable account along it.

EM_OPTS='{"withSSTaxability": 0.85, "withMedicare": "None"}' makes Owl a single exact LP.
"""
import sys, glob, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa  (chdir to examples)
from owlplanner import utils as u  # noqa
import em  # noqa
import seed  # noqa

EXTRA = json.loads(os.environ.get("EM_OPTS", "{}"))


def one(path):
    p = compare.load(path)
    if compare.PHI1:
        p.setBeneficiaryFractions([1, 1, 1, 1])
    opts = dict(p.solverOptions)
    opts.update(EXTRA)
    opts["maxTime"] = 300
    p.solve(p.objective, opts)
    full = seed.value(p)
    kw = (dict(bequest=u.get_monetary_option(opts, "bequest", 1) if "bequest" in opts else 1.0)
          if p.objective == "maxSpending" else dict(netSpending=u.get_monetary_option(opts, "netSpending", 1)))
    s = seed.em_seed(p, opts)
    q = compare.load(path)
    if compare.PHI1:
        q.setBeneficiaryFractions([1, 1, 1, 1])
    seed.seeded_pinned_solve(q, dict(opts), s)
    out = {"case": os.path.basename(path)[5:-5], "phi1": compare.PHI1, "opts": EXTRA, "objective": p.objective,
           "full": round(full), "em": round(s["em"]), "pinned": None, "status_pinned": q.caseStatus,
           "conv_pinned": q.convergenceType, "resid_pinned": seed.resid(q)}
    if q.caseStatus == "solved":
        inp = em.inputs(q, opts)
        xq = q.w_ijn[:, 1, :].sum(axis=0) + q.x_in.sum(axis=0)
        eo, eq, pen = em.owl_extras(q)
        a0 = em.evaluate(inp, None, xq, pen=pen, **kw)["value"]
        a1 = em.evaluate(inp, None, xq, eo=eo, eq=eq, pen=pen, **kw)["value"]
        out.update(pinned=round(seed.value(q)), acct0=round(a0), acct=round(a1))
    return out


if __name__ == "__main__":
    for c in sys.argv[1:] or sorted(glob.glob("Case_*.toml")):
        print(json.dumps(one(c)), flush=True)
