"""NJ stakes: FL / NY / NJ without and with the retirement exclusion, for a synthetic couple.

Couple born 1964-03-15 and 1964-09-15, life expectancies 89 and 92, SS $3,000 and $2,400/month at 70,
$300k taxable, $150k Roth, conservative rates, 60/40, maxSpending with no bequest.
Usage: nj_stakes.py exact|default|ls [tax-deferred in $k for each spouse, e.g. 900,600] [case;case...]
"exact": Medicare off, SS taxability pinned at 0.85. "default": the loops on. "ls": the loops on, then
upstream's local search over the tax breakpoints (breakpointMethod="local-search", 2026.10.6).
Lifetime state tax in today's dollars.
"""
import io
import sys
import time

import numpy as np

import owlplanner as owl
from owlplanner import tax_state

mode = sys.argv[1]
td = [float(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else [900.0, 600.0]
opts = {"bequest": 0}
if mode == "exact":
    opts.update({"withMedicare": "None", "withSSTaxability": 0.85})
elif mode == "ls":
    opts.update({"breakpointMethod": "local-search"})
only = sys.argv[3].split(";") if len(sys.argv) > 3 else None


def run(state, exclusion=True):
    orig = tax_state._read_exclusion_tiers
    if not exclusion:
        tax_state._read_exclusion_tiers = lambda entry: []
    try:
        p = owl.Plan(["Joe", "Jane"], ["1964-03-15", "1964-09-15"], [89, 92], "stakes",
                     verbose=False, logstreams=[io.StringIO()])
        p.setSpendingProfile("flat")
        p.setAccountBalances(taxable=[150, 150], taxDeferred=td, taxFree=[75, 75])
        p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
        p.setRates("conservative")
        p.setSocialSecurity([3000, 2400], [70, 70])
        p.setStateTax(state)
        t = time.time()
        p.solve("maxSpending", options=dict(opts))
        dt = time.time() - t
    finally:
        tax_state._read_exclusion_tiers = orig
    st = float(np.sum(p.st_T_n / p.gamma_n[:-1]))
    gap = "LP" if p.solverGap < 0 else f"{100 * p.solverGap:.2f}%"
    resid = sum(v["abs_sum"] for v in (getattr(p, "fixedPointResidual", None) or {}).values())
    return p.basis, st, dt, gap, p.caseStatus, resid, getattr(p, "breakpointMethodUsed", "")


label = f"${sum(td) / 1000:.1f}M"
for name, state, excl in (("FL", "FL", True), ("NY", "NY", True), ("NJ, no exclusion", "NJ", False),
                          ("NJ, exclusion", "NJ", True)):
    if only and name not in only:
        continue
    basis, st, dt, gap, status, resid, used = run(state, excl)
    print(f"| {label} | {name} | {basis:,.0f} | {st:,.0f} | {dt:.1f} s | {gap} | {resid:,.0f} | {used} |"
          + ("" if status == "solved" else f" {status}"))
    sys.stdout.flush()
