# Draft upstream issue (mdlacasse/Owl): self-consistent loop stops on a false cycle, and keeps the wrong member of a real one

**Filed as mdlacasse/Owl#163.**

**Title:** SC loop: a flat objective is taken for a 2-cycle while the loop is still converging; in a real cycle the highest objective is kept rather than the most self-consistent iterate

---

`_check_cycle` decides from the objective history alone (`u.detect_oscillation`). Two things follow.

**1. A flat objective is reported as a cycle.** When the objective stops moving but the lagged parameters are still converging, the history is a run of equal values. A constant sequence matches every cycle length, so the loop reports a 2-cycle and stops. In `Case_cameron` the objective is identical from the third iterate on. The SS fixed-point residual is still falling by the factor the 30% `Psi_n` damping gives (about 0.7 per iteration), and the loop stops at $29,773 over the horizon. Run on, the same case converges in 17 iterations to $1,302 with the same spending.

**2. In a real cycle the highest objective is kept.** `Case_jack+jill` alternates between two iterates. The loop keeps the higher objective, whose own income disagrees more with the model it was solved with: SS residual $4,951 and LTCG residual $2,604, against $4,429 and $65 for the other member. The extra $37/yr of spending in the accepted plan is roughly what it gains by undercharging its own taxes. Choosing by objective systematically favors that kind of iterate, because the higher objective in a 2-cycle is usually the one built with the lower lagged costs.

This doesn't make the loop converge where it can't. It only makes the loop (1) not stop while it is still converging, and (2) return the iterate that is most consistent with its own income. The residual it uses is the one `_scSolve` already computes for the convergence test.

**Repro** (on `dev`, `c1e5619`), from the repository root:

```python
import io, re
import owlplanner as owl

for case in ("Case_cameron", "Case_jack+jill"):
    log = io.StringIO()
    p = owl.readConfig(f"examples/{case}.toml", verbose=True, logstreams=[log])
    p.resolve()
    iters = [ln for ln in log.getvalue().splitlines() if "Iter:" in ln]
    print(case)
    for ln in iters[-4:]:
        print("  " + re.sub(r".*(Iter:.*?); gap.*(residual:.*)", r"\1; \2", ln))
    for ln in log.getvalue().splitlines():
        if "cycle" in ln.lower() or "Converged" in ln:
            print("  " + ln.split("| ")[-1])
    res = {k: round(v["abs_sum"]) for k, v in p.fixedPointResidual.items() if v["abs_sum"] >= 1}
    print(f"  basis {p.basis:,.0f}/yr; fixed-point residual over the horizon: {res}")
```

On `dev`:

```
Case_cameron
  Iter: 04; f: $512,900; residual: $86,605
  Iter: 05; f: $512,900; residual: $60,302
  Iter: 06; f: $512,900; residual: $42,533
  Iter: 07; f: $512,900; residual: $29,773
  Oscillation detected: 2-cycle pattern identified.
  Best objective in cycle: $512,900.47
  Accepting best solution from cycle and terminating.
  basis 18,996/yr; fixed-point residual over the horizon: {'SS': 29773}
Case_jack+jill
  Iter: 21; f: $2,867,978; residual: $4,447
  Iter: 22; f: $2,869,006; residual: $5,449
  Iter: 23; f: $2,867,965; residual: $4,425
  Iter: 24; f: $2,868,995; residual: $4,952
  Oscillation detected: 2-cycle pattern identified.
  Best objective in cycle: $2,868,994.89
  Accepting best solution from cycle and terminating.
  basis 102,577/yr; fixed-point residual over the horizon: {'SS': 4951, 'NIIT': 1, 'LTCG': 2604}
```

With the patch below:

```
Case_cameron
  Iter: 13; f: $512,900; residual: $3,516
  Iter: 14; f: $512,900; residual: $2,461
  Iter: 15; f: $512,900; residual: $1,878
  Iter: 16; f: $512,900; residual: $1,302
  Converged on full solution with oscillatory behavior.
  basis 18,996/yr; fixed-point residual over the horizon: {'SS': 1302}
Case_jack+jill
  Iter: 21; f: $2,867,978; residual: $4,447
  Iter: 22; f: $2,869,006; residual: $5,449
  Iter: 23; f: $2,867,965; residual: $4,425
  Iter: 24; f: $2,868,995; residual: $4,952
  Oscillation detected: 2-cycle pattern identified.
  Keeping the cycle's iterate with the smallest residual: objective $2,867,965.39, residual $4,425.
  Accepting best solution from cycle and terminating.
  basis 102,540/yr; fixed-point residual over the horizon: {'SS': 4429, 'NIIT': 1, 'LTCG': 65}
```

