"""
Documentation page for Owl retirement planner Streamlit UI.

This module provides the interface for viewing application documentation,
user guides, and help information.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import streamlit as st
import sskeys as kz

col1, col2, col3 = st.columns([0.69, 0.02, 0.29], gap="large")
with col1:
    st.markdown("# :material/help: Documentation")
    kz.divider("orange")
    st.markdown("## :orange[The *Owl* Retirement Planner]\n-------")
    st.markdown("""
### *Owl* - Optimal Wealth Lab
#### A retirement financial exploration tool based on linear programming

The goal of *Owl* is to provide a free and open-source ecosystem that has cutting-edge
optimization capabilities, allowing for the new generation of computer-literate retirees
to experiment with their own financial future while providing a codebase where they can learn and contribute.
At the same time, Streamlit provides an intuitive and easy-to-use
interface which allows a broad set of users to benefit from the application
as it only requires basic financial knowledge.

Strictly speaking, *Owl* is not a planning tool, but more an environment for exploring *what if* scenarios.
It provides different realizations of a financial strategy through the rigorous
mathematical optimization of relevant decision variables. Using a linear programming approach,
two different objectives can currently be optimized: either
maximize the net spending amount under the constraint of a desired bequest,
or maximize an after-tax bequest under the constraint of a desired net spending amount.
In each case, Roth conversions are optimized to reduce the tax burden,
while federal income tax and Medicare premiums (including IRMAA) are calculated.
A full description of the package can be found on the GitHub
open [repository](https://github.com/mdlacasse/Owl), and the mathematical
formulation of the optimization problem can be found
[here](https://github.com/mdlacasse/Owl/blob/main/papers/owl.pdf).
""")
with col3:
    # Use URL-based logo to avoid race conditions with local file access
    logofile = "https://raw.githubusercontent.com/mdlacasse/Owl/main/ui/owl.png"
    st.image(logofile)
    st.caption("Retirement planner with great wisdom")

col1, col2 = st.columns([0.80, 0.20], gap="large")
with col1:
    st.markdown("""

-------------------------------------------------
### :orange[Table of Contents]
[Getting Started with User Interface](#getting-started-with-user-interface)

[Case Setup](#case-setup)
- [Case Definition](#case-definition)
- [:material/person_add: Create Case](#person-add-create-case)
- [:material/home: Household Financial Profile](#home-household-financial-profile)
    - [:material/work_history: Wages and Contributions](#work-history-wages-and-contributions)
    - [:material/account_balance: Debts and Fixed Assets](#account-balance-debts-and-fixed-assets)
- [:material/currency_exchange: Fixed Income](#currency-exchange-fixed-income)
- [:material/savings: Savings Assets](#savings-savings-assets)
- [:material/percent: Asset Allocation](#percent-asset-allocation)
- [:material/monitoring: Rates Selection](#monitoring-rates-selection)
- [:material/tune: Optimization Parameters](#tune-optimization-parameters)

[Single Scenario](#single-scenario)
- [:material/stacked_line_chart: Graphs](#stacked-line-chart-graphs)
- [:material/data_table: Worksheets](#data-table-worksheets)
- [:material/description: Output Files](#description-output-files)

[Multiple Scenarios](#multiple-scenarios)
- [:material/history: Historical Range](#history-historical-range)
- [:material/finance: Monte Carlo](#finance-monte-carlo)

[Resources](#resources)
- [:material/rocket_launch: Quick Start](#rocket-launch-quick-start)
- [:material/help: Documentation](#help-documentation)
- [:material/settings: Settings](#settings-settings)
- [:material/error: Logs](#error-logs)
- [:material/info: About *Owl*](#info-about-owl)

[Tips](#tips)
- [:material/lightbulb_2: Advice on Optimization and Roth Conversions]\
(#lightbulb-2-advice-on-optimization-and-roth-conversions)
- [:material/rule_settings: Typical Workflow](#rule-settings-typical-workflow)
- [:material/mindfulness: Scope of Use](#mindfulness-scope-of-use)

--------------------------------------------------------------------------------------
### :orange[Getting Started with the User Interface]
The functions of each page are described below in the same order as they appear in the menu bar:
Typically, pages would be accessed in order, starting from left to right and from the top down.

A `Case selector` box located at the top of each page allows
to navigate between the different scenarios created.
When on the [Create Case](#person-add-create-case) page, however, the selector box offers two more options:
one to create a new *case* from scratch, and one to create a case
from a *case* parameter file, which
would then populate values of all parameters found
in the [Case Setup](#case-setup) section.
This box is present on all pages except those in the [Resources](#resource) section.
The *case* being currently displayed is marked with a small red triangle.

A typical workflow for exploring different scenarios involves starting with a base
case and then copying/creating derived scenarios with slight changes in the parameters.
A comparison between the
different resulting outcomes can be found on the [Output Files](#description-output-files) page.
The [Typical Workflow](#typical-workflow) section below
goes through a more specific example.

*Owl* uses a full year as the standard unit of time. All values are therefore entered and
reported as yearly values. These include wages, income, rates, social security, etc.
Dollar values are typically entered in thousands, unless in tables, where they
are entered and reported in unit dollars.
Graphs report values in thousands, either in nominal value or in today's \\$, as selected.

There are four sections in the menu bar:
[Case Setup](#case-setup), [Single Scenario](#single-scenario),
[Multiple Scenarios](#multiple-scenarios), and [Resources](#resources).
The sections below follow the same logical order.

-------------------------------------------------
### :orange[Case Setup]
This section contains the steps for creating and configuring *case* scenarios.
For new *cases*, every page of this section should be visited and parameters
entered according to your personal situation. To make this process easier,
a progress bar tracking which page has been visited is shown at the bottom of the page.

#### Case Definition

A *case* is a collection of parameters that fully defines a retirement scenario. A *case* contains
individual's life parameters, financial profile, fixed income sources, savings account balances,
asset allocation ratios, anticipated rates of return, and optimization parameters.

A *run* is the execution of a *case* using a single instance of rates, either fixed or varying.

*Owl* helps the planner to create and run *cases*. By carefully selecting and modifying parameters,
the planner can explore the impacts of differing assumptions and strategies on their portfolio
at the end of their planning period.

#### :material/person_add: Create Case
The **Create Case** page is where every new scenario begins.
It controls the creation of scenarios as the `Case selector` drop-down menu contains
two additional items:
one to create new *cases*, and the other to create  *cases* from a *case* parameter file.
This page also allows you to copy and/or rename scenarios, as well as deleting them.

For creating a scenario from scratch, (first) name(s), marital status,
birth date(s), and life expectancies are required.
The reason for asking the birth date is that social security rules
have special considerations when born on the first days of the month.
If you're not born on a 1st or 2nd day of the month, any other day of the
month will generate the same results.

*Cases* start on Jan 1st of this year and ends on December 31st of the year when all individuals
have passed according to the specified life expectancies.

A typical workflow will involve creating
a base *case*, and copying it a few times with slight changes in its parameters
in order to investigate their effects.
Copy renames the *case* by appending a number counter in parenthesis, just as creating
a copy of a file on Windows.
It is recommended to rename each *case* to reflect the change in parameters.
When copying a scenario, make sure to visit all pages in the [Case Setup](#case-setup)
section and verify that all parameters are as intended.
When all *cases* have successfully run,
results of related *cases* are compared side-by-side with differences
in the [Output Files](#description-output-files) section.
Related *cases* are determined by having the same individual's names:
anything else can change between *cases*.

##### Initializing the life parameters of a scenario
While on the **Create Case** page,
click on the `Case selector` box and choose one of `New case...` or `Upload case file...`.

##### Creating a case from scratch
When starting from `New case...`,
one must provide the birth date of each spouse(s) and their expected lifespan(s).
For selecting your own longevity numbers, there are plenty of predictors on the Internet.
Pick your favorite:
- [longevityillustrator](https://longevityillustrator.org),
- [livingto100](https://www.livingto100.com/calculator),

or just Google *life expectancy calculator*.

##### Using a *case* file
If `Upload case file...` is selected, a *case* file must be uploaded.
These files end with the *.toml* extension, are human readable (and therefore editable),
and contain all the parameters required to characterize a scenario.
An example is provided
[here](https://github.com/mdlacasse/Owl/main/blob/examples/case_jack+jill.toml?raw=true) and more
can be found in this [directory](https://github.com/mdlacasse/Owl/blob/main/examples/).
Using a *case* file
will populate all the fields in the [Case Setup](#case-setup) section,
except those in the *Household Financial Profile* which get populated
separately by an Excel workbook (see next section).

Once a *case* was successfully run, the *case* file for the *case* being developed
can be saved under the [Output Files](#description-output-files) page and
can be reloaded at a later time.
Case parameter files can have any name but when saving from the interface,
their name will start with *case_* followed by the *case* name.

#### :material/home: Household Financial Profile
The *Household Financial Profile* contains two major sections,
one representing *Wages and Contributions* for each individual, and
the other capturing the household's *Debts and Fixed Assets*.
While the values can be entered manually in each table,
an option is given to upload an Excel file containing all the data,
thus avoiding this tedious exercise.
These data include future wages and contributions,
past and future Roth contributions and conversions, large expenses
or large influx of after-tax money, debts, and fixed assets.

##### :material/work_history: Wages and Contributions
Values in the *Wages and Contributions* tables are all in nominal values, and in \\$, not thousands (\\$k).
The **Wages and Contributions** table contains 9 columns titled as follows:

|year|anticipated wages|ctrb taxable|ctrb 401k|ctrb Roth 401k|ctrb IRA|ctrb Roth IRA|Roth conv|big-ticket items|
|--|--|--|--|--|--|--|--|--|
|2021 | | | | | | | | |
| ... | | | | | | | | |
|2026 | | | | | | | | |
|2027 | | | | | | | | |
| ... | | | | | | | | |
|20XX | | | | | | | | |

Note that column names are case sensitive and all entries are in lower case.
The easiest way to complete the process of filling this file is either to start from the template
file provided [here](https://github.com/mdlacasse/Owl/blob/main/examples/HFP_template.xlsx?raw=true) or
to fill in the values using the user interface, but this last approach does not provide
Excel capabilities for cross-column calculations.

This file goes five year back in time in order to capture previous contributions and
conversions to Roth accounts.
Entries in columns others than contributions or conversions to Roth accounts
for past years will be ignored by *Owl* but can be left there for documentation purposes.
Past contributions and conversions are required for implementing
constraints restricting withdrawals from Roth accounts, thus avoiding
penalties resulting from breaking the five-year maturation rule.
For that purpose, a retainer on the tax-free account
is put as the sum of all Roth conversions performed
during the last five years plus an additional amount for potential
compounded gains. These gains are assumed to be 10% per year for the past
years, and use the predicted returns for future years.
Unlike conversions, contributions can be withdrawn, but a retainer is
put covering the sum of all potential gains resulting from contributions
made over the last five years.
However, if funds were converted through a Roth backdoor, this is
still considered as a conversion, and retainer will include the contribution amount.
While this approach is somehow more restrictive than
the actual rules, it avoids unnecessary penalties while being a somehow simple approach.
An exact calculation would require to know (and input) the annual rates of return for
the last five years and asset allocation ratios, and the same for all future years.
Note that in certain *cases*, constraints on Roth withdrawals can make a zero bequest impossible
if Roth conversions took place in the five years before passing.

In the table above, year 20XX represents the last row which could be the last year based on the life
expectancy values provided.
While loading an Excel workbook, missing years or empty cells will be filled with zero values,
while years outside the time span of the *case* will simply be ignored with the exception
of five-year back history.

The column *anticipated wages* is the annual amount
(gross minus tax-deferred contributions) that you anticipate to receive from employment
or other sources (e.g., rentals).
This column does not include dividends from your taxable investment accounts,
as they will be calculated based on your assumptions for future return rates.

For the purpose of planning, there is no clear definition of retirement age. There will be a year,
however, from which you will stop having anticipated income, or diminished income due to decreasing your
work load. This transition can be gradual or sudden, and can be explored through these wages
and contributions tables. The only *hard* dates are the years when you intend to receive
a pension or collect social security, and these years are entered elsewhere on the
[Fixed Income](#currency-exchange-fixed-income) page.

Contributions to your savings accounts are marked as *ctrb*. We use 401k as a term that includes
contributions to 403b as well or any other tax-deferred account, with the exception
of IRAs accounts which are treated separately to facilitate data entry.
Contributions to your 401k/403b must also include your employer's
contributions, if any. As these data can be entered in Excel,
one can use the native calculator to enter a percentage
of the anticipated wages for contributions to savings accounts as an easier way to enter the data.
For this purpose, additional columns can coexist in the Excel file
and can be used for tracking other quantities from which
the needed values can be derived. These extra columns will be ignored when the file is processed.

Manual Roth conversions can be specified in the column marked *Roth conv*.
This column is provided to override the Roth conversion optimization in *Owl*.
When the option `Convert as in contribution file` is toggled
in the [Optimization Parameters](#tune-optimization-parameters) page,
values from the **Wages and Contributions** file will be used and no optimization on Roth conversions
will be performed. This column is provided for flexibility and to allow comparisons
between an optimized solution and your best guesses.

Finally, *big-ticket items* are used for accounting for the sale or purchase of a house, or any
other major expense or money that you would give or receive (e.g., inheritance, or large gifts
to or from you). Therefore, the sign (+/-) of entries in this column is important.
Positive numbers will be considered in the cash flow for that year and the surplus, if any, will be
deposited in the taxable savings accounts. Negative numbers will potentially generate additional
withdrawals and distributions from retirement accounts. This is the only column that can contain
negative numbers: all other column entries must be positive.

When loading an Excel workbook, each individual in the *case* must have an associated sheet
for reporting yearly transactions affecting the *case*. The association is made by having
the individual's name as the sheet name in the workbook.
Therefore, if preparing your own *case* using a template, you will need to rename the tabs in the file to
match the names used when creating the case
(i.e., *Jack* and *Jill* in the example files provided).
If a file was originally associated with a *case* file, a message will remind the user to upload the file.

If values were entered or edited directly in the table,
values can be saved directly in Excel format by clicking
the `Download Wages and Contributions` on the
[Output Files](#description-output-files) page. This allows to rerun the same *case* at a later time
by reloading the same **Wages and Contributions** file.

##### :material/account_balance: Debts and Fixed Assets
These tables contain current or future debts and existing fixed assets.
Note that no optimization is taking place on debts, as the question
*"Should I pay my mortgage or leave my money invested?"* has to consider risk,
and therefore risk tolerance, and not only compare interest rates.

The *Debts* table is used to track mortgage and loan payments which are not included
in the net spending amount.
*Debts* remaining at the end of the *case* will be taken out of the savings accounts.
A bequest of zero will therefore leave sufficient money from the savings accounts
to pay the remaining debts. Mortgage interest is not deducted for income tax purposes,
as *Owl* assumes taking the standard tax deduction.

The *Household Financial Profile* workbook can optionally contain a *Debts* sheet and
a *Fixed Assets* sheet to store these data.
The *Debts* worksheet looks like the following:

|active|name|type|year|term|amount|rate|
|--|--|--|--|--|--|--|
| | | | | | | |

where:
- *active* is a Boolean value (`TRUE` or `FALSE`) that allows to turn debts on or off in the
  calculations. This is useful for *case* comparison purposes. If not specified or set to `TRUE`,
  the debt is included in calculations. Boolean values are marked in all caps as `TRUE` or `FALSE` in Excel.
- *name* is a unique identifier for the debt (e.g., "Primary Mortgage", "Car Loan", "HELOC").
- *type* is one of *loan* or *mortgage*. This classification helps organize different types of debts,
  though both are treated the same way in calculations.
- *year* is the **start year** when the debt begins (the year the loan was taken out or when payments
  start). Payments are calculated from this year forward for the duration of the term.
- *term* is the **loan term in years** (the total number of years over which the debt will be repaid).
  The loan ends in year + term. For example, a loan starting in 2025 with a 30-year term ends in 2055.
- *amount* is the **principal amount** of the debt (in dollars) at the start year. This is the initial
  loan balance that will be amortized over the term.
- *rate* is the **annual interest rate** (percentage) for the debt. This rate is used to calculate
  the fixed annual payment amount based on standard amortization formulas. The payment amount remains
  constant throughout the loan term.

**Debt Payment Calculation:**
- Debt payments are calculated using standard amortization formulas based on the principal amount,
  interest rate, and term.
- Annual payments are made each year from the start year until the loan is fully paid off
  (start year + term).
- Debt payments are **not included** in the net spending amount and are treated as separate expenses.
- Any remaining debt balance at the end of the plan will be deducted from savings accounts.
- If a bequest of zero is specified, the optimizer will ensure sufficient funds remain in savings
  accounts to pay off all remaining debts.

*Fixed Assets* are used to track illiquid assets such as a house, real estate, collectibles,
or restricted stocks. Fixed-rate annuities with a lump sum can also be modeled. Assets can be
reported in the current year or acquired in future years. In the year of disposition (yod), the proceeds
will be separated in three portions: tax-free, ordinary income, and capital gains, depending on
the asset, and be taxed appropriately.

The *Fixed Assets* worksheet looks like the following:

|active|name|type|year|basis|value|rate|yod|commission|
|--|--|--|--|--|--|--|--|--|
| | | | | | | | | |

where:
- *active* is a Boolean value (`TRUE` or `FALSE`) that allows to turn fixed assets on or off in the
  calculations. This is useful for *case* comparison purposes. If not specified or set to `TRUE`,
  the asset is included in calculations.
- *name* is a unique identifier for the fixed asset (e.g., "Primary Residence", "Rental Property").
- *type* is one of *residence*, *real estate*, *collectibles*, *precious metals*, *stocks*, and *fixed annuity*.
  In the current version, only fixed-rate lump-sum annuities can be represented. The asset type determines
  the tax treatment upon disposition (see Asset Lifecycle section below).
- *year* is the **reference year** (this year or after). If the year is in the past, it will be
  automatically reset to the current year when reading from the HFP file. Assets acquired in
  the future have a future reference year. The asset is considered assessed (current) or acquired (future)
  at the beginning of the year.
- *basis* is the **cost basis** of the asset (in reference-year dollars). This is typically the original purchase price
  or adjusted basis for tax purposes. The basis is used to calculate capital gains or losses upon disposition.
- *value* is the **value in reference-year dollars**. This value represents the asset's worth
  at the beginning of the reference year, and it grows from the reference year to the disposition
  year using the specified growth rate (no inflation conversion is applied).
- *rate* is the **annual growth rate** (percentage) applied from the acquisition year to the disposition year.
  This rate is used to calculate the future value of the asset at the time of disposition.
- *yod* is the **year of disposition**. Assets are disposed at the beginning of the year specified.
  Negative values count backward from the end of the plan: -1 is the final plan year, -2 is the
  year before that, and so on. A value of 0 means the asset is liquidated at the end of the plan
  and added to the bequest.
  If the disposition year is beyond the plan duration, the asset is liquidated at the end of the
  last year of the plan and added to the bequest (no taxes applied, step-up in basis for heirs).
- *commission* is the **sale commission** (percentage) charged when the asset is disposed. This percentage
  is applied to the future value of the asset at disposition to calculate the net proceeds after commission.

**Asset Lifecycle:**
- Assets are **acquired at the beginning** of the year specified in the *year* column.
- Assets are **disposed at the beginning** of the year specified in *yod* (if within the plan duration).
- The asset value grows from the acquisition year to the disposition year using the specified growth rate.
- If *yod* is beyond the plan duration, the asset is **liquidated at the end of the last year** of the plan
  and added to the bequest value (no taxes, as assets pass to heirs with step-up in basis).
- Assets disposed during the plan (yod within plan duration) generate taxable proceeds in the year of disposition.

#### :material/currency_exchange: Fixed Income
This page is for entering data related to the individual's anticipated fixed income
from pensions and social security.
Unlike other parts of the user interface, amounts on this page are
monthly amounts in today's \\$ and not in thousands.
The monthly amounts to be entered for social security are the Primary Insurance Amounts (PIA)
which are a critical part used by the Social Security Administration (SSA) for calculating benefits.
The PIA monthly amounts are always in today's \\$: this means that PIA numbers need to
be updated every year as they are modified by cost of living adjustments (COLA).
The PIA is equivalent to the monthly benefit
that one would receive at full retirement age (FRA), which varies between 65 and 67 depending
on the birth year.
The SSA also provides a future estimate of benefits at FRA by projecting current
earnings until reaching FRA. You can use this number if you are comfortable
with the underlying assumption that you will continue to work until FRA, at a salary
similar to last year's.
A way to get a more robust PIA estimate
is to use an online calculator such as [ssa.tools](https://ssa.tools/calculator).
This tool requires the full earning records from one's personal account
on the SSA website. The table listing all earning records from the SSA web page needs
to be copied and pasted as instructed.
Follow instructions carefully and do not cut from the PDF version
as it can contain aggregated years.
Please see
[this page](https://ssa.tools/guides/earnings-record-paste) for common input errors.
After making sure that all entries are valid, paste these data into the tool.
Enter birth year and month and number of years the individual is planning
to continue to work, if any.

Note that the year and month entered are the month when you receive your first
benefits. Most likely, you will have claimed a month earlier as the first
check follows the month when you claim benefits.

*Owl* considers the exact FRA associated with the individual's birth year and adjusts the PIA
according to the age (year and month) when benefits are claimed. Total amount received
during the first year of benefits (if in the future) is adjusted for situations
when benefits do not cover the full year.
This is important for bridging the transition to retirement.
Spousal benefits are calculated under the assumption that those benefits
are claimed at the latest date at which both spouses have claimed benefits.
Survivor benefits rule provides the largest of both benefits to the survivor. Complex
cases involving divorce or deceased spouses are not considered.

*Owl* does not optimize social security benefits.
You have to design (and explore) your own strategy, which
might often involves personal goals such as ensuring maximum
survivor benefits, or maximum lifetime benefits.
A great website for guidance on when to start taking social security is
[opensocialsecurity.com](https://opensocialsecurity.com).
And obviously there are
[ssa.tools](https://ssa.tools), and [ssa.gov](https://ssa.gov).

Pensions amounts, if any, are also entered on this page.
While social security is always adjusted for inflation, pensions can optionally be
indexed for inflation by selecting the corresponding button.
As for social security, the selected month age, combined with your birth month,
determines the exact time benefits start in the first year and the total
annual amount for the first year is adjusted accordingly.

#### :material/savings: Savings Assets
This page allows to enter account balances in all savings accounts.
Notice that all amounts are entered in units of \\$1,000, referred to as (\\$k).

Three types of savings accounts are considered and are tracked separately for spouses:
- Taxable savings accounts (e.g., investment accounts, CDs),
- Tax-deferred savings accounts (e.g., 401k, 403b, IRA),
- Tax-free savings accounts (e.g., Roth 401k, Roth IRA).

Account values are assumed to be known at the beginning of the current year,
which is not always possible. For that purpose,
the `Account balance date` has the effect of back projecting the amounts entered
to the beginning of the year using the return rates and allocations
assumed for the first year. If withdrawals contributing to the
net spending were already performed for the current year,
true account balances should be corrected to reflect values as of Jan 1st.

For married couples, the spousal `Beneficiary fractions` associated with each account
can be configured, as well as a surplus deposit fraction. The first one controls
how much is left to the surviving spouse while the second determines
how to split potential surplus budget moneys between the taxable accounts of the spouses.
When the `Beneficiary fractions` are not all 1, it is recommended to deposit all
surplus moneys in the taxable account of the first individual to pass. Otherwise,
the optimizer will find creative solutions that can generate surpluses in order
to maximize the final bequest. Finally, when fractions between accounts are not all equal,
it can take longer to solve (minutes) as these *cases* trigger the use
of binary variables which involves more complex algorithms.
In some situations, creative transfers from tax-deferred savings accounts to taxable
savings accounts, through surpluses and deposits, can be part of the optimal solution.

Setting a surplus fraction that deposits some or all surpluses in the survivor's account
can also sometimes lead to slow convergence. This is especially noticeable when solving with
varying rates and not so common when using fixed rates.
When using varying rates, it is recommended to set surpluses to be
deposited in the taxable account of first spouse to pass unless exploring specific scenarios.

#### :material/percent: Asset Allocation
This page allows you to select how to partition your assets between 4 investment options,
one equity and three fixed-income securities:
- S&P 500,
- Corporate Bonds Baa,
- 10-year Treasury Notes,
- Cash assets assumed to follow inflation.

When using historical data, the term S&P 500 represents the real index. However,
when selecting non-historical rates, the term can represent any mix of stocks or equities
(domestic, international, emerging, etc.).
The main difference between equities and fixed securities lies
in the tax treatment of gains realized in the taxable account:
equities will be taxed differently than fixed securities.
Cash assets are securities such as Treasury Inflation-Protected Securities (TIPS)
considered to merely track inflation and therefore remain at constant value.

Two choices of asset allocations are possible:
`account` and `individual`. For `account` type, each type
of individual savings account is associated with its own asset allocation ratios.
It is wise to be more aggresive in tax-exempt accounts and more conservative in
taxable investment accounts. This choice will naturally push the optimizer
to load more assets into the tax-exempt accounts through Roth conversions.
These Roth conversions can be artificially driven by the better return rates
provided by the tax-exempt accounts. A more neutral approach is to select `individual`.
For `individual`, it is assumed that all savings accounts of a given
individual follow the same allocation ratios. You should experiment with both.
A smarter approach would be to optimize allocation ratios in the different accounts
subject to the constraint of a global allocation ratio that includes all assets.
This, however, creates a quadratic problem that cannot be simply solved by a linear
programming solver. A future version of *Owl* might tackle this issue using a different strategy.

Allocation ratios can vary over the duration of the *case*, starting
from an `initial` allocation ratio at the beginning of the *case*
to a `final` allocation ratio at the passing of the individual.
It is assumed that the accounts are regularly
rebalanced to maintain the prescribed allocation ratios.
A gliding function (either `linear` or an `s-curve`) interpolates the values
of the allocation ratios from the `initial` values to the `final` values as the *case* progresses in time.
When an `s-curve` is selected, two additional parameters controlling the shape of the transition
will appear, one for the timing of the inflection point measured in years from now,
and the other for the width of the transition, measured in +/- years from the inflection point.

#### :material/monitoring: Rates Selection
This page allows you to select the return rates over the
time span of the *case*. All rates are nominal and annual.
There are two major types of rates:
- `Fixed` - staying the same from one year to another:
    - `conservative`,
    - `optimistic`,
    - `historical average` - i.e., average over a range of past years,
    - `user` - rates are provided by the user.
- `Varying` - changing from year to year:
    - `historical` - using a rate sequence which happened in the past,
    - `histochastic` - using stochastic rates derived from statistics over a time range of historical rates,
    - `stochastic` - using stochastic rates created from statistical parameters specified by the user.

These rates are the annual rates of return for each of the assets considered.
The types of asset are described in the previous section.
Rates for the S&P 500 equities include dividends.
A roundup of expert opinions on stock and bond return forecasts for the next decade can be found
[here](https://www.morningstar.com/portfolios/experts-forecast-stock-bond-returns-2025-edition) for 2025.

An option to set the dividend rate for your stock portfolio is available.
This [reference](https://us500.com/tools/data/sp500-dividend-yield) provides
historical S&P 500 dividend yields over different periods.
This page also includes some adjustments related to future tax rates. One is the anticipated
tax rate that heirs will pay on the tax-deferred portion of the bequest. Another setting is related
to the year when the OBBBA rates are anticipated to return to pre-Tax Cut and Job Act
rates.

#### :material/tune: Optimization Parameters
This page allows you to select the objective function to optimize.
One can choose between maximizing the net spending amount subject to the constraint
of a desired bequest, or maximizing a bequest, subject to the constraint of providing
a desired net spending amount.
As one of the two choices (net spending or bequest) is selected as the value to maximize,
the other becomes a constraint to obey.

The maximum amount for Roth conversions and which spouse can execute them is configurable.
Roth conversions are optimized for reducing taxes and maximizing the selected objective function,
unless the `Convert from contributions file`
button is toggled, in which case Roth conversions will not be optimized,
but will rather be performed according to
the *Roth conv* column on the
[Wages and Contributions](#work-history-wages-and-contributions) page.
A year from which Roth conversions can begin to be considered can also be selected:
no Roth conversions will be allowed before the year specified.

A **self-consistent loop** is an iterative calculation method used to compute values that are difficult
to integrate directly into a linear program. The loop works by:
1. Solving the optimization problem with initial estimates for these values
2. Calculating the actual values based on the solution
3. Re-solving the problem with the updated values
4. Repeating until the values converge (stop changing significantly)

This method is used for the net investment income tax (NIIT),
the rate on capital gains (0, 15, or 20%), the phase out of the additional exemption for seniors,
and potentially the Medicare and IRMAA premiums.
Turning off the self-consistent loop will default all these values to zero.

**Medicare and IRMAA calculations** can be handled in three ways:

- **`None`**: Medicare premiums are ignored (set to zero). This is the fastest option but least accurate.

- **`loop` (self-consistent loop)**: Medicare premiums are calculated iteratively after each optimization solution.
  The optimizer finds the best strategy, then Medicare premiums are computed based on that strategy's income (MAGI),
  and the problem is re-solved with those premiums as fixed costs. This process repeats until the premiums stabilize.
  This is the **recommended default** as it provides good accuracy with reasonable computation time.
  However, when income is near an IRMAA bracket boundary, the solution may oscillate slightly between iterations.

- **`optimize` (full optimization)**: Medicare premiums are integrated directly into the optimization problem
  as decision variables. The optimizer simultaneously finds the best financial strategy AND the optimal Medicare
  premium bracket, considering all trade-offs. This is the **most accurate** method but can be significantly slower
  (sometimes taking many minutes) due to the additional binary variables required. Use this option for single-case
  analysis when you want the most precise results, and compare with self-consistent loop results to verify.
  **Do not use this option** when running multiple scenarios such as Monte Carlo simulations, as the computation
  time would be prohibitive.

Medicare premiums start automatically in the year each individual reaches age 65.

An additional setting allows to turn off mutually exclusive operations,
such as Roth conversions and withdrawals from the tax-free account.
Enabling these mutually exclusive constraints avoids both these situations.
Surprinsingly, dropping these constraints can lead to slightly different optimal points
for reasons that escape me.

If the current age of any individual in the *case* makes them eligible
for Medicare within the next two years,
additional cells will appear for entering the MAGI's for the
past 1 or 2 years, whichever applies. Values default to zero.
These numbers are needed to calculate the Income-Related Monthly Adjusted Amounts (IRMAA).

Different mixed-integer linear programming solvers can be selected.
This option is mostly for verification purposes.
All solvers tested
(HiGHS, COIN-OR Branch-and-Cut solver through PuLP, HiGHS through PuLP, and MOSEK)
provided very similar results.
Due to the mixed-integer formulation, solver performance is sometimes unpredictable.
In general, CBC tends to be slower, partly because of the algorithm,
and partly because it solves the problem through a model description saved in
a temporary file requiring I/O.
In most cases, selecting `HiGHS` will provide great results in the shortest time.

The time profile modulating the net spending amount
can be selected to either be `flat` or follow a `smile` shape.
The *smile* shape has three configurable parameters: a `dip` percentage
a linear `increase` (or decrease if negative), over the time period (apart from inflation),
and a time `delay`, in years from today, before the non-flat behavior starts to act.
Values default to 15%, 12%, and 0 year respectively, but they are fully configurable
for experimentation and to fit your anticipated lifestyle.

A `slack` variable can also be adjusted. This variable allows the net spending to deviate from
the desired profile in order to maximize the objective. This is provided mostly for educational purpose
as maximizing the total net spending will involve leaving the savings invested for as long as possible,
and therefore this will favor smaller spending early in the *case* and larger towards the end.
This tension between maximizing a dollar amount and the utility of money then becomes evident.
While the health of the individuals and therefore the utility of money is higher at the beginning
of retirement, maximizing the total spending or bequest will pull in the opposite direction.

For married couples, the survivor's
net spending percentage is also configurable. A value of 60% is typically used.
The selected profile multiplies
the net spending *basis* which sets the resulting spending
amounts over the duration of the *case*.
Notice that *smile* curves are re-scaled to have the same total spending as flat curves:
for that reason they do not start at 1.

--------------------------------------------------------------------------------------
### :orange[Single Scenario]

#### :material/stacked_line_chart: Graphs
This page displays various plots from a single scenario based on the selections made
in the [Case Setup](#case-setup) section.
This simulation uses a single instance of a series of rates, either fixed or varying,
as selected in the [Case Setup](#case-setup) section.
The outcome is optimized according to the chosen parameters: either maximize the
net spending, of maximize the bequest under the constraint of a net spending amount.
Various plots show the results, which can be displayed in today's \\$ or
in nominal value.

A button allows to re-run the *case* which would generate a different result
if the chosen rates are `histochastic` or `stochastic`. Each graph can be seen
in full screen, and are interactive when using the `plotly` library.
Graphs can be drawn using the `matplotlib` or `plotly` libraries as
selected in the [Settings](#settings-settings) section described below.

#### :material/data_table: Worksheets
This page shows the various worksheets containing annual transactions
and savings account balances in nominal \\$.
Savings balances are values at the beginning of the year, while other quantities
are for the full year.
Each table can be downloaded separately in csv format, or all tables can be downloaded
jointly as a single Excel workbook by clicking on the `Download Worksheets` on the
[Output Files](#description-output-files) page.
Note that all values here (worksheets and workbook) are in \\$, not in thousands.
The first few lines of the **Sources** worksheets are the most important
as these lines are the only ones that are actionable in the near term.

#### :material/description: Output Files
This page allows to compare *cases* and save files for future use.
First, it shows a synopsis of the computed scenario by
displaying sums of income, bequest, and spending values over the duration of the *case*.
Note that all tables are scrollable and can be seen in full-screen mode.
If multiple *cases* were configured and run (most likely through copying and
modifying the parameters), they will be compared in that panel provided they were made
for the same individuals and years spans. Column on the left shows the values for the selected case
while those on the right shows the differences.
The contents of the synopsis can be downloaded as a plain text file by
clicking the button below it.
An additional button allows to rerun all *cases*,
ensuring that the table provides an accurate comparison
of the parameters selected for each case.

Another section called **Excel Workbooks** allows
to save the contents of the tables on corresponding pages as a single Excel workbook.
The `Download Wages and Contributions file` will save the data displayed on the
[Wages and Contributions](#work-history-wages-and-contributions) page while the
`Download Worksheets` will save all tables displayed
on the [Worksheets](#data-table-worksheets) page as a single Excel file.

Similarly, all parameters used to generate the *case* are collected in *toml* format and displayed.
The `Download case parameter file...` button allows to save the parameters of the selected scenario
to a *case* file for future use.

With the *case* parameter file and the **Wages and Contributions** worksheet,
the same *case* can be reproduced at a later time by uploading
them through the widgets on the [Create Case](#person-add-create-case)
and [Wages and Contributions](#work-history-wages-and-contributions) pages,
respectively.

--------------------------------------------------------------------------------------
### :orange[Multiple Scenarios]
There are two different ways to run multiple scenarios and generate a histogram
of results.

#### :material/history: Historical Range
This page is for backtesting your scenario over a selected range of past years,
and generate a histogram of results.
User can run multiple simulations,
each starting at a different year within a range of historical years.
Each simulation assumes that the rates follow the same sequence that happened in the past,
starting from a selected year in the past, and then offset by one year, and so on.
A histogram of results and a success rate is displayed at the end of the run.
$N$ is the number of runs that could fit in the year range selected,
$P$ the probability of success,
$\\bar{x}$ is the resulting average, and $M$ is the median.

If the `Beneficiary fractions` are not all unity, two histograms will be displayed:
one for the partial bequest left at the passing of the first spouse
and the other for the distribution of values of the objective being optimized,
either maximum net spending or maximum bequest left at the passing
of the surviving spouse, depending on the objective function being optimized.

#### :material/finance: Monte Carlo
This page runs a Monte Carlo simulation using time sequences of
annual rates of return that are generated
using statistical methods. At the end of the run,
a histogram is shown, with a probability of success.

The mean outcome $\\bar{x}$ and the median $M$ are provided in the graph, as are the number
of cases $N$ and the probability of success $P$, which is the percentage of cases that succeeded.
Cases that failed are termed infeasible, as the optimizer could not find
values that could satisty all constraints.

As is the case for [Historical Range](#history-historical-range),
if the `Beneficiary fractions` are not all unity, two histograms will also be displayed:
one for the partial bequest left at the passing of the first spouse
and the other for the distribution of values of the objective being optimized,
either maximum net spending or maximum bequest left at the passing
of the surviving spouse.

Linear programming solutions are more expensive than event-driven forward simulators.
Therefore, when considering Monte Carlo simulations, consider:
- Turning off Medicare calculations completely, or at least using self-consistent loop,
- Installing *Owl* and running on your local computer as it can sometimes be
faster than running on the Streamlit host, depending on your hardware.
Moreover, the community server has a
CPU time limit that will stop a session after the quota is reached.
Most likely, this will not happen unless you devise unusually long Monte Carlo runs.

--------------------------------------------------------------------------------------
### :orange[Resources]
#### :material/rocket_launch: Quick Start
This page is the landing page of the application.
It shows new users how to quickly get started by using an example *case* file.

#### :material/help: Documentation
These very pages.

#### :material/settings: Settings
This page allows to select different backends for plotting the graphs.
The `plotly` package is currently the default as the graphs generated are interactive
while `matplotlib` graphs are not.
Plots generated by `matplotlib`, however, have a more traditional look
and form the most mature part of the code.

When using `plotly`, users can zoom and pan, and toggle
traces by clicking on the associated legend. Double clicking on a legend item
selects only this item. Double-clicking on a disabled item restores all traces.
A copy of the plot can also be saved as a *png* file. Both `matplotlib` and `plotly`
graphs can be seen in full-screen mode.

The position of the menubar can be selected to be at the top or as a sidebar.
The sidebar menu can also be collapsed if needed.
Default behavior is to have the menubar at the top, unless on a mobile device.

###### Streamlit App and Theme
If you are accessing *Owl* remotely on the Streamlit Community Server through the Chrome browser,
the Chrome performance manager might disable hidden or inactive tabs.
This could cause your *Owl* session to inadvertently reset when idling for too long,
and losing the state of the calculator.
The best way to avoid this situation is to run the web page through the Streamlit app on your device.
This is done by clicking the '+" icon shown at the right end of the browser URL bar,
showing *App available: Install Streamlit*.
The app provides more screen space as it doesn't have a navigation bar.
On a mobile device, saving the page to the home screen will achieve the same result.
A similar timing problem can happen if your simulations
(Monte Carlo) are extremely long.
The Streamlit community server has a hard resource limit
on CPU time that might stop your calculations before completion.
I could successfully run 1,000 simulations using the Streamlit app while
being hosted on the Streamlit community server.
However, if you are contemplating running Monte Carlo simulations
with thousands of *cases* routinely,
you should definitely consider installing and running *Owl*
locally on your computer, either natively or through a container.
See instructions on the GitHub repository for how to proceed.

If not using the Streamlit app, going full screen while in the Chrome browser
can also greatly improve the visualization of graphs and worksheets
(achieved by pressing F11 on Windows, or Ctl+Cmd+F on MacOS).

*Owl*'s default theme is the *Dark* mode but a *Light* theme is also available by
clicking on the three vertical dots located on the upper right of the app
and selecting the **Settings** option.

#### :material/error: Logs
Messages coming from the underlying *Owl* calculation engine are displayed on this page.
This page is mainly used for debugging purposes.

#### :material/info: About *Owl*
Credits and disclaimers.

--------------------------------------------------------------------------------------
### :orange[Tips]
#### :material/lightbulb_2: Advice on Optimization and Roth Conversions
*Owl* can optimize explicitly for Medicare costs but these can sometimes be
costly computations. This approach is included in the current version but
be aware that computing time can be unpredictable
due to the additional complexity and the number of binary variables involved.
As a second option, a self-consistent loop is provided which consists in adding
Medicare costs after the optimization step, and then iterate to convergence.
In this case, the suggested Roth conversions can sometimes lead to
smaller net spending or bequest than when no Roth conversions are made.
This is due to higher Medicare costs triggered by the increased MAGI
resulting from Roth conversions
which are factored in during the optimization step.

In general, one should **always** run comparisons between *cases*
with and without Roth conversions. These comparisons will help quantify
the effects of the suggested conversions. Optimizers will give the "best" approach
even if it means only generating one more dollar.

While considering Roth conversions,
always keep in mind that all projections rely on our current best assumptions.
To account for the effects of potential changes in future income tax rates,
one can use a termination year for current tax rates to revert to higher rates.

#### :material/rule_settings: Typical Workflow
A typical workflow would look like the following:
1) Create a base *case* representing your basic scenario;
2) Copy the base *case* and modify the parameter you want to investigate;
3) Repeat 2) with other end-member values of the parameter you would like to consider;
4) Run all *cases* and compare them on the [Output Files](#description-output-files) page.

To make it more concrete, here is an example
where one would like to investigate the effects of Roth conversions
on total net spending.
1) Create a *case* called, say, *2025 - Base case*.
Fill in all parameters representing your goals and situation.
Upload file or fill-in values for Wages and Contributions.
Let's say this *case* allows for Roth conversions up to \\$100k.
2) Copy the base case, call it *2025 - No Roth conversions* and
set maximum Roth conversions to 0.
3) Copy the base *case* again, call it *2025 - No Roth limit* and
set maximum Roth conversions to a very large number, say, \\$800k.
4) Compare all *cases* on the [Output Files](#description-output-files) page.

As mentionned above, the most actionable information is located on the first few lines
of the **Sources** tables on the [Worksheets](#data-table-worksheets) pages.
This is where withdrawals and conversions are displayed for this year and the next few years.

#### :material/mindfulness: Scope of Use
In general, computer modeling is not about predicting the future,
but rather about exploring possibilities.
*Owl* has been designed to allow users to explore multiple parameters
and their effects on their future financial situation while avoiding the trap of overmodeling.
Overmodeling happens when a computer model has a level of detail
far beyond the uncertainty of the problem, which can lead some users to assume
an unjustified level of certainty in the results.

The main goal of retirement financial planning is to characterize
uncertainty and translate this uncertainty into actionable, near-term decisions.
Therefore, as a deliberate choice in design, state tax and complex federal tax rules were
not included into *Owl*. As can be seen from this
[graph](https://marottaonmoney.com/wp-content/uploads/2023/04/Historical-Effective-Rates-Through-2023.jpg),
income tax rates have varied a lot over the last century. Assuming that current rates will
stay fixed for the next 30 years is just unrealistic. But the best assumption
we have is to predict rates from what we currently know,
or by projecting historical data into the future.
This approach allows us to frame the problem within a range of likely scenarios.

Users must always keep in mind that retirement financial planning tools have inherent limitations
and that common sense will always be the best ally. *Cases* need to be revisited
as new information is obtained, allowing to make regular corrections to
the best estimates.
Understanding the limitations of any retirement financial planning tool is absolutely critical
to interpreting the results they provide.
""")
