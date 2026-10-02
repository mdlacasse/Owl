# Phase 1 revised after the upstream fix (2026-09-29)

Fork-only planning note. Not part of any upstream PR; cherry-pick around it.

## What upstream did (mdlacasse/Owl, `main` = `dev` = fb539f4)

| Upstream commit | Content |
|---|---|
| 81bc8d6, d4cbac4 | State base is AGI: `− e_n` added to the `state_taxable_income` row. Under `withSSTaxability="optimize"` the SS exclusion goes through `tss`. States that follow the federal standard deduction (`standard_deduction = "federal"`: AZ CO DC IA ID MO MT ND NM) take this year's federal amount with the 65+ additions, and `senior_deduction` says whether they also take the OBBBA $6,000. |
| 940f427 | LTCG added to the fixed-point residual (`U_n` against `_ltcg_tax_implied()`). |
| (dev) | Big-M constants replaced by derived bounds (`_incomeCeiling`); `bigM*` options retired; `EPSILON` 5e-7; engine provenance in results. |

## Our three PRs against that

| PR | Verdict | Why |
|---|---|---|
| 1 state base | **Dropped.** | Same row change and same `tss` change as upstream. Our `income_base = "federal_taxable"` is superseded: it only chose whether to subtract `e_n`, so it could not express the age-65 additions or the senior bonus that `"federal"` handles. Our tests for it went with it. |
| 2 typed params + `indexed` | **Re-applied** (`ad4452d`). | Upstream has nothing equivalent. `federal_deduction()` is kept (upstream tests call it) and its two flags now also ride on the dataclass. `income_base` and the unused `recapture` field are gone. |
| 3 SC registry | **Re-applied** (`58fd9a8`). | One conflict, the residual `moves` list; resolved by keeping upstream's LTCG line beside the registry loop. The LTCG residual is a check on an implied value, not a fed-back parameter, so it does not belong in `_SC_PARAMS`. Also replaced an upstream `trace["M_n_lp"]` truthiness test with `trace["solutions"]`. |

## The maintainer's comment, point by point

**"A good compromise would be a fixed rate with a given threshold."**
The `brackets` local type already contains it: `[[0, 0], [T, r]]` is tax = r·max(0, base − T). NYC needs four brackets and is exact with the same type. Nothing in the design depends on income type: NYC and MD-county tax are functions of state taxable income, and the Yonkers surcharge is a function of net state tax. So the "capital gains vs pensions vs other" plumbing he wants to avoid is not needed. Kept as designed. What changes: scope statements. Wage-only local taxes are out of scope and documented as such (he says they are the majority of the ~4,600; I have not checked jurisdictions individually).

**"Switching states in the middle of the plan."**
Taken. It is relevant to this household, and a Roth-conversion optimizer that sees NY rates now and none later (or the reverse) is the useful case. It also decides the shape of two later pieces, so it goes before them:

- `Plan.state` is a scalar. Most state parameters are already per-year arrays; the scalars are `tax_ss`, `conv_ok`, `fed_sd`, `senior_bonus`, the pension-pooling test at `plan.py:_add_state_taxable_income` (reads the TOML by `self.state`), and `st_lp`. These become per-year.
- Residency becomes a schedule of `(from_year, state, locality)`. The local-tax layer is built per-year from the start, so it needs no second pass.
- Phase 2 (property tax, rent) attaches to the same schedule: a residence period, not a global setting.
- Granularity is the calendar year: the state in force on 31 Dec governs the whole year. No part-year apportionment; documented.

**"There was a lot of flux in the big-M bounds."**
Recapture optimize mode needs a big-M. `_ceiling_n` survives and is what NIIT/Medicare/ACA now use (`M_niit = max(self._ceiling_n[n], T)`), so the design stands, but it is the part most likely to conflict with in-flight upstream work. Moved to last and split off. Loop mode does not touch MIP code.

## Revised Phase 1 order (all stacked on upstream/main `fb539f4`)

