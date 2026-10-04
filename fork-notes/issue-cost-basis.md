# Draft upstream issue (mdlacasse/Owl): tracked cost basis leaves out reinvested dividends, and applies the account's gain fraction to the equity share only

**Filed upstream by the user on 2026-10-04** (issue number not recorded yet).

**Title:** Cost basis: taxed, reinvested dividends and interest are not added to basis, and the whole-account gain fraction multiplies only the equity share of a withdrawal

---

Two problems in the basis tracking behind `setCostBasis()`. They push in opposite directions.

**1. Reinvested income is taxed twice.** `_update_gain_fraction` (paper Eq. BasisUpdate) adds only contributions and surplus deposits to basis:

```
K_{n+1} = K_n (1 - w_n/b_n) + kappa_n + d_n
```

The model taxes dividends every year (`mu * alpha_0 * (b - w + d + kappa/2)` in `Q_n`), and it taxes the positive returns on bonds and cash as ordinary income (`max(0, tau_k) * alpha_k * (...)` in `_add_taxable_income`). Balances grow at total return, so that income stays in the account. It is a purchase at full cost and belongs in basis. Left out, it is taxed again when the shares are sold. For $1M taxable on a $500k basis, all equity, drawn down over 11 years, the gain fraction reaches 0.762 where it should be 0.633 (repro below).

**2. The gain fraction is applied to the equity share only.** The realized gain on a withdrawal is `alpha_0 * psi * w` (Eq. Qx3), with `psi = 1 - K/b` taken over the **whole** account. That product is right only if the bond share carries none of the account's gain **and** the equities carry only their own share of it. The model taxes bond and cash returns yearly, so those holdings sit at their basis. The account's whole unrealized gain `b - K` is then in the equities, whose gain fraction is `(1 - K/b) / alpha_0`. The realized gain is `(1 - K/b) * w`. With a 60/40 account, `dev` realizes 60% of that.

**Repro for 1** (on `dev`, `c1e5619`), from the repository root. 100% equity, so problem 2 doesn't interfere. `psi_with_divs` replays Owl's own flows with the taxed dividends added to basis.

```python
import io
import numpy as np
import owlplanner as owl

p = owl.Plan(["Bo"], ["1966-06-15"], [90], "basis", verbose=False, logstreams=[io.StringIO()])
p.setSpendingProfile("flat")
p.setAccountBalances(taxable=[1000], taxDeferred=[1000], taxFree=[0], startDate="01-01")
p.setCostBasis([500])
p.setAllocationRatios("individual", generic=[[[100, 0, 0, 0], [100, 0, 0, 0]]])
p.setRates("user", values=[7, 4, 3, 2.5])
p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
mu = p.mu
b = p.b_ijn[0, 0, :]; w = p.w_ijn[0, 0, :]; d = p.d_in[0, :]; k = p.kappa_ijn[0, 0, :]
K_owl = 500e3; K_true = 500e3
print(" year  balance  w_taxable  psi_owl  psi_with_divs  divs_taxed")
for n in range(12):
    psi_o = max(0, 1 - K_owl / b[n]) if b[n] > 0 else 0
    psi_t = max(0, 1 - K_true / b[n]) if b[n] > 0 else 0
    div = mu * (b[n] - w[n] + d[n] + 0.5 * k[n])
    print(f" {int(p.year_n[n])} {b[n]:9.0f} {w[n]:9.0f}   {psi_o:6.3f}   {psi_t:6.3f}   {div:8.0f}")
    frac = (1 - w[n] / b[n]) if b[n] > 0 else 0
    K_owl = K_owl * frac + k[n] + d[n]
    K_true = K_true * frac + k[n] + d[n] + div
print("Owl's own gain_fraction_in[0,:12]:", np.round(p.gain_fraction_in[0, :12], 3))
```

On `dev`:

