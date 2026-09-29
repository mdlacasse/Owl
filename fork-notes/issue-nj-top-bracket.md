# Draft upstream issue (mdlacasse/Owl): NJ top bracket taxed at 0% for Single filers and survivors

**Title:** State tax: top bracket lost when Single and MFJ schedules have different lengths (NJ income above $1M taxed at 0%)

---

`st_taxParams` pads the shorter of the Single and MFJ bracket lists so both have `N_st` entries. The padding entry repeats the last lower bound with a 0% rate:

```python
def _pad(brackets, target_n):
    while len(brackets) < target_n:
        brackets.append([brackets[-1][0], 0.0])
```

Widths come from consecutive lower bounds, so the real top bracket gets width 0 and the 0% padding entry gets the open-ended sentinel width. Any income above the top threshold then falls into a 0% bracket.

NJ is the only state affected today: Single has 7 brackets and MFJ has 8, so `N_st = 8` and the Single schedule is padded. It applies to a single filer, and to the survivor of a couple after `n_d`, above $1,000,000 of NJ taxable income.

**Repro** (on `fb539f4`):

```python
import numpy as np
from owlplanner import tax_state

res = tax_state.st_taxParams("NJ", 1, 30, 30, np.ones(31), [1960], mobs=[1])
N_st, theta, delta = res[0], res[1], res[2]
for t in range(N_st):
    print(t, theta[t, 0], delta[t, 0])
```

```
  bracket 5: rate 8.9700%   width      500,000
  bracket 6: rate 10.7500%  width            0
  bracket 7: rate 0.0000%   width    5,000,000
```

Tax from filling those brackets in order, against the TOML schedule:

| NJ taxable income | LP brackets | TOML schedule |
|---:|---:|---:|
| 900,000 | 65,604 | 65,604 |
| 1,500,000 | 74,574 | 128,324 |
| 3,000,000 | 74,574 | 289,574 |

Above $1M the LP sees no NJ tax at the margin, both in the tax charged and in the incentives the optimizer responds to.

**Suggested fix:** pad with zero-width brackets at the top rate, after the open-ended bracket keeps its sentinel width:

```python
def _padded_rates_and_widths(brackets, n_st):
    rates, widths = _brackets_to_rates_and_widths(brackets, _LAST_BRACKET_SENTINEL)
    extra = n_st - len(rates)
    return np.append(rates, np.full(extra, rates[-1])), np.append(widths, np.zeros(extra))
```

Repeating the top rate (rather than 0%) keeps the padding harmless even if a solver put income there. We have this with two tests in our fork (Single filer at $1.5M, and the survivor years after `n_d`); happy to open a PR against `dev` if useful.
