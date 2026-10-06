"""NY couple of nj_stakes.py: spending basis, lifetime state tax and recapture (today's $). Usage: ny_recap_cmp.py LABEL (set PYTHONPATH to the checkout to test)."""
import io, sys
import numpy as np
import owlplanner as owl
for td in ([900.0, 600.0], [1500.0, 1000.0]):
    for mode in ("exact", "default"):
        opts = {"bequest": 0}
        if mode == "exact":
            opts.update({"withMedicare": "None", "withSSTaxability": 0.85})
        p = owl.Plan(["Joe", "Jane"], ["1964-03-15", "1964-09-15"], [89, 92], "ny", verbose=False, logstreams=[io.StringIO()])
        p.setSpendingProfile("flat")
        p.setAccountBalances(taxable=[150, 150], taxDeferred=td, taxFree=[75, 75])
        p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
        p.setRates("conservative")
        p.setSocialSecurity([3000, 2400], [70, 70])
        p.setStateTax("NY")
        p.solve("maxSpending", options=opts)
        g = p.gamma_n[:p.N_n]
        rec = getattr(p, "st_recap_n", np.zeros(p.N_n))
        r = (getattr(p, "fixedPointResidual", {}) or {}).get("state recapture", {}).get("abs_sum")
        print(f"{sys.argv[1]:6} ${sum(td)/1000:.1f}M {mode:7} basis {p.basis:>9,.0f}  state tax {np.sum(p.st_T_n/g):>8,.0f}"
              f"  recapture {np.sum(rec/g):>6,.0f}  recap residual {r}", flush=True)
