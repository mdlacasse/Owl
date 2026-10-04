# Owl fork — progress (as of 2026-10-04)

Fork-only file, like `CLAUDE.md`; not for upstream. Keep it current at the end of each work session.

Fork `fmateoc/Owl`, branch `claude/project-thread-qx5fy0` (four model-review fixes, 2026-10-04), continued from `claude/project-thread-v39073` (from `claude/optimistic-darwin-n5xykl`, from `claude/relaxed-turing-xzrv89`, from `claude/inspiring-rubin-f0a0p9`), merged with upstream `main` at `c58228e` (2026.10.4, with the #162 fix; contains `dev` `c1e5619`) on 2026-10-04.
Plan details: `fork-notes/phase1-revised.md`. Scenario commands: `fork-notes/phase0/phase0-scenarios.md`.

## Upstream

| Item | State |
|---|---|
| #147 State tax base included the federal deduction | Fixed upstream (`81bc8d6`, `d4cbac4`); our PR 1 dropped |
| #149 NJ top bracket taxed at 0% (Single, survivors) | Fixed upstream in `dev` (`0aabf00`) with our proposed patch; our copy dropped in the merge |
| #155 Married case without `pension_indexed` crashes | Fixed upstream (`8971005`); our copy dropped in the merge |
| #157 NY amounts inflated though NY does not index them | **Fixed upstream** (`3c88ce1`, 2026.10.3: `brackets_/deduction_/exemptions_indexed` flags, per-filer exemptions and credits). **Merged** 2026-10-04: took theirs; our `indexed` flag, NJ exemption data and duplicate tests dropped |
| #157 addendum: NJ not indexed either; NJ exemptions missing | **Posted** by the user on #157; covered by `3c88ce1` (NJ nominal, $1,000 per filer + $1,000 per filer 65+, which our fork did not model) |
| #158 NY benefit recapture missing | **Filed**; awaiting upstream (draft in `fork-notes/issue-ny-recapture.md`) |
| #159 Design proposal: mid-plan moves + local tax | **Filed**; awaiting the maintainer's answers to its six questions (draft in `fork-notes/issue-residency-local-design.md`) |
| #160 NJ retirement-income exclusion missing | **Answered 2026-10-04**: maintainer confirmed the rule against the 2025 NJ-1040 but keeps the state layer a pure LP (no binaries for state rules); NJ stays `retirement_income_exemption = 0`, limitation to be documented (overstates NJ tax, never understates). Open to a broad strategy later that covers similar rules in other states without (much) longer MILP solves. The fork keeps its MILP exclusion: without it NJ ranks below NY for the stakes couple, with it above (exact: $1.5M -$476 vs +$1,007/yr; $2.5M -$323 vs +$903/yr). The drafted follow-up comment (`issue-nj-retirement-exclusion-comment.md`) is superseded; not posted. Reply (`issue-nj-retirement-exclusion-reply.md`) **posted** by the user 2026-10-04; awaiting the maintainer |
| #162 Tax brackets filled top-down where late cash has no value | **Fixed upstream** (`3fca646`, 2026.10.4, on `main`): its `plan.py` change is our patch line for line, and `tests/plan/test_bracket_order.py` is identical. **Merged** 2026-10-04: the fork keeps its own copy, which extends the same code to local brackets (`lt_f`) and the SC registry; nothing to drop (draft `fork-notes/issue-bracket-order.md`) |
| `withACA="optimize"` infeasible where pct x MAGI > SLCSP below 400% FPL | **Drafted** (`fork-notes/issue-aca-optimize-infeasible.md`, patch `.patch`); verified on stock `dev` (patch alone: 2596 passed, 1 skipped). **Filed** as #161; open |
| SC loop: flat objective taken for a 2-cycle; real cycles keep the highest objective | **Drafted** (`fork-notes/issue-cycle-selection.md`, patch `.patch`); repro and patch verified on stock `dev` `c1e5619` (2605 passed, 1 skipped; of 17 examples only cameron, residual $29,773 to $1,302 with the same spending, and jack+jill, -$37/yr with SS/LTCG residual $4,951/$2,604 to $4,429/$65, change). **Filed** as #163 2026-10-04; awaiting the maintainer. Not yet applied in the fork |
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

NJ stakes, rerun 2026-10-04 after merging upstream 2026.10.3, which adds NJ's $1,000 exemption per filer aged 65+. Synthetic couple born 1964-03-15 and 1964-09-15, life expectancies 89 and 92, SS $3,000 and $2,400/month at 70, $300k taxable, $150k Roth, conservative rates, 60/40, `maxSpending`, no bequest; lifetime state tax in today's $. Script: `fork-notes/model-review/nj_stakes.py` (on the pre-merge code it reproduces the tables recorded on 2026-10-03 within $5-14; plans start "today", so balances back-project by a day's growth). Change = merged minus pre-merge (`7394ecc`), same day, runs one at a time.

Exact LP (Medicare off, SS taxability 0.85):

| Tax-deferred | Case | Spending ($/yr) | Lifetime state tax | Change in spending / tax | Solve | Gap |
|---|---|---:|---:|---:|---:|---:|
| $1.5M | FL | 126,361 | 0 | 0 / 0 | 0.1 s | LP |
| $1.5M | NY | 125,083 | 31,582 | 0 / 0 | 0.1 s | LP |
| $1.5M | NJ, no exclusion | 124,607 | 42,619 | +36 / -1,480 | 0.1 s | LP |
| $1.5M | NJ, exclusion | 126,090 | 0 | 0 / 0 | 6.1 s | 0.01% |
| $2.5M | FL | 161,872 | 0 | 0 / 0 | 0.1 s | LP |
| $2.5M | NY | 157,971 | 97,408 | 0 / 0 | 0.1 s | LP |
| $2.5M | NJ, no exclusion | 157,648 | 106,751 | +61 / -1,796 | 0.1 s | LP |
| $2.5M | NJ, exclusion | 158,874 | 63,255 | +58 / -982 | 61.4 s | 0.19% (time cap) |

Default options (Medicare and SS loops on):

| Tax-deferred | Case | Spending ($/yr) | Lifetime state tax | Change in spending / tax | Solve | Gap |
|---|---|---:|---:|---:|---:|---:|
| $1.5M | FL | 123,839 | 0 | 0 / 0 | 0.6 s | LP |
| $1.5M | NY | 122,621 | 31,593 | 0 / 0 | 0.5 s | LP |
| $1.5M | NJ, no exclusion | 121,837 | 42,550 | -60 / -1,559 | 0.5 s | LP |
| $1.5M | NJ, exclusion | 122,427 | 0 | -1 / 0 | 15.0 s | 0.01% |
| $2.5M | FL | 157,850 | 0 | 0 / 0 | 0.2 s | LP |
| $2.5M | NY | 153,979 | 97,678 | 0 / 0 | 0.2 s | LP |
| $2.5M | NJ, no exclusion | 153,659 | 106,918 | +64 / -1,887 | 0.2 s | LP |
| $2.5M | NJ, exclusion | 154,460 | 63,687 | -32 / -404 | 65.8 s | 0.21% (time cap) |

Reading: the senior exemption ($1,000 per filer from 65, nominal, at NJ's marginal rates) is worth about $1.5k-1.9k of lifetime NJ tax without the exclusion, which is +$36 to +$64/yr of spending in the exact runs. With the exclusion at $1.5M there is no NJ tax left to reduce. The two negative spending changes under the loops (-$60, -$32) come with lower tax, so they are loop noise and, at $2.5M, the 60 s cap (gap 0.21%, about $320/yr), not an effect of the exemption. Comparisons, exact: NJ (exclusion) beats NY by +$1,007/yr at $1.5M (unchanged) and +$903/yr at $2.5M (was +$845). With the loops: -$194/yr at $1.5M (was -$193), inside the ~1% loop-noise band, and +$481/yr at $2.5M (was +$513). The exclusion is now worth +$1,483/yr at $1.5M exact (was +$1,519 against the no-exclusion plan without the senior exemption). With `maxTime=600` the $2.5M NJ plan was $53/yr better than at the 60 s cap on 2026-10-03; not rerun.

Known limits: NYC household/school credits, part-year residency, the 10.9% NY cliff above $25M AGI, NJ Special Exclusion / disability before 62, NJ line 28b when only one spouse is 62+ (only 28a taken), NJ basis in IRAs. Residency comparisons under ~1% may be loop noise.

## Model review (2026-10-03)

Review of the paper (`papers/owl.tex`) against the implementation: `fork-notes/model-review/README.md`, with repro scripts and raw output in the same directory. Main findings (all upstream code):

- [ ] Loop mode returns a self-consistent plan, not an optimal one. Optimizing IRMAA or SS taxability raised the objective on 9 of 13 examples by up to +1.3% bequest / +2.3% spending, never lowered it.
- [ ] A non-converging loop keeps its highest-objective iterate, whatever its residual (cameron: SS off by $29.8k).
- [x] Bracket fill goes out of order when late cash has no value (constructed case: $1.56M reported vs $0.91M). **Fixed 2026-10-04**: tax tie-break switched on in the loop when a year goes out of order, a final re-solve, and a post-solve check. The 17 examples are unchanged.
- [x] `withACA="optimize"` infeasible where `pct x MAGI > SLCSP` below 400% FPL. **Fixed 2026-10-04**: thresholds clipped at that crossing. Step rates are still open.
- [x] NJ kept tier held income on its floor (`maxTime=2`: a year at exactly $150,000 claimed nothing instead of 25%, $5,402 vs $3,330 statutory; failed on `06468de` too). **Fixed 2026-10-04** (`755377e`): such a year's kept tier moves down to the statute's, downward only. 4 of 4 repeated runs were non-statutory without the fix, 0 of 4 with it; deterministic unit test added.
- [x] SS claiming-age MILP charged every candidate age the same SS tax. **Fixed 2026-10-04** (`d92c118`): taxable SS, IRMAA/ACA MAGI and the state SS exclusion use offset + `ssb` with the loop's `Psi_n`. Exact-LP repro: result no longer depends on the starting age and equals a fixed-age solve (start 62 used to report $104,526/yr for an age worth $104,518/yr). Not covered: `withSSTaxability="optimize"` (its min() needs another binary). Draft `fork-notes/issue-ss-age-taxes.md`.
- [x] Cost basis omitted reinvested dividends; whole-account gain fraction applied to the equity share only. **Fixed 2026-10-04** (`245d200`): taxed dividends/interest added to basis, equity gain fraction `(1 - K/b)/alpha0`. Examples: joe -469, helen+ruth -1,036, jack+jill -42, robin -57 $/yr (references re-recorded; MOSEK helen+ruth reference not re-recorded). Draft `fork-notes/issue-cost-basis.md`.
- [ ] Partial first year: balances are back-projected for growth only, while year-0 flows run full-year (same $1M on Oct 1 vs Jan 1: -2.1% spending). Design question; drafted, no patch: `fork-notes/issue-partial-first-year.md`. Not fixed in the fork.
- [x] Survivor of a worker who died before claiming got 82.5% of PIA. **Fixed 2026-10-04** (`adeea31`): full PIA, plus DRCs to death after FRA. Rule from memory and secondary summaries of POMS RS 00615.320 (ssa.gov, ecfr, govinfo blocked); **user to confirm before filing**. Draft `fork-notes/issue-survivor-never-claimed.md`.
- [x] New: ACA loop mode 133-150% FPL band started at 2.10% instead of 3.14% (Rev. Proc. 2025-25; irs.gov blocked, table from secondary sources). **Fixed 2026-10-04** (`5bd010e`). Draft `fork-notes/issue-aca-133-150.md`.
- [ ] ACA optimize: step rates (each band charged its final %) and the <138% FPL rule differs from loop mode (repro: optimize ends $1,786/yr higher where income drifts below 138%). Design question; drafted: `fork-notes/issue-aca-optimize-rates.md`.
- [ ] Paper vs code drift, loop mode as a fixed point, taxable bond returns, plan year: one docs issue drafted, `fork-notes/issue-docs-loop-and-paper.md`.

**Filed by the user on 2026-10-04** (issue numbers not recorded yet): ACA 133-150% band, survivor never claimed, cost basis, SS-age taxes, partial first year, ACA optimize rates. **Not filed:** docs/paper drift (`issue-docs-loop-and-paper.md`). The last two were verified on 2026-10-04 against the primary text: Rev. Proc. 2025-25 section 3.01 (irs.gov) and 26 CFR 1.36B-3(g)(1) for the ACA band; 42 U.S.C. 402(e)(2)(D) (govinfo.gov), 20 CFR 404.338 and 404.313(e)(1) (ecfr.gov) and POMS RS 00615.320 (secure.ssa.gov) for the survivor rule. Repro numbers re-run on this branch match the drafts. Note: www.ssa.gov itself answers 403 to curl (the site, not the proxy); POMS is on secure.ssa.gov. Rule from the user: never file a draft that asks the maintainer to check a source we didn't check; mark it not ready instead. Each patch draft has a `.patch` verified on stock `dev` `c1e5619` (full suite with each patch alone: 2604-2606 passed, 1 skipped; flake8 clean). Applied in the fork on branch `claude/project-thread-qx5fy0`.

## Upstream contributions (maintainer implements from issues; send issue + patch, not PRs)

1. #157 NY non-indexed amounts (patch `ad4452d`) — filed; NJ addendum drafted (patch `20ccb2d`)
2. #158 NY benefit recapture (patch `fe7fba3`) — filed
3. #159 Design issue: residency moves + local tax layer — filed
4. #160 NJ retirement-income exclusion (patches `7fcfadf`, `395be10`) — filed; maintainer keeps state taxes a pure LP; our reply posted
5. #161 ACA optimize infeasibility — filed
6. #162 Bracket order — fixed upstream with our patch (2026.10.4), merged
7. #163 SC-loop cycle selection — filed
8. Filed 2026-10-04 by the user (numbers not recorded yet): ACA 133-150% band, survivor never claimed, cost basis, SS-age taxes (each with a patch verified on `dev`); partial first year, ACA optimize rates (design, no patch). Not filed: docs/paper drift

When upstream lands #157/#158, merge `dev` and drop our duplicates, as with #149 and #155.

## Later phases (from requirements.md)

2 housing ledger (rent vs buy, property tax) · 3 itemized deductions · 4 healthcare cost model · 5 part-time work and SS earnings test · 6 scenario sweep and report · 7 NJ specifics (exclusion done; left: property tax deduction/credit up to $15k, which belongs with Phase 2, and the 65+ exemption)

Next: Phase 2, housing ledger and property tax. NJ's property tax deduction (line 41) or credit (line 56) attaches there.

Phase 5 now has a concrete case to serve: scenario 4b. The earnings test would let `withSSAges` optimize the working spouse too; a per-scenario PIA (or recomputing it from extra work years) would remove the manual PIA step. Medicare past 65 with employer coverage (delayed Part B) only matters if the worker goes past 65.

## Test status

With the four model-review fixes (2026-10-04, `d92c118`): 2724 passed, 1 skipped; flake8 clean.

Full suite after merging upstream 2026.10.4 (2026-10-04): 2714 passed, 1 skipped; flake8 clean (same count as after 2026.10.3: upstream's #162 test file is identical to ours). After merging 2026.10.3: 2714 passed, 1 skipped. Before the merge: 2711 passed, 1 skipped.

Merge notes: NJ now also takes the $1,000 exemption per filer aged 65+ (upstream), so NJ figures recorded before this merge (stakes tables above, the #160 issue numbers) are slightly high for couples 65+. Fork-only amounts follow upstream's flags (NY recapture thresholds with `brackets_indexed`, NJ exclusion ceilings/cap with `exemptions_indexed`); upstream's personal credits are wired through the moves schedule (`StateTaxParams.credit_n`), offset recapture too, and come before a local surcharge.
