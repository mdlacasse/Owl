# Draft upstream issue (mdlacasse/Owl): the claiming-age MILP charges every candidate age the same tax on SS

**Filed upstream by the user on 2026-10-04** (issue number not recorded yet).

**Title:** `withSSAges="optimize"`: taxable SS, IRMAA/ACA MAGI and the state SS exclusion use the previous iterate's benefits, so the MILP compares claiming ages on pre-tax benefits

---

With `withSSAges="optimize"`, the own benefit is the LP variable `ssb[i,n] = sum_k B_own[i,k,n] * zssa[i,k]`. It appears in the cash-flow row only. Every row that charges tax or premiums on SS still uses the parameter `zetaBar_in` from the previous iterate:

- taxable income, `Psi_n * zetaBar_in[i,n]` (`_add_taxable_income`);
- IRMAA MAGI, `Psi_n[n2] * zetaBar_in[i,n2]` (`_configure_Medicare_binary_variables`);
- ACA MAGI, the full `zetaBar_in[i,n]` (`_configure_ACA_binary_variables`);
- the state SS exclusion, `Psi_n * sum_i zetaBar_in` (`_add_state_taxable_income`).

So within one MILP, every candidate claiming age is charged the same tax on SS. That is the tax on the benefits of the age the previous iterate chose. The loop then has to find the right age by trial. Its fixed point depends on where it starts, and the accepted plan can be one whose tax was computed for a different benefit stream. Chapter 11 of the paper says only the spousal and survivor amounts go through the loop.

**Repro** (on `dev`, `c1e5619`), from the repository root. A single filer with tax-deferred savings only, constant rates, an indexed pension from 63, Medicare off and the taxable share pinned. Nothing else is fed back, so with the benefits priced in the MILP each solve is exact.

```python
import io
from datetime import date
import owlplanner as owl

ty = date.today().year
OPTS = {"withMedicare": "None", "withSSTaxability": 0.85, "bequest": 0}

def plan(age):
    p = owl.Plan(["Bo"], [f"{ty - 61}-03-15"], [85], "ss", verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[0], taxDeferred=[300], taxFree=[0], startDate="01-01")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("user", values=[6, 4, 3, 2.5])
    p.setSocialSecurity([3000], [age])
    p.setPension([8000], [63], indexed=[True])
    return p

for start in (62, 70):
    p = plan(start)
    p.solve("maxSpending", options={**OPTS, "withSSAges": "optimize"})
    age = float(p.ssecAges[0])
    q = plan(age)
    q.solve("maxSpending", options=OPTS)
    print(f"start {start}: chose {age:.3f}, spending {p.g_n[0]:,.0f}/yr; fixed-age solve at {age:.3f}: {q.g_n[0]:,.0f}/yr")
```

On `dev`:

```
start 62: chose 64.417, spending 104,526/yr; fixed-age solve at 64.417: 104,518/yr
start 70: chose 64.417, spending 104,518/yr; fixed-age solve at 64.417: 104,518/yr
```

Starting from 62, the accepted plan reports $8/yr more than that same claiming age gives when its taxes are computed for its own benefits. With the patch below, both starts return 104,518/yr, equal to the fixed-age solve. In a variant without the pension, starting from 62, `dev` settles on 68 5/12. The patch picks 68 3/12, which a fixed-age solve confirms is better by $4.7/yr. The amounts are small here because, at a pinned 85%, the tax on SS is close to proportional to the benefit. The bias grows where the marginal rate on SS differs across the candidate claiming years: a pension or wages that stop, an IRMAA tier, or the ACA band.

**Suggested fix.** Add a helper `_ss_benefit_terms(i, n)` that returns `(spousal/survivor offset, ssb column)` when `ssb` exists, and `(zetaBar_in[i,n], None)` otherwise. Use it in the four rows above. The constant part goes to the right-hand side as before, and `ssb` enters the row with the same coefficient, `Psi_n` (or 1 for ACA MAGI). `Psi_n` stays the loop's lagged taxable share, so a candidate age is charged at the previous iterate's share of its **own** benefits. Rows are rebuilt every iteration already, so `_fixedAcrossIterations` is not affected.

