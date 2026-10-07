# Owl fork — progress (as of 2026-10-07)

Fork-only file, like `CLAUDE.md`; not for upstream. Keep it current at the end of each work session.

Fork `fmateoc/Owl`, branch `claude/nifty-tesla-gbq1wt` (2026-10-06: merge of upstream 2026.10.7, NJ exclusion under local search, node cap, local-search tie rule), continued from `claude/project-thread-u0d9t0` (envelope model) and the branches before it (see `CLAUDE.md`), merged with upstream `dev` `5006479` (2026.10.7) and then `b4f1605` (five more fixes: partial-bequest weight 0.1% in the objective for couples with beneficiary fractions below 1, exact-NIIT cap row, local-search steps at a 0.01% gap, solve time in the Summary, lifespan-sampled copies) on 2026-10-06, then `5dd1623` on 2026-10-07 (`785217c`: our local-search tie rule adopted, an unchanged problem not searched again, IRMAA/ACA brackets $2 above their thresholds, partial-bequest weight max(1%, 2 x gap), HiGHS retries a MIP it calls infeasible, new example avery+quinn; `5dd1623`: a loop stopped early no longer returns iteration 0).
Phase 1 closed 2026-10-07: the fork's `main` was fast-forwarded to this branch (`7551d75`).
Branch `claude/compassionate-cannon-fb1srw` (2026-10-07, from `main`): Phase 2 plan, then merge of upstream `004c840` (2026.10.8: package upgrades, Streamlit 1.65, `tests/conftest.py` iterates over a copy of `sys.modules`); no conflicts.
Plan details: `fork-notes/phase1-revised.md`. Scenario commands: `fork-notes/phase0/phase0-scenarios.md`.

## Upstream

Maintainer's responses as relayed by the user on 2026-10-06; issue states not re-checked on GitHub (this session's GitHub access covers the fork only).

| Item | State |
|---|---|
| #147, #149, #155 | Fixed upstream earlier; our copies dropped |
| #157 NY/NJ not indexed (+ NJ addendum) | Fixed upstream (`3c88ce1`, 2026.10.3); merged, theirs |
| #158 NY benefit recapture missing | Filed; no response (the issue said our code would not apply as is). **2026-10-06: rebuilt on stock `dev` `b4f1605`** without our loop registry or typed params, on upstream's `st_schedule`: `fork-notes/issue-ny-recapture.patch` (4 files, +369/−6, 23 tests; full upstream suite 2720 passed, 1 skipped; plans identical to the fork's to the dollar, also under local search and after the fork merged `b4f1605`). Follow-up comment **posted** by the user (`fork-notes/issue-ny-recapture-update.md`); no reply on #158 yet (the 2026-10-07 reply relayed answered the #171 points). 2026-10-07: patch refreshed on `5dd1623` (applies without offsets; upstream suite with it 2732 passed, 1 skipped; fork and patched stock still identical, by the same numbers moved $3-14/yr by upstream's own changes). Fork keeps its own version (locality surcharge on it, credits, Summary line) |
| #159 Moves + local tax (design) | **Implemented upstream as one move** (`f5820c0`, `a3897b2`, 2026.10.6), no local tax. Maintainer: wants equivalence of all variables between states and no lookup between years (e.g. IRMAA) before folding more in; "consider PA". **Merged 2026-10-06**: Plan names, `_states_n()`, the UI toggle and `basic_info.moves` follow upstream; the fork keeps several moves, a locality per move, and typed `StateTaxParams` (`st_schedule` under upstream's name). Three upstream asserts adapted (3-tuples), two `st_schedule` tests read fields. PA not looked at (its local earned-income taxes are wage taxes, which `taxes_local.toml` excludes by design; not verified this session) |
| #160 NJ retirement-income exclusion | Answered 2026-10-04: upstream keeps state taxes a pure LP. Our reply posted. Fork keeps its MILP |
| #161 ACA optimize infeasible | **Fixed upstream** (`bf817dd`, 2026.10.5), crossing found on the sliding scale; merged, theirs |
| #162 Bracket order | Fixed upstream with our patch (`3fca646`); fork keeps its copy (local brackets) |
| #163 SC-loop cycle selection | **On hold**: maintainer tested it over parameter ladders; it does not address optimality and the run-time difference is marginal. Not applied in the fork. Local search now covers the cameron case (section "Local search") |
| #164 ACA 133-150% band | Fixed upstream (`d88a37e`); merged, theirs |
| #165 ACA optimize rates | Fixed upstream (`7ad4c7e`): sliding scale by tangents, and Medicaid at no premium up to 138% FPL in both modes (morgan +$2,100/yr). Merged, theirs |
| #166 Cost basis | Fixed upstream (`4f90899`); merged, theirs |
| #167 Partial first year | **Documented upstream** (`22ec12f`), left open for a short first period. Maintainer suggests adding the amount spent since Jan 1 to the balances. Reply **posted** by the user 2026-10-06 (`fork-notes/issue-partial-first-year-reply.md`): with income kept full-year, as his docs say, the add-back is spending and taxes paid minus income received. Fork template updated (`fork-notes/phase0/Case_us.template.toml`) |
| #168 SS-age taxes | Fixed upstream (`a746a04`); merged, theirs |
| #169 Survivor never claimed | Fixed upstream (`1a21641`); merged, theirs |
| #170 Envelope model | Filed with #171; one conversation with it (the maintainer answered both on #171) |
| #171 Pinned loop | **Declined**: second model too costly; `withACA="optimize"` captures morgan's gain; maintainer's answer is local search (`breakpointMethod="local-search"`, 2026.10.6). Asked for our findings: measured, reply **posted** by the user 2026-10-06 (`fork-notes/issue-local-search-reply.md`, details `fork-notes/local-search/README.md`). Maintainer (2026-10-07): all three points right; tie rule and repeat reuse in `785217c`, merged (fork's own tie code and test dropped, theirs kept). He also notes the cost basis is still a source of non-convergence with Medicare exact (on his list) |
| Loop anomaly (NY→FL at year 5) | Not filed (no repro beyond loop noise) |
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
| NJ exclusion: 20,000-node cap instead of 60 s (HiGHS); a local-search family | 2026-10-06 | Done (same plan as the 60 s cap on the $2.5M couple; deterministic) |

