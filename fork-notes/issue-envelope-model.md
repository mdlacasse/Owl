# Draft upstream issue (mdlacasse/Owl): design proposal, a one-dimensional DP over yearly tax-deferred income

**Not filed.** Companion of `issue-pinned-loop.md`; the two can be filed together, this one first. All numbers are from stock `dev` at `c1e5619`, produced by the scripts in `fork-notes/envelope/` at fork commit `8927703`; raw output in `fork-notes/envelope/dev/`.

**Title:** Proposal: a one-dimensional dynamic program over each year's tax-deferred income, which sees the SS, IRMAA and ACA thresholds the self-consistent loop prices with lagged values

---

The self-consistent loop prices SS taxability, IRMAA, ACA and NIIT with values taken from the previous iterate. Each LP sees them as constants, so it never sees what crossing a threshold costs or saves at the margin, and the loop can settle on a fixed point where a threshold is costing the plan money (morgan below). Under three simplifying assumptions, the planning problem reduces to a one-dimensional problem that does see these costs, and that a dynamic program solves globally. We built it in our fork and measured it against `dev` on the shipped examples. This issue describes the model and what it gets right and wrong. A companion issue proposes the use we think is worth having upstream: starting a second loop from its plan.

## 1. The reduction

Assume:

- (a) every account earns the same return in a given year;
- (b) no tax inside the taxable account (no tax on interest, dividends or realized gains);
- (c) the taxable, Roth and HSA balances form one liquid pool. This follows from (a) and (b), except for the HSA's medical-expense cap.

Then a dollar grows the same wherever it sits, and the only choice left that changes taxes is *when* tax-deferred dollars become ordinary income. Let x_n be the tax-deferred dollars recognized in year n (withdrawals plus Roth conversions) and d_n the discount factor at the plan's own returns. The plan reduces to:

> minimize Σ_n d_n [τ_n(x_n) − ν x_n] subject to Σ_n d_n x_n ≤ D,

where τ_n is the year's whole bill as a function of x_n alone, ν the heirs' rate on tax-deferred money, and D the PV of the tax-deferred balances plus contributions. Spending (`maxSpending`) or the bequest (`maxBequest`) follows from a PV budget identity.

τ_n is tabulated with Owl's own parameters and rules: federal brackets, LTCG stacked on ordinary income, the SS taxability formula, the OBBBA senior deduction and its phase-out, NIIT, state tax from the plan's `st_*` parameters, IRMAA two years later (`tx.irmaaBrackets`, `tx.partB_irmaa_fees`) and the ACA rule of `tx.acaCosts`. Wages, pensions, SS and fixed assets enter as given incomes, read from the plan.

Owl rules that survive the reduction, and are kept:

- RMDs, as a floor on the running PV recognized;
- liquidity: the liquid pool stays non-negative every year (a constraint inside the DP);
- Roth conversion limits: `maxRothConversion`, `noRothConversions`, `startRothConversions`, `stopRothConversions`;
- the 10% penalty on tax-deferred withdrawals before 59½, with the 5-year lock on conversions (`_add_roth_maturation_constraints`). The cash plan is simulated, and penalized withdrawals become a floor on x_n plus a known cost, iterated to a fixed point.

The DP's state is the PV recognized so far, on a grid of about 1/2000 of the tax-deferred budget, rounded up to a multiple of $500. Its decision is the year's recognition. Each year is a min-plus convolution, and a band around the previous solution keeps it fast.

Out of scope by construction: tax inside the taxable account; different returns by account (an `account`-type allocation, or a spread between accounts); beneficiary fractions below 1; the HSA's medical-expense cap; spending slack.

## 2. Results on `dev`

Shipped examples, each case's own options. The two jordan cases ship with beneficiary fractions of 0.28, which the reduction can't represent, so they are compared at 1 (`setBeneficiaryFractions([1, 1, 1, 1])`). The last column is Owl solving with each year's recognition held within one grid step of the EM's schedule. That is Owl's own accounting of the EM's plan, with every Owl constraint kept (the "pinned loop" of the companion issue).

