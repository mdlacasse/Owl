# Owl Release Notes

---

## Version 2026.02.23

### Social Security accuracy improvements
- **Dynamic SS taxability fraction**: `Psi_n` (the fraction of SS benefits subject to
  federal income tax) is now computed each self-consistent-loop iteration using the IRS
  provisional income formula instead of a fixed 85%. Thresholds follow IRS rules frozen
  since 1983/1994 — MFJ: 0% below $32k PI, up to 50% to $44k, 85% above; Single: $25k/$34k.
  A 30% damping blend ensures SC-loop convergence. Retirees with lower income now get a
  more accurate (lower) tax on SS benefits, improving Roth conversion and spending results.
- **`tax_fraction` override**: `setSocialSecurity()` accepts an optional `tax_fraction`
  parameter to pin `Psi_n` to a fixed value (0.0 / 0.5 / 0.85), bypassing the dynamic
  computation. Also available in the TOML schema as `social_security_tax_fraction`.
- **Corrected FRA table**: `getFRAs()` now returns the correct Full Retirement Age for
  birth years 1938–1942 (65+2/12 to 65+10/12 per the SSA table), instead of the
  incorrect 66.

### Social Security trim
- **Remove `trim_year` fallback**: A TOML config with `social_security_trim_pct > 0`
  but no `social_security_trim_year` now raises an error instead of silently defaulting
  to 10 years from now. Supply both fields together.
- **Better UI default**: The "Starting year" field for SS benefit reduction now defaults
  to 2033 (the SSA Trustees Report projection for OASI trust-fund exhaustion) instead of
  an arbitrary `current year + 10`.
- **Disabled year widget**: The "Starting year" input is now greyed out in the UI when
  the reduction percentage is 0.

### Tests
- TOML reproducibility tests now force HiGHS as the solver for consistent results across
  environments (eliminates MOSEK vs. HiGHS non-determinism in the full test suite).
- Updated regression baselines to reflect the corrected SS taxation calculations.

---

## Version 2026.02.20

### UI
- **Create Case redesign**: Replace sentinel-based selectbox entries (`New Case...`, `Upload Case File...`) with explicit widgets. When no case is selected, the page shows three columns side by side: create from scratch, upload a TOML case file, and load an example. When a case is already active, a collapsible expander provides the same options for adding more cases.
- **Inline HFP uploader**: After a case is created, an HFP upload widget appears directly on the Create Case page (when no HFP has been loaded yet), allowing a full case setup without leaving the page.
- **Streamlit compatibility**: Remove version pin (`== 1.52.2`) and `altair < 5` restriction from `requirements.txt`; manage selectbox value entirely via session state to avoid the newer Streamlit "default value + Session State API" conflict.

---

## Version 2026.02.19

