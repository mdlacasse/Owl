# Follow-up comment on mdlacasse/Owl#158 (NY benefit recapture), posted by the user

Status: drafted 2026-10-06 for the user. When we filed #158 we said our implementation "sits on our SC-loop refactor and on a per-year state layer that upstream does not have, so it will not apply as is". Since then upstream has the per-year layer (#159, `st_schedule`, 2026.10.6). This comment offers a patch made on stock `dev` that needs neither of our layers. Patch: `fork-notes/issue-ny-recapture.patch`.

How it was checked (2026-10-06, stock `dev` `b4f1605`):
- `git apply --check` on a clean checkout of `b4f1605`: applies.
- Full upstream suite with the patch: 2720 passed, 1 skipped. flake8 (120 columns): only `localsearch.py:29`, which the patch does not touch.
- Comparison script: `fork-notes/model-review/ny_recap_cmp.py` (run with `PYTHONPATH` set to each checkout).
- Rechecked after the fork merged `b4f1605` (2026-10-06): the patch still applies to upstream's tip (`b4f1605`, unchanged), and the fork and the patched stock `dev` give identical plans in all four runs, and under local search ($2.5M: basis 154,484, lifetime recapture $10,552 in both; `fork-notes/model-review/ny_recap_ls.py`). Without the patch the local-search row was not run.
- Rechecked 2026-10-07 on upstream `5dd1623` (after the comment was posted): the patch applied with line offsets only; `issue-ny-recapture.patch` was regenerated on `5dd1623` and applies without offsets. Upstream suite with it: 2732 passed, 1 skipped. Fork and patched stock still identical; all versions moved by $3-14/yr from upstream's own changes (not isolated):

  | Tax-deferred | Options | Stock | Patched | Fork | Lifetime recapture |
  |---|---|---:|---:|---:|---:|
  | $1.5M | Medicare off, SS 0.85 | 125,056 | 125,053 | 125,053 | 81 |
  | $1.5M | defaults | 122,600 | 122,597 | 122,597 | 81 |
  | $2.5M | Medicare off, SS 0.85 | 158,208 | 157,931 | 157,931 | 6,372 |
  | $2.5M | defaults | 154,198 | 153,938 | 153,938 | 5,955 |
  | $2.5M | defaults + local search | 154,929 | 154,471 | 154,471 | 10,552 |

- The 23 recapture tests (worksheet constants, worksheet 1 by hand, notch, continuity, monotonicity, data, plan-level worksheet tax, loop residual, cash flow, a move to NJ, replayed rows) pass.
- The plans are identical to the fork's implementation, to the dollar, on the NY couple below (exact LP and default options, $1.5M and $2.5M).

---

Following up on this one, since #159 changed what it needs. When I filed it I said our implementation would not apply as is, because it sat on a per-year state layer and on our refactor of the loop parameters. Your `st_schedule` now provides the first, so I rebuilt it on stock `dev` (`b4f1605`) without either. The patch is attached; it applies to `b4f1605` and the full suite passes with it (2720 passed, 1 skipped).

What it touches:

- **Data** (`taxes_state.toml`): `recapture_agi_start = 107650`, `recapture_width = 50000`, `recapture_until = 5000000` on `NY_Single` and `NY_MFJ`, documented in the header. They index with `brackets_indexed`, so they stay nominal for NY.
- **`tax_state.py`**: `state_recapture()` (the rule; it reproduces every constant on the 2025 IT-201-I worksheets, as in the issue), a small `bracket_tax()`, and `st_recapture()`, which reads the three amounts per year with the filing-status switch at the first death. `st_taxParams` keeps its 9-tuple; `st_schedule` gets three more keys (`recap_start_n`, `recap_width_n`, `recap_until_n`, start `np.inf` where there is none), so a move out of NY stops the recapture from that year.
- **`plan.py`**: `STR_n` is a loop quantity like `J_n`: computed in `_computeNLstuff` from the iterate, charged in `_add_net_cash_flow`, added to `st_T_n` (and kept separately as `st_recap_n`), and a `state recapture` family in the fixed-point residual. State AGI comes straight from the LP: it is the state taxable income plus the state deduction claimed, since the `state_taxable_income` row makes that sum equal to federal AGI less the state's own subtractions. So the SS, pension and retirement exclusions don't have to be re-derived. The rest of the `plan.py` diff (about 20 of its 60 changed lines) is carrying `STR_n` through the loop's snapshot, step-back, trace, best-iterate and restore sites, next to `M_n`, `ACA_n`, `J_n` and `Psi_n`.
- **Tests**: `tests/tax/test_state_recapture.py`, 23 tests.

Effect on a NY couple (born 1964, SS $3,000 and $2,400/month at 70, $300k taxable, $150k Roth, conservative rates, `maxSpending`, no bequest), spending basis and lifetime recapture in today's dollars:

| Tax-deferred | Options | Without | With | Lifetime recapture |
|---|---|---:|---:|---:|
| $1.5M | Medicare off, SS 0.85 | 125,066 | 125,063 | 81 |
| $1.5M | defaults | 122,609 | 122,597 | 81 |
| $2.5M | Medicare off, SS 0.85 | 158,221 | 157,945 | 6,372 |
| $2.5M | defaults | 154,211 | 153,952 | 5,955 |
| $2.5M | defaults + `breakpointMethod = "local-search"` | — | 154,484 | 10,552 |

Small for most households, as the issue said, but it is tax NY charges, in every year with NY AGI above $107,650, and it grows with income.

Not in the patch: a Summary or worksheet line for the recapture (it is inside the state tax), and its interaction with personal credits (NY has none in the data). Happy to adjust anything, or to split the loop plumbing differently if you'd rather keep the number of loop quantities down.
