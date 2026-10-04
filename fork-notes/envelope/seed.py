"""Seed Owl's self-consistent loop with the one-state EM's plan.

The loop starts from Psi = 0.85 and zero Medicare, ACA and NIIT costs (_computeNLstuff(None)).
Here its first LP instead gets the values implied by the EM's plan: Psi_n, IRMAA premiums M_n,
ACA costs ACA_n and NIIT J_n computed from the EM's MAGI path with Owl's own functions. Only
the starting point changes; the loop then runs as usual.

Compared on the original cases: default loop vs seeded loop (value, iterations, time).
The EM reads its exogenous inputs from a plan solved once by default (inputs do not depend on
the solution), so the timing of the EM is reported separately.
"""
import sys, glob, os, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa  (chdir to examples)
from owlplanner import utils as u  # noqa
from owlplanner import tax_federal as tx  # noqa
import em  # noqa

PHI1 = compare.PHI1
# pin band around the EM's recognition, in EM grid steps below and above
BAND = tuple(float(v) for v in os.environ.get("EM_BAND", "1,1").split(","))


def em_seed(p, opts):
    """One-state EM plan and the loop parameters it implies."""
    inp = em.inputs(p, opts)
    kw = (dict(bequest=u.get_monetary_option(opts, "bequest", 1) if "bequest" in opts else 1.0)
          if p.objective == "maxSpending" else dict(netSpending=u.get_monetary_option(opts, "netSpending", 1)))
    t = time.time()
    r = em.solve_dp(inp, taxable=False, penalty=True, **kw)
    t_em = time.time() - t
    N = inp["N"]
    parts = {}
    for n in range(N):
        em.row_cost(inp, n, np.array([r["x"][n]]), parts=parts)
    agi = np.array([parts["agi"][n][0] for n in range(N)])
    tss = np.array([parts["tss"][n][0] for n in range(N)])
    niit = np.array([parts["niit"][n][0] for n in range(N)])
    ss = inp["ss"]
    psi = np.where(ss > 0, tss / np.maximum(ss, 1e-9), 0.85)
    M = tx.mediCosts(p.yobs, p.horizons, agi, p.prevMAGI, p.gamma_n[:-1], p.N_n,
                     include_part_d=getattr(p, "_include_medicare_part_d", True),
                     part_d_base_annual_per_person=getattr(p, "_medicare_part_d_base_annual_per_person", 0.0))
    aca = np.zeros(N)
    if p.slcsp_annual > 0:
        n0 = max(0, p.aca_start_year - int(p.year_n[0])) if p.aca_start_year > 0 else 0
        aca = tx.acaCosts(p.yobs, p.horizons, agi + (ss - tss), p.gamma_n[:-1], p.slcsp_annual, p.N_n, n_aca_start=n0)
    return dict(Psi_n=psi, M_n=M, ACA_n=aca, J_n=niit, em=r["value"], t_em=t_em, x=r["x"], h=r["h"] / inp["d"][:N])


def seeded_solve(p, opts, seed):
    """Solve p with the loop started from seed (None: Owl's default start). Returns (time, LPs)."""
    orig = p._computeNLstuff
    count = [0]

    def nl(x, includeMedicare, fixedPsi=None):
        orig(x, includeMedicare, fixedPsi=fixedPsi)
        if x is not None:
            count[0] += 1
        elif seed is not None:
            if fixedPsi is None and "tss" not in getattr(p, "vm", {}):
                p.Psi_n = seed["Psi_n"].copy()
            if includeMedicare:
                p.M_n = seed["M_n"].copy()
            if p.slcsp_annual > 0 and not getattr(p, "_aca_lp", False):
                p.ACA_n = seed["ACA_n"].copy()
            if not getattr(p, "_niit_lp", False):
                p.J_n = seed["J_n"].copy()
    p._computeNLstuff = nl
    t = time.time()
    p.solve(p.objective, opts)
    return time.time() - t, count[0]


