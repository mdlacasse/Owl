# Owl Release Notes

---

## Version 2026.04.21

### Longevity risk in stochastic spending + parallel plan solving

- **Longevity risk** (MC-only, `with_longevity=True`): Each Monte Carlo scenario in
  `runStochasticSpending` can now independently draw ages-at-death from an actuarial mortality
  table, capturing joint market and longevity uncertainty. For couples the last-survivor horizon
  is used per scenario. Draws are seeded independently of the rate RNG for full reproducibility.
- **Five actuarial mortality tables** (`setMortalityTable`): `SSA2025` (default, general US
  population), `RP2014` (pension recipients), `IAM2012` (individual annuity purchasers, longest-
  lived), `VBT2015-NS` (non-smoking life insurance), `VBT2015-SM` (smoking life insurance).
  Sampled via `sample_lifespans(sex, current_age, n, rng, table)` in
  `owlplanner.data.mortality_tables`.
- **`plan.sexes` / `setSexes`**: Biological sex (`"M"`/`"F"`) per individual, required for
  mortality sampling. Defaults to `["F"]` (single) or `["M","F"]` (married).
- **Parallel plan solving** (`runMC`, `runHistoricalRange`, `runStochasticSpending`): Scenarios are
  now solved in parallel using `ThreadPoolExecutor`. HiGHS releases the GIL during solve, enabling
  real multi-core throughput. Worker count auto-sized to available CPUs. All randomness
  pre-generated in the parent thread for determinism independent of thread scheduling.
- **UI — Spending Optimization**: Longevity risk toggle, mortality table selector, and longevity
  seed control added. Summary line now includes the selected mortality table when longevity is on.
  Outcome chart and efficient frontier title reflect active scenario method.
- **Removed aliases**: `stochastic` and `histochastic` rate-method aliases removed; use `gaussian`
  and `histogaussian` (canonical names since v2026.03.05). `default` alias for `trailing-30` retained.
- **UI — Rates**: Random seed control and reproducibility toggle exposed directly in the UI.
- Fix short horizons and added edge tests
- Add spending-to-savings ratio in summaries
- Add savings retention curve over horizon to graphs
- Add Case_bill and test for simple depletion test - document discrepancies
- Fix textbox height in Create_Case to fit description
- Update documentation

---

## Version 2026.04.08

### Stochastic spending optimization + stress-test refactoring

- **`runStochasticSpending`** (new): Collects per-scenario optimal spending bases across historical
  or Monte Carlo scenarios, then solves a stochastic recourse LP to find a committed first-year
  spending level $g^*$ that maximizes spending subject to a target shortfall probability. Sweeps a
  risk-aversion parameter $\lambda$ to trace the efficient frontier (committed spending vs. expected
  shortfall). Returns a dict with bases, lambdas, frontier arrays, and plan metadata.
- **`g_for_success_rate`** (new, public API): Returns $(g^*, \lambda)$ for the least conservative
  frontier point achieving a target success rate. Exported from `owlplanner`.
- **New plots** (both backends): `plot_spending_by_year` — bar chart of optimal spending/bequest by
  historical start year (plan-year dollars). `plot_stochastic_frontier` — success rate curve and
  efficient frontier side by side. `plot_stochastic_outcomes` — scenario bar chart colored by
  success/failure.
- **Stress-test refactoring**: `runHistoricalRange` and `runMC` extracted from `plan.py` into
  `src/owlplanner/stresstests.py` as module functions (`run_historical_range`, etc.) with `Plan` delegating methods.
  Public API unchanged.
- **Historical Range page**: When augmented sampling is off, a per-start-year bar chart is shown
  below the histogram.
- **New UI page**: *Spending Optimization* (`:material/query_stats:`) under Stress Tests. Scenario
  method radio (historical / Monte Carlo), target success rate slider, and an advanced options
  expander with roll and reverse sequence controls for historical mode.
