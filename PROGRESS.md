# Owl fork — progress (as of 2026-10-03)

Fork-only file, like `CLAUDE.md`; not for upstream. Keep it current at the end of each work session.

Fork `fmateoc/Owl`, branch `claude/optimistic-darwin-n5xykl` (continued from `claude/relaxed-turing-xzrv89`, itself from `claude/inspiring-rubin-f0a0p9`), merged with upstream `dev` at `a85ff76` (2026.10.1; nothing newer upstream on 2026-10-03).
Plan details: `fork-notes/phase1-revised.md`. Scenario commands: `fork-notes/phase0/phase0-scenarios.md`.

## Upstream

| Item | State |
|---|---|
| #147 State tax base included the federal deduction | Fixed upstream (`81bc8d6`, `d4cbac4`); our PR 1 dropped |
| #149 NJ top bracket taxed at 0% (Single, survivors) | Fixed upstream in `dev` (`0aabf00`) with our proposed patch; our copy dropped in the merge |
| #155 Married case without `pension_indexed` crashes | Fixed upstream (`8971005`); our copy dropped in the merge |
| #157 NY amounts inflated though NY does not index them | **Filed**; awaiting upstream (+$17k–25k lifetime NY tax on stock `dev` test couples; draft in `fork-notes/issue-ny-not-indexed.md`) |
| #157 addendum: NJ not indexed either; NJ exemptions missing | **Drafted** as a comment on #157 (`fork-notes/issue-nj-not-indexed.md`; repro run on stock `dev`); user to post |
| #158 NY benefit recapture missing | **Filed**; awaiting upstream (draft in `fork-notes/issue-ny-recapture.md`) |
| #159 Design proposal: mid-plan moves + local tax | **Filed**; awaiting the maintainer's answers to its six questions (draft in `fork-notes/issue-residency-local-design.md`) |
| NJ retirement-income exclusion missing | **Drafted** (`fork-notes/issue-nj-retirement-exclusion.md`); user to file |
| Loop anomaly (NY→FL at year 5 scored below staying) | Not filed: no repro on stock upstream beyond the known ~0.1% loop noise (search recorded in `phase1-revised.md`) |
| Upstream workflow | Branch from and target `dev` (CONTRIBUTING) |

## Phase 0 — baseline case and scenarios

- [x] Templates in the repo, placeholders only: `fork-notes/phase0/` (case template, HFP generator, scenario commands)
- [x] Template checked: solves with placeholder numbers; Yonkers, NJ move, fixed SS ages and the alternate HFP all run
- [ ] Copy the template to `otherFiles/Case_us.toml` and fill in the TODOs (names, DOBs, balances as of `start_date`, basis, PIAs, SLCSP)
- [x] Scenario 4b written and checked: one spouse stops (and may claim SS), the other keeps working full or part time
- [ ] Generate and fill `otherFiles/HFP_us.xlsx`, `otherFiles/HFP_us_2027.xlsx` and `otherFiles/HFP_us_oneworks.xlsx`
- [ ] Run the baseline and the scenario comparisons; record rate method/seed with each

Scenario 4b settings: `aca_start_year` = the year after the worker's last year (family coverage through the job, so one household start year is right); `withSSAges=["<the one who stops>"]` and the worker's claiming age at 67+ while earning above the limit, because the earnings test is not modeled; a PIA per scenario, since extra work years don't raise it in Owl.

Notes: `owlcli compare` applies `--set` to the variant only, so the base case file must be filled in. Save TOML files as UTF-8 (the Windows-1252 em dash broke loading). Keep `basic_info.names` equal to the HFP sheet names. The fork is public: real numbers only in `otherFiles/`. In the NJ scenarios, wages above $3,000 in a year close NJ line 28b (other income), so scenario 4b's working years get only line 28a.

## Phase 1 — state and local income tax