```
 year  balance  w_taxable  psi_owl  psi_with_divs  divs_taxed
 2026   1000000    120642    0.500    0.500      15125
 2027    940913    124081    0.533    0.517      14050
 2028    874010    127564    0.563    0.532      12839
 2029    798697    131092    0.592    0.547      11483
 2030    714338    134665    0.619    0.560       9970
 2031    620250    138283    0.644    0.573       8290
 2032    515704    143566    0.667    0.585       6401
 2033    398188    147316    0.689    0.596       4315
 2034    268433     94109    0.709    0.606       2998
 2035    186526     60228    0.728    0.616       2172
 2036    135139     61550    0.746    0.625       1266
 2037     78740     63060    0.762    0.633        270
Owl's own gain_fraction_in[0,:12]: [0.5   0.533 0.563 0.592 0.619 0.644 0.667 0.689 0.709 0.728 0.746 0.762]
```

With the patch below, Owl's own `gain_fraction_in` follows `psi_with_divs`: `[0.5 0.517 0.532 0.547 0.56 0.573 0.585 0.596 0.606 0.616 0.625 0.633]`.

**Suggested fix.**

- In `_update_gain_fraction`, add the year's taxed income to basis: `(mu * alpha_0 + sum_k alpha_k * max(0, tau_k)) * (b - w + d + kappa/2)`. These are the same coefficients `_add_taxable_income` and the `Q_n` rows use.
- Store the equity gain fraction in `gain_fraction_in`: `min(1, (1 - K/b) / alpha_0)`, or 0 when `alpha_0 = 0`. This also applies at initialization. Every consumer already multiplies it by `alpha_0` (the `Q_n` rows, provisional income, the IRMAA and ACA MAGI rows, `_aggregateResults`), so nothing else changes.
- The paper's Eqs. GainFrac and BasisUpdate and `info/modeling-capabilities.md` are updated to match.

The no-basis fallback (`tau_0 - mu`) is untouched.

**Effect on the shipped examples** (HiGHS, `absTol=50`, `relTol=2e-5` as in `test_reproducibility`). Only the four cases with a cost basis change. Columns: spending basis on `dev`, with the patch, and with only part 1 of the patch.

| Case | `dev` | Patch | Part 1 only |
|---|---:|---:|---:|
| helen+ruth | 195,105 | 194,069 | 195,185 |
| jack+jill | 102,577 | 102,535 | 102,713 |
| joe | 93,044 | 92,575 | 93,363 |
| robin | 44,070 | 44,013 | 44,070 |

The other 13 examples give identical spending and bequest.

Part 1 alone raises spending, and part 2 lowers it by more. The net effect is about -0.5% for joe and helen+ruth. The references that moved are re-recorded in the patch: `test_repro` `SPENDING1`/`BEQUEST1`, `test_toml_cases` jack+jill/joe/robin, and the HiGHS entry for helen+ruth in `amo_mip_reference.json`. I could not re-record its MOSEK entry, because I don't have MOSEK.

Verified against `dev` (`c1e5619`): with the patch alone the full suite gives 2606 passed, 1 skipped; flake8 is clean. New tests are in `TestCostBasisReinvestedIncome`. `test_basis_includes_taxed_income` recomputes the basis by hand from the plan's own flows, for 100/0 and 60/40. There are also `test_gain_fraction_grows_slower_than_without_dividends` and `test_equity_gain_fraction`. All fail on `dev`.

<details><summary>Patch (source, docs and tests, applies to <code>c1e5619</code>)</summary>

