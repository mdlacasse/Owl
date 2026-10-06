# Draft reply on mdlacasse/Owl#171 (pinned loop → local search), not posted

Status: drafted 2026-10-06 for the user to post or edit. The maintainer declined the pinned loop and asked us to look at `breakpointMethod = "local-search"` and report. Every number below comes from runs on stock `dev` `5006479` (2026.10.7), on a 4-core cloud container, one solve at a time; details and scripts in `fork-notes/local-search/README.md`. Our fork-only findings (NJ exclusion binaries, node cap) are left out: they concern fork code.

---

Thanks, local search does what the pinned loop was after, without a second model. I ran it on stock `dev` (`5006479`) against the default loop on all 17 examples, each with its own options, one solve at a time on a 4-core container.

| Case | Loop | Residual | Local search | Residual | Change | Time |
|---|---:|---:|---:|---:|---:|---:|
| alex+jamie | 228,369 | 802 | 229,084 | 622 | +0.31% | 120 s |
| bill | 36,666 | 0 | 36,666 | 0 | 0 (loop plan kept) | 0.5 s |
| cameron | 18,996 | 29,429 | 18,996 | 29,429 | 0 (loop plan kept) | 1.1 s |
| chris+pat | 117,052 | 20,287 | 117,090 | 874 | +0.03% | 13 s |
| dana | 81,228 | 3 | 81,238 | 1 | +0.01% | 40 s |
| devon | 248,306 | 0 | 248,306 | 0 | 0 (loop plan kept) | 98 s |
| helen+ruth | 194,069 | 612 | 195,157 | 0 | +0.56% | 41 s |
| jack+jill | 102,545 | 1,459 | 103,290 | 0 | +0.73% | 79 s |
| joe | 92,575 | 3 | 93,108 | 7 | +0.58% | 98 s |
| john+sally | 16,803 | 0 | 16,803 | 0 | 0 (loop plan kept) | 45 s |
| jon+jane | 160,677 | 0 | 160,677 | 0 | 0 (loop plan kept) | 1.6 s |
| jordan+taylor-qcd | 1,180,200 | 0 | 1,196,963 | 205 | +1.42% | 127 s |
| jordan+taylor | 1,530,120 | 0 | 1,550,875 | 0 | +1.36% | 122 s |
| kim+sam-bequest | 1,944,071 | 814 | 1,960,802 | 0 | +0.86% | 168 s |
| kim+sam-spending | 185,949 | 1,355 | 186,230 | 0 | +0.15% | 173 s |
| morgan | 40,889 | 1,795 | 44,074 | 1 | +7.79% | 49 s |
| robin | 44,013 | 1,040 | 44,118 | 1 | +0.24% | 17 s |

Spending basis or bequest in today's dollars; residual is the fixed-point residual summed over families. The loop takes 0.0-1.3 s.

Never worse, better on 12 of 17, and the residual drops to about zero wherever it moves. Several of these gains are bigger than what I had been writing off as noise in our pinned-loop table (jordan+taylor +1.36%, kim+sam-bequest +0.86%, jack+jill +0.73%), and they come with consistent plans, so they are real.

Three smaller things:

1. **morgan's numbers.** The 44,200 in your table is the first-year net spending (`g_n[0]`). Our 38,744 was the spending basis. On `dev` the default basis is 40,889 (first year 44,200, ACA $85,641 as in your table). The two measures differ by a constant factor, so your +7.9% for `withACA = "optimize"` holds either way (basis 44,100). Local search gives 44,074.

2. **cameron: on a tie, the inconsistent plan wins.** The loop ends on a 2-cycle whose plan charges $29,429 more taxable Social Security than its income implies. The search finds the same objective, so `_localSearchSolve` keeps the loop's plan, with its residual. Branch-and-bound and `withSSTaxability = "optimize"` both give the same 18,996 with zero residual in under a second. A small change fixes it: on a tie, keep the search's plan when its residual is lower.

   ```diff
            floor = self._objectiveValue(objective)
   +        floor_resid = sum(v["abs_sum"] for v in (getattr(self, "fixedPointResidual", None) or {}).values())
   ...
   -            found = self.caseStatus == "solved" and self._objectiveValue(objective) > floor * (1 + 1e-9)
   +            value = self._objectiveValue(objective)
   +            resid = sum(v["abs_sum"] for v in (getattr(self, "fixedPointResidual", None) or {}).values())
   +            tie_but_consistent = value >= floor * (1 - 1e-9) and resid < floor_resid - 1.0
   +            found = self.caseStatus == "solved" and (value > floor * (1 + 1e-9) or tie_but_consistent)
   ```

   With it, cameron returns 18,996 with no residual, and bill and jon+jane (the other ties) are unchanged.

3. **A repeated last iteration.** The loop around the search stops when two objectives agree, so the last search can repeat the previous one step for step: jordan+taylor spends 36 of its 123 s that way, helen+ruth 8 of 39. In the other 6 cases I checked it didn't happen. Not worth much on its own.
