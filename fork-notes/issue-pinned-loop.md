# Draft upstream issue (mdlacasse/Owl): design proposal, a second loop pinned to the one-dimensional DP's schedule

**Not filed.** Builds on `issue-envelope-model.md` (file that one first and replace "the companion issue" below with its number). All numbers are from stock `dev` at `c1e5619` unless marked as fork, produced by the scripts in `fork-notes/envelope/` at fork commit `8927703`; raw output in `fork-notes/envelope/dev/`.

**Title:** Proposal: re-solve with each year's tax-deferred income held near a schedule optimized over the SS, IRMAA and ACA thresholds, and keep the better plan

---

The self-consistent loop can settle where a threshold is costing the plan money, because each LP prices SS taxability, IRMAA, ACA and NIIT with the previous iterate's values and never sees what moving across the threshold would save. The companion issue describes a one-dimensional DP that prices those thresholds exactly, at the cost of three simplifying assumptions. Its own objective overstates, mainly because it leaves out tax inside the taxable account. Its yearly schedule, though, can be handed to Owl, which then does the accounting with its full model. On `Case_morgan` that finds a plan with 10.2% more spending than the default solve.

## Proposal

After the default solve:

1. Compute the DP's schedule x_n (tax-deferred withdrawals plus Roth conversions in year n), and the loop parameters it implies: Ψ_n, IRMAA premiums (`tx.mediCosts`), ACA costs (`tx.acaCosts`) and NIIT, from the schedule's MAGI path.
2. Solve again with one extra row per year, which holds the year's recognition within one DP grid step h_n of the schedule, and with the loop started from those parameters instead of Ψ = 0.85 and zero costs. Owl chooses everything else: which account, conversions versus withdrawals, deposits, and the taxable account with its own tax.
3. Keep the second plan only if its objective beats the default's by more than a threshold, and report which plan was kept.

The row, as our prototype adds it next to the Roth maturation constraints:

```python
for n in range(self.N_n):
    row = self.A.newRow()
    for i in range(self.N_i):
        row.addElem(self.vm["w"].idx(i, 1, n), 1)   # tax-deferred withdrawals
        row.addElem(self.vm["x"].idx(i, n), 1)      # Roth conversions
    self.A.addRow(row, max(0.0, x_em[n] - h[n]), x_em[n] + h[n], tag=("em_pin", n))
```

When no family runs in loop mode (every one set to `"optimize"` or fixed), the problem is already solved exactly and an extra constraint can't improve it, so step 2 would be skipped.

## Results on `dev`

Shipped examples, each case's own options. "Seeded only" starts the loop from the DP's parameters without the extra rows. Residual is the loop's fixed-point residual over the horizon (the sum of `fixedPointResidual`), in dollars.

| Case | Owl | Seeded only | Pinned | Pinned vs Owl | Residual, Owl | Residual, pinned |
|---|---:|---:|---:|---:|---:|---:|
| alex+jamie | 228,369 | 0.00% | 228,218 | −0.07% | 802 | 1,140 |
| bill | 36,666 | 0.00% | 36,666 | 0.00% | 0 | 0 |
| cameron | 18,996 | 0.00% | 18,996 | 0.00% | 29,773 | 108 |
| chris+pat | 116,916 | 0.00% | 117,175 | +0.22% | 1,459 | 1,222 |
| dana | 81,228 | +0.01% | 81,255 | +0.03% | 3 | 907 |
| devon | 248,306 | 0.00% | 248,223 | −0.03% | 0 | 0 |
| helen+ruth | 195,105 | 0.00% | 195,402 | +0.15% | 1,026 | 756 |
| jack+jill | 102,577 | 0.00% | 103,056 | +0.47% | 7,556 | 3,178 |
| joe | 93,044 | +0.01% | 92,848 | −0.21% | 0 | 1,555 |
| john+sally | 16,803 | +2.99% | 11,023 | −34.40% | 0 | 1,044 |
| jon+jane | 160,677 | 0.00% | 159,787 | −0.55% | 0 | 0 |
| jordan+taylor | 1,530,120 | 0.00% | 1,523,916 | −0.41% | 0 | 0 |
| jordan+taylor-qcd | 1,180,200 | 0.00% | 1,179,087 | −0.09% | 0 | 1 |
| kim+sam-bequest | 1,944,071 | +0.05% | 1,949,282 | +0.27% | 814 | 1,807 |
| kim+sam-spending | 185,949 | +0.01% | 186,130 | +0.10% | 1,344 | 1,561 |
| **morgan** | 38,744 | 0.00% | **42,704** | **+10.22%** | 1,794 | 3,613 |
| robin | 44,070 | +0.02% | 44,093 | +0.05% | 992 | 9,860 |

