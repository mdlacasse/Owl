This document describes all parameters used in Owl TOML configuration files. The TOML file structure is organized into sections for clarity, and can be consumed by both the UI and CLI applications.

**Note:** Throughout this document, `N_i` refers to the number of individuals in the plan (1 for single, 2 for married).

-------

## :orange[Root level parameters]

These parameters are defined at the root level of the TOML file (not within any section).

| Parameter | Type | Description |
|-----------|------|-------------|
| `case_name` | string | Name of the case/plan |
| `description` | string | A short text describing the purpose of the case |

-------

## :orange[[basic_info]]

Basic information about the individuals in the plan.

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filing status. Valid values: `"single"`, `"married"` |
| `names` | list of strings | Names of the individuals in the plan. Must contain 1 or 2 names. Length determines `N_i` |
| `date_of_birth` | list of `N_i` ISO dates | Date of birth for each individual in ISO format (e.g., `"1967-01-15"`). Defaults to `"1965-01-15"` if not specified |
| `life_expectancy` | list of `N_i` integers | Life expectancy in years for each individual |
| `start_date` | string | Start date of the plan (e.g., `"01-01"`, `"01/01"`, `"2026-01-01"`). Only the month and day are used; the plan always starts in the current year. Defaults to `"today"` if not specified |

-------

## :orange[[savings_assets]]

Initial account balances and beneficiary information.

| Parameter | Type | Description |
|-----------|------|-------------|
| `taxable_savings_balances` | list of `N_i` floats | Initial balance in taxable accounts for each individual (in thousands of dollars) |
| `tax_deferred_savings_balances` | list of `N_i` floats | Initial balance in tax-deferred accounts (e.g., 401k, traditional IRA) for each individual (in thousands of dollars) |
| `tax_free_savings_balances` | list of `N_i` floats | Initial balance in tax-free accounts (e.g., Roth IRA, Roth 401k) for each individual (in thousands of dollars) |
| `hsa_savings_balances` | list of `N_i` floats | *(Optional)* Initial balance in Health Savings Accounts (HSA) for each individual (in thousands of dollars). Defaults to `[0.0]` (or `[0.0, 0.0]` for married). HSA contributions must stop at Medicare enrollment (~age 65); see `HSA ctrb` column in the HFP file |
| `beneficiary_fractions` | list of 3 or 4 floats | *(Married only)* Fraction of each account type (taxable, tax-deferred, tax-free, and optionally HSA) bequeathed to the surviving spouse. Each value should be between 0.0 and 1.0. The HSA fraction defaults to `1.0` (spouse inherits intact, per IRS rules). A 3-element list is accepted for backward compatibility and is automatically extended with `1.0` for HSA |
| `spousal_surplus_deposit_fraction` | float | *(Married only)* Fraction of surplus to deposit in the second spouse's taxable account. Value between 0.0 and 1.0 |

-------

## :orange[[household_financial_profile]]

Reference to the **Household Financial Profile (HFP)** workbook: wages, contributions, Roth activity, and optional household debts and fixed assets. Scalar balances and solver targets stay in the TOML file; year-by-year cash flows live in the HFP.

| Parameter | Type | Description |
|-----------|------|-------------|
| `HFP_file_name` | string | Filename of the HFP workbook (typically `.xlsx`). Resolved relative to the directory of the case TOML when loading. Use `"None"` if the case has no HFP (wages and contributions are then zero unless set another way). |

### HFP workbook layout