```diff
diff --git a/info/modeling-capabilities.md b/info/modeling-capabilities.md
index c848930..658b038 100644
--- a/info/modeling-capabilities.md
+++ b/info/modeling-capabilities.md
@@ -13,7 +13,7 @@ This document summarizes all modeling components in Owl (Optimal wealth lab), ho
 | **Objectives** | maxSpending: maximize net spending subject to bequest floor. maxBequest: maximize after-tax bequest subject to spending floor; requires `netSpending` option to set the spending floor. Roth conversion amounts optimized in both (subject to caps and per-person controls). Optional `timePreference` (%/year) discounts future spending to reduce end-of-life back-loading. To see the trade-off between the two objectives rather than one point on it, sweep the `bequest` floor under maxSpending to trace the spending-vs-bequest trade-off curve. | LP objective is linear, so it always drives spending to an extreme of the feasible range; use profile slack and bequest/spending constraints to shape the solution. |
 | **Spending profile** | User-specified shape (flat or smile) scaling a first-year basis. Survivorship factor at first death. Optimizer determines achievable basis. The profile is a bilateral constraint for both objectives: spending stays within ±slack% of the profile shape (`spendingSlack` sets the tolerance). | Profile shape fixed; only scale is optimized. |
 | **Bequest objective** | After-tax estate value. Tax-deferred and HSA balances discounted by heirs' marginal rate. Surviving spouse inherits per beneficiary fractions; non-spouse portion taxed. | Single heirs' marginal tax rate applied to all inherited tax-deferred and HSA balances. |
-| **Taxable accounts** | Dividend and interest yield proportional to balance each year; capital gains when optimizer elects to sell. All realized gains treated as long-term. Capital gains on withdrawals use the **average-cost** method: when a fraction of the account is sold, the same fraction of the total cost basis is recovered, so the realized gain equals `gain_fraction × withdrawal` where `gain_fraction = (balance − basis) / balance`. Optional: `setCostBasis([b1, b2])` (or TOML field `taxable_cost_basis`) supplies the current cost basis per person; the SC loop then tracks how basis evolves each year as shares are sold and new contributions (HFP contributions plus LP surplus deposits) add fresh basis. Without a supplied basis, realized gains fall back to current-year price appreciation only (`(τ₀ − μ) × withdrawal`), which underestimates gains for accounts with substantial embedded appreciation. | All gains treated as long-term; short-term gains (holding period &lt; 1 year) not distinguished. Average-cost method only; FIFO and LIFO lot accounting not supported. Tax-loss harvesting not modeled. |
+| **Taxable accounts** | Dividend and interest yield proportional to balance each year; capital gains when optimizer elects to sell. All realized gains treated as long-term. Capital gains on withdrawals use the **average-cost** method: when a fraction of the account is sold, the same fraction of the total cost basis is recovered, so the realized gain equals `gain_fraction × withdrawal` where `gain_fraction = (balance − basis) / balance`. Optional: `setCostBasis([b1, b2])` (or TOML field `taxable_cost_basis`) supplies the current cost basis per person; the SC loop then tracks how basis evolves each year as shares are sold and new contributions (HFP contributions plus LP surplus deposits) add fresh basis, as do the dividends and interest taxed each year and reinvested in the account. Bond and cash returns are taxed yearly, so the account's unrealized gain is attributed to its equity share. Without a supplied basis, realized gains fall back to current-year price appreciation only (`(τ₀ − μ) × withdrawal`), which underestimates gains for accounts with substantial embedded appreciation. | All gains treated as long-term; short-term gains (holding period &lt; 1 year) not distinguished. Average-cost method only; FIFO and LIFO lot accounting not supported. Tax-loss harvesting not modeled. |
 | **Safety net (taxable)** | Optional inflation-indexed minimum balance per individual's taxable account. Enforced from year 2 through each individual's life horizon. | First year excluded. Can cause infeasibility if minimum exceeds initial balance or desired bequest is smaller than survivor's safety net. |
 | **Tax-deferred accounts** (401k, IRA, 403b) | Pre-tax contributions from Wages and Contributions table. Withdrawals taxed as ordinary income. RMDs enforced as minimum withdrawal floors from age 70–75 (birth-year dependent). 10% early withdrawal penalty before age 59½. | Pro-rata rule (IRS Form 8606) not modeled; entire balance treated as pre-tax. Early withdrawal exceptions (72(t), disability, etc.) not modeled. |
 | **Roth accounts** | After-tax contributions. Five-year maturation rule enforced via minimum-balance constraints (recent conversions + contribution gains retained). Age 59½ threshold per individual. Conversion amounts optimized; taxable as ordinary income in year of conversion. Individual years can be held fixed instead of optimized by ticking the *Roth conv fixed* column of the Wages & Contributions table beside the amount in *Roth conv*: the conversion is then pinned to exactly that amount, bypassing the annual cap and the last-two-years restriction, and an amount of `0` pins the year at no conversion. | Contribution principal not separately tracked; some valid early withdrawals of principal conservatively disallowed. Pro-rata rule not modeled. Roth conversions disallowed in last two years of plan horizon (unless that year is held fixed). |
diff --git a/papers/owl.tex b/papers/owl.tex
index 618b7c5..216d520 100644
--- a/papers/owl.tex
+++ b/papers/owl.tex
@@ -1619,7 +1619,7 @@ Parameter values are either set by the user, historical data, or by the tax code
 	in year $n$.  It is computed by the self-consistent loop and enters the LP as a
 	fixed parameter each iteration.
 	When a cost basis is provided via \code{setCostBasis()},
-	$\psi_{in} = 1 - K_{in}/b_{i0n}$ (see Eq.~(\ref{Eq:GainFrac})).
+	$\psi_{in} = (1 - K_{in}/b_{i0n})/\alpha_{i00n}$, capped at 1 (see Eq.~(\ref{Eq:GainFrac})).
 	Otherwise, $\psi_{in} = \max(0,\tau_{0(n-1)}-\mu)$, i.e., only the most
 	recent year's price appreciation is treated as a gain (Eq.~(\ref{Eq:Qx2})).
 \item [$\sigma_n$]
@@ -2004,20 +2004,29 @@ Intermediate variables are represented in roman uppercase letters, or in double
 	where
 	\begin{equation}
 		\label{Eq:GainFrac}
-		\psi_{in} = \max\!\left(0,\;1 - \frac{K_{in}}{b_{i0n}}\right)
+		\psi_{in} = \min\!\left(1,\;\frac{1}{\alpha_{i00n}}\max\!\left(0,\;1 - \frac{K_{in}}{b_{i0n}}\right)\right)
 	\end{equation}
-	is the fraction of the taxable account balance that represents unrealized gain.
+	is the fraction of the equity holdings that represents unrealized gain.
+	Bond and cash returns are taxed every year, so those holdings sit at their basis and
+	the account's whole unrealized gain $b_{i0n} - K_{in}$ is carried by the equity share
+	$\alpha_{i00n} b_{i0n}$; the realized gain $\alpha_{i00n}\psi_{in} w_{i0n}$ is then
+	$(1 - K_{in}/b_{i0n})\,w_{i0n}$.
 	Equation~(\ref{Eq:Qx2}) is recovered when $\psi_{in} = \max(0,\tau_{0(n-1)}-\mu)$,
 	the fallback used in the absence of a known basis.
 	The basis evolves between self-consistent iterations via the pro-rata (average-cost) rule
 	\begin{equation}
 		\label{Eq:BasisUpdate}
-		K_{i,n+1} = K_{in}\!\left(1 - \frac{w_{i0n}}{b_{i0n}}\right) + \kappa_{i0n} + d_{in},
+		K_{i,n+1} = K_{in}\!\left(1 - \frac{w_{i0n}}{b_{i0n}}\right) + \kappa_{i0n} + d_{in}
+		+ \Big(\alpha_{i00n}\mu + \sum_{k\ge1}\alpha_{i0kn}\max(0, \tau_{kn})\Big)
+		  \big(b_{i0n} - w_{i0n} + d_{in} + \tfrac{1}{2}\kappa_{i0n}\big),
 	\end{equation}
 	initialized at $K_{i0}$ from \code{setCostBasis()}.
 	Each withdrawal reduces the total basis in proportion to the account fraction
 	liquidated; fixed contributions $\kappa_{i0n}$ and surplus deposits $d_{in}$ are
 	new purchases added at full cost (zero embedded gain).
+	The last term is the year's dividends and interest: they are taxed as they are earned
+	and stay in the account, so they are reinvested at full cost too; leaving them out
+	would tax them a second time on sale.
 
 \item [$\mathbb{G}_n$]
 	Modified adjusted gross income (MAGI) for year $n$, on the adjusted-gross-income
diff --git a/src/owlplanner/plan.py b/src/owlplanner/plan.py
index 76abd9d..5207120 100644
--- a/src/owlplanner/plan.py
+++ b/src/owlplanner/plan.py
@@ -819,6 +819,19 @@ class Plan:
         """Unrealized gain fraction in [0, 1] from average-cost basis and account balance."""
         return min(1.0, max(0.0, 1.0 - float(basis) / max(1.0, float(balance))))
 
+    @staticmethod
+    def _equity_gain_fraction(basis, balance, alpha0):
+        """Unrealized gain fraction of the equity share of a taxable account, in [0, 1].
+
+        The model taxes bond and cash returns every year, so those holdings sit at their basis and
+        the account's whole unrealized gain, balance - basis, is in the equities. The gain fraction
+        is applied to the equity share of each withdrawal (alpha0 * w), so it is the whole-account
+        fraction divided by alpha0; realized gains are then (1 - basis/balance) * w.
+        """
+        if alpha0 <= 0:
+            return 0.0
+        return min(1.0, Plan._gain_fraction_from_basis(basis, balance) / float(alpha0))
+
     def setExpirationYearOBBBA(self, yOBBBA):
         """
         Set year at which OBBBA is speculated to expire and rates go back to something like pre-TCJA.
@@ -4714,15 +4727,20 @@ class Plan:
             if self.taxable_basis_i[i] == 0:
                 continue  # NaN → legacy fallback for this person
             b0 = self.beta_ij[i, 0]
-            self.gain_fraction_in[i, :] = self._gain_fraction_from_basis(self.taxable_basis_i[i], b0)
+            alpha0 = self.alpha_ijkn[i, 0, 0, 0]
+            self.gain_fraction_in[i, :] = self._equity_gain_fraction(self.taxable_basis_i[i], b0, alpha0)
 
     def _update_gain_fraction(self):
         """Update gain_fraction_in using last SC-iteration balances and withdrawals.
         Both fixed contributions (kappa) and LP surplus deposits (d_in) add to basis at full value
-        because they are new purchases at the current market price.
+        because they are new purchases at the current market price. So do the dividends and the
+        bond/cash returns taxed each year, which stay in the account and are reinvested: leaving
+        them out would tax them a second time on sale.
         Persons with zero basis are skipped (their NaN entries mean legacy fallback)."""
         if self.gain_fraction_in is None:
             return
+        # Same yield the model taxes each year as dividends and interest (see _add_taxable_income).
+        fak_in = np.sum(np.maximum(0, self.tau_kn[1:, :]) * self.alpha_ijkn[:, 0, 1:, : self.N_n], axis=1)
         for i in range(self.N_i):
             if self.taxable_basis_i[i] == 0:
                 continue  # stays NaN → legacy
@@ -4730,13 +4748,18 @@ class Plan:
             for n in range(self.N_n):
                 b_n = self.b_ijn[i, 0, n]
                 w_n = self.w_ijn[i, 0, n]
+                d_n = self.d_in[i, n]
+                kappa_n = self.kappa_ijn[i, 0, n]
+                alpha0 = self.alpha_ijkn[i, 0, 0, n]
                 # New purchases: fixed HFP contributions + LP-decided surplus deposits (both at full basis).
-                c_n = self.kappa_ijn[i, 0, n] + self.d_in[i, n]
-                self.gain_fraction_in[i, n] = self._gain_fraction_from_basis(basis, b_n)
+                c_n = kappa_n + d_n
+                # Reinvested income taxed this year: dividends on equities, all positive returns on the rest.
+                taxed_n = (self.mu * alpha0 + fak_in[i, n]) * (b_n - w_n + d_n + 0.5 * kappa_n)
+                self.gain_fraction_in[i, n] = self._equity_gain_fraction(basis, b_n, alpha0)
                 if b_n > 0:
-                    basis = basis * (1.0 - w_n / b_n) + c_n
+                    basis = basis * (1.0 - w_n / b_n) + c_n + max(0.0, taxed_n)
                 else:
-                    basis = c_n
+                    basis = c_n + max(0.0, taxed_n)
 
     def _scSolve(self, objective, options, solverMethod):
         """
diff --git a/tests/assets/test_cost_basis.py b/tests/assets/test_cost_basis.py
index 799f99a..e4bc420 100644
--- a/tests/assets/test_cost_basis.py
+++ b/tests/assets/test_cost_basis.py
@@ -199,6 +199,56 @@ class TestCostBasisValidation:
         assert owl.Plan._gain_fraction_from_basis(200, 1000) == 0.8
 
 
+class TestCostBasisReinvestedIncome:
+    """Taxed, reinvested dividends and interest add to basis; the gain sits in the equity share."""
+
+    def _solved(self, alloc):
+        thisyear = date.today().year
+        p = owl.Plan(["Bo"], [f"{thisyear - 60}-06-15"], [90], "reinvested", verbose=False)
+        p.setSpendingProfile("flat")
+        p.setAccountBalances(taxable=[1000], taxDeferred=[1000], taxFree=[0], startDate="01-01")
+        p.setCostBasis([500])
+        p.setAllocationRatios("individual", generic=[[alloc, alloc]])
+        p.setRates("user", values=[7, 4, 3, 2.5])
+        p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
+        assert p.caseStatus == "solved"
+        return p
+
+    @pytest.mark.parametrize("alloc", [[100, 0, 0, 0], [60, 40, 0, 0]])
+    def test_basis_includes_taxed_income(self, alloc):
+        """Recompute the basis by hand from the plan's own flows and compare the gain fractions."""
+        p = self._solved(alloc)
+        p._update_gain_fraction()
+        b, w, d, k = p.b_ijn[0, 0, :], p.w_ijn[0, 0, :], p.d_in[0, :], p.kappa_ijn[0, 0, :]
+        a0 = p.alpha_ijkn[0, 0, 0, :]
+        fak = np.sum(np.maximum(0, p.tau_kn[1:, :]) * p.alpha_ijkn[0, 0, 1:, : p.N_n], axis=0)
+        basis = 500e3
+        for n in range(p.N_n):
+            whole = min(1.0, max(0.0, 1 - basis / max(1.0, b[n])))
+            # Realized gain per dollar withdrawn is the whole-account gain fraction.
+            assert a0[n] * p.gain_fraction_in[0, n] == pytest.approx(min(a0[n], whole), abs=1e-9)
+            taxed = (p.mu * a0[n] + fak[n]) * (b[n] - w[n] + d[n] + 0.5 * k[n])
+            basis = (basis * (1 - w[n] / b[n]) if b[n] > 0 else 0) + k[n] + d[n] + max(0.0, taxed)
+
+    def test_gain_fraction_grows_slower_than_without_dividends(self):
+        """All equity, drawn down: dividends taxed every year keep the gain fraction lower."""
+        p = self._solved([100, 0, 0, 0])
+        p._update_gain_fraction()
+        b, w, d, k = p.b_ijn[0, 0, :], p.w_ijn[0, 0, :], p.d_in[0, :], p.kappa_ijn[0, 0, :]
+        basis_no_div = 500e3
+        n_last = int(np.max(np.nonzero(b[: p.N_n] > 1000)))
+        for n in range(n_last):
+            basis_no_div = basis_no_div * (1 - w[n] / b[n]) + k[n] + d[n]
+        gf_no_div = 1 - basis_no_div / b[n_last]
+        assert p.gain_fraction_in[0, n_last] < gf_no_div - 0.05
+
+    def test_equity_gain_fraction(self):
+        assert owl.Plan._equity_gain_fraction(500, 1000, 1.0) == pytest.approx(0.5)
+        assert owl.Plan._equity_gain_fraction(500, 1000, 0.6) == pytest.approx(0.5 / 0.6)
+        assert owl.Plan._equity_gain_fraction(100, 1000, 0.5) == 1.0  # capped
+        assert owl.Plan._equity_gain_fraction(100, 1000, 0.0) == 0.0  # no equity, no gain realized
+
+
 class TestCostBasisConfig:
     def test_plan_to_config_roundtrip(self):
         p = _make_plan("rt", taxable_k=500, tax_deferred_k=200, tax_free_k=50)
diff --git a/tests/data/amo_mip_reference.json b/tests/data/amo_mip_reference.json
index 95d10aa..8818ca9 100644
--- a/tests/data/amo_mip_reference.json
+++ b/tests/data/amo_mip_reference.json
@@ -2002,12 +2002,12 @@
   },
   "Case_helen+ruth": {
    "HiGHS": {
-    "_rerecorded": "2026-09-28 from Owl.dev LP after state base stopped deducting the federal standard deduction",
+    "_rerecorded": "2026-10-04 after taxable cost basis started counting reinvested dividends and putting the gain in equities (was 195243.52)",
     "amo_violations": {
      "roth": 0,
      "surplus": 0
     },
-    "basis": 195243.52,
+    "basis": 194069.03,
     "bequest": 200000.0,
     "conversions_n": [
      150000.0,
diff --git a/tests/plan/test_repro.py b/tests/plan/test_repro.py
index 994f839..35f81f3 100644
--- a/tests/plan/test_repro.py
+++ b/tests/plan/test_repro.py
@@ -40,21 +40,24 @@ import owlplanner as owl
 # solving it under different constraint subsets gave 939_900 / 978_246 / 960_684, an ordering
 # no relaxation can produce. Most of the move is which fixed point the loop lands on, not a
 # change in what is achievable, so these are reproducibility anchors and not optimality claims.
+# Updated when taxable cost basis started counting taxed, reinvested dividends and interest and
+# putting the account's unrealized gain in its equity share: SPENDING1 89_532 -> 89_154,
+# BEQUEST1 960_684 -> 959_220 (recorded with HiGHS on linux; the other platforms take the same).
 if platform == "darwin":
-    SPENDING1 = 89_532
-    BEQUEST1 = 960_684
+    SPENDING1 = 89_154
+    BEQUEST1 = 959_220
     SPENDING2 = 99_246
     SPENDING1_FIXED = 93_255
     BEQUEST1_FIXED = 500_000
 elif platform == "linux":
-    SPENDING1 = 89_532
-    BEQUEST1 = 960_684
+    SPENDING1 = 89_154
+    BEQUEST1 = 959_220
     SPENDING2 = 99_246
     SPENDING1_FIXED = 93_255
     BEQUEST1_FIXED = 500_000
 elif platform in "win32":
-    SPENDING1 = 89_532
-    BEQUEST1 = 960_684
+    SPENDING1 = 89_154
+    BEQUEST1 = 959_220
     SPENDING2 = 99_246
     SPENDING1_FIXED = 93_255
     BEQUEST1_FIXED = 500_000
diff --git a/tests/plan/test_toml_cases.py b/tests/plan/test_toml_cases.py
index d3341d7..78594b8 100644
--- a/tests/plan/test_toml_cases.py
+++ b/tests/plan/test_toml_cases.py
@@ -117,6 +117,8 @@ def getHFP(exdir, case, check_exists=True):
 # neither: jack+jill 102_515 -> 102_577 (the loop now waits for its fed-back quantities to
 # settle) and kim+sam-spending 186_583 -> 186_590 under HiGHS.
 #
+# jack+jill, joe and robin moved (-42, -469, -56) when taxable cost basis started counting taxed,
+# reinvested dividends and interest and putting the unrealized gain in the equity share.
 # kim+sam-spending returned to 186_583 under HiGHS when residualTol became a per-year bar: at
 # $50/yr it converges where it did before the exit test, while MOSEK still settles at 186_519.
 EXPECTED_OBJECTIVE_VALUES = {
@@ -125,11 +127,11 @@ EXPECTED_OBJECTIVE_VALUES = {
         "bequest": 16_803,
     },
     "Case_jack+jill": {
-        "net_spending_basis": 102_577,
+        "net_spending_basis": 102_535,
         "bequest": 400_000,
     },
     "Case_joe": {
-        "net_spending_basis": 93_044,
+        "net_spending_basis": 92_575,
         "bequest": 300_000,
     },
     "Case_kim+sam-spending": {
@@ -141,7 +143,7 @@ EXPECTED_OBJECTIVE_VALUES = {
         "bequest": 1_944_071,
     },
     "Case_robin": {
-        "net_spending_basis": 44_069,
+        "net_spending_basis": 44_013,
         "bequest": 50_000,
     },
 }
```

</details>
