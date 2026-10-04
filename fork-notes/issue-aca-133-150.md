# Draft upstream issue (mdlacasse/Owl): ACA 2026 contribution between 133% and 150% FPL starts at 2.10% instead of 3.14%

**Not filed yet.**

**Title:** ACA (loop mode): the 2026 applicable percentage from 133% to 150% FPL should run from 3.14% to 4.19%, not from 2.10%

---

Rev. Proc. 2025-25 sets the 2026 applicable percentage table as:

| Household income (% FPL) | Initial | Final |
|---|---:|---:|
| below 133% | 2.10% | 2.10% |
| 133% to 150% | 3.14% | 4.19% |
| 150% to 200% | 4.19% | 6.60% |
| 200% to 250% | 6.60% | 8.44% |
| 250% to 300% | 8.44% | 9.96% |
| 300% to 400% | 9.96% | 9.96% |

The table jumps at 133%. `_ACA_CONTRIB_PCT_2026` stores one value per breakpoint, `[0.021, 0.0419, 0.066, 0.0844, 0.0996, 0.0996]`, and `_aca_contrib_pct` interpolates between consecutive values, so in the 133-150% band `acaCosts` runs from 2.10% (the rate below 133%) to 4.19%. Every other band starts where the previous one ends, so this is the only band affected. Because loop mode charges the full premium below 138% (Medicaid), the affected incomes are 138-150% FPL. There the expected contribution is understated by up to 0.73 points of MAGI, at 138%.

(Source note: irs.gov was not reachable from where I checked this. The table above matches my reading of Rev. Proc. 2025-25 and several secondary summaries of it. Please check it against the Rev. Proc. before relying on it.)

**Repro** (on `dev`, `c1e5619`), from the repository root:

```python
import numpy as np
from owlplanner import tax_federal as tx

fpl = tx._ACA_FPL[2026][0]  # single, 2026
yobs, horizons, gamma = np.array([1985]), np.array([3]), np.ones(4)
print(" FPL%   MAGI     Owl cost  Owl pct   Rev.Proc.2025-25 pct  cost")
for r in (1.38, 1.40, 1.45, 1.49):
    magi = r * fpl
    cost = tx.acaCosts(yobs, horizons, np.full(3, magi), gamma, slcsp_annual=12_000, N_n=3, thisyear=2026)[0]
    pct = 0.0314 + (r - 1.33) / 0.17 * (0.0419 - 0.0314)
    print(f" {r*100:4.0f}  {magi:7.0f}  {cost:8.0f}  {cost/magi*100:6.2f}%  {pct*100:6.2f}%  {pct*magi:8.0f}")
```

On `dev`:

```
 FPL%   MAGI     Owl cost  Owl pct   Rev.Proc.2025-25 pct  cost
  138    22025       598    2.71%    3.45%       760
  140    22344       662    2.96%    3.57%       798
  145    23142       827    3.58%    3.88%       898
  149    23780       967    4.07%    4.13%       982
```

With the patch below, the Owl columns equal the Rev. Proc. columns (760, 798, 898, 982).

**Suggested fix.** Add the initial percentage of each band (`_ACA_CONTRIB_INITIAL_2026`), and give `_aca_contrib_pct` an optional `initial_pct` argument; without it, each band starts where the previous one ends, as before, so the 2025 table is unchanged. `withACA="optimize"` is not touched: its brackets charge each band's final rate (`_ACA_LP_CONTRIB`), which is a separate question.

Verified against `dev` (`c1e5619`): with the patch alone the full suite gives RESULT_ACA; flake8 is clean. New tests: `test_2026_band_133_150_starts_at_3_14`, which fails on `dev`, and `test_2026_bands_continuous_above_150`, which fails there only because the new constant is missing. None of the 17 examples changes.

<details><summary>Patch (source and tests, applies to <code>c1e5619</code>)</summary>

```diff
PATCH_ACA
```

</details>
