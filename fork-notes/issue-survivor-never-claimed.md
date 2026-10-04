# Draft upstream issue (mdlacasse/Owl): survivor of a worker who died before claiming gets 82.5% of PIA

**Filed upstream by the user on 2026-10-04** (issue number not recorded yet).

**Title:** Survivor benefit: a worker who dies before claiming should leave 100% of PIA (plus DRCs earned up to death), not the 82.5% floor

---

`compute_survivor_stream` (`socialsecurity.py`) sets the deceased's benefit to 0 when they had not started benefits by the year of death, so the survivor gets the floor, 0.825 x PIA:

```python
    else:
        deceased_monthly = 0.0  # Died before claiming; only the 82.5% PIA floor applies.

    monthly = max(deceased_monthly, 0.825 * pias[deceased_idx]) * _survivor_factor(survivor_fra, claim_age)
```

The 82.5% figure is the widow(er)'s limit (RIB-LIM). It caps a survivor benefit when the deceased had **reduced** their own benefit by claiming early: the survivor gets the larger of the deceased's reduced benefit and 82.5% of PIA. A worker who was never entitled had no reduced benefit, so the limit doesn't apply. The survivor's base is 100% of PIA. If death came after FRA, it also includes the delayed retirement credits earned up to death. The sources:

- Social Security Act 202(e)(2)(D) ([42 U.S.C. 402(e)(2)(D)](https://www.govinfo.gov/content/pkg/USCODE-2024-title42/html/USCODE-2024-title42-chap7-subchapII-sec402.htm)) applies the limit only "if the deceased individual ... was, at any time, entitled to an old-age insurance benefit which was reduced by reason of the application of subsection (q)".
- [20 CFR 404.338](https://www.ecfr.gov/current/title-20/section-404.338): "(a) Your monthly benefit is equal to the insured person's primary insurance amount. ... (b) We may increase your monthly benefit amount if the insured person delays filing for benefits ... and thereby earns delayed retirement credit (see § 404.313) ... (c) Your monthly benefit will be reduced if the insured person chooses to receive old-age benefits before reaching full retirement age. If so, your benefit will be reduced to the amount the insured person would be receiving if alive, or 82 1/2 percent of his or her primary insurance amount, whichever is larger."
- [20 CFR 404.313(e)(1)](https://www.ecfr.gov/current/title-20/section-404.313#p-404.313(e)(1)): "All delayed retirement credits, including any earned during the year of death, can be used in computing the benefit amount for your surviving spouse ... beginning with the month of your death. We compute delayed retirement credits up to but not including the month of death." Credits run from the month of FRA to the month of age 70 (404.313(a)).
- [POMS RS 00615.320](https://secure.ssa.gov/poms.nsf/lnx/0300615320) A.1: "Consider the RIB LIM ... if the deceased NH was ever entitled to a reduced RIB or reduced DIB."

The paper lists the current behavior as a limitation ("credited with the 82.5% PIA floor rather than the benefit accrued to the date of death"). The gap is 17.5 to 49.5 points of PIA: 100% to 132% against 82.5%. It applies whenever the user's fixed claiming age is later than the first death. For example, a spouse planning to claim at 70 whose life expectancy is 68.


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

Verified against `dev` (`c1e5619`): with the patch alone the full suite gives 2604 passed, 1 skipped; flake8 is clean. New test: `test_compute_ss_survivor_deceased_never_claimed` (two cases; both fail on `dev`). None of the 17 examples changes.

<details><summary>Patch (source, docs and tests, applies to <code>c1e5619</code>)</summary>

```diff
diff --git a/info/modeling-capabilities.md b/info/modeling-capabilities.md
index c848930..593e065 100644
--- a/info/modeling-capabilities.md
+++ b/info/modeling-capabilities.md
@@ -22,7 +22,7 @@ This document summarizes all modeling components in Owl (Optimal wealth lab), ho
 | **Debts** | Amortized payments from start year for term years. Principal and interest from standard amortization. Enters cash-flow as fixed outflows. | No optimization of paydown vs. invest. Mortgage interest not deducted (standard deduction assumed). |
 | **Wages & contributions** | Year-indexed table: wages, other income, net inv, contributions to all account types, Roth conversions, QCDs, big-ticket items. Five-year lookback for Roth maturation. Only the `year` column is required; any other column may be omitted and is read as zero. | User-supplied; no optimization of contribution amounts. HSA contributions zeroed at Medicare age. |
 | **Qualified Charitable Distributions (QCDs)** | Per-person, per-year amounts from the `QCD` column of the Wages & Contributions table. Excluded from AGI, so they lower federal and state taxable income, Social Security taxability, and the MAGI feeding IRMAA and NIIT. Credited against the RMD dollar-for-dollar, drawn from the tax-deferred balance, and never available as spending. Age 70.5 and the annual per-person limit ($108k in 2025, $115k in 2026, indexed; later years projected at a fixed 3%) are enforced as errors. Reported as a `Charitable giving` slice in the lifetime-allocation and cash-flow-mix charts, as a dedicated *Charitable Giving (QCD)* chart splitting each gift at the RMD it satisfies, as its own worksheet column, and in the case description. | Amount is user-specified, not optimized. IRA-only eligibility not checked: Owl aggregates IRA with 401(k)/403(b) into one tax-deferred account. A 401(k) balance must be rolled over to an IRA first to be eligible, which is a real-world step but a non-event in the model. Anti-abuse offset for deductible IRA contributions after 70.5 not modeled. One-time split-interest-entity QCD (CGA/CRT) not modeled. |
-| **Social Security benefits** | PIA × age-based adjustment factor. FRA by birth year (65–67). Own, spousal, and survivor benefits computed from PIA and DOB. First-year proration by fraction of year remaining (same as pension). Taxability (0–85%) from provisional income formula converged via the SC loop. Optional trim for trust-fund scenarios. Claiming ages are user-specified by default. Optional: `withSSTaxability="optimize"` replaces the SC-loop taxability approximation with an exact MILP formulation. Optional: `withSSAges="optimize"` co-optimizes SS claiming ages (monthly resolution, 62–70) via MILP. **Survivor benefits:** the survivor's own benefit and the survivor benefit are tracked as separate streams and the larger is paid each year, so a survivor who has not yet claimed keeps their own (still growing) benefit. Amount is set by the deceased's record — the greater of their benefit at death and 82.5% of their PIA (CFR §404.338) — and fixed at death (no posthumous DRCs). The reduction is measured against the survivor's own age at filing, linearly from 71.5% at 60 to 100% at the survivor FRA (a distinct schedule from the retirement FRA, up to 4 months earlier); no credit accrues past it. `social_security_survivor_claim_age` sets the timing: `"immediate"` (default), `"fra"`, or an explicit age. | Family maximum benefit cap not modeled. Earnings test not modeled; users assumed fully retired before FRA. Survivor claiming date is user-specified, not optimized. A worker who dies before claiming is credited with the 82.5% PIA floor rather than their accrued benefit. WEP and GPO repealed (2025); not modeled. |
+| **Social Security benefits** | PIA × age-based adjustment factor. FRA by birth year (65–67). Own, spousal, and survivor benefits computed from PIA and DOB. First-year proration by fraction of year remaining (same as pension). Taxability (0–85%) from provisional income formula converged via the SC loop. Optional trim for trust-fund scenarios. Claiming ages are user-specified by default. Optional: `withSSTaxability="optimize"` replaces the SC-loop taxability approximation with an exact MILP formulation. Optional: `withSSAges="optimize"` co-optimizes SS claiming ages (monthly resolution, 62–70) via MILP. **Survivor benefits:** the survivor's own benefit and the survivor benefit are tracked as separate streams and the larger is paid each year, so a survivor who has not yet claimed keeps their own (still growing) benefit. Amount is set by the deceased's record — the greater of their benefit at death and 82.5% of their PIA (CFR §404.338); a worker who died before claiming leaves the full PIA plus the DRCs earned up to death — and fixed at death (no posthumous DRCs). The reduction is measured against the survivor's own age at filing, linearly from 71.5% at 60 to 100% at the survivor FRA (a distinct schedule from the retirement FRA, up to 4 months earlier); no credit accrues past it. `social_security_survivor_claim_age` sets the timing: `"immediate"` (default), `"fra"`, or an explicit age. | Family maximum benefit cap not modeled. Earnings test not modeled; users assumed fully retired before FRA. Survivor claiming date is user-specified, not optimized. WEP and GPO repealed (2025); not modeled. |
 | **Pension income** | Monthly amount and commencement age per individual. Optional inflation indexing. First-year proration by fraction of year remaining. Joint-and-survivor fraction for survivor benefit. | Early-commencement reductions and late-commencement credits not modeled. |
 | **SPIA (Single Premium Immediate Annuity)** | IRA/401k rollover funds a SPIA: premium deducted from tax-deferred account in buy year (non-taxable event); annual payments begin in the same year as purchase as fully taxable ordinary income. Optional CPI indexing. Optional joint-and-survivor fraction for couples. Payments increase MAGI, affecting Medicare IRMAA surcharges and Social Security taxability. Multiple SPIAs supported per plan. | Premium assumed drawn entirely from tax-deferred account (IRA rollover); non-IRA funding not modeled. Partial-year proration of income in buy year not modeled (full annual payment assumed). Annuity pricing (premium-to-income ratio) is user-supplied; no built-in pricing model. |
 | **Ordinary income tax** | Seven brackets (OBBBA 2026: 10–37%). Standard deduction + 65+ additional + OBBBA §1002 bonus (phases out by MAGI). Bracket widths and rates inflation-adjusted. Optional reversion to pre-TCJA rates. | Itemized deductions not modeled; standard deduction only. OBBBA 65+ bonus phaseout computed outside LP (post-solution update). |
diff --git a/papers/owl.tex b/papers/owl.tex
index 618b7c5..4a80f70 100644
--- a/papers/owl.tex
+++ b/papers/owl.tex
@@ -352,7 +352,8 @@ of 25/36 of~1\% per month for claiming before the spousal FRA (which mirrors
 the own FRA schedule) and no bonus for deferral beyond FRA.
 
 The survivor benefit is the greater of the deceased spouse's actual benefit and
-82.5\% of the deceased's PIA, reduced if the survivor claims before their own
+82.5\% of the deceased's PIA; a spouse who died before claiming leaves the full PIA,
+plus the delayed retirement credits earned up to death. It is reduced if the survivor claims before their own
 survivor FRA (minimum 71.5\% at age~60, interpolated linearly in the claiming month).
 Unlike the retirement benefit, it earns no delayed retirement credits past the
 survivor FRA, so deferring beyond that date is never advantageous.
@@ -407,8 +408,7 @@ The SSA earnings test is not modeled; users are assumed to be fully retired
 before their FRA.
 The survivor claiming date is a user setting rather than an optimized decision:
 the model evaluates whichever date is specified, but does not search for the one
-that maximizes the objective. A worker who dies before claiming is credited with
-the 82.5\% PIA floor rather than the benefit accrued to the date of death.
+that maximizes the objective.
 The Windfall Elimination Provision (WEP) and Government Pension Offset (GPO)
 were repealed by the Social Security Fairness Act (signed January~5, 2025) and therefore
 require no modeling.
diff --git a/src/owlplanner/socialsecurity.py b/src/owlplanner/socialsecurity.py
index 965dc8d..ae16f00 100644
--- a/src/owlplanner/socialsecurity.py
+++ b/src/owlplanner/socialsecurity.py
@@ -520,8 +520,10 @@ def compute_survivor_stream(
 
     The amount follows CFR § 404.338: the greater of the deceased's actual benefit at
     death and 82.5% of their PIA, reduced by ``_survivor_factor`` when claimed before the
-    survivor FRA. The start date comes from ``survivor_claim_age`` and is never earlier
-    than age 60 or the year of the first death.
+    survivor FRA. A deceased who had not claimed leaves the full PIA, plus the delayed
+    retirement credits earned up to death; the 82.5% limit applies only to reduced benefits.
+    The start date comes from ``survivor_claim_age`` and is never earlier than age 60 or the
+    year of the first death.
 
     This is the same stream ``compute_social_security_benefits`` combines with the
     survivor's own benefit; it is exposed separately so the SS claiming-age MIP can fold
@@ -560,7 +562,14 @@ def compute_survivor_stream(
             fra_deceased, ages[deceased_idx], bool(tobs[deceased_idx] == 1)
         )
     else:
-        deceased_monthly = 0.0  # Died before claiming; only the 82.5% PIA floor applies.
+        # Died before claiming: no reduced benefit, so the widow(er)'s limit (82.5% floor) does not
+        # apply (POMS RS 00615.320). The survivor's base is the full PIA, plus the delayed retirement
+        # credits earned up to death when death came after FRA (capped at 70).
+        age_at_death_dec = (thisyear + death_year_n) - yobs[deceased_idx] - (mobs[deceased_idx] - 1) / 12
+        deceased_monthly = pias[deceased_idx] * max(
+            1.0,
+            getSelfFactor(fra_deceased, min(70.0, max(62.0, age_at_death_dec)), bool(tobs[deceased_idx] == 1)),
+        )
 
     monthly = max(deceased_monthly, 0.825 * pias[deceased_idx]) * _survivor_factor(survivor_fra, claim_age)
 
diff --git a/tests/ss/test_socsec.py b/tests/ss/test_socsec.py
index 66349d6..186e7ba 100644
--- a/tests/ss/test_socsec.py
+++ b/tests/ss/test_socsec.py
@@ -373,6 +373,35 @@ def test_compute_ss_survivor_pia_floor():
     assert zeta_in[1, 15] == pytest.approx(expected_annual, rel=0.01)
 
 
+@pytest.mark.parametrize(
+    "age_now, factor",
+    [
+        (60, 1.0),  # dies at 63, before FRA 67: full PIA, not the 82.5% floor
+        (66, 1.16),  # dies at 69, after FRA 67 without claiming: PIA plus 2 years of DRCs
+    ],
+)
+def test_compute_ss_survivor_deceased_never_claimed(age_now, factor):
+    """A worker who dies before claiming leaves the full PIA, plus DRCs earned up to death."""
+    from datetime import date
+
+    thisyear = date.today().year
+    yobs = np.array([thisyear - age_now, thisyear - 67])
+    pias = np.array([2000, 400])
+    ages = np.array([70.0, 67.0])  # person 0 would have claimed at 70
+    mobs = np.array([1, 1])
+    tobs = np.array([15, 15])
+    horizons = np.array([3, 20])  # person 0 dies at the start of year 3
+    N_i, N_n = 2, 20
+
+    zeta_in, _ = ss.compute_social_security_benefits(
+        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, thisyear=thisyear
+    )
+    assert np.all(zeta_in[0, :] == 0)  # never claimed
+    expected_annual = factor * pias[0] * 12  # survivor is past their survivor FRA: no reduction
+    assert zeta_in[1, 3] == pytest.approx(expected_annual, rel=1e-6)
+    assert zeta_in[1, 15] == pytest.approx(expected_annual, rel=1e-6)
+
+
 def test_survivor_min_age_60():
     """Survivor under 60 at death: factor clamped to age-60 floor (71.5%)."""
     # Age 55 is below SSA minimum; factor must equal the age-60 value (0.715).
```

</details>