Spending basis or bequest in today's dollars. john+sally's bequest is what is left after a $145k spending floor; −34.4% is −$5,780. The DP needs beneficiary fractions of 1 for its own value, but the pinned loop doesn't: Owl does the accounting, so the two jordan cases run with their shipped 0.28.

**morgan.** The default loop pays the full benchmark premium, $14,000 a year in today's dollars, in 10 of the 11 ACA years. Its MAGI is 417–437% FPL in 2026–2031, above the 400% cliff, and 133% FPL in 2033–2036, below 138%, where loop mode charges the full premium. The pinned plan keeps 9 of the 11 years at 142–169% FPL and concentrates income in 2029–2030. ACA costs fall from $141,655 to $36,604 in today's dollars (`morgan_aca.py`).

The gain is not lagged costs undercharged by the loop. With SS taxability fixed (`withSSTaxability=0.85`) in both runs, so that SS is not looped, the pinned plan gives 42,250 against 38,049 for the default (+11.0%). Every remaining residual is zero, ACA and IRMAA included, except $10 of LTCG in the pinned run (`morgan_psi.py`). On our fork, which also carries the fix for the 133–150% FPL band we reported, the default-options comparison gives 38,744 against 42,773 (+10.40%).

**The pin is what does it.** Started from the DP's parameters without the rows, the loop lands within 0.05% of the default in 16 of 17 cases, morgan included (38,746). The exception is john+sally, +2.99%.

**The seed is what keeps the pin solvable.** Without it, the pinned loop's first LP charges Ψ = 0.85 and no IRMAA, ACA or NIIT cost, against a schedule chosen under its own, different costs. On john+sally that run ends on an unsolvable iterate. Seeded, it converges with a residual of $1,044 (`seed.py`, columns `pinned` and `seeded_pinned`).

**Elsewhere the pinned plan is within −0.55% to +0.47%,** and john+sally loses $5,780. There the DP's schedule depends on the taxable account being untaxed (companion issue), and the rule keeps the default plan.

**Threshold.** Four of the seven gains below 1% come with a larger residual than the default's (dana, kim+sam-bequest, kim+sam-spending, robin). robin's +0.05%, $23 a year, comes with a residual of $9,860 against $992. A gain that small does not show that the pinned plan is better. On these examples, any threshold from 0.5% to 10% switches to the pinned plan for morgan only.

## Cost

One DP and one more loop. On these examples they add 0.06–1.5 s to a solve, between 0.5 and 4.8 times the default solve's own time. The DP takes 0.01–0.68 s (morgan is the slowest) and the second loop 0.04–1.4 s (single runs on an idle 4-core container; `t_default`, `t_em` and `t_seeded_pinned` in `seed.py`'s output).

## Questions for you

1. On by default, or an option (e.g. `withPinnedLoop`)? It adds the time above to every loop-mode solve.
2. A fixed threshold (1%), or one tied to the loop's convergence tolerance?
3. Should the report show both objectives when the default is kept, so a user sees how close the alternative came?

**Repro.** Against a `dev` checkout:

```bash
git clone https://github.com/mdlacasse/Owl.git owl-dev && git -C owl-dev checkout c1e5619
git clone https://github.com/fmateoc/Owl.git owl-fork && git -C owl-fork checkout 8927703
DEV=$PWD/owl-dev; cd owl-fork/fork-notes/envelope
PYTHONPATH=$DEV/src EM_EXAMPLES=$DEV/examples python seed.py      # table: default, seeded, pinned, seeded_pinned
PYTHONPATH=$DEV/src EM_EXAMPLES=$DEV/examples python morgan_aca.py
PYTHONPATH=$DEV/src EM_EXAMPLES=$DEV/examples python morgan_psi.py
```

`seed.py` monkeypatches `Plan._computeNLstuff` (seed) and `Plan._add_roth_maturation_constraints` (rows); "Pinned" in the table is its `seeded_pinned` column.
