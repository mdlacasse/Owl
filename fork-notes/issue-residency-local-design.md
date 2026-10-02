# Draft upstream issue (mdlacasse/Owl): design proposal, mid-plan state changes and local income tax

**Title:** Proposal: change of state during the plan, and a data-driven local income tax layer (NYC, Yonkers)

---

Following up on your comment on #147: switching states in the middle of a plan matters to more retirees than local tax does, and for local tax a fixed rate above a threshold covers most cases. We have both working in our fork, with tests. Before preparing anything for `dev`, here is the design, and the choices that are yours to make.

## 1. Change of state during the plan

**Config.** `state` stays the residence in the first plan year. A new optional list gives later moves:

```toml
[basic_info]
state = "NY"
moves = [ { year = 2031, state = "FL" } ]
```

API: `Plan.setStateTax(state, moves=())`, with `moves` as `(year, state)` pairs. `--set 'basic_info.moves=[{"year": 2031, "state": "FL"}]'` works from the CLI.

**Semantics.**

- The state in force on December 31 governs the whole year. There is no part-year apportionment.
- A move must fall after the first plan year and within the horizon, and two moves in the same year are an error. A move to `""` (or to a no-tax state) ends state tax from that year on.
- With no `moves`, the state parameters are identical to today's: a test checks every field against the single-state path for NY, NJ, CO, FL and PA, and no regression baseline moved.

**What changes inside.** The LP is already year-indexed, so only the per-state *scalars* have to become per-year:

- `st_tax_ss`, `st_conv_ok`, `st_fed_sd`, `st_senior_bonus`, and the pension-pooling test in `_add_state_taxable_income`, which today reads the TOML by `self.state`.
- `st_taxParams_schedule(states_n, ...)` builds each state's parameters with the existing `st_taxParams` and takes each year's column from the state in force. It pads the bracket dimension to the longest schedule, using the #149 rule: zero width at the top rate.

**Why it is worth having.** The optimizer sees today's state rates against later ones, so it times Roth conversions and withdrawals around the move. On a NY couple (illustration below), moving to Florida after five years cuts the Roth conversions of those first five years from $485k to $202k.

## 2. Local income tax

A new data file, `data/taxes_local.toml`, has one table per locality, `"<STATE>:<Locality>"`, with `_MFJ` and `_Single` variants where the schedule differs. Two types cover the cases that reach retirement income:

```toml
["NY:NYC_MFJ"]           # graduated rates on the state's taxable income
type = "brackets"
base = "state_taxable"
brackets = [[0.0, 3.078], [21600.0, 3.762], [45000.0, 3.819], [90000.0, 3.876]]
indexed = false

["NY:Yonkers"]           # a percentage of the state's own tax
type = "surcharge"
base = "net_state_tax"
rate = 16.75
```

Your "fixed rate with a given threshold" is the `brackets` type with two rows: `[[0, 0], [T, rate]]`. Wage-only local taxes (most of the ~4,600) do not belong in the file, and its header says so. Adding a locality is data only. The values are checked against the 2025 IT-201-I (NYC rate schedule, Yonkers worksheet). The Yonkers rate also appears in the 2026 Yonkers withholding tables.

**Config:** `basic_info.locality = "NYC"`, validated against the state; blank means none. A move may name a locality, and a locality does not carry over to a new state.

**LP.**

- `brackets`: adds `N_lt` continuous variables per year, bounded by the local widths, with one row per year, `sum(lt_f) = sum(st_f)` (tag `local_taxable_income`), and their rates in the cash-flow row. Nothing depends on income type.
- `surcharge`: no new variables. The state bracket coefficients in the cash-flow row are scaled by `1 + rate`.
- None of these builders is `@_fixedAcrossIterations`. A test compares a replayed build with a fresh one on a plan with a locality and two moves.

**Reporting.** `st_T_n` stays the total sub-federal income tax, so the cash-flow identities, exports and plots need no change. `Plan.lt_T_n` is the local part. The summary and the Taxes sheet show it as a separate line only when it is nonzero, and the MCP explanation reports it per year.

## Illustration

A NY couple born 1964, $300k taxable, $2.5M tax-deferred, $150k Roth, SS at 70, `maxSpending`, `conservative` rates. Medicare is off and SS taxability pinned at 0.85, so the LP is exact. NY amounts are non-indexed and NY recapture is on (the two issues filed separately). Lifetime figures are in today's dollars:

| Residency | Spending /yr | State + local tax | of which local | Roth conversions | in the first 5 years |
|---|---:|---:|---:|---:|---:|
| NY (rest of Westchester) | 158,261 | 96,335 | 0 | 525,606 | 484,586 |
| NY, Yonkers | 157,632 | 112,470 | 16,136 | 517,861 | 478,169 |
| NY, NYC | 155,774 | 160,680 | 64,353 | 496,588 | 460,563 |
| NJ | 158,252 | 90,890 | 0 | 322,720 | 322,720 |
| FL | 162,009 | 0 | 0 | 577,656 | 528,696 |
| NY, then FL from 2031 | 160,496 | 20,857 | 0 | 398,366 | 201,860 |
| NYC, then NJ from 2031 | 157,581 | 102,969 | 15,026 | 340,514 | 201,766 |

NJ is overstated here: its retirement-income exclusion is not in the data. One caution from testing: under the default loop settings, residency variants can differ by up to about 1% from the loop settling on different fixed points rather than from the tax. Comparisons are cleaner with the exact settings used above.

## Choices that are yours

1. **Whole-year residence.** Is the December-31 rule acceptable, or do you want part-year apportionment from the start? It would need income timing within the year, which Owl does not have.
2. **Where local data lives.** A separate `taxes_local.toml`, as above, or tables inside `taxes_state.toml`?
3. **Names.** `basic_info.moves` and `basic_info.locality`.
4. **Reporting.** Local tax folded into `st_T_n` with a separate `lt_T_n`, or its own cash-flow line?
5. **UI.** We added a city dropdown next to the state dropdown, shown only when the state has a locality. Moves are preserved from a file but not editable in the UI. Is that enough for a first version?
6. **Shape of the change.** Ours sits on a refactor that makes `st_taxParams` return a frozen dataclass, with the flags as per-year arrays. The smaller alternative keeps the tuple and adds per-year arrays next to it. Which would you rather review?

## Size and order

In the fork:

- **Moves:** +182 / -55 lines in `src` and `ui`, mostly `tax_state.py` and `plan.py`; 200 lines of tests.
- **Local layer:** +396 / -67, of which `tax_local.py` is 157, `residency.py` 72 and the data file 47; 235 lines of tests.

Suggested order, each behavior-neutral for plans that don't use it:

1. Per-year state parameters (no visible change).
2. Moves.
3. Local layer.

Code: `fmateoc/Owl`, branch `claude/inspiring-rubin-f0a0p9`, commits `8849a3d` (moves) and `14d0b57` (local layer). Later commits on that branch adapt them to #151 and to the MCP state-tax explanation.