NJ exclusion, how it is built: one binary per tier per year in which a filer is 62+, in the disaggregated (convex-hull) form. Rejected alternatives, measured on the $1.5M couple: a self-consistent-loop version (2-cycle; the accepted plan undercharged its own NJ tax by $13.9k lifetime), and a big-M-on-income MILP (4–6 s per MILP; with `gap=1e-3` it hit a 30 s limit).

Solve limits (`plan.py`: `RX_WINDOW`, `RX_NODE_LIMIT`; until 2026-10-06 `RX_TIME_LIMIT`): binaries are free only in years whose income in the previous iterate was at most 1.5× the top ceiling ($225k); iteration 0 runs without the exclusion, and the free set (`RXF_n`, an SC parameter) only grows, so at convergence every left-out year is far above $150k, where nothing is excluded. Without `maxTime`, a MILP carrying the binaries stops at 20,000 HiGHS nodes (until 2026-10-06: 60 s), warns with its gap, and later iterations keep its tiers; `solverGap` reports that gap. The window alone did not fix the $2.5M case (60 s cap hit on all four iterations, 240 s); keeping the tiers did (61 s).

NJ stakes, rerun 2026-10-06 on this branch (upstream 2026.10.7 merged; NJ exclusion as a local-search family; node cap). Synthetic couple born 1964-03-15 and 1964-09-15, life expectancies 89 and 92, SS $3,000 and $2,400/month at 70, $300k taxable, $150k Roth, conservative rates, 60/40, `maxSpending`, no bequest. Script `fork-notes/model-review/nj_stakes.py exact|default|ls`; raw output `fork-notes/local-search/nj_stakes_2026-10-06.txt`. Spending basis in $/yr; lifetime state tax in today's $; runs one at a time on the 4-core container.

| Tax-deferred | Case | Exact LP | Loop (default) | Local search | Lifetime state tax (exact / loop / LS) | Time (exact / loop / LS) |
|---|---|---:|---:|---:|---|---|
| $1.5M | FL | 126,340 | 123,818 | 125,130 | 0 / 0 / 0 | 0.1 / 0.6 / 43 s |
| $1.5M | NY | 125,063 | 122,597 | 123,206 | 31,554 / 31,572 / 46,892 | 0.1 / 0.6 / 59 s |
| $1.5M | NJ, no exclusion | 124,587 | 121,817 | 122,947 | 42,595 / 42,526 / 54,692 | 0.1 / 0.9 / 46 s |
| $1.5M | NJ, exclusion | 126,069 | 122,406 | 123,636 | 0 / 0 / 20,193 | 6.2 / 17.8 / 184 s |
| $2.5M | FL | 161,844 | 157,821 | 158,833 | 0 / 0 / 0 | 0.1 / 0.2 / 64 s |
| $2.5M | NY | 157,945 | 153,952 | 154,431 | 97,369 / 97,634 / 98,123 | 0.1 / 0.2 / 82 s |
| $2.5M | NJ, no exclusion | 157,621 | 153,632 | 154,038 | 106,720 / 106,872 / 106,500 | 0.1 / 0.2 / 60 s |
| $2.5M | NJ, exclusion | 158,828 | 154,482 | 154,993 | 63,291 / 63,370 / 75,289 | 63 / 67 / 180 s |