Not covered: `withSSTaxability="optimize"`. Its provisional-income and `tss` rows still use `zetaBar_in`. The 50% tier is `min(SS, ...)`, which would need another binary per year once SS is a variable. The patch adds this to the paper's limitations list for Chapter 11, and the chapter's text now says how the tax rows see the benefit.

Verified against `dev` (`c1e5619`): with the patch alone the full suite gives 2604 passed, 1 skipped; flake8 is clean. New tests: `TestClaimingAgeTaxes::test_tax_rows_carry_ssb` and `test_result_independent_of_starting_age_and_consistent`. Both fail on `dev`. None of the 17 examples changes (none uses `withSSAges="optimize"`).

<details><summary>Patch (source, paper and tests, applies to <code>c1e5619</code>)</summary>

```diff
diff --git a/papers/owl.tex b/papers/owl.tex
index 618b7c5..3a009be 100644
--- a/papers/owl.tex
+++ b/papers/owl.tex
@@ -5293,7 +5293,15 @@ The spousal/survivor offset is then updated as
 so that the difference between the total benefit and the own benefit
 at the chosen age is passed to the next LP iteration as a fixed income term.
 The variable $\bar{\zeta}_{in}$ in the plan is simultaneously updated to
-$\bar{\zeta}_{in}^{\mathrm{new}}$ for use in taxability and MAGI computations.
+$\bar{\zeta}_{in}^{\mathrm{new}}$ for reporting and for the SC-loop quantities
+computed after each solve.
+Within each LP, every row that charges tax or premiums on benefits uses the
+benefit variable rather than $\bar{\zeta}_{in}$: taxable income carries
+$\Psi_n(\delta^\mathrm{sp}_{in} + b^\mathrm{ss}_{in})$, and so do the
+IRMAA MAGI rows and the state SS exclusion, while the ACA MAGI rows carry the full
+$\delta^\mathrm{sp}_{in} + b^\mathrm{ss}_{in}$.
+Each candidate claiming age is therefore charged the tax on its own benefits,
+at the taxable share $\Psi_n$ of the previous iterate.
 
 \paragraph*{Convergence and oscillation.}
 \label{sec:ss-scloop}
@@ -5328,6 +5336,11 @@ streams as in the base mode.
           They are approximated through the SC loop, which may require several
           iterations for couple cases and can oscillate when the two partners'
           optimal ages are mutually dependent.
+    \item With \code{withSSTaxability="optimize"}, the provisional-income and
+          taxable-SS rows still use the previous iterate's benefits
+          $\bar{\zeta}_{in}$, because the taxable-SS formula takes the minimum
+          of the benefit and the provisional-income excess, which would need
+          another binary per year once the benefit is a variable.
     \item The survivor benefit is assumed to be claimed in the year of the
           spouse's death; the strategy of deferring the survivor benefit to a
           later age is not optimized.
diff --git a/src/owlplanner/plan.py b/src/owlplanner/plan.py
index 76abd9d..f01e236 100644
--- a/src/owlplanner/plan.py
+++ b/src/owlplanner/plan.py
@@ -2651,8 +2651,12 @@ class Plan:
         # through tss: Psi_n there lags the LP by one self-consistent iteration.
         ss_lp = "tss" in vm
         # SS adjustment: federal G_n contains taxable SS; remove it if state excludes SS.
-        if self.st_tax_ss or ss_lp:
+        excluded = not (self.st_tax_ss or ss_lp)
+        if not excluded:
             ss_excl_n = np.zeros(self.N_n)
+        elif "ssb" in vm:
+            # With withSSAges="optimize" the own benefit is the ssb variable (added to the row below).
+            ss_excl_n = self.Psi_n * self._ssa_spousal_offset.sum(axis=0)
         else:
             ss_excl_n = self.Psi_n * np.sum(self.zetaBar_in, axis=0)
         # Pension exemption (parameter): each person's pension up to their own cap.
@@ -2675,6 +2679,9 @@ class Plan:
                 row.addElem(vm["q"].idx(p, n), -1)  # subtract Q_n (capital gains)
             if ss_lp and not self.st_tax_ss:
                 row.addElem(vm["tss"].idx(n), 1)  # exclude taxable SS (LP variable)
+            elif excluded and "ssb" in vm:
+                for i in range(self.N_i):
+                    row.addElem(vm["ssb"].idx(i, n), self.Psi_n[n])  # exclude Psi_n * own benefit
             self.A.addRow(row, rhs, rhs, tag=("state_taxable_income", n))
 
         # A personal credit only offsets tax: the credit used stays below the year's state tax.
@@ -3218,14 +3225,18 @@ class Plan:
                         + self.spiaBar_in[i, n]
                     )
                 else:
+                    ss_const, ssb_idx = self._ss_benefit_terms(i, n)
                     rhs += (
                         self.omega_in[i, n]
                         + self.other_inc_in[i, n]
                         + self.netinv_in[i, n]
-                        + self.Psi_n[n] * self.zetaBar_in[i, n]
+                        + self.Psi_n[n] * ss_const
                         + self.piBar_in[i, n]
                         + self.spiaBar_in[i, n]
                     )
+                    if ssb_idx is not None:
+                        # Taxable SS follows the claiming age the MILP picks (Psi_n lags).
+                        row.addElem(ssb_idx, -self.Psi_n[n])
                 row.addElem(self.vm["w"].idx(i, 1, n), -1)
                 row.addElem(self.vm["x"].idx(i, n), -1)
                 fak = fak_in[i, n]
@@ -3381,6 +3392,17 @@ class Plan:
             )
             self.B.setRange(tss_idx, 0, 0.85 * zetaBar_n)  # t^σ ≤ 0.85·ζ̄
 
+    def _ss_benefit_terms(self, i, n):
+        """Person i's SS income in year n as (constant part, ssb column index or None).
+
+        With withSSAges="optimize" the own benefit is the LP variable ssb[i, n] and only the
+        spousal/survivor offset is a parameter, so every row that charges tax or premiums on SS
+        sees the benefit of the claiming age the MILP picks. Otherwise all of it is zetaBar.
+        """
+        if "ssb" in self.vm:
+            return self._ssa_spousal_offset[i, n], self.vm["ssb"].idx(i, n)
+        return self.zetaBar_in[i, n], None
+
     def _ssaAgeIsFixed(self, i):
         """
         Return True if individual i's SS claiming age is not a free decision variable.
@@ -3812,7 +3834,10 @@ class Plan:
                     + 0.5 * self.kappa_ijn[i, 0, n2] * afac
                 )
                 if not ss_lp:
-                    sumoni += self.Psi_n[n2] * self.zetaBar_in[i, n2]  # taxable SS (SC-loop param)
+                    ss_const, ssb_idx = self._ss_benefit_terms(i, n2)
+                    sumoni += self.Psi_n[n2] * ss_const  # taxable SS (SC-loop param)
+                    if ssb_idx is not None:
+                        row.addElem(ssb_idx, -self.Psi_n[n2])
                 rhs += sumoni
 
             if ss_lp:
@@ -3908,11 +3933,14 @@ class Plan:
                 row_magi[d_idx] = row_magi.get(d_idx, 0) - afac
                 row_magi[w0_idx] = row_magi.get(w0_idx, 0) + (afac - bfac)
 
+                ss_const, ssb_idx = self._ss_benefit_terms(i, n)
+                if ssb_idx is not None:
+                    row_magi[ssb_idx] = row_magi.get(ssb_idx, 0) - 1
                 rhs_magi += (
                     self.omega_in[i, n]
                     + self.other_inc_in[i, n]
                     + self.netinv_in[i, n]
-                    + self.zetaBar_in[i, n]  # full SS (not 0.5×SS; ACA uses MAGI)
+                    + ss_const  # full SS (not 0.5×SS; ACA uses MAGI)
                     + self.piBar_in[i, n]
                     + self.spiaBar_in[i, n]
                     + 0.5 * self.kappa_ijn[i, 0, n] * afac
diff --git a/tests/ss/test_ss_ages.py b/tests/ss/test_ss_ages.py
index 4cfcaf2..5ff9eef 100644
--- a/tests/ss/test_ss_ages.py
+++ b/tests/ss/test_ss_ages.py
@@ -305,3 +305,65 @@ class TestSurvivorOffset:
         assert jack_jill.caseStatus == "solved"
         assert not jack_jill._ssa_fold_survivor
         assert np.all(jack_jill._ssa_spousal_offset > -1e-6)
+
+
+# ---------------------------------------------------------------------------
+# Taxes on SS follow the claiming age the MILP picks
+# ---------------------------------------------------------------------------
+
+
+def _exact_ss_plan(age):
+    """Single, tax-deferred only, constant rates, an indexed pension from 63.
+
+    With Medicare off and the SS taxable share pinned, the only quantity the loop still feeds
+    back is the benefit stream itself, so each claiming-age MILP is exact once taxable SS
+    follows the ssb variables.
+    """
+    import io
+    from datetime import date
+
+    import owlplanner as owl
+
+    ty = date.today().year
+    p = owl.Plan(["Bo"], [f"{ty - 61}-03-15"], [85], "ss_age_tax", verbose=False, logstreams=[io.StringIO()])
+    p.setSpendingProfile("flat")
+    p.setAccountBalances(taxable=[0], taxDeferred=[300], taxFree=[0], startDate="01-01")
+    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
+    p.setRates("user", values=[6, 4, 3, 2.5])
+    p.setSocialSecurity([3000], [age])
+    p.setPension([8000], [63], indexed=[True])
+    return p
+
+
+_EXACT_OPTS = {"withMedicare": "None", "withSSTaxability": 0.85, "bequest": 0}
+
+
+class TestClaimingAgeTaxes:
+    def test_tax_rows_carry_ssb(self):
+        """The taxable-income row charges Psi_n on the own-benefit variable."""
+        p = _exact_ss_plan(67)
+        p.solve("maxSpending", options={**_EXACT_OPTS, "withSSAges": "optimize"})
+        assert p.caseStatus == "solved"
+        const, idx = p._ss_benefit_terms(0, 10)
+        assert idx == p.vm["ssb"].idx(0, 10)
+        assert const == pytest.approx(p._ssa_spousal_offset[0, 10])
+
+    def test_result_independent_of_starting_age_and_consistent(self):
+        """Same age and spending from any starting age, equal to a fixed-age solve at that age.
+
+        When taxable SS came from the previous iterate's benefits, the plan started at 62 stopped
+        on 64 5/12 reporting $104,526/yr, while a fixed-age solve at 64 5/12 gives $104,518/yr:
+        the accepted plan had not been charged the tax on its own benefits.
+        """
+        results = []
+        for start in (62, 70):
+            p = _exact_ss_plan(start)
+            p.solve("maxSpending", options={**_EXACT_OPTS, "withSSAges": "optimize"})
+            assert p.caseStatus == "solved"
+            results.append((float(p.ssecAges[0]), float(p.g_n[0])))
+        assert results[0][0] == pytest.approx(results[1][0])
+        assert results[0][1] == pytest.approx(results[1][1], abs=1.0)
+
+        fixed = _exact_ss_plan(results[0][0])
+        fixed.solve("maxSpending", options=_EXACT_OPTS)
+        assert results[0][1] == pytest.approx(float(fixed.g_n[0]), abs=1.0)
```

</details>
