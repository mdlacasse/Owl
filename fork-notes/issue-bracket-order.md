# Draft upstream issue (mdlacasse/Owl): tax brackets filled top-down where late cash has no value

**Filed as mdlacasse/Owl#162.** Fixed upstream in `3fca646` (2026.10.4) with this patch verbatim; merged into the fork 2026-10-04.

**Title:** Reported taxes and bequest wrong when a year's cash has no value: brackets filled out of order

---

The bracket variables `f_tn` (and `q_pn`, `st_f`) are a relaxation of the progressive schedule. The LP fills the low brackets first only because tax costs the objective something. The paper says as much where it explains why `fixedSpending` was withdrawn. The same thing happens without `fixedSpending`, in any year where cash has no marginal value.

A common way to get such years under `maxSpending` is a liquidity-limited plan. The first years cap spending. Later income (a pension, SS, RMDs) exceeds the profile, becomes surplus, and ends in a bequest above its floor. A dollar of tax in those years costs the objective nothing, so any split of income across brackets is optimal, and HiGHS returns one with the top bracket filled while the lower ones are empty. Spending (the objective) is right. The reported taxes, the bequest and the Taxes sheet are not. No warning is printed: the only consistency check, the LTCG "may be degenerate" warning, doesn't look at `f_tn`.

The degenerate fill also leaves the plan's LTCG tax disagreeing with what its income implies. The loop then never meets its residual test and stops on a "2-cycle" of identical objectives, accepting an earlier iterate.

**Repro** (on `dev`, `a85ff76`). A single filer with $150k saved, an indexed $12,000/month pension and SS from 70. Medicare is off and SS taxability pinned, so the LP is exact. From 2032 the default `yOBBBA = 2032` switches to the pre-TCJA schedule, which explains the different bracket widths below.

```python
import io
import numpy as np
import owlplanner as owl

p = owl.Plan(["Ann"], ["1961-03-15"], [90], "degen", verbose=False, logstreams=[io.StringIO()])
p.setSpendingProfile("flat")
p.setAccountBalances(taxable=[50], taxDeferred=[100], taxFree=[0], startDate="01-01")
p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
p.setRates("user", values=[6, 4, 3, 2.5])
p.setPension([12000], [70], indexed=[True])
p.setSocialSecurity([2500], [70])
p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
print("status", p.caseStatus, "basis", round(p.basis))
bad = []
for n in range(p.N_n):
    for t in range(1, p.N_t):
        if p.f_tn[t, n] > 1 and p.f_tn[t - 1, n] < p.DeltaBar_tn[t - 1, n] - 1:
            bad.append((int(p.year_n[n]), t, round(p.f_tn[t - 1, n]), round(p.DeltaBar_tn[t - 1, n]), round(p.f_tn[t, n])))
            break
print("years with out-of-order bracket fill:", len(bad))
for b in bad[:3]:
    print("  year %d: bracket %d has %s while bracket %d holds %s of %s" % (b[0], b[1], b[4], b[1] - 1, b[2], b[3]))
print("surplus years:", int(np.sum(p.s_n > 1)), " final bequest (today $):", round(p.bequest))
ordered = reported = 0.0
for n in range(p.N_n):
    rem, tax = p.f_tn[:, n].sum(), 0.0
    for t in range(p.N_t):
        x = min(rem, p.DeltaBar_tn[t, n])
        tax += x * p.theta_tn[t, n]
        rem -= x
    ordered += tax / p.gamma_n[n]
    reported += p.T_n[n] / p.gamma_n[n]
print("lifetime federal ordinary tax, today $: reported %.0f, same income filled in order %.0f" % (reported, ordered))
```

On `dev`:

```
status solved basis 31580
years with out-of-order bracket fill: 21
  year 2031: bracket 6 has 163734 while bracket 5 holds 0 of 434885
  year 2032: bracket 6 has 206319 while bracket 5 holds 0 of 2667
  year 2033: bracket 6 has 213032 while bracket 5 holds 0 of 2734
surplus years: 21  final bequest (today $): 2020040
lifetime federal ordinary tax, today $: reported 1558338, same income filled in order 911265
```

`fixedPointResidual` for that plan: `LTCG` $10,413; `convergenceType` is "oscillatory (cycle length 2)".

With the patch below:

```
status solved basis 31580
years with out-of-order bracket fill: 0
surplus years: 21  final bequest (today $): 2912759
lifetime federal ordinary tax, today $: reported 887113, same income filled in order 887113
```

