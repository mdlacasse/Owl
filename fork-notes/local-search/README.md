# Upstream's local search for the tax breakpoints, measured (2026-10-06)

The maintainer answered our pinned-loop proposal (upstream #171) with `breakpointMethod = "local-search"` (2026.10.6, `localsearch.py`): the loop first, then, inside each loop iteration, restricted MILPs that free one binary family at a time (or SS taxability within 4 flips, or the inconsistent years), each capped at 3,000 HiGHS nodes. He asked what we find. This note records what was run, on stock upstream `dev` `5006479` (2026.10.7) unless it says "fork".

Machine: the 4-core cloud container, one solve at a time. Times are wall clock. Script: `bench.py` (`results_dev.jsonl`). Values are the spending basis (today's $) for `maxSpending` cases and the bequest (today's $) for `maxBequest` ones (jordan+taylor, jordan+taylor-qcd, kim+sam-bequest, john+sally).

## 1. Loop vs local search on the 17 examples [run]

Each case with its own solver options ("Loop"), then with `breakpointMethod = "local-search"` added. Residual: the fixed-point residual, summed over families (today's $).

| Case | Loop | Time | Residual | Local search | Time | Residual | Change | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| alex+jamie | 228,369 | 0.2 s | 802 | 229,084 | 120.5 s | 622 | +0.31% | search plan |
| bill | 36,666 | 0.0 s | 0 | 36,666 | 0.5 s | 0 | +0.00% | loop plan kept |
| cameron | 18,996 | 0.1 s | 29,429 | 18,996 | 1.1 s | 29,429 | +0.00% | loop plan kept |
| chris+pat | 117,052 | 1.0 s | 20,287 | 117,090 | 13.2 s | 874 | +0.03% | search plan |
| dana | 81,228 | 0.1 s | 3 | 81,238 | 39.9 s | 1 | +0.01% | search plan |
| devon | 248,306 | 0.1 s | 0 | 248,306 | 97.8 s | 0 | +0.00% | loop plan kept |
| helen+ruth | 194,069 | 0.1 s | 612 | 195,157 | 40.7 s | 0 | +0.56% | search plan |
| jack+jill | 102,545 | 1.3 s | 1,459 | 103,290 | 79.4 s | 0 | +0.73% | search plan |
| joe | 92,575 | 0.1 s | 3 | 93,108 | 97.8 s | 7 | +0.58% | search plan |
| john+sally | 16,803 | 0.1 s | 0 | 16,803 | 44.8 s | 0 | +0.00% | loop plan kept |
| jon+jane | 160,677 | 0.2 s | 0 | 160,677 | 1.6 s | 0 | +0.00% | loop plan kept |
| jordan+taylor-qcd | 1,180,200 | 0.1 s | 0 | 1,196,963 | 127.3 s | 205 | +1.42% | search plan |
| jordan+taylor | 1,530,120 | 0.1 s | 0 | 1,550,875 | 122.2 s | 0 | +1.36% | search plan |
| kim+sam-bequest | 1,944,071 | 0.5 s | 814 | 1,960,802 | 168.0 s | 0 | +0.86% | search plan |
| kim+sam-spending | 185,949 | 0.3 s | 1,355 | 186,230 | 172.6 s | 0 | +0.15% | search plan |
| morgan | 40,889 | 0.4 s | 1,795 | 44,074 | 49.3 s | 1 | +7.79% | search plan |
| robin | 44,013 | 0.3 s | 1,040 | 44,118 | 16.6 s | 1 | +0.24% | search plan |

jack+jill's own options already put IRMAA in branch-and-bound (`withMedicare = "optimize"`), so its "Loop" column is that.

Reading:
- Never worse than the loop, as designed. Better on 12 of 17, by up to +1.42% outside morgan (+7.79%); the other 5 keep the loop's plan. Residuals fall to near zero on every case that changed.
- Several gains are larger than the "noise" we had been assuming: jordan+taylor +1.36%, kim+sam-bequest +0.86%, jack+jill +0.73%, joe +0.58%, helen+ruth +0.56%. Our pinned-loop draft read gains under 0.5% as noise; here they come with lower residuals, so they are real improvements to self-consistent plans.
- Not measured: the distance to full branch-and-bound. A run at `maxTime = 300` per MILP was stopped after alex+jamie alone passed 11 minutes (the loop calls the MILP every iteration). Only cameron was compared to branch-and-bound (section 3).
- Cost: 0.5-173 s against 0.0-1.3 s for the loop. The first loop iteration takes most of it (e.g. kim+sam-spending 156 of 174 s, morgan 44 of 50 s).

## 2. morgan, and the measure in the maintainer's table [run]

The maintainer's reply compares "44,200" on current `dev` with the 38,744 of our table. Those are different quantities: 44,200 is morgan's net spending for 2026 (`g_n[0]`, the Summary's "Net spending for year 2026"), 38,744 was the spending basis. On `dev` `5006479`, morgan's default solve gives a basis of 40,889 and a first-year spending of 44,200 (`morgan_measures.py`, ACA cost $85,641 as in his table). The two measures differ by a constant factor (1.081 here), so his relative comparisons hold: `withACA = "optimize"` gives basis 44,100 / first year 47,671, +7.85% either way, in 65.9 s here (his 21 s on an M5). So #165 moved morgan's default by +5.5% (38,744 to 40,889), not +14%. Local search gives 44,074, 0.06% below ACA-optimize alone and 0.33% below his all-five MOSEK MILP (47,801 first-year = 44,220 basis at the same factor; not run here).

## 3. cameron: a tie keeps the inconsistent plan [run]

cameron's loop ends on a 2-cycle whose plan charges $29,429 more taxable Social Security than its own income implies (residual sign checked: `Psi_n` above the formula's). Local search starts from it and finds no better objective, so it keeps the loop's plan, residual included. Branch-and-bound (`breakpointMethod = "branch-and-bound"`) and `withSSTaxability = "optimize"` alone both return the same 18,996 with zero residual in 0.2-0.6 s. So the objective was right and only the plan was inconsistent.

Proposed (fork: applied in `Plan._localSearchSolve`, test `test_a_tie_keeps_the_more_consistent_plan`; verified on stock `dev` as a temporary patch): on a tie within 1e-9, keep the search's plan when its residual is smaller. On `dev` with that change, cameron returns 18,996 with no residual. bill and jon+jane, the other ties checked, are unchanged ("local search -> loop", residual 0).

## 4. Repeated last iteration [run]

The loop around the search stops when two successive objectives agree, so its last iteration can repeat the previous one step for step (same steps, same objectives). Of 8 cases checked (`ls_repeat.py`): jordan+taylor (36 of 123 s) and helen+ruth (8 of 39 s). Not proposed: the saving is case-dependent and the check has to be exact.

## 5. Fork: the NJ exclusion's tier binaries under local search [run, fork]

`localsearch.FAMILIES` lists upstream's families only. The fork's NJ tier binaries (`zx`) were left out, so:
- the starting LP ("previous binaries (LP)") relaxed them, giving an objective no integer step could reach;
- every later step was rejected as "not better", and the plan returned was that LP's, with fractional tiers (up to 0.08) and a tax off the statute's;
- every step was a MILP over `zx`, so the search took 431 s.

Fix (fork, `localsearch.py`): `zx` is a family, labeled "state exclusion", with no residual family. On the $1.5M couple of `model-review/nj_stakes.py`: 123,636/yr with integral tiers in 186 s, against 124,702 with fractional tiers in 431 s. Test: `test_local_search_keeps_the_tiers_integral` (fails without the fix: a year charged $1,645 that owes $7,290).

Not an upstream issue: upstream's other non-family binaries (`zssa`, `zo`) are sent to branch-and-bound before the search starts.

## 6. Fork: NJ MILP capped by nodes, not seconds [run, fork]

Without `maxTime`, a HiGHS MILP carrying free `zx` binaries used to stop at 60 s, so a capped plan depended on the machine. It now stops at `RX_NODE_LIMIT` = 20,000 nodes (HiGHS reports "Solution limit reached"), with upstream's 900 s `TIME_LIMIT` as backstop; MOSEK keeps the 60 s cap (its node count is not comparable and was not recalibrated). On the $2.5M couple the 60 s cap had stopped at 20,809 nodes; with the node cap the plan is the same (154,482/yr, gap 0.19%, 64 s). Test: `test_node_limit_keeps_the_tiers_and_gives_the_same_plan_every_time` (two runs, identical plans).

## 7. NJ / NY / FL stakes under the three methods [run, fork]

See `PROGRESS.md` (Phase 1, NJ stakes) for the table and its reading.

## Files

Stock `dev` runs: `PYTHONPATH=<dev checkout>/src`, run from `<dev checkout>/examples` (bench.py takes `OWL_EXAMPLES`).

- `bench.py`: loop vs local search (or any `--methods`) on the examples; JSON lines. `results_dev.jsonl` (section 1; stderr was empty).
- `morgan_measures.py`: section 2 (basis vs first-year spending, ACA loop vs optimize).
- `cameron_ls.py`, `cameron_bb.py`: section 3 (residual sign, search steps; SS-optimize and branch-and-bound).
- `ls_repeat.py`: section 4.
- `nj_ls_frac.py` (`loop` | `local-search`), `nj_nodes.py` (`1500,1000`): sections 5 and 6, on the fork.