- **Documentation**: Stress Tests section updated (three pages, new expander);
  `modeling-capabilities.md` Simulation modes row updated.

---

## Version 2026.04.07

### SS claiming age optimization (`withSSAges`)

- **`withSSAges` solver option**: The MIP optimizer now selects the optimal Social Security claiming
  month per individual (age 62–70, 97 choices). Pass `"optimize"` for all individuals, a name or
  list of names for specific individuals, or `"fixed"` (default) to use ages from
  `setSocialSecurity()`.
- **Per-individual selection**: Useful for couples where one spouse has already claimed — pass that
  spouse's actual claiming age to `setSocialSecurity()` and optimize only the other. Individuals
  whose current age exceeds their recorded claiming age are always treated as fixed.
- **Formulation**: Own SS benefits co-optimized in the LP via a precomputed benefit table
  `B_own[i, k, n]` and binary claiming-month selectors `zssa[i, k]`. Spousal and survivor benefit
  offsets recomputed each SC iteration. Compatible with all other solver options.
- **UI (Run Options)**: New *Optimize SS claiming age* radio group. Age inputs on the Fixed Income
  page become read-only for optimized individuals; optimal ages written back after solving.
- **`plan.ssecAges`**: Optimal claiming ages after solving. `summaryDf()` / `summaryString()`
  include a *SS claiming age* line per individual with non-zero PIA (e.g. `"67y 03m"`).
- **`PARAMETERS.md`**: New `withSSAges` entry.
- **Tests**: 17 tests in `tests/test_ss_ages.py`.

---

## Version 2026.04.02

### New objective: `maxHybrid` — blended spending and bequest

- **`maxHybrid` objective**: Blends spending and bequest into a single LP objective. Controlled by
  `spendingWeight` *h* ∈ [0, 1]: `h=1` maximizes spending only, `h=0` maximizes bequest only,
  `h=0.5` gives equal weight (both terms normalized to present-value dollars).
