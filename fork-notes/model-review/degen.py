"""Construct a maxSpending plan in which late-year cash has zero value; check federal bracket fill order."""
import io
import numpy as np
import owlplanner as owl

p = owl.Plan(["Ann"], ["1961-03-15"], [90], "degen", verbose=False, logstreams=[io.StringIO()])
p.setSpendingProfile("flat")
p.setAccountBalances(taxable=[50], taxDeferred=[100], taxFree=[0], startDate="01-01")
p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
p.setRates("user", values=[6, 4, 3, 2.5])
p.setPension([12000], [70], indexed=[True])   # big pension from 70 (monthly)
p.setSocialSecurity([2500], [70])
p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
print("status", p.caseStatus, "basis", round(p.basis))
bad = []
for n in range(p.N_n):
    for t in range(1, p.N_t):
        if p.f_tn[t, n] > 1 and p.f_tn[t - 1, n] < p.DeltaBar_tn[t - 1, n] - 1:
            bad.append((int(p.year_n[n]), t, round(p.f_tn[t - 1, n]), round(p.DeltaBar_tn[t - 1, n]), round(p.f_tn[t, n])))
            break
print("years with out-of-order bracket fill:", len(bad))
for b in bad[:8]:
    print("  year %d: bracket %d has %s while bracket %d holds %s of %s" % (b[0], b[1], b[4], b[1] - 1, b[2], b[3]))
print("surplus years:", int(np.sum(p.s_n > 1)), " final bequest (today $):", round(p.bequest))
# tax the solver reports vs tax on the same income filled in order
ordered = 0.0; reported = 0.0
for n in range(p.N_n):
    G = p.f_tn[:, n].sum(); rem = G; tax = 0.0
    for t in range(p.N_t):
        x = min(rem, p.DeltaBar_tn[t, n]); tax += x * p.theta_tn[t, n]; rem -= x
    ordered += tax / p.gamma_n[n]; reported += p.T_n[n] / p.gamma_n[n]
print("lifetime federal ordinary tax, today $: reported %.0f, same income filled in order %.0f" % (reported, ordered))
