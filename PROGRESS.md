# Owl fork — progress (as of 2026-10-03)

Fork-only file, like `CLAUDE.md`; not for upstream. Keep it current at the end of each work session.

Fork `fmateoc/Owl`, branch `claude/relaxed-turing-xzrv89` (continued from `claude/inspiring-rubin-f0a0p9`), merged with upstream `dev` at `a85ff76` (2026.10.1; nothing newer upstream on 2026-10-03).
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
| NJ retirement-income exclusion (lines 28a–28c, from Phase 7) | `7fcfadf` | Done, exact MILP (see below) |

NJ exclusion, how it is built: one binary per tier per year in which a filer is 62+, in the disaggregated (convex-hull) form; about 1 s per MILP on a 32-year couple whose income sits near the ceilings (but see the performance problem below). Rejected alternatives, measured on that couple: a self-consistent-loop version (2-cycle; the accepted plan undercharged its own NJ tax by $13.9k lifetime), and a big-M-on-income MILP (4–6 s per MILP; with `gap=1e-3` it hit a 30 s limit). The optimizer holds NJ income at exactly $100,000 in many years when it can.

NJ stakes (synthetic couple born 1964, SS at 70, $300k taxable, $150k Roth, `maxSpending`, Medicare off, SS taxability 0.85; lifetime, today's $):

| Tax-deferred | Case | Spending ($/yr) | Lifetime state tax | Solve |
|---|---|---:|---:|---:|
| $1.5M | FL | 126,372 | 0 | 0.1 s |
| $1.5M | NY | 125,093 | 31,585 | 0.1 s |
| $1.5M | NJ, no exclusion (as upstream) | 124,581 | 44,111 | 0.1 s |
| $1.5M | NJ, exclusion | 126,100 | 0 | 3.4 s (income held at $100k in 14 years) |
| $2.5M | FL | 161,885 | 0 | 0.1 s |
| $2.5M | NY | 157,985 | 97,427 | 0.1 s |
| $2.5M | NJ, no exclusion (as upstream) | 157,601 | 108,561 | 0.1 s |
| $2.5M | NJ, exclusion | 158,648 | 65,240 | **not proven**: 0.86% gap after a 30 s cap, one iteration |

Ignoring the exclusion ranked NJ below NY on both couples. With it, NJ is above NY by ~$1,000/yr at $1.5M and within $280/yr of FL. With default solver options (Medicare and SS loops on) the $1.5M couple takes 19.6 s against 0.5 s, and the exclusion is worth +$528/yr.

**Open problem, performance:** at $2.5M the MILP does not close: no first iteration finished in 10 minutes. It stays at 0.4% even with an artificially tight income bound ($400k), so the difficulty is combinatorial: which early high-conversion years to hold at $125k/$150k, each choice worth a few hundred dollars. Not yet decided: a time cap with the gap reported, a heuristic warm start, or restricting the free binaries to years near the ceilings. Until then, set `maxTime` (and maybe `gap`) for large NJ cases.

Known limits: NYC household/school credits, part-year residency, the 10.9% NY cliff above $25M AGI, NJ Special Exclusion / disability before 62 / 65+ exemption, NJ line 28b when only one spouse is 62+ (only 28a taken), NJ basis in IRAs. Residency comparisons under ~1% may be loop noise.

## Upstream contributions (maintainer implements from issues; send issue + patch, not PRs)

1. #157 NY non-indexed amounts (patch `ad4452d`) — filed; NJ addendum drafted (patch `20ccb2d`)
2. #158 NY benefit recapture (patch `fe7fba3`) — filed
3. #159 Design issue: residency moves + local tax layer — filed
4. NJ retirement-income exclusion (patch `7fcfadf`) — drafted

When upstream lands #157/#158, merge `dev` and drop our duplicates, as with #149 and #155.

## Later phases (from requirements.md)

2 housing ledger (rent vs buy, property tax) · 3 itemized deductions · 4 healthcare cost model · 5 part-time work and SS earnings test · 6 scenario sweep and report · 7 NJ specifics (exclusion done; left: property tax deduction/credit up to $15k, which belongs with Phase 2, and the 65+ exemption)

Next: Phase 2, housing ledger and property tax. NJ's property tax deduction (line 41) or credit (line 56) attaches there.

Phase 5 now has a concrete case to serve: scenario 4b. The earnings test would let `withSSAges` optimize the working spouse too; a per-scenario PIA (or recomputing it from extra work years) would remove the manual PIA step. Medicare past 65 with employer coverage (delayed Part B) only matters if the worker goes past 65.

## Test status

Full suite with the NJ exclusion (before the docs-only commits): 2697 passed, 1 skipped; flake8 clean.
