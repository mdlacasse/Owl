# Draft upstream issue (mdlacasse/Owl): ACA 2026 contribution between 133% and 150% FPL starts at 2.10% instead of 3.14%

**Filed upstream by the user on 2026-10-04** (issue number not recorded yet).

**Title:** ACA (loop mode): the 2026 applicable percentage from 133% to 150% FPL should run from 3.14% to 4.19%, not from 2.10%

---

[Rev. Proc. 2025-25](https://www.irs.gov/pub/irs-drop/rp-25-25.pdf), section 3.01, sets the 2026 applicable percentage table as:

| Household income (% FPL) | Initial | Final |
|---|---:|---:|
| below 133% | 2.10% | 2.10% |
| 133% to 150% | 3.14% | 4.19% |
| 150% to 200% | 4.19% | 6.60% |
| 200% to 250% | 6.60% | 8.44% |
| 250% to 300% | 8.44% | 9.96% |
| 300% to 400% | 9.96% | 9.96% |

Within each band the percentage "increases on a sliding scale in a linear manner" from the initial to the final percentage ([26 CFR 1.36B-3(g)(1)](https://www.ecfr.gov/current/title-26/section-1.36B-3#p-1.36B-3(g)(1))). The table jumps at 133%. `_ACA_CONTRIB_PCT_2026` stores one value per breakpoint, `[0.021, 0.0419, 0.066, 0.0844, 0.0996, 0.0996]`, and `_aca_contrib_pct` interpolates between consecutive values, so in the 133-150% band `acaCosts` runs from 2.10% (the rate below 133%) to 4.19%. Every other band starts where the previous one ends, so this is the only band affected. Because loop mode charges the full premium below 138% (Medicaid), the affected incomes are 138-150% FPL. There the expected contribution is understated by up to 0.73 points of MAGI, at 138%.


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

Verified against `dev` (`c1e5619`): with the patch alone the full suite gives 2604 passed, 1 skipped; flake8 is clean. New tests: `test_2026_band_133_150_starts_at_3_14`, which fails on `dev`, and `test_2026_bands_continuous_above_150`, which fails there only because the new constant is missing. None of the 17 examples changes.

<details><summary>Patch (source and tests, applies to <code>c1e5619</code>)</summary>

```diff
diff --git a/src/owlplanner/tax_federal.py b/src/owlplanner/tax_federal.py
index fb09240..99e7c2e 100644
--- a/src/owlplanner/tax_federal.py
+++ b/src/owlplanner/tax_federal.py
@@ -191,6 +191,10 @@ _ACA_CONTRIB_CAP_2025 = 0.085  # ARP/IRA cap above 400% FPL
 # If an extension is enacted, update to IRA-style rules (0% below 150%, 8.5% cap).
 _ACA_BREAKPOINTS_2026 = np.array([1.33, 1.50, 2.00, 2.50, 3.00, 4.00])
 _ACA_CONTRIB_PCT_2026 = np.array([0.021, 0.0419, 0.066, 0.0844, 0.0996, 0.0996])
+# Initial percentage of each band that starts at a breakpoint (133-150%, ..., 300-400%). The table
+# jumps at 133%: below it 2.10%, from it 3.14% rising to 4.19% at 150%. The other bands start where
+# the previous one ends.
+_ACA_CONTRIB_INITIAL_2026 = np.array([0.0314, 0.0419, 0.066, 0.0844, 0.0996])
 # No cap above 400%: full SLCSP (no PTC)
 
 # ACA LP bracket configuration (2026+ rules; used only in withACA="optimize" mode).
@@ -461,13 +465,18 @@ def mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn, *, include_part_d=Tru
     return costs
 
 
-def _aca_contrib_pct(ratio, breakpoints, contrib_pct):
-    """Interpolate contribution percentage from FPL ratio. Caller handles ratio below/above range."""
+def _aca_contrib_pct(ratio, breakpoints, contrib_pct, initial_pct=None):
+    """Interpolate contribution percentage from FPL ratio. Caller handles ratio below/above range.
+
+    The band from breakpoints[k] to breakpoints[k+1] runs from initial_pct[k] to contrib_pct[k+1].
+    Without initial_pct each band starts where the previous one ends (initial_pct[k] = contrib_pct[k]).
+    """
     idx = int(np.searchsorted(breakpoints, ratio, side="right")) - 1
     idx = max(0, min(idx, len(breakpoints) - 2))
     lo, hi = breakpoints[idx], breakpoints[idx + 1]
     t = (ratio - lo) / (hi - lo)
-    return contrib_pct[idx] + t * (contrib_pct[idx + 1] - contrib_pct[idx])
+    start = contrib_pct[idx] if initial_pct is None else initial_pct[idx]
+    return start + t * (contrib_pct[idx + 1] - start)
 
 
 def acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual, N_n, thisyear=None, n_aca_start=0):
@@ -576,7 +585,9 @@ def acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual, N_n, thisyear=None,
             if ratio < _ACA_BREAKPOINTS_2026[0]:
                 cap_pct = _ACA_CONTRIB_PCT_2026[0]
             else:
-                cap_pct = _aca_contrib_pct(ratio, _ACA_BREAKPOINTS_2026, _ACA_CONTRIB_PCT_2026)
+                cap_pct = _aca_contrib_pct(
+                    ratio, _ACA_BREAKPOINTS_2026, _ACA_CONTRIB_PCT_2026, _ACA_CONTRIB_INITIAL_2026
+                )
 
         costs[n] = min(slcsp, cap_pct * magi)
 
diff --git a/tests/tax/test_aca.py b/tests/tax/test_aca.py
index e3d0207..50e3918 100644
--- a/tests/tax/test_aca.py
+++ b/tests/tax/test_aca.py
@@ -216,6 +216,29 @@ class TestAcaCostsFunction:
         costs = tx.acaCosts(yobs, horizons, np.full(5, magi), gamma_n, slcsp_annual=slcsp, N_n=5, thisyear=2026)
         assert np.isclose(costs[0], slcsp, rtol=1e-4), "2026 above 400%: expect full premium"
 
+    def test_2026_band_133_150_starts_at_3_14(self):
+        """2026 (Rev. Proc. 2025-25): the 133-150% band runs from 3.14% to 4.19%, not from 2.10%."""
+        yobs = np.array([1985])
+        horizons = np.array([5])
+        fpl_2026 = tx._ACA_FPL[2026][0]
+        gamma_n = self._gamma(5)
+        slcsp = 12_000.0
+        for ratio in (1.40, 1.45, 1.4999):
+            magi = ratio * fpl_2026
+            costs = tx.acaCosts(
+                yobs, horizons, np.full(5, magi), gamma_n, slcsp_annual=slcsp, N_n=5, thisyear=2026
+            )
+            pct = 0.0314 + (ratio - 1.33) / (1.50 - 1.33) * (0.0419 - 0.0314)
+            assert np.isclose(costs[0], pct * magi, rtol=1e-6), f"ratio {ratio}: {costs[0]} vs {pct * magi}"
+
+    def test_2026_bands_continuous_above_150(self):
+        """2026: the percentage is continuous at 150%, 200%, 250% and 300% FPL."""
+        bp, pct, init = tx._ACA_BREAKPOINTS_2026, tx._ACA_CONTRIB_PCT_2026, tx._ACA_CONTRIB_INITIAL_2026
+        for k in range(1, len(bp) - 1):
+            below = tx._aca_contrib_pct(bp[k] - 1e-9, bp, pct, init)
+            above = tx._aca_contrib_pct(bp[k], bp, pct, init)
+            assert np.isclose(below, above, atol=1e-6), f"jump at {bp[k]}: {below} vs {above}"
+
 
 # ---------------------------------------------------------------------------
 # Integration tests using Plan.solve()
```

</details>
