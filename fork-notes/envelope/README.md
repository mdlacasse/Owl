# Envelope model: what Owl collapses to under back-of-envelope assumptions (2026-10-04)

Fork-only note. Question (Florin): with no inflation, no gains, no interest and no bracket or threshold changes, is there a structurally simpler, faster formulation that is still largely correct, rather than the same solver with parameters zeroed?

Branch `claude/project-thread-u0d9t0`, from `claude/project-thread-qx5fy0`. Scripts and raw output are in this directory.

Evidence labels: **[run]** measured by a script here, output in the named file; **[derived]** follows from the model's equations, argued below; **[inferred]** my reading, not checked by a run.

## 1. Answer

Yes, with one change to the assumptions: keep a **common real return r** instead of r = 0. Under real dollars, constant brackets and thresholds, one return for every account and asset class, and no tax drag inside the taxable account, Owl's multi-year LP/MILP plus its self-consistent loop collapses to a one-dimensional problem:

> choose x_n, the tax-deferred dollars recognized as ordinary income in year n (withdrawals plus Roth conversions), to minimize Σ_n d_n [τ_n(x_n) − ν x_n] subject to Σ_n d_n x_n ≤ D, with d_n = (1+r)^−n.

τ_n is the year's whole bill as a function of x_n alone: federal ordinary and LTCG tax, SS taxability, the OBBBA senior deduction phase-out, NIIT, state and local tax, IRMAA two years later, and ACA. ν is the heirs' rate on tax-deferred money and D the PV of the tax-deferred balance plus contributions. Spending (maxSpending) or the bequest (maxBequest) then follows from a PV budget identity. RMDs and cash liquidity are constraints on the running PV recognized, Σ_{m≤n} d_m x_m.

This is a separable resource-allocation problem with one scalar state, solved exactly up to a grid by dynamic programming (`em.py`, `solve_dp`).

On the shipped examples, inside the envelope world (same inputs fed to both models), the EM lands within 0.0 to +0.74% of the full model at r = 0 in 12 of 16 comparable cases, and within 0.0 to +2.7% at a common real return in 12 of 16 [run]. The other four are explained in §4. Where it is higher, the gap splits into two parts. One is things it leaves out on purpose, mainly taxable-account drag. The other is plans that are genuinely better than Owl's loop fixed point, which I confirmed against Owl's own exact MILP modes on two cases (§4).

It is **not** faster than Owl's default loop mode: both take about a second (EM median 1.3–1.5 s in Python, full model median 0.1–0.3 s, max 3.7 s) [run]. Its speed advantage is against Owl's exact modes, which it matches (§4) and which take seconds to tens of minutes.

## 2. Why it collapses [derived]

1. **Accounts become fungible.** With one return r and no tax inside the taxable account, a dollar grows the same in the taxable, Roth and HSA accounts. Those three pool into one liquid balance. Per-spouse balances, withdrawal order, surplus deposits and the choice between conversion and withdrawal-plus-deposit stop mattering. What remains is *when* tax-deferred dollars are recognized as income.
2. **Returns cancel at the margin.** Discount everything to year 0 at r. The budget is Σ d_n x_n ≤ D and the cost is Σ d_n τ_n(x_n), so the first-order condition is τ'_n(x_n) = ν + λ in every year with interior x_n, independent of r. This is the classic traditional-vs-Roth equivalence. r enters only through the budget and the spending-profile weights, and it costs nothing to keep. Section 3 shows that dropping it (r = 0) is the one envelope assumption that wrecks magnitudes.
3. **The nonlinearity becomes 1-D.** Every term the full model handles with a lagged loop parameter or a MILP family depends, within a year, only on that year's x_n, given the exogenous incomes. IRMAA depends on year n−2, which is just a shifted attribution. So each τ_n can be tabulated on a grid with Owl's own functions (`tx.mediCosts`, `tx.acaCosts`, `tx.taxParams` constants), cliffs and torpedo included. The DP then sees their **marginal** cost, which the loop does not (model review §2.1).
4. **Stationary brackets and thresholds are not needed for the structure.** τ_n can differ by year at no cost (filing status at first death, OBBBA expiry, ages). Inflation 0 matters only because it makes Owl's unindexed thresholds (SS taxability, NIIT) behave like the indexed ones.

The full LP for `jack+jill` has 1,502 variables and 1,387 rows over 33 years (with Medicare binaries). The EM has one decision per year and one scalar state [run].

What does **not** collapse, and so is left out of the EM:

