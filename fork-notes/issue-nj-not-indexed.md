# Draft comment for upstream #157 (mdlacasse/Owl): New Jersey is not indexed either

Post as a comment on #157 (it is the same defect, and the same `indexed` flag fixes it). Fork commit: `20ccb2d`.

---

The same applies to New Jersey. The NJ-1040 instructions print the same rate schedules in 2020 and 2025 (Tables A and B: Single 20,000 / 35,000 / 40,000 / 75,000 / 500,000 / 1,000,000; MFJ 20,000 / 50,000 / 70,000 / 80,000 / 150,000 / 500,000 / 1,000,000), and the same $1,000 regular and age-65 exemptions (lines 6-7). On `dev` (`a85ff76`) Owl inflates them like every state's:

```python
import numpy as np
from owlplanner import tax_state

gamma = np.array([1.025**n for n in range(31)])
res = tax_state.st_taxParams("NJ", 2, 30, 30, gamma, [1964, 1964], mobs=[6, 12])
delta, sigma = res[2], res[3]
for n in (0, 10, 20):
    lower = np.concatenate(([0.0], np.cumsum(delta[:, n])[:-1]))
    print(f"year {n:2d}: thresholds " + " / ".join(f"{x:,.0f}" for x in lower[1:7]) + f"   deduction {sigma[n]:,.0f}")
```

```
year  0: thresholds 20,000 / 50,000 / 70,000 / 80,000 / 150,000 / 500,000   deduction 0
year 10: thresholds 25,602 / 64,004 / 89,606 / 102,407 / 192,013 / 640,042   deduction 0
year 20: thresholds 32,772 / 81,931 / 114,703 / 131,089 / 245,792 / 819,308   deduction 0
```

The output also shows a second, smaller problem: NJ's `standard_deduction` is 0, but the data header says the field holds personal exemptions, and NJ allows $1,000 per filer (line 6), plus $1,000 per filer aged 65+ (line 7).

Effect on the same couple as above, with the `indexed` flag set false for NJ and the $1,000 exemptions in both runs. These figures come from our fork (branch `claude/relaxed-turing-xzrv89`), with NJ's retirement exclusion switched off so the two runs differ only in indexing. Lifetime NJ tax in today's dollars:

| Tax-deferred | NJ tax, indexed (as `dev`) | NJ tax, not indexed | Difference | Spending change |
|---:|---:|---:|---:|---:|
| $1.5M | 35,694 | 44,111 | +8,417 | -$200/yr |
| $2.5M | 89,262 | 108,561 | +19,299 | -$480/yr |

Suggested data change, on top of the patch above:

```toml
[NJ_Single]
standard_deduction = 1000   # $1,000 regular exemption (line 6); the 65+ one is not modeled
indexed = false             # same schedules and exemptions in the 2020 and 2025 NJ-1040 instructions

[NJ_MFJ]
standard_deduction = 2000
indexed = false
```
