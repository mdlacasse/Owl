"""ACA optimize mode: is MAGI in a band where 9.96% x MAGI > SLCSP (below 400% FPL) feasible?"""
import io
import owlplanner as owl

def run(mode, slcsp):
    p = owl.Plan(["Cy"], ["1976-06-15"], [85], "aca", verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[0], taxFree=[50], startDate="01-01")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("user", values=[6, 4, 3, 2.5])
    p.setPension([4600], [45], indexed=[True])   # $54k/yr from now: MAGI ~ 340% FPL (single)
    p.setACA(slcsp)
    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85, "withACA": mode})
    out = (p.caseStatus, round(p.basis) if p.caseStatus == "solved" else None)
    if p.caseStatus == "solved":
        out += ([round(v) for v in p.aca_costs_n[1:4]], [round(v) for v in p.MAGI_aca_n[1:4]])
    return out

for s in (5.0, 9.0):
    print(f"SLCSP ${s}k  loop:", run("loop", s), "  optimize:", run("optimize", s))