Spending is unchanged, $647k of tax that wasn't owed is gone, and the bequest is $892k higher. The loop converges monotonically with LTCG residual 0.

**Suggested fix.** Price tax slightly in the objective, 1e-4 per today's dollar of bracket tax, which makes the bottom-up fill the unique optimum. Three points about it:

- **Only when needed.** Always on, the term changes no example's objective directly, but it moves the fixed point the loop settles on in two cases that were never out of order: morgan +1.5% spending, john+sally -4% bequest (`test_objective_matches_reference` fails on both). So the patch switches the term on from the first iterate that fills a year out of order. A final iterate that first does so is re-solved once with spending (and any binaries) pinned. A post-solve check warns and records `bracketOrderExcess`.
- **Size.** `EPSILON` (5e-7) is too small: the reduced-cost differences it creates (about 1e-7) sit at HiGHS's dual feasibility tolerance, and the fill stays top-down. 1e-4 (`MIP_TIEBREAK`) works.
- **Surplus polish.** `_polishSurplus` minimizes the surplus with spending and terminal balances pinned. With those pins, a dollar of extra tax lowers the surplus by a dollar, so the polish could shed surplus by filling the top brackets. The patch charges tax at twice a surplus dollar there.

Re-checked on `dev` `3c88ce1` (after the #157 fix): the patch applies cleanly, the repro output is identical before and after, and the full suite gives 2605 passed, 1 skipped. First verified against `dev` (`a85ff76`): the 17 example cases give the same spending and bequest; with this patch alone the full suite gives 2597 passed, 1 skipped; flake8 is clean. Tests added: `tests/plan/test_bracket_order.py`. Two of its three tests fail on `dev`. The third checks that spending is unchanged, so it passes on both.

<details><summary>Patch (source and tests, applies to <code>a85ff76</code>)</summary>

```diff
diff --git a/src/owlplanner/plan.py b/src/owlplanner/plan.py
index 3de39bb..5e90236 100644
--- a/src/owlplanner/plan.py
+++ b/src/owlplanner/plan.py
@@ -146,6 +146,17 @@ EPSILON = 5e-7
 # tolerance, so a MIP tie-break has to be visible above it while staying far below any real
 # cost in the objective. See the t^sigma_n preference in _buildObjective.
 MIP_TIEBREAK = 1e-4
+# Tie-break on the tax a year's brackets charge, per today's dollar of tax. The bracket variables are
+# a relaxation, tight only while the year's cash has a price: where it has none (late surplus that
+# can only swell a bequest above its floor), any split of income across brackets is optimal and the
+# solver can fill the top one first, reporting tax the plan does not owe. The self-consistent
+# loop switches tax pricing this size on from the first iterate that fills a year out of order (the
+# degenerate fill also stalls convergence, through the LTCG residual), and _repairBracketOrder
+# re-solves an accepted LP that first goes out of order in the final iterate. It stays off otherwise:
+# always on, it moved the fixed point the loop settles on in cases that were never out of order
+# (morgan +1.5% spending, john+sally -4% bequest). EPSILON (5e-7) is too small: the reduced costs it
+# makes sit at HiGHS's dual feasibility tolerance and the fill stays.
+TAX_TIEBREAK = MIP_TIEBREAK
 LTCG_CONSISTENCY_MAX_PASSES = 5  # max monolithic re-solves to clear stale LTCG bracket room
 LTCG_CONSISTENCY_TOL = 1.0  # allowed U_n - 0.20*Q_n slack ($) before a re-solve is needed
 
@@ -530,6 +541,9 @@ class Plan:
         # Per-family distance between the model solved and the model this plan's own income
         # implies, today's dollars; set by _computeFixedPointResidual after a successful solve.
         self.fixedPointResidual = {}
+        self.bracketOrderExcess = 0.0
+        # Whether the objective prices tax (TAX_TIEBREAK); switched on by _scSolve when needed.
+        self._tax_tiebreak_on = False
         # Achieved MIP gap of the accepted solution (0 when solved to optimality,
         # larger when a time limit truncated the search; -1 before any solve)
         self.solverGap = -1.0
@@ -3971,6 +3985,9 @@ class Plan:
         else:
             raise RuntimeError("Internal error in objective function.")
 
+        if self._tax_tiebreak_on:
+            c_arr += TAX_TIEBREAK * self._tax_cost_vector()
+
         # Turn on epsilon by default to reduce churn and frontload Roth conversions.
         default_epsilon = EPSILON
         epsilon = u.get_numeric_option(options, "epsilon", default_epsilon, min_value=0)
@@ -4033,6 +4050,134 @@ class Plan:
             c.setElem(idx, c_arr[idx])
         self.c = c
 
+    def _tax_cost_vector(self):
+        """Tax each bracket variable charges per dollar, in today's dollars, as a dense vector.
+
+        Federal ordinary and capital-gains brackets and state brackets: the terms the cash-flow row
+        charges on these columns.
+        """
+        cost = np.zeros(self.nvars)
+        vm = self.vm
+        for n in range(self.N_n):
+            deflate = 1.0 / self.gamma_n[n]
+            for t in range(self.N_t):
+                cost[vm["f"].idx(t, n)] = self.theta_tn[t, n] * deflate
+            cost[vm["q"].idx(1, n)] = 0.15 * deflate
+            cost[vm["q"].idx(2, n)] = 0.20 * deflate
+            if "st_f" in vm:
+                for t in range(self.N_st):
+                    cost[vm["st_f"].idx(t, n)] = self.st_theta_tn[t, n] * deflate
+        return cost
+
+    def _bracket_order_excess(self, x=None):
+        """Tax the solution charges beyond what its own income owes with brackets filled bottom-up.
+
+        Returns (years, excess): the plan years whose federal or state brackets are filled
+        out of order, and the overcharge summed over the horizon in today's dollars. Zero when the
+        relaxation is tight, which it is wherever the year's cash has a price. Reads the solution
+        vector x when given, the aggregated results otherwise.
+        """
+        vm = self.vm
+        if x is None:
+            f_tn = self.f_tn
+            st_f_tn = self.st_f_tn if "st_f" in vm else np.zeros((self.N_st, self.N_n))
+        else:
+            f_tn = vm["f"].extract(x)
+            st_f_tn = vm["st_f"].extract(x) if "st_f" in vm else np.zeros((self.N_st, self.N_n))
+
+        def ordered_tax(total, width, rate):
+            tax = 0.0
+            for t in range(len(width)):
+                part = min(max(total, 0.0), width[t])
+                tax += part * rate[t]
+                total -= part
+            return tax
+
+        years = []
+        excess = 0.0
+        schedules = [(f_tn, self.DeltaBar_tn, self.theta_tn)]
+        if self.N_st > 0 and np.any(st_f_tn):
+            schedules.append((st_f_tn, self.st_DeltaBar_tn, self.st_theta_tn))
+        for n in range(self.N_n):
+            over = 0.0
+            for f, width, rate in schedules:
+                charged = float(np.dot(f[:, n], rate[:, n]))
+                over += charged - ordered_tax(float(np.sum(f[:, n])), width[:, n], rate[:, n])
+            if over > 1.0:
+                years.append(int(self.year_n[n]))
+                excess += over / self.gamma_n[n]
+        return years, excess
+
+    def _repairBracketOrder(self, xx, objfn, objective, options, matricesMatch):
+        """Re-fill out-of-order tax brackets by re-solving the accepted LP with tax priced (TAX_TIEBREAK).
+
+        Spending is pinned (it is the objective, or fixed by netSpending), and so are the binaries;
+        everything else is free, so the tax no longer charged lands where the plan's cash goes,
+        usually a larger bequest. The incumbent stays feasible, so the re-solve cannot fail for want
+        of a solution. Returns the (possibly repaired) vector and its objective value; any failure
+        keeps the solver's own answer, which _check_bracket_order then reports.
+        """
+        years, excess = self._bracket_order_excess(xx)
+        if not years:
+            return xx, objfn
+        if not matricesMatch:
+            self.mylog.vprint(
+                "Leaving the tax brackets as solved: an earlier iterate was accepted, so the "
+                "constraint matrices no longer describe this solution."
+            )
+            return xx, objfn
+
+        c_orig = self.c.arrays()
+        col_lb, col_ub = self.B.arrays()
+        res0 = amorepair.max_row_violation(xx, self.A, col_lb, col_ub)
+        overrides = {}
+        for n in range(self.N_n):
+            j = self.vm["g"].idx(n)
+            overrides[j] = (xx[j], xx[j])
+        for j in range(self.vm.nconts, self.nvars):
+            v = float(np.round(xx[j]))
+            overrides[j] = (v, v)
+        c_tie = np.asarray(c_orig) + TAX_TIEBREAK * self._tax_cost_vector()
+        obj = abc.Objective(self.nvars)
+        for j in np.flatnonzero(c_tie):
+            obj.setElem(int(j), float(c_tie[j]))
+        repair_options = dict(options)
+        repair_options["maxTime"] = min(u.get_numeric_option(options, "maxTime", TIME_LIMIT, min_value=0), 60)
+
+        _, yy, ok, msg, _ = self._run_mip(
+            self.A, self.B, obj, repair_options, col_overrides=overrides, lp_relax=True, update_warm=False
+        )
+        if not ok or yy is None:
+            self.mylog.vprint(f"Bracket-order repair did not solve ({msg}); keeping the original solution.")
+            return xx, objfn
+        yy = np.array(yy)
+        res = amorepair.max_row_violation(yy, self.A, col_lb, col_ub)
+        if res > max(res0, 1.0):
+            self.mylog.print(
+                f"Bracket-order repair rejected: residual {res:.2e} exceeds {max(res0, 1.0):.2e}.", tag="WARNING"
+            )
+            return xx, objfn
+        new_years, new_excess = self._bracket_order_excess(yy)
+        if new_excess >= excess:
+            return xx, objfn
+        self.mylog.vprint(
+            f"Tax brackets re-filled bottom-up in {len(years) - len(new_years)} of {len(years)} year(s); "
+            f"{u.d(excess - new_excess)} of tax the income did not owe removed (today's $)."
+        )
+        return yy, float(np.dot(c_orig, yy))
+
+    def _check_bracket_order(self):
+        """Warn when the solved brackets are filled out of order (see TAX_TIEBREAK)."""
+        years, excess = self._bracket_order_excess()
+        self.bracketOrderExcess = excess
+        if years:
+            self.mylog.print(
+                f"Tax brackets filled out of order in {len(years)} year(s) ({years[0]}-{years[-1]}): "
+                f"reported taxes exceed what this income owes by {u.d(excess)} over the horizon "
+                "(today's $). The objective is unaffected; taxes and bequest are not.",
+                tag="WARNING",
+            )
+
     @_checkConfiguration(requireRates=False)
     @_timer
     def runHistoricalRange(
@@ -4752,6 +4897,7 @@ class Plan:
 
         self._computeNLstuff(None, includeMedicare, fixedPsi=fixed_psi)
         self._init_gain_fraction()
+        self._tax_tiebreak_on = False
         M_n_lp = self.M_n.copy()
         ACA_n_lp = self.ACA_n.copy()
         Psi_n_lp = self.Psi_n.copy()
@@ -4836,6 +4982,13 @@ class Plan:
                 self._infeasible = False
                 break
 
+            if self._tax_tiebreak_on:
+                # Report the objective without the tie-break, so iterates compare on the same terms.
+                objfn -= TAX_TIEBREAK * float(np.dot(self._tax_cost_vector(), xx))
+            elif self._bracket_order_excess(xx)[0]:
+                self._tax_tiebreak_on = True
+                self.mylog.vprint(f"Iteration {it} filled tax brackets out of order; pricing tax from now on.")
+
             self._computeNLstuff(xx, includeMedicare, fixedPsi=fixed_psi)
             self._update_gain_fraction()
 
@@ -4977,6 +5130,7 @@ class Plan:
             self.mylog.print(f"Self-consistent loop returned after {it + 1} iterations.")
             if solverMsg:
                 self.mylog.print(solverMsg)
+            xx, objfn = self._repairBracketOrder(xx, objfn, objective, options, matricesMatchSolution)
             xx, objfn = self._restoreExclusions(xx, objfn, objective, options, matricesMatchSolution)
             self.mylog.print(f"Objective: {u.d(objfn * objFac)}")
             # Psi_n is restored BEFORE aggregation, unlike the three below: MAGI_aca_n is
@@ -5005,6 +5159,7 @@ class Plan:
             if self.slcsp_annual > 0 and not self._aca_lp:
                 self.ACA_n = ACA_n_lp
             self._check_cashflow_balance()
+            self._check_bracket_order()
             self._computeFixedPointResidual(includeMedicare)
             if options.get("withDuals", False):
                 self._computeDuals(xx, options)
@@ -5173,6 +5328,10 @@ class Plan:
         """
         overrides = amorepair.build_polish_overrides(xx, ctx, self.vm.nconts, self.nvars)
         c_polish = amorepair.build_polish_objective(ctx, c_orig, self.gamma_n, self.nvars)
+        # With spending and the terminal balances pinned, a dollar of tax lowers the surplus by a
+        # dollar, so minimizing the surplus alone would pay tax to shed it -- by filling the top
+        # brackets first. Charging tax at twice a surplus dollar rules that trade out.
+        c_polish = c_polish + 2.0 * self._tax_cost_vector()
         polish_options = dict(options)
         polish_options["maxTime"] = min(u.get_numeric_option(options, "maxTime", TIME_LIMIT, min_value=0), 60)
 
diff --git a/tests/plan/test_bracket_order.py b/tests/plan/test_bracket_order.py
new file mode 100644
index 0000000..fdfa598
--- /dev/null
+++ b/tests/plan/test_bracket_order.py
@@ -0,0 +1,96 @@
+"""
+Tests for the bottom-up fill of the tax brackets.
+
+The bracket variables are a relaxation: the LP fills the cheap brackets first only because tax
+costs it something. In a year whose cash has no value -- late surplus that can only swell a
+bequest above its floor -- any split is optimal, and the solver used to fill the top bracket
+first, reporting tax the plan did not owe. The loop now prices tax from the first iterate that
+does this, and the solved plan is checked.
+
+Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
+
+This program is free software: you can redistribute it and/or modify
+it under the terms of the GNU General Public License as published by
+the Free Software Foundation, either version 3 of the License, or
+(at your option) any later version.
+
+This program is distributed in the hope that it will be useful,
+but WITHOUT ANY WARRANTY; without even the implied warranty of
+MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
+GNU General Public License for more details.
+
+You should have received a copy of the GNU General Public License
+along with this program.  If not, see <https://www.gnu.org/licenses/>.
+"""
+
+import numpy as np
+
+from owlplanner import Plan
+
+
+def _cash_rich_late_plan():
+    """Spending is capped by the first years; a large pension from 70 then piles up as surplus."""
+    p = Plan(["Ann"], ["1961-03-15"], [90], "brackets", verbose=False)
+    p.setSpendingProfile("flat")
+    p.setAccountBalances(taxable=[50], taxDeferred=[100], taxFree=[0], startDate="01-01")
+    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
+    p.setRates("user", values=[6, 4, 3, 2.5])
+    p.setPension([12000], [70], indexed=[True])
+    p.setSocialSecurity([2500], [70])
+    return p
+
+
+def _out_of_order_years(p):
+    years = []
+    for n in range(p.N_n):
+        for t in range(1, p.N_t):
+            if p.f_tn[t, n] > 1 and p.f_tn[t - 1, n] < p.DeltaBar_tn[t - 1, n] - 1:
+                years.append(int(p.year_n[n]))
+                break
+    return years
+
+
+def _ordered_tax(p, n):
+    total, tax = float(np.sum(p.f_tn[:, n])), 0.0
+    for t in range(p.N_t):
+        part = min(total, p.DeltaBar_tn[t, n])
+        tax += part * p.theta_tn[t, n]
+        total -= part
+    return tax
+
+
+def test_brackets_fill_bottom_up_when_late_cash_is_worthless():
+    p = _cash_rich_late_plan()
+    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
+    assert p.caseStatus == "solved"
+    # The case does exercise the degenerate face: surplus in the late years, bequest far above 0.
+    assert np.sum(p.s_n > 1) > 10
+    assert p.bequest > 1e6
+
+    assert _out_of_order_years(p) == []
+    assert p.bracketOrderExcess == 0.0
+    for n in range(p.N_n):
+        assert abs(p.T_n[n] - _ordered_tax(p, n)) < 1.0
+
+
+def test_pricing_tax_leaves_spending_unchanged():
+    """Spending is set by the early years, where cash is valuable; the tie-break must not move it."""
+    p = _cash_rich_late_plan()
+    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
+    # Recorded before the fix, when the late years were filled top-down: basis 31,580.
+    assert abs(p.basis - 31580) < 5
+
+
+def test_excess_measures_an_out_of_order_fill():
+    """_bracket_order_excess charges the gap between the fill given and the bottom-up one."""
+    p = _cash_rich_late_plan()
+    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
+    n = int(np.flatnonzero(np.sum(p.f_tn, axis=0) > 1e5)[0])
+    total = float(np.sum(p.f_tn[:, n]))
+    p.f_tn = p.f_tn.copy()
+    p.f_tn[:, n] = 0.0
+    p.f_tn[-1, n] = total  # all of it in the top bracket
+    years, excess = p._bracket_order_excess()
+    assert years == [int(p.year_n[n])]
+    expected = (total * p.theta_tn[-1, n] - _ordered_tax(p, n)) / p.gamma_n[n]
+    assert abs(excess - expected) < 1.0
```

</details>