| Case | Objective | Owl | EM | EM vs Owl | EM's accounting of Owl's plan | Owl's value of the EM's schedule | t Owl (s) | t EM (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| alex+jamie | spending | 228,369 | 231,466 | +1.36% | +0.11% | 228,218 (−0.07%) | 0.46 | 0.073 |
| bill | spending | 36,666 | 36,666 | 0.00% | 0.00% | 36,666 (0.00%) | 0.03 | 0.006 |
| cameron | spending | 18,996 | 18,996 | 0.00% | 0.00% | 18,996 (0.00%) | 0.10 | 0.033 |
| chris+pat | spending | 116,916 | 117,616 | +0.60% | −0.01% | 117,175 (+0.22%) | 0.39 | 0.066 |
| dana | spending | 81,228 | 81,416 | +0.23% | 0.00% | 81,255 (+0.03%) | 0.04 | 0.048 |
| devon | spending | 248,306 | 249,748 | +0.58% | 0.00% | 248,223 (−0.03%) | 0.07 | 0.166 |
| helen+ruth | spending | 195,105 | 197,867 | +1.42% | 0.00% | 195,402 (+0.15%) | 0.09 | 0.037 |
| jack+jill | spending | 102,577 | 103,667 | +1.06% | −0.43% | 103,056 (+0.47%) | 2.12 | 0.111 |
| joe | spending | 93,044 | 95,662 | +2.81% | 0.00% | 92,848 (−0.21%) | 0.07 | 0.052 |
| john+sally | bequest | 16,803 | 43,474 | +26,671 | 0.00% | 11,023 (−5,780) | 0.09 | 0.032 |
| jon+jane | spending | 160,677 | 161,642 | +0.60% | 0.00% | 159,787 (−0.55%) | 0.12 | 0.061 |
| jordan+taylor (φ=1) | bequest | 4,220,573 | 4,411,886 | +4.53% | 0.00% | 4,203,652 (−0.40%) | 0.09 | 0.024 |
| jordan+taylor-qcd (φ=1) | bequest | 3,111,557 | 3,282,501 | +5.49% | 0.00% | 3,137,776 (+0.84%) | 0.11 | 0.035 |
| kim+sam-bequest | bequest | 1,944,071 | 2,028,525 | +4.34% | +0.01% | 1,949,282 (+0.27%) | 0.40 | 0.029 |
| kim+sam-spending | spending | 185,949 | 187,351 | +0.75% | 0.00% | 186,130 (+0.10%) | 0.29 | 0.069 |
| morgan | spending | 38,744 | 43,503 | +12.28% | +0.01% | 42,704 (+10.22%) | 0.29 | 0.351 |
| robin | spending | 44,070 | 42,888 | −2.68% | −4.01% | 44,093 (+0.05%) | 0.28 | 0.039 |

Values are the spending basis or the bequest in today's dollars. john+sally's bequest is what is left after a $145k spending floor, so it is shown in dollars rather than percent. "EM's accounting of Owl's plan" feeds Owl's own recognition schedule, and the taxable-account income and penalties Owl booked for it, into the EM's τ and budget identity. Times are single runs on one container.

**The accounting is right.** On Owl's own plan the EM reproduces Owl's objective within ±0.11% in 15 of 17 cases. The two exceptions break assumption (a). jack+jill gives each spouse's accounts their own allocation, and under its historical rates their returns differ by up to 2.9 points in a year. robin holds a different stock/bond mix in each account (`type = "account"`), so its accounts earn from 8.4% to 10.0% in 2026.

**The EM's own value overstates.** Its optimum is 0 to +1.4% above Owl's in 10 cases, +2.8% to +5.5% in joe, kim+sam-bequest and the jordans, and +12.3% in morgan. john+sally is +$26,671. robin is −2.7%, for the reason above. Owl's value of the EM's schedule tells how much of that is real. It is within −0.55% to +0.84% of Owl's own plan in 15 of 17 cases, +10.2% in morgan and −$5,780 in john+sally. The difference between the EM's value and Owl's value of the same schedule splits into three parts, each measured (`pin_check.py`):

| Case | EM | Owl, EM's schedule | Difference | Band | Taxable-account tax | Accounting |
|---|---:|---:|---:|---:|---:|---:|
| alex+jamie | 231,466 | 228,218 | 3,248 | 1,561 | 1,205 | 482 |
| bill | 36,666 | 36,666 | 0 | 0 | 0 | 0 |
| cameron | 18,996 | 18,996 | 0 | 0 | 0 | 0 |
| chris+pat | 117,616 | 117,175 | 441 | 46 | 398 | −3 |
| dana | 81,416 | 81,255 | 161 | 1 | 166 | −6 |
| devon | 249,748 | 248,223 | 1,525 | 684 | 841 | 0 |
| helen+ruth | 197,867 | 195,402 | 2,465 | 289 | 2,182 | −6 |
| jack+jill | 103,667 | 103,056 | 611 | 2 | 903 | −294 |
| joe | 95,662 | 92,848 | 2,814 | 5 | 2,826 | −17 |
| john+sally | 43,474 | 11,023 | 32,451 | 21,974 | 10,825 | −348 |
| jon+jane | 161,642 | 159,787 | 1,855 | 8 | 1,847 | 0 |
| jordan+taylor (φ=1) | 4,411,886 | 4,203,652 | 208,234 | 87,233 | 120,899 | 102 |
| jordan+taylor-qcd (φ=1) | 3,282,501 | 3,137,776 | 144,725 | 28,065 | 116,580 | 80 |
| kim+sam-bequest | 2,028,525 | 1,949,282 | 79,243 | 5,009 | 74,861 | −627 |
| kim+sam-spending | 187,351 | 186,130 | 1,221 | 103 | 1,129 | −11 |
| morgan | 43,503 | 42,704 | 799 | 259 | 152 | 388 |
| robin | 42,888 | 44,093 | −1,205 | 70 | 20 | −1,295 |

- **Band:** Owl may recognize up to one grid step more or less than the EM each year, and it uses that room. The column is the EM's valuation of those deviations. It is never negative, because the EM's schedule is optimal for the EM.
- **Taxable-account tax:** the tax Owl charges inside the taxable account along that plan, which assumption (b) drops. It is the largest part in most cases.
- **Accounting:** the EM's accounting of Owl's plan against Owl's value of it. robin and jack+jill are assumption (a), as above.

**john+sally** is the case where assumption (b) changes the plan, not just its value. The EM recognizes nothing from 2032 to 2037, which keeps 41–47% of SS taxable instead of 85%. It funds those years from the liquid pool, which it runs down to $1,367. Owl taxes the taxable account, so on that schedule it cannot fund the $145k spending floor. Pinned at or below the EM's recognition, Owl's LP is infeasible. With one grid step of headroom ($1,000 in 2026, growing with the plan's returns) it solves, at $11,023 against $16,803 for Owl's own plan (`band.py`). The band column above is the EM's valuation of that headroom.

**morgan** is the case where the loop misses a better plan. Owl's loop pays the full benchmark premium, $14,000 a year in today's dollars, in 10 of the 11 ACA years. MAGI is 417–437% FPL in 2026–2031, above the 400% cliff, and 133% FPL in 2033–2036, below 138%, where loop mode charges the full premium. The EM's schedule keeps 9 of the 11 years at 142–169% FPL. ACA costs fall from $141,655 to $36,604 in today's dollars (`morgan_aca.py`). The companion issue shows the gain survives Owl's own accounting.

**Speed is not the argument.** On these cases the EM takes 0.006–0.35 s and Owl's default loop 0.03–2.1 s. The EM is faster in 14 of 17 cases, but both are well under a second except jack+jill. What the EM adds is a global view of the threshold costs, not time.

## 3. Proposal

A module, e.g. `owlplanner/envelope.py`, that takes a plan Owl has set up and returns the EM's yearly recognition schedule, its value, and the loop parameters that schedule implies (Ψ_n, IRMAA, ACA and NIIT costs from Owl's own functions). It reads everything from the plan's arrays and adds no configuration. Its main use is the companion issue's second loop. It can also be exposed as a diagnostic that reports the EM's value next to Owl's.

The EM is not a second model of record. Its own value overstates by the parts in the table above, so it is not proposed as an estimate to show users.

Questions for you:

1. Would you take a DP module inside the package, next to the LP? The alternative is a script under `tools/` that the second loop calls only when it is installed.
2. The EM reads state tax from the `st_*` arrays as Owl computes them. Is that interface stable enough to depend on, or would you rather it call `st_taxParams` itself?

**Repro.** Our prototype is `fork-notes/envelope/em.py` in our fork; `solve_dp(..., taxable=False)` is the model above. Its second state for the taxable account (`taxable=True`) is not part of this proposal. Against a `dev` checkout:

```bash
git clone https://github.com/mdlacasse/Owl.git owl-dev && git -C owl-dev checkout c1e5619
git clone https://github.com/fmateoc/Owl.git owl-fork && git -C owl-fork checkout 8927703
DEV=$PWD/owl-dev; cd owl-fork/fork-notes/envelope
export PYTHONPATH=$DEV/src EM_EXAMPLES=$DEV/examples
EM_TAX=0 python compare_orig.py                       # first table: Owl, EM, EM's accounting of Owl's plan
EM_TAX=0 EM_PHI1=1 python compare_orig.py Case_jordan+taylor.toml Case_jordan+taylor-qcd.toml
python seed.py                                        # Owl's value of the EM's schedule (seeded_pinned)
python pin_check.py                                   # second table: acct0, acct, pinned
EM_PHI1=1 python seed.py Case_jordan+taylor.toml Case_jordan+taylor-qcd.toml
EM_PHI1=1 python pin_check.py Case_jordan+taylor.toml Case_jordan+taylor-qcd.toml
for b in 1,1 1,0 0,0; do EM_BAND=$b python band.py Case_john+sally.toml; done
python morgan_aca.py
```
