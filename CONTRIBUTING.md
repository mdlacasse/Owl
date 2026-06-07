# Contributing to Owl

Thank you for your interest in contributing to Owl. This document covers the
development workflow: setting up your environment, running tests, linting, and
submitting a pull request.

For installation instructions see [INSTALL.md](INSTALL.md).

---

## Development setup

Create a virtual environment with all runtime and development dependencies
(pytest, pytest-xdist, flake8) in one step:

```shell
uv sync --extra dev
```

To also work with the Jupyter notebooks in `notebooks/`:
```shell
uv sync --extra dev --extra notebooks
```

`uv sync` creates `.venv/` in the project root if it does not already exist.
All subsequent `uv run` commands use that environment automatically.

---

## Running tests

```shell
# Run all tests
uv run pytest

# Run in parallel (recommended before a PR)
uv run pytest -n auto

# Run a single file or test
uv run pytest tests/test_plan_edge_cases.py
uv run pytest tests/test_plan_edge_cases.py::test_foo

# Run only TOML case tests
uv run pytest -m toml

# Run with coverage report
uv run pytest -v --cov=owlplanner
```

### Testing against specific solvers

The default solver is HiGHS. To run the suite against a specific solver, set
`OWL_TEST_SOLVER` before running pytest:

**macOS / Linux:**
```shell
OWL_TEST_SOLVER="HiGHS" uv run pytest -n auto
OWL_TEST_SOLVER="MOSEK" uv run pytest -n auto
```

**Windows (PowerShell):**
```powershell
$env:OWL_TEST_SOLVER="HiGHS" ; uv run pytest -n auto
$env:OWL_TEST_SOLVER="MOSEK" ; uv run pytest -n auto
```

MOSEK requires a separate licence. HiGHS is free and is the default.

---

## Linting

```shell
# Hard errors only (syntax errors, undefined names) — must be clean
uv run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Full style check (warnings only, exit-zero)
uv run flake8 . --exit-zero --max-complexity=30 --max-line-length=120 --statistics
```

Line length limit is **120 characters** (configured in `.flake8`).

---

## Code conventions

- **Python 3.11+** required. CI runs against 3.11, 3.12, and 3.13.
- **Comments**: only add one when the *why* is non-obvious — a hidden constraint,
  a subtle invariant, or a workaround for a specific bug. Don't describe what the
  code does; well-named identifiers already do that.
- **No speculative abstractions**: don't add error handling, fallbacks, or
  generalisations beyond what the task requires.
- **Test markers**: use `@pytest.mark.toml` for tests that load example TOML files.

---

## Commit message conventions

Prefix each commit message with a category tag:

| Tag | When to use |
|-----|-------------|
| `[feat]` | New feature or capability |
| `[fix]` | Bug fix |
| `[docs]` | Documentation only |
| `[test]` | Tests only |
| `[ui]` | Streamlit UI changes |
| `[refactor]` | Code restructuring with no behaviour change |
| `[maint]` | Maintenance: renames, baseline updates, housekeeping |
| `[build]` | Build system, packaging, or dependency changes |
| `[bump]` | Version number update |
| `[lint]` | Code linting |

Append `[no ci]` at the end to skip the CI pipeline (e.g. for documentation-only changes):

```shell
git commit -m "[docs] Update docstring wording [no ci]"
```

---

## Continuous integration

CI runs automatically on every push via GitHub Actions (`.github/workflows/`).
It lints with flake8 and runs the full pytest suite across Python 3.11, 3.12, 3.13, and 3.14.

---

## Submitting a pull request

1. Fork the repository and create a branch from `dev` (not `main`).
2. Make your changes, add or update tests as appropriate.
3. Run the full test suite and linter locally before pushing.
4. Open a PR against the `dev` branch with a clear description of what changed
   and why.

Bug fixes and new features should include at least one test that fails before
the change and passes after.

Changes merged to `dev` are automatically deployed to
[owlplanner-dev.streamlit.app](https://owlplanner-dev.streamlit.app), so you
can verify the live effect without running locally.