### Rate models
- **BuiltinRateModel decomposition**: Replace single dispatcher with 8 concrete `BaseRateModel` subclasses (Default, Optimistic, Conservative, User, Historical, HistoricalAverage, Stochastic, Histochastic), each with its own metadata and `generate()`. `BuiltinRateModel` shim preserves backward compatibility.
- **Stochastic UI fix**: Builtin rate model accepts config-style parameter names (`standard_deviations`, `correlations`) in addition to API names (`stdev`, `corr`). Fixes "Rate model 'builtin' requires parameter 'stdev'" when stochastic rates are selected in the UI. Name remap moved into `BuiltinRateModel.__init__`.
- **getRatesDistributions** (issue #92): Standardize to return percent by default; add optional `df=` parameter to accept user-supplied DataFrame (e.g. from DataFrameRateModel) for distribution statistics.
- **DataFrame rate model** (issue #92): Rename TNotes/TBills to T-Notes/T-Bills in CSV and `REQUIRED_RATE_COLUMNS`; add `in_percent` parameter to replace heuristic; align `RATE_DISPLAY_NAMES_SHORT` with column names for direct workbook→dataframe use; enforce bool type on `in_percent`.
- **Rates UI**: Rename label 'fixed' to 'constant' in rates selection (radio, tooltips, section labels, `rateType` comparisons).

### Social Security
- **SS trim**: Add trim percent and year to SS benefits (reduction from a given year onward). Config, schema, UI bridge, and Fixed Income page updated.
- Fix SS trim params not properly saving from UI.

### Code maintainability and reduction
- **Config UI bridge**: Add `_get_ui` helper to replace repeated `uidic.get(key, default) or default` patterns (~30 occurrences).
- **Rate display constants**: Add `RATE_DISPLAY_NAMES` and `RATE_DISPLAY_NAMES_SHORT` in `rate_models/constants.py`; use in plotting backends and plan.
- **Plotly backend**: Extract legend/layout dicts to module constants (`_LEGEND_TOP`, `_LEGEND_BOTTOM`, `_LEGEND_BOTTOM_REVERSED`).
- **Matplotlib backend**: Refactor `plot_rates_distributions` to use a loop over rate names/data.
- Net ~90 lines removed.

### UI
- Rename "copy case" to "copy parameters".
- Make asset names consistent everywhere (issue #92).
- Change worksheets output to % (issue #92 partial).

### Documentation and notebooks
- Update documentation and doc alignment.
- Fix broken notebooks.

### Code quality
- Flake8: fix E402 in `matplotlib_backend.py` (imports after `os.environ` for Jupyter); general lint fixes.

---

## Version 2026.02.17

### Rates API consolidation
- **Single API**: Consolidate `Rates.setMethod` and `Plan.setRates` into one API. Use `Plan.setRates()` as the sole entry point.
- **Remove Rates class**: Deprecate and remove the legacy `Rates` class from `rates.py`. Rate generation logic moved to `BuiltinRateModel` and `rate_models._builtin_impl`.
- **New `rate_models/_builtin_impl.py`**: Helper functions for built-in rate methods (fixed, historical, stochastic) used by `BuiltinRateModel`.
- **Canonical fixed rates**: Single source of truth in `rates.py`. Add `get_fixed_rates_decimal()`; remove duplicate definitions from `_builtin_impl`.

### Rate model constants
- **`rate_models/constants.py`**: Centralize method name sets (e.g. `FIXED_PRESET_METHODS`, `HISTORICAL_RANGE_METHODS`, `RATE_METHODS_NO_REGEN`, `STOCHASTIC_METHODS`) for use across plan, config, UI, and plotting.
- Remove `CONSTANT_RATE_METHODS` and `RATE_METHODS_NO_REGEN` from `rates.py` (now in rate_models).

### Documentation
- Rename `LegacyRateModel` to `BasicRateModel` in plugable-rates docs.
- Update plugable-rates Step 2 to reflect BuiltinRateModel architecture.

### Tests
- Migrate `test_rates.py` from `Rates.setMethod` to `BuiltinRateModel` and `Plan.setRates`.

---

## Version 2026.02.16

### Rates
- **Pluggable rate model architecture**: New `owlplanner.rate_models` package with loader, base class, and pluggable model resolution.
  - Basic methods (default, optimistic, conservative, user, historical, historical average, stochastic, histochastic) wrapped via `BasicRateModel`.
  - Built-in `dataframe` and `bootstrap_sor` models.
  - External plugin support via `method_file=` in `setRates`.
- **DataFrame rate method** (issue #84): Supply rates from a pandas DataFrame with columns S&P 500, Bonds Baa, TNotes, Inflation; supports year-based or sequential mode with optional offset.
- **Remove mean/means aliases**: Drop deprecated rate method aliases; use `historical average` only.

### Constraints and optimization
- **Safety net**: Add constraint for minimum taxable account balance per individual; configurable per spouse, applies from year 2 onward.
- Add caption on infeasibility when safety net exceeds bequest target.
- Enhance optimization page of UI.

### Configuration and UI
- Rename contributions -> Household Financial Profile (HFP) for consistency.
- Discovery UI helpers for rate models and metadata.
- Tooltip and wording improvements; fix int/float conversion for fixed income age.
- Fix `startRothConversions` in examples; clamp year when in the past.
- Highlight create-on-copy in UI.

### Documentation and notebooks
- Add README and docs for pluggable rate models and SOR (sequence-of-returns) models.
- Update template notebook: fix outdated rate method names (`average` -> `historical average`, `fixed` -> `user`), remove obsolete "means" mention.

### Code quality
- Flake8 fixes across scripts (cumulative_returns_analysis, roth_case_study, time_time_correlation, etc.) and tests.
- Remove undefined `sc_damping` from roth_case_study; fix type hints and line length.

---

## Version 2026.02.13
- Add capability to include user-defined tokens in configuration file

---

## Version 2026.02.12
- Improve integration wih MOSEK 

---

## Version 2026.02.06
### Multiple scenarios
- Add capabilities for running augmented historical range.
- Add log scale option to hostograms

---

## Version 2026.02.04

### Optimization
- Reduce default gap for MILP optimization with withMedicare is optimized.

---

## Version 2026.02.02

### Rates
- **Rate sequence modifiers** (issue #77): Add reverse and roll options for varying rate methods.
  - New `reverse_sequence` (boolean) and `roll_sequence` (integer) in `setRates`, config, and TOML.
  - UI: Reverse toggle and Roll (years) in Rates Selection -> Advanced Options.
  - Historical Range: same reverse/roll options in Advanced Options; `runHistoricalRange` accepts `reverse` and `roll` and applies them to each year’s historical sequence.
  - Ignored for fixed/constant rate methods (with warning). Documented in PARAMETERS.md and Documentation.

### Landing page and Quick Start
- Update landing page (layout, link to repo, instructions for beginners).
- Add short description of what optimization is performed.
- Fix Quick Start line length (flake8).

### UI and examples
- Highlight current year in timelist and in worksheets (this year’s accounts).
- Fix case status incorrectly set to modified when visiting Create Case page (getDate/sskeys).
- Fix Joe’s example missing `withMedicare` option.
- Fix Social Security URL on Fixed Income page.

### Documentation and parameters
- Sync Documentation.py with UI: TOC (Parameters Reference, Quick Start icon), Create Case labels, Output Files button names, Roth conversion toggle wording, Resources link, case file naming.
- Update owl.tex description.
- Document lexicographic weight and self-consistent loop default tolerance in docs.
- PARAMETERS.md: document `reverse_sequence` and `roll_sequence`.

---

## Version 2026.01.28
- Recoded Medicare optimization algorithm for SOS1 formulation.
- Updated documents and parameters.
- Added lexicographic weight epsilon in solver options.

## Version 2026.01.26
- Updated Jupyter notebooks.
- Improved logging.

## Version 2026.01.21
- Move "optimize" Medicare option to advanced section.
- Add solver option to disable surpluses in late years.
- Rename XOR → AMO as correct term.

## Version 2026.01.20
- Fix negative taxable gains in years of negative returns
- Fix limits in UI not allowing negative rates
- Add more control hooks on solver (xor, maxIter)
- Clarify docs for reference year of fixed assets
- Improve logging while reading fixed assets and debts
- Bring most hard-coded constants to top of file
- Enable Python 3.14 in GH CI
- Investigate tests on GH failing due to different linear solver
- Disallow conversions and surplus in last 2 years
- Connect MOSEK logger with verbose keyword.

## Version 2026.01.17
- Add more parameters to control solver
- Add capability to specify years from last in fixed assets
- Document negative/zero fixed-asset disposition years and update UI tooltip
- Add tests for negative/zero fixed-asset disposition years
- Improved default values for broader case applicability.

## Version 2026.01.16
- Extend longevity table to 120 and add safety checks.
- Add 15% of untaxed SS back to MAGI.
- Update documentation (TeX).
- Adjust reproducibility tests.

## Version 2026.01.15
- Fix LTCG tax computation (self-consistent stacking accuracy).
- Add non-taxable portion of SS to MAGI.
- Fix cash flow to include all fixed-asset proceeds.
- Apply max Roth conversion cap across both spouses.
- Clarify SS tax fraction vs LTCG effective rate.
- Align documentation and reproducibility baselines with code.

## Version 2026.01.12
- Merge binary exclusion constraints for both spouses (one set per year instead of per individual)
  - Update paper to reflect binary variables $z_{nz}$ shared across both spouses
  - Reduce binary variable count from $4N_iN_n$ to $4N_n$ for married couples
- Improve loop detection for oscillatory solutions
- Expose tolerance and bigM parameters for solver experiments
- Add 15-minute time limit for solution
- Fix rare UI condition when starting Upload Case and hopping to Logs
- Change convergence criteria to only consider objective function (not solution vector)
- Split bigM between XOR exclusion constraints and IRMAA Medicare conditions.

## Version 2026.01.08
- Fix dividends being taxed twice on taxable account withdrawals
- Remove int32 normalization of seed (reverted from 2026.01.07)
- Remove unused file-based rates parameters (rateFile, rateSheetName, workbook_file, worksheet_name)
  - Clean up leftover code from deprecated file method for reading rates
  - Remove from plan.py, config.py, owlbridge.py, and Rates_Selection.py
  - Update PARAMETERS.md to remove file method documentation
- Add tip help to case delete operation in UI
- Update paper PDF to reflect change in dividend tax calculation
- Replace duplicate owl.tex and images with symlinks to avoid duplication
- Refactor code in config.py, debts.py, fixedassets.py, and utils.py
- Add tests to increase coverage and harden code.

## Version 2026.01.07
- Normalize seed to fit in signed int32 (issue #59)
- Remove animation
- Update Adamodar rates for 2025
- Make Kim+Sam cases consistent
- Make minor edits in About page.

## Version 2026.01.05
- Migrate examples and TOML configuration to snake_case (closing issue #52)
    - Optimizer still uses camelCase for distinction
- Add reproducibility flag and merge reproducibility branch
- Add year field for Fixed Assets (issue #57)
- Add check on Debts validation
- Fix bug in timelist when missing years
- Fix withMedicare config when no longer Boolean
- Add confirm button to case delete in UI
- Add preliminary file listing TOML parameters (PARAMETERS.md)
- Add script to build container on macOS/Linux
- Fix Streamlit race condition and column conditioning
- Update all cases and repro tests for 2026
- Improve documentation on self-consistent loops and Medicare
- Improve documentation and terminology on fixed assets
- Make Create Case page more consistent
- Update About page to point to AUTHORS file
- Add one-to-many map for HFP-case in examples
- Update kim+sam example for sharing
- Clean license and authorship
- Improve Summary output styling

## Version 2025.12.29
- Integrate loguru logging system with global log and filters
    - Split logger per object
    - Add persistence in TOML file
    - Update logger when case is renamed
    - Use a stack for verbose status
    - Address multiline logs (issue #36)
    - Check case name in first line of log group
- Add id to allow name change and log filtering (issue #36)
- Fix issue #48 caused by past contributions
- Propagate HFP filename to TOML if unedited
- Fix minor HFP filename issues
- Remove hydra-core dependency (pull request #44)
- Simplify CLI, remove hydra dependencies
- Fix SSA issues
- Change word "claiming" to "starting" for SSA
- Add different tool tip for those born on 1st and 2nd
- Improve benefits explanations
- Regenerate efficiency and no-correlation for fixed rates
- Improve error message in tax202x
- Warn on clearing logs for yOBBBA year rebase
- Make OBBBA expiration year idiot-proof
- Fix typo (issue #47)

## Version 2025.12.20
- Implement Debts and Fixed Assets capabilities
    - Mortgages, loans, restricted stocks, etc. and fixed lump-sum annuities can now be modeled
    - Include debts and fixed assets at end of plan in bequest
- Extend Wages and Contributions page, renamed to Household Financial Profile
- Add debt payment and fixed assets bequest reporting to Synopsis
- Improve bequest-constraint logic
- Add constraint on fixed assets
- Fix bug in Debts and Fixed Assets tables
- Include Debts and Fixed Assets in example HFPs
- Improve UI
- Improve integration with ssa.tools

## Version 2025.12.16
- Fix error message when dates are empty in Create_Case
- Add fix to prevent stored TOML age from being out of range
- Rename duplicate to copy
- Fix input error on months
- Prepare for new tax season
- Carry minor fixes from dev version

## Version 2025.12.11
- Add more bubble help messages in Create Case
- Fix bug in rates selection UI
- Remove reliance on GitHub for graphics and example files
- Update UI to use new file locations
- Add new owl.png logo

## Version 2025.12.10
- Add date of birth due to social security rules when birthday on 1st and 2nd
- Modify FRA calculations accordingly
- Add integration to ssa.tools
- Add Dale's help message for date of birth

## Version 2025.12.09
- Improve instructions for developers
- Add link to ssa.tools on Fixed Income page
- Fix bug on max age range for SS when month != 0
- Add table of federal income tax itemized by bracket
- Improve instructions for ssa.tools

## Version 2025.12.05
- Add instructions for obtaining PIA
- Enhance documentation for obtaining PIA
- Add generic reference for PIA calculation
- Fix bug in Fixed Income UI
- Fix error in month input
- Add hint for birth month

## Version 2025.12.03
- Code Social Security to use monthly PIA instead of annual amount
    - Add exact routines for FRA and increase/decrease factors due to claiming age
    - Add exact spousal benefits
- Adjust documentation for Social Security
- Add birth month for more precise calculation on first year of Social Security
- Add month to age for claiming Social Security

### Version 2025.11.29
- Fix Social Security for survivor benefits
- Enhance documentation for SS amounts
- Add caveat on account allocation ratios in documentation
- Fix typo in documentation

## Version 2025.11.09
- Move development status to production/stable in pyproject
- Make version propagate everywhere needed
- Add node limit on MILP to avoid Streamlit server shutdown on memory consumption
- Update documentation and README for clarity
- Update section titles for clarity
- Clarify options for running Owl in README
- Update GitHub star request wording in Quick Start

### Version 2025.11.05
- Mention Owl as Optimal Wealth Lab
- Port to Streamlit 1.50 which breaks many widgets
- Fix UI bugs from port to Streamlit 1.50
- Rework backprojection of assets to beginning of the year
- Improve backprojection when not January 1
- Rework Docker to smaller Alpine image and fix docs
- Clarify instructions for Docker
- Update FI Calc link to use full URL
- Fix tests and error messages
- Fix graph settings
- Make case naming consistent

## Version 2025.07.01
- Add settings option for menu position (top or sidebar) thanks to Streamlit 1.46
    - Default is top menu
- Add Net Investment Income Tax calculations in self-consistent loop
- Add capability to load example Wages and Contributions Excel file from GitHub directly from UI
- Add constraint for 5-year maturation rule on Roth conversions
- Extend Wages and Contributions table 5 years in the past for tracking recent contributions to tax-free accounts and Roth conversions
- Add option in UI to turn off sticky header (useful for mobile or tablet use)
- Add new case file allowing for direct comparison with DrawdownCalc
    - Both versions agree to the dollar, demonstrating perfect agreement in compounding, withdrawals, and federal tax calculations
    - Uses two different approaches: direct matrix encoding vs PuLP high-level language
- Add option to use HiGHS library through PuLP for speed comparison
    - Using HiGHS directly is the fastest option
- Add RELEASE_NOTES file
- Change color scheme in header gradient for visibility
- Remove long-term capital tax rate from options
    - Rate is now automatically calculated in self-consistent loop

