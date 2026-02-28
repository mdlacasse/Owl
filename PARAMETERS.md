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
| `beneficiary_fractions` | list of 3 floats | *(Married only)* Fraction of each account type (taxable, tax-deferred, tax-free) bequeathed to the surviving spouse. Each value should be between 0.0 and 1.0 |
| `spousal_surplus_deposit_fraction` | float | *(Married only)* Fraction of surplus to deposit in the second spouse's taxable account. Value between 0.0 and 1.0 |

-------

## :orange[[household_financial_profile]]

Reference to the Excel file containing wages, contributions, and other time-varying financial data.

| Parameter | Type | Description |
|-----------|------|-------------|
| `HFP_file_name` | string | Name of the Excel file (`.xlsx`) containing wages, contributions, Roth conversions, and big-ticket items. Use `"None"` if no file is associated with the case |

**Note:** The Excel file should contain one sheet per individual with columns for: year, anticipated wages, other inc (optional), taxable contributions, 401k contributions, Roth 401k contributions, IRA contributions, Roth IRA contributions, Roth conversions, and big-ticket items.

-------

## :orange[[fixed_income]]

Pension and Social Security information.

| Parameter | Type | Description |
|-----------|------|-------------|
| `pension_monthly_amounts` | list of `N_i` floats | Monthly pension amount for each individual (in dollars). Use `0` if no pension |
| `pension_ages` | list of `N_i` floats | Age at which pension starts for each individual |
| `pension_indexed` | list of `N_i` booleans | Whether each pension is indexed for inflation |
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
| `heirs_rate_on_tax_deferred_estate` | float | Tax rate (as percentage, e.g., `30.0` for 30%) that heirs will pay on inherited tax-deferred accounts |
| `dividend_rate` | float | Dividend rate as a percentage (e.g., `1.72` for 1.72%) |
| `obbba_expiration_year` | integer | Year when the OBBBA (One Big Beautiful Bill Act) provisions expire. Default is `2032` |
| `method` | string | Method for determining rates. Valid values: `"default"`, `"optimistic"`, `"conservative"`, `"user"`, `"historical"`, `"historical average"`, `"stochastic"`, `"histochastic"` |

### :orange[Conditional parameters based on `method`]

#### :orange[For method = "user" or "stochastic"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `values` | list of 4 floats | Mean returns in percent: [S&P 500, Corporate Baa bonds, 10-year Treasury notes, Inflation] (e.g., `7` for 7%) |

#### :orange[For method = "stochastic"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `standard_deviations` | list of 4 floats | Volatility in percent for each rate type (e.g., `17` for 17% annualized standard deviation) |
| `correlations` | list of 6 floats | Pearson correlation coefficient (range -1 to 1) for upper triangle: (1,2), (1,3), (1,4), (2,3), (2,4), (3,4). Standard representation in finance and statistics. |

#### :orange[For method = "stochastic" or "histochastic"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `rate_seed` | integer | Random seed for reproducible stochastic rates |
| `reproducible_rates` | boolean | Whether stochastic rates should be reproducible |

#### :orange[For method = "historical", "historical average", or "histochastic"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | integer | Starting year for historical data range (must be between 1928 and 2025) |
| `to` | integer | Ending year for historical data range (must be between 1928 and 2025, and greater than `from`) |

#### :orange[For method = "historical", "histochastic", or "stochastic" (varying rates only)]
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
| `interpolation_method` | string | Method for interpolating asset allocation over time. Valid values: `"linear"`, `"s-curve"` |
| `interpolation_center` | float | Center point of the interpolation curve (in years from start). Ignored for `"linear"` |
| `interpolation_width` | float | Width of the interpolation curve (in years). Ignored for `"linear"` |
| `type` | string | Type of allocation strategy. Valid values: `"account"`, `"individual"`, `"spouses"` |

### :orange[Conditional parameters based on `type`]

#### :orange[For type = "account"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `taxable` | 3D array | Asset allocation bounds for taxable accounts. Structure: `[[[initial_stocks, initial_bonds, initial_fixed, initial_real_estate], [final_stocks, final_bonds, final_fixed, final_real_estate]]]` for each individual |
| `tax-deferred` | 3D array | Asset allocation bounds for tax-deferred accounts (same structure as `taxable`) |
| `tax-free` | 3D array | Asset allocation bounds for tax-free accounts (same structure as `taxable`) |

#### :orange[For type = "individual" or "spouses"]
| Parameter | Type | Description |
|-----------|------|-------------|
| `generic` | 3D array | Generic asset allocation bounds. Structure: `[[[initial_stocks, initial_bonds, initial_fixed, initial_real_estate], [final_stocks, final_bonds, final_fixed, final_real_estate]], ...]` for each individual. For single individuals, only one pair is needed |

