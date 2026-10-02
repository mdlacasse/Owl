# Draft upstream issue (mdlacasse/Owl): New York benefit recapture is missing

**Title:** State tax: New York's benefit recapture (supplemental tax above $107,650 of NY AGI) is not modeled

---

Owl taxes NY income with the rate schedule alone. Above $107,650 of NY AGI, New York also takes back the benefit of the lower brackets: the IT-201 *tax computation worksheets* add a supplemental amount that phases in over $50,000 of AGI, tier by tier, until all of the taxable income is taxed at the rate of its top bracket. Owl leaves that amount out, so NY tax is understated in every year a NY plan's AGI exceeds $107,650, which Roth-conversion years often do.

**How much.** With the 2026 NY rates (`taxes_state.toml` as on `dev`), taking the standard deduction:

| NY AGI | MFJ: bracket tax | MFJ: recapture | Single: bracket tax | Single: recapture |
|---:|---:|---:|---:|---:|
| 100,000 | 4,201 | 0 | 4,860 | 0 |
| 125,000 | 5,551 | 115 | 6,335 | 197 |
| 150,000 | 6,901 | 282 | 7,810 | 481 |
| 175,000 | 8,251 | 332 | 9,285 | 568 |
| 200,000 | 9,713 | 954 | 10,760 | 568 |
| 225,000 | 11,188 | 1,140 | 12,250 | 961 |
| 250,000 | 12,663 | 1,140 | 13,962 | 1,984 |
| 300,000 | 15,613 | 1,140 | 17,387 | 2,615 |
| 400,000 | 22,090 | 4,211 | 24,237 | 2,615 |

At the margin that is about +0.7% from $107,650 to $157,650 of AGI and +1.6% from $161,550 to $211,550 (MFJ), on top of the bracket rate.

**The rule** (worksheets 1-10 of the 2025 IT-201-I):

