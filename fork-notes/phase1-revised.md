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

| # | Piece | Commit | State |
|---|---|---|---|
| 1 | State base | upstream `81bc8d6`, `d4cbac4` | Ours dropped. |
| 2 | Typed params + `indexed` (NY non-indexed) | `ad4452d` | Done. |
| 3 | SC registry | `58fd9a8` | Done. |
| – | Padding fix for unequal Single/MFJ bracket counts (NJ top bracket taxed at 0%) | `983fcb2` | Done. Upstream bug; a good first PR to send. |
| 4 | Residency schedule (`basic_info.moves`) | `8849a3d` | Done. |
| 5 | Local layer (`taxes_local.toml`; `basic_info.locality`) | `14d0b57` | Done. NYC schedule and Yonkers 16.75% checked against the 2025 IT-201-I. |
| 6 | NY benefit recapture, loop mode | `fe7fba3` | Done. Tier amounts reproduce every constant on the 2025 worksheets. |
| – | Summary/Taxes-sheet breakdown of recapture and local tax | this commit | Done (shown only where nonzero). |
| 7 | Recapture, optimize mode | – | Not started. Needs a gate binary per tier because of the notch (below). Waiting on upstream: ask whether the MIP bounds have settled. |

Still open outside Phase 1 proper: the Phase 0 baseline case for the household (TOML + HFP), and a generic NY example case under `examples/` for the tests the original plan called for.

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