"Exact LP": Medicare off and SS taxability pinned at 0.85, a different model (no IRMAA, no SS formula), so its residuals are large by construction. "Loop": the default options. "Local search": the default options plus `breakpointMethod="local-search"`, which also replaces the pinned SS fraction by the IRS formula. NJ-with-exclusion gaps: 0.01% / 0.17-0.19% at the node cap for the MILPs; local search reports no gap (no certificate).

NJ (exclusion) minus NY, $/yr:

| | Exact LP | Loop | Local search |
|---|---:|---:|---:|
| $1.5M | +1,006 | −191 | +430 |
| $2.5M | +883 | +530 | +562 |

FL minus NY: +1,277 / +1,221 / +1,924 at $1.5M; +3,899 / +3,869 / +4,402 at $2.5M.

Reading: the loop alone flips the sign of NJ vs NY at $1.5M; local search and the exact LP agree that NJ (with its exclusion) is ahead at both levels, by $430-1,006/yr. Local search finds better plans under the full model in every case here (+0.3% to +1.1% over the loop) and pays more state tax in 5 of the 6 taxed cases; that it trades state tax for federal costs the loop prices with a lag (IRMAA, SS taxability) is inferred, not decomposed. For decisions: compare variants under local search, cross-check with the exact LP, and treat differences smaller than the spread between the two as unresolved. Earlier tables (2026-10-03/04, before the upstream ACA/basis fixes and with the 60 s cap) are in git history; the exact-LP figures moved by $20-50/yr since.

Known limits: NYC household/school credits, part-year residency, the 10.9% NY cliff above $25M AGI, NJ Special Exclusion / disability before 62, NJ line 28b when only one spouse is 62+ (only 28a taken), NJ basis in IRAs. Residency comparisons under ~1% made with the loop alone can have the wrong sign (table above).

## Model review (2026-10-03)

Review of the paper (`papers/owl.tex`) against the implementation: `fork-notes/model-review/README.md`, with repro scripts and raw output in the same directory. Main findings (all upstream code):

