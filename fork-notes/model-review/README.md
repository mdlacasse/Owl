# Owl model review: paper and implementation (2026-10-03)

Fork-only note. Scope: the mathematical model in `papers/owl.tex` (2026 edition, the source of `owl.pdf`) and its implementation in `src/owlplanner/plan.py`, `tax_federal.py`, `socialsecurity.py`, `tax_state.py` and `stresstests.py`, at branch `claude/optimistic-darwin-n5xykl` (= `claude/relaxed-turing-xzrv89` @ `024ac26`, upstream `dev` @ `a85ff76`).

Evidence labels used below:

- **[run]**: reproduced by a script in this directory; output pasted from a real run.
- **[code]**: read in the source; line numbers given.
- **[recalled]**: from memory of the rule, not checked against a primary source in this session (ssa.gov and ecfr.gov are blocked by the proxy).

Almost everything below is upstream code, not fork additions. Fork additions are marked where they are affected.

## 1. The architecture in one paragraph

One LP/MILP per solve over annual periods, with all account flows at the start of the year (contributions at mid-year), accounts rebalanced to prescribed allocations so that only per-account balances are variables, and a fixed spending profile tying every year's spending to year 0. Progressive taxes are bracket-fill variables (`f`, `st_f`, `q`): a relaxation that is tight only because the objective prices tax. Everything nonlinear in income goes one of two ways. It is either a constant taken from the previous iterate, in a self-consistent (SC) loop: SS taxable share, IRMAA, NIIT, ACA, LTCG bracket room, the OBBBA senior-deduction phase-out, cost-basis gain fractions, NY recapture, spousal and survivor SS. Or it becomes an exact MILP family under an `"optimize"` flag. Every flag defaults to the loop.

## 2. Findings, in order of weight

### 2.1 In loop mode the result is a fixed point, not an optimum [code, run]

The paper (Ch. 3, "The Self-Consistent Iteration Loop") presents the loop as resolving the nonlinearity. The loop actually iterates "optimize with these costs held constant, then recompute the costs". At its fixed point the plan charges itself the right IRMAA, SS tax, NIIT and so on, but the LP never sees their **marginal** cost:

- IRMAA cliffs and the ACA premium-credit phase-out are invisible when choosing conversions;
- the SS "tax torpedo" (taxable SS rising with other income, so a marginal rate of 1.5x or 1.85x the bracket) is invisible, because taxable SS enters `_add_taxable_income` as the constant `Psi_n * zetaBar` (`plan.py:3417`);
- the same holds for the 3.8% NIIT, the 6% OBBBA phase-out slope, the LTCG stacking room (`plan.py:3752`), and in the fork NY recapture.

A fixed point of this map is an equilibrium between the optimizer and the tax function. It is optimal only if the derivatives of the lagged terms are zero. Measured on shipped examples with every family in loop mode, then one family switched to `"optimize"` (`modes.py`, `maxTime=60` per MILP):

Objective: spending basis in $/yr or bequest in $, both today's dollars. Deltas are optimize minus all-loop. "Residual" is the loop plan's largest `fixedPointResidual` family, summed over the horizon. Raw output: `modes_results.txt`.

| Case | Objective | All loop | Medicare optimize | SS taxability optimize | Loop residual | Loop exit |
|---|---|---:|---:|---:|---|---|
| alex+jamie | spending | 228,574 | +1,229 (62 s) | +111 (240 s) | SS $1,045 | oscillatory |
| bill | spending | 34,231 | +0 | +0 | 0 | monotonic |
| cameron | spending | 18,996 | +0 | +0 | SS $29,773 | 2-cycle |
| chris+pat | spending | 116,916 | +40 | +76 (1,800 s, max iterations) | SS $1,459 | oscillatory |
| dana | spending | 80,919 | +0 | not run | $2 | monotonic |
| jack+jill | spending | 102,577 | +0 | +208 (1,200 s) | SS $4,952 | 2-cycle |
| joe | spending | 93,044 | +374 | +121 (1,800 s, max iterations) | 0 | oscillatory |
| john+sally | bequest | 16,803 | +0 | not run | 0 | oscillatory |
| jordan+taylor | bequest | 1,530,120 | +19,368 (40 s) | +0 | 0 | monotonic |
| kim+sam-bequest | bequest | 1,917,624 | +2,504 | +9,124 (660 s) | SS $814 | oscillatory |
| kim+sam-spending | spending | 185,393 | +27 | +219 (240 s) | SS $1,650 | oscillatory |
| morgan | spending | 37,920 | +0 | +866 (300 s) | SS $1,553 | oscillatory |
| robin | spending | 44,070 | +0 | +96 (81 s) | SS $992 | monotonic |

