# Draft follow-up comment on mdlacasse/Owl#160 (NJ retirement exclusion)

**Superseded, not posted.** The maintainer answered on 2026-10-04: the state layer stays a pure LP, so NJ keeps `retirement_income_exemption = 0` upstream for now. Kept for the record of the fork's solve limits.

#160 was filed from the draft at `9e3b658`, which left solve time as an open question with three options. This comment reports what the fork chose. Post it as a comment rather than an edit, so the original question stays readable.

---

An update on the solve-time question in the last paragraph. In the fork I ended up combining the first two options, plus one correction:

1. **Binaries only near a ceiling.** Tier binaries are free only in years whose income, in the previous loop iteration, was at most 1.5x the top ceiling ($225k MFJ). The first iteration runs without the exclusion, and the set of free years only grows. At convergence, every year left out is far above $150k, where the statute excludes nothing anyway.
2. **A time cap that keeps the tiers.** Without a user `maxTime`, a MILP carrying these binaries stops at 60 s with a warning and its gap. Later loop iterations keep its tiers, so they re-solve only the continuous part, and the plan reports that MILP's gap.
3. **Moving a kept tier down when income sits on its floor.** A kept tier bounds income from below as well as above. A later iteration that wants less income can stop exactly on the tier's floor, which is the ceiling of the tier below, and the statute ("$150,000 or less") puts that income in the tier below. With a 2 s cap, one year of a $2.5M couple sat at exactly $150,000 claiming nothing instead of 25%: NJ tax $5,402 instead of $3,330. Such a year's kept tier is now moved down to the statute's tier at the same income, downward only, so it can't cycle.

For the issue's couple with $2.5M tax-deferred (Medicare off, SS taxability 0.85), a solve returns in about a minute, 0.19% from proven optimal. That's on one machine; the gap at the cap depends on CPU speed. The run hits the 60 s cap, but no tier needed moving down, so point 3 changes nothing there.

Updated figures now that `dev` has NJ's $1,000 senior exemption (#157), run on the fork after merging 2026.10.3. For the $1.5M couple in the issue, lifetime NJ tax without the exclusion is $42,619 (the issue says $44,111), and the exclusion is worth +$1,483/yr of spending (the issue says +$1,519). With the exclusion, NJ tax is still $0.

Reference implementation: fork `fmateoc/Owl`, branch `claude/optimistic-darwin-n5xykl`, commits `7fcfadf` (exclusion), `395be10` (window and cap) and `755377e` (moving a kept tier down).

The question from the issue still stands: would you rather have this always on for NJ, or behind an option like `withMedicare`?
