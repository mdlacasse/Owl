# Year-End Update Checklist

This document describes the steps required when advancing Owl to a new tax year (e.g., from 2026 to 2027).

---

## Background

Most of the codebase dynamically computes the current year via `date.today().year`, so it adapts automatically. The items below are the exceptions — places where a year is hardcoded and must be updated manually.

The test suite is frozen to a reference year (currently **2026**) via `tests/conftest.py`, so tests will not break just because the calendar year advances. The steps below are only needed when you deliberately want to roll the project forward to a new year.

---

## Checklist

### 1. Update the frozen test year — `tests/conftest.py`

Change `_FixedDate._fixed` to January 1 of the new year:

```python
# Before:
_fixed = _REAL_DATE(2026, 1, 1)

# After:
_fixed = _REAL_DATE(2027, 1, 1)
```

---

### 2. Update birth years in example TOML files — `examples/*.toml`

Increment every `date_of_birth` year by **+1** in each case file.

Files to update:
- `Case_jack+jill.toml`
- `Case_jill+jack.toml` (if present)
- `Case_joe.toml`
- `Case_john+sally.toml`
- `Case_jon+jane.toml`
- `Case_alex+jamie.toml`
- `Case_kim+sam-spending.toml`
- `Case_kim+sam-bequest.toml`

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

### 3. Update expected objective values — `tests/test_toml_cases.py`

After changing the frozen year and birth years, re-run the TOML reproducibility test to get
the new solver outputs, then update `EXPECTED_OBJECTIVE_VALUES`:

```bash
pytest tests/test_toml_cases.py -v
```

Update the `net_spending_basis` and `bequest` values for each case on both the `darwin`
and `win32/linux` branches.

---

### 4. Update the tax module — `src/owlplanner/tax2026.py`

If tax brackets, Medicare IRMAA thresholds, or other IRS values change for the new year:

1. Update the constants inside `tax2026.py` to reflect the new year's values.
2. Rename the file to `taxYYYY.py` (e.g., `tax2027.py`).
3. Update all imports:

```bash
grep -r "tax2026" src/ tests/ ui/
```

Key values to verify against IRS/CMS announcements:
- Federal income tax brackets and standard deductions
- Long-term capital gains thresholds
- Medicare Part B base premium and IRMAA brackets
- Net Investment Income Tax threshold
- OBBBA expiration year (if applicable)

---

### 5. Update hardcoded year arrays in test data (optional / cosmetic)

These tests use year arrays like `[2024, 2025, 2026]` as time-list data. They still pass
after the year rolls over (the data is treated as historical), but updating them keeps the
test data feeling "current":

- `tests/test_timelists.py` — year columns in HFP DataFrames
- `tests/test_timelists_coverage.py` — year columns in time-list test fixtures
- `tests/test_debts.py` — `yod` (year-of-debt) values

---

### 6. Run the full test suite

```bash
pytest
```

All tests must pass before committing.

---

### 7. Smoke-test an example case

```bash
owlcli run examples/Case_jack+jill.toml
```

Verify the plan solves and the output looks reasonable.

---

## Summary table

| Step | File(s) | Required? |
|------|---------|-----------|
| Freeze year | `tests/conftest.py` | **Yes** |
| Birth years | `examples/*.toml` | **Yes** |
| Expected values | `tests/test_toml_cases.py` | **Yes** |
| Tax module | `src/owlplanner/tax2026.py` | Yes, if IRS values changed |
| Year arrays in tests | `tests/test_timelists*.py`, `test_debts.py` | Optional (cosmetic) |
