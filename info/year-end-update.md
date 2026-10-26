<!--
Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
SPDX-License-Identifier: CC-BY-NC-SA-4.0
This documentation is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0; see LICENSE-docs in the repository root.
-->

# Year-End Update Checklist

This document describes the steps required when advancing Owl to a new tax year (e.g., from 2026 to 2027).

---

## Background

Most of the codebase dynamically computes the current year via `date.today().year`, so it adapts automatically. The items below are the exceptions — places where a year is hardcoded and must be updated manually.

### How the test freeze works

`tests/conftest.py` contains a session-scoped autouse fixture (`freeze_year`) that runs
before any test executes. It scans `sys.modules` for every imported module whose `date`
attribute is `datetime.date` — covering both `owlplanner.*` source modules and the test
files themselves — and replaces it with a subclass whose `today()` always returns a fixed
date (`_FROZEN_DATE`, currently `date(2026, 1, 1)`).

Because all call sites use `date.today().year`, this single patch makes every plan
construction, tax calculation, and time-list operation behave as if the current year is
**2026**, regardless of when the tests actually run.

Two design decisions complement the freeze:

- **`tests/plan/test_repro.py`** computes birth years as `thisyear - age` (e.g., `thisyear - 62`
  for Jack) with a fixed life expectancy. This keeps the individuals at the same age each
  year, so Social Security and Medicare start dates remain the same number of years into
  the plan — the scenario is identical across calendar years.

- **`tests/plan/test_regressions.py`** uses the same age-relative pattern
  (`yobs = [thisyear - topAge + ny]`), so it was already year-agnostic.

The net result: **tests never break at year rollover**. The steps below are only needed
when you deliberately want to roll the project forward to a new year.

---

## Checklist

### 1. Update the frozen test year — `tests/conftest.py`

Change `_FROZEN_DATE` to January 1 of the new year:

```python
# Before:
_FROZEN_DATE = _REAL_DATE(2026, 1, 1)

# After:
_FROZEN_DATE = _REAL_DATE(2027, 1, 1)
```

---

### 2. Update birth years in example TOML files — `examples/*.toml`

Increment every `date_of_birth` year by **+1** in each case file. Every `examples/Case_*.toml`
file has one, so update them all:

```bash
grep -l "date_of_birth" examples/*.toml
```

Example:
```toml
# Before:
date_of_birth = ["1963-01-15", "1966-03-20"]

# After:
date_of_birth = ["1964-01-15", "1967-03-20"]
```

> **Note:** `start_date` and `startRothConversions` values in these files do **not** need updating.
> The year in `start_date` is ignored by the parser (only month and day are used).
> `startRothConversions` values in the past are automatically clamped to the current year
> by `config/toml_io.py`.

---

### 3. Update the year-keyed tax and benefit data

Owl's federal tables are keyed by year inside a single module, `src/owlplanner/tax_federal.py`;
the file keeps its name from year to year. Add the new year's entry to each table (do not
replace the previous one, which past-year lookups still use) and update the values that are
stored for one year only. Verify against IRS, CMS, SSA, and HHS announcements:

- **`src/owlplanner/tax_federal.py`**
  - Federal income tax brackets and standard deductions
  - Long-term capital gains thresholds and the Net Investment Income Tax threshold
  - Medicare Part B base premium, Part D IRMAA amounts, and IRMAA brackets
  - Contribution limits keyed by year: `electiveDeferralLimit`, `electiveDeferralCatchup50`,
    `electiveDeferralCatchup60to63`, `iraContributionLimit`, `iraCatchup50`, `hsaContributionLimit`,
    and `qcdLimit`. Years past the last entry reuse it (`_limit_for_year`); `qcdLimit` is
    grown by `QCD_LIMIT_INFLATION` instead.
  - ACA: the federal poverty line table (`_ACA_FPL`) and the applicable-percentage tables
    (`_ACA_CONTRIB_PCT_YYYY`, `_ACA_CONTRIB_INITIAL_YYYY`, and their entry in the year table)
  - Payroll tax: the Social Security wage base `payrollWageBase` (one year's value)
  - OBBBA expiration year (if applicable)
- **`src/owlplanner/socialsecurity.py`** — the earnings test's exempt amounts (`_EXEMPT_TABLE`)
- **`src/owlplanner/data/taxes_state.toml`** — state brackets, deductions, and exemptions
  (labelled with its basis year in the header)

---

### 4. Add last year's market returns — `src/owlplanner/data/rates.csv`

Append the completed year's row (`year`, `S&P 500`, `Bonds Baa`, `real estate`, `T-Bills`,
`T-Notes`, `Inflation`, in percent), then raise `TO` in `src/owlplanner/rates.py`
(`FROM, TO = 1928, 2025`) to that year: it is set by hand, not read from the file.

---

### 5. Update expected objective values — `tests/plan/test_toml_cases.py`

After changing the frozen year, the birth years, and the data, re-run the TOML
reproducibility test to get the new solver outputs, then update `EXPECTED_OBJECTIVE_VALUES`:

```bash
uv run pytest tests/plan/test_toml_cases.py -v
```

Update the `net_spending_basis` and `bequest` values of each case in the table. A single
table serves all platforms and both solvers (no case needs a MOSEK override any more), so
re-run it with `OWL_TEST_SOLVER=mosek` as well to confirm the two still agree.

---

### 6. Update year-specific UI text (cosmetic)

- `ui/Welcome.py` — "current US federal and state tax rules (including 2026)"
- `ui/Rates.py` — the help text linking the year's Morningstar forecast roundup

---

### 7. Run the full test suite

```bash
make tests
```

This runs the suite under both solvers (MOSEK, then HiGHS). All tests must pass before committing.

---

### 8. Smoke-test an example case

```bash
uv run owlcli run examples/Case_jack+jill.toml
```

Verify the plan solves and the output looks reasonable.

---

## Summary table

| Step | File(s) | Required? |
|------|---------|-----------|
| Freeze year | `tests/conftest.py` | **Yes** |
| Birth years | `examples/Case_*.toml` | **Yes** |
| Tax and benefit data | `src/owlplanner/tax_federal.py`, `socialsecurity.py`, `data/taxes_state.toml` | Yes, if values changed |
| Market returns | `src/owlplanner/data/rates.csv`, `src/owlplanner/rates.py` | **Yes** |
| Expected values | `tests/plan/test_toml_cases.py` | **Yes** |
| UI text | `ui/Welcome.py`, `ui/Rates.py` | Optional (cosmetic) |
