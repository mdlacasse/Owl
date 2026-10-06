import io, sys, time
import numpy as np
import owlplanner as owl
from owlplanner import plan as P
calls = []
orig = P.Plan._run_highs
def run(self, *a, **k):
    t = time.time()
    out = orig(self, *a, **k)
    calls.append((round(time.time() - t, 1), getattr(self, "_lastMipNodes", None), out[3] if len(out) > 3 else None,
                  "zx" in self.vm and bool(np.any(self.RXF_n >= 0.5))))
    return out
P.Plan._run_highs = run
td = [float(v) for v in sys.argv[1].split(",")]
extra = eval(sys.argv[2]) if len(sys.argv) > 2 else {}
p = owl.Plan(["Joe", "Jane"], ["1964-03-15", "1964-09-15"], [89, 92], "stakes", verbose=False, logstreams=[io.StringIO()])
p.setSpendingProfile("flat")
p.setAccountBalances(taxable=[150, 150], taxDeferred=td, taxFree=[75, 75])
p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
p.setRates("conservative")
p.setSocialSecurity([3000, 2400], [70, 70])
p.setStateTax("NJ")
t = time.time()
p.solve("maxSpending", options={"bequest": 0, **extra})
print(f"{td} {extra}: {time.time() - t:.0f}s basis {p.basis:,.0f} gap {p.solverGap} rx_fixed {p._rx_fixed is not None}")
for c in calls: print("   ", c)