- The bracket that contains $107,650 gives the rate r1 (MFJ 5.5%, Single 6% in 2025). While taxable income stays below the next bracket threshold, the recapture is (r1 x TI - tax(TI)), phased in linearly as AGI rises from 107,650 to 157,650.
- Once taxable income reaches a higher threshold L (rate r, the rate below it r0), the recapture is the fully phased amount up to L, r0 x L - tax(L) (the worksheets' *Recapture Base amount*), plus (r - r0) x L (the *Incremental Benefit amount*) phased in as AGI rises from L to L + 50,000.
- Amounts follow from the brackets, so the 2026 rate cut flows through without editing constants. The worksheet lines "excess of line 1 over $107,650" and "Divide line 6 by $50,000" read the same in the 2018, 2021, 2024 and 2025 instructions, and the 2026 withholding tables keep the 107,650 / 157,650 bands.
- Not covered: the flat 10.9% that applies above $25M of AGI.

One property worth knowing: when taxable income crosses a tier threshold while AGI is above it, the tax jumps by the phased-in incremental amount (e.g. +$807.75 at TI 161,550 once MFJ AGI is 211,550 or more), because the whole income moves to the higher flat rate. That is what the printed worksheets compute.

**Reference implementation** of the rule, standalone on `dev` (`a85ff76`), with a check against every constant printed on the worksheets:

```python
import numpy as np
from owlplanner import tax_state


def bracket_tax(ti: float, theta: np.ndarray, Delta: np.ndarray) -> float:
    """Tax on taxable income *ti* from one year's marginal rates and bracket widths."""
    lower = np.concatenate(([0.0], np.cumsum(Delta)[:-1]))
    return float(np.sum(theta * np.clip(ti - lower, 0.0, Delta)))


def state_recapture(
    agi: float, ti: float, theta: np.ndarray, Delta: np.ndarray, start: float, width: float, until: float,
    round_phase: bool = False,
) -> float:
    """Supplemental tax that takes back the benefit of the lower brackets (NY Tax Law sec. 601(d)).

    The state's tax on *ti* comes from the brackets; above state AGI *start* the benefit of paying
    less than the top rate on the lower slices is recaptured, in tiers:

    - The bracket that contains *start* gives the rate r1. While *ti* is below the next bracket
      threshold, the recapture is (r1 * ti - tax(ti)), phased in linearly as AGI rises from
      *start* to *start* + *width*.
    - Once *ti* reaches a higher bracket threshold L, with rate r and the rate below it r0, the
      recapture is the fully phased amount up to L, r0 * L - tax(L), plus (r - r0) * L phased in
      as AGI rises from L to L + *width*. The highest threshold that counts is *until*.

    This reproduces the constants on the IT-201-I tax computation worksheets (2025). *round_phase*
    rounds the phase-in fraction to four decimals, as the worksheets do.
    """
    if agi <= start:
        return 0.0

    def phase(x):
        f = min(max(x / width, 0.0), 1.0)
        return round(f, 4) if round_phase else f

    real = Delta > 0
    theta, Delta = theta[real], Delta[real]
    lower = np.concatenate(([0.0], np.cumsum(Delta)[:-1]))
    j0 = int(np.searchsorted(lower, start, side="right")) - 1  # bracket holding the start
    tiers = [k for k in range(j0 + 1, len(lower)) if lower[k] <= until]
    reached = [k for k in tiers if ti >= lower[k]]
    if not reached:
        return (theta[j0] * ti - bracket_tax(ti, theta, Delta)) * phase(agi - start)
    k = reached[-1]
    base = theta[k - 1] * lower[k] - bracket_tax(lower[k], theta, Delta)
    return base + (theta[k] - theta[k - 1]) * lower[k] * phase(agi - lower[k])


# Check against the 2025 IT-201-I worksheets (rate schedules on page 34, constants on worksheets 2-5, 8-10).
MFJ_2025 = [[0, 4], [17150, 4.5], [23600, 5.25], [27900, 5.5], [161550, 6], [323200, 6.85],
            [2155350, 9.65], [5000000, 10.3]]
SINGLE_2025 = [[0, 4], [8500, 4.5], [11700, 5.25], [13900, 5.5], [80650, 6], [215400, 6.85],
               [1077550, 9.65], [5000000, 10.3]]
SHEETS = {"MFJ": (MFJ_2025, [(161550, 333, 807), (323200, 1140, 2747), (2155350, 3887, 60350), (5000000, 64237, 32500)]),
          "Single": (SINGLE_2025, [(215400, 568, 1831), (1077550, 2399, 30172), (5000000, 32571, 32500)])}
for name, (brackets, sheets) in SHEETS.items():
    theta, Delta = tax_state._brackets_to_rates_and_widths(brackets, 5e6)
    for L, base, incremental in sheets:
        lo = state_recapture(L, L + 1000, theta, Delta, 107650, 50000, 5e6)
        hi = state_recapture(L + 50000, L + 1000, theta, Delta, 107650, 50000, 5e6)
        assert abs(lo - base) < 1 and abs(hi - lo - incremental) < 1, (name, L, lo, hi - lo)
        print(f"{name:6} threshold {L:>9,}: base {lo:>9,.1f} (sheet {base:,})  incremental {hi - lo:>9,.1f} (sheet {incremental:,})")
# Worksheet 1 by hand: MFJ, NY AGI 120,000, taxable income 100,000.
theta, Delta = tax_state._brackets_to_rates_and_widths(MFJ_2025, 5e6)
r = state_recapture(120_000, 100_000, theta, Delta, 107650, 50000, 5e6, round_phase=True)
print(f"worksheet 1, AGI 120,000 / TI 100,000: line 8 = {r:.2f} (hand: (5,500 - 5,167.50) x 0.2470 = 82.13)")
```

Output on `dev`:

```
MFJ    threshold   161,550: base     332.5 (sheet 333)  incremental     807.7 (sheet 807)
MFJ    threshold   323,200: base   1,140.2 (sheet 1,140)  incremental   2,747.2 (sheet 2,747)
MFJ    threshold 2,155,350: base   3,887.5 (sheet 3,887)  incremental  60,349.8 (sheet 60,350)
MFJ    threshold 5,000,000: base  64,237.2 (sheet 64,237)  incremental  32,500.0 (sheet 32,500)
Single threshold   215,400: base     568.2 (sheet 568)  incremental   1,830.9 (sheet 1,831)
Single threshold 1,077,550: base   2,399.1 (sheet 2,399)  incremental  30,171.4 (sheet 30,172)
Single threshold 5,000,000: base  32,570.6 (sheet 32,571)  incremental  32,500.0 (sheet 32,500)
worksheet 1, AGI 120,000 / TI 100,000: line 8 = 82.13 (hand: (5,500 - 5,167.50) x 0.2470 = 82.13)
```

**Data**, on `NY_Single` and `NY_MFJ`:

```toml
recapture_agi_start = 107650  # benefit recapture, Tax Law sec. 601(d)
recapture_width = 50000
recapture_until = 5000000     # highest threshold that starts a tier; the 25M cliff is not modeled
```

**Wiring it into the solve.** The recapture is a function of NY AGI and NY taxable income, both of which come out of the LP, so it fits the self-consistent loop exactly as the NIIT `J_n` does:

1. After `_aggregateResults(x, short=True)` in `_computeNLstuff`, compute `STR_n[n] = state_recapture(SAGI_n, TI_n, ...)` with TI = sum of `st_f`, and SAGI = `G_n + e_n + Q_n` less the SS the state excludes, the pension exemption and the claimed `st_re`, the same terms as the `state_taxable_income` row. That needs `st_f` and `st_re` extracted before the `if short: return` in `_aggregateResults`.
2. In `_add_net_cash_flow`, `rhs -= STR_n[n]` next to `J_n`.
3. Snapshot, step-back blend, trace and restore it with `M_n`, `ACA_n`, `J_n` and `Psi_n` in `_scSolve`. On `dev` those four are spelled out at about a dozen sites (`J_n_lp` appears 12 times), so a fifth quantity means touching each of them. In our fork we first folded them into one tuple of names (`_SC_PARAMS`) so that adding `STR_n` is a single entry; happy to send that refactor separately if you want it.
4. Add it to `st_T_n` after the final restore, and a `state recapture` family to the fixed-point residual.

The cash-flow builder is not one of the `@_fixedAcrossIterations` blocks, so #151's row caching is unaffected.

**Loop mode is enough.** Loop mode charges the amount but the LP does not see the marginal rate, so in principle a conversion schedule is not steered away from the phase-in range. I checked whether that matters. On NY couples (born 1964, $1.5M and $2.5M tax-deferred; plain NY and Yonkers; Medicare off and SS taxability pinned so the LP is exact), I put a grid of Roth-conversion caps from 0 to $300k a year against the uncapped loop solution. No cap beat it, in four out of four cases, and the recapture actually paid over the whole plan was $81 to $6.4k in today's dollars. An exact MILP would need a gate binary per tier per year, because of the notch above, for very little. That evidence covers one lever (the cap), not every year-by-year schedule.

Our implementation is commit `fe7fba3` on `fmateoc/Owl`, branch `claude/inspiring-rubin-f0a0p9`, with tests that pin the worksheet constants, the worksheet-1 hand case, the notch, continuity in AGI, monotonicity, and plan-level agreement with the worksheet tax. It sits on our SC-loop refactor and on a per-year state layer that upstream does not have, so it will not apply as is; the steps above are the stock-`dev` version.
