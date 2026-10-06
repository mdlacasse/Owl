import io, sys, time
import numpy as np
import owlplanner as owl
from owlplanner import plan as P
cap = {}
orig = P.Plan._aggregateResults
def agg(self, x, short=False):
    cap["x"] = np.array(x, dtype=float)
    return orig(self, x, short)
P.Plan._aggregateResults = agg
method = sys.argv[1]
p = owl.Plan(["Joe", "Jane"], ["1964-03-15", "1964-09-15"], [89, 92], "stakes", verbose=False, logstreams=[io.StringIO()])
p.setSpendingProfile("flat")
p.setAccountBalances(taxable=[150, 150], taxDeferred=[900, 600], taxFree=[75, 75])
p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
p.setRates("conservative")
p.setSocialSecurity([3000, 2400], [70, 70])
p.setStateTax("NJ")
opts = {"bequest": 0}
if method != "loop":
    opts["breakpointMethod"] = method
t = time.time(); p.solve("maxSpending", options=opts); dt = time.time() - t
x = cap["x"]
zx = p.vm["zx"].extract(x)
frac = np.abs(zx - np.round(zx))
print(f"{method}: {dt:.0f}s basis {p.basis:,.0f} used {p.breakpointMethodUsed}; zx max fractionality {frac.max():.3f}")
for n in np.where(frac.max(axis=1) > 1e-6)[0]:
    print("  year", int(p.year_n[n]), "zx", np.round(zx[n], 3), "st_agi", round(p._state_agi_and_ti()[0][n]), "rx", round(p.st_rx_n[n]))
# statutory exclusion vs claimed
agi = p._state_agi_and_ti()[0]
print("rx claimed today's $:", round(float((p.st_rx_n / p.gamma_n[:p.N_n]).sum())))
