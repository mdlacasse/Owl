# Draft upstream issue (mdlacasse/Owl): paper and docs, loop mode is self-consistent not optimal, and paper vs code drift

**Not filed yet.** Documentation only. No code change is proposed, except possibly the defaults question at the end.

**Title:** Paper: say that loop mode returns a self-consistent plan, not an optimal one; correct places where the text no longer matches the code

---

**1. Loop mode returns a fixed point, not an optimum.** Chapter 3 ("The Self-Consistent Iteration Loop") presents the loop as resolving the nonlinear terms. Each iteration optimizes with the lagged quantities held constant, then recomputes them. At the fixed point the plan charges itself the right IRMAA, SS tax, NIIT, ACA premium and LTCG room, but the LP never sees their **marginal** cost. IRMAA cliffs and the premium-credit phase-out are invisible when choosing conversions. So is the SS "tax torpedo": taxable SS enters `_add_taxable_income` as the constant `Psi_n * zetaBar`, so a dollar of other income is charged its bracket rate and not the 1.5x or 1.85x it really costs. The same holds for the 3.8% NIIT, the OBBBA senior-deduction phase-out and the LTCG stacking room. A fixed point of this map is optimal only where the derivatives of the lagged terms are zero.

Measured on the shipped examples, all loop vs. one family switched to `"optimize"` (`maxTime=60` per MILP). This was run on a fork at upstream `dev` `a85ff76`. The fork's additions are opt-in except its NY benefit recapture, which applies to the two NY examples, cameron and robin. Those two were rerun on stock `dev` `c1e5619` and gave identical figures (cameron +0/+0, robin +0/+96). Objective: spending basis $/yr, or bequest $, today's dollars.

| Case | Objective | All loop | Medicare optimize | SS taxability optimize |
|---|---|---:|---:|---:|
| alex+jamie | spending | 228,574 | +1,229 | +111 |
| chris+pat | spending | 116,916 | +40 | +76 (max iterations) |
| jack+jill | spending | 102,577 | +0 | +208 |
| joe | spending | 93,044 | +374 | +121 (max iterations) |
| jordan+taylor | bequest | 1,530,120 | +19,368 | +0 |
| kim+sam-bequest | bequest | 1,917,624 | +2,504 | +9,124 |
| kim+sam-spending | spending | 185,393 | +27 | +219 |
| morgan | spending | 37,920 | +0 | +866 |
| robin | spending | 44,070 | +0 | +96 |

bill, cameron, dana and john+sally gave +0 in what was run. devon, helen+ruth, jon+jane and jordan+taylor-qcd were not run. No delta was negative. The largest are +1.3% of bequest (jordan+taylor, IRMAA) and +2.3% of spending (morgan, SS taxability). Medicare optimize took 0.1-62 s; SS-taxability optimize took up to 30 minutes, which is too slow for a default.

Suggested text: loop mode returns a self-consistent plan whose own income agrees with the costs it was charged, but it may leave value on the table where a cliff or phase-out sits near the plan's income. The `"optimize"` flags price those marginal costs exactly, at the cost of binaries. Whether `withMedicare` should default to `"optimize"` given these timings is a question for you.

**2. Taxable bond and cash returns.** `_add_taxable_income` taxes `max(0, tau_k)` of bonds and cash held in taxable accounts each year as ordinary income. That is total return, price changes included, so negative years are ignored. Under variable rates (historical, Monte Carlo) this overtaxes: `E[max(0, tau)] > E[tau]`, and price gains are taxed before any sale. Under constant rates the effect is small. Eq. Tx2 in the paper uses `tau_kn` and omits the clip. Worth stating as an assumption.

**3. Plan year is today's calendar year.** `_setStartingDate` ignores the year, and ages, RMD start, FRA and tax-year logic follow `date.today()`. The same case file gives different results after January 1, and a pinned seed reproduces the rates but not the plan. `info/PARAMETERS.md` documents this; the paper's assumptions don't.

**4. Paper vs code drift** (`papers/owl.tex` on `dev`):

| Paper | Code | Note |
|---|---|---|
| Roth cap: Ch. 5 per person; Ch. 7 "applied to the combined conversions" | per person (`_add_roth_conversion_constraints`) | Ch. 7 wrong |
| IRMAA MAGI expansion, Eqs. MedDecomp2/3 and rows `J_3`: `-e_(n-2)` and income terms with flipped signs | income before the exemption, no `e` term ("Subtracting e here as well would add it a second time") | paper wrong, code right |
| Eq. (PI): `Pi = MAGI - SS/2` with the AGI-basis MAGI (taxable SS only) | `MAGI_aca_n - SS/2` (full SS) | the intermediate-variables section is right; Eq. (PI) is not |
| "Adding binary variables z^x ... always contributes 4N_n binaries"; "coupled with binary variables excluding ..." | AMO binaries removed; post-solve repair (`amorepair.py`) | stale |
| MIP decomposition, sequential and Benders, "certified global optimum" (Sec. 3.9; table "benders_cut") | `withDecomposition` retired (`84811f1`, 2026-09-26) | stale |
| Big-M "about 10^8"; `M_n = 3 B20` for LTCG/NIIT | per-year ceilings from the portfolio plus fixed income (`_incomeCeiling`) | stale |
| Ch. 11: "survivor benefit assumed claimed in the year of death" | `survivor_claim_age` setting (Ch. 2 describes it) | Ch. 11 stale |
| Lexicographic term: `+eps` on `x` and spouse-1 withdrawals | `eps*(1+n)` on `x`; also on `w_i2n` and `s_n`; `1e-4` on `tss` | incomplete |
| Eq. Tx2: taxable-account interest uses `tau_kn` | `max(0, tau_kn)` | paper omits the clip |
| Stochastic spending scenarios "drawn from the calibrated multivariate lognormal model" | any configured rate model | imprecise |
| Ch. 10 longevity: "life expectancy set to the drawn last-survivor horizon" | each person's drawn age is passed to `clone` | code more correct than text |
| CVaR relation and "efficient frontier" | the commitment LP's optimum is the empirical quantile of the scenario bases at level `1/Lambda`, and each is a perfect-foresight optimum | the framing overstates |

These were found reading the 2026 `owl.tex` against the code at `a85ff76`, and are cited by equation label.