- tax drag in the taxable account (bond interest taxed yearly, LTCG on growth when sold). This is the one place accounts stop being fungible once r > 0;
- beneficiary fractions below 1 at the first death. Which spouse's account a dollar sits in then matters;
- conversion caps (`maxRothConversion`, `noRothConversions`, start year) and the 10% early-withdrawal penalty;
- the NJ tiered exclusion, NY recapture and state SS-exclusion subtleties. None of the examples is in NJ; `st_*` parameters are read as the plan computed them;
- spending slack. All examples use 0.

## 3. Which envelope assumptions cost accuracy (full model only) [run]

`ladder.py`, raw output `ladder_results.jsonl`. Each rung adds one assumption, solved by the full model with the case's own options. Objective is spending basis ($/yr) or bequest ($), today's dollars; % vs L0.

| Case | Obj | L0 original | L1 no OBBBA expiry | L2 mean rates | L3 real, no inflation | L4 r=0 | L5 common real r |
|---|---|---:|---:|---:|---:|---:|---:|
| alex+jamie | Spending | 228,369 | 232,703 (+1.90%) | 232,703 (+1.90%) | 232,583 (+1.85%) | 191,603 (-16.10%) | 232,587 (+1.85%) |
| bill | Spending | 36,666 | 36,666 (+0.00%) | 57,268 (+56.19%) | 57,268 (+56.19%) | 33,333 (-9.09%) | 63,427 (+72.99%) |
| cameron | Spending | 18,996 | 18,996 (+0.00%) | 18,996 (+0.00%) | 18,996 (+0.00%) | 16,904 (-11.01%) | 18,996 (+0.00%) |
| chris+pat | Spending | 116,916 | 119,009 (+1.79%) | 134,176 (+14.76%) | 135,364 (+15.78%) | 73,017 (-37.55%) | 135,380 (+15.79%) |
| dana | Spending | 81,228 | 83,348 (+2.61%) | 83,348 (+2.61%) | 83,421 (+2.70%) | 48,471 (-40.33%) | 83,416 (+2.69%) |
| devon | Spending | 248,306 | 252,232 (+1.58%) | 252,232 (+1.58%) | 252,551 (+1.71%) | 122,979 (-50.47%) | 252,512 (+1.69%) |
| helen+ruth | Spending | 194,069 | 199,362 (+2.73%) | 199,364 (+2.73%) | 198,831 (+2.45%) | 180,509 (-6.99%) | 203,060 (+4.63%) |
| jack+jill | Spending | 102,545 | 104,197 (+1.61%) | 133,119 (+29.82%) | 139,956 (+36.48%) | 92,590 (-9.71%) | 139,584 (+36.12%) |
| joe | Spending | 92,575 | 94,364 (+1.93%) | 94,364 (+1.93%) | 95,970 (+3.67%) | 59,729 (-35.48%) | 95,758 (+3.44%) |
| john+sally | Bequest | 16,803 | 196,103 (+1067%) | 196,103 (+1067%) | 199,551 (+1088%) | infeasible | 199,417 (+1087%) |
| jon+jane | Spending | 160,677 | 165,428 (+2.96%) | 165,428 (+2.96%) | 169,993 (+5.80%) | 96,331 (-40.05%) | 151,184 (-5.91%) |
| jordan+taylor | Bequest | 1,530,120 | 1,618,135 (+5.75%) | 1,618,135 (+5.75%) | 1,558,563 (+1.86%) | 424,674 (-72.25%) | 1,567,060 (+2.41%) |
| jordan+taylor-qcd | Bequest | 1,180,200 | 1,259,255 (+6.70%) | 1,259,255 (+6.70%) | 1,052,056 (-10.86%) | 66,914 (-94.33%) | 1,068,158 (-9.49%) |
| kim+sam-bequest | Bequest | 1,944,071 | 2,148,728 (+10.53%) | 2,148,728 (+10.53%) | 2,203,136 (+13.33%) | 538,661 (-72.29%) | 2,211,216 (+13.74%) |
| kim+sam-spending | Spending | 185,949 | 190,252 (+2.31%) | 190,252 (+2.31%) | 191,210 (+2.83%) | 162,370 (-12.68%) | 191,294 (+2.87%) |
| morgan | Spending | 38,744 | 43,157 (+11.39%) | 43,157 (+11.39%) | 44,480 (+14.80%) | 27,498 (-29.03%) | 44,277 (+14.28%) |
| robin | Spending | 44,013 | 44,242 (+0.52%) | 44,242 (+0.52%) | 44,346 (+0.76%) | 32,092 (-27.09%) | 45,210 (+2.72%) |

