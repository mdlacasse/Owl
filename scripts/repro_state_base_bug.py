"""Minimal repro: state tax base understates by the federal standard deduction."""
import logging
logging.disable(logging.CRITICAL)
import numpy as np
from owlplanner import Plan

p = Plan(["Jack"], ["1960-01-01"], [90], "ReproNY")
p.setStateTax("NY")
p.setAccountBalances(taxable=[0], taxDeferred=[500], taxFree=[0])
p.setSocialSecurity([2000], [67])
p.setRates("conservative")
p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]]))
p.setSpendingProfile("flat")
p.other_inc_in[0, :] = 60_000.0
p.solve("maxSpending", options={"verbose": False, "noRothConversions": "Jack"})

n = 0
e_n = p.e_n[n]
G_n = p.G_n[n]
Q_n = p.Q_n[n]
psi = p.Psi_n[n]
zeta = float(np.sum(p.zetaBar_in[:, n]))
ss_taxable = psi * zeta
pe_adj = float(np.sum(np.minimum(p.piBar_in[:, n], p.st_pe_cap_in[:, n])))
st_re = float(np.sum(p.st_re_in[:, n]))
sigma = p.st_sigmaBar_n[n]
lp_ti = float(np.sum(p.st_f_tn[:, n]))

agi = e_n + G_n + Q_n
new_ti = agi - ss_taxable - pe_adj - sigma - st_re
old_ti = (G_n + Q_n) - ss_taxable - pe_adj - sigma - st_re

# Correct graduated NY Single 2026 tax (brackets: [lower_start, rate])
brackets = [
    (0.0, 0.039), (8500.0, 0.044), (11700.0, 0.0515), (13900.0, 0.054),
    (80650.0, 0.059), (215400.0, 0.0685), (1077550.0, 0.0965),
]
def ny_tax(ti):
    tax = 0.0
    for i, (lower, rate) in enumerate(brackets):
        upper = brackets[i + 1][0] if i + 1 < len(brackets) else float("inf")
        if ti <= lower:
            break
        width = min(ti, upper) - lower
        tax += width * rate
    return tax

old_tax = ny_tax(max(old_ti, 0))
new_tax = ny_tax(max(new_ti, 0))

print(f"e_n (fed std deduction)   = {e_n:>12,.2f}")
print(f"G_n (fed ordinary income) = {G_n:>12,.2f}")
print(f"AGI = e_n + G_n + Q_n     = {agi:>12,.2f}")
print(f"st_sigmaBar (NY std ded)  = {sigma:>12,.2f}")
print(f"st_re (retirement excl)   = {st_re:>12,.2f}")
print()
print(f"OLD state taxable (fed TI)= {old_ti:>12,.2f}")
print(f"NEW state taxable (AGI)   = {new_ti:>12,.2f}")
print(f"LP st_f sum               = {lp_ti:>12,.2f}")
print(f"Understatement            = {new_ti - old_ti:>12,.2f}  (= e_n)")
print()
print(f"OLD NY tax                = {old_tax:>12,.2f}")
print(f"NEW NY tax                = {new_tax:>12,.2f}")
print(f"LP st_T_n[0]              = {p.st_T_n[0]:>12,.2f}")
print(f"Tax understatement        = {new_tax - old_tax:>12,.2f}")