- **Person sheets (required):** One worksheet per individual. The sheet name must **exactly** match the corresponding entry in `[basic_info]` `names` (e.g. `Jack` and `Jill`).
- **Years:** On read, each person’s sheet is trimmed to calendar years from five years before the **current** year through that person’s last plan year (from date of birth and `life_expectancy`). Rows with `year` outside that window are dropped. **Any missing calendar year inside that window—including the terminal year—is inserted with zeros**; you do not need a spreadsheet row for every year. After loading, the in-memory table for each person always ends on that person’s final plan year.
- **Column headers:** Use the **exact** strings below (lowercase; column order may vary). **Every column must be present** on each person sheet; enter `0` where a concept does not apply. The legacy header `other inc.` is accepted and normalized to `other inc`. **Any other column** on a person sheet (including helper or calculated columns), and blank or `Unnamed` columns, are **dropped** when the file is read; they are not preserved in the planner. A blank template is [HFP_template.xlsx](https://github.com/mdlacasse/Owl/blob/main/examples/HFP_template.xlsx?raw=true).
- **Units:** All numeric cells on person sheets are **nominal dollars** (full dollars), not thousands. This is independent of `[solver_options]` `units` (`k` / `1` / `M`), which applies to amounts in the TOML case file and solver options such as `bequest` and `netSpending`.
- **Optional household sheets:** The workbook may include sheets named **`Debts`** and **`Fixed Assets`**. If omitted, debts and fixed assets are treated as empty. See column lists under *Optional sheets* below.
- **Roth conversion caps:** When `[solver_options]` `maxRothConversion` is `"file"`, per-year limits are taken from the HFP time lists (see solver options).

#### Person sheet columns (all required)

| Header | Meaning |
|--------|---------|
| `year` | Calendar year |
| `anticipated wages` | Expected annual wages (gross minus tax-deferred contributions through payroll), nominal $ |
| `other inc` | Other ordinary income (e.g. part-time work, consulting, royalties), nominal $ |
| `net inv` | Net investment income from rent or trust distributions treated as ordinary income; also feeds NIIT, nominal $ |
| `taxable ctrb` | Contributions to taxable / after-tax investment accounts, nominal $ |
| `401k ctrb` | Traditional employer plan / 401(k) deferrals, nominal $ |
| `Roth 401k ctrb` | Roth employer plan contributions, nominal $ |
| `IRA ctrb` | Traditional IRA contributions, nominal $ |
| `Roth IRA ctrb` | Roth IRA contributions, nominal $ |
| `HSA ctrb` | HSA contributions, nominal **dollars** (not $k). Pre-tax; reduce AGI, MAGI, and SS provisional income. Values after Medicare enrollment (~65) are ignored. 2026 IRS limits: $4,400 (self-only) / $8,750 (family); +$1,000 catch-up if 55+ |
| `Roth conv` | Roth conversions from tax-deferred accounts, nominal $ |
| `big-ticket items` | Large one-off expenses or after-tax inflows (may be negative), nominal $ |

#### Optional sheet `Debts`

Columns: `active`, `name`, `type`, `year`, `term`, `amount`, `rate`. Allowed `type` values: `loan`, `mortgage`.

#### Optional sheet `Fixed Assets`

Columns: `active`, `name`, `type`, `year`, `basis`, `value`, `rate`, `yod`, `commission`. Allowed `type` values: `collectibles`, `fixed annuity`, `precious metals`, `real estate`, `residence`, `stocks`.

-------

## :orange[[fixed_income]]

Pension and Social Security information.

| Parameter | Type | Description |
|-----------|------|-------------|
| `pension_monthly_amounts` | list of `N_i` floats | Monthly pension amount for each individual (in dollars). Use `0` if no pension |
| `pension_ages` | list of `N_i` floats | Age at which pension starts for each individual |
| `pension_indexed` | list of `N_i` booleans | Whether each pension is indexed for inflation |
| `pension_survivor_fraction` | list of `N_i` floats | Fraction of pension (0–1) continuing to surviving spouse. 0 = single-life. Typical: 0, 0.5, 0.75, 1.0 |
| `social_security_pia_amounts` | list of `N_i` integers | Primary Insurance Amount (PIA) for Social Security for each individual (in dollars) |
| `social_security_ages` | list of `N_i` floats | Age at which Social Security benefits start for each individual |
| `social_security_trim_pct` | integer | *(Optional)* Percentage reduction applied to Social Security benefits from `social_security_trim_year` onward. Range 0–100. Use to model trust-fund shortfall scenarios (e.g. 23). Omit or set to 0 for no reduction |
| `social_security_trim_year` | integer | *(Required when `social_security_trim_pct > 0`)* Calendar year when the SS benefit reduction begins. Default UI value is 2033 (SSA Trustees Report projection for OASI exhaustion). Must be supplied alongside `social_security_trim_pct` |

-------

## :orange[[rates_selection]]

Investment return rates and inflation assumptions.

### :orange[Units of measure]

Rates use standard financial conventions:

| Quantity | UI & config | Plan (internal) | Convention |
|----------|-------------|-----------------|------------|
| Returns (e.g., S&P 500) | Percent: `7` = 7% | Decimal: `0.07` | Finance convention: returns in percent |
| Volatility (standard deviation) | Percent: `17` = 17% | Decimal: `0.17` | Finance convention: volatility in percent |
| Correlations | Coefficient: `0.4` = 0.4 | Same: `0.4` | Pearson coefficient, range -1 to 1 (standard in statistics and finance) |

*Correlations are not expressed in percent.* The Pearson correlation coefficient ranges from -1 (perfect negative) to +1 (perfect positive). Expressing it as a percent is non-standard; the decimal coefficient is the universal convention in finance and statistics.

| Parameter | Type | Description |
|-----------|------|-------------|
| `heirs_rate_on_tax_deferred_estate` | float | Tax rate (as percentage, e.g., `30.0` for 30%) that heirs will pay on inherited tax-deferred and HSA accounts. Non-spouse HSA beneficiaries must include the full inherited HSA balance as ordinary income (IRC §223(f)(8)(B)) |
| `dividend_rate` | float | Dividend rate as a percentage (e.g., `1.72` for 1.72%) |
| `obbba_expiration_year` | integer | Year when the OBBBA (One Big Beautiful Bill Act) provisions expire. Default is `2032` |
| `method` | string | Method for determining rates. Valid values: `"trailing-30"`, `"optimistic"`, `"conservative"`, `"user"`, `"historical"`, `"historical average"`, `"gaussian"`, `"histogaussian"`, `"lognormal"`, `"histolognormal"`, `"bootstrap_sor"`, `"var"`, `"garch_dcc"`, `"dataframe"` |

**Deprecated aliases:** `stochastic` and `histochastic` are deprecated aliases for `gaussian` and `histogaussian` respectively; and `default` is an alias for `trailing-30`. All are accepted for backward compatibility but new cases should use the canonical names.

### :orange[Conditional parameters based on `method`]

#### :orange[For method = "user", "gaussian", or "lognormal"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `values` | list of 4 floats | Mean returns in percent: [S&P 500, Corporate Baa bonds, 10-year Treasury notes, Inflation] (e.g., `7` for 7%) |

#### :orange[For method = "gaussian" or "lognormal"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `standard_deviations` | list of 4 floats | Volatility in percent for each rate type (e.g., `17` for 17% annualized standard deviation) |
| `correlations` | list of 6 floats | Pearson correlation coefficient (range -1 to 1) for upper triangle: (1,2), (1,3), (1,4), (2,3), (2,4), (3,4). Standard representation in finance and statistics. |

#### :orange[For method = "gaussian", "histogaussian", "lognormal", "histolognormal", "bootstrap_sor", "var", or "garch_dcc"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `rate_seed` | integer | Random seed for reproducible stochastic rates |
| `reproducible_rates` | boolean | Whether stochastic rates should be reproducible |

#### :orange[For method = "historical", "historical average", "histogaussian", "histolognormal", "bootstrap_sor", "var", or "garch_dcc"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | integer | Starting year for historical data range (must be between 1928 and 2025) |
| `to` | integer | Ending year for historical data range (must be between 1928 and 2025, and greater than `from`). `garch_dcc` requires at least 15 years of data (`to - from ≥ 15`) |

#### :orange[For method = "var"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `shrink` | boolean | *(Optional)* When `true`, applies spectral shrinkage to the VAR(1) coefficient matrix to improve stability and reduce estimation error, especially for short historical windows. Default is `false` |

#### :orange[For method = "bootstrap_sor"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `bootstrap_type` | string | Type of bootstrap resampling. Valid values: `"iid"` (independent draws), `"block"`, `"circular"`, `"stationary"`. Default is `"iid"` |
| `block_size` | integer | Block length for block/circular/stationary bootstraps. Ignored when `bootstrap_type = "iid"`. Default is `1` |
| `crisis_years` | list of integers | *(TOML only)* Calendar years to overweight in sampling (e.g. `[1929, 2008]`) |
| `crisis_weight` | float | *(TOML only)* Sampling multiplier applied to crisis years. Default is `1.0` (no overweighting) |

#### :orange[For method = "historical", "histogaussian", "histolognormal", "bootstrap_sor", "var", "garch_dcc", "gaussian", or "lognormal" (varying rates only)]
| Parameter | Type | Description |
|-----------|------|-------------|
| `reverse_sequence` | boolean | If true, reverse the rate sequence along the time axis (e.g. last year first). Default is `false`. Ignored for fixed/constant rate methods. Used for both single-scenario and Historical Range runs. |
| `roll_sequence` | integer | Number of years to roll (shift) the rate sequence; positive shifts toward the end, values wrap. Default is `0`. Ignored for fixed/constant rate methods. Used for both single-scenario and Historical Range runs. |

**Note:** `from`/`to` are stored for all methods in saved case files. Methods that do not use them ignore these fields. When running Historical Range, each year in the range uses the historical rate sequence starting at that year, with `reverse_sequence` and `roll_sequence` applied to each sequence.

-------

## :orange[[asset_allocation]]

Asset allocation strategy and how it changes over time.

| Parameter | Type | Description |
|-----------|------|-------------|
| `interpolation_method` | string | Method for gliding the allocation from initial to final values over time. `"linear"` = straight-line transition (equal steps each year). `"s-curve"` = smooth sigmoid (slow change at first, fast in the middle, slow again at the end), controlled by `interpolation_center` and `interpolation_width`. |
| `interpolation_center` | float | For `"s-curve"`: the year (measured from the start of the plan) at which the transition is halfway complete — the inflection point of the sigmoid. Ignored for `"linear"`. |
| `interpolation_width` | float | For `"s-curve"`: controls the steepness of the transition. Smaller values produce a sharper change; larger values spread the change over more years (±`width` years around the center). Ignored for `"linear"`. |
| `type` | string | How the allocation is defined. `"individual"` — each person has their own set of ratios applied identically to all their accounts. `"account"` — separate ratios for each account type (taxable, tax-deferred, tax-free, HSA), allowing more aggressive allocation in tax-free accounts. `"spouses"` — a single shared set of ratios applied across all accounts and both spouses simultaneously, reducing the number of parameters needed. *(Note: `"spouses"` is only available via the Python API, not the Streamlit UI.)* |

### :orange[Conditional parameters based on `type`]

#### :orange[For type = "account"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `taxable` | 3D array | Asset allocation bounds for taxable accounts. Structure: `[[[initial_stocks, initial_bonds, initial_tnotes, initial_cash], [final_stocks, final_bonds, final_tnotes, final_cash]]]` for each individual. The four classes are: S&P 500 (stocks), Corporate Baa bonds, 10-year Treasury notes, and cash/inflation |
| `tax-deferred` | 3D array | Asset allocation bounds for tax-deferred accounts (same structure as `taxable`) |
| `tax-free` | 3D array | Asset allocation bounds for tax-free accounts (same structure as `taxable`) |
| `hsa` | 3D array | *(Optional)* Asset allocation bounds for HSA accounts (same structure as `taxable`). When omitted, HSA uses the same allocation as `tax-free` |

#### :orange[For type = "individual"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `generic` | 3D array | Asset allocation bounds, one `[initial, final]` pair per individual. Structure: `[[[s0, b0, t0, c0], [sf, bf, tf, cf]], [[s0, b0, t0, c0], [sf, bf, tf, cf]]]` for a married couple (two pairs), or `[[[s0, b0, t0, c0], [sf, bf, tf, cf]]]` for a single. All four accounts (taxable, tax-deferred, tax-free, HSA) use the same ratios for a given individual. |

#### :orange[For type = "spouses" *(Python API only)*]
| Parameter | Type | Description |
|-----------|------|-------------|
| `generic` | 2D array | A single `[initial, final]` allocation pair shared by both spouses and applied uniformly across all their accounts. Structure: `[[s0, b0, t0, c0], [sf, bf, tf, cf]]`. Simpler to configure than `"individual"` when both spouses follow the same investment strategy. |

**Note:** All allocation values are percentages that should sum to 100 for each time point. The four asset classes are: stocks (S&P 500), corporate bonds (Baa), 10-year Treasury notes, and cash/inflation (e.g. TIPS).

-------

## :orange[[optimization_parameters]]

Parameters controlling the optimization objective and spending profile.

| Parameter | Type | Description |
|-----------|------|-------------|
| `spending_profile` | string | Type of spending profile. Valid values: `"flat"`, `"smile"` |
| `surviving_spouse_spending_percent` | integer | Percentage of spending amount for the surviving spouse (0-100). Default is `60` |
| `objective` | string | Optimization objective. Valid values: `"maxSpending"`, `"maxBequest"` |

### :orange[Conditional parameters for spending_profile = "smile"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `smile_dip` | integer | Percentage to decrease spending during the "slow-go" years (0-100). Default is `15` |
| `smile_increase` | integer | Percentage to increase (or decrease if negative) spending over the time span (-100 to 100). Default is `12` |
| `smile_delay` | integer | Number of years from the start before spending begins to decrease (0 to plan duration - 2). Default is `0` |

**Note:** The "smile" profile creates a spending pattern that starts high, decreases during middle years, and increases again later in retirement.

-------

## :orange[[aca_settings]]

*(Optional)* ACA marketplace health insurance for pre-65 years. When omitted or `slcsp_annual = 0`, no ACA costs are modeled.

| Parameter | Type | Description |
|-----------|------|-------------|
| `slcsp_annual` | float | Annual benchmark Silver plan (SLCSP) premium in today's dollars (in `units`). Set to 0 to disable ACA. Inflated internally by the plan's inflation factor. |

**Note:** ACA costs apply only in years when at least one individual is under 65 and within their planning horizon. The Premium Tax Credit (PTC) is computed from MAGI and Federal Poverty Level; net cost = SLCSP minus PTC. Use `withACA` in `[solver_options]` to choose loop (default) or optimize mode.

-------

## :orange[[solver_options]]

Options controlling the optimization solver and constraints.

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `absTol` | float | *(Advanced)* Absolute convergence tolerance for the self-consistent loop objective. | `100` |
| `amoConstraints` | boolean | *(Advanced)* Whether to use at-most-one (AMO) constraints in the optimization. | `true` |
| `amoRoth` | boolean | *(Advanced)* Whether to enforce at-most-one (AMO) constraints preventing simultaneous Roth conversions and tax-free withdrawals. | `true` |
| `amoSurplus` | boolean | *(Advanced)* Whether to enforce XOR constraints preventing simultaneous surplus deposits and withdrawals from taxable or tax-free accounts. | `true` |
| `bequest` | float | Target bequest value in today's dollars (in `units`). Used when `objective = "maxSpending"`. | `1` (if omitted with `maxSpending`) |
| `bigMamo` | float | *(Advanced)* Big-M value for at-most-one (AMO) constraints (mutually exclusive operations). Should exceed any individual withdrawal, conversion, or surplus deposit. | `5e7` |
| `bigMaca` | float | *(Advanced)* Big-M value for the upper bound on the above-400%-FPL ACA MAGI bracket (when `withACA = "optimize"`). Should exceed any plausible annual MAGI. | `5e7` |
| `bigMss` | float | *(Advanced)* Big-M value for the Social Security taxability MIP formulation (when `withSSTaxability = "optimize"`). Should exceed provisional income and related quantities. | Same as `bigMamo` |
| `epsilon` | float | *(Advanced)* Lexicographic weight added to the objective to break ties. Adds a linearly increasing penalty to Roth conversions (earlier years are cheaper) to frontload conversions, and when `N_i = 2`, also penalizes withdrawals of spouse 2 to favor withdrawals from spouse 1. Use a very small value so the primary objective dominates. | `1e-8` |
| `gap` | float | *(Advanced)* Relative MILP gap used by solvers and to scale convergence tolerances. | `1e-4` (default); if `withMedicare = "optimize"` and unset, set to `3e-3` (or `3e-2` when `maxRothConversion <= 15`) |
| `maxIter` | integer | *(Advanced)* Maximum number of iterations for the self-consistent loop. Must be at least 1. | `29` |
| `maxRothConversion` | float or string | Maximum annual Roth conversion amount (in `units`). Use `"file"` to take per-year limits from time lists; omit for no cap (except last year). | No cap unless provided |
| `minTaxableBalance` | array | Minimum taxable account balance per spouse (in today's `units`). Values are indexed for inflation. Constraints apply from year 2 through each individual's life horizon. | Omit for no minimum |
| `maxTime` | float | *(Advanced)* Per-iteration solver time limit in seconds. The self-consistent loop re-solves with warm-starting, so shorter limits often converge faster on hard MILP cases. Increase only if individual solves are being cut off before finding a first feasible solution. | `180` |
| `netSpending` | float | Target net spending amount in today's dollars (in `units`). Used when `objective = "maxBequest"`. | Required for `maxBequest` |
| `noLateSurplus` | boolean | Disallow surplus deposits in the final two years of the plan. | `false` |
| `noRothConversions` | string | Name of individual for whom Roth conversions are disabled, or `"none"` to allow conversions for all. | `"none"` |
| `oppCostX` | float | *(Advanced)* Opportunity cost applied to Roth conversions (percent). | `0` |
| `previousMAGIs` | array | *(Advanced)* Two-element list of prior-year MAGI values (in `units`) for Medicare calculations. | `[0, 0]` |
| `relTol` | float | *(Advanced)* Relative convergence tolerance for the self-consistent loop objective. | `max(5e-5, gap / 300)` |
| `solver` | string | Solver to use for optimization. Valid values: `"default"`, `"HiGHS"`, `"MOSEK"`. `"default"` automatically selects MOSEK when available and licensed, otherwise falls back to HiGHS. | `"default"` |
| `spendingSlack` | integer | Percentage allowed to deviate from the spending profile (0-50). | `0` |
| `startRothConversions` | integer | Year when Roth conversions can begin (clamped to the current year). | Current year |
| `swapRothConverters` | integer | *(Advanced)* For plans involving spouses, only allow one spouse to perform Roth conversions per year. The year provided determines a transition year when roles are swapped. The sign selects who converts first: positive means person 1 can convert first and person 2 any time after; negative year means person 2 before and person 1 after. This option overrides the `noRothConversions` option. | `0` |
| `units` | string | Units for amounts. Valid values: `"1"` (dollars), `"k"` (thousands), `"M"` (millions). | `"k"` |
| `verbose` | boolean | When `true`, prints detailed solver iteration logs to the console. Supported by HiGHS and MOSEK; output format varies by solver. Useful for diagnosing infeasibility or slow convergence. | `false` |
| `withACA` | string | ACA marketplace premium handling (when `slcsp_annual` > 0). `"loop"` (default): compute ACA cost in SC loop each iteration using the exact piecewise-linear ACA formula. `"optimize"`: co-optimize ACA bracket selection within the LP — enables the optimizer to shift MAGI across brackets for better plan objectives (expert; can be slower; applies 2026 rules only). | `"loop"` |
| `withLTCG` | string | Long-term capital gains (LTCG) bracket handling. `"loop"` (default): ordinary income stacking computed in SC loop. `"optimize"`: exact MILP formulation for LTCG bracket selection — binary variables determine which 0%/15%/20% bracket applies each year (expert; adds `zl` binary family). | `"loop"` |
| `bigMltcg` | float | *(Advanced)* Big-M value for LTCG bracket binary constraints (when `withLTCG = "optimize"`). Scaled by the inflation factor γ_n each year. Defaults to `3 × T20_n` per year when omitted. | Auto |
| `withNIIT` | string | Net Investment Income Tax (NIIT) handling. `"loop"` (default): NIIT computed after each SC iteration. `"optimize"`: exact MILP formulation — binary variable determines whether MAGI exceeds the NIIT threshold ($200k single / $250k MFJ) each year (expert; adds `zj` binary family; most effective when `withLTCG = "optimize"` is also set). | `"loop"` |
| `bigMniit` | float | *(Advanced)* Big-M value for NIIT threshold binary constraints (when `withNIIT = "optimize"`). Scaled by the inflation factor γ_n each year. Defaults to `3 × T20_n` per year when omitted. | Auto |
| `withDecomposition` | string | *(Advanced)* MIP decomposition strategy for plans with multiple `"optimize"` flags active simultaneously. `"none"` (default): monolithic MIP. `"sequential"`: relax-and-fix heuristic — fixes bracket binary families (LTCG → SS taxability → NIIT → Medicare → ACA) one at a time from an LP relaxation; fast but not globally optimal. `"benders"`: classical Benders decomposition — separates bracket selection (master: `zm`, `za`, `zs`, `zj`) from continuous planning (subproblem, which also optimizes `zl` and `zx`); certifies global optimality within `gap` tolerance via accumulated dual cuts; slower per iteration but reliable. Silently ignored when no bracket-selection binaries are present. HiGHS and MOSEK supported. | `"none"` |
| `bendersMaxIter` | integer | *(Advanced)* Maximum number of Benders iterations when `withDecomposition = "benders"`. Each iteration solves a subproblem LP (for the dual cut) plus a subproblem MIP (for the upper bound) plus a master MIP (for the new lower bound). In practice, convergence typically occurs within 1–3 iterations because the LP relaxation's bracket assignment is nearly globally optimal. | `50` |
| `withMedicare` | string | Medicare Part B and Part D IRMAA handling. Valid values: `"none"`, `"loop"`, `"optimize"` (expert). When not `"none"`, Part B and Part D premiums (including IRMAA) are included; Part D can be disabled or given a base premium via the options below. | `"loop"` |
| `includeMedicarePartD` | boolean | Whether to include Medicare Part D premiums (IRMAA surcharges use same MAGI brackets as Part B). Set to `false` if you have other drug coverage (e.g., employer, VA). | `true` |
| `medicarePartDBasePremium` | float | *(Optional)* Monthly Part D base premium per person in today's dollars. Omit or set to 0 to model IRMAA only. National average is roughly $39–47/month. | `0` (no base) |
| `withSCLoop` | boolean | Whether to run the self-consistent loop to full convergence. When `false`, the solver always performs exactly two iterations: the first establishes ordinary income (`G_n`) so that LTCG bracket room is computed correctly; the second is the accepted solve. Medicare IRMAA and SS taxability are not converged in this mode — Medicare premiums are computed for display only. Useful for speed in Monte Carlo runs where full convergence is not required. | `true` |
| `withSSTaxability` | string or float | Controls how the taxable fraction of Social Security benefits (Ψ) is determined. The IRS provisional income (PI) formula taxes 0% of SS below $25k/$32k PI (single/MFJ), up to 50% between those and $34k/$44k, and up to 85% above. `"loop"` — recomputes Ψ each SC-loop iteration based on that year's projected income (recommended). `"optimize"` — encodes the IRS piecewise formula exactly as a MIP with binary variables (expert; can require a larger `gap`). Float in [0, 0.85] — pins Ψ to a fixed value: `0.0` (income well below the lower threshold), `0.5` (income in the mid range), or `0.85` (income above the upper threshold). | `"loop"` |

**Note:** The solver options dictionary is passed directly to the optimization routine. Only the options listed above are validated; other options may be accepted but are not documented here.

-------

## :orange[[results]]

Parameters controlling result display and output (graphs and the Streamlit **Worksheets** tables). These keys are stored on the `Plan`, round-trip in the case TOML, and can be changed from the **Worksheets** page (*Table display and save options* expander) as well as by editing the file.

| Parameter | Type | Description |
|-----------|------|-------------|
| `default_plots` | string | Default plot display mode. Valid values: `"nominal"` (nominal dollars), `"today"` (today's dollars) |
| `worksheet_show_ages` | boolean | When `true` (default `false`), adds per-person **age** columns next to `year` in both the on-screen tables and the saved Excel workbook. Each value is the individual's integer age on **December 31** of that row's calendar year. The cell is blank for years after that person's plan horizon. |
| `worksheet_hide_zero_columns` | boolean | When `true` (default `false`), the Streamlit **Worksheets** page omits numeric columns where every value is zero (within a small tolerance). The `year` and age columns are never removed. Applies to the **on-screen display only** — the saved Excel workbook always retains all columns. |
| `worksheet_real_dollars` | boolean | When `true` (default `false`), all currency values in both the on-screen tables and the saved Excel workbook are divided by the cumulative inflation factor `gamma_n`, converting nominal dollars to today's (real) dollars. The saved Excel filename gains a `_real` suffix to distinguish it from the nominal version. |

-------

## :orange[User-defined sections]

Any TOML section not listed in this document is treated as user-defined and **preserved on load and save**. You can add custom sections (e.g. `[user]`, `[custom_metadata]`, `[notes]`) to store notes, tags, or other data. These sections are ignored by Owl for planning but are round-tripped when you save a case file after loading one that contained them.

**Reserved section names** (do not use for custom data): `basic_info`, `savings_assets`, `household_financial_profile`, `fixed_income`, `rates_selection`, `asset_allocation`, `optimization_parameters`, `solver_options`, `aca_settings`, `results`, plus root-level keys `case_name` and `description`.

-------

## :orange[Notes on data types]

- **Floats**: In the TOML case file, monetary amounts are typically in **thousands of dollars** unless otherwise specified (see `[solver_options]` `units`). **HFP workbook** monetary cells on person sheets are always **nominal dollars** (full dollars), regardless of `units`.
- **Integers**: Used for years, ages, and counts
- **Booleans**: `true` or `false` in TOML
- **ISO Dates**: Format `"YYYY-MM-DD"` (e.g., `"1967-01-15"`)
- **Lists**: Arrays in TOML, e.g., `[1, 2, 3]` or `["Name1", "Name2"]`
- **3D Arrays**: Nested arrays, e.g., `[[[60, 40, 0, 0], [70, 30, 0, 0]]]`

-------

## :orange[Example TOML structure]

```toml
case_name = "example"
description = "Example case description"

[basic_info]
status = "married"
names = ["Person1", "Person2"]
date_of_birth = ["1965-01-15", "1967-03-20"]
life_expectancy = [89, 92]
start_date = "2026-01-01"

[savings_assets]
taxable_savings_balances = [100.0, 50.0]
tax_deferred_savings_balances = [500.0, 300.0]
tax_free_savings_balances = [200.0, 150.0]
hsa_savings_balances = [30.0, 20.0]
beneficiary_fractions = [1.0, 1.0, 1.0, 1.0]
spousal_surplus_deposit_fraction = 0.5

[household_financial_profile]
HFP_file_name = "HFP_example.xlsx"

[fixed_income]
pension_monthly_amounts = [0, 0]
pension_ages = [65.0, 65.0]
pension_indexed = [false, false]
pension_survivor_fraction = [0, 0]
social_security_pia_amounts = [2360, 1642]
social_security_ages = [70.0, 67.0]

[rates_selection]
heirs_rate_on_tax_deferred_estate = 30.0
dividend_rate = 1.8
obbba_expiration_year = 2032
method = "historical average"
from = 1969
to = 2002

[asset_allocation]
interpolation_method = "s-curve"
interpolation_center = 15.0
interpolation_width = 5.0
type = "individual"
generic = [[[60, 40, 0, 0], [70, 30, 0, 0]], [[60, 40, 0, 0], [80, 20, 0, 0]]]

[optimization_parameters]
spending_profile = "smile"
surviving_spouse_spending_percent = 60
smile_dip = 15
smile_increase = 12
smile_delay = 0
objective = "maxSpending"

[solver_options]
maxRothConversion = 100
noRothConversions = "none"
startRothConversions = 2026
withMedicare = "loop"
withSSTaxability = "loop"
bequest = 500
solver = "default"
spendingSlack = 0
amoRoth = true
amoSurplus = true
withSCLoop = true
maxIter = 29
maxTime = 180

[results]
default_plots = "nominal"
# Optional Streamlit Worksheets display and save options (defaults shown):
worksheet_show_ages = false
worksheet_hide_zero_columns = false
worksheet_real_dollars = false

# Optional: user-defined sections are preserved on load/save
[user]
notes = "Custom notes or metadata"
version = 1
```

