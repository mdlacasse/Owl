# Draft upstream issue (mdlacasse/Owl): withACA="optimize" infeasible where the contribution exceeds the premium

**Filed as mdlacasse/Owl#161.**

**Title:** `withACA="optimize"`: plans infeasible below 400% FPL when the expected contribution exceeds the SLCSP

---

In optimize mode, the ACA cost row is an equality,

```
maca_n = sum_{r<6} pct_r * haca_{n,r} + SLCSP_n * za_{n,6}
```

and `_add_ACA_costs` also bounds `maca_n <= SLCSP_n`. The net premium is `min(SLCSP, pct * MAGI)`, and `acaCosts` (loop mode) computes it that way. In the MILP, though, any MAGI below 400% FPL where `pct_r * MAGI > SLCSP` violates the bound. Instead of costing the full premium, that MAGI is infeasible. When the household can't move its income out of that band, the whole case is reported infeasible. The band needs a low SLCSP relative to income: a younger household, a cheap market, or the couple-to-individual scaling after one spouse reaches 65. For a single filer in the 300-400% bracket, 9.96% x 400% FPL is $6,358, so any SLCSP below that opens a band.

**Repro** (on `dev`, `a85ff76`). A single filer born 1976, a $4,600/month indexed pension and no tax-deferred account, so MAGI sits near 370% FPL and can't move. Medicare off, SS taxability pinned.

```python
import io
import owlplanner as owl

def run(mode, slcsp):
    p = owl.Plan(["Cy"], ["1976-06-15"], [85], "aca", verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[0], taxFree=[50], startDate="01-01")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("user", values=[6, 4, 3, 2.5])
    p.setPension([4600], [45], indexed=[True])
    p.setACA(slcsp)
    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85, "withACA": mode})
    out = (p.caseStatus, round(p.basis) if p.caseStatus == "solved" else None)
    if p.caseStatus == "solved":
        out += ([round(v) for v in p.aca_costs_n[1:4]], [round(v) for v in p.MAGI_aca_n[1:4]])
    return out

for s in (5.0, 9.0):
    print(f"SLCSP ${s}k  loop:", run("loop", s), "  optimize:", run("optimize", s))
```

Columns: status, spending basis, ACA cost in years 1-3, ACA MAGI in years 1-3. On `dev`:

```
SLCSP $5.0k  loop: ('solved', 53058, [5125, 5253, 5384], [59137, 60472, 61834])   optimize: ('infeasible', None)
SLCSP $9.0k  loop: ('solved', 52718, [5889, 6021, 6155], [59125, 60449, 61798])   optimize: ('solved', 52718, [5889, 6021, 6155], [59125, 60449, 61798])
```

With the patch below:

```
SLCSP $5.0k  loop: ('solved', 53058, [5125, 5253, 5384], [59137, 60472, 61834])   optimize: ('solved', 53058, [5125, 5253, 5384], [59137, 60472, 61834])
SLCSP $9.0k  loop: ('solved', 52718, [5889, 6021, 6155], [59125, 60449, 61798])   optimize: ('solved', 52718, [5889, 6021, 6155], [59125, 60449, 61798])
```

**Suggested fix.** The applicable percentage only rises from one bracket to the next, so from the first MAGI where a bracket's charge reaches the SLCSP, every higher income pays the full premium, which is bracket 6's cost. `acaVals` can therefore clip the thresholds at that crossing, `Lbar_r <- min(Lbar_r, MAGI*)`, so those incomes fall in bracket 6. Brackets left with zero width get their binary fixed to 0. The change is parameter-only: no new variables or rows, and nothing changes when the SLCSP exceeds every bracket's charge.

Two related gaps between optimize and loop mode are left alone here. I can file them separately if you want them:

- Optimize mode charges each bracket's top rate across the whole bracket (`_ACA_LP_CONTRIB`), while loop mode interpolates the sliding scale. Inside a bracket the MILP overcharges, and it adds cliffs at 150/200/250/300% FPL.
- Below 138% FPL, loop mode charges the full SLCSP (Medicaid assumption), while optimize mode charges 2.1%.