L2 uses each asset class at the arithmetic mean of the case's own rate series. L3 deflates those means by the mean inflation. L5 puts every class at r_c = 0.6·stocks + 0.4·bonds (real) with dividends 0. L4 sets every rate and dividends to 0.

Readings:

- **"No gains, no interest" is the expensive assumption:** −7% to −94% (median about −30%). It is also unnecessary, because the EM keeps r for free.
- **No scheduled bracket change (OBBBA kept past 2032)** moves spending by 0 to +3% (morgan +11%), bequests by +6 to +11%. `john+sally`'s bequest is a small residual of a large plan, so its +1,067% is about $179k in absolute terms.
- **Deterministic mean rates instead of a historical sequence** is large where the case runs one (bill +56%, jack+jill +30%, chris+pat +15%, the last a stochastic draw). That is sequence risk, which no deterministic envelope can capture.
- **Inflation 0** (L2 to L3) is small except jordan+taylor-qcd (−16%) and jon+jane (+3%). One common real return (L3 to L5) is within 2% except jon+jane (−11%, their stock-heavy mix earns more than r_c) and helen+ruth (+2%).

## 4. EM vs the full model on identical envelope inputs [run]

`compare.py`, raw output `compare_results.jsonl` (and `compare_phi1.jsonl` for the two jordan cases with beneficiary fractions forced to 1, in both models). Both models get the same plan object: OBBBA never expires, inflation 0, dividends 0, every asset class at r (0, or r_c from §3). The EM reads its exogenous series (SS, pensions, wages, contributions, QCDs, fixed assets, debts, spending profile, brackets, state parameters) from that plan.

"EM on full's x" evaluates the full model's own recognition schedule with the EM accounting. It measures how far the two models' tax and budget accounting disagree, separate from optimization. "EM vs full" minus that is the EM's optimization gain (or loss).

| Case | r=0: full | EM | EM vs full | EM on full's x | full loop exit | r_c % | full | EM | EM vs full | EM on full's x |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| alex+jamie | 191,603 | 192,990 | +0.72% | +0.11% | oscillatory | 2.92 | 232,612 | 235,292 | +1.15% | +0.66% |
| bill | 33,333 | 33,333 | 0.00% | 0.00% | monotonic | 5.23 | 63,448 | 63,448 | 0.00% | 0.00% |
| cameron | 16,904 | 16,904 | 0.00% | 0.00% | 2-cycle | 5.46 | 18,996 | 18,996 | 0.00% | 0.00% |
| chris+pat | 73,017 | 73,540 | +0.72% | 0.00% | oscillatory | 6.5 | 135,460 | 136,097 | +0.47% | +0.07% |
| dana | 48,471 | 48,690 | +0.45% | +0.01% | 2-cycle | 5.46 | 83,410 | 83,512 | +0.12% | +0.11% |
| devon | 122,979 | 123,503 | +0.43% | 0.00% | monotonic | 5.46 | 252,492 | 253,308 | +0.32% | +0.22% |
| helen+ruth | 180,509 | 181,681 | +0.65% | +0.29% | max iteration | 2.33 | 203,009 | 206,913 | +1.92% | +1.20% |
| jack+jill | 92,590 | 93,279 | +0.74% | −0.03% | max iteration | 6.19 | 139,591 | 140,451 | +0.62% | +0.26% |
| joe | 59,729 | 60,140 | +0.69% | +0.36% | 2-cycle | 4.84 | 95,751 | 98,337 | +2.70% | +2.43% |
| john+sally | infeasible | — | — | — | — | 2.33 | 197,516 | 206,834 | +4.72% | +2.50% |
| jon+jane | 96,331 | 96,898 | +0.59% | −0.03% | max iteration | 4.73 | 151,132 | 151,216 | +0.06% | +0.06% |
| jordan+taylor (φ=1) | 1,145,407 | 1,185,974 | +3.54% | 0.00% | oscillatory | 2.63 | 4,280,331 | 4,455,406 | +4.09% | +0.67% |
| jordan+taylor-qcd (φ=1) | 75,889 | 14,709 | see below | see below | unsolvable iterate | 2.63 | 2,737,126 | 2,827,098 | +3.29% | +1.14% |
| kim+sam-bequest | 538,661 | 569,032 | +5.64% | +0.03% | oscillatory | 2.33 | 2,206,266 | 2,238,409 | +1.46% | +1.12% |
| kim+sam-spending | 162,370 | 163,356 | +0.61% | +0.01% | 2-cycle | 2.33 | 191,239 | 191,775 | +0.28% | +0.18% |
| morgan | 27,498 | 29,112 | +5.87% | −1.65% | 2-cycle | 6.46 | 44,287 | 46,074 | +4.04% | −0.10% |
| robin | 32,092 | 32,092 | 0.00% | 0.00% | 2-cycle | 6.46 | 45,216 | 45,325 | +0.24% | 0.00% |

