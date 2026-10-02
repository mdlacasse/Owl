# Draft upstream issue (mdlacasse/Owl): NY tax understated because Owl inflates amounts NY fixes in statute

**Title:** State tax: New York brackets, standard deduction and $20k exclusion are inflation-adjusted, but NY does not index them

---

`st_taxParams` multiplies every state's bracket widths, standard deduction and exemption caps by `gamma_n`. That is right for states that index (MN, CA, ...), but New York fixes these amounts in nominal dollars. In Owl, inflation widens NY's brackets and raises its deductions year after year, which never happens on a real return. The further out the year, the more NY tax is understated.

**Evidence that NY does not index.** The IT-201 instructions print the same dollar amounts in every year I checked (2018, 2021, 2024, 2025), across seven years of inflation:

| Amount | 2018 | 2021 | 2024 | 2025 |
|---|---|---|---|---|
| MFJ rate-schedule thresholds 17,150 / 23,600 / 27,900 / 161,550 / 323,200 | same | same | same | same |
| Standard deduction, MFJ / Single | 16,050 / 8,000 | same | same | same |
| Pension and annuity income exclusion | $20,000 | same | same | same |

Only the rates have changed (the bracket above 161,550 was 6.57% in 2018 and 6% in 2024). The 2026 withholding tables (NYS-50-T-NYS, 1/26) keep the same thresholds with the 2026 rate cuts.

**Repro** (on `dev`, `a85ff76`), with 2.5% inflation:

```python
import numpy as np
from owlplanner import tax_state

gamma = np.array([1.025**n for n in range(31)])
res = tax_state.st_taxParams("NY", 2, 30, 30, gamma, [1964, 1964], mobs=[6, 12])
delta, sigma, re_cap = res[2], res[3], res[4]
for n in (0, 10, 20):
    lower = np.concatenate(([0.0], np.cumsum(delta[:, n])[:-1]))
    print(f"year {n:2d}: std deduction {sigma[n]:,.0f}   fifth-bracket threshold {lower[4]:,.0f}   "
          f"pension exclusion {re_cap[0, n]:,.0f}")
```

```
year  0: std deduction 16,050   fifth-bracket threshold 161,550   pension exclusion 20,000
year 10: std deduction 20,545   fifth-bracket threshold 206,798   pension exclusion 25,602
year 20: std deduction 26,300   fifth-bracket threshold 264,718   pension exclusion 32,772
```

**Effect on a plan.** A NY couple born 1964, SS at 70, $300k taxable, $150k Roth, `maxSpending`, `conservative` rates, with Medicare off and SS taxability pinned at 0.85 so the comparison is exact. Lifetime NY tax in today's dollars, on `dev` and with the patch below:

| Tax-deferred | NY tax, `dev` | NY tax, patched | Spending change |
|---:|---:|---:|---:|
| $1.5M | 13,345 | 30,590 | -$417/yr |
| $2.5M | 64,553 | 89,965 | -$705/yr |

**Suggested fix:** a per-state `indexed` flag, default true, set false for NY:

```diff
diff --git a/src/owlplanner/data/taxes_state.toml b/src/owlplanner/data/taxes_state.toml
index dd5de9f..1224e94 100644
--- a/src/owlplanner/data/taxes_state.toml
+++ b/src/owlplanner/data/taxes_state.toml
@@ -35,6 +35,9 @@
 #   roth_conversion_eligible  = true/false — whether Roth conversion income counts toward
 #                               retirement_income_exemption (default true; false for MD,
 #                               whose pension exclusion does not cover IRAs or conversions)
+#   indexed                   = true/false — whether bracket thresholds, the standard deduction
+#                               and dollar caps grow with inflation (default true). False for
+#                               states whose statute fixes them in nominal dollars (NY).
 #
 # Exemption caps are per person: each spouse's exemption is limited by that spouse's own
 # age and eligible income (tax-deferred withdrawals, Roth conversions, pensions), and an
@@ -974,6 +977,7 @@ retirement_income_exemption = 20000
 exemption_age = 59.5
 pension_exemption = 0
 roth_conversion_eligible = true
+indexed = false  # thresholds, deduction and $20k exclusion are statutory dollars
 
 [NY_MFJ]
 brackets = [
@@ -988,6 +992,7 @@ retirement_income_exemption = 20000
 exemption_age = 59.5
 pension_exemption = 0
 roth_conversion_eligible = true
+indexed = false  # thresholds, deduction and $20k exclusion are statutory dollars
 
 [ND_Single]
 # ND: SB 2302 (2023) dramatically simplified brackets. 2026 structure (inflation-adjusted
diff --git a/src/owlplanner/tax_state.py b/src/owlplanner/tax_state.py
index 33aa4e7..c3339b6 100644
--- a/src/owlplanner/tax_state.py
+++ b/src/owlplanner/tax_state.py
@@ -155,6 +155,10 @@ def st_taxParams(
     n_mfj = len(entry_mfj["brackets"])
     N_st = max(n_single, n_mfj)
 
+    # States that fix their dollar amounts in statute (NY) keep them nominal.
+    indexed = entry_single.get("indexed", True)
+    gamma_n = gamma_n if indexed else np.ones_like(gamma_n)
+
     # --- Pre-compute base rates and widths for each filing status ---
     # Pad the shorter schedule with zero-width brackets at the top rate, after its
     # open-ended bracket has kept the sentinel width. Padding before converting would
```

Holding `gamma_n` at 1 for a non-indexed state keeps the brackets, the standard deduction, the retirement and pension caps and the SS threshold nominal. It also leaves the open-ended top bracket's sentinel width nominal; that only matters above about $30M of NY taxable income. Two tests come with it (NY amounts constant across years; MN still indexed). The full suite passes with it (2596 passed, 1 skipped) and no regression baseline moves.

```python
def test_ny_amounts_are_not_indexed():
    """NY fixes its thresholds, standard deduction and $20k exclusion in statute."""
    gamma = np.array([1.025**n for n in range(31)])
    _, _, delta, sigma, re_cap, *_ = tax_state.st_taxParams("NY", 2, 30, 30, gamma, [1964, 1964], mobs=[6, 12])
    np.testing.assert_array_equal(delta[:-1, 20], delta[:-1, 0])
    assert sigma[20] == sigma[0] == 16050
    assert re_cap[0, 20] == 20000


def test_other_states_stay_indexed():
    gamma = np.array([1.025**n for n in range(31)])
    _, _, delta, sigma, *_ = tax_state.st_taxParams("MN", 2, 30, 30, gamma, [1964, 1964], mobs=[6, 12])
    assert sigma[20] == pytest.approx(sigma[0] * gamma[20])
    assert delta[0, 20] == pytest.approx(delta[0, 0] * gamma[20])
```

Related, and separate: NY's benefit recapture (the supplemental tax above $107,650 of NY AGI) is also missing. I'll file it on its own.
