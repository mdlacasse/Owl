# Envelope model: what Owl collapses to under back-of-envelope assumptions (2026-10-04)

Fork-only note. Question (Florin): with no inflation, no gains, no interest and no bracket or threshold changes, is there a structurally simpler, faster formulation that is still largely correct, rather than the same solver with parameters zeroed?

Branch `claude/project-thread-u0d9t0`, from `claude/project-thread-qx5fy0`. Scripts and raw output are in this directory.

Evidence labels: **[run]** measured by a script here, output in the named file; **[derived]** follows from the model's equations, argued below; **[inferred]** my reading, not checked by a run.

## 1. Answer

Yes, with one change to the assumptions: keep a **common real return r** instead of r = 0. Under real dollars, constant brackets and thresholds, one return for every account and asset class, and no tax drag inside the taxable account, Owl's multi-year LP/MILP plus its self-consistent loop collapses to a one-dimensional problem:

> choose x_n, the tax-deferred dollars recognized as ordinary income in year n (withdrawals plus Roth conversions), to minimize Σ_n d_n [τ_n(x_n) − ν x_n] subject to Σ_n d_n x_n ≤ D, with d_n = (1+r)^−n.

τ_n is the year's whole bill as a function of x_n alone: federal ordinary and LTCG tax, SS taxability, the OBBBA senior deduction phase-out, NIIT, state and local tax, IRMAA two years later, and ACA. ν is the heirs' rate on tax-deferred money and D the PV of the tax-deferred balance plus contributions. Spending (maxSpending) or the bequest (maxBequest) then follows from a PV budget identity. RMDs and cash liquidity are constraints on the running PV recognized, Σ_{m≤n} d_m x_m.

This is a separable resource-allocation problem with one scalar state, solved exactly up to a grid by dynamic programming (`em.py`, `solve_dp`).

On the shipped examples, inside the envelope world (same inputs fed to both models), the EM lands within 0.0 to +0.74% of the full model at r = 0 in 12 of 16 comparable cases, and within 0.0 to +2.7% at a common real return in 12 of 16 [run]. The other four are explained in §4. Where it is higher, the gap splits into two parts. One is things it leaves out on purpose, mainly taxable-account drag. The other is plans that are genuinely better than Owl's loop fixed point, which I confirmed against Owl's own exact MILP modes on five cases (§4).

