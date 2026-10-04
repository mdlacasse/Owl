# Draft reply on mdlacasse/Owl#160 (NJ retirement exclusion), after the maintainer's answer of 2026-10-04

Replaces the earlier follow-up draft (`issue-nj-retirement-exclusion-comment.md`, superseded). Short on purpose.

---

Thanks for checking the rule, and agreed on all of it. The tiers are cliffs, so there's no exact LP form. A loop version cycles: in my fork it settled into a 2-cycle that undercharged its own NJ tax by $13.9k. And a concave bound that stays under the staircase across the whole income range throws away most of the exclusion. Keeping the state layer LP-only and documenting the overstatement makes sense for Owl.

My fork keeps the exclusion, because I'm using Owl to compare living in New York and New Jersey, and the exclusion decides that comparison. For the couple in the issue, with Medicare off and SS taxability pinned:

| Tax-deferred | NJ vs NY, no exclusion | NJ vs NY, with exclusion |
|---|---:|---:|
| $1.5M | -$476/yr | +$1,007/yr |
| $2.5M | -$323/yr | +$903/yr |

These include NJ's senior exemption from your #157 fix.

On the broader strategy, if it ever comes up again: the state data already notes a few other income-gated rules. Some are cliffs, like KS's and MO's Social Security thresholds (marked binary in the data) and IL's exemption, which disappears above $250k/$500k. Others are phase-outs, like NM's 65+ exemption, RI's exemption, WI's standard deduction and SC's senior deduction. One data schema could describe them all: tiers or ramps on any exemption, exclusion or credit, keyed on state income. Each entry would carry a solve mode, off by default (today's conservative behavior), with loop or exact MILP as opt-ins. The default plan would stay a pure LP. Happy to sketch it in a separate design issue when you want one.

On the multiple fixed points: I found two things in the cycle handling that look worth fixing whatever else you try there. A flat objective gets reported as a 2-cycle while the loop is still converging (`Case_cameron` stops with $29,773 of SS residual and converges to $1,302 if it runs on). And within a real cycle, the loop keeps the highest objective rather than the most self-consistent iterate. I'll file that as its own issue with a repro and a patch.