**Effect on the shipped examples.** All 17 cases were run with and without the patch. Only these two change: cameron (same spending, residual $29,773 to $1,302, 17 iterations instead of 8, 0.1 s to 0.2 s) and jack+jill (spending -$37/yr, SS residual $4,951 to $4,429, LTCG residual $2,604 to $65). The other 15 give identical spending, bequest and residuals.

**Suggested fix.** Record each iterate's residual in the loop trace. In `_check_cycle`, don't call a flat objective a cycle while the residual is still falling across the cycle, and within a cycle keep the member with the smallest residual (ties go to the higher objective). The stagnation, max-iteration and unsolvable-iterate exits still choose by objective (`_pick_best_valid_index`). The same reasoning applies to them, but I've left them alone to keep this change small.

Verified against `dev` (`c1e5619`): with the patch the full suite gives 2605 passed, 1 skipped; flake8 is clean. Tests: `test_cycle_and_stagnation_checks` passes a residual history now (equal residuals keep its old expectation). New are `test_cycle_keeps_the_iterate_with_the_smallest_residual`, `test_flat_objective_is_not_a_cycle_while_the_residual_falls` and `test_flat_objective_case_runs_to_convergence` (cameron). All four fail on `dev`.

<details><summary>Patch (source and tests, applies to <code>c1e5619</code>)</summary>

