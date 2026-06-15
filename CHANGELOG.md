

### Version 2026.6.15

#### Balance Sheet graph

A new **Balance Sheet** graph on the **Graphs** page (Portfolio section) complements the
traditional and liquid balance-sheet worksheets. Assets (taxable, tax-deferred, tax-free, HSA,
fixed assets) are stacked above the zero line and liabilities (debt, deferred income tax on
tax-deferred/HSA balances, and fixed-asset disposition costs) below it, with the traditional and
liquid net-worth lines overlaid so the gap between gross and liquidatable wealth is visible at a
glance. Available as `Plan.showBalanceSheet()` for notebook use; honors the nominal/today's-dollars
toggle and renders in both the Plotly (UI) and Matplotlib (CLI/notebook) backends.

#### Fix: one-year net-worth dip when a fixed asset is sold

Corrected an accounting error in the beginning-of-year fixed-asset arrays. A disposed asset was
dropped from the balance sheet at the start of its disposition year, but its sale proceeds only
land in the savings accounts the following year, so net worth was under-counted for that one year
(an artificial dip in the Balance Sheet graph, worksheets, and per-year JSON). Fixed assets are
now counted through their disposition year and drop out the year after, when the proceeds appear,
keeping net worth continuous. The cash flow, taxes, and bequest values were already correct and
are unchanged.

#### Clearer "today's dollars" labeling on plots and in the UI

Inflation-adjusted plots now label the vertical axis as `$k (constant <year>)` (e.g.
`$k (constant 2026)`) instead of an ambiguous year tag, making the deflation base explicit and
pairing cleanly with the `$k (nominal)` antonym. This also fixes a rendering bug where the
dollar sign in the today's-dollars axis title was interpreted as a LaTeX/MathJax delimiter by
the Plotly static-image export, mangling the label. The matching tooltips on the **Graphs**
dollar-amount selector, the **Worksheets** "real (today's) dollars" toggle, and the **Goals**
bequest/spending/safety-net fields now spell out "constant `<year>` dollars", all keyed off a
new `baseYear()` helper so the wording always tracks the plan's base year.

#### Documentation

Added a Savings Balance example plot (the *chris+pat* case) to the README to illustrate how
Owl draws down tax-deferred accounts while growing tax-free Roth balances through optimized
early-retirement conversions.

#### Documentation reorganization

Hand-authored reference docs now live in a single top-level `info/` directory instead of being
split between the repository root and the Quarto site's output folder (`docs/`). `USER_GUIDE.md`,
`PARAMETERS.md`, `RATE_MODELS.md`, `mcp.md`, `modeling-capabilities.md`, and `year-end-update.md`
moved to `info/`; community-health files (`README`, `CHANGELOG`, `CONTRIBUTING`, `CREDITS`,
`LICENSE`, `INSTALL`) remain at the root. All internal links, the wheel `force-include` for
`PARAMETERS.md`, the CLI/UI path resolution, and the `make rate-model-docs` target were updated
accordingly, leaving `docs/` reserved for generated Quarto output.

Documentation images were likewise separated: the markdown screenshots and plots moved to
`info/images/`, leaving `papers/images/` for the LaTeX figures used by `owl.tex`; two unused
images were removed. Several long-broken references were fixed in passing — the `docs/images/`
image paths, the tutorial-notebook links, and the worked-example's data file
(`HFP_jack+jill.xlsx`) — and the `odfpy`/`uv` installation wording was clarified. A new
`make site` target renders the Quarto website and cleans up render artifacts (the demo workbook
and orphaned hashed assets).

### Version 2026.6.14

#### Balance sheets in worksheets (traditional and liquid)

Two new worksheets summarize total wealth by combining savings accounts, fixed assets, and
debts at the beginning of each year (plus a final end-of-plan bequest row). The **Balance
Sheet** uses traditional accounting at gross market value: assets (taxable, tax-deferred,
tax-free, HSA, fixed assets), `total assets`, `debt`, and `net worth`. The **Liquid Balance
Sheet** shows the same gross assets but adds future obligations as liabilities to estimate
realizable wealth: `debt`, `deferred income tax` (tax-deferred + HSA balances times a new
*Liquidation tax rate*), `disposition costs` (fixed-asset commission plus capital-gains tax
at a new *Liquidation cap-gains rate*, with the primary-residence exclusion applied),
`total liabilities`, and `liquid net worth`. Taxable savings are shown at face value and HSA
balances are treated as ordinary-taxable (a conservative estimate). Both rates are set on the
**Rates** page and saved with the case. The sheets appear under a new **Balance Sheets** tab
in the **Worksheets** page and honor all display options (nominal/today's dollars, optional
age columns, hide all-zero columns) and the Excel download.

#### MCP & CLI: balance sheet and net worth in results

The balance-sheet quantities are now reachable through the MCP server and CLI, not just the
Streamlit worksheets. `run_case`/`run_from_params` add the opening balance sheet to the
`summary` block (`net_worth_start_*`, `liquid_net_worth_start_*`, `fixed_assets_start_nominal`,
`debt_start_nominal`, `deferred_income_tax_start_nominal`) and the liquidation-rate
assumptions, plus per-year `fixed_assets`, `debt`, `net_worth`, `deferred_income_tax`,
`disposition_costs`, and `liquid_net_worth` in `by_year` (the existing `portfolio_total`
remains savings-only). `explain_case` now loads the HFP workbook so it can report the
`fixed_assets` and `debts` inputs and an `opening_balance_sheet` summary. `run_from_params`
and `save_case` accept new `liquidation_tax_rate` / `liquidation_capgains_rate` parameters
(percent), which `save_case` persists to the case TOML. A shared
`export.balance_sheet_arrays()` helper is the single source for the worksheet, the summary
metrics, and the JSON output so they stay consistent. Documented in `docs/mcp.md`.

#### Tests: generic schema-driven config round-trip guard

Added `tests/config/test_roundtrip_generic.py`, which introspects the Pydantic schema and
verifies every scalar parameter survives both the plan and UI config bridges, with a
completeness guard so a newly-added field that isn't wired (or consciously skip-listed) fails
loudly — replacing the need for a hand-written round-trip test per parameter.

---

### Version 2026.6.13

---

### Version 2026.6.13

#### Fix: Social Security treatment in MAGI (IRMAA / NIIT vs ACA)

MAGI is now computed on two distinct bases instead of one. IRMAA (Medicare Part B/D
surcharges), the Net Investment Income Tax, and the OBBBA 65+ senior-deduction phaseout use
the **AGI-basis** MAGI (`MAGI_n`), which includes only the *taxable* portion of Social
Security — matching the statutory definition (SSA POMS HI 01101.010: AGI + tax-exempt
interest). The ACA premium credit (IRC §36B) and the Social Security provisional-income
formula continue to use the **full-SS** MAGI (`MAGI_aca_n`), which adds back the non-taxable
portion. Previously a single full-SS MAGI drove all of them, overstating IRMAA/NIIT/OBBBA
exposure for households collecting Social Security. The fix applies in both loop and
optimize modes (Medicare and NIIT MILP embeddings updated). `papers/owl.tex` updated to
match; reproducibility references shifted accordingly (bequest/spending rise slightly).

