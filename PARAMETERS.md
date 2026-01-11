# Owl Parameters

This document describes all parameters used in Owl TOML configuration files. The TOML file structure is organized into sections for clarity, and can be consumed by both the UI and CLI applications.

**Note:** Throughout this document, `N_i` refers to the number of individuals in the plan (1 for single, 2 for married).

---

## Root Level Parameters

These parameters are defined at the root level of the TOML file (not within any section).

| Parameter | Type | Description |
|-----------|------|-------------|
| `case_name` | string | Name of the case/plan |
| `description` | string | A short text describing the purpose of the case |

---

## [basic_info]

Basic information about the individuals in the plan.

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filing status. Valid values: `"single"`, `"married"` |
| `names` | list of strings | Names of the individuals in the plan. Must contain 1 or 2 names. Length determines `N_i` |
| `date_of_birth` | list of `N_i` ISO dates | Date of birth for each individual in ISO format (e.g., `"1967-01-15"`). Defaults to `"1965-01-15"` if not specified |
| `life_expectancy` | list of `N_i` integers | Life expectancy in years for each individual |
| `start_date` | string | Start date of the plan in ISO format (e.g., `"2026-01-01"`). Only the month and day are used; the plan always starts in the current year. Defaults to `"today"` if not specified |

---

## [savings_assets]

Initial account balances and beneficiary information.

| Parameter | Type | Description |
|-----------|------|-------------|
| `taxable_savings_balances` | list of `N_i` floats | Initial balance in taxable accounts for each individual (in thousands of dollars) |
| `tax_deferred_savings_balances` | list of `N_i` floats | Initial balance in tax-deferred accounts (e.g., 401k, traditional IRA) for each individual (in thousands of dollars) |
| `tax_free_savings_balances` | list of `N_i` floats | Initial balance in tax-free accounts (e.g., Roth IRA, Roth 401k) for each individual (in thousands of dollars) |
| `beneficiary_fractions` | list of 3 floats | *(Married only)* Fraction of each account type (taxable, tax-deferred, tax-free) bequeathed to the surviving spouse. Each value should be between 0.0 and 1.0 |
| `spousal_surplus_deposit_fraction` | float | *(Married only)* Fraction of surplus to deposit in the second spouse's taxable account. Value between 0.0 and 1.0 |

---

## [household_financial_profile]

Reference to the Excel file containing wages, contributions, and other time-varying financial data.

| Parameter | Type | Description |
|-----------|------|-------------|
| `HFP_file_name` | string | Name of the Excel file (`.xlsx`) containing wages, contributions, Roth conversions, and big-ticket items. Use `"None"` if no file is associated with the case |

**Note:** The Excel file should contain one sheet per individual with columns for: year, anticipated wages, taxable contributions, 401k contributions, Roth 401k contributions, IRA contributions, Roth IRA contributions, Roth conversions, and big-ticket items.

---

## [fixed_income]

Pension and Social Security information.

| Parameter | Type | Description |
|-----------|------|-------------|
| `pension_monthly_amounts` | list of `N_i` floats | Monthly pension amount for each individual (in dollars). Use `0` if no pension |
| `pension_ages` | list of `N_i` floats | Age at which pension starts for each individual |
| `pension_indexed` | list of `N_i` booleans | Whether each pension is indexed for inflation |
| `social_security_pia_amounts` | list of `N_i` integers | Primary Insurance Amount (PIA) for Social Security for each individual (in dollars) |
| `social_security_ages` | list of `N_i` floats | Age at which Social Security benefits start for each individual |

---

## [rates_selection]

Investment return rates and inflation assumptions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `heirs_rate_on_tax_deferred_estate` | float | Tax rate (as percentage, e.g., `30.0` for 30%) that heirs will pay on inherited tax-deferred accounts |
| `dividend_rate` | float | Dividend rate as a percentage (e.g., `1.72` for 1.72%) |
| `obbba_expiration_year` | integer | Year when the OBBBA (One Big Beautiful Bill Act) provisions expire. Default is `2032` |
| `method` | string | Method for determining rates. Valid values: `"user"`, `"stochastic"`, `"historical"`, `"historical average"`, `"histochastic"`, `"optimistic"`, `"conservative"` |

### Conditional Parameters Based on `method`

#### For `method = "user"` or `"stochastic"`:
| Parameter | Type | Description |
|-----------|------|-------------|
| `values` | list of 4 floats | Fixed rate values as percentages: [S&P 500 return, Corporate Baa bonds return, 10-year Treasury notes return, Inflation rate] |

#### For `method = "stochastic"`:
| Parameter | Type | Description |
|-----------|------|-------------|
| `standard_deviations` | list of 4 floats | Standard deviations (as percentages) for each rate type |
| `correlations` | array | Correlation matrix (4×4) or flattened upper triangle (6 values) for the four rate types |

#### For `method = "historical"`, `"historical average"`, or `"histochastic"`:
| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | integer | Starting year for historical data range (must be between 1928 and 2024) |
| `to` | integer | Ending year for historical data range (must be between 1928 and 2024, and greater than `from`) |

**Note:** If `from` and `to` are not specified for methods that don't require them, they default to the full available range (1928-2025).

---

## [asset_allocation]

Asset allocation strategy and how it changes over time.

| Parameter | Type | Description |
|-----------|------|-------------|
| `interpolation_method` | string | Method for interpolating asset allocation over time. Valid values: `"linear"`, `"s-curve"` |
| `interpolation_center` | float | *(For s-curve only)* Center point of the interpolation curve (in years from start) |
| `interpolation_width` | float | *(For s-curve only)* Width of the interpolation curve (in years) |
| `type` | string | Type of allocation strategy. Valid values: `"account"`, `"individual"`, `"spouses"` |