- [x] Loop mode returns a self-consistent plan, not an optimal one. Optimizing IRMAA or SS taxability raised the objective on 9 of 13 examples by up to +1.3% bequest / +2.3% spending, never lowered it. **Addressed upstream** by `breakpointMethod="local-search"` (2026.10.6, opt-in): better than the loop on 12 of 17 examples, up to +1.42% (+7.79% morgan), never worse (`fork-notes/local-search/README.md`).
- [ ] A non-converging loop keeps its highest-objective iterate, whatever its residual (cameron: SS off by $29.8k). #163 on hold upstream. Under local search, the fork's tie rule now returns cameron's objective with zero residual; proposed in the #171 reply draft.
- [x] Bracket fill goes out of order when late cash has no value (constructed case: $1.56M reported vs $0.91M). **Fixed 2026-10-04**: tax tie-break switched on in the loop when a year goes out of order, a final re-solve, and a post-solve check. The 17 examples are unchanged.
- [x] `withACA="optimize"` infeasible where `pct x MAGI > SLCSP` below 400% FPL. **Fixed 2026-10-04**; upstream's own fix (#161, crossing on the sliding scale) replaced ours in the 2026.10.7 merge.
- [x] NJ kept tier held income on its floor (`maxTime=2`: a year at exactly $150,000 claimed nothing instead of 25%, $5,402 vs $3,330 statutory; failed on `06468de` too). **Fixed 2026-10-04** (`755377e`): such a year's kept tier moves down to the statute's, downward only. 4 of 4 repeated runs were non-statutory without the fix, 0 of 4 with it; deterministic unit test added.
- [x] SS claiming-age MILP charged every candidate age the same SS tax. **Fixed 2026-10-04** (`d92c118`): taxable SS, IRMAA/ACA MAGI and the state SS exclusion use offset + `ssb` with the loop's `Psi_n`. Exact-LP repro: result no longer depends on the starting age and equals a fixed-age solve (start 62 used to report $104,526/yr for an age worth $104,518/yr). Not covered: `withSSTaxability="optimize"` (its min() needs another binary). Draft `fork-notes/issue-ss-age-taxes.md`. Upstream #168; theirs since the 2026.10.7 merge.
- [x] Cost basis omitted reinvested dividends; whole-account gain fraction applied to the equity share only. **Fixed 2026-10-04** (`245d200`): taxed dividends/interest added to basis, equity gain fraction `(1 - K/b)/alpha0`. Examples: joe -469, helen+ruth -1,036, jack+jill -42, robin -57 $/yr (references re-recorded; MOSEK helen+ruth reference not re-recorded). Draft `fork-notes/issue-cost-basis.md`. Upstream #166; theirs since the 2026.10.7 merge.
- [ ] Partial first year: balances are back-projected for growth only, while year-0 flows run full-year (same $1M on Oct 1 vs Jan 1: -2.1% spending). Upstream #167: documented (`22ec12f`), left open. Not fixed in the fork; the household case uses January 1 balances (template).
- [x] Survivor of a worker who died before claiming got 82.5% of PIA. **Fixed 2026-10-04** (`adeea31`): full PIA, plus DRCs to death after FRA. Rule from memory and secondary summaries of POMS RS 00615.320 (ssa.gov, ecfr, govinfo blocked); **user to confirm before filing**. Draft `fork-notes/issue-survivor-never-claimed.md`. Upstream #169; theirs since the 2026.10.7 merge.
- [x] New: ACA loop mode 133-150% FPL band started at 2.10% instead of 3.14% (Rev. Proc. 2025-25; irs.gov blocked, table from secondary sources). **Fixed 2026-10-04** (`5bd010e`). Draft `fork-notes/issue-aca-133-150.md`. Upstream #164; theirs since the 2026.10.7 merge.
- [x] ACA optimize: step rates (each band charged its final %) and the <138% FPL rule differs from loop mode (repro: optimize ends $1,786/yr higher where income drifts below 138%). **Fixed upstream** (#165, `7ad4c7e`): tangent-line sliding scale, Medicaid at no premium up to 138% FPL in both modes.
- [ ] Paper vs code drift, loop mode as a fixed point, taxable bond returns, plan year: one docs issue drafted, `fork-notes/issue-docs-loop-and-paper.md`. Upstream rewrote parts of `papers/owl.tex` in 2026.10.6-7: recheck before filing.

**Filed by the user on 2026-10-04**: ACA 133-150% band (#164), survivor never claimed (#169), cost basis (#166), SS-age taxes (#168), partial first year (#167), ACA optimize rates (#165); numbers from upstream's CHANGELOG and commit messages. **Not filed:** docs/paper drift (`issue-docs-loop-and-paper.md`). The last two were verified on 2026-10-04 against the primary text: Rev. Proc. 2025-25 section 3.01 (irs.gov) and 26 CFR 1.36B-3(g)(1) for the ACA band; 42 U.S.C. 402(e)(2)(D) (govinfo.gov), 20 CFR 404.338 and 404.313(e)(1) (ecfr.gov) and POMS RS 00615.320 (secure.ssa.gov) for the survivor rule. Repro numbers re-run on this branch match the drafts. Note: www.ssa.gov itself answers 403 to curl (the site, not the proxy); POMS is on secure.ssa.gov. Rule from the user: never file a draft that asks the maintainer to check a source we didn't check; mark it not ready instead. Each patch draft has a `.patch` verified on stock `dev` `c1e5619` (full suite with each patch alone: 2604-2606 passed, 1 skipped; flake8 clean). Applied in the fork on branch `claude/project-thread-qx5fy0`.

## Envelope model (2026-10-04, branch `claude/project-thread-u0d9t0`)

Back-of-envelope question: `fork-notes/envelope/README.md`. A one-state DP (`em.py`) reproduces Owl within ±1% on most examples in 0.02–0.2 s; with the early-withdrawal penalty, conversion caps and the taxable account as a second state (§8), the EM's accounting matches Owl's within ±0.11% in 15 of 17 cases and its optimum is within −0.3% to +0.9% in 12 of 17, but it takes 0.7–5 s (slower than Owl's loop). Decision (Florin): the one-state version is the quick screen.

Seeding Owl's loop from the one-state plan does nothing (≤0.05% except john+sally +3%). Pinning Owl's yearly recognition to it, with the loop seeded from it, gives morgan +10.2% on stock `dev` (+11.0% with Ψ fixed, all other residuals 0) and −0.55% to +0.47% elsewhere; john+sally −$5.8k, because the EM's schedule needs an untaxed taxable account (README §10, which also explains the john+sally gap).

Upstream: the pinned loop was filed as #171 and **declined** (2026-10-05/06): a second model with its own assumptions costs too much to maintain; `withACA="optimize"` already gets morgan's gain (+7.9%); the maintainer's answer is local search (2026.10.6), which beats the pinned loop's results on the examples (`fork-notes/local-search/README.md`). The EM issue is #170, answered together with #171. The EM stays a fork-notes screen.

## Upstream contributions (maintainer implements from issues; send issue + patch, not PRs)

1. #157 NY non-indexed amounts (patch `ad4452d`) — filed; NJ addendum drafted (patch `20ccb2d`)
2. #158 NY benefit recapture (patch `fe7fba3`) — filed; stock-`dev` patch and follow-up drafted 2026-10-06, not posted
3. #159 Design issue: residency moves + local tax layer — one move implemented upstream (2026.10.6), no local tax; merged
4. #160 NJ retirement-income exclusion (patches `7fcfadf`, `395be10`) — filed; maintainer keeps state taxes a pure LP; our reply posted
5. #161 ACA optimize infeasibility — fixed upstream (2026.10.5), merged
6. #162 Bracket order — fixed upstream with our patch (2026.10.4), merged
7. #163 SC-loop cycle selection — on hold upstream
8. Filed 2026-10-04 by the user: #164 ACA 133-150% band, #169 survivor never claimed, #166 cost basis, #168 SS-age taxes (all fixed upstream, merged); #167 partial first year (documented, open); #165 ACA optimize rates (fixed upstream). Not filed: docs/paper drift
9. #170 envelope model and #171 pinned loop (one conversation) — declined in favor of local search; findings reply posted 2026-10-06
10. #167 reply posted 2026-10-06

When upstream lands #158, merge `dev` and drop our duplicate, as with #149, #155, #157 and the 2026.10.5-7 fixes.

## Later phases (from requirements.md)

2 housing ledger (rent vs buy, property tax) · 3 itemized deductions · 4 healthcare cost model · 5 part-time work and SS earnings test · 6 scenario sweep and report · 7 NJ specifics (exclusion done; 65+ exemption done upstream in 2026.10.3; left: property tax deduction/credit up to $15k, which belongs with Phase 2)

Next: Phase 2, housing ledger and property tax. **Plan written 2026-10-07: `fork-notes/phase2-plan.md`** (a `Housing` HFP sheet shaped like `Debts`; costs subtracted in the cash flow; NJ line 41 property tax deduction as a bounded LP variable, no binaries). NJ rule verified this session against the 2025 and 2020 NJ-1040 instructions: deduction up to $15,000 after line 39, tenants 18% of rent, $50 credit as the alternative, amounts not indexed. The user agreed to all three recommendations (a `Housing` sheet; rent vs buy read as `maxBequest` at fixed `netSpending` on `final_bequest_today`; the $50 credit left out). No code yet.

Phase 5 now has a concrete case to serve: scenario 4b. The earnings test would let `withSSAges` optimize the working spouse too; a per-scenario PIA (or recomputing it from extra work years) would remove the manual PIA step. Medicare past 65 with employer coverage (delayed Part B) only matters if the worker goes past 65.

## Test status

2026-10-06, after merging upstream 2026.10.7: 2791 passed, 1 skipped, 1 failed (upstream's new UTF-8 check caught two fork `open()`s; fixed, then that test passed), so 2792 passed. flake8 clean except upstream's `localsearch.py:28` (122 > 120; their CI allows 127). After the local-search fixes and the node cap: 2795 passed, 1 skipped. After merging `5dd1623` (2026-10-07): 2818 passed, 1 skipped; flake8 only upstream's `localsearch.py:31` and `config/schema.py:388`. After merging `004c840` (2026-10-07): 2818 passed, 1 skipped; flake8 the same two upstream lines. After merging `b4f1605`: 2807 passed, 1 skipped (one conflict, in `tests/plan/test_local_search.py`, where both sides appended a test; both kept). The local-search benchmark in `fork-notes/local-search/` was run on `5006479`, before upstream tightened the step gap; not rerun.

Merge notes (2026-10-06): `tax_federal.py` and `socialsecurity.py` are now identical to upstream. Per-year state flags carry upstream's names. Upstream's explanation omits years without a state income tax and reports the state on every row; the fork follows. Earlier merge notes: NJ's $1,000 exemption per filer aged 65+ came from upstream 2026.10.3; fork-only amounts follow upstream's indexing flags (NY recapture thresholds with `brackets_indexed`, NJ exclusion ceilings/cap with `exemptions_indexed`).