*(Superseded by §7: the EM now keeps inflation, the OBBBA expiry and each case's own rate sequence, and a banded DP solves in 0.005–0.18 s.)* As first measured, it was **not** faster than Owl's default loop mode: both take about a second (EM median 1.3–1.5 s in Python, full model median 0.1–0.3 s, max 3.7 s) [run]. Its speed advantage is against Owl's exact modes, which it matches (§4) and which take seconds to tens of minutes.

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
| kim+sam-bequest | 538,661 | 539,300 (`withMedicare=optimize`); 569,071 (Medicare + `withSSTaxability=optimize`, 480 s) | 569,032 |
| dana | 48,471 | 48,689 (Medicare + SS optimize, 180 s) | 48,690 |
| kim+sam-spending | 162,370 | 163,357 (Medicare + SS optimize, 240 s, loop oscillatory) | 163,356 |
| devon | 122,979 | 120,748 (Medicare + SS optimize, 240 s, loop oscillatory) | 123,503 |

On five of the six cases the EM agrees with Owl's exact modes to within 0.07% (morgan), and within $1 to $92 on the other four. For kim+sam-bequest the gain comes from SS taxability, not IRMAA: Medicare-optimize alone recovers only $639 of the $30k. Devon is inconclusive: the exact-mode run ended below loop mode, on an oscillating loop with each MILP capped at 60 s (`maxTime=60`). It neither confirms nor refutes the EM's +0.43%. The remaining +0.4 to +0.7% EM gains at r = 0 (alex+jamie, chris+pat, jack+jill, joe) are consistent with the loop's blindness to marginal SS/IRMAA cost (model review §2.1) but are not individually verified [inferred].

**EM vs the real plan (L0).** The EM at r_c is the full model's L5 plus the gaps above. So the total error against the original case is the §3 ladder plus a few percent. It is dominated by the assumption ladder (sequence risk, OBBBA expiry), not by the formulation.

## 5. What this is good for, and what it is not

- **Good:** a transparent sanity check on any full-model run, in Florin's sense. Its value is close to an upper bound for the envelope world: it omits frictions (caps, drag, penalties) and optimizes the nonconvex terms exactly. Where the full loop lands well below it at r = 0 with the accounting agreeing, the loop is leaving value on the table, and an exact mode is worth running (morgan, jordan+taylor, kim+sam-bequest).
- **Good:** an exact treatment of SS taxability, IRMAA and ACA cliffs at seconds per case. Owl's MILP modes for the same thing take seconds to tens of minutes (model review §2.1). It could serve as a warm start or a check for those modes [inferred].
- **Not:** a replacement for the full model. It cannot see sequence risk (historical or stochastic rates), taxable-account drag, conversion caps, partial beneficiary fractions or the early-withdrawal penalty, and it is not faster than default loop mode.
- **Speed headroom:** the DP is a pure-Python loop over states (B ≈ 1,500–1,900 PV steps per case). A vectorized min-plus convolution would likely cut it by 10× or more [inferred, not measured]. That would only matter for batch uses (Monte Carlo over r, sweeps of claiming ages).

## 6. Files

- `ladder.py` → `ladder_results.jsonl`: the assumption ladder (§3).
- `em.py`: the envelope model (`inputs`, `cost_table`, `solve_dp`, `evaluate`).
- `compare.py` → `compare_results.jsonl`, `compare_phi1.jsonl` (`EM_PHI1=1`): EM vs full (§4).
- `verify_exact.py` → `verify_*.jsonl`: full model with exact MILP modes.
- `compare_orig.py` → `orig*_results.jsonl`: EM vs full on the original cases (§7, §8). `EM_PEN=0`/`EM_TAX=0` turn off the penalty and the taxable state, `EM_REF=1` adds the exact DP, `EM_PHI1=1` sets beneficiary fractions to 1.
- `verify_orig.py` → `verify_orig.jsonl`: full model with exact MILP modes on the original cases (§8).
- `seed.py` → `seed_results.jsonl`, `seed_phi1.jsonl`: Owl seeded / pinned from the one-state EM (§9).

§3–§7 were produced by `em.py` as of commit 359bdf4; `solve_dp` now defaults to the §8 model (`penalty=True, taxable=True`), so re-running `compare.py` gives §8-style numbers.

Reproduce: `cd fork-notes/envelope && python3 ladder.py && python3 compare.py` (all examples; a case path as argument runs one).

## 7. Follow-up (2026-10-04): keeping every assumption the collapse tolerates, a faster DP, other collapses

### 7.1 Only three assumptions are needed [derived], so the EM now drops the rest

The collapse in §2 needs only: (a) in each year, every account earns the same return R_n; (b) no tax inside the taxable account; (c) pooling of taxable, Roth and HSA, which (a) and (b) make exact. Inflation, the OBBBA expiry, indexed and unindexed thresholds, and any rate sequence (historical, stochastic, glide paths) only change the per-year cost functions τ_n and the discount factors d_n = Π_{m<n} 1/R_m. §4 imposed them anyway. `em.py` now works in nominal dollars with the plan's own per-year returns (the balance-weighted mean across the accounts that exist that year; `R_spread` reports the largest gap between accounts) and its own inflation, brackets and thresholds.

`compare_orig.py` → `orig_results.jsonl`, `orig_phi1.jsonl`: full model vs EM on the **original** cases (the full model keeps dividends; the `mu0` column in the raw output sets dividends to 0 in both and changes little). "EM fast vs exact DP" is the §7.2 banded DP against the reference DP.

| Case | Full (L0) | EM | EM vs full | EM on full's x | EM fast vs exact DP | R spread % | t full (s) | t EM fast | t EM exact DP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| alex+jamie | 228,369 | 231,464 | +1.36% | +0.84% | -0.012% | 0.0 | 0.15 | 0.096 | 1.85 |
| bill | 36,666 | 36,666 | -0.00% | -0.00% | +0.000% | 0.0 | 0.06 | 0.005 | 0.0 |
| cameron | 18,996 | 18,996 | +0.00% | +0.00% | +0.000% | 0.0 | 0.15 | 0.026 | 0.04 |
| chris+pat | 116,916 | 117,616 | +0.60% | +0.30% | +0.000% | 0.0 | 0.37 | 0.055 | 0.42 |
| dana | 81,228 | 81,416 | +0.23% | +0.19% | +0.000% | 0.0 | 0.14 | 0.039 | 0.68 |
| devon | 248,306 | 249,748 | +0.58% | +0.33% | +0.000% | 0.0 | 0.07 | 0.149 | 2.19 |
| helen+ruth | 194,069 | 197,867 | +1.96% | +1.19% | -0.021% | 0.0 | 0.16 | 0.031 | 0.44 |
| jack+jill | 102,545 | 103,667 | +1.09% | +0.46% | +0.000% | 2.87 | 1.39 | 0.081 | 0.73 |
| joe | 92,575 | 95,662 | +3.34% | +2.87% | +0.000% | 0.0 | 0.11 | 0.041 | 0.66 |
| john+sally | 16,803 | 43,474 | +158.74% | +63.43% | +0.000% | 0.0 | 0.12 | 0.149 | 1.52 |
| jon+jane | 160,677 | 161,642 | +0.60% | +0.22% | +0.000% | 0.0 | 0.17 | 0.058 | 0.66 |
| jordan+taylor (φ=1) | 4,220,573 | 4,411,886 | +4.53% | +2.55% | -0.007% | 0.0 | 0.12 | 0.04 | 0.75 |
| jordan+taylor-qcd (φ=1) | 3,111,557 | 3,282,501 | +5.49% | +3.01% | +0.000% | 0.0 | 0.12 | 0.054 | 0.9 |
| kim+sam-bequest | 1,944,071 | 2,028,525 | +4.34% | +2.97% | +0.000% | 0.0 | 0.49 | 0.074 | 1.02 |
| kim+sam-spending | 185,949 | 187,351 | +0.75% | +0.47% | +0.000% | 0.0 | 0.41 | 0.048 | 0.9 |
| morgan | 38,744 | 45,154 | +16.54% | +3.49% | -0.009% | 0.0 | 0.38 | 0.181 | 0.96 |
| robin | 44,013 | 42,888 | -2.56% | -3.64% | +0.000% | 1.59 | 0.29 | 0.035 | 0.23 |

Readings [run unless marked]:

- **Within 0 to +2% in 10 of 17** (bill, cameron, alex+jamie, dana, chris+pat, devon, helen+ruth, jack+jill, jon+jane, kim+sam-spending), on the cases' own inputs. That includes jack+jill's 1969 historical sequence and chris+pat's stochastic draw.
- **Taxable-account tax**, assumption (b): joe, kim+sam-bequest, both jordans and john+sally. The accounting gap ("EM on full's x") is +2.6% to +3.0%, and these are the cases with the largest taxable accounts. john+sally's bequest is a small residual: the gap is $26.7k on a plan whose L1 bequest is $196k.
- **Per-account allocations**, assumption (a): robin is the only example with `type = "account"` allocations. The EM is −2.6% and its accounting −3.6%. The full model can hold the higher-return mix where it is taxed least (asset location), which a common return cannot represent [mechanism inferred; the 1.6% return spread is measured].
- **Early-withdrawal penalty**: morgan's accounting gap of +3.5% sits in years 2026–2030, before age 59½. In those years the full model's tax exceeds the EM's at the same income (e.g. $17.1k vs $11.4k in 2028), which is the 10% penalty in `T_n`. The rest of morgan's +16.5% is the ACA marginal cost the loop does not see. §4 confirmed that with `withACA="optimize"` in the envelope world; it is not re-verified here [inferred]. The penalty fits the collapse: it applies to the recognition the liquidity floor forces before 59½. It is not implemented.
- A first version of this run counted a deceased spouse's accounts as earning 0 after the death, because their allocation is zero. That gave alex+jamie −11% and kim+sam-bequest −10%. Fixed before the table above.

So two assumptions must stay, because they *are* the collapse: (a) the same return in every account (robin shows the cost when it fails), and (b) no taxable-account tax. Everything else can be kept at no structural cost.

### 7.2 The DP for a single run [run]

- **Cost table:** `tx.mediCosts` and `tx.acaCosts` were called once per grid point. Vectorized copies (`_medicare`, `_aca`) agree with Owl's functions to 4e-12 on 40 random MAGI paths for each of four cases. Table time dropped from 0.3–0.5 s to 0.01–0.02 s.
- **DP:** a coarse pass on a grid 1/200 of the budget (all states), then the exact DP restricted to a band of ±4 coarse steps around the coarse path. The band is widened and re-solved whenever the optimum touches its edge.
- **Result:** 0.005–0.18 s per solve (median 0.05 s), against 0.04–2.2 s for the exact DP and 0.06–1.4 s for the full model's default loop mode. The banded result equals the exact DP in 13 of 17 cases and is within 0.02% in the other four (table above). It is a heuristic: a nonconvex optimum far from the coarse path could be missed, and nothing guarantees otherwise.
- A dense min-plus convolution over all states was tried first. It was 2–4× *slower* than the reference loop, because the (B+1)² array per year is memory-bound.

### 7.3 Other collapses

- **SS claiming ages as an outer enumeration** [run, `ss_ages.py` → `ss_ages_results.jsonl`]. Claiming ages only change the exogenous SS series. So each candidate pair is one EM solve: every whole year 62–70 per person, then a monthly refinement. Compared with Owl's `withSSAges="optimize"` MILP:

  | Case | EM's ages | Owl MILP's ages | Full model at EM's ages | Owl MILP | EM search time | Owl MILP time |
  |---|---|---|---:|---:|---:|---:|
  | dana | 68.25 | 68.17 | 81,459 | 81,452 | 2.1 s | 0.3 s |
  | kim+sam-spending | 70, 69.92 | 70, 70 | 186,159 | 186,153 | 7.7 s | 1.5 s |
  | jack+jill | 68.92, 65.92 | 68.92, 65.92 | 103,811 | 104,092 | 11.2 s | 4.3 s |
  | robin | 68.08 | 65.5 | 44,022 | 44,070 | 2.0 s | 1.4 s |

  It agrees with the MILP to within a month in three of four cases. Robin, the asset-location case, is the exception. It is slower, not faster. jack+jill gets two different full-model values at identical ages, 0.27% apart: loop-mode noise, as CLAUDE.md warns.
- **Spending–bequest frontier from one solve** [derived, spot-checked]. In the EM the bequest target enters only the budget identity. Unless the liquidity or RMD constraints move the optimal x, basis is linear in the bequest, with slope −d_N γ_N / Σ d_n ξ_n γ_n. Measured at bequests of 0, 200k, 400k and 800k: the EM's x was unchanged and its basis exactly linear for kim+sam-spending and jack+jill. The full model's slopes differ from the EM's by 0.6% and 1.9%. For dana the x changed and the EM's increments drift by 1.5%.
- **Single-multiplier water-filling** ("recognize until the marginal rate is ν + λ"). This is exact when every τ_n is convex (no IRMAA/ACA cliffs, no torpedo) and is solved by bisection on λ. It is useful as an interpretable rule. With cliffs it lost 1.3% against the DP on jack+jill in the envelope world (first EM version, §4 period) [run, not kept as a script].
- **Not tried** [inferred]: seeding Owl's loop parameters (Ψ, M, ACA) from the EM's plan, so the loop starts at the better point the EM finds. (The taxable-account state and the penalty, listed here before, are §8.)

## 8. Follow-up 2 (2026-10-04): early-withdrawal penalty, Roth conversion caps, taxable account as a DP state

Florin's point stands: the penalty fits the collapse and should have been in the EM from the start. So should the conversion caps, which every example sets (`maxRothConversion` from 0 to 400k, `noRothConversions`, `startRothConversions`) and which §2 had listed as left out. All three are now in `em.py` (`solve_dp(..., penalty=True, taxable=True)`).

### 8.1 What was added [derived from Owl's code, then measured]

- **Penalty.** Owl charges 10% on tax-deferred withdrawals before 59½ (`P_n`, plan.py:6585) and locks each Roth conversion for 5 years (`_add_roth_maturation_constraints`). The EM simulates the cash plan: in a year in which no living holder is 59½ yet, cash comes from the liquid pool and matured conversions first, and the shortfall S is withdrawn as S/0.9 with a 10% penalty. That withdrawal becomes a floor on x_n and the penalty is added to τ_n, iterated to a fixed point. Simplifications: the lock is applied only in penalized years; conversions made before the plan starts are not locked; a couple is penalized only when both are under 59½.
- **Liquidity inside the DP.** The liquid pool after year n is L0 + s·h − (PV of spending net of fixed cash) − (F + ν·s·h), and F + ν·s·h is the PV of taxes paid so far. For a given state the cheapest path is also the most liquid, so this constraint keeps the DP exact for a given spending path. It replaces the iterated floor of §7.
- **Taxable account as a second state.** State (s, t): PV recognized so far, PV taxable balance. The second decision is the year's net draw (negative = deposit). Each year's tax gets Owl's own taxable income: interest-like yield on the balance after the draw (ordinary), dividends on its equity share and the gain on the equity share of the draw (`_add_taxable_income`, `_update_gain_fraction`). Constraints:
  - net draw ≤ cash need − (cash that cannot go to the Roth). That cash is the RMD, or recognition beyond the year's conversion cap. Without this, money would move from the taxable account to the Roth, which Owl allows only through conversions. A negative right-hand side forces a deposit: windfalls (joe sells a house in 2032), RMDs beyond spending, and every withdrawal beyond spending when the cap is 0 (bill, jon+jane).
  - taxable balance ≤ liquid pool (Roth ≥ 0).
  - The gain fraction K/b evolves as (K/b + taxed yield)/R regardless of draws, because average-cost basis scales with the balance on a withdrawal. So it is exogenous, exact without contributions or deposits and approximate with them.
- **Solver.** A coarse 2-D DP (recognition on 1/100 of the budget, taxable on 16–41 levels), then alternating fine 1-D DPs: the recognition schedule for the taxable path (§7 banded DP), and the taxable path for the schedule (4× finer levels). Each pair is re-checked, and the best consistent pair is kept. Spending (maxSpending) is iterated from an upper estimate with damping; from below it stops at the lowest fixed point. Levels force one level of slack in the draw and Roth constraints, otherwise rounding accumulates over years of forced deposits. The `draw_excess` column measures what that slack lets through.

### 8.2 Results on the original cases [run]

`compare_orig.py` → `orig2_results.jsonl`, `orig2_phi1.jsonl` (penalty, caps and taxable state on); `orig1d_results.jsonl` (`EM_PEN=0 EM_TAX=0`: the §7 model, for comparison). "EM on full's x" now feeds Owl's own taxable income and penalties (`owl_extras`) into the EM's accounting.

| Case | Full (loop) | EM now | EM vs full | §7 EM vs full | EM on full's x (now / §7) | draw excess (PV) | t full | t EM now | t §7 EM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| alex+jamie | 228,369 | 230,038 | +0.73% | +1.36% | +0.11% / +0.84% | 16,654 | 0.17 | 1.46 | 0.09 |
| bill | 36,666 | 36,666 | 0.00% | 0.00% | 0.00% / 0.00% | 0 | 0.04 | 0.01 | 0.02 |
| cameron | 18,996 | 18,996 | 0.00% | 0.00% | 0.00% / 0.00% | 0 | 0.13 | 1.42 | 0.04 |
| chris+pat | 116,916 | 117,287 | +0.32% | +0.60% | −0.01% / +0.30% | 5,146 | 0.33 | 1.94 | 0.07 |
| dana | 81,228 | 81,270 | +0.05% | +0.23% | 0.00% / +0.19% | 1,412 | 0.06 | 0.93 | 0.07 |
| devon | 248,306 | 248,775 | +0.19% | +0.58% | 0.00% / +0.33% | 264 | 0.07 | 1.35 | 0.21 |
| helen+ruth | 194,069 | 195,227 | +0.60% | +1.96% | 0.00% / +1.19% | 14,677 | 0.14 | 0.67 | 0.05 |
| jack+jill | 102,545 | 102,966 | +0.41% | +1.09% | −0.33% / +0.46% | 5,093 | 1.30 | 3.31 | 0.11 |
| joe | 92,575 | 92,652 | +0.08% | +3.34% | 0.00% / +2.87% | 26,307 | 0.08 | 1.80 | 0.06 |
| john+sally | 16,803 | 32,022 | +90.6% | +158.7% | 0.00% / +63.4% | 7,746 | 0.13 | 0.90 | 0.04 |
| jon+jane | 160,677 | 160,176 | −0.31% | +0.60% | 0.00% / +0.22% | 121,460 | 0.15 | 5.21 | 0.09 |
| jordan+taylor (φ=1) | 4,220,573 | 4,335,996 | +2.73% | +4.53% | 0.00% / +2.55% | 105,600 | 0.12 | 1.67 | 0.03 |
| jordan+taylor-qcd (φ=1) | 3,111,557 | 3,225,845 | +3.67% | +5.49% | 0.00% / +3.01% | 83,629 | 0.14 | 1.83 | 0.04 |
| kim+sam-bequest | 1,944,071 | 1,962,350 | +0.94% | +4.34% | +0.01% / +2.97% | 84,406 | 0.48 | 1.87 | 0.04 |
| kim+sam-spending | 185,949 | 186,409 | +0.25% | +0.75% | 0.00% / +0.47% | 59,982 | 0.37 | 1.71 | 0.07 |
| morgan | 38,744 | 43,341 | +11.87% | +16.55% | +0.01% / +3.49% | 268 | 0.32 | 2.12 | 0.16 |
| robin | 44,013 | 42,847 | −2.65% | −2.56% | −3.88% / −3.64% | 0 | 0.26 | 0.79 | 0.05 |

Readings:

- **The accounting now matches Owl.** Fed Owl's own recognition schedule, taxable income and penalties, the EM reproduces Owl's objective within ±0.11% in 15 of 17 cases (§7: up to +3.5%) [run]. The exceptions are jack+jill (−0.33%, which has a 2.9% return spread between accounts) and robin (per-account allocations). Both are assumption (a). The two jordan cases are compared at φ=1 as before.
- **The optimum is within −0.3% to +0.9% of Owl in 12 of 17** (§7: −2.6% to +2% in 10, of which 7 within ±1%) [run]. joe went from +3.34% to +0.08% and kim+sam-bequest from +4.34% to +0.94%.
- **morgan +11.9% is Owl's ACA loop, not the EM.** Owl's loop settles in 2026–2036 at MAGI levels where ACA costs the full benchmark premium, $14–18k a year: above 400% FPL in 2026–2031, and just under the 138% floor in 2033–2036. Re-solved with `withACA="optimize"` (exact MILP, gap 1e-4, 51 s), Owl gives 43,931, and the EM is −1.3% below that (`verify_orig.py` → `verify_orig.jsonl`) [run]. The penalty itself is now matched: the EM charges $21.6k against Owl's $23.7k.
- **john+sally (+$15.2k on the bequest) is unexplained.** The accounting gap is 0, and Owl's exact modes (`withMedicare`, `withLTCG`, `withNIIT` = optimize) return the same 16,803 as the loop [run]. So the EM's plan is either infeasible in Owl for a reason the EM does not model, or better than Owl's optimum. I have not found which. The bequest is the residual behind a $145k spending floor on $2M of assets, so the percentage is inflated; in absolute terms the gap is $15k.
- **jordans (φ=1) +2.7% and +3.7%: not confirmed.** Owl's exact modes gave *lower* values than its loop here (3,978,469 and 2,996,389, both "oscillatory"), so they are no reference [run]. I did not investigate further.
- **Draw excess:** levels force one level of slack, and the final plan's taxable draws exceed the cash need by these PV totals. That is optimistic: the excess should stay in the taxable account and pay drag. It is large in jon+jane ($121k: the fine path DP finds no consistent path and the coarse one is used), the jordans and kim+sam (all with forced deposits) [run]. Bounding its effect on the objective needs a run that charges it, which I have not done.
- **Speed: the taxable state makes the EM slower than Owl.** 0.7–5.2 s against Owl's default loop at 0.04–1.3 s, and against 0.02–0.21 s for the §7 one-state EM [run]. A second continuous state, coupled to the first through the draw limit and liquidity, is no longer a cheap DP. The exact Owl modes it can stand in for take 51–93 s on morgan and the jordans [run].

### 8.3 What this says about the collapse [inferred from the runs above]

- The penalty and the conversion caps keep the one-state structure. The penalty is a floor on x_n plus a known cost; the cap is a limit on the Roth share of x_n. Both should have been in the EM from the first version.
- The taxable account does not collapse. With it as a state, the EM's accounting matches Owl's, and its optimum moves to within 1% of Owl in most cases. But the solver needs alternation, damping and slack to get there, and it ends up slower than Owl. For the household's decisions, the one-state EM (§7) is the fast screen and Owl remains the model of record.

## 9. Follow-up 3 (2026-10-04): seeding Owl's loop from the one-state EM's plan

`seed.py` → `seed_results.jsonl`, `seed_phi1.jsonl`. The one-state EM (`taxable=False`, penalty on) solves first. Two ways of handing its plan to Owl, both on the original cases:

- **Seeded:** Owl's loop starts from the parameters the EM's plan implies, instead of Ψ = 0.85 and zero IRMAA, ACA and NIIT. These are Ψ_n, M_n (`tx.mediCosts`), ACA_n (`tx.acaCosts`) and J_n, all from the EM's MAGI path. Only the starting point changes.
- **Pinned:** Owl solves with each year's tax-deferred recognition (Σ_i w_i1n + x_in) held within one EM grid step of the EM's schedule. Owl chooses everything else (which account, conversions vs withdrawals, deposits) and does its own accounting. The result is Owl's value of the EM's plan.

| Case | Owl default | Seeded | Pinned | Pinned residual | EM (one-state) |
|---|---:|---:|---:|---:|---:|
| alex+jamie | 228,369 | 0.00% | −0.08% | 1,200 | 231,466 |
| bill | 36,666 | 0.00% | 0.00% | 0 | 36,666 |
| cameron | 18,996 | 0.00% (residual 29,773 → 149) | 0.00% | 20,644 | 18,996 |
| chris+pat | 116,916 | 0.00% | +0.22% | 1,409 | 117,616 |
| dana | 81,228 | +0.01% | +0.01% | 1,218 | 81,416 |
| devon | 248,306 | 0.00% | −0.03% | 0 | 249,748 |
| helen+ruth | 194,069 | 0.00% | +0.19% | 768 | 197,867 |
| jack+jill | 102,545 | 0.00% | +0.35% | 1,101 | 103,667 |
| joe | 92,575 | +0.01% | −0.22% | 1,528 | 95,662 |
| john+sally | 16,803 | +2.99% | (invalid: unsolvable iterate) | 190,213 | 43,474 |
| jon+jane | 160,677 | 0.00% | −0.55% | 0 | 161,642 |
| jordan+taylor (φ=1) | 4,220,573 | 0.00% | −0.40% | 0 | 4,411,886 |
| jordan+taylor-qcd (φ=1) | 3,111,557 | 0.00% | +0.84% | 0 | 3,282,501 |
| kim+sam-bequest | 1,944,071 | +0.05% | +0.22% | 887 | 2,028,525 |
| kim+sam-spending | 185,949 | +0.01% | +0.09% | 1,392 | 187,351 |
| morgan | 38,744 | 0.00% | **+10.40%** | 18,727 | 43,442 |
| robin | 44,013 | +0.01% | +0.07% | 982 | 42,888 |

Readings [run unless marked]:

- **Seeding does almost nothing.** It moves the result by at most 0.05% in 16 of 17 cases. The exception is john+sally, where it lands on a better fixed point (+3.0%, residual $970). It does not help morgan. The LP treats the seeded costs as constants and drifts back to the same fixed point within a few iterations [mechanism inferred from Owl's loop design]. It does tighten cameron's residual from $29,773 to $149 at the same value.
- **Pinning makes morgan's gain real in Owl's own accounting.** Owl's value of the EM's schedule is 42,773 (+10.4%). Its residual is in SS taxability. With Ψ fixed at 0.85 in both runs, which overstates the tax in both, the pinned run gives 42,584 against Owl's 38,049 (+11.9%), with zero ACA residual. Owl's exact `withACA="optimize"` at Ψ = 0.85 reaches 43,568 in 11.5 s. So the pinned EM plan gets within 2.3% of the exact optimum, at the cost of the EM (0.5 s) plus one ordinary loop (0.1 s).
- **Elsewhere pinning is −0.55% to +0.84%.** It gains in 9 cases and loses in 6. The losses are joe, jon+jane, jordan+taylor (φ=1), alex+jamie, devon and jordan+taylor (φ=0.28, not in the table: −0.41%), mostly the cases where the one-state EM ignores taxable drag and conversion caps that the §8 model showed matter.
- **john+sally pinned is not a result.** The loop ended on an unsolvable iterate with a residual of $190k.

**Practical form** [inferred]: run Owl's default loop and the pinned loop and keep the better plan. That costs the one-state EM plus a second loop, 0.1–2 s in total on these cases. It catches morgan-type failures of the loop (+10%) and never loses anything, since the default plan is kept when pinning loses.

## 10. Follow-up 4 (2026-10-04): stock `dev`, seeded pinned loop, upstream drafts

Drafts: `../issue-envelope-model.md` (the one-state EM as a design proposal) and `../issue-pinned-loop.md` (the second loop). Both cite only runs on stock upstream `dev` `c1e5619` (worktree with `PYTHONPATH=<dev>/src EM_EXAMPLES=<dev>/examples`), raw output in `dev/`, scripts at commit 8927703. The §8 two-state model is left out of both: it is slower than Owl and its rounding slack (`draw_excess`) was never charged.

What changed since §9 [run unless marked]:

- **Seeded and pinned together** (`seed.seeded_pinned_solve`, column `seeded_pinned` in `dev/seed_results.jsonl`). Same values as pinned alone, except john+sally: the unseeded pinned loop starts at Ψ = 0.85 with zero IRMAA, ACA and NIIT and ends on an unsolvable iterate; seeded, it converges at 11,023 (residual $1,044) against Owl's 16,803. The drafts use this variant.
- **john+sally is explained.** The EM recognizes nothing in 2032–2037 (SS 41–47% taxable instead of 85%) and runs the liquid pool down to $1,367. Owl taxes the taxable account and cannot fund the $145k floor on that schedule: pinned with no headroom above the EM's recognition, the LP is infeasible (`band.py` → `dev/band.jsonl`). With one step of headroom it is 11,023. So the §8 "unexplained" gap is assumption (b). The exact `withSSTaxability="optimize"` run started for this question (maxTime 600 per MILP) did not finish in 25 minutes on dev or the fork; the drafts do not use it.
- **Where the EM's own value goes** (`pin_check.py` → `dev/pin_check*.jsonl`): EM value − Owl's value of the EM schedule = band deviations (EM's valuation of Owl's ±1-step deviations, ≥ 0 by construction) + taxable-account tax on that plan + accounting gap. The taxable-account tax is the largest part in most cases.
- **morgan, on dev** (`morgan_aca.py`, `morgan_psi.py`): default pays the full $14,000 benchmark in 10 of 11 ACA years ($141,655 in total, today's $); pinned keeps 9 years at 142–169% FPL ($36,604). With Ψ = 0.85 in both runs, seeded pinned 42,250 vs 38,049 (+11.0%), all non-SS residuals 0 except $10 LTCG.
- **Correction to §9:** `withACA="optimize"` is not a reference for morgan. It uses a different rule from loop mode (each band's top rate, 2.10% below 138% FPL instead of the full premium; `../issue-aca-optimize-rates.md`), and on `dev` it leaves an ACA residual of $88,967. The drafts compare at fixed Ψ instead.
- **Pin band:** holding recognition at or below the EM's (`EM_BAND=1,0` or `0,0`) gives morgan 42,345 (monotonic, residual $925–1,346) and makes john+sally infeasible; the drafts keep ±1 step.
- **HSA:** at φ = 1 the jordans' HSA ends at 0 (`hsa_estate.py`), so the HSA cap is not part of their φ = 1 gap. At φ = 0.28 it ends at $185–193k nominal ($28–29k heirs' tax, today's $).
