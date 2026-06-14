# OWLCLI — Owl (*Optimal Wealth Lab*) Command Line Interface

`owlcli` is the command-line interface for Owl. It can list, run, and compare
retirement planning scenarios directly from the terminal — and it doubles as an
**MCP server** that exposes all functionality to AI assistants such as Claude Desktop
or Claude Code.

## Installation

`owlcli` is installed with the `owlplanner` package:

```bash
pip install owlplanner      # or: uv add owlplanner
```

---

## Commands

### `list` — enumerate case files

```bash
owlcli list examples/
```

Lists all `.toml` case files in a directory with their plan names and whether
the associated Household Financial Profile (HFP) Excel file exists.

```
FILE                           PLAN NAME             TIME LISTS FILE
--------------------------------------------------------------------------------
Case_jack+jill                 jack+jill             ✓HFP_jack+jill.xlsx
Case_joe                       joe                   ✓HFP_joe.xlsx
Case_kim+sam-spending          kim+sam-spending      ✓HFP_kim+sam.xlsx
```

---

### `explain` — describe a case without solving

```bash
owlcli explain examples/Case_jack+jill.toml
owlcli explain examples/Case_jack+jill.toml --set basic_info.state=CA
```

Loads and validates the TOML file, then prints a JSON document describing the
scenario: individuals, time horizon, account balances, Social Security and
pension income, rate method, objective, and solver options. No LP solve — returns
in under a second.

---

### `list-rates` — enumerate rate models

```bash
owlcli list-rates
owlcli list-rates --category stochastic
```

Prints a JSON document listing every registered return model with its
description, category (`single`, `deterministic`, `stochastic`, `dataframe`),
required and optional parameters, and legacy aliases.

---

### `run` — solve a case

```bash
owlcli run examples/Case_jack+jill.toml
owlcli run examples/Case_jack+jill.toml --output-format json
owlcli run examples/Case_jack+jill.toml --set basic_info.state=TX --set solver_options.bequest=500
```

Loads, solves, and writes results.

- Default: writes an Excel workbook (`<stem>_results.xlsx`).
- `--output-format json`: prints a structured JSON document to stdout instead
  (solver diagnostics go to stderr).

#### Solver flags

| Flag | Description |
|------|-------------|
| `--solver` | `default`, `HiGHS`, or `MOSEK` |
| `--max-time` | Solver time limit in seconds |
| `--gap` | MIP relative gap tolerance (e.g. `1e-4`) |
| `--verbose` / `--no-verbose` | Solver verbosity |
| `--seed` | Random seed for stochastic rate methods |
| `--solver-opt KEY=VALUE` | Override any solver option (repeatable) |
| `--help-solver-options` | List all solver options and exit |

#### `--set` overrides

Override any TOML parameter before solving without editing the file:

```bash
owlcli run Case.toml --set basic_info.state=MN
owlcli run Case.toml --set fixed_income.social_security_ages=[70,68]
owlcli run Case.toml --set solver_options.withSSAges=optimize --set optimization_parameters.objective=maxBequest
```

Values are JSON-parsed (`true`, `42`, `[70,68]`) or kept as strings.

---

### `compare` — run base vs. variant

```bash
owlcli compare examples/Case_jack+jill.toml --set basic_info.state=MN
owlcli compare examples/Case_jack+jill.toml \
    --set fixed_income.social_security_ages=[70,70] \
    --set optimization_parameters.objective=maxBequest
```

Solves the original case and a variant defined by `--set`, then prints a JSON
document with base metrics, variant metrics, the numeric delta, and percent
changes for key decision metrics. All solver flags (`--solver`, `--max-time`,
etc.) apply to both runs.

---

### `serve` — start the MCP server

```bash
owlcli serve
```

Starts an MCP (Model Context Protocol) server over stdio, exposing all five
tools to any compatible AI client. See [`info/mcp.md`](../../../info/mcp.md)
for setup instructions.

---

## Common patterns

```bash
# Explore available cases
owlcli list examples/

# Quickly inspect a case before running
owlcli explain examples/Case_jack+jill.toml

# What rate models are available for Monte Carlo?
owlcli list-rates --category stochastic

# Run and capture results as JSON (e.g. for scripting)
owlcli run examples/Case_jack+jill.toml --output-format json | jq .summary

# How much does delaying SS to 70 change spending?
owlcli compare examples/Case_jack+jill.toml \
    --set fixed_income.social_security_ages=[70,70] \
    | jq '{spending_delta: .delta.spending_basis, pct: .pct_change.spending_basis}'
```