- **`spendingFloor`** (new): Hard lower bound on annual net spending (today's \$k) for `maxHybrid`.
  Recommended to prevent degenerate zero-spending solutions when growth rates are high.
- **`spendingWeight`** (new): Blend weight *h*; defaults to `0.5`.
- **`timePreference`** (new): Discounts future spending exponentially (%/year), shifting the optimal
  spending profile earlier. Supported for `maxSpending` and `maxHybrid`.
- **`spendingSlack` for `maxHybrid`**: Repurposed as a one-sided cap (spending ≤ floor × (1 + slack%));
  set to `0` (default) for no cap.
- **UI (Goals page)**: New *Hybrid* choice in the Maximize radio group with spending floor input and
  spending weight slider (0–1, step 0.05). Time preference slider in Spending Profile section
  (0–10 %/yr, step 0.5).
- **Schema**: `SolverOptions` gains `spendingWeight`, `spendingFloor`, and `timePreference`.
- **Docs**: `PARAMETERS.md`, Documentation (Goals expander), `modeling-capabilities.md`
  (Objectives and Spending profile rows) updated.
- **Tests**: 13 tests in `tests/test_hybrid_objective.py`.

---

## Version 2026.03.29

### Worksheets: age columns, real-dollar display, and solver time limit

- **`worksheet_show_ages`**: Age columns now included in the saved Excel workbook (not just
  on-screen). Final balance row carries the correct age; blank beyond the individual's horizon.
- **`worksheet_real_dollars`** (new): Divides all currency values by the cumulative inflation factor
  $\gamma_n$, converting nominal to today's dollars in both on-screen tables and the saved workbook.
  Saved filename gains a `_real` suffix. Toggled on the Worksheets page; round-tripped in TOML.
- **`worksheet_hide_zero_columns`**: Clarified as display-only; saved Excel retains all columns.
  Age columns protected from zero-column filtering.
- **Worksheets page**: Expander renamed to *Table display and save options*; real-dollars toggle added.
- **Default solver time limit**: `maxTime` default reduced from 900 s to 180 s, leveraging
  SC-loop warm-starting to cut total solve time on hard MILP cases.
- **Docs**: `PARAMETERS.md` (`[results]` table and example TOML); Documentation (Worksheets).
- **Tests**: 9 new tests in `tests/test_export.py`.

---

## Version 2026.03.26

### Breaking change: HFP person sheets require all columns

- Each person worksheet must include every time-horizon column: `year`, `anticipated wages`,
  `other inc`, `net inv`, `taxable ctrb`, `401k ctrb`, `Roth 401k ctrb`, `IRA ctrb`,
  `Roth IRA ctrb`, `HSA ctrb`, `Roth conv`, `big-ticket items`. Omitting a column is an error.
- Clearer `ValueError` listing missing headers; legacy `other inc.` still normalized.
- All `examples/HFP_*.xlsx` workbooks and `HFP_template.xlsx` updated.
- **Docs**: `PARAMETERS.md` HFP section; Documentation (Financial Profile) aligned.
- **Tests**: `tests/test_timelists.py` expects errors for missing required columns.

---

## Version 2026.03.24

### Worksheets: optional ages and hide-zero columns

- **`worksheet_show_ages`** and **`worksheet_hide_zero_columns`** (new `[results]` options,
  default `false`): round-tripped in TOML.
- **Worksheets page**: *Table display options* expander with both toggles.
- **Show ages**: Per-person age columns (integer, Dec 31 of each year); blank beyond horizon.
  On-screen only — saved Excel unchanged.
- **Hide all-zero columns**: Drops numeric columns where every value is zero; `year` never dropped.
  On-screen only.
- **Docs**: `PARAMETERS.md` (`[results]` table and example TOML); Documentation (Worksheets).
- **Tests**: `tests/test_worksheet_display_utils.py`.

---

## Version 2026.03.12

### Medicare Part D

- Part D premiums (IRMAA surcharges, same MAGI brackets as Part B) now included by default.
- `medicarePartDBasePremium`: optional monthly base premium per person (default `0`).
- `includeMedicarePartD` solver option (default `true`); set `false` for other drug coverage
  (employer plan, VA, etc.).
- Schema, `PARAMETERS.md`, `modeling-capabilities.md`, `owl.tex`, and Run Options UI updated.

---

## Version 2026.03.11

### Decomposition fixes

- Benders: skip zm pre-fixing when both individuals are already on Medicare at plan start;
  prevents SP LP infeasibility on later iterations.
- Benders: gap check and stall-detection added after the master MIP step.

---

## Version 2026.03.10

### LTCG and NIIT exact MIP formulations

- **`withLTCG="optimize"`**: Binary variables (`zl`) replace the SC-loop heuristic for LTCG
  bracket assignment, giving provably correct long-term capital gains tax rates.
- **`withNIIT="optimize"`**: Binary selection (`zj`) on whether MAGI exceeds the \$200k/\$250k
  NIIT threshold. Most effective combined with `withLTCG="optimize"`.
- Both modes exposed as expert toggles in the UI (Advanced Options).
- **Tests**: `tests/test_ltcg_lp.py` (6 tests) and `tests/test_niit_milp.py` (6 tests).

### MIP decomposition (`withDecomposition`)

When multiple `"optimize"` flags are active simultaneously, the monolithic MIP can be slow
(~400 binaries for a typical two-person plan). Two strategies are available:

- **`"sequential"` (relax-and-fix heuristic)**: LP relaxation → round and fix bracket families
  one at a time (`zl → zs → zj → zm → za`) → solve reduced MIP. Fast but not globally optimal.
- **`"benders"` (certified global optimum)**: Classical Benders decomposition — bracket-selection
  binaries in the master MIP, continuous planning in the subproblem LP/MIP. Dual-based optimality
  cuts certify global optimality. Converges in 1–3 iterations in practice. HiGHS and MOSEK supported.
- **`"none"`** (default): monolithic MIP (unchanged).
- `bendersMaxIter` option (default 50) caps Benders iterations.
- **Tests**: 11 tests in `tests/test_decomposition.py`.

### HiGHS direct API

- HiGHS is now called directly via `highspy`; the `scipy.optimize.linprog` proxy is removed.
- **PuLP/CBC and PuLP/HiGHS removed**: only HiGHS (direct) and MOSEK are supported.
- `abcapi.py`: `ConstraintMatrix.to_csr()` returns HiGHS rowwise CSR format. Warm-start via
  `_highs_warm_start`.

### `owlcli`: schema-driven solver options

- `SolverOptions` Pydantic model in `schema.py` is the single source of truth; used by TOML
  load, `plan_bridge`, and the CLI.
- **`--help-solver-options`**: Parses `PARAMETERS.md` at runtime — always in sync with docs.
- **`--solver-opt KEY=VALUE`**: Override any solver option on the command line.
- **Solver choices**: `--solver` now accepts only `default`, `HiGHS`, and `MOSEK`.

### UI and configuration

- Run Options: expert toggles for *Optimize LTCG brackets* and *Optimize NIIT*; *MIP decomposition*
  radio (`none` / `sequential` / `benders`).
- `withDecomposition` wired through `config_to_ui` / `ui_to_config`; legacy boolean `True` coerced
  to `"sequential"`.
- **`PARAMETERS.md`**: `withDecomposition` and `bendersMaxIter` entries added.

---

## Version 2026.03.09

### ACA marketplace (pre-65) UI exposure

- **Run Options**: New *ACA Marketplace (Pre-65)* section with SLCSP benchmark premium input.
  *Optimize ACA (expert)* toggle in Advanced Options (enabled only when SLCSP > 0).
- Config/UI bridge: `aca_settings` and `withACA` wired through `config_to_ui`, `ui_to_config`,
  and `genDic`.
- **Example**: `Case_morgan` illustrates ACA modeling for a pre-65 retiree.
- **Documentation**: ACA added to the self-consistent loop description.

### HSA accounts (fourth savings account type)

- HSA balances tracked alongside taxable, tax-deferred, and tax-free accounts (`j=3`).
- Pre-tax contributions reduce ordinary income, SS provisional income, and MAGI. Contributions
  zeroed at Medicare enrollment age (IRC §223). All withdrawals treated as qualified (tax-free).
- Non-spouse heirs include the full HSA balance in ordinary income (IRC §223(f)(8)(B)); bequest
  discounted accordingly.
- `setAccountBalances(hsa=...)` and `setHSA(balances, medicare_ages)` convenience method.
  Account allocation, asset composition, and Fixed Income page updated.
- **Tests**: 9 tests in `tests/test_hsa.py`.

---

## Version 2026.03.07

### `"net inv"` column in HFP

- New optional `net inv` column (net investment income from rent or trust distributions) in the
  Wages and Contributions spreadsheet. Enters cash-flow, taxable-income, SS-taxability, and MAGI
  constraints; counted in NII for NIIT. Backward compatible (defaults to zero when absent).
- `"net inv"` appears in each individual's Sources sheet in the workbook.

### Pension survivor benefits

- **Joint-and-survivor (J&S) option**: Surviving spouse receives a configurable fraction (0–100%)
  of the primary's pension after death. Config: `pension_survivor_fraction`; UI: Fixed Income page.

---

## Version 2026.03.05

### Rate models

- **`lognormal`** (new): Correlated log-normal with user-specified arithmetic means, volatilities,
  and correlations. Returns bounded below −100%, consistent with Geometric Brownian Motion.
- **`histolognormal`** (new): Fits a correlated log-normal to the selected historical window.
  History-grounded alternative to `lognormal`.
- **`var`** (new): VAR(1) model fitted by OLS on a historical window. Captures year-to-year serial
  correlations across all four asset classes; optional spectral shrinkage for stationarity.
- `bootstrap_sor` and `var` now exposed in the Rates Selection and Monte Carlo pages.
- **MC guard fix**: `runMC()` uses `rateModel.deterministic` attribute instead of a hardcoded name
  check.

### Rates Selection UI redesign

- Constant-preset and varying-method selectors are now `st.selectbox` widgets with a concise
  description caption surfaced from each model's metadata.

### Bug fixes

- `reverse_sequence` and `roll_sequence` were silently ignored in non-augmented historical range
  runs; both now read from session state and passed correctly.
- Run Options page warns when the minimum balance constraint may cause infeasibility.
- **Rename**: *Simulations* → *Stress Tests* throughout.

### Tests

- `test_rate_model_var.py`: 24 tests (shape, reproducibility, fitting, Cholesky, shrinkage,
  parameter validation, reverse/roll, MC integration).

---

## Version 2026.02.24

### HFP (Household Financial Profile)

- **Optional `"other inc"` column**: Other ordinary income (consulting, royalties, etc.) in the
  wages and contributions table. Backward compatible; `scripts/add_other_inc_column.py` migrates
  existing files.
- **Reports page**: Warning shown when HFP values were edited in the UI (case file alone cannot
  reproduce the run).

### Configuration

- Case-insensitive `case_` prefix check when saving TOML (issue #96).

### Code organization

- `pension.py` and `spending.py` extracted from `plan.py`. SS tax logic moved to `tax2026.py`;
  `setSocialSecurity` logic to `socialsecurity.py`; gamma/rate transforms to `rates.py`;
  oscillation detection to `utils.py`.

---

## Version 2026.02.23

### Social Security accuracy

- **Dynamic SS taxability fraction**: `Psi_n` now computed each SC iteration from the IRS
  provisional income formula (MFJ: \$32k/\$44k; single: \$25k/\$34k) with 30% damping for
  convergence, replacing a fixed 85%. Retirees with lower income get more accurate (lower) SS taxation.
- **`withSSTaxability`**: Pin `Psi_n` to a fixed value in [0, 0.85] (replaces `tax_fraction`
  parameter to `setSocialSecurity()`).
- **FRA table fix**: `getFRAs()` now returns the correct Full Retirement Age for birth years
  1938–1942 (65+2/12 to 65+10/12 per SSA table).

### SS trim

- `social_security_trim_pct > 0` without `social_security_trim_year` now raises an error instead
  of silently defaulting to 10 years from now.
- SS trust-fund exhaustion default changed to 2033 (SSA Trustees Report projection).
- "Starting year" widget greyed out when reduction percentage is 0.

---

## Version 2026.02.20

### UI

- **Create Case redesign**: Three columns (create, upload, load example) when no case is active;
  collapsible expander when a case is already loaded.
- **Inline HFP uploader**: After case creation, an HFP upload widget appears directly on the
  Create Case page.
- **Streamlit compatibility**: Version pin and `altair < 5` restriction removed from
  `requirements.txt`.

---

## Version 2026.02.19

### Rate models

- **`BuiltinRateModel` decomposition**: Single dispatcher replaced by 8 concrete `BaseRateModel`
  subclasses. `BuiltinRateModel` shim preserves backward compatibility.
- **Stochastic UI fix**: Builtin rate model now accepts config-style parameter names
  (`standard_deviations`, `correlations`) in addition to API names.
- **`getRatesDistributions`** (issue #92): Returns percent by default; accepts optional `df=`
  parameter for user-supplied DataFrames.
- **DataFrame rate model** (issue #92): Column names standardized (T-Notes/T-Bills); `in_percent`
  parameter replaces heuristic; display names aligned with column names.
- Rates UI: label `'fixed'` renamed to `'constant'`.

### Social Security

- SS trim (reduction from a given year onward): config, schema, UI bridge, and Fixed Income page.

---
