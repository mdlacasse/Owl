# OWLCLI - a Command Line Interface for Owl

`owlcli` is a command line interface tool to streamline the listing, running and experimenting with Owl case files outside the streamlit interface.

## Installation

`owlcli` is installed with the owlplanner module. Once OWLPLANNER is installed, `owlcli` can be run from the command line. 

## Usage

At present, OWLCLI provides two commands: `list` and `run`.

```bash
❯ owlcli list
```

This command will list all the available TOML case files in the current directory.

To list all the available OWL case files in the `examples` directory, relative to the current directory, use:

```bash
❯ owlcli list examples
FILE                           CASE NAME             HOUSEHOLD FINANCIAL PROFILE
--------------------------------------------------------------------------------
Case_jack+jill                 jack+jill             ✓HFP_jack+jill.xlsx
Case_joe                       joe                   ✓HFP_joe.xlsx
Case_john+sally                john+sally            ✓HFP_john+sally.xlsx
Case_jon+jane                  Jon+Jane              ✗HFP_jon+jane.xslx
Case_kim+sam-bequest           kim+sam-bequest       ✓HFP_kim+sam.xlsx
Case_kim+sam-spending          kim+sam-spending      ✓HFP_kim+sam.xlsx
case_drawdowncalc-comparison-1 drawdowncalc-com...   ✗None
```

The listing shows the file name, case name, and the Household Financial Profile associated with each case.

✓ indicates that the Household Financial Profile listed in the Owl case file exists.
✗ indicates that a Household Financial Profile file was not found.
Case files with HFP set to `None` have no HFP (e.g., test cases). *edited values* can appear when a case was edited in the UI; download the HFP workbook for reproducibility.


To run an Owl case file, use the `run` command followed by the case file name:

```bash
❯ owlcli run examples/Case_kim+sam-spending
Case status: solved
Results saved to: examples/Case_kim+sam-spending_results.xlsx
```

This example runs the `Case_kim+sam-spending` case file located in the `examples` directory. The results of the run are saved to a new Excel file with `_results.xlsx` appended to the original case file name.  A copy of the input Owl case file is saved as the new first tab in the Excel file.

### Solver options from the command line

You can override solver options without editing the TOML file:

```bash
owlcli run examples/Case_joe.toml --solver HiGHS --max-time 600 --verbose
owlcli run examples/Case_kim+sam-spending.toml --gap 1e-3
```

| Option | Description |
|--------|-------------|
| `--solver` | Solver to use: `default`, `HiGHS`, or `MOSEK` |
| `--max-time` | Solver time limit in seconds |
| `--gap` | MIP relative gap tolerance |
| `--verbose` | Enable solver verbosity |
| `--solver-opt KEY=VALUE` | Override any solver option (repeat for multiple) |

Use `--solver-opt` for options not covered by the flags above:

```bash
owlcli run Case.toml --solver-opt maxRothConversion=50 --solver-opt withMedicare=loop
```

Command-line values override settings in the TOML `[solver_options]` section. Use `--help-solver-options` to list all options (parsed from PARAMETERS.md).