Upstream re-checked 2026-09-29 13:30 UTC: `main` and `dev` are both still `fb539f4`; the only newer ref is a dependabot PR (#148, `astral-sh/setup-uv` bump). Nothing to merge.

Later the same day `dev` moved to `0aabf00` and is merged into this branch: our NJ padding fix taken upstream as #149 (our duplicate dropped), and loop-invariant constraint caching (#151: builders marked `@_fixedAcrossIterations` are built once per solve and replayed). None of our state, recapture or local-tax builders are in the replayed set; `test_replayed_rows_match_a_fresh_build_with_recapture_local_tax_and_a_move` guards that. CONTRIBUTING now says to branch from and target `dev`, so PRs from here go against `dev`.

Found while checking the Phase 0 files: a married case without `pension_indexed` crashes on stock `dev` (fixed here in `3062ae5`; issue drafted in `fork-notes/issue-pension-indexed.md`).

Phase 0 templates: `fork-notes/phase0/` (placeholders only); filled-in copies go in the gitignored `otherFiles/`.

| # | Piece | Commit | State |
|---|---|---|---|
| 1 | State base | upstream `81bc8d6`, `d4cbac4` | Ours dropped. |
| 2 | Typed params + `indexed` (NY non-indexed) | `ad4452d` | Done. |
| 3 | SC registry | `58fd9a8` | Done. |
| – | Padding fix for unequal Single/MFJ bracket counts (NJ top bracket taxed at 0%) | upstream `0aabf00` | Taken upstream as #149; ours dropped in the merge. |
| 4 | Residency schedule (`basic_info.moves`) | `8849a3d` | Done. |
| 5 | Local layer (`taxes_local.toml`; `basic_info.locality`) | `14d0b57` | Done. NYC schedule and Yonkers 16.75% checked against the 2025 IT-201-I. |
| 6 | NY benefit recapture, loop mode | `fe7fba3` | Done. Tier amounts reproduce every constant on the 2025 worksheets. |
| – | Summary/Taxes-sheet breakdown of recapture and local tax | this commit | Done (shown only where nonzero). |
| 7 | Recapture, optimize mode | – | Not started. Needs a gate binary per tier because of the notch (below). Waiting on upstream: ask whether the MIP bounds have settled. |

Still open outside Phase 1 proper: filling in the Phase 0 case (templates in `fork-notes/phase0/`), and a generic NY example case under `examples/` for the tests the original plan called for.

## Recapture: sources and behaviour

Source: IT-201-I (2025), tax computation worksheets 1-10, read from tax.ny.gov; NYS-50-T-NYS (1/26) for the 2026 rates and AGI thresholds. The 2026 worksheets are not published, so 2026 amounts are derived from the 2026 brackets by the same rule, not checked against printed constants.

- Rule (`tax_state.state_recapture`): above AGI 107,650 the benefit of the lower brackets phases in over 50,000 of AGI, tier by tier; tier amounts follow from the brackets, so rate changes need no data edit.
- Notch: when taxable income crosses a tier threshold while AGI is inside that tier's phase-in (or above it), the worksheet tax jumps by the phased-in part of the increment. This is what the printed worksheets compute; pinned in a test.
- Loop mode charges the amount; the LP does not see the marginal cost, so it does not steer conversions out of the phase-in range. That is what step 7 is for.
- Not modeled: the flat 10.9% above 25M AGI; part-year NYC/Yonkers; NYC household and school-tax credits.

## Loop-mode behaviour worth knowing

Synthetic NY couple (62/62, $1.95M pre-tax/taxable, SS at 67), `maxSpending`, checked by running the same five residencies twice:

| Residency | `withMedicare="loop"` (default SS loop) | `withMedicare="None"`, `withSSTaxability=0.85` |
|---|---|---|
| NY throughout | 124,921 | 127,690 |
| NY, FL from year 5 | **124,179** | 128,405 |
| NY, FL from year 1 | 126,178 | 128,815 |
| FL throughout | 126,615 | 128,895 |

Under the default loop, moving after five years scored below staying, and Roth conversions differed by 2x. With the two loop-fed quantities pinned the LP is exact and the order is monotone, as it must be. So the anomaly is the self-consistent loop settling on different fixed points, not the residency layer. Compare residency scenarios under the same solver options, and do not read differences under about 1% as decisions unless an exact mode agrees. The demo script is not in the repo; the numbers are a sanity check, not a result about any real household.

## Stock-upstream search for the loop anomaly (2026-09-29, on `fb539f4`)

Question: on upstream code alone, does a change that can only help ever lower the objective by more than the ~0.25% that upstream already accepts as the cost of `epsilon`?

1. All 17 shipped cases, each with its own solver options; levers +$5k/+$20k/+$50k taxable, +$20k tax-free, +$20k tax-deferred, and state→FL where the case has an income-tax state: no drop at all (threshold 0.005%).
2. All 17 cases, taxable balance swept in $1k steps over $40k (41 solves each): drops in two cases only, both small:
   - `Case_chris+pat`: 5 of 40 steps, worst -0.074% (118,603 → 118,516 $/yr).
   - `Case_jack+jill`: 2 of 40 steps, worst -0.088% (102,742 → 102,652 $/yr).
3. The synthetic NY couple from the residency check, NY vs FL at taxable balances $100k-$1M (19 points, default loop and `withMedicare="loop"`): FL never below NY.

Verdict: not worth an issue. The drops are the loop noise upstream already documents (chris+pat is the case their `epsilon` changelog entry names) and sit well under the 0.1-0.25% they state. The 0.6% NY→FL-at-year-5 gap from our residency check did not reproduce with anything stock can express. Mention it in the residency PR description instead. Scripts were one-off (scratchpad), not committed.

## Reassessment, 2026-10-02 (after merging upstream 2026.10.1)

Merged `upstream/dev` at `a85ff76`: #155 (`pension_indexed`/`pension_ages` defaults; our identical fix and tests dropped) and a new MCP state-tax explanation, adapted here (`d0d171e`) for moves, locality, recapture and local tax. Suite: 2674 passed, 1 skipped.

**How upstream takes contributions.** Both of our reports (#149, #155) were implemented by the maintainer from the issue, with credit, rather than merged as PRs. So: one issue per finding, with a repro and a minimal patch; larger features as a design issue that points at this branch. Not a stack of PRs.

**Stakes, measured** (synthetic NY couple, born 1964, SS at 70, $300k taxable, $150k Roth, `maxSpending`, Medicare off and SS taxability pinned at 0.85 so the LP is exact; lifetime, today's dollars):

| Tax-deferred | NY tax, statutory (non-indexed) | NY tax, as upstream (indexed) | Difference | Spending | Recapture (loop) |
|---|---:|---:|---:|---:|---:|
| $1.5M | 30,671 | 13,345 | +17,326 | -420/yr | 81 |
| $2.5M | 96,335 | 69,499 | +26,836 | -763/yr | 6,372 |

Evidence that the NY amounts are statutory dollars: the 2025 IT-201-I rate schedule and the 2026 withholding tables use the same thresholds (MFJ 17,150 / 23,600 / 27,900 / 161,550 / 323,200; recapture start 107,650); only the rates changed.

**Recapture optimize mode: dropped from Phase 1.** On the same couples, plus Yonkers, a grid of Roth-conversion caps (0-300k/yr) never beat the uncapped loop-mode plan: regret 0 in all four. The recapture the optimizer ends up paying is $81-$6.4k over the whole plan, so even a perfect MILP could recover only part of that, at the price of a gate binary per tier per year in code upstream is still changing. A caveat on the evidence: one lever (the conversion cap) was searched, not every year-by-year schedule.

**Revised priorities**

1. Filed as #157: *NY amounts are inflated though NY does not index them* (patch = `indexed` flag, `ad4452d`). Largest correctness effect found so far for NY users.
2. Filed as #158: *NY benefit recapture missing* (rule verified against every 2025 worksheet constant; reference implementation `fe7fba3`).
3. Filed as #159: design proposal for residency moves and the local layer, with six questions for the maintainer.
4. Next fork work, for the household's decision: **NJ retirement-income exclusion** (pulled forward from Phase 7). Without it Owl overstates NJ tax for retirees below its income cliffs, which biases exactly the NY-vs-NJ comparison Phase 0 runs; the stakes look like thousands per year, against recapture's hundreds (estimate, to be checked against the NJ-1040 instructions, which needs `www.nj.gov`/`www.state.nj.us` on the allow list). Same structure as recapture: an AGI-gated amount computed in the loop.
5. Then Phase 2 (property tax and housing ledger), which the original analysis already expected to outweigh every income-tax difference.

**Design consequences**

- Keep `_SC_PARAMS`, the residency schedule and the local layer as they are.
- Generalise the recapture plumbing into "AGI-gated state amounts" when the NJ exclusion lands (one loop quantity per state rule, both computed from `st_agi_n`/`st_ti_n`), rather than adding NJ-specific code paths.
- Residency and locality comparisons: decide on differences above ~1%, or rerun with Medicare and SS taxability exact, as the loop-noise section says.