#### Robustness: Benders fall-back and LTCG bracket-partition bound

`withDecomposition="benders"` now falls back to the relax-and-fix heuristic when it cannot
certify optimality within the requested gap (keeping the better objective), instead of
silently returning an uncertified solution. The LTCG bracket-partition companion bound now
seeds its capital-loss buffer from the known fixed-asset capital gains so a first-iteration
fixed-asset loss cannot make the partition infeasible.

#### MCP: `list_contribution_limits` tool for IRS contribution ceilings

New MCP tool returns each person's maximum annual contribution to 401(k)/403(b)/457(b)/TSP,
IRA, and HSA accounts for a given tax year, including the age-50+ catch-up and the SECURE 2.0
"super" catch-up for ages 60-63. Helps AI assistants guide users in their 50s and 60s toward
maxing out tax-advantaged contributions before filling in the `contributions` list for
`run_from_params`/`save_case`. Adds `contributionLimits()` and a 2025/2026 limits table to
`tax_federal.py` (statutory ceilings only — does not check MAGI-based eligibility/phase-outs).

#### Per-cell Roth conversion overrides (discussion #129)

New `useRothConvOverrides` solver option lets the *Roth conv* column of the Wages and
Contributions table pin a year/individual's conversion to an exact amount — bypassing the
annual cap — or force it to zero, while every other year stays optimized. Replaces the
all-or-nothing `maxRothConversion="file"` mode.

**Breaking change:** `maxRothConversion="file"`
is no longer accepted (raises a validation error); update TOMLs to use `useRothConvOverrides`
instead. Run Options also gains a "Swap Roth converters mid-plan" control for couples,
mutually exclusive with the existing Roth-conversion exclusion selector.

#### CI: bump Node per GitHub's request
Bump `actions/checkout` and `astral-sh/setup-uv` to Node 24 releases ahead of GitHub's Node 20 deprecation.

---

### Version 2026.6.12

#### LTCG bracket-partition and state-tax LP fixes

Fixed an LP degeneracy that could let the 20%-LTCG-bracket variable (`q_pn[2,n]`) be
inflated far beyond the actual realized gain `Q_n` (most visible with
`maxRothConversion="file"`). A companion upper bound on the bracket-partition row in
`_configure_ltcg_constraints` now keeps `q_pn` tied to `Q_n`. The same flat-direction
pattern was also present for no-income-tax states (FL, TX, AK, ...): state-tax LP
variables (`st_f`/`st_e`/`st_re`) are now skipped entirely when every bracket rate is
zero, since they could never contribute to `st_T_n` anyway. Added a new regression test
for `maxRothConversion="file"`.

#### Balance-sheet arrays for fixed assets and debts (issue #128)

`Plan` exposes two new arrays (length N_n), computed in `processDebtsAndFixedAssets()`:
- `fixed_assets_current_asset_values_n` — gross market value of fixed assets still held
  at the start of each year (`fixedassets.get_fixed_assets_current_values_array`).
- `fixed_assets_debt_balances_remaining_n` — remaining loan balance at the start of each
  year (`debts.get_debt_balances_array`).

No commission or tax treatment applied — simple snapshots for a future balance-sheet worksheet.

---

### Version 2026.6.9

#### MCP server — AI assistant access to Owl

