# Draft upstream issue (mdlacasse/Owl): the claiming-age MILP charges every candidate age the same tax on SS

**Not filed yet.**

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

Verified against `dev` (`c1e5619`): with the patch alone the full suite gives RESULT_SSAGE; flake8 is clean. New tests: `TestClaimingAgeTaxes::test_tax_rows_carry_ssb` and `test_result_independent_of_starting_age_and_consistent`. Both fail on `dev`. None of the 17 examples changes (none uses `withSSAges="optimize"`).

<details><summary>Patch (source, paper and tests, applies to <code>c1e5619</code>)</summary>

```diff
PATCH_SSAGE
```

</details>
