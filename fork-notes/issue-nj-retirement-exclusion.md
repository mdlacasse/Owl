# Draft upstream issue (mdlacasse/Owl): New Jersey's retirement income exclusion is missing

**Title:** State tax: New Jersey pension/retirement exclusion (NJ-1040 line 28) is not modeled, so NJ tax is overstated for retirees

Status: draft, ready to file. Reference implementation: fork commits `7fcfadf` (exclusion) and `395be10` (solve limits) (branch `claude/relaxed-turing-xzrv89`).

---

`taxes_state.toml` notes the exclusion in a comment ("excludes up to $100k pension/IRA if household income <= $100k (complex phaseout)") but sets `retirement_income_exemption = 0`, so Owl taxes all of a NJ retiree's pension, IRA withdrawals and Roth conversions.

**Rule** (2025 NJ-1040 instructions, lines 28a-28c and Worksheet D; the same amounts are printed for 2021, 2023 and 2024). For a filer who is 62 or older on December 31:

| Line 27 income | MFJ | Single / HoH / QW |
|---|---|---|
| up to $100,000 | all of line 20a, up to $100,000 | up to $75,000 |
| $100,001-$125,000 | 50% of line 20a | 37.5% |
| $125,001-$150,000 | 25% of line 20a | 18.75% |
| above $150,000 | nothing | nothing |

Line 20a includes pensions, annuities, IRA withdrawals and Roth conversions (the instructions say so for conversions). With wages, business, partnership and S-corp income of at most $3,000, the unused part covers other income (line 28b), and the total becomes the same share of line 27. Joint filers exclude only the income of the spouse who is 62 or older.

**Why it is not just a cap:** the steps are cliffs. A married couple at $100,000 excludes up to $100,000; at $100,001 it excludes half its eligible income. An LP that sees a plain cap would plan conversions straight through the cliff.

**Effect** (fork, couple born 1964, SS at 70, $300k taxable, $150k Roth, $1.5M tax-deferred, `maxSpending`, Medicare off, SS taxability 0.85): lifetime NJ tax $44,111 without the exclusion and $0 with it, spending +$1,519/yr. Without the exclusion NJ ranks below NY for this couple; with it, NJ is above NY.

**Implementation in the fork:** data fields `retirement_exclusion_tiers`, `_cap`, `_age`, `_earned_limit`; one binary per tier per eligible year, in the disaggregated (convex-hull) form, so only the copy of income above the last ceiling needs a big-M. A self-consistent-loop version 2-cycled and returned plans that undercharged their own tax, so the cliff has to be in the MILP.

**Solve time, and how the fork bounds it.** About 1 s per MILP for the couple above. With $2.5M tax-deferred the full MILP did not prove optimal in ten minutes (the choice of which high-conversion years to hold at $125k or $150k is combinatorial, and each alternative is worth a few hundred dollars). The fork does two things: (1) tier binaries are free only in years whose income, in the previous loop iteration, was at most 1.5x the top ceiling (the first iteration runs without the exclusion, and the set only grows, so at convergence every excluded year is far above $150k, where nothing is excluded anyway); (2) without `maxTime`, a MILP carrying these binaries stops at 60 s with a warning and its gap, and later iterations keep its tiers. A kept tier also bounds income from below, so a later iteration that wants less income can stop on the tier's floor, which is the ceiling of the tier below and belongs to that tier under the statute; such a year's tier is moved down to the statute's (only downward, at the same income, so it cannot cycle). Without that move, a 2 s cap left one year at exactly $150,000 claiming nothing instead of 25%. The $2.5M couple then returns in about a minute, 0.19% from proven optimal. Question for the maintainer: would you rather have this always on for NJ, or behind an option like `withMedicare`?
