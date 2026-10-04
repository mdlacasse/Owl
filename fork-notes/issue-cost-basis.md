# Draft upstream issue (mdlacasse/Owl): tracked cost basis leaves out reinvested dividends, and applies the account's gain fraction to the equity share only

**Not filed yet.**

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

Verified against `dev` (`c1e5619`): with the patch alone the full suite gives RESULT_BASIS; flake8 is clean. New tests are in `TestCostBasisReinvestedIncome`. `test_basis_includes_taxed_income` recomputes the basis by hand from the plan's own flows, for 100/0 and 60/40. There are also `test_gain_fraction_grows_slower_than_without_dividends` and `test_equity_gain_fraction`. All fail on `dev`.

<details><summary>Patch (source, docs and tests, applies to <code>c1e5619</code>)</summary>

```diff
PATCH_BASIS
```

</details>
