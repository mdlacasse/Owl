# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Owl** (Optimal Wealth Lab) is a retirement financial planning tool that uses linear programming (LP) optimization to model US retirement scenarios. It handles federal tax laws, Medicare premiums, Social Security rules, Roth conversion strategies, and more. Users can run historical backtests, Monte Carlo simulations, or fixed-rate analyses.

The tool can be used as a Python library, a CLI (`owlcli`), or via a Streamlit web UI.

## Commands

### Testing
```bash
pytest                                          # Run all tests
pytest tests/test_plan_edge_cases.py            # Run a single test file
pytest tests/test_plan_edge_cases.py::test_foo  # Run a single test function
pytest -m toml                                  # Run only TOML case tests
pytest -v --cov=owlplanner                      # With coverage
```

### Linting
```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --exit-zero --max-complexity=30 --max-line-length=120 --statistics
```

### Running the Streamlit UI
```bash
streamlit run ui/main.py
```

### Running the CLI
```bash
owlcli list examples/                   # List available cases
owlcli run examples/Case_jack+jill.toml # Run a case
```

### Build / Documentation
```bash
python -m build                         # Build distribution
make rate-model-docs                    # Regenerate RATE_MODELS.md
```

## Architecture

### Package Structure

The source package is at `src/owlplanner/`. Key modules:

- **`plan.py`** — The core optimization engine. Constructs and solves an LP/MIP using PuLP with HiGHS (default) or MOSEK. This is the largest and most complex file.
- **`abcapi.py`** — Solver-neutral constraint-building API used by `plan.py`.
- **`tax2026.py`** — Federal tax calculations (brackets, LTCG, NII, Medicare IRMAA).
- **`socialsecurity.py`** — Social Security benefit modeling.
- **`debts.py`** / **`fixedassets.py`** — Debt and fixed-income asset modeling.
- **`timelists.py`** — Time-indexed data structures used throughout.
- **`rates.py`** + **`data/rates.csv`** — Historical market return data (1928–2025).

### Configuration System (`src/owlplanner/config/`)

- **`schema.py`** — Pydantic v2 models defining the full case schema (validated with `extra="allow"` for extensibility).
- **`toml_io.py`** — TOML file loading/saving. Case files are `.toml` (see `examples/`).
- **`plan_bridge.py`** — Bidirectional bridge between the Pydantic config and a `Plan` object.
- **`ui_bridge.py`** — Bidirectional bridge between the Pydantic config and Streamlit session state.
- **`legacy.py`** — Handles backward compatibility for old TOML formats.

### Rate Models (`src/owlplanner/rate_models/`)

A pluggable system for generating return series:
- **`base.py`** — Abstract `BaseRateModel` interface all models must implement.
- **`builtin.py`** / **`_builtin_impl.py`** — Built-in rate methods (historical, fixed, etc.).
- **`bootstrap_sor.py`** — Sequence-of-Returns (SOR) bootstrap for Monte Carlo.
- **`dataframe.py`** — Custom model backed by a user-supplied DataFrame.
- **`loader.py`** — Dynamic plugin discovery (scans for subclasses of `BaseRateModel` at runtime).

Custom rate model plugins are discoverable if they subclass `BaseRateModel` and are importable. See `docs/plugable-rates.md`.

### Streamlit UI (`ui/`)

- **`main.py`** — App entry point; defines multi-page navigation.
- **`owlbridge.py`** — The main UI↔backend interface; calls into `plan.py` and the config bridges.
- **`sskeys.py`** — All Streamlit session state key definitions and accessors. Centralizes `st.session_state` usage.
- Page files (e.g., `Graphs.py`, `Worksheets.py`) correspond directly to sidebar navigation items.

### Visualization (`src/owlplanner/plotting/`)

Factory pattern with two backends:
- `plotly_backend.py` — Interactive plots (used in Streamlit UI).
- `matplotlib_backend.py` — Static plots (used in CLI/notebooks).

### CLI (`src/owlplanner/cli/`)

Click-based CLI registered as the `owlcli` entry point. Commands: `list`, `run`.

### Public API

```python
from owlplanner import Plan, clone, readConfig, saveConfig, getRatesDistributions
```

`Plan` is the main class. Users configure it programmatically or via TOML, then call `.solve()`.

## Key Conventions

- **Python 3.10+ required**. CI tests against 3.10, 3.13, and 3.14.
- **Line length**: 120 characters (configured in `.flake8`).
- **Test markers**: Use `@pytest.mark.toml` for tests that load example TOML files.
- **`pytest.ini`** sets `pythonpath = . src ui`, so both `owlplanner` and `ui` modules are importable in tests without installation.
- Commits tagged `[no ci]` skip the GitHub Actions pipeline.
- MOSEK is an optional commercial solver; HiGHS (via `highspy`) is the default free solver.
