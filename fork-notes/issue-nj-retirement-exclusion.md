# Draft upstream issue (mdlacasse/Owl): New Jersey's retirement income exclusion is missing

**Title:** State tax: New Jersey pension/retirement exclusion (NJ-1040 line 28) is not modeled, so NJ tax is overstated for retirees

Status: draft. File after deciding what to do about the solve-time problem below; the maintainer will ask about it. Reference implementation: fork commit `7fcfadf` (branch `claude/relaxed-turing-xzrv89`).

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

**Open question for the maintainer — solve time:** about 1 s per MILP for the couple above, but with $2.5M tax-deferred the MILP stays 0.4-0.9% from proven optimal after a minute. Options: accept that and rely on `maxTime`; free the binaries only in years whose income is near a ceiling; or offer the exclusion behind an option (like `withMedicare`), off by default.