Re-checked on `dev` `3c88ce1` (after the #157 fix): the patch applies cleanly, the repro output is identical before and after, and the full suite gives 2604 passed, 1 skipped. First verified against `dev` (`a85ff76`): with this patch alone the full suite gives 2596 passed, 1 skipped; flake8 is clean. Tests added in `tests/tax/test_aca.py::TestACAOptimize`: a unit test of the clipping and the repro above as a plan test. Both fail on `dev`.

<details><summary>Patch (source and tests, applies to <code>a85ff76</code>)</summary>

```diff
diff --git a/src/owlplanner/plan.py b/src/owlplanner/plan.py
index 3de39bb..7b3ba07 100644
--- a/src/owlplanner/plan.py
+++ b/src/owlplanner/plan.py
@@ -3920,8 +3920,13 @@ class Plan:
 
                 if r < tx.N_ACA_R - 1:
                     upper = self.Lbar_aca_nr[nn, r]
+                    if upper <= lower:
+                        # Above the MAGI where the contribution reaches the SLCSP (see
+                        # tx._aca_capped_limits): such incomes belong to the full-premium bracket.
+                        self.B.setRange(za_idx, 0, 0)
                 else:
-                    # Last bracket (above 400% FPL): use BigM as upper bound so haca = 0 when za = 0.
+                    # Last bracket (full SLCSP, from 400% FPL or the cap crossing): BigM upper bound
+                    # so haca = 0 when za = 0.
                     upper = self._ceiling_n[nn]  # the year's MAGI ceiling
                 self.A.addNewRow({haca_idx: 1, za_idx: -upper}, -np.inf, 0, tag=("aca_bracket_ub", nn, r))
 
diff --git a/src/owlplanner/tax_federal.py b/src/owlplanner/tax_federal.py
index fb09240..f89ecef 100644
--- a/src/owlplanner/tax_federal.py
+++ b/src/owlplanner/tax_federal.py
@@ -583,6 +583,25 @@ def acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual, N_n, thisyear=None,
     return costs
 
 
+def _aca_capped_limits(limits, contrib_pct, slcsp):
+    """Clip the LP bracket thresholds at the MAGI where the expected contribution reaches the SLCSP.
+
+    The net premium is min(SLCSP, pct * MAGI), but bracket r of the LP charges pct_r * MAGI with
+    the cost capped at the SLCSP by a bound, which made every MAGI with pct_r * MAGI > SLCSP below
+    400% FPL infeasible instead of costing the full premium. Contributions only rise from one bracket
+    to the next, so from the first MAGI where the charge reaches the SLCSP, every higher income pays
+    the full premium: the cost of the last bracket. Clipping the thresholds there moves those incomes
+    into the last bracket; the brackets above the crossing get zero width.
+    """
+    lower = 0.0
+    for r, upper in enumerate(limits):
+        pct = contrib_pct[r]
+        if pct > 0 and slcsp <= pct * upper:
+            return np.minimum(limits, max(lower, slcsp / pct))
+        lower = upper
+    return limits
+
+
 def acaVals(yobs, horizons, gamma_n, slcsp_annual, Nn, n_aca_start=0):
     """
     Return (n_aca, Lbar_aca_nr, cap_pct_aca_r, slcsp_aca_n) for the ACA LP/MIP formulation.
@@ -595,6 +614,7 @@ def acaVals(yobs, horizons, gamma_n, slcsp_annual, Nn, n_aca_start=0):
       - No year-awareness for contribution rates: always 2026 rules. Plans starting in 2025
         use 2026 rates; SC-loop mode (acaCosts) is year-aware.
       - MAGI below 138% FPL: LP uses bracket 0 at 2.1% instead of full SLCSP (Medicaid).
+      - Each bracket charges one rate (its top one), where acaCosts interpolates the sliding scale.
 
     Parameters
     ----------
@@ -617,7 +637,8 @@ def acaVals(yobs, horizons, gamma_n, slcsp_annual, Nn, n_aca_start=0):
     n_aca : int
         Number of ACA-eligible plan years (0 = no ACA in LP).
     Lbar_aca_nr : ndarray, shape (n_aca, N_ACA_R-1)
-        Inflation-adjusted FPL bracket thresholds per year ($).
+        Inflation-adjusted FPL bracket thresholds per year ($), clipped at the MAGI where the
+        contribution reaches the SLCSP (see _aca_capped_limits).
     cap_pct_aca_r : ndarray, shape (N_ACA_R,)
         Contribution rates per bracket (constant across years).
     slcsp_aca_n : ndarray, shape (n_aca,)
@@ -654,7 +675,6 @@ def acaVals(yobs, horizons, gamma_n, slcsp_annual, Nn, n_aca_start=0):
         fpl_year = calendar_year if calendar_year in _ACA_FPL else fpl_max_year
         fpl = _ACA_FPL[fpl_year][hh_size - 1] * gamma_n[n]
 
-        Lbar[nn] = _ACA_LP_BREAKPOINTS * fpl
         # Scale SLCSP for couple-to-individual transition (same logic as acaCosts).
         if Ni == 2 and hh_size == 1:
             age_remaining = thisyear + n - yobs[eligible[0]]
@@ -662,6 +682,7 @@ def acaVals(yobs, horizons, gamma_n, slcsp_annual, Nn, n_aca_start=0):
         else:
             slcsp_scale = 1.0
         slcsp_aca_n[nn] = slcsp_annual * slcsp_scale * gamma_n[n]
+        Lbar[nn] = _aca_capped_limits(_ACA_LP_BREAKPOINTS * fpl, _ACA_LP_CONTRIB, slcsp_aca_n[nn])
 
     return n_aca, Lbar, _ACA_LP_CONTRIB.copy(), slcsp_aca_n
 
diff --git a/tests/tax/test_aca.py b/tests/tax/test_aca.py
index e3d0207..499832f 100644
--- a/tests/tax/test_aca.py
+++ b/tests/tax/test_aca.py
@@ -376,6 +376,44 @@ class TestACAOptimize:
                 )
         assert hit_bracket_6, "Expected at least one ACA year with MAGI >= 400% FPL and maca > 0"
 
+    def test_capped_limits_move_full_premium_incomes_to_last_bracket(self):
+        """Thresholds are clipped where the bracket's charge pct_r * MAGI reaches the SLCSP."""
+        fpl = 15_960.0
+        limits = tx._ACA_LP_BREAKPOINTS * fpl
+        # 5,000 / 9.96% = 50,201 lies in the 300-400% bracket [47,880, 63,840].
+        capped = tx._aca_capped_limits(limits, tx._ACA_LP_CONTRIB, 5_000.0)
+        assert np.allclose(capped, np.minimum(limits, 5_000.0 / 0.0996))
+        # A premium above every bracket's charge leaves the thresholds alone.
+        assert np.allclose(tx._aca_capped_limits(limits, tx._ACA_LP_CONTRIB, 20_000.0), limits)
+        # No premium (before coverage starts): every income is in the last bracket, at no cost.
+        assert np.allclose(tx._aca_capped_limits(limits, tx._ACA_LP_CONTRIB, 0.0), 0.0)
+
+    def test_income_where_contribution_exceeds_premium_is_feasible(self):
+        """Below 400% FPL with 9.96% x MAGI above the SLCSP: full premium, not infeasibility.
+
+        No tax-deferred account, so MAGI (a $55k pension plus investment income, about 370% FPL)
+        cannot be moved out of the band. The bound maca <= SLCSP used to make this infeasible.
+        """
+        def solve(mode):
+            p = Plan(["Cy"], ["1976-06-15"], [85], "aca band", verbose=False)
+            p.setSpendingProfile("flat")
+            p.setAccountBalances(taxable=[100], taxDeferred=[0], taxFree=[50], startDate="01-01")
+            p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
+            p.setRates("user", values=[6, 4, 3, 2.5])
+            p.setPension([4600], [45], indexed=[True])
+            p.setACA(5.0)
+            p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85,
+                                    "withACA": mode})
+            return p
+
+        p_opt, p_loop = solve("optimize"), solve("loop")
+        assert p_opt.caseStatus == "solved"
+        for n in range(1, 4):
+            ratio = p_opt.MAGI_aca_n[n] / (tx._ACA_FPL[2026][0] * p_opt.gamma_n[n])
+            assert 3.0 < ratio < 4.0
+            assert p_opt.maca_n[n] == pytest.approx(5_000 * p_opt.gamma_n[n], rel=1e-6)
+        assert p_opt.basis == pytest.approx(p_loop.basis, rel=1e-4)
+
 
 # ---------------------------------------------------------------------------
 # Config round-trip test
```

</details>