**Accounting agrees at r = 0.** "EM on full's x" is within ±0.4% in 14 of 16 cases. The two exceptions are both the full model's loop not reaching a consistent point, not EM errors:

- `jordan+taylor-qcd`: the full model's loop exits on an "unsolvable iterate" with an IRMAA fixed-point residual of $91,574. The EM's value at the full model's own x is $75,889 − $91,574 = −$15,685 [run]. The full plan undercharges Medicare by exactly its residual: its `M_n` is half of `tx.mediCosts` on its own MAGI in every year [run]. The full model's 75,889 is therefore not attainable. The EM's 14,709 is.
- `morgan` (−1.65%): the loop ends in a 2-cycle with a residual of $42,178 [run]. The −1.65% is its accepted iterate undercharging ACA/SS [inferred from the residual; not decomposed].

**At r = r_c the accounting gap is the taxable-account drag** that the EM leaves out. It is largest where the taxable account is large and grows: joe +2.43%, john+sally +2.50%, helen+ruth +1.20%, kim+sam-bequest +1.12%. For joe, the full model charges $50,231 of LTCG tax and taxes $54,465 of interest that the EM does not see [run]. That is roughly $62k over 27 years, about 2.4% of the spending basis [inferred arithmetic; matches the measured 2.43%].

**Optimization gains are real where checked.** I re-solved the full model in the envelope world with Owl's exact MILP modes (`verify_exact.py`, `verify_*.jsonl`):

| Case (r=0) | Full, loop | Full, exact mode | EM |
|---|---:|---:|---:|
| morgan | 27,498 | 29,091 (`withACA=optimize`, also with Medicare+SS optimize) | 29,112 |
| jordan+taylor (φ=1) | 1,145,407 | 1,185,882 (`withMedicare=optimize`) | 1,185,974 |
| kim+sam-bequest | 538,661 | 539,300 (`withMedicare=optimize`); SS-optimize: PENDING | 569,032 |

PENDING lines are filled in below when the runs finish. On the two finished cases the EM agrees with Owl's exact mode to 0.07% and 0.008%. The remaining +0.4 to +0.7% EM gains at r = 0 (alex+jamie, chris+pat, dana, devon, jack+jill, joe, kim+sam-spending) are consistent with the loop's blindness to marginal SS/IRMAA cost (model review §2.1) but are not individually verified [inferred].

**EM vs the real plan (L0).** The EM at r_c is the full model's L5 plus the gaps above. So the total error against the original case is the §3 ladder plus a few percent. It is dominated by the assumption ladder (sequence risk, OBBBA expiry), not by the formulation.

## 5. What this is good for, and what it is not

- **Good:** a transparent sanity check on any full-model run, in Florin's sense. Its value is close to an upper bound for the envelope world: it omits frictions (caps, drag, penalties) and optimizes the nonconvex terms exactly. Where the full loop lands well below it at r = 0 with the accounting agreeing, the loop is leaving value on the table, and an exact mode is worth running (morgan, jordan+taylor, likely kim+sam-bequest).
- **Good:** an exact treatment of SS taxability, IRMAA and ACA cliffs at seconds per case. Owl's MILP modes for the same thing take seconds to tens of minutes (model review §2.1). It could serve as a warm start or a check for those modes [inferred].
- **Not:** a replacement for the full model. It cannot see sequence risk (historical or stochastic rates), taxable-account drag, conversion caps, partial beneficiary fractions or the early-withdrawal penalty, and it is not faster than default loop mode.
- **Speed headroom:** the DP is a pure-Python loop over states (B ≈ 1,500–1,900 PV steps per case). A vectorized min-plus convolution would likely cut it by 10× or more [inferred, not measured]. That would only matter for batch uses (Monte Carlo over r, sweeps of claiming ages).

## 6. Files

- `ladder.py` → `ladder_results.jsonl`: the assumption ladder (§3).
- `em.py`: the envelope model (`inputs`, `cost_table`, `solve_dp`, `evaluate`).
- `compare.py` → `compare_results.jsonl`, `compare_phi1.jsonl` (`EM_PHI1=1`): EM vs full (§4).
- `verify_exact.py` → `verify_*.jsonl`: full model with exact MILP modes.

Reproduce: `cd fork-notes/envelope && python3 ladder.py && python3 compare.py` (all examples; a case path as argument runs one).
