"""Compare Owl's tracked gain fraction with one that adds taxed, reinvested dividends to basis."""
import io
import numpy as np
import owlplanner as owl

p = owl.Plan(["Bo"], ["1966-06-15"], [90], "basis", verbose=False, logstreams=[io.StringIO()])
p.setSpendingProfile("flat")
p.setAccountBalances(taxable=[1000], taxDeferred=[1000], taxFree=[0], startDate="01-01")
p.setCostBasis([500])
p.setAllocationRatios("individual", generic=[[[100, 0, 0, 0], [100, 0, 0, 0]]])
p.setRates("user", values=[7, 4, 3, 2.5])
p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
mu = p.mu
b = p.b_ijn[0, 0, :]; w = p.w_ijn[0, 0, :]; d = p.d_in[0, :]; k = p.kappa_ijn[0, 0, :]
K_owl = 500e3; K_true = 500e3
print(" year  balance  w_taxable  psi_owl  psi_with_divs  divs_taxed")
for n in range(12):
    psi_o = max(0, 1 - K_owl / b[n]) if b[n] > 0 else 0
    psi_t = max(0, 1 - K_true / b[n]) if b[n] > 0 else 0
    div = mu * (b[n] - w[n] + d[n] + 0.5 * k[n])
    print(f" {int(p.year_n[n])} {b[n]:9.0f} {w[n]:9.0f}   {psi_o:6.3f}   {psi_t:6.3f}   {div:8.0f}")
    frac = (1 - w[n] / b[n]) if b[n] > 0 else 0
    K_owl = K_owl * frac + k[n] + d[n]
    K_true = K_true * frac + k[n] + d[n] + div
print("Owl's own gain_fraction_in[0,:12]:", np.round(p.gain_fraction_in[0, :12], 3))