Owl is now accessible as a tool to AI assistants that support the
[Model Context Protocol](https://modelcontextprotocol.io) (MCP): Claude Desktop, Claude Code,
Cursor, Zed, VS Code (GitHub Copilot 1.99+ or Cline extension), Windsurf, and any other
MCP-compatible client.

**New MCP tools:**

- **`run_from_params`**: Build and solve a retirement plan directly from structured parameters
  (names, birth years, account balances, SS benefits, etc.) without preparing any files. AI
  assistants can describe a financial situation in natural language and immediately get an
  optimized plan back as JSON.
- **`save_case`**: Persist a flat-parameter plan to disk as a TOML case file and an HFP
  workbook (`.xlsx`). Useful for saving AI-generated plans for later UI use.
- **`run_stochastic`**: Compute the stochastic spending efficient frontier from either a TOML
  file or flat parameters. Accepts `"historical"` (back-test) or `"mc"` (Monte Carlo) scenarios,
  sweeps risk-aversion parameter λ across the frontier, and returns committed spending at a
  target success rate and the full efficient frontier — all as structured JSON.
- **`convert_ss_benefit`**: Utility tool that converts between a Social Security PIA
  (Primary Insurance Amount, the benefit at Full Retirement Age) and the actual monthly
  benefit at a given claiming age, in either direction. Lets an AI assistant turn a
  statement like "I'm 65 and I get a $2,800 check" into the PIA value expected by
  `ss_monthly_pias` in `run_from_params`, `save_case`, `run_stochastic`,
  `run_longevity_stochastic`, `run_historical`, and `run_monte_carlo`.

**MCP parameter coverage — all three tools (`run_from_params`, `save_case`, `run_stochastic`):**

All monetary values use full dollars (`$`) throughout the MCP interface via `units="1"`.

- **Unit convention**: All account balances, solver limits, and monetary options use full
  dollars (`$`). Social Security is the monthly PIA in `$/month` (matching the Plan API's
  `setSocialSecurity()`). Pensions are monthly `$/month`. Time-series amounts (wages,
  contributions) are `$/year`.
- **`ss_monthly_pias`**: Monthly Social Security PIA per person — the benefit at Full
  Retirement Age from the SSA statement (e.g. `[2667, 1833]`). Renamed from the initial
  annual-amount convention.
- **`min_taxable_balance`**: Per-person inflation-indexed floor on the taxable account
  balance (emergency fund / safety net). The optimizer will not draw the taxable account
  below this amount in any year.
- **`spending_profile`**: Retirement spending shape — `"smile"` (default, go-go/slow-go/
  no-go curve) or `"flat"` (constant inflation-adjusted spending). Companions:
  - `smile_dip` — depth of the slow-go spending dip in % (default 15).
  - `smile_increase` — additional spending growth toward no-go years for medical costs in %
    (default 12). Can be negative to model a declining-spending trajectory.
  - `smile_delay` — number of initial go-go years held flat before the smile curve begins
    (default 0).
- **`spias`**: List of Single Premium Immediate Annuities. Each entry specifies
  `person`, `buy_year`, `premium` (deducted automatically from the IRA as a non-taxable
  rollover), `monthly_income`, `indexed` (CPI-linked), and `survivor_fraction`.
  Supports multiple SPIAs per plan and pre-purchased annuities (`buy_year` before plan start).
- **`start_roth_year`**: 4-digit year before which no Roth conversions are allowed. Useful
  when the user expects to remain in a high tax bracket for several years.
- **`no_roth_person`**: Name of the individual excluded from all Roth conversions (couples only).
- **`max_roth_conversion`**: Annual per-person Roth conversion cap in `$/year`.
- **`bequest`**: Target estate value in today's dollars when `objective="maxSpending"`.
  The optimizer maximizes spending subject to leaving at least this amount to heirs.
- **`optimize_ss_ages`**: Boolean — if `True`, the MIP optimizes the Social Security
  claiming month for each person (ages 62–70, monthly resolution) instead of using the
  fixed `ss_ages` values.

**Documentation (`docs/mcp.md`):**

- Full setup instructions for Claude Desktop, Claude Code (CLI), Cursor, Zed, VS Code
  (GitHub Copilot + `.vscode/mcp.json` format; Cline extension format), and Windsurf.
- `run_stochastic` added to the tools reference table and example interaction section.
- All example interactions updated to use monthly PIA language (was annual benefit).
- New example: Robert with `min_taxable_balance` (emergency fund / safety net).
- New example: SPIA comparison — AI fetches current payout rates from the web and
  compares the plan with and without converting a portion of the IRA to a SPIA.

**README and Streamlit Welcome page:**

- MCP listed as the fourth way to run Owl alongside cloud, Docker, and native install.
- AI assistant bullet added to the key capabilities list, naming all supported clients.
- SEO-friendly H3 heading (*AI-powered retirement planning — ask your AI assistant*) added
  to the Welcome page.

**Modeling capabilities (`docs/modeling-capabilities.md`):**

- New *Access interfaces* table below the modeling table listing all four access modes
  (Streamlit UI, Python API, CLI, AI assistant/MCP).

**Tests:**

- `tests/test_mcp_params.py` (53 tests): `_build_plan_from_params`, `_build_hfp_dataframes`,
  `save_case` round-trip, `run_from_params` integration tests, and 5 new SPIA unit tests.
- `tests/test_mcp_stochastic.py` (30 tests): `_stochastic_blocking`, `_build_stochastic_json`,
  and `run_stochastic` async end-to-end tests covering historical and MC paths, error handling,
  and frontier monotonicity.

---

### Version 2026.6.7

#### Python

Pinned version to 3.14 for Streamlit Cloud Server and uv deployment.
However, versions >= 3.11 are fine for owlplanner package.
Docker containers are using an image with Python 3.14.

#### State income tax

State income tax brackets are now embedded directly in the LP alongside federal taxes,
giving the optimizer full visibility into state marginal rates when planning Roth conversions,
withdrawals, and spending.

A new `state` field in `[basic_info]` accepts any two-letter US state abbreviation (e.g.
`state = "MN"`). Leaving it blank or omitting it preserves the previous federal-only behavior.
No-income-tax states (AK, FL, NV, NH, SD, TN, TX, WA, WY) are accepted and simply contribute
zero state tax.

State tax is modeled using the same graduated-bracket mechanism as federal income tax:
- **Brackets and marginal rates** — state-specific, inflation-adjusted each year.
- **State standard deduction** — subtracted from state taxable income, inflation-adjusted.
- **Retirement income exemption** — optional age-gated per-person dollar cap (e.g. GA, NY, PA).
- **Pension-only exemption** — separate cap where states distinguish pension from other retirement income.
- **Social Security treatment** — binary flag; states that tax SS (e.g. MN, VT) include
  85% of SS benefits in state taxable income.

Filing status transitions from MFJ to Single at the year the first spouse dies, matching
the federal filing-status transition already in the optimizer.

**New public method:** `Plan.setStateTax(state)`.
**New module:** `src/owlplanner/tax_state.py` — `st_taxParams()`, `valid_states()`.
**New data file:** `src/owlplanner/data/taxes_state.toml` — all 50 states + DC with 2026 rates.
**UI:** State selectbox added to the **Create Case** page.
**Output:** State tax appears as a separate series in `showTaxes()`, as a standalone line in
the plan summary (*Total state income tax paid*), and as a *State tx* column in the
income tax worksheet.

**Worksheet renamed:** The *Federal Income Tax* worksheet in the plan workbook is now called
*Taxes*, reflecting that it includes both federal and state tax detail.

**Cash flow fix:** State income tax was missing from the *Cash Flow* worksheet and CSV export,
causing the sheet to not balance when a state is configured. Fixed; test coverage added.

**Taxes worksheet:** Now includes Medicare+IRMAA and ACA premiums (when applicable) for a
complete year-by-year view of all optimizer-managed costs.

#### 2026 state tax data audit

All 51 jurisdictions in `taxes_state.toml` were verified against official 2026 sources, with
bracket and rate corrections applied to 21 states.

#### `tax2026.py` renamed to `tax_federal.py`

The federal tax module `tax2026.py` was renamed to `tax_federal.py` for consistency with
the new `tax_state.py` module. All internal imports updated; no public API change.

#### Drop Python 3.10 support

Python 3.10 is no longer supported. The minimum required version is now **Python 3.11**.
CI tests against Python 3.11, 3.12, 3.13, and 3.14.

#### MOSEK moved to required dependencies

MOSEK was previously an optional extra (`pip install owlplanner[mosek]`). It is now listed
as a standard dependency. Users without a MOSEK license can still install and run Owl — the
HiGHS solver remains the default and no license is required for normal use.

#### In-app documentation audit

The in-app help (**Documentation** page) was audited page-by-page against the actual UI and
brought back into alignment, including the state-tax help, **Worksheets** tab names, Monte-Carlo
rate-method lists, and a new experimental note on the Retirement Efficiency Score (RES). A couple
of stale UI labels were corrected along the way.

#### Versioning and committed lockfile

The package version is now a static field in `pyproject.toml` (single source of truth),
mirrored into `src/owlplanner/version.py` via `make sync-version` and guarded by a test.
uv now records this version natively in `uv.lock`, which is committed to the repository
(previously excluded because Streamlit Cloud could not parse the versionless editable entry).
Version numbers now use canonical PEP 440 form with no zero-padding (`YYYY.M.D`, e.g. `2026.6.7`),
so the string is identical across `pyproject.toml`, the wheel metadata, and `uv.lock`.

---

### Version 2026.06.06

#### Rate CDF plot (`showRatesCDF`)

Adds a new plot showing the empirical CDF of each asset class's generated rates (S&P 500, Bonds Baa, T-Notes, Inflation), one panel per asset class.
For historical methods, the empirical CDF of the selected frm–to window is overlaid as a dashed gray line for goodness-of-fit comparison.
The y-axis gives cumulative probability directly — no binning artifact — making tail probabilities easy to read.
Constant-rate methods do not produce a CDF plot.

The same 2 000-sample representative draw used for the correlation graph is used here, so the CDF reflects the model's true distribution rather than the short plan-horizon realization.

**New public method:** `Plan.showRatesCDF(tag="", figure=False)`.
**New backend methods:** `plot_rates_cdf` in both `matplotlib_backend.py` and `plotly_backend.py`, declared abstract in `plotting/base.py`.
**UI:** Appears on the **Rates** page (left column, below *Selected Rates Over Time Horizon*) and on the **Graphs** page under the **Rates** tab, for varying rate methods only.

---

#### Constrain mean option for history-fitted stochastic rate models

Adds an optional `constrain_mean` parameter (default `False`) to six history-fitted stochastic rate models: `historical_gaussian`, `historical_lognormal`, `historical_copula`, `garch_dcc`, `gmm`, and `hmm`.

When enabled, each generated rate series is post-processed with an additive per-column shift so its arithmetic mean exactly matches the historical arithmetic mean of the selected window.
The distribution shape — variance, skew, volatility clustering, and cross-asset correlations — is fully preserved; only the mean is corrected.
This isolates sequence-of-returns risk from mean-estimation noise, which is useful when comparing scenarios across methods or plan horizons.

A **Constrain mean** checkbox is exposed in the Rates UI next to the year-range selectors for the six supported methods.
Return floors are applied after the mean correction: equity, bonds, and T-notes are floored at −100%; inflation is floored at −5%.

**New helper functions** in `src/owlplanner/rate_models/_builtin_impl.py`: `constrain_series_mean` (pure additive shift, no flooring), `_historical_arith_means` (arithmetic mean of the selected window from in-memory globals), and `apply_return_floors` (universal floor applied as the final step of every `generate()` method).

**`CONSTRAIN_MEAN_METHODS`** constant added to `constants.py`; sync between this constant and each model's `optional_parameters` is enforced by a new test (`tests/test_rate_models.py::test_constrain_mean_methods_in_sync`).

---

### Version 2026.06.05

#### New rate model — Gaussian Copula (`historical_copula`)

Adds a non-parametric Gaussian copula rate model fitted to the selected historical window.
Each asset's marginal distribution is preserved exactly via a rank-based empirical CDF — no Gaussian or log-normal shape is imposed on any marginal — while joint dependence is captured by a 4×4 copula correlation matrix in normal space.
New year-combinations are generated that were not observed historically but honour all pairwise rank correlations.
Generated values are bounded to the historical `[min, max]` of each asset class; inflation is floored at −5% to exclude Great Depression tail artefacts.
The empirical quantile resolution equals the number of years T in the selected window.

Registered in `STOCHASTIC_METHODS`, `HISTORICAL_STOCHASTIC_METHODS`, `VARYING_TYPE_UI`, and `HISTORICAL_RANGE_METHODS` in `constants.py`.
Exposed in the Rates UI alongside the other varying-rate methods; seed and reproducibility controls apply.
`HISTORICAL_STOCHASTIC_METHODS` is a new constant replacing the repeated inline method tuples in `owlbridge.py`, `plotly_backend.py`, and `matplotlib_backend.py`.

**New file:** `src/owlplanner/rate_models/copula.py` — `generate_histocopula_series`, `HistoCopulaRateModel`.

**Documentation:** `PARAMETERS.md`, `docs/modeling-capabilities.md`, `ui/Documentation.py` (method description, comparison table, correlation graph table, Monte Carlo section, reproducible rates, references — Sklar 1959).

---

#### Documentation and schema alignment (issue #126)

Added `fixedSpending` and `hsa` as explicit fields in the Pydantic schema (`SolverOptions` and `AssetAllocation`). Removed stale `spendingFloor`, `spendingWeight`, and `maxHybrid` references from `PARAMETERS.md`.

---

#### Inflation skewness correction for parametric rate models

Historical US inflation rates are right-skewed (long right tail from high-inflation episodes such as the 1970s), which violates the Gaussian residual assumption implicit in four parametric stochastic models.
A piecewise-linear (PWL) normalization transform $\varphi$ is now automatically applied to the inflation dimension before fitting those models, and its inverse $\varphi^{-1}$ is applied to generated samples so outputs remain in actual inflation units:

$$\varphi(z) = \begin{cases} (z-\kappa)\,s^- + \kappa & z \le \kappa \\ (z-\kappa)\,s^+ + \kappa & z > \kappa \end{cases}$$

where $\kappa$ is the empirical median of the selected historical window.
The slopes $s^-$ and $s^+$ are auto-fitted by minimizing squared skewness of $\varphi(z)$ with a small regularization toward the identity, so they adapt automatically when the user changes the date range.
For US inflation over 1928–2025 the optimizer typically finds $s^- \approx 2.3$, $s^+ \approx 0.8$.
Fitted values are reported in the debug log at model initialization.

**Affected models:**
- `historical_gaussian`, `vector_ar`, `garch_dcc` — transform applied in return space.
- `historical_lognormal` — transform applied in log-return space to avoid log-domain constraints.

**Unaffected:** `gaussian`, `lognormal` (user-supplied parameters), `historical_bootstrap`, `historical_average`, `gmm`, `hmm` (no Gaussian residual assumption on inflation).

**New module:** `src/owlplanner/rate_models/inflation_transform.py` — `fit_inflation_transform`, `pwl_transform`, `inv_pwl_transform`.

**Documentation:** `papers/owl.tex` §"Inflation skewness correction", `docs/modeling-capabilities.md`, `ui/Documentation.py`.

---

### Version 2026.06.05

#### New rate model — Hidden Markov Model (`hmm`)

Adds a Hidden Markov Model rate model that extends the GMM by fitting a $K \times K$ Markov transition matrix between regimes via the Baum-Welch algorithm. Consecutive simulated years are no longer independent: regime persistence produces realistic multi-year bull and bear runs, capturing sequence-of-returns risk that the i.i.d. GMM cannot reproduce. Exposed in the UI with a configurable number of regimes (default $K=3$). The correlation plot uses 2 000 synthetic draws from the fitted model. Registered in `STOCHASTIC_METHODS`, `VARYING_TYPE_UI`, and `HISTORICAL_RANGE_METHODS`; seed and reproducibility controls work identically to `gmm`.

---

### Version 2026.06.04

#### New rate model — Gaussian Mixture Model (`gmm`)

Adds a multivariate GMM rate model that fits $K$ Gaussian components on the selected historical window via EM, capturing regime-dependent cross-asset correlations (bull, bear, crisis). Exposed in the UI alongside the other varying-rate methods, with a configurable number of components (default $K=3$).

---

### Version 2026.06.03

#### Bug fix — NIIT MILP (`withNIIT="optimize"`)

The MAGI equality constraint in `_add_magi_lp` incorrectly expressed $Q_n$
(LTCG capital gains) as `q_total − portfolio_LP_expression`.
At the LTCG partition minimum where `q_total = Q_n`, these two expressions
cancel, silently removing $Q_n$ from MAGI.
As a result, the optimizer computed NIIT as $0.038 \times \mathbb{I}_n$
instead of the correct $0.038 \times \min(\text{MAGI} - T,\; \mathbb{I}_n + Q_n)$,
understating NIIT by up to $0.038 \times Q_n$ per year when the NII cap was binding.

**Fix:** The MAGI LP constraint now uses the LTCG bracket allocation variables
$q^{(0)}_n + q^{(1)}_n + q^{(2)}_n$ directly for $Q_n$ (which equals the true
capital gains at the partition minimum).
The portfolio b/w/d LP expression is no longer subtracted.

**Regression test added:** `test_niit_optimize_large_taxable_J_n_vs_reference`
uses a large taxable balance to exercise the NII-cap path with significant $Q_n$.

#### Cash Flow worksheet — NIIT column

`ord taxes` in the Cash Flow worksheet now reports income tax ($T_n$) only.
NIIT ($J_n$) is shown as a separate `NIIT` column, consistent with how
`div taxes` ($U_n$) is already separated from income tax.
The `NIIT` column also appears in the CSV export.

---

### Version 2026.06.01

#### UI improvements

- **Documentation and Parameters Reference** — all expanders now use `type="compact"`
  with bold orange titles, giving each section a clear visual boundary consistent
  with the rest of the app styling.
- **Reports page** — download buttons are grouped into labeled *Input files* and
  *Output files* sections for clearer navigation.

#### Bug fix

- **Reports comparison** — `build_summary_dic()` now always emits `Total debt payments`
  and `Total ACA premiums paid` fields (with $0 when none apply), so `compareSummaries()`
  no longer silently drops cases whose column sets differ when one case has debts or ACA
  costs and another does not.

#### Refactor

- **Logging** — all config modules (`toml_io.py`, `ui_bridge.py`) now route warnings
  through `mylogging` instead of the stdlib `logging` module, so messages appear
  consistently in the Streamlit case log.

---

### Version 2026.05.27

#### Rate method names — consistency and accessibility

All rate method names now use underscore separators and plain-language labels.
Old names are accepted as backward-compatible aliases (with a deprecation warning
logged on load) and will be removed in a future release.

| Old name | New name |
|---|---|
| `historical average` | `historical_average` |
| `trailing-30` | `trailing_30` |
| `histogaussian` | `historical_gaussian` |
| `histolognormal` | `historical_lognormal` |
| `bootstrap_sor` | `historical_bootstrap` |
| `var` | `vector_ar` |

Source files renamed accordingly:
`bootstrap_sor.py/.md` → `historical_bootstrap.py/.md`,
`var_model.py` → `vector_ar.py`.

#### Bootstrap documentation

- Tooltip and UI documentation clarify that `block_size` is a **fixed** block
  length for `block`/`circular`, but the **expected** (geometric mean) block length
  for `stationary`.
- All three non-iid variants collapse to iid when `block_size = 1`.
- Recommended range for annual return data: **3–5** (Politis & White 2004).

#### Bug fix

- `OWL_TEST_SOLVER` environment variable comparison is now case-insensitive
  (`highs`, `HiGHS`, and `HIGHS` all select the HiGHS solver in tests).

---

### Version 2026.05.24

#### Fixed assets — real vs. nominal growth rate

The `rate` column in the *Fixed Assets* HFP sheet now has **type-dependent semantics**:

- **Physical assets** (*residence*, *real estate*, *collectibles*, *precious metals*): `rate` is a
  **real (inflation-adjusted)** annual growth rate. Setting `rate = 0` means the asset maintains its
  purchasing power by tracking inflation. A value of `1` means 1 % above inflation per year.
  Shiller's long-run US data shows roughly 0–0.5 % real appreciation for real estate, so `0` is a
  reasonable default.
- **Financial assets** (*stocks*, *fixed annuity*): `rate` remains a **nominal** annual growth rate,
  unchanged from prior behavior.

**Migration:** existing HFP files that had a nominal rate (e.g. `3`) for a residence or real estate
asset should be updated. A rate of `0` now correctly means "tracks inflation" rather than "flat
nominal." All bundled example HFP files have been updated (residence and real estate rates set to `0`).

---

### Version 2026.05.23

#### Graphs

- **Annual cash flow mix** — new `showCashFlowMix()` chart: normalized stacked-area panels showing
  income sources (left) and outflow composition (right) as a percentage per year in today's dollars.
  Colors match the lifetime allocation pie charts. Wired into the Spending graphs section.
- **Lifetime allocation layout** — pie chart order swapped: income sources left, outflows right
  (both backends).

#### Bug fix

- **TOML parse errors now raise `ValueError`** instead of the misleading `FileNotFoundError`
  when a case file contains invalid TOML (e.g. a mixed int/float array like `[10.0, 2_000]`).
- **`Case_jack+jill` example** — corrected Jill's pension from `10.5` to `2_000.0` $/month
  (issue #125); expected spending basis updated in regression tests.

---

### Version 2026.05.20

#### Mortality tables — SOA Pub-2010 public-sector tables

- Added **Pub2010-Safety**, **Pub2010-General**, and **Pub2010-Teacher** tables from mort.soa.org.
- Dropdown and documentation now ordered by life expectancy at 65 (shortest to longest).

#### Spending Optimization — longevity plots

- **Survival curves** — when longevity risk is enabled, a new chart shows P(alive at age X)
  for each individual derived from the selected mortality table. For couples, a dashed joint
  (last-survivor) curve is also plotted.
- **Drawn lifespans histogram** — overlapping histograms of the ages at death sampled across
  all Monte Carlo scenarios, one series per individual and one for the joint last-survivor
  horizon. Median age at death for each series is shown in a color-coded text box.
- **matplotlib stubs** — `plot_stochastic_cvar_vs_pos` and `plot_stochastic_res_vs_cvar`
  added as stubs returning `None` in the matplotlib backend (RES section is plotly-only for now).
- **Documentation** updated in the *Spending Optimization* section to describe the new charts.

---

### Version 2026.05.19

#### UX
- **Financial Profile page**: A status caption now appears below the HFP upload widget confirming
  which file was loaded. If any table value is edited after the upload, the filename is marked with
  a trailing `*` (e.g. `HFP_jack+jill.xlsx *`) so the original filename is never lost and the
  modified state is immediately visible without having to run the plan first.

---

### Version 2026.05.16

#### Taxable account cost-basis tracking

- **`setCostBasis(amounts, units='k')`** (new): Declares the aggregate cost basis of each
  individual's taxable account. When provided, capital-gains tax on taxable-account withdrawals
  is computed using the **average-cost method**: the gain fraction `(balance − basis) / balance`
  is applied per dollar withdrawn, capturing all embedded unrealized gains rather than only
  this year's price appreciation. The basis evolves each SC-loop iteration as withdrawals reduce
  it proportionally and new contributions (HFP deposits and LP surplus deposits) increase it at
  full cost.
- **Fallback**: If `setCostBasis` is not called, the prior approximation (`cap_rate ≈ τ₀ − μ`,
  this year's appreciation only) is used — no behavioral change for existing cases.
- **TOML**: `taxable_cost_basis` field in `[savings_assets]`; round-tripped through
  `saveConfig()` / `readConfig()`.
- **UI**: Per-person cost-basis inputs on the *Account Balances* page (optional; leave at 0 to
  use the legacy approximation).
- **Example files**: `Case_jack+jill`, `Case_joe`, and `Case_robin` updated with realistic
  cost-basis values (roughly half of taxable balance, consistent with ~10 years of compounding).
- **Docs**: `docs/modeling-capabilities.md` corrected — taxable-account gain treatment now
  accurately described as average-cost rather than LIFO.
- **Tests**: 8 new tests in `tests/test_cost_basis.py` covering backward compatibility,
  high-gain scenarios, edge cases (zero basis, full basis, basis > balance), and SC-loop
  convergence.

---

### Version 2026.05.15

#### UX
- Rework _Graphs_, _Worksheets_,  and _Create Case_ pages.
- Updated documentation.

---

### Version 2026.05.11

#### Hardening
- **Tests**: Add cash flow balance test
- **Advisory**: Upgrade requirements per GitHub advisory
- **Clean up**: Make HFP I/O consistent with new names for files

---

### Version 2026.05.07

#### Theme

- **Streamlit theme**: Remove default dark theme and leave it to system's settings.

#### Plots
- Improve threshhold for displaying QME values.

#### Cleanup
- Remove legacy names in HFP I/O.

---

### Version 2026.05.06

#### HSA qualified medical expense cap

- **`setMedicalExpenses(amount)`**: new method to declare annual non-Medicare qualified medical
  expenses (dental, vision, co-pays, deductibles). HSA withdrawals are now capped at
  Medicare costs + this amount per year, enforced as an LP constraint. Pre-Medicare years:
  only `setMedicalExpenses` amount is eligible (Medicare costs are zero). Without this call,
  HSA is limited to Medicare costs only; pre-Medicare HSA withdrawals default to zero — the
  tax-law-correct conservative default. Available in TOML via `optimization_parameters.other_medical_expenses`
  and in the UI under **Run Options → Health Insurance → Other Qualified Medical Expenses**,
  alongside Medicare and ACA settings.

#### HSA depletion graph

- **Stacked withdrawals**: `showHSA()` now splits the withdrawal area into a Medicare portion
  (attributed to Medicare costs, distinct color) and a `QME` portion (remaining qualified
  medical withdrawals),
  using stacked filled areas. Zero-valued series are suppressed from the legend.

#### HSA reporting

- **Cash Flow cleanup**: Removed `HSA→Medicare` from the **Cash Flow** worksheet so rows keep
  the balancing identity.
- **New HSA worksheet**: Added a dedicated **HSA** worksheet with `Medicare`, `QME`,
  `HSA total wdrwl`, `HSA→Medicare`, and `HSA→QME`, plus per-individual HSA balances,
  contributions, and withdrawals.

--- 

### Version 2026.05.06

#### Summary sheet refactor

- **Structured sections**: the Summary worksheet now groups entries under labelled section dividers
  (*Overview*, *Spending & income*, *Taxes & premiums*, *Partial bequest*, *Final bequest*,
  *Plan & solver*) for easier reading and navigation.
- **Currency formatting**: a `_parse_usd_string` helper centralises conversion of `u.d()` output
  to float so that numeric cells are stored as numbers rather than strings, enabling Excel
  formulas and sorting.
- **Reports UI**: the Reports page and its session-state keys updated in lock-step with the new
  export structure.
- **Tests**: `tests/test_export.py` and `tests/test_summary.py` each extended with 15 additional
  assertions covering section headers and numeric cell types.

#### Solver option round-trip fix

- **`SOLVER_UI_PASSTHROUGH_KEYS`**: a single authoritative list in `config/ui_bridge.py` of all
  solver options that are copied verbatim between the TOML/Plan solver options and the flat UI
  case dict. Options with dedicated UI translations (`withMedicare`, `withACA`, `withDecomposition`,
  `previousMAGIs`, etc.) are handled separately and excluded from the list.
- **Lifecycle fix**: solver options were not reliably preserved across UI navigation; the new
  passthrough mechanism ensures a lossless round-trip for all 30+ passthrough keys.
- **Tests**: 111 new assertions in `tests/test_config_ui_bridge.py` covering round-trip
  correctness for every passthrough key.

#### Bug fixes

- **Empty spending profile navigation**: fixed a UI crash when navigating to the Financial Profile
  page with an uninitialised profile.
- **Goals page alignment**: minor layout fix after the `maxHybrid` removal left a misaligned
  control row.

#### Savings Retention Margin chart

- **`showRetentionMargin()`** replaces `showSavingsRetentionRate()`: the new chart plots the annual
  difference between the savings retention rate and the real break-even threshold (in percentage
  points), so the zero axis is the neutral boundary. Blue bars indicate years where real wealth
  is growing; red bars indicate years where it is shrinking. The break-even line is no longer
  overlaid — it *is* the axis.
- **Log scale removed**: the log-scale toggle added no actionable information to the diverging
  chart and has been removed from the UI.
- **`plot_retention_margin`** added to both the Plotly and Matplotlib backends; the old
  `plot_savings_retention_rate` function has been removed from all backends and the base class.

---

### Version 2026.05.04

#### Remove maxHybrid objective

- **`maxHybrid` removed**: The hybrid objective (blending spending and bequest via a weight
  parameter `h`) has been removed. Because the LP objective is linear, it always drives
  spending to an extreme (floor or cap), providing no useful intermediate behavior that
  `maxSpending` with a bequest constraint or `maxBequest` with a spending constraint cannot
  achieve more directly.
- **Spending profile now always bilateral**: The profile slack (±slack%) is enforced as a
  symmetric bilateral bound for both `maxSpending` and `maxBequest`. The former one-way
  (floor-only) treatment that existed for `maxHybrid` is gone with the objective.
- **Options removed**: `spendingWeight` and `spendingFloor` solver options are no longer
  accepted (passing them logs an "unknown option" warning as with any unrecognized key).
- **`fixedSpending` and `spendingSlack` unchanged**: Both still work as before.
- **UI**: Goals page now offers two objectives (*Net spending* and *Bequest*) with no weight
  or floor controls; profile slack help text updated accordingly.
- **Schema**: `spendingWeight` and `spendingFloor` fields removed from the config schema.
- **Tests**: `tests/test_hybrid_objective.py` removed (214 lines, no replacement needed).

---

### Version 2026.05.03

#### ACA improvements for couples

- **Automatic SLCSP scaling**: When one spouse transitions from an ACA marketplace plan to
  Medicare, the benchmark Silver plan premium (`slcsp_annual`) is automatically scaled down
  to the remaining spouse's individual plan using the CMS age rating curve (45 CFR 147.102).
  The scaling factor is `f_younger / (f_older + f_younger)`, evaluated at the transition year,
  and ranges from roughly 37–48% of the combined household premium depending on the age gap.
  Users should set `slcsp_annual` to the **combined household premium**; no manual adjustment
  is needed for the transition years.
- **Age rating table**: CMS age rating factors (ages 0–64) are now stored in
  `src/owlplanner/data/aca_age_rating.py` alongside other regulatory tables.
- **`start_year` validation**: `setACA(start_year=N)` now raises a `ValueError` with a clear
  message if `N` is between 1 and 1999, catching the common mistake of entering an offset
  (e.g. `3`) instead of a 4-digit calendar year (e.g. `2029`). The UI field label and help
  text have been updated accordingly.
- **Tests**: 7 new tests (`TestACACoupleSLCSPScaling` and offset guard tests); total 35 in
  `tests/test_aca.py`.

---

### Version 2026.05.01

#### SPIA (Single Premium Immediate Annuity)

- **`addSPIA(individual, buy_year, premium, monthly_income, indexed, survivor_fraction)`**:
  Adds a qualified SPIA funded by a tax-deferred IRA rollover. Premium is deducted from the
  tax-deferred account in the buy year (non-taxable transfer); income begins in the same year
  and is fully taxable as ordinary income. Optional CPI indexing and joint-and-survivor fraction
  for couples. Multiple SPIAs per plan supported. Pre-purchased annuities (`buy_year` before plan
  start) generate income from year 0 with no premium deduction.
- **UI**: New *SPIA* section on the Fixed Income page with data editor for annuitant, buy year,
  premium, monthly income, CPI-linked flag, and survivor fraction (couples only).
- **Schema**: `spia_individuals`, `spia_buy_years`, `spia_premiums`, `spia_monthly_incomes`,
  `spia_indexed`, `spia_survivor_fractions` fields added to `[fixed_income]`.
- **Docs**: `PARAMETERS.md` SPIA section; `modeling-capabilities.md` SPIA row.
- **Tests**: 11 tests in `tests/test_spia.py` including TOML round-trip and clone round-trip.

#### Retirement Efficiency Score (RES) — experimental

- **`compute_res` / `compute_cvar`** (new, public API): Compute the floor-capped CVaR and the
  Retirement Efficiency Score (RES = committed spending above floor / CVaR) across the efficient
  frontier. `rho_star` is the success rate that maximizes RES. Exported from `owlplanner`.
- RES is shown as an experimental expander in the Spending Optimization UI for **historical
  scenarios only**. MC RES is suppressed — the lognormal tail structure produces unreliable ρ\*.
- **Docs**: `modeling-capabilities.md` RES row.

#### SC loop convergence refactor

- Convergence logic extracted into helper methods (`_check_obj_convergence`, `_check_cycle`,
  `_check_stagnation`, `_check_max_iterations`) and `_build_sc_loop_policy()` for clarity.
- Tolerance formula: `tol = max(abs_tol, rel_tol × scale)` where scale adapts to objective
  magnitude. Medicare gate (skip iteration 0 for convergence) correctly preserved.
- **Tests**: 5 tests in `tests/test_sc_convergence_helpers.py`.

#### ACA start year

- `aca_start_year`: Calendar year when ACA coverage begins. Years before this are treated as
  employer-covered (zero ACA cost). Default `0` = ACA applies from plan start.
- Documented in `PARAMETERS.md` and `modeling-capabilities.md`.
- **Tests**: 5 tests added for ACA start year.

#### Bug fixes

- **Correlation matrix**: Division by zero for constant-return series now handled correctly
  with masking; avoids inf/nan in rate model fitting.
- **SPIA annuitant lookup**: Typo in annuitant name now logged as a warning and row skipped,
  rather than silently misassigned to individual 1.

#### Scripts

- `owlplanner.sh` / `owlplanner.cmd`: Launcher script improvements - update on changes as opposed to cloud.

---

### Version 2026.04.27

- Improve detection of convergence anomalies in MC (issue#119).
- Upgrade requirement on gitpython to address vulnerability.

---

### Version 2026.04.21

#### Longevity risk in stochastic spending + parallel plan solving

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

### Version 2026.04.08

#### Stochastic spending optimization + stress-test refactoring

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

### Version 2026.04.07

#### SS claiming age optimization (`withSSAges`)

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

### Version 2026.04.02

#### New objective: `maxHybrid` — blended spending and bequest

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

### Version 2026.03.29

#### Worksheets: age columns, real-dollar display, and solver time limit

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

### Version 2026.03.26

#### Breaking change: HFP person sheets require all columns

- Each person worksheet must include every time-horizon column: `year`, `anticipated wages`,
  `other inc`, `net inv`, `taxable ctrb`, `401k ctrb`, `Roth 401k ctrb`, `IRA ctrb`,
  `Roth IRA ctrb`, `HSA ctrb`, `Roth conv`, `big-ticket items`. Omitting a column is an error.
- Clearer `ValueError` listing missing headers; legacy `other inc.` still normalized.
- All `examples/HFP_*.xlsx` workbooks and `HFP_template.xlsx` updated.
- **Docs**: `PARAMETERS.md` HFP section; Documentation (Financial Profile) aligned.
- **Tests**: `tests/test_timelists.py` expects errors for missing required columns.

---

### Version 2026.03.24

#### Worksheets: optional ages and hide-zero columns

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

### Version 2026.03.12

#### Medicare Part D

- Part D premiums (IRMAA surcharges, same MAGI brackets as Part B) now included by default.
- `medicarePartDBasePremium`: optional monthly base premium per person (default `0`).
- `includeMedicarePartD` solver option (default `true`); set `false` for other drug coverage
  (employer plan, VA, etc.).
- Schema, `PARAMETERS.md`, `modeling-capabilities.md`, `owl.tex`, and Run Options UI updated.

---

### Version 2026.03.11

#### Decomposition fixes

- Benders: skip zm pre-fixing when both individuals are already on Medicare at plan start;
  prevents SP LP infeasibility on later iterations.
- Benders: gap check and stall-detection added after the master MIP step.

---

### Version 2026.03.10

#### LTCG and NIIT exact MIP formulations

- **`withLTCG="optimize"`**: Binary variables (`zl`) replace the SC-loop heuristic for LTCG
  bracket assignment, giving provably correct long-term capital gains tax rates.
- **`withNIIT="optimize"`**: Binary selection (`zj`) on whether MAGI exceeds the \$200k/\$250k
  NIIT threshold. Most effective combined with `withLTCG="optimize"`.
- Both modes exposed as expert toggles in the UI (Advanced Options).
- **Tests**: `tests/test_ltcg_lp.py` (6 tests) and `tests/test_niit_milp.py` (6 tests).

#### MIP decomposition (`withDecomposition`)

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

#### HiGHS direct API

- HiGHS is now called directly via `highspy`; the `scipy.optimize.linprog` proxy is removed.
- **PuLP/CBC and PuLP/HiGHS removed**: only HiGHS (direct) and MOSEK are supported.
- `abcapi.py`: `ConstraintMatrix.to_csr()` returns HiGHS rowwise CSR format. Warm-start via
  `_highs_warm_start`.

#### `owlcli`: schema-driven solver options

- `SolverOptions` Pydantic model in `schema.py` is the single source of truth; used by TOML
  load, `plan_bridge`, and the CLI.
- **`--help-solver-options`**: Parses `PARAMETERS.md` at runtime — always in sync with docs.
- **`--solver-opt KEY=VALUE`**: Override any solver option on the command line.
- **Solver choices**: `--solver` now accepts only `default`, `HiGHS`, and `MOSEK`.

#### UI and configuration

- Run Options: expert toggles for *Optimize LTCG brackets* and *Optimize NIIT*; *MIP decomposition*
  radio (`none` / `sequential` / `benders`).
- `withDecomposition` wired through `config_to_ui` / `ui_to_config`; legacy boolean `True` coerced
  to `"sequential"`.
- **`PARAMETERS.md`**: `withDecomposition` and `bendersMaxIter` entries added.

---

### Version 2026.03.09

#### ACA marketplace (pre-65) UI exposure

- **Run Options**: New *ACA Marketplace (Pre-65)* section with SLCSP benchmark premium input.
  *Optimize ACA (expert)* toggle in Advanced Options (enabled only when SLCSP > 0).
- Config/UI bridge: `aca_settings` and `withACA` wired through `config_to_ui`, `ui_to_config`,
  and `genDic`.
- **Example**: `Case_morgan` illustrates ACA modeling for a pre-65 retiree.
- **Documentation**: ACA added to the self-consistent loop description.

#### HSA accounts (fourth savings account type)

- HSA balances tracked alongside taxable, tax-deferred, and tax-free accounts (`j=3`).
- Pre-tax contributions reduce ordinary income, SS provisional income, and MAGI. Contributions
  zeroed at Medicare enrollment age (IRC §223). All withdrawals treated as qualified (tax-free).
- Non-spouse heirs include the full HSA balance in ordinary income (IRC §223(f)(8)(B)); bequest
  discounted accordingly.
- `setAccountBalances(hsa=...)` and `setHSA(balances, medicare_ages)` convenience method.
  Account allocation, asset composition, and Fixed Income page updated.
- **Tests**: 9 tests in `tests/test_hsa.py`.

---

### Version 2026.03.07

#### `"net inv"` column in HFP

- New optional `net inv` column (net investment income from rent or trust distributions) in the
  Wages and Contributions spreadsheet. Enters cash-flow, taxable-income, SS-taxability, and MAGI
  constraints; counted in NII for NIIT. Backward compatible (defaults to zero when absent).
- `"net inv"` appears in each individual's Sources sheet in the workbook.

#### Pension survivor benefits

- **Joint-and-survivor (J&S) option**: Surviving spouse receives a configurable fraction (0–100%)
  of the primary's pension after death. Config: `pension_survivor_fraction`; UI: Fixed Income page.

---

### Version 2026.03.05

#### Rate models

- **`lognormal`** (new): Correlated log-normal with user-specified arithmetic means, volatilities,
  and correlations. Returns bounded below −100%, consistent with Geometric Brownian Motion.
- **`histolognormal`** (new): Fits a correlated log-normal to the selected historical window.
  History-grounded alternative to `lognormal`.
- **`var`** (new): VAR(1) model fitted by OLS on a historical window. Captures year-to-year serial
  correlations across all four asset classes; optional spectral shrinkage for stationarity.
- `bootstrap_sor` and `var` now exposed in the Rates Selection and Monte Carlo pages.
- **MC guard fix**: `runMC()` uses `rateModel.deterministic` attribute instead of a hardcoded name
  check.

#### Rates Selection UI redesign

- Constant-preset and varying-method selectors are now `st.selectbox` widgets with a concise
  description caption surfaced from each model's metadata.

#### Bug fixes

- `reverse_sequence` and `roll_sequence` were silently ignored in non-augmented historical range
  runs; both now read from session state and passed correctly.
- Run Options page warns when the minimum balance constraint may cause infeasibility.
- **Rename**: *Simulations* → *Stress Tests* throughout.

#### Tests

- `test_rate_model_var.py`: 24 tests (shape, reproducibility, fitting, Cholesky, shrinkage,
  parameter validation, reverse/roll, MC integration).

---

### Version 2026.02.24

#### HFP (Household Financial Profile)

- **Optional `"other inc"` column**: Other ordinary income (consulting, royalties, etc.) in the
  wages and contributions table. Backward compatible; `scripts/add_other_inc_column.py` migrates
  existing files.
- **Reports page**: Warning shown when HFP values were edited in the UI (case file alone cannot
  reproduce the run).

#### Configuration

- Case-insensitive `case_` prefix check when saving TOML (issue #96).

#### Code organization

- `pension.py` and `spending.py` extracted from `plan.py`. SS tax logic moved to `tax2026.py`;
  `setSocialSecurity` logic to `socialsecurity.py`; gamma/rate transforms to `rates.py`;
  oscillation detection to `utils.py`.

---

### Version 2026.02.23

#### Social Security accuracy

- **Dynamic SS taxability fraction**: `Psi_n` now computed each SC iteration from the IRS
  provisional income formula (MFJ: \$32k/\$44k; single: \$25k/\$34k) with 30% damping for
  convergence, replacing a fixed 85%. Retirees with lower income get more accurate (lower) SS taxation.
- **`withSSTaxability`**: Pin `Psi_n` to a fixed value in [0, 0.85] (replaces `tax_fraction`
  parameter to `setSocialSecurity()`).
- **FRA table fix**: `getFRAs()` now returns the correct Full Retirement Age for birth years
  1938–1942 (65+2/12 to 65+10/12 per SSA table).

#### SS trim

- `social_security_trim_pct > 0` without `social_security_trim_year` now raises an error instead
  of silently defaulting to 10 years from now.
- SS trust-fund exhaustion default changed to 2033 (SSA Trustees Report projection).
- "Starting year" widget greyed out when reduction percentage is 0.

---

### Version 2026.02.20

#### UI

- **Create Case redesign**: Three columns (create, upload, load example) when no case is active;
  collapsible expander when a case is already loaded.
- **Inline HFP uploader**: After case creation, an HFP upload widget appears directly on the
  Create Case page.
- **Streamlit compatibility**: Version pin and `altair < 5` restriction removed from
  `requirements.txt`.

---

### Version 2026.02.19

#### Rate models

- **`BuiltinRateModel` decomposition**: Single dispatcher replaced by 8 concrete `BaseRateModel`
  subclasses. `BuiltinRateModel` shim preserves backward compatibility.
- **Stochastic UI fix**: Builtin rate model now accepts config-style parameter names
  (`standard_deviations`, `correlations`) in addition to API names.
- **`getRatesDistributions`** (issue #92): Returns percent by default; accepts optional `df=`
  parameter for user-supplied DataFrames.
- **DataFrame rate model** (issue #92): Column names standardized (T-Notes/T-Bills); `in_percent`
  parameter replaces heuristic; display names aligned with column names.
- Rates UI: label `'fixed'` renamed to `'constant'`.

#### Social Security

- SS trim (reduction from a given year onward): config, schema, UI bridge, and Fixed Income page.

---
