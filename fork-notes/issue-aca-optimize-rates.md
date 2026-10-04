# Draft upstream issue (mdlacasse/Owl): withACA="optimize" charges each band its top rate, and disagrees with loop mode below 138% FPL

**Filed upstream by the user on 2026-10-04** (issue number not recorded yet). A design question, so no patch. Follows #161 (the infeasible band).

**Title:** `withACA="optimize"`: step contribution rates (each FPL band charged its final percentage) and a different rule than loop mode below 138% FPL

---

**1. Step rates.** In optimize mode, MAGI in FPL bracket `r` is charged `pct_r * MAGI`, where `pct_r` is the band's **final** percentage (`_ACA_LP_CONTRIB`, the 2026 values at 133, 150, 200, 250, 300 and 400% FPL). The statute's percentage rises linearly across each band, and loop mode (`acaCosts`, via `_aca_contrib_pct`) interpolates it. Inside a band the MILP therefore overcharges, by up to the band's rise: 2.41 points of MAGI just above 150% FPL, 1.84 just above 200%, 1.52 just above 250%. It also creates cliffs at the band edges that the statute does not have. The exact cost `(a_r + s_r MAGI) MAGI` is quadratic in MAGI inside a band, so the MILP can't take it exactly. Splitting each band into a few sub-bands with their own percentages would bound the error, at the price of more binaries.

**2. Below 138% FPL.** Loop mode charges the full SLCSP there, on the assumption that the household is on Medicaid (`acaCosts`: "Below 138% FPL: Medicaid territory; return full premium"). Optimize mode charges 2.10% of MAGI (the docstring of `_configure_ACA_binary_variables` notes this). The two modes cost the same income differently, and in non-expansion states neither is the rule. Either way, a Medicaid household would pay neither the SLCSP nor 2.10%: its premium is about zero.

**Repro** (on `dev`, `c1e5619`), from the repository root. A single filer born 1976, an indexed pension that pins MAGI, SLCSP $9k. Medicare off, SS taxability pinned.

```python
import io
import owlplanner as owl

def run(mode, pension):
    p = owl.Plan(["Cy"], ["1976-06-15"], [85], "aca", verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[0], taxFree=[50], startDate="01-01")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("user", values=[6, 4, 3, 2.5])
    p.setPension([pension], [45], indexed=[True])
    p.setACA(9.0)
    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85, "withACA": mode})
    fpl = 15_960 * p.gamma_n[1]
    return p.caseStatus, round(p.basis), round(p.aca_costs_n[1]), round(p.MAGI_aca_n[1]), p.MAGI_aca_n[1] / fpl

for pension in (1_650, 2_200, 3_000):
    for mode in ("loop", "optimize"):
        st, basis, cost, magi, r = run(mode, pension)
        print(f"pension ${pension:,}/mo {mode:8s} {st}  basis {basis:,}/yr  year-1 MAGI {magi:,} ({r:.0%} FPL)"
              f"  ACA cost {cost:,} ({cost / magi:.2%} of MAGI)")
```

```
pension $1,650/mo loop     solved  basis 23,031/yr  year-1 MAGI 22,938 (140% FPL)  ACA cost 685 (2.99% of MAGI)
pension $1,650/mo optimize solved  basis 24,817/yr  year-1 MAGI 22,880 (140% FPL)  ACA cost 959 (4.19% of MAGI)
pension $2,200/mo loop     solved  basis 30,193/yr  year-1 MAGI 29,641 (181% FPL)  ACA cost 1,688 (5.69% of MAGI)
pension $2,200/mo optimize solved  basis 30,027/yr  year-1 MAGI 29,638 (181% FPL)  ACA cost 1,956 (6.60% of MAGI)
pension $3,000/mo loop     solved  basis 37,665/yr  year-1 MAGI 39,467 (241% FPL)  ACA cost 3,204 (8.12% of MAGI)
pension $3,000/mo optimize solved  basis 37,564/yr  year-1 MAGI 39,466 (241% FPL)  ACA cost 3,331 (8.44% of MAGI)
```

At 181% and 241% FPL the MILP charges the band's final rate, 6.60% and 8.44%, where loop mode interpolates 5.69% and 8.12%. Optimize mode should be the exact one, but here it is the worse approximation. In the first case the year-1 MAGI is the same in both modes. Optimize nonetheless ends $1,786/yr **higher**. Income drifts below 138% FPL from the ninth year, as the taxable account is drawn down. From there loop mode charges the full SLCSP, $10,966 in that year and rising, while optimize charges 2.10%, $569 to $610 a year (per-year `aca_costs_n` from the same runs). Loop mode also has a cliff at 138% that its LP can't see: a household just above it pays about $700, and one just below pays the full premium. (At 140% FPL loop mode itself is low, 2.99% against the statute's 3.57%; that is the separate 133-150% band issue, `issue-aca-133-150.md`.)

**Questions for the maintainer.** For 1: are a few more breakpoints per band acceptable (the binaries are per year and only in pre-65 years)? For 2: which rule should both modes share below 138%? Options are a zero premium (Medicaid, for expansion states), 2.10% (no Medicaid), or a user setting.