```diff
diff --git a/src/owlplanner/plan.py b/src/owlplanner/plan.py
index 76abd9d..81b1eb0 100644
--- a/src/owlplanner/plan.py
+++ b/src/owlplanner/plan.py
@@ -4532,6 +4532,7 @@ class Plan:
             "solutions": [],
             "objectives": [],
             "gaps": [],
+            "residuals": [],
             "M_n_lp": [],  # M_n parameter used by each iteration's LP
             "ACA_n_lp": [],  # ACA_n parameter used by each iteration's LP
             "J_n_lp": [],  # J_n parameter used by each iteration's LP
@@ -4573,7 +4574,16 @@ class Plan:
             "message": f"Converged on full solution with {convergence_type} behavior.",
         }
 
-    def _check_cycle(self, it, scaled_obj_history, tol):
+    def _check_cycle(self, it, scaled_obj_history, tol, residual_history):
+        """A repeating pattern in the objective, and which of its iterates to keep.
+
+        A flat objective matches every cycle length, but it is not a cycle while the residual is
+        still falling: the loop is converging in quantities the objective does not price (e.g. a
+        damped Psi_n in a year whose SS tax costs nothing), and stopping there returns a plan
+        whose own income implies a different model. Within a real cycle, keep the iterate that
+        agrees best with the model its own income implies (smallest residual), not the one with
+        the highest objective, which tends to be the iterate built with the lowest lagged costs.
+        """
         # Need at least 4 iterations to detect a 2-cycle.
         if it < 3:
             return None
@@ -4581,7 +4591,11 @@ class Plan:
         if cycle_len is None:
             return None
         cycle_values = scaled_obj_history[-cycle_len:]
-        best_idx = int(np.argmax(cycle_values))
+        flat = max(cycle_values) - min(cycle_values) <= tol
+        if flat and residual_history[-1] < residual_history[-1 - cycle_len]:
+            return None
+        cycle_residuals = residual_history[-cycle_len:]
+        best_idx = min(range(cycle_len), key=lambda k: (cycle_residuals[k], -cycle_values[k]))
         return {
             "reason": "cycle",
             "cycleLength": cycle_len,
@@ -4900,6 +4914,7 @@ class Plan:
             # gains tax can disagree with the tax this iterate's own income implies.
             moves.append(np.sum(np.abs(self.U_n - self._ltcg_tax_implied()) / g_today))
             scResidual = float(max(moves))
+            trace["residuals"].append(scResidual)
 
             has_prev_obj = len(trace["scaledObjectives"]) > 1
             prev_scaled_obj = trace["scaledObjectives"][-2] if has_prev_obj else scaled_obj
@@ -4917,7 +4932,7 @@ class Plan:
                 it, absObjDiff, tol, includeMedicare, trace["scaledObjectives"], scResidual
             )
             if decision is None:
-                decision = self._check_cycle(it, trace["scaledObjectives"], tol)
+                decision = self._check_cycle(it, trace["scaledObjectives"], tol, trace["residuals"])
             if decision is None:
                 decision = self._check_stagnation(it, trace["scaledObjectives"], trace["gaps"], includeMedicare)
             if decision is None:
@@ -4946,8 +4961,11 @@ class Plan:
                     best_obj = decision["bestScaledObjective"]
                     cycle_offset = decision["cycleOffset"]
                     self.mylog.print(f"Oscillation detected: {cycle_len}-cycle pattern identified.")
-                    self.mylog.print(f"Best objective in cycle: {u.d(best_obj, f=2)}")
                     best_idx = len(trace["scaledObjectives"]) - cycle_len + cycle_offset
+                    self.mylog.print(
+                        f"Keeping the cycle's iterate with the smallest residual: objective {u.d(best_obj, f=2)}, "
+                        f"residual {u.d(trace['residuals'][best_idx])}."
+                    )
                     xx = trace["solutions"][best_idx]
                     objfn = trace["objectives"][best_idx]
                     M_n_lp = trace["M_n_lp"][best_idx]
diff --git a/tests/solver/test_sc_convergence_helpers.py b/tests/solver/test_sc_convergence_helpers.py
index f01e0c8..879ee08 100644
--- a/tests/solver/test_sc_convergence_helpers.py
+++ b/tests/solver/test_sc_convergence_helpers.py
@@ -88,7 +88,10 @@ def test_cycle_and_stagnation_checks(monkeypatch):
     p = _make_plan()
     monkeypatch.setattr(planmod.u, "detect_oscillation", lambda history, tol: 3)
 
-    cycle = p._check_cycle(it=4, scaled_obj_history=[100.0, 95.0, 96.0, 95.0], tol=1.0)
+    # Equal residuals: the highest objective in the cycle is kept, as before.
+    cycle = p._check_cycle(
+        it=4, scaled_obj_history=[100.0, 95.0, 96.0, 95.0], tol=1.0, residual_history=[5.0, 5.0, 5.0, 5.0]
+    )
     assert cycle["reason"] == "cycle"
     assert cycle["cycleLength"] == 3
     assert cycle["cycleOffset"] == 1
@@ -99,8 +102,44 @@ def test_cycle_and_stagnation_checks(monkeypatch):
     assert stagnation["reason"] == "stagnation"
 
 
+def test_cycle_keeps_the_iterate_with_the_smallest_residual():
+    """In a real cycle the iterate whose own income agrees best with its model is kept, not the highest objective."""
+    p = _make_plan()
+    history = [100.0, 90.0, 100.0, 90.0, 100.0, 90.0]
+    residuals = [50.0, 40.0, 30.0, 20.0, 30.0, 20.0]  # the lower objective has the smaller residual
+    cycle = p._check_cycle(it=5, scaled_obj_history=history, tol=1.0, residual_history=residuals)
+    assert cycle["cycleLength"] == 2
+    assert cycle["cycleOffset"] == 1
+    assert cycle["bestScaledObjective"] == 90.0
+
+
+def test_flat_objective_is_not_a_cycle_while_the_residual_falls():
+    """A constant objective matches every cycle length; the loop is still converging if the residual falls."""
+    p = _make_plan()
+    history = [512.0] * 6
+    falling = [600.0, 400.0, 280.0, 200.0, 140.0, 100.0]
+    assert p._check_cycle(it=5, scaled_obj_history=history, tol=1.0, residual_history=falling) is None
+    stuck = [600.0, 400.0, 280.0, 200.0, 200.0, 200.0]
+    assert p._check_cycle(it=5, scaled_obj_history=history, tol=1.0, residual_history=stuck)["reason"] == "cycle"
+
+
 def test_max_iteration_check():
     p = _make_plan()
     assert p._check_max_iterations(5, 6) is None
     decision = p._check_max_iterations(6, 6)
     assert decision["reason"] == "max_iter"
+
+
+def test_flat_objective_case_runs_to_convergence():
+    """Case_cameron's objective is flat from the third iterate while the damped SS share keeps converging.
+
+    It used to stop there on a "2-cycle" of equal objectives, leaving $29,773 of SS tax
+    inconsistent over the horizon; it now converges, with the same spending.
+    """
+    import os
+
+    p = owl.readConfig(os.path.join("examples", "Case_cameron.toml"), verbose=False)
+    p.resolve()
+    assert p.caseStatus == "solved"
+    assert "cycle" not in p.convergenceType
+    assert p.fixedPointResidual["SS"]["abs_sum"] / p.N_n <= p._residual_tol
```

</details>