**Note:** All allocation values are percentages that should sum to 100 for each time point. The four asset classes are: stocks, bonds, fixed assets, and real estate.

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
| `bigMss` | float | *(Advanced)* Big-M value for the Social Security taxability MIP formulation (when `withSSTaxability = "optimize"`). Should exceed provisional income and related quantities. | Same as `bigMamo` |
| `epsilon` | float | *(Advanced)* Lexicographic weight added to the objective to break ties. Adds a linearly increasing penalty to Roth conversions (earlier years are cheaper) to frontload conversions, and when `N_i = 2`, also penalizes withdrawals of spouse 2 to favor withdrawals from spouse 1. Use a very small value so the primary objective dominates. | `1e-8` |
| `gap` | float | *(Advanced)* Relative MILP gap used by solvers and to scale convergence tolerances. | `1e-4` (default); if `withMedicare = "optimize"` and unset, set to `3e-3` (or `3e-2` when `maxRothConversion <= 15`) |
| `maxIter` | integer | *(Advanced)* Maximum number of iterations for the self-consistent loop. Must be at least 1. | `29` |
| `maxRothConversion` | float or string | Maximum annual Roth conversion amount (in `units`). Use `"file"` to take per-year limits from time lists; omit for no cap (except last year). | No cap unless provided |
| `minTaxableBalance` | array | Minimum taxable account balance per spouse (in today's `units`). Values are indexed for inflation. Constraints apply from year 2 through each individual's life horizon. | Omit for no minimum |
| `maxTime` | float | *(Advanced)* Solver time limit in seconds. | `900` |
| `netSpending` | float | Target net spending amount in today's dollars (in `units`). Used when `objective = "maxBequest"`. | Required for `maxBequest` |
| `noLateSurplus` | boolean | Disallow surplus deposits in the final two years of the plan. | `false` |
| `noRothConversions` | string | Name of individual for whom Roth conversions are disabled, or `"None"` to allow conversions for all. | `"None"` |
| `oppCostX` | float | *(Advanced)* Opportunity cost applied to Roth conversions (percent). | `0` |
| `previousMAGIs` | array | *(Advanced)* Two-element list of prior-year MAGI values (in `units`) for Medicare calculations. | `[0, 0]` |
| `relTol` | float | *(Advanced)* Relative convergence tolerance for the self-consistent loop objective. | `max(5e-5, gap / 300)` |
| `solver` | string | Solver to use for optimization. Valid values: `"default"`, `"HiGHS"`, `"PuLP/CBC"`, `"PuLP/HiGHS"`, `"MOSEK"`. `"default"` automatically selects MOSEK when available and licensed, otherwise falls back to HiGHS. | `"default"` |
| `spendingSlack` | integer | Percentage allowed to deviate from the spending profile (0-50). | `0` |
| `startRothConversions` | integer | Year when Roth conversions can begin (clamped to the current year). | Current year |
| `swapRothConverters` | integer | *(Advanced)* For plans involving spouses, only allow one spouse to perform Roth conversions per year. The year provided determines a transition year when roles are swapped. The sign selects who converts first: positive means person 1 can convert first and person 2 any time after; negative year means person 2 before and person 1 after. This option overrides the `noRothConversions` option. | `0` |
| `units` | string | Units for amounts. Valid values: `"1"` (dollars), `"k"` (thousands), `"M"` (millions). | `"k"` |
| `verbose` | boolean | Enable solver verbosity/output where supported. | `false` |
| `withMedicare` | string | Medicare IRMAA handling. Valid values: `"None"`, `"loop"`, `"optimize"` (expert). | `"loop"` |
| `withSCLoop` | boolean | Whether to use the self-consistent loop for solving. | `true` |
| `withSSTaxability` | string or float | Social Security taxable-fraction (Ψ) handling. Use `"loop"` to compute Ψ dynamically each SC-loop iteration (recommended). Use `"optimize"` to solve Ψ exactly as a MIP decision variable (expert). Use a float in [0, 0.85] to pin Ψ to a fixed value — `0.0` (PI well below lower threshold), `0.5` (mid-range PI), or `0.85` (PI above upper threshold). | `"loop"` |

**Note:** The solver options dictionary is passed directly to the optimization routine. Only the options listed above are validated; other options may be accepted but are not documented here.

-------

## :orange[[results]]

Parameters controlling result display and output.

| Parameter | Type | Description |
|-----------|------|-------------|
| `default_plots` | string | Default plot display mode. Valid values: `"nominal"` (nominal dollars), `"today"` (today's dollars) |

-------

## :orange[User-defined sections]

Any TOML section not listed in this document is treated as user-defined and **preserved on load and save**. You can add custom sections (e.g. `[user]`, `[custom_metadata]`, `[notes]`) to store notes, tags, or other data. These sections are ignored by Owl for planning but are round-tripped when you save a case file after loading one that contained them.

**Reserved section names** (do not use for custom data): `basic_info`, `savings_assets`, `household_financial_profile`, `fixed_income`, `rates_selection`, `asset_allocation`, `optimization_parameters`, `solver_options`, `results`, plus root-level keys `case_name` and `description`.

-------

## :orange[Notes on data types]

- **Floats**: All monetary amounts are typically in thousands of dollars unless otherwise specified
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
beneficiary_fractions = [1.0, 1.0, 1.0]
spousal_surplus_deposit_fraction = 0.5

[household_financial_profile]
HFP_file_name = "HFP_example.xlsx"

[fixed_income]
pension_monthly_amounts = [0, 0]
pension_ages = [65.0, 65.0]
pension_indexed = [false, false]
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
noRothConversions = "None"
startRothConversions = 2025
withMedicare = "loop"
withSSTaxability = "loop"
bequest = 500
solver = "default"
spendingSlack = 0
amoRoth = true
amoSurplus = true
withSCLoop = true
maxIter = 29
maxTime = 900

[results]
default_plots = "nominal"

# Optional: user-defined sections are preserved on load/save
[user]
notes = "Custom notes or metadata"
version = 1
```

