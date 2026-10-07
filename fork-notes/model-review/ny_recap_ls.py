import io, sys
import numpy as np
import owlplanner as owl
p = owl.Plan(["Joe", "Jane"], ["1964-03-15", "1964-09-15"], [89, 92], "ny", verbose=False, logstreams=[io.StringIO()])
p.setSpendingProfile("flat")
p.setAccountBalances(taxable=[150, 150], taxDeferred=[1500, 1000], taxFree=[75, 75])
p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
p.setRates("conservative")
p.setSocialSecurity([3000, 2400], [70, 70])
p.setStateTax("NY")
p.solve("maxSpending", options={"bequest": 0, "breakpointMethod": "local-search"})
g = p.gamma_n[:p.N_n]
r = p.fixedPointResidual.get("state recapture", {}).get("abs_sum")
print(f"{sys.argv[1]:5} LS basis {p.basis:,.0f} used {p.breakpointMethodUsed} recapture {np.sum(getattr(p, 'st_recap_n', np.zeros(p.N_n))/g):,.0f} residual {r}")