def pinned_solve(p, opts, seed):
    """Solve p with each year's tax-deferred recognition (withdrawals + conversions) held within
    one EM grid step of the EM's plan: Owl's exact accounting of the EM's schedule."""
    orig = p._add_roth_maturation_constraints

    def rows():
        orig()
        for n in range(p.N_n):
            row = p.A.newRow()
            for i in range(p.N_i):
                row.addElem(p.vm["w"].idx(i, 1, n), 1)
                row.addElem(p.vm["x"].idx(i, n), 1)
            xn, hn = float(seed["x"][n]), float(seed["h"][n])
            p.A.addRow(row, max(0.0, xn - BAND[0] * hn), xn + BAND[1] * hn, tag=("em_pin", n))
    p._add_roth_maturation_constraints = rows
    t = time.time()
    p.solve(p.objective, opts)
    return time.time() - t


def seeded_pinned_solve(p, opts, seed):
    """Pinned as above, with the loop also started from the EM plan's own Psi, IRMAA, ACA and NIIT
    (seeded_solve): the first LP then charges the costs of the schedule it is pinned to."""
    orig = p._add_roth_maturation_constraints

    def rows():
        orig()
        for n in range(p.N_n):
            row = p.A.newRow()
            for i in range(p.N_i):
                row.addElem(p.vm["w"].idx(i, 1, n), 1)
                row.addElem(p.vm["x"].idx(i, n), 1)
            xn, hn = float(seed["x"][n]), float(seed["h"][n])
            p.A.addRow(row, max(0.0, xn - BAND[0] * hn), xn + BAND[1] * hn, tag=("em_pin", n))
    p._add_roth_maturation_constraints = rows
    t, _ = seeded_solve(p, opts, seed)
    return t


def resid(p):
    return round(sum(v["abs_sum"] for v in getattr(p, "fixedPointResidual", {}).values()))


def value(p):
    if p.caseStatus != "solved":
        return None
    return p.basis if p.objective == "maxSpending" else p.bequest


def one(path):
    out = {"case": os.path.basename(path)[5:-5]}
    if PHI1:
        out["phi1"] = True
    p = compare.load(path)
    if PHI1:
        p.setBeneficiaryFractions([1, 1, 1, 1])
    opts = dict(p.solverOptions)
    opts["maxTime"] = 120
    td, nd = seeded_solve(p, dict(opts), None)
    out.update(default=round(value(p)), lps_default=nd, conv_default=p.convergenceType, resid_default=resid(p),
               t_default=round(td, 2))
    seed = em_seed(p, opts)
    q = compare.load(path)
    if PHI1:
        q.setBeneficiaryFractions([1, 1, 1, 1])
    ts, ns = seeded_solve(q, dict(opts), seed)
    v = value(q)
    out.update(seeded=None if v is None else round(v), lps_seeded=ns, conv_seeded=q.convergenceType,
               resid_seeded=resid(q), t_seeded=round(ts, 2),
               em=round(seed["em"]), t_em=round(seed["t_em"], 3))
    out["seeded_vs_default_pct"] = None if v is None else round(100 * (v - out["default"]) / abs(out["default"]), 2)
    r = compare.load(path)
    if PHI1:
        r.setBeneficiaryFractions([1, 1, 1, 1])
    tp = pinned_solve(r, dict(opts), seed)
    v = value(r)
    out.update(pinned=None if v is None else round(v), status_pinned=r.caseStatus, conv_pinned=r.convergenceType,
               resid_pinned=resid(r), t_pinned=round(tp, 2))
    out["pinned_vs_default_pct"] = None if v is None else round(100 * (v - out["default"]) / abs(out["default"]), 2)
    r = compare.load(path)
    if PHI1:
        r.setBeneficiaryFractions([1, 1, 1, 1])
    tp = seeded_pinned_solve(r, dict(opts), seed)
    v = value(r)
    out.update(seeded_pinned=None if v is None else round(v), status_seeded_pinned=r.caseStatus,
               conv_seeded_pinned=r.convergenceType, resid_seeded_pinned=resid(r), t_seeded_pinned=round(tp, 2))
    out["seeded_pinned_vs_default_pct"] = (None if v is None else
                                           round(100 * (v - out["default"]) / abs(out["default"]), 2))
    return out


if __name__ == "__main__":
    cases = sys.argv[1:] or sorted(glob.glob("Case_*.toml"))
    for c in cases:
        print(json.dumps(one(c)), flush=True)
