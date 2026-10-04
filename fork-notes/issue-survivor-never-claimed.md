# Draft upstream issue (mdlacasse/Owl): survivor of a worker who died before claiming gets 82.5% of PIA

**Not filed yet.**

**Title:** Survivor benefit: a worker who dies before claiming should leave 100% of PIA (plus DRCs earned up to death), not the 82.5% floor

---

`compute_survivor_stream` (`socialsecurity.py`) sets the deceased's benefit to 0 when they had not started benefits by the year of death, so the survivor gets the floor, 0.825 x PIA:

```python
    else:
        deceased_monthly = 0.0  # Died before claiming; only the 82.5% PIA floor applies.

    monthly = max(deceased_monthly, 0.825 * pias[deceased_idx]) * _survivor_factor(survivor_fra, claim_age)
```

The 82.5% figure is the widow(er)'s limit (RIB-LIM). It caps a survivor benefit when the deceased had **reduced** their own benefit by claiming early: the survivor gets the larger of the deceased's reduced benefit and 82.5% of PIA (POMS RS 00615.320; Social Security Act 202(e)(2)(D)). A worker who was never entitled had no reduced benefit, so the limit doesn't apply. The survivor's base is 100% of PIA. If death came after FRA, it also includes the delayed retirement credits earned up to death. The paper lists the current behavior as a limitation ("credited with the 82.5% PIA floor rather than the benefit accrued to the date of death"). The gap is 17.5 to 49.5 points of PIA: 100% to 132% against 82.5%. It applies whenever the user's fixed claiming age is later than the first death. For example, a spouse planning to claim at 70 whose life expectancy is 68.

(Source note: ssa.gov, ecfr.gov and govinfo.gov were not reachable from where I checked this, so the rule above is from memory and secondary summaries of POMS RS 00615.320, not from the primary text. Please check it before relying on it.)

**Repro** (on `dev`, `c1e5619`), from the repository root:

```python
import numpy as np
from owlplanner import socialsecurity as ss

thisyear = 2026
# Person 0 (FRA 67) would claim at 70 but dies at the start of plan year 3; person 1 is 67 and outlives.
for age_now in (60, 66):
    yobs = np.array([thisyear - age_now, thisyear - 67])
    zeta, _ = ss.compute_social_security_benefits(
        np.array([2000, 400]), np.array([70.0, 67.0]), yobs, np.array([1, 1]), np.array([15, 15]),
        np.array([3, 20]), 2, 20, thisyear=thisyear,
    )
    print(f"deceased dies at {age_now + 3} before claiming (PIA $2,000/mo): survivor gets ${zeta[1, 5] / 12:,.0f}/mo")
```

On `dev`:

```
deceased dies at 63 before claiming (PIA $2,000/mo): survivor gets $1,650/mo
deceased dies at 69 before claiming (PIA $2,000/mo): survivor gets $1,650/mo
```

With the patch below:

```
deceased dies at 63 before claiming (PIA $2,000/mo): survivor gets $2,000/mo
deceased dies at 69 before claiming (PIA $2,000/mo): survivor gets $2,320/mo
```

**Suggested fix.** When the deceased had not claimed, set their benefit to `PIA x max(1, getSelfFactor(FRA, min(70, age at death)))`. That is the full PIA before FRA, and PIA plus the DRCs to death after it. The existing `max(..., 0.825 * PIA)` then never binds in this branch. Age at death uses the same convention as the survivor's age a few lines above. The paper's survivor paragraph and limitations list, and `info/modeling-capabilities.md`, are updated to match.

Verified against `dev` (`c1e5619`): with the patch alone the full suite gives RESULT_SURVIVOR; flake8 is clean. New test: `test_compute_ss_survivor_deceased_never_claimed` (two cases; both fail on `dev`). None of the 17 examples changes.

<details><summary>Patch (source, docs and tests, applies to <code>c1e5619</code>)</summary>

```diff
PATCH_SURVIVOR
```

</details>