### Conditional Parameters Based on `type`

#### For `type = "account"`:
| Parameter | Type | Description |
|-----------|------|-------------|
| `taxable` | 3D array | Asset allocation bounds for taxable accounts. Structure: `[[[initial_stocks, initial_bonds, initial_fixed, initial_real_estate], [final_stocks, final_bonds, final_fixed, final_real_estate]]]` for each individual |
| `tax-deferred` | 3D array | Asset allocation bounds for tax-deferred accounts (same structure as `taxable`) |
| `tax-free` | 3D array | Asset allocation bounds for tax-free accounts (same structure as `taxable`) |

#### For `type = "individual"` or `"spouses"`:
| Parameter | Type | Description |
|-----------|------|-------------|
| `generic` | 3D array | Generic asset allocation bounds. Structure: `[[[initial_stocks, initial_bonds, initial_fixed, initial_real_estate], [final_stocks, final_bonds, final_fixed, final_real_estate]], ...]` for each individual. For single individuals, only one pair is needed |

**Note:** All allocation values are percentages that should sum to 100 for each time point. The four asset classes are: stocks, bonds, fixed assets, and real estate.

---

## [optimization_parameters]

Parameters controlling the optimization objective and spending profile.

| Parameter | Type | Description |
|-----------|------|-------------|
| `spending_profile` | string | Type of spending profile. Valid values: `"flat"`, `"smile"` |
| `surviving_spouse_spending_percent` | integer | Percentage of spending amount for the surviving spouse (0-100). Default is `60` |
| `objective` | string | Optimization objective. Valid values: `"maxSpending"`, `"maxBequest"` |

### Conditional Parameters for `spending_profile = "smile"`:
| Parameter | Type | Description |
|-----------|------|-------------|
| `smile_dip` | integer | Percentage to decrease spending during the "slow-go" years (0-100). Default is `15` |
| `smile_increase` | integer | Percentage to increase (or decrease if negative) spending over the time span (-100 to 100). Default is `12` |
| `smile_delay` | integer | Number of years from the start before spending begins to decrease (0 to plan duration - 2). Default is `0` |

**Note:** The "smile" profile creates a spending pattern that starts high, decreases during middle years, and increases again later in retirement.

---

## [solver_options]

Options controlling the optimization solver and constraints.

| Parameter | Type | Description | Required For |
|-----------|------|-------------|--------------|
| `maxRothConversion` | float | Maximum annual Roth conversion amount in thousands of dollars. Use `0.0` to disable Roth conversions | Optional |
| `noRothConversions` | string | Name of individual for whom Roth conversions are disabled, or `"None"` to allow conversions for all | Optional |
| `startRothConversions` | integer | Year when Roth conversions can begin. Defaults to current year if not specified | Optional |
| `withMedicare` | string | Medicare IRMAA handling. Valid values: `"None"`, `"loop"`, `"optimize"`. Default is `"loop"` | Optional |
| `bequest` | float | Target bequest value in thousands of dollars (today's dollars). Required when `objective = "maxSpending"` | Required for `maxSpending` |
| `netSpending` | float | Target net spending amount in thousands of dollars. Required when `objective = "maxBequest"` | Required for `maxBequest` |
| `solver` | string | Solver to use for optimization. Valid values: `"HiGHS"`, `"PuLP/CBC"`, `"PuLP/HiGHS"`, `"MOSEK"`. Default is `"HiGHS"` | Optional |
| `spendingSlack` | integer | Percentage allowed to deviate from the spending profile (0-50). Default is `0` | Optional |
| `xorConstraints` | boolean | Whether to use XOR constraints in the optimization. Default is `true` | Optional |
| `withSCLoop` | boolean | Whether to use self-consistent loop for solving. Default is `true` | Optional |
| `bigM_xor` | float | *(Advanced)* Big-M value for XOR constraints (mutually exclusive operations). Default is `1e7` (10 million). Should be larger than any individual withdrawal, conversion, or surplus deposit. | Optional |
| `bigM_irmaa` | float | *(Advanced)* Big-M value for Medicare IRMAA bracket constraints. Default is `1e8` (100 million). Should be larger than any possible MAGI value. Typically larger than `bigM_xor` since it bounds aggregate income. | Optional |
| `oppCostX` | float | *(Advanced)* Opportunity cost parameter | Optional |
| `previousMAGIs` | array | *(Advanced)* Previous MAGI values for Medicare calculations | Optional |
| `units` | string | Units for amounts. Valid values: `"1"` (dollars), `"k"` (thousands), `"M"` (millions). Default is `"k"` | Optional |

**Note:** The solver options dictionary is passed directly to the optimization routine. Only the options listed above are validated; other options may be accepted but are not documented here.

---

## [results]

Parameters controlling result display and output.

| Parameter | Type | Description |
|-----------|------|-------------|
| `default_plots` | string | Default plot display mode. Valid values: `"nominal"` (nominal dollars), `"today"` (today's dollars) |

---

## Notes on Data Types

- **Floats**: All monetary amounts are typically in thousands of dollars unless otherwise specified
- **Integers**: Used for years, ages, and counts
- **Booleans**: `true` or `false` in TOML
- **ISO Dates**: Format `"YYYY-MM-DD"` (e.g., `"1967-01-15"`)
- **Lists**: Arrays in TOML, e.g., `[1, 2, 3]` or `["Name1", "Name2"]`
- **3D Arrays**: Nested arrays, e.g., `[[[60, 40, 0, 0], [70, 30, 0, 0]]]`

## Example TOML Structure

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
bequest = 500
solver = "HiGHS"
spendingSlack = 0
xorConstraints = true
withSCLoop = true

[results]
default_plots = "nominal"
```