Not covered: devon, helen+ruth, jon+jane, jordan+taylor-qcd, and SS-optimize for dana and john+sally. I stopped the runs, because one SS-optimize case takes up to 30 minutes (60 s per MILP times up to 30 iterations). No delta is negative. The largest are +1.3% of bequest (jordan+taylor, IRMAA), +2.3% of spending (morgan, SS taxability) and +0.5% (alex+jamie, IRMAA). Times are wall-clock with three runs in parallel.

The default setting therefore leaves value on the table, and the size varies from case to case. The paper should say plainly that loop mode gives a self-consistent plan, not an optimal one. The fork already acted on this for NJ, putting the exclusion into the MILP after a loop version 2-cycled. The NY recapture decision (loop, zero measured regret on a conversion-cap grid) is consistent with it.

### 2.2 A loop that does not converge returns its most optimistic iterate [code]

On a detected cycle, `_check_cycle` keeps the iterate with the **highest objective** (`plan.py:4782`). On stagnation, max iterations, or an unsolvable step, `_pick_best_valid_index` does the same (`plan.py:4742`). In a 2-cycle, the higher-objective iterate is typically the one whose LP was built with the lower lagged costs, so the selection is biased toward plans that undercharge themselves. `fixedPointResidual` measures the inconsistency and logs it, but nothing uses it to choose. In the examples, `Case_cameron` ends in a 2-cycle whose accepted plan is off by $29,773 of SS tax over the horizon ($42,229 with Medicare optimized), and `Case_jack+jill` by $4,952 (table above).

Suggestion: among the iterates in the cycle, pick the one with the smallest fixed-point residual, or re-solve once with the cycle's averaged parameters. At minimum, show the residual next to the objective in the summary.

### 2.3 Bracket fill is wrong in years where cash has no marginal value [run] — fixed 2026-10-04

