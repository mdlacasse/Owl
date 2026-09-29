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
| 2 typed params + `indexed` | **Re-applied** (ad4452d). | Upstream has nothing equivalent. `federal_deduction()` is kept (upstream tests call it) and its two flags now also ride on the dataclass. `income_base` and the unused `recapture` field are gone. |
| 3 SC registry | **Re-applied** (d3d44dd). | One conflict, the residual `moves` list; resolved by keeping upstream's LTCG line beside the registry loop. The LTCG residual is a check on an implied value, not a fed-back parameter, so it does not belong in `_SC_PARAMS`. Also replaced an upstream `trace["M_n_lp"]` truthiness test with `trace["solutions"]`. |

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

## Revised Phase 1 order (all stacked on upstream/main)

1. ~~State base~~ upstream.
2. Typed params + `indexed`. Done (ad4452d).
3. SC registry. Done (d3d44dd).
4. **Residency schedule.** Per-year state scalars; `setResidency([(year, state, locality)])`; TOML `basic_info.moves`; CLI/`--set`. Single-state plans must produce identical LPs.
5. **State recapture, loop mode** (NY §601(d-1), generic tiers in TOML). `STR_n` joins `_SC_PARAMS`. State AGI expression added to aggregation. Rates re-verified against the 2026 IT-201 worksheets before pinning tests, because NY cut the first five rates for 2026.
6. **Local layer** (`taxes_local.toml`: `brackets` and `surcharge`). Yonkers surcharge multiplies recapture too (IT-201 base is line 39 plus the supplemental tax). Per-year arrays from the start.
7. **Recapture, optimize mode**, after asking upstream whether MIP internals have settled.

Loop mode fixes the recapture *amount* but the LP does not see its marginal effect, so a conversion schedule is not deterred from the phase-in range. That is why step 7 exists; step 5 is still worth having alone because the amounts are otherwise missing entirely (earlier estimate $330–$1,100/yr, computed before the 2026 rate cut and not yet re-verified).