| Step | Commit | State |
|---|---|---|
| State base = AGI | upstream | Done |
| Typed state params; NY not inflation-indexed | `ad4452d` | Done |
| Registry of self-consistent-loop parameters | `58fd9a8` | Done |
| Change of state during the plan (`basic_info.moves`) | `8849a3d` | Done |
| Local tax: NYC brackets, Yonkers 16.75% surcharge (`basic_info.locality`) | `14d0b57` | Done; checked against the 2025 IT-201-I |
| NY benefit recapture, loop mode | `fe7fba3` | Done; reproduces every 2025 worksheet constant; 2026 derived |
| Recapture and local tax in summary and Taxes sheet | `0696df8` | Done |
| Upstream constraint caching (#151) compatibility | merge `d500c1b` | Done; replay test covers recapture/local/moves |
| MCP explain adapted for moves/locality/recapture | `d0d171e` | Done |
| Recapture, optimize mode | — | **Dropped**: zero regret on a conversion-cap grid; lifetime recapture $81–6.4k |
| NJ not indexed; NJ $1,000 exemptions | `20ccb2d` | Done; schedules and exemptions identical in the 2020 and 2025 NJ-1040 instructions |
| NJ retirement-income exclusion (lines 28a–28c, from Phase 7) | `7fcfadf` | Done, MILP (see below) |
| NJ exclusion: free binaries only near the ceilings; 60 s cap that keeps the tiers | `395be10` | Done (user chose: window first, time cap as fallback) |

NJ exclusion, how it is built: one binary per tier per year in which a filer is 62+, in the disaggregated (convex-hull) form. Rejected alternatives, measured on the $1.5M couple: a self-consistent-loop version (2-cycle; the accepted plan undercharged its own NJ tax by $13.9k lifetime), and a big-M-on-income MILP (4–6 s per MILP; with `gap=1e-3` it hit a 30 s limit).

Solve limits (`plan.py`: `RX_WINDOW`, `RX_TIME_LIMIT`): binaries are free only in years whose income in the previous iterate was at most 1.5× the top ceiling ($225k); iteration 0 runs without the exclusion, and the free set (`RXF_n`, an SC parameter) only grows, so at convergence every left-out year is far above $150k, where nothing is excluded. Without `maxTime`, a MILP carrying the binaries stops at 60 s, warns with its gap, and later iterations keep its tiers; `solverGap` reports that gap. The window alone did not fix the $2.5M case (60 s cap hit on all four iterations, 240 s); keeping the tiers did (61 s).

NJ stakes (synthetic couple born 1964, SS at 70, $300k taxable, $150k Roth, `maxSpending`; lifetime state tax in today's $). Medicare off, SS taxability 0.85 (exact LP apart from the exclusion):

| Tax-deferred | Case | Spending ($/yr) | Lifetime state tax | Solve | Gap |
|---|---|---:|---:|---:|---:|
| $1.5M | FL | 126,372 | 0 | 0.1 s | LP |
| $1.5M | NY | 125,093 | 31,585 | 0.1 s | LP |
| $1.5M | NJ, no exclusion (as upstream) | 124,581 | 44,111 | 0.1 s | LP |
| $1.5M | NJ, exclusion | 126,100 | 0 | 4.9 s | 0.01% |
| $2.5M | FL | 161,885 | 0 | 0.1 s | LP |
| $2.5M | NY | 157,985 | 97,427 | 0.1 s | LP |
| $2.5M | NJ, no exclusion (as upstream) | 157,601 | 108,561 | 0.1 s | LP |
| $2.5M | NJ, exclusion | 158,820 | 64,235 | 61.4 s | 0.19% (time cap) |

With `maxTime=600` the $2.5M NJ plan reaches 158,873 (+$53/yr), still 0.09% from proven: the 60 s cap costs little here.

Default options (Medicare and SS loops on):

| Tax-deferred | Case | Spending ($/yr) | Lifetime state tax | Solve | Gap |
|---|---|---:|---:|---:|---:|
| $1.5M | FL | 123,848 | 0 | 0.6 s | LP |
| $1.5M | NY | 122,627 | 31,603 | 0.5 s | LP |
| $1.5M | NJ, no exclusion (as upstream) | 121,907 | 44,121 | 0.4 s | LP |
| $1.5M | NJ, exclusion | 122,438 | 0 | 12.6 s | 0.01% |
| $2.5M | FL | 157,864 | 0 | 0.1 s | LP |
| $2.5M | NY | 153,992 | 97,699 | 0.2 s | LP |
| $2.5M | NJ, no exclusion (as upstream) | 153,609 | 108,828 | 0.2 s | LP |
| $2.5M | NJ, exclusion | 154,519 | 64,032 | 65.3 s | 0.18% (time cap) |

Reading: the exclusion moves NJ by +$530 to +$1,520/yr and removes all $44k of lifetime NJ tax at $1.5M (about 40% of it at $2.5M). NJ vs NY at $1.5M flips sign between the two settings (+$1,007/yr exact, −$189/yr with the loops); that difference is under the ~1% loop-noise band, so the exact setting decides. At $2.5M NJ beats NY under both (+$835 and +$527/yr).

Known limits: NYC household/school credits, part-year residency, the 10.9% NY cliff above $25M AGI, NJ Special Exclusion / disability before 62 / 65+ exemption, NJ line 28b when only one spouse is 62+ (only 28a taken), NJ basis in IRAs. Residency comparisons under ~1% may be loop noise.

## Model review (2026-10-03)

Review of the paper (`papers/owl.tex`) against the implementation: `fork-notes/model-review/README.md`, with repro scripts and raw output in the same directory. Main findings (all upstream code):

- [ ] Loop mode returns a self-consistent plan, not an optimal one. Optimizing IRMAA or SS taxability raised the objective on 9 of 13 examples by up to +1.3% bequest / +2.3% spending, never lowered it.
- [ ] A non-converging loop keeps its highest-objective iterate, whatever its residual (cameron: SS off by $29.8k).
- [x] Bracket fill goes out of order when late cash has no value (constructed case: $1.56M reported vs $0.91M). **Fixed 2026-10-04**: tax tie-break switched on in the loop when a year goes out of order, a final re-solve, and a post-solve check. The 17 examples are unchanged.
- [x] `withACA="optimize"` infeasible where `pct x MAGI > SLCSP` below 400% FPL. **Fixed 2026-10-04**: thresholds clipped at that crossing. Step rates are still open.
- [ ] Pre-existing, found while testing: `test_time_limit_keeps_the_tiers_and_reports_the_gap` fails on `06468de` too. With `maxTime=2` the fixed NJ tier puts 2032 (state AGI exactly $150,000) in the above-ceiling tier, so it claims nothing where the statute allows 25%: $5,402 charged vs $3,330 statutory. Timing-dependent (2 s MILP).
- [ ] SS claiming-age MILP charges every candidate age the same SS tax (taxable SS from the previous iterate).
- [ ] Cost basis omits reinvested dividends (gain fraction 0.76 vs 0.63 after 11 years in the repro); whole-account gain fraction applied to the equity share only.
- [ ] Partial first year: balances are back-projected for growth only, while year-0 flows run full-year.
- [ ] Survivor of a worker who died before claiming gets 82.5% of PIA (rule recalled as 100%; to check in POMS).
- [ ] Paper vs code drift: Roth cap (Ch. 7), IRMAA MAGI expansion signs, Eq. (PI), AMO binaries, decomposition (retired upstream 2026-09-26), big-M, Ch. 11 survivor claim.

Not yet decided: which of these to fix in the fork and which to draft as upstream issues.

## Upstream contributions (maintainer implements from issues; send issue + patch, not PRs)

1. #157 NY non-indexed amounts (patch `ad4452d`) — filed; NJ addendum drafted (patch `20ccb2d`)
2. #158 NY benefit recapture (patch `fe7fba3`) — filed
3. #159 Design issue: residency moves + local tax layer — filed
4. NJ retirement-income exclusion (patches `7fcfadf`, `395be10`) — drafted, ready to file

When upstream lands #157/#158, merge `dev` and drop our duplicates, as with #149 and #155.

## Later phases (from requirements.md)

2 housing ledger (rent vs buy, property tax) · 3 itemized deductions · 4 healthcare cost model · 5 part-time work and SS earnings test · 6 scenario sweep and report · 7 NJ specifics (exclusion done; left: property tax deduction/credit up to $15k, which belongs with Phase 2, and the 65+ exemption)

Next: Phase 2, housing ledger and property tax. NJ's property tax deduction (line 41) or credit (line 56) attaches there.

Phase 5 now has a concrete case to serve: scenario 4b. The earnings test would let `withSSAges` optimize the working spouse too; a per-scenario PIA (or recomputing it from extra work years) would remove the manual PIA step. Medicare past 65 with employer coverage (delayed Part B) only matters if the worker goes past 65.

## Test status

Full suite after the bracket-order and ACA fixes (2026-10-04): 2704 passed, 1 failed, 1 skipped; flake8 clean. The failure is `test_time_limit_keeps_the_tiers_and_reports_the_gap`, which fails the same way on `06468de` (see the model review list above). After the NJ solve limits it was 2700 passed, 1 skipped.