**Fix:** the loop prices tax at `TAX_TIEBREAK` (1e-4 per today's dollar) from the first iterate that fills a year out of order. An accepted final LP that first goes out of order is re-solved with spending pinned (`_repairBracketOrder`). `_check_bracket_order` warns and sets `bracketOrderExcess`. Always-on pricing was tried and rejected: it moved two examples' fixed points (morgan +1.5% spending, john+sally -4% bequest) though neither was out of order. At `EPSILON` (5e-7) the fill stayed wrong, since those reduced costs sit at HiGHS's dual tolerance. After the fix `degen.py` gives 0 out-of-order years, reported tax $887,113 = filled in order, bequest $2,912,759, spending unchanged at $31,580, and the loop converges in 3 iterations. Before, it stopped on a false 2-cycle with an LTCG residual of $10,413. All 17 examples are unchanged. Tests: `tests/plan/test_bracket_order.py`. Upstream draft: `fork-notes/issue-bracket-order.md`.


The `f_tn` bracket variables are tight only when the year's cash carries a positive shadow price. In a liquidity-constrained `maxSpending` plan, the early years bind spending. Late-year income above spending then becomes surplus that ends in a bequest above its floor, and it is worth nothing to the objective. The solver may then fill brackets in any order. `degen.py` (single, $150k saved, a $144k/yr indexed pension and SS from 70):

```
status solved basis 31580
years with out-of-order bracket fill: 21
  year 2031: bracket 6 has 163734 while bracket 5 holds 0 of 434885
  year 2032: bracket 6 has 206319 while bracket 5 holds 0 of 2667
  ...
surplus years: 21  final bequest (today $): 2020040
lifetime federal ordinary tax, today $: reported 1558338, same income filled in order 911265
```

The objective is unaffected, but the reported taxes, bequest and the Taxes sheet are wrong by $647k (today's $). No post-solve check exists: `grep` finds only the LTCG "may be degenerate" warning (`plan.py:6249`). None of the 13 examples run triggers it (`orderViol=0` in every run of `modes_results.txt`). The paper describes this pathology in the context of the withdrawn `fixedSpending` option, but it is not limited to that option. Fix candidates:

- a lexicographic epsilon on total tax (always consistent with the primary objective);
- a post-solve check that re-fills brackets in order, or re-solves with tax minimized while the objective is pinned.

### 2.4 `withACA="optimize"` is not exact and can make feasible cases infeasible [code, run] — infeasible band fixed 2026-10-04

**Fix (band only):** `tx._aca_capped_limits` clips the bracket thresholds at the first MAGI where `pct_r x MAGI` reaches the SLCSP. Contributions only rise with the bracket, so every higher income pays the full premium, which is the last bracket's cost. Brackets left with zero width get their binary fixed to 0. `aca.py` now solves in optimize mode with the full premium ($5,125), identical to loop mode. Tests: `TestACAOptimize::test_capped_limits_*` and `test_income_where_contribution_exceeds_premium_is_feasible`. Upstream draft: `fork-notes/issue-aca-optimize-infeasible.md`. **Still open:** top-of-bracket step rates; the <138% FPL disagreement with loop mode (drafted: `fork-notes/issue-aca-optimize-rates.md`); 2026 rates used for 2025 (moot now that plans start in 2026). **Also fixed 2026-10-04:** loop mode's 2026 133-150% band started at 2.10% instead of 3.14% (`fork-notes/issue-aca-133-150.md`).


- **Step rates.** Each FPL bracket charges a constant applicable percentage, the value at the bracket's top (`_ACA_LP_CONTRIB`, `tax_federal.py:202`), while loop mode interpolates the sliding scale (`_aca_contrib_pct`). Inside a bracket the MILP overcharges, and it creates cliffs at 150/200/250/300% FPL that the statute does not have [recalled: the 2026 table is piecewise linear in FPL ratio except 300-400%].
- **Infeasible band.** The cost row is an equality `maca = pct_r * MAGI` with the bound `maca <= SLCSP` (`plan.py:4160`). Any MAGI below 400% FPL where `pct_r * MAGI > SLCSP` is therefore infeasible, when the true cost is `min(SLCSP, pct * MAGI)`. `aca.py` (single, no tax-deferred account, so MAGI is pinned near 370% FPL):

  ```
  SLCSP $5.0k  loop: ('solved', 53058, [5125, 5253, 5384], [59137, 60472, 61834])   optimize: ('infeasible', None)
  SLCSP $9.0k  loop: ('solved', 52718, [5889, 6021, 6155], [59125, 60449, 61798])   optimize: ('solved', 52718, [5889, 6021, 6155], [59125, 60449, 61798])
  ```

  Columns: status, spending basis, ACA cost in years 1-3, ACA MAGI in years 1-3.

  The band needs a low SLCSP relative to income (young or cheap market), so typical pre-65 retirees will rarely hit it. The paper's FIRE ladder discussion is exactly the population that can.
- **Mode disagreement.** Below 138% FPL, loop mode charges the full SLCSP (Medicaid assumption, `tax_federal.py:558`) while optimize mode charges 2.1%. Optimize mode always uses the 2026 table, including for 2025.

### 2.5 The SS claiming-age MILP chooses on pre-tax benefits [code] — fixed 2026-10-04

**Fix:** taxable SS, IRMAA/ACA MAGI and the state SS exclusion use the offset plus `ssb` (`_ss_benefit_terms`), at the loop's `Psi_n`. Not covered under `withSSTaxability="optimize"`. Tests: `TestClaimingAgeTaxes`. Draft: `fork-notes/issue-ss-age-taxes.md`.


With `withSSAges="optimize"`, the own-benefit variable `ssb` appears only in the cash-flow row. `grep '"ssb"'` finds `plan.py:2558, 3338, 3341, 3641` and nothing else. Taxable SS (`Psi_n * zetaBar` in loop mode, or `tss` bounded by `0.85*zetaBar`), provisional income, IRMAA/ACA MAGI and the state SS exclusion all use the previous iterate's `zetaBar`. Within each MILP, therefore, every candidate claiming age is charged the same tax on SS. The paper (Ch. 11) says only spousal and survivor amounts are carried by the loop. Its limitations list should add this.

### 2.6 Cost-basis tracking overstates gains [code, run] — fixed 2026-10-04

**Fix:** taxed, reinvested dividends and interest go into basis; `gain_fraction_in` holds the equity gain fraction `min(1, (1 - K/b)/alpha0)`. `basis.py` now gives 0.633 in 2037. Examples: joe -0.5%, helen+ruth -0.5%, jack+jill and robin -0.04%/-0.1%. Draft: `fork-notes/issue-cost-basis.md`.


`_update_gain_fraction` adds only contributions and surplus deposits to basis (`plan.py:4932`). Dividends and interest are taxed every year (in `Q_n` and `G_n`) and reinvested in the account, since balances grow at total return, so they belong in basis. Leaving them out taxes them again on sale. `basis.py` (100% equity, so the factor below does not interfere; $1M taxable with $500k basis, drawn down):

```
 year  balance  w_taxable  psi_owl  psi_with_divs
 2026   1000000    120642    0.500    0.500
 2030    714338    134665    0.619    0.560
 2034    268433     94109    0.709    0.606
 2037     78740     63060    0.762    0.633
```

A second, opposite-signed inconsistency: the whole-account gain fraction `1 - K/b` multiplies only the equity share of a withdrawal (`alpha_i00n * psi * w`, Eq. Qx3 and `plan.py` Q rows). That is correct only if the bond share carries no gain. With the basis updated as suggested (bond returns are taxed yearly, so bonds sit at basis), the equity gain fraction is `(1 - K/b)/alpha_0`. With a mixed allocation the two errors partly offset, by accident.

### 2.7 The partial first year counts elapsed flows twice [code; inference]

With `start_date` later than Jan 1, `_add_initial_balances` divides each balance by `1 + yearSpent * T` (`plan.py:3244`), which removes market growth only. Year 0 then runs full-year wages, contributions, SS and spending from that back-projected balance. `grep yearFracLeft` finds no other use in the model (one in `export.py:375`, a report line). A balance entered on Oct 1 already reflects nine months of spending and income, and the model applies them again. For a retiree this understates wealth by about 0.75 of a year's net withdrawal (conservative). For a worker it double-counts 0.75 of a year's net saving (optimistic). Either back-project the elapsed net flows as well, or prorate year-0 flows by `yearFracLeft`.

### 2.8 Survivor benefit when the deceased had not yet claimed [code; rule recalled] — fixed 2026-10-04

**Fix:** full PIA, plus DRCs to death after FRA. The rule is still from memory plus secondary summaries of POMS RS 00615.320 (primary sources blocked). Draft: `fork-notes/issue-survivor-never-claimed.md`.


`compute_survivor_stream` gives the survivor 0.825 x PIA (the `max` against a deceased benefit set to 0) when the first to die had not started benefits (`socialsecurity.py:563`). As I recall the rule, the 82.5% floor (the widow(er)'s limit) applies only when the deceased had taken **reduced** benefits. A worker who dies before claiming leaves a survivor benefit based on 100% of PIA, plus any delayed credits earned up to death. The paper lists this under limitations ("credited with the 82.5% PIA floor rather than the benefit accrued"), but the gap is 17.5 to 41.5 points of PIA (100-124% vs 82.5%), not a rounding matter. It is reached when a user's fixed claiming age is above the first death age. To check against POMS RS 00615 / 20 CFR 404.338 before acting.

### 2.9 Taxable-account bond returns [code]

`fak_in = sum_k max(0, tau_k) * alpha` for bonds and cash (`plan.py:3396`) taxes positive **total** returns, price changes included, as ordinary income every year and ignores negative years. Under variable rates (historical, Monte Carlo) this overtaxes bonds held in taxable accounts: the expected taxed amount `E[max(0, tau)]` exceeds `E[tau]`, and price gains are taxed as ordinary income before any sale. Under constant rates the effect is small.

### 2.10 Plan year is today's calendar year [code]

`_setStartingDate` ignores the year (`plan.py:630`), and about 50 `date.today()` calls set ages, RMD start, FRA and tax-year logic. The same case file gives different results after Jan 1, and a pinned seed reproduces the rates but not the plan. This is a documented choice (`info/PARAMETERS.md:35`). It belongs in the paper's assumptions because it limits reproducibility.

## 3. Paper vs. code drift

| Paper (owl.tex) | Code | Note |
|---|---|---|
| Roth cap: Ch. 5 per person; Ch. 7 (l. 3539-3547) "applied to the combined conversions" | per person (`_add_roth_conversion_constraints`) | Ch. 7 wrong |
| IRMAA MAGI expansion Eqs. MedDecomp2/3 and rows `J_3` (l. 3114-3143, 3614-3641): `-e_(n-2)` and income terms with flipped signs | `h = income before exemption`, no `e` (comment: "Subtracting e here as well would add it a second time") | paper wrong; code right |
| Eq. (PI) l. 2905: `Pi = MAGI - SS/2` with the AGI-basis MAGI (taxable SS only) | `MAGI_aca_n - SS/2` (full SS) | the intermediate-variables section is right, Eq. (PI) is not |
| "Adding binary variables z^x ... always contributes 4N_n binaries" (l. 3421); "coupled with binary variables excluding ..." (l. 2644) | AMO binaries removed; post-solve repair (`amorepair.py`) | stale |
| MIP decomposition, sequential and Benders, "certified global optimum" (Sec. 3.9, l. 1342-1398; Tab. "benders_cut") | `withDecomposition` retired upstream on 2026-09-26 (`84811f1`) | stale upstream too |
| Big-M "about 10^8" (l. 1962); `M_n = 3 B20` for LTCG/NIIT (l. 2744, 2775) | per-year ceilings from the portfolio plus fixed income (`_incomeCeiling`) | stale |
| Ch. 11: "survivor benefit assumed claimed in the year of death" | `survivor_claim_age` setting (Ch. 2 describes it) | Ch. 11 stale |
| Lexicographic term: `+eps` on `x` and on spouse-1 withdrawals (l. 4097) | `eps*(1+n)` on `x`; also `eps` on `w_i2n` and `s_n`; `1e-4` on `tss` | incomplete |
| Taxable-account interest uses `tau_kn` (Eq. Tx2) | `max(0, tau_kn)` | paper omits the clip |
| Stochastic spending scenarios "drawn from the calibrated multivariate lognormal model" (l. 5118) | any configured rate model | imprecise |
| Ch. 10 longevity: "life expectancy set to the drawn last-survivor horizon" | each person's drawn age is passed to `clone` | code is more correct than the text |
| CVaR relation `CVaR = mean shortfall/(1-rho)` and "efficient frontier" | the commitment LP's optimum is the empirical quantile of `{g_s}` at level `1/Lambda` | the framing overstates. The frontier is the sorted scenario bases, and each `g_s` is a perfect-foresight optimum, which the paper notes for year-1 robustness but not here |

## 4. What I checked and found sound [code]

- IRMAA, ACA and provisional-income MAGI rows in code: income terms match `G + e + Q` term by term (interest via `max(0, tau)`, dividends `mu`, gains via `bfac`).
- NIIT `min()` without a second binary: the floor and surplus-cap rows reproduce `0.038*min(MAGI - T, NII)` with `J` minimized.
- LTCG MILP link rows: `T <= G + M z <= T + M` gives z=1 iff G <= T. Loop mode's `ltcg_partition_hi` stops `q` from being inflated into the state base and MAGI.
- QCD: excluded from income by never entering it, counted against the RMD, removed from the balance in the carryover and the death-year inheritance.
- Roth-overlap substitution `x -> x-m, w2 -> w2-m, w1 -> w1+m` after 59½: invariant on the carryover, income and cash rows when `xnet = 1`.
- SC loop hygiene: parameters restored to those the accepted LP was built with (the cash flow balances exactly). Step-back retry on an unsolvable step. A fixed-point residual is reported.
- Per-year big-M derived from the portfolio ceiling plus fixed income, rather than a flat constant.
- `constrain_mean` defaults to off. It would remove most of the cross-scenario risk, since the spread of a path's mean return is real risk, not a finite-sample artefact as the paper's mean-anchoring section says.
- Fork: the NJ exclusion's disaggregated tier formulation is the convex hull per year. State AGI is identical however `st_e` splits.

## 5. Suggested order

1. ~~Bracket-order degeneracy (2.3)~~ done.
2. ACA optimize mode (2.4): ~~infeasible band~~ done; still to do: the sliding scale (SOS2 or finer breakpoints).
3. Cost basis (2.6) and the partial first year (2.7): bookkeeping, easy to test.
4. Cycle acceptance by residual (2.2).
5. Paper corrections (section 3). Most are upstream issues; draft them as such, per CONTRIBUTING.
6. Larger: decide whether the defaults should move toward `"optimize"` where it is cheap (Medicare took 0.1-62 s in the runs above; SS taxability up to 30 min, too slow for a default), and document loop mode as self-consistent, not optimal (2.1, 2.5).

## Scripts

`modes.py` (loop vs. optimize on the examples), `degen.py` (2.3), `aca.py` (2.4), `basis.py` (2.6). Run from the repo root with `.venv/bin/python fork-notes/model-review/<script>`.
