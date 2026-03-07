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
    st.markdown("## :orange[The **Owl** Retirement Planner]")
    # st.markdown("## :orange[The **Owl** Retirement Planner]\n-------")
    st.markdown("""
### **Owl** - *Optimal Wealth Lab*
#### A retirement financial exploration tool based on linear programming

The goal of **Owl** is to provide a free and open-source ecosystem that has cutting-edge
optimization capabilities, allowing for the new generation of computer-literate retirees
to experiment with their own financial future while providing a codebase where they can learn and contribute.
At the same time, Streamlit provides an intuitive and easy-to-use
interface which allows a broad set of users to benefit from the application
as it only requires basic financial knowledge.

Strictly speaking, **Owl** is not a planning tool, but more an environment for exploring *what if* scenarios.
It provides different realizations of a financial strategy through the rigorous
mathematical optimization of relevant decision variables.
**Owl** is designed for US retirees as it considers US federal tax laws,
Medicare premiums, rules for 401k including required minimum distributions,
maturation rules for Roth accounts and conversions, Social Security rules, etc.
Using a mixed-integer linear programming approach,
two different objectives can currently be optimized: either
maximize the net spending amount under the constraint of a desired bequest,
or maximize an after-tax bequest under the constraint of a desired net spending amount.
In each case, Roth conversions are optimized to reduce the tax burden,
while federal income tax and Medicare premiums (including IRMAA) are calculated.
A full description of the package can be found on the GitHub
the [repository](https://github.com/mdlacasse/Owl), and the mathematical
formulation of the optimization problem can be found
[here](https://github.com/mdlacasse/Owl/blob/main/papers/owl.pdf).
""")
with col3:
    # Use URL-based logo to avoid race conditions with local file access
    logofile = "https://raw.githubusercontent.com/mdlacasse/Owl/main/ui/owl.png"
    st.image(logofile)
    st.caption("Retirement planner with great wisdom")

st.markdown("""
-------
### :orange[Table of Contents]
""")
st.caption("*Use the tabs below to navigate documentation by section.*")

# st.markdown("---")

# Tabs for bite-sized navigation
tab_overview, tab_plan, tab_results, tab_sim, tab_tools, tab_tips = st.tabs([
    "Overview",
    "Plan Setup",
    "Results",
    "Stress Tests",
    "Tools & Help",
    "Tips",
])

# --- Overview tab ---
with tab_overview:
    st.markdown("""
#### Getting Started with Owl
The menu at the top allows you to navigate through the different pages of the application.
Typically, pages under the *Plan Setup* tab would be accessed successively in order,
starting from the top down. Once completed, the user would move to the second tab, *Results*,
to visualize the results.

A `Case selector` box located at the top of each page allows you
to navigate between the different scenarios created.
This box is present on all pages in **Plan Setup** and **Results** sections.
The *case* being currently displayed is marked with a small red triangle.

A typical workflow for exploring different scenarios involves starting with a base
case and then copying+creating derived scenarios with slight changes in the parameters.
A comparison between the different resulting outcomes can be found on the **Reports** page.
The **Typical Workflow** section (Tips tab) goes through a more specific example.

**Owl** uses a full year as the standard unit of time. Most values are therefore entered and
reported as yearly values. These include wages, income, rates, etc. To better align
with numbers from the Social Security Administration, Social Security
and pensions are entered as monthly values.
Dollar values are typically entered in thousands, unless in tables, where they
are entered and reported in unit dollars.
Graphs report values in thousands, either in nominal value or in today's \\$, as selected.

There are five sections in the menu bar:
**Plan Setup**, **Results**, **Stress Tests**, **Tools**, and **Help**.
The documentation is structured along the same menus.
""")

    with st.expander(":material/folder: Definitions", expanded=True):
        st.markdown("""
**Case**
> A *case* is a collection of parameters that fully defines a retirement scenario. A *case* contains
the case name and a short description, the individual's life parameters, fixed income sources, savings account balances,
asset allocation ratios, anticipated rates of return, and optimization parameters.
It also holds a reference to its *Household Financial Profile*, if one is used.

**Household Financial Profile**
> A *Household Financial Profile* (HFP) is an
optional Excel workbook that holds the year-by-year
time-series data for the household: anticipated wages and other income, taxable and retirement
contributions, Roth conversions, and large expenses for each individual, plus optional debts and
fixed assets. When no HFP is provided, wages and contributions are assumed to be zero.
See *Input and Output Files* below for a detailed description of both files.

**Run**
> A *run* is the execution of a *case* using a single instance of parameters,
including rates, either constant or varying.

**Owl** helps the planner to create and run *cases*. By carefully selecting and modifying parameters,
the planner can explore the impacts of differing assumptions and strategies on their financial situation.
""")

    with st.expander(":material/sync_alt: Input and Output Files"):
        st.markdown("""
Every *case* in **Owl** is fully described by two input files and produces three output files.
Together they capture the complete data flow from configuration to results.
In the file names below, `<case>` stands for the *case* name and `<individual>` stands
for an individual's first name (e.g., *Jack* or *Jill*).

##### :material/upload: Input Files

**`Case_<case>.toml`** — *Case parameter file*

This human-readable text file encodes all the scalar parameters of a *case*:
individual demographics (names, birth dates, life expectancies),
savings account balances, asset allocation ratios,
fixed income sources (Social Security, pensions),
run options (objective, Roth conversion strategy, solver options),
the rates selection, and the filename of the associated *HFP* workbook (if any).
It does **not** contain the time-series data from the *Household Financial Profile* itself.

In practice, **users never need to write or edit this file by hand** — the interface
generates it automatically as parameters are entered across the **Plan Setup** pages.
Many ready-to-use example cases can be loaded directly from the **Create Case** page,
making it easy to get started without any manual file preparation.
Once a *case* has run successfully, its case file can be downloaded from the **Reports** page
and reloaded at any future session to restore the exact same configuration.
When uploaded on the **Create Case** page,
all fields in **Plan Setup** are populated automatically.
The naming convention when saving from the interface is `Case_<case>.toml`.

**`HFP_<case>.xlsx`** — *Household Financial Profile workbook*

This Excel workbook holds the year-by-year time-series data that cannot be expressed
as single scalars in the case file. It must contain one sheet per individual, named
after that individual (e.g., *Jack* and *Jill*), each with a **Wages and Contributions**
table covering five years of history through the last year of the plan. Columns include:
anticipated wages, other income, taxable contributions, 401k and Roth 401k contributions,
IRA and Roth IRA contributions, manual Roth conversions, and big-ticket items.

Two optional sheets extend the workbook:
- **`Debts`** — mortgage and loan entries (label, type, start year, term, principal, rate).
- **`Fixed Assets`** — illiquid assets such as real estate or fixed annuities
  (label, type, reference year, cost basis, value, growth rate, year of disposition, commission).

A blank template is available
[here](https://github.com/mdlacasse/Owl/blob/main/examples/HFP_template.xlsx?raw=true).
The naming convention when saving from the interface is `HFP_<case>.xlsx`.
The case file stores the HFP filename internally; matching `<case>` names simply makes the pair easy to identify.

---

##### :material/download: Output Files

After a *case* has been solved, the **Reports** page offers the following downloads:

**`Case_<case>.toml`** — *Saved case parameter file*

Identical in format to the input case file and fully round-trips: re-uploading it
recreates the exact same *case* configuration. If the HFP data were edited directly
in the UI (rather than loaded from a file), this file alone is not sufficient to
reproduce the run — the HFP workbook must also be saved.

**`HFP_<case>.xlsx`** — *Saved Household Financial Profile workbook*

The HFP workbook as currently loaded or edited in the session. Saving it alongside
`Case_<case>.toml` guarantees a fully reproducible *case*.

**`Workbook_<case>.xlsx`** — *Output worksheets*

The primary numerical output of a solved *case*. Contains one worksheet per topic,
all indexed by year:
- **Income** — net spending, taxable ordinary income, taxable capital gains and dividends,
  total tax bills and Medicare premiums.
- **Cash Flow** — full breakdown of all money inflows and outflows for the household.
- **`<individual>`'s Sources** *(one sheet per individual)* — year-by-year sources of spending
  (wages, Social Security, pension, taxable/tax-deferred/tax-free withdrawals, RMDs,
  Roth conversions, big-ticket items).
- **Household Sources** — fixed-asset proceeds (ordinary income, capital gains, tax-free)
  and debt payments.
- **`<individual>`'s Accounts** *(one sheet per individual)* — balances, contributions,
  deposits, withdrawals, and Roth conversions for each of the three account types.
- **Federal Income Tax** — income allocated to each tax bracket, NIIT, LTCG tax,
  early-withdrawal penalty, and the fraction of Social Security that is taxable.
- **`<individual>`'s Allocations** *(one sheet per individual)* — asset allocation percentages
  (stocks, corporate bonds, T-notes, common assets) for each account type over time.

**`Synopsis_<case>.txt`** — *Case summary*

A plain-text table of key metrics (spending, bequest, taxes, etc.) for the solved *case*.
When multiple *cases* sharing the same individuals' names have been solved, additional columns
show the differences between cases for a quick side-by-side comparison.
""")

# --- Plan Setup tab ---
with tab_plan:
    st.markdown("""
This section contains the steps for creating and configuring *case* scenarios.
For new *cases*, every page of this section should be visited and parameters
entered according to your personal situation. To make this process easier,
a progress bar tracking which page has been visited is shown at the bottom of the page.
This bar can also be used to navigate between the pages of the *Plan Setup* section.
The sections below describe the pages under the *Plan Setup* tab and follow the same logical order.
""")

    with st.expander(":material/person_add: Create Case", expanded=True):
        st.markdown("""
The **Create Case** page is where every new scenario begins.
When no case is yet selected, the page displays three columns side by side:
one to create a new *case* from scratch, one to upload a *case* parameter file,
and one to load an example *case* from the repository.
When a case is already selected, an expandable panel at the top of the page
provides the same options for creating or loading additional cases.
This page also allows you to copy and/or rename scenarios, as well as delete them.

For creating a scenario from scratch, (first) name(s), marital status,
birth date(s), and life expectancies are required.
The reason for asking the birth date is that Social Security rules
have special considerations when born on the first days of the month.
If you're not born on a 1st or 2nd day of the month, any other day of the
month will generate the same results.

*Cases* start on Jan 1st of this year and end on December 31st of the year when all individuals
have passed according to the specified life expectancies.

A typical workflow will involve creating
a base *case*, and copying it a few times with slight changes in its parameters
in order to investigate their effects.
Copy renames the *case* by appending a number counter in parentheses, just as creating
a copy of a file on Windows.
It is recommended to rename each *case* to reflect the change in parameters.
When copying a scenario, make sure to visit all pages in the **Plan Setup**
section and verify that all parameters are as intended.
When all *cases* have successfully run,
results of related *cases* are compared side-by-side with differences
in the **Reports** section.
Related *cases* are determined by having the same individuals' names:
anything else can change between *cases*.

##### Creating a case from scratch
Enter a name in the **Create a New Case** text box and press Enter.
One must then provide the birth date of each spouse(s) and their expected lifespan(s).
For selecting your own longevity numbers, there are plenty of predictors on the Internet.
Pick your favorite:
- [longevityillustrator](https://longevityillustrator.org),
- [livingto100](https://www.livingto100.com/calculator),

or just Google *life expectancy calculator*.

##### Using a *case* file
To start from a *case* file, use the **Upload Your Own Case File** widget or pick one
from the **Load a Case Example** dropdown. A *case* file must be uploaded.
These files end with the *.toml* extension, are human readable (and therefore editable),
and contain all the parameters required to characterize a scenario.
An example is provided
[here](https://github.com/mdlacasse/Owl/blob/main/examples/Case_jack+jill.toml?raw=true) and more
can be found in this [directory](https://github.com/mdlacasse/Owl/blob/main/examples/).
Using a *case* file
will populate all the fields in the **Plan Setup** section,
except those in the *Household Financial Profile* (HFP) which get populated
separately by an Excel workbook (see next section).

Once a *case* was successfully run, the *case* file for the *case* being developed
can be saved under the Reports page and can be reloaded at a later time.
Case parameter files can have any name but when saving from the interface,
their name will start with *Case_* followed by the *case* name.
""")

    with st.expander(":material/home: Financial Profile"):
        st.markdown("""
The *Household Financial Profile* (HFP) contains two major sections,
one representing *Wages and Contributions* for each individual, and
the other capturing the household's *Debts and Fixed Assets*.
While the values can be entered manually in each table,
an option is given to upload an Excel file containing all the data,
thus avoiding this tedious exercise.
After a case is created, an HFP upload widget also appears directly on the
**Create Case** page, so both uploads can be done
without leaving that page.
These data include future wages and contributions,
past and future Roth contributions and conversions, large expenses
or large influx of after-tax money, debts, and fixed assets.

##### :material/work_history: Wages and Contributions
Values in the *Wages and Contributions* tables are all in nominal values, and in \\$, not thousands (\\$k).
The **Wages and Contributions** table contains 10 columns titled as follows:

|year|anticipated wages|other inc|taxable ctrb|401k ctrb|Roth 401k ctrb|IRA ctrb|Roth IRA ctrb|Roth conv|big-ticket items|
|--|--|--|--|--|--|--|--|--|--|
|2021 | | | | | | | | | |
| ... | | | | | | | | | |
|2026 | | | | | | | | | |
|2027 | | | | | | | | | |
| ... | | | | | | | | | |
|20XX | | | | | | | | | |

The *other inc* column is optional; older HFP files without it will default to zero.
It contributes to ordinary income (e.g., part-time work, consulting, royalties).
Note that column names are case sensitive and all entries are in lower case.
The easiest way to complete the process of filling this file is either to start from the template
file provided [here](https://github.com/mdlacasse/Owl/blob/main/examples/HFP_template.xlsx?raw=true) or
to fill in the values using the user interface, but this last approach does not provide
Excel capabilities for cross-column calculations.

This file goes five years back in time in order to capture previous contributions and
conversions to Roth accounts.
Entries in columns other than contributions or conversions to Roth accounts
for past years will be ignored by **Owl** but can be left there for documentation purposes.
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
While this approach is somewhat more restrictive than the actual IRS rules,
it avoids unnecessary penalties and is simple to implement.
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
a pension or collect Social Security, and these years are entered elsewhere on the
**Fixed Income** page.

Contributions to your savings accounts are marked as *ctrb*. We use 401k as a term that includes
contributions to 403b as well or any other tax-deferred account, with the exception
of IRA accounts which are treated separately to facilitate data entry.
Contributions to your 401k/403b must also include your employer's
contributions, if any. As these data can be entered in Excel,
one can use the native calculator to enter a percentage
of the anticipated wages for contributions to savings accounts as an easier way to enter the data.
For this purpose, additional columns can coexist in the Excel file
and can be used for tracking other quantities from which
the needed values can be derived. These extra columns will be ignored when the file is processed.

Manual Roth conversions can be specified in the column marked *Roth conv*.
This column is provided to override the Roth conversion optimization in **Owl**.
When the option `Convert as in Wages and Contributions tables` is toggled
in the **Run Options** page,
values from the **Wages and Contributions** table will be used and no optimization on Roth conversions
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
the `Download Financial Profile workbook` on the
**Reports** page. This allows you to rerun the same *case* at a later time
by reloading the same **Household Financial Profile** workbook (which contains the Wages and Contributions data).

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
as **Owl** assumes taking the standard tax deduction. Be mindful that selling a house near
the end of the plan while leaving a zero bequest may lead to infeasible solutions.

The *Household Financial Profile* workbook can optionally contain a *Debts* sheet and
a *Fixed Assets* sheet to store these data.
The *Debts* worksheet looks like the following:

|active|name|type|year|term|amount|rate|
|--|--|--|--|--|--|--|
| | | | | | | |

where:
- *active* is a Boolean value (`TRUE` or `FALSE`) that allows you to turn debts on or off in the
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
- *active* is a Boolean value (`TRUE` or `FALSE`) that allows you to turn fixed assets on or off in the
  calculations. This is useful for *case* comparison purposes. If not specified or set to `TRUE`,
  the asset is included in calculations.
- *name* is a unique identifier for the fixed asset (e.g., "Primary Residence", "Rental Property").
- *type* is one of *residence*, *real estate*, *collectibles*, *precious metals*, *stocks*, and *fixed annuity*.
  The asset type determines the tax treatment upon disposition (see Asset Lifecycle section below).
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
""")

    with st.expander(":material/currency_exchange: Fixed Income"):
        st.markdown("""
This page is for entering data related to the individual's anticipated fixed income
from pensions and Social Security.
Unlike other parts of the user interface, amounts on this page are
monthly amounts in today's \\$ and not in thousands.
The monthly amounts to be entered for Social Security are the Primary Insurance Amounts (PIA)
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
Follow the instructions carefully and do not copy from a PDF version,
as it can contain aggregated years.
Please see
[this page](https://ssa.tools/guides/earnings-record-paste) for common input errors.
After making sure that all entries are valid, paste these data into the tool.
Enter birth year and month and number of years the individual is planning
to continue to work, if any.

Note that the year and month entered correspond to when you receive your first
benefit payment. Most likely, you will have claimed a month earlier as the first
check follows the month when you claim benefits.

**Owl** considers the exact FRA associated with the individual's birth year and adjusts the PIA
according to the age (year and month) when benefits are claimed. Total amount received
during the first year of benefits (if in the future) is adjusted for situations
when benefits do not cover the full year.
This is important for bridging the transition to retirement.
Spousal benefits are calculated under the assumption that those benefits
are claimed at the latest date at which both spouses have claimed benefits.
Survivor benefits rules provide the larger of the two benefits to the survivor. Complex
cases involving divorce or deceased spouses are not considered.

**Owl** does not optimize when to claim Social Security benefits.
You have to design (and explore) your own strategy, which
often involves personal goals such as ensuring maximum
survivor benefits, or maximum lifetime benefits.
A great website for guidance on when to start taking Social Security is
[opensocialsecurity.com](https://opensocialsecurity.com).
And obviously there are
[ssa.tools](https://ssa.tools), and [ssa.gov](https://ssa.gov).

The *Advanced options* expander allows you to model trust fund shortfall scenarios.
You can reduce Social Security benefits by a given percentage starting in a
specified year. The default starting year is 2033, the current SSA Trustees Report
projection for OASI trust-fund exhaustion (e.g. a 23% cut from 2033).
Use 0% reduction for the baseline case. The starting year field is disabled when
the reduction percentage is zero. Both percentage and starting year must be provided
when enabling a reduction.

Pension amounts, if any, are also entered on this page.
While Social Security is always adjusted for inflation, pensions can optionally be
indexed for inflation by selecting the corresponding button.
As for Social Security, the exact age in years and months, combined with your birth month,
determines the exact time benefits start in the first year and the total
annual amount for the first year is adjusted accordingly.
""")

    with st.expander(":material/savings: Account Balances"):
        st.markdown("""
This page allows you to enter account balances in all savings accounts.
Notice that all amounts are entered in units of \\$1,000, referred to as (\\$k).

Three types of savings accounts are considered and are tracked separately for spouses:
- Taxable savings accounts (e.g., investment accounts, CDs),
- Tax-deferred savings accounts (e.g., 401k, 403b, IRA),
- Tax-free savings accounts (e.g., Roth 401k, Roth IRA).

Account values are assumed to be known at the beginning of the current year,
which is not always possible. For that purpose,
the `Account balance date` has the effect of back-projecting the amounts entered
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
the optimizer will find unexpected solutions that can generate surpluses in order
to maximize the final bequest. Finally, when fractions between accounts are not all equal,
it can take longer to solve (minutes) as these *cases* trigger the use
of binary variables which involves more complex algorithms.
In some situations, unconventional transfers from tax-deferred savings accounts to taxable
savings accounts, through surpluses and deposits, can be part of the optimal solution.

Setting a surplus fraction that deposits some or all surpluses in the survivor's account
can also sometimes lead to slow convergence. This is especially noticeable when solving with
varying rates and not so common when using constant rates.
When using varying rates, it is recommended to set surpluses to be
deposited in the taxable account of first spouse to pass unless exploring specific scenarios.
""")

    with st.expander(":material/percent: Asset Allocation"):
        st.markdown("""
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
It is wise to be more aggressive in tax-exempt accounts and more conservative in
taxable investment accounts. This choice will naturally push the optimizer
to load more assets into the tax-exempt accounts through Roth conversions.
These Roth conversions can be disproportionately driven by the better return rates
provided by the tax-exempt accounts. A more neutral approach is to select `individual`.
For `individual`, it is assumed that all savings accounts of a given
individual follow the same allocation ratios. You should experiment with both.
A smarter approach would be to optimize allocation ratios in the different accounts
subject to the constraint of a global allocation ratio that includes all assets.
This, however, creates a quadratic problem that cannot be simply solved by a linear
programming solver. A future version of **Owl** might tackle this issue using a different strategy.

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
""")

    with st.expander(":material/monitoring: Rates Selection"):
        st.markdown("""
This page controls the annual rates of return used throughout the plan.
All rates are **nominal** (not inflation-adjusted) and expressed as yearly percentages.
Owl tracks four asset classes:
- **S&P 500** — U.S. large-cap equities; rates include dividends. When not using historical
  data, this label can represent any mix of equities (domestic, international, emerging, etc.).
- **Corporate Bonds Baa** — Investment-grade corporate debt with moderate default risk.
- **10-year Treasury Notes** — Medium-term U.S. government debt; interest is state/local tax-exempt.
- **Cash Assets / Inflation** — TIPS-like securities assumed to track inflation, holding constant
  real value.

---
##### Constant rates
Constant rates stay the same for every year of the plan. Choose from:
- `trailing-30` — constant rates equal to the 30-year trailing geometric mean of annual returns. A reasonable middle-ground assumption.
- `conservative` — a pessimistic but plausible set of forecasts.
- `optimistic` — a more bullish set of forecasts.
- `historical average` — geometric means computed over a selectable historical window
  (1928–present by default). Because averages can be negative when the window is narrow,
  the rate fields allow negative values in this mode.
- `user` — enter your own values for each asset class.

A roundup of expert stock and bond return forecasts can be found
[here](https://www.morningstar.com/portfolios/experts-forecast-stock-bond-returns-2025-edition).

> **Note:** Constant rates produce a single deterministic outcome and do not capture
> **sequence-of-returns risk** — the danger that poor returns early in retirement can
> permanently deplete a portfolio even if the long-run average is favorable. For a more
> realistic assessment of that risk, use one of the varying stochastic methods below.

---
##### Varying rates
Varying rates change year by year, enabling realistic uncertainty modeling.
There are eight methods:

**`historical`** — Replays the exact year-by-year returns from a selected historical window
in chronological order. Each year of the plan receives the return from one calendar year of
history; the plan horizon must fit within the selected window.
This is deterministic (no randomness) and is the right choice for backtesting: *"how would
this strategy have performed starting in 1970?"*

**`histogaussian`** — Computes the mean returns, volatilities, and cross-asset covariance
from the selected historical window, then draws samples from the **fitted multivariate
normal distribution**. Each year of the plan is an independent draw from that distribution.
Unlike `bootstrap_sor`, no actual historical years are resampled — only their statistical
summary (mean and covariance) is used. The result is parametric and Gaussian, but with
parameters grounded in history rather than supplied by the user. *(Old configs with
`method = "histochastic"` are automatically translated to `histogaussian` when loaded.)*

**`gaussian`** — Draws independently from a multivariate normal distribution each year.
The mean returns, volatilities, and cross-asset correlations are **user-supplied** in the
*Stochastic Parameters* panel. Use this when you have a specific return/risk view that
differs from any historical period. *(Old configs with `method = "stochastic"` are
automatically translated to `gaussian` when loaded.)*

**`lognormal`** — Like `gaussian`, the mean returns, volatilities, and cross-asset
correlations are **user-supplied**. However, samples are drawn from a **log-normal**
distribution: arithmetic parameters are converted to log-space ($\\mu_Z$, $\\Sigma_Z$), a multivariate
normal is sampled in log-space, and returns are recovered as $R = \\exp(Z) - 1$. Advantages
over `gaussian`: returns are strictly bounded below by −100% (no total-loss artifacts),
the distribution is naturally right-skewed (large gains more probable than large losses),
and it is consistent with **Geometric Brownian Motion** — the foundation of most option
pricing theory.

**`histolognormal`** — Like `histogaussian` but fits a **log-normal** model to the
historical window. Log-returns $\\ln(1 + r)$ are computed from history; their mean and
covariance are estimated directly in log-space, and samples are drawn from that fitted
distribution and exponentiated. Inherits all the right-skew and lower-bound advantages
of `lognormal` while deriving its parameters from history rather than user input.

**`bootstrap_sor`** *(Sequence-of-Returns bootstrap)* — Resamples **actual historical years**
from the selected window to build synthetic rate sequences. Because real observations are
used directly (not a fitted distribution), extreme events, fat tails, and cross-asset
patterns that occurred in history are naturally preserved. Four resampling strategies
control how much year-to-year serial structure is retained:
- `iid` *(independent and identically distributed)* — draws individual years independently
  at random with replacement. Each year of the plan is equally likely to be any year from
  the selected window, with no memory of the previous draw. This is non-parametric
  resampling.
- `block` — draws consecutive fixed-length blocks of years, preserving short-run momentum
  and mean-reversion patterns within each block.
- `circular` — like block bootstrap, but wraps around the dataset ends to avoid edge effects
  near the beginning and end of the historical record.
- `stationary` — draws variable-length blocks from a geometric distribution, which produces
  a stationary output process with the correct unconditional mean and covariance.

The block size is adjustable (1 = iid; larger values preserve more serial structure).
`bootstrap_sor` is well-suited for Monte Carlo stress-testing when you want history-derived
randomness that respects multi-year market cycles.

**`var`** *(Vector Autoregression, order 1)* — Fits a VAR(1) model to the selected
historical window and then simulates new rate paths from that model. A VAR(1) captures
explicit year-to-year relationships across all four asset classes simultaneously: each
year's return depends linearly on last year's returns plus a multivariate normal shock.
This means momentum (positive serial correlation) and mean-reversion (negative serial
correlation) observed in the historical data are naturally reproduced. `var` is the most
statistically sophisticated method and is particularly appropriate when the sequence and
persistence of returns matter, as is often the case for sequence-of-returns risk analysis.

**`garch_dcc`** *(Dynamic Conditional Correlation GARCH, Engle 2002)* — Fits a
DCC-GARCH(1,1) model to the selected historical window using a two-step maximum
likelihood procedure. In the first step, a univariate GARCH(1,1) model is estimated
independently for each asset class, capturing **volatility clustering** — the well-documented
tendency for large return moves (up or down) to be followed by further large moves.
In the second step, a DCC layer is fitted to the standardized residuals, modelling
**time-varying cross-asset correlations** that spike during market-stress episodes. Each
simulated year inherits the conditional variance and correlation state from the previous
year, making `garch_dcc` the only Owl method to reproduce both heteroskedasticity and
correlation dynamics. It is most useful when realistic tail behavior and stress-period
contagion are important, such as for retirement scenarios that include equity-heavy portfolios.

---
##### Method comparison

| Method | Rate type | Character | Pros | Cons |
|---|---|---|---|---|
| `trailing-30` | Constant | Deterministic | Long-run geometric mean of trailing 30 years; no parameters | Single outcome; no uncertainty modeling |
| `conservative` | Constant | Deterministic | Simple; clearly stress-tests the downside | Single outcome; no uncertainty modeling |
| `optimistic` | Constant | Deterministic | Simple; tests bullish scenario | Single outcome; no uncertainty modeling |
| `historical average` | Constant | Deterministic | Grounded in a specific historical period | Sensitive to choice of historical window |
| `user` | Constant | Deterministic | Full control over all return assumptions | Accuracy depends entirely on user inputs |
| `bootstrap_sor` | Varying | Stochastic | Preserves fat tails and extreme historical events | IID (independent and identically distributed) mode discards year-to-year serial structure |
| `garch_dcc` | Varying | Stochastic | Realistic volatility clustering and time-varying correlations | Higher per-trial cost; requires ≥ 15 years of history |
| `gaussian` | Varying | Stochastic | Full control over means, volatilities, and correlations | Accuracy depends entirely on user inputs; unbounded downside |
| `histogaussian` | Varying | Stochastic | History-grounded statistics; no user parameters needed | Assumes normally distributed returns; draws are independent |
| `histolognormal` | Varying | Stochastic | History-grounded log-normal; bounded below −100%; right-skewed | Draws are independent; log-normal approximation |
| `historical` | Varying | Deterministic | Exact historical replay; no modeling assumptions | No Monte Carlo; one path per start year |
| `lognormal` | Varying | Stochastic | User-specified parameters; bounded below −100%; right-skewed; GBM-consistent | Accuracy depends entirely on user inputs |
| `var` | Varying | Stochastic | Captures momentum and mean-reversion across all asset classes | More complex; sensitive to choice of historical window |

---
##### Historical range
For all methods that reference history (`historical`, `histogaussian`, `histolognormal`,
`bootstrap_sor`, `historical average`, `var`, and `garch_dcc`), a **Starting year / Ending year** selector appears.
The range determines which calendar years are included in the dataset from which rates
are drawn or statistics are computed. At least two years are required. For `historical`,
the ending year is fixed by the starting year plus the plan horizon.

---
##### Stochastic parameters
When `gaussian` or `lognormal` is selected, a panel with three sub-sections appears:
- **Means (%)** — expected annual return for each asset class.
- **Volatility (%)** — standard deviation of annual returns for each asset class.
- **Correlation matrix** — Pearson correlations between every pair of asset classes.
  Values range from −1 (perfect inverse) to +1 (perfect co-movement); 0 means no
  linear relationship. The diagonal is always 1. The matrix must be positive semi-definite,
  i.e., you cannot set correlations to arbitrary values — the optimizer will warn if the
  matrix is invalid.

For the other varying methods, these fields are displayed but disabled; the statistical
parameters are derived automatically from the historical data.

---
##### Which method enables Monte Carlo?
Monte Carlo simulations (see the **Stress Tests** page) require a **stochastic** method —
one that generates a fresh random sample for each simulation trial. The methods that
support Monte Carlo are: `histogaussian`, `histolognormal`, `gaussian`,
`lognormal`, `bootstrap_sor`, `var`, and `garch_dcc`.
The `historical` method is deterministic (it always produces the same sequence for a
given starting year) and therefore cannot be used for Monte Carlo.

---
##### Dividend rate and tax settings
An option to set the dividend rate for your stock portfolio is available under
*Advanced options*. This [reference](https://us500.com/tools/data/sp500-dividend-yield)
provides historical S&P 500 dividend yields over different periods.

Two tax-related settings are also accessible:
- **Heirs marginal tax rate** — the marginal rate your beneficiaries would pay on
  inherited tax-deferred balances. Used to compute the after-tax value of a bequest.
- **OBBBA expiration year** — the projected year when the One Big Beautiful Bill Act
  tax rates are expected to revert to pre-Tax Cuts and Jobs Act levels. Owl uses different
  tax brackets before and after this year.

---
##### Rate sequence controls (Advanced options)
For all varying methods, two tools let you shift the temporal position of the rate series:
- **Reverse sequence** — reverses the rate series along the time axis (last year becomes
  first). Useful for stress-testing a "worst years first" scenario.
- **Roll (years)** — shifts the series by a given number of years; values wrap around
  so no data is lost. Allows starting the plan at a different point in the same sequence.

The `roll` operation is applied before `reverse`.
These controls do not apply to constant rates since the same value is used every year.

---
##### Reproducible rates (Advanced options)
For the stochastic methods (`histogaussian`, `histolognormal`, `gaussian`, `lognormal`, `bootstrap_sor`, `var`, `garch_dcc`),
an option to **Enable reproducible rates** is available. When checked, the random number
generator is seeded with a fixed value so the same rate sequence is produced every time
the case is run. This is useful for isolating the effect of other parameters (spending
targets, allocations, Roth strategy) while holding the random scenario constant.

---
##### References
- Engle, R. F. (2002). *Dynamic Conditional Correlation: A Simple Class of Multivariate Generalized
  Autoregressive Conditional Heteroskedasticity Models.*
  Journal of Business & Economic Statistics, 20(3), 339–350.
  *(Foundational paper for the `garch_dcc` method.)*
- Campbell, J. Y., & Viceira, L. M. (2002). *Strategic Asset Allocation: Portfolio Choice for
  Long-Term Investors.* Oxford University Press.
  *(Basis for the `var` method.)*
- Efron, B., & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap.*
  Chapman & Hall/CRC. *(Foundation for `bootstrap_sor` resampling methods.)*
- Hull, J. C. (2017). *Options, Futures, and Other Derivatives* (10th ed.). Pearson.
  *(Basis for the `lognormal` and `histolognormal` log-normal / GBM framework.)*
""")

    with st.expander(":material/tune: Run Options"):
        st.markdown("""
This page allows you to select the objective function to optimize.
One can choose between maximizing the net spending amount subject to the constraint
of a desired bequest, or maximizing a bequest, subject to the constraint of providing
a desired net spending amount.
As one of the two choices (net spending or bequest) is selected as the value to maximize,
the other becomes a constraint to obey.

The maximum amount for Roth conversions and which spouse can execute them is configurable.
Roth conversions are optimized for reducing taxes and maximizing the selected objective function,
unless the `Convert as in Wages and Contributions tables`
toggle is on, in which case Roth conversions will not be optimized,
but will rather be performed according to
the *Roth conv* column on the
**Wages and Contributions** page.
A year from which Roth conversions can begin to be considered can also be selected:
no Roth conversions will be allowed before the year specified.

The **Medicare** section has a toggle *Medicare and IRMAA calculations*.
When turned off, Medicare premiums are ignored (set to zero); this is the fastest option but least accurate.
When turned on (the default), Medicare premiums are computed via a self-consistent loop: the optimizer
finds the best strategy, then Medicare premiums are calculated from that strategy's income (MAGI),
and the problem is re-solved with those premiums as fixed costs until they stabilize.
This provides good accuracy with reasonable computation time.

For maximum accuracy, enable *Optimize Medicare (expert)* in the *Advanced options* expander.
That option integrates Medicare premiums directly into the optimization as decision variables,
so the optimizer simultaneously finds the best strategy and premium bracket.
It can be significantly slower (sometimes many minutes) due to additional binary variables.
Use it for single-case analysis; do not use it for Monte Carlo or multiple scenarios.

Medicare premiums start automatically in the year each individual reaches age 65.
If anyone in the case is age 64 or older, inputs appear for `MAGI for [year] ($k)`
for the prior 1 or 2 years (nominal thousands). These values are needed for
Income-Related Monthly Adjusted Amounts (IRMAA). Values default to zero.
A warning appears if Medicare is on while the self-consistent loop is off,
since Medicare in loop mode requires the loop to compute premiums iteratively.

A **self-consistent loop** is an iterative method used for values that are difficult
to integrate into the linear program: the net investment income tax (NIIT),
the capital gains rate (0, 15, or 20%), the phase out of the additional exemption for seniors,
the taxable fraction of Social Security benefits (computed from the IRS provisional income
formula — 0% below \\$25k PI (single) / \\$32k (MFJ); 50% between those and \\$34k (single) / \\$44k (MFJ);
up to 85% above the upper threshold), and Medicare/IRMAA when Medicare is enabled. The loop solves,
recalculates these values from the solution, re-solves, and repeats until convergence.
The *Self-consistent loop calculations* toggle in *Advanced options* turns this on or off;
turning it off defaults all these values to their conservative upper bounds (e.g. 85% SS
taxability for all years).

**Safety Net** settings allow you to enforce a minimum balance in each spouse's taxable account.
The amount is specified in today's dollars and is indexed for inflation over the plan horizon.
These constraints apply from year 2 onward through each individual's life horizon (the first year
is excluded to avoid conflicts with initial balances).
The minimum should ideally be smaller than each spouse's initial taxable balance, otherwise the
optimizer may find the problem infeasible or produce unexpected results.
When maximizing spending with a bequest target, the desired bequest should be at least as large
as the survivor's safety net (in today's \\$), otherwise optimization may be infeasible.
Use this to ensure a reserve of liquid assets is maintained for emergencies or opportunities,
or to reflect a personal preference for keeping a buffer in taxable accounts.

The *Advanced options* expander contains:
- *Self-consistent loop calculations* – when on, iteratively computes NIIT, capital gains rates,
  phase out of senior exemptions, the taxable fraction of SS benefits, and Medicare/IRMAA
  (when Medicare is enabled).
- *Optimize Medicare (expert)* – integrates Medicare into the optimization; enabled only when
  Medicare and IRMAA calculations are on.
- *Disallow same-year surplus deposits and withdrawals from taxable or tax-free accounts*
- *Disallow same-year Roth conversions and tax-free withdrawals*
- *Disallow cash-flow surpluses in the last two years of the plan*
- *Social Security taxability method* (loop, value, or optimize) and, when `value`, fixed SS tax fraction $\\Psi$.
- *Solver* selection (default, HiGHS, PuLP/CBC, PuLP/HiGHS, or MOSEK if available), plus optional extra solver options.

**Social Security Taxability** controls how the taxable fraction of Social Security benefits is determined.
Choose *loop* to compute it dynamically via the self-consistent loop (recommended).
Choose *value* to pin it to a fixed fraction $\\Psi \\in [0, 0.85]$: use 0.0 for low provisional income,
0.5 for mid-range, or 0.85 for high provisional income. Choose *optimize* (expert) to solve taxable SS
exactly within the LP using binary variables; this can be slower and require additional configuration
like increasing the `gap` to ~2% using the *Extra solver options* (i.e. `{"gap":2e-2}`).

Different mixed-integer linear programming solvers can be selected.
Choose `default` to auto-select MOSEK when available, otherwise HiGHS.
The *Extra solver options (expert)* field accepts a JSON dictionary (e.g. `{"key": "value"}`)
that is merged into the solver options; leave empty unless experimenting.
This option is mostly for developer use and verification purposes.
All solvers tested
(HiGHS, COIN-OR Branch-and-Cut solver through PuLP, HiGHS through PuLP, and MOSEK)
provided very similar results.
Due to the mixed-integer formulation, solver performance is sometimes unpredictable.
In general, CBC tends to be slower, partly because of the algorithm,
and partly because it solves the problem through a model description saved in
a temporary file requiring I/O.
In most cases, `MOSEK` will provide the best performance.
Otherwise, selecting `HiGHS` will provide comparable results in a little more time.

The time profile modulating the net spending amount
can be selected to either be `flat` or follow a `smile` shape.
The *smile* shape has three configurable parameters: a `dip` percentage
a linear `increase` (or decrease if negative), over the time period (apart from inflation),
and a time `delay`, in years from today, before the non-flat behavior starts to act.
Values default to 15%, 12%, and 0 year respectively, but they are fully configurable
for experimentation and to fit your anticipated lifestyle.

A `slack` variable can also be adjusted. This variable allows the net spending to deviate from
the desired profile in order to maximize the objective. This is provided mostly for educational purposes
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
""")

# --- Results tab ---
with tab_results:
    st.markdown("Results from a case can be visualized in three different ways.")
    with st.expander(":material/stacked_line_chart: Graphs", expanded=True):
        st.markdown("""
This page displays various plots from a single scenario based on the selections made
in the **Plan Setup** section.
This simulation uses a single series of rates, either constant or varying,
as selected in the **Plan Setup** section.
The outcome is optimized according to the chosen parameters: either maximize the
net spending, or maximize the bequest under the constraint of a net spending amount.
Various plots show the results, which can be displayed in today's \\$ or
in nominal value.

A button allows you to re-run the *case* which would generate a different result
if the chosen rates are `histogaussian` or `gaussian`. Each graph can be seen
in full screen, and are interactive when using the `plotly` library.
Graphs can be drawn using the `matplotlib` or `plotly` libraries as
selected in the Settings section (Tools & Help tab).

""")

    with st.expander(":material/data_table: Worksheets"):
        st.markdown("""
This page shows the various worksheets containing annual transactions
and savings account balances in nominal \\$.
Savings balances are values at the beginning of the year, while other quantities
are for the full year.
Each table can be downloaded separately in csv format, or all tables can be downloaded
jointly as a single Excel workbook by clicking on the `Download Worksheets` on the
**Reports** page.
Note that all values here (worksheets and workbook) are in \\$, not in thousands.
The first line of the individual's **Sources** worksheets is highlighted in blue
indicating that these lines contain actionable items for the current year.
""")

    with st.expander(":material/description: Reports"):
        st.markdown("""
This page allows you to compare *cases* and save files for future use.
First, it shows a synopsis of the computed scenario by
displaying sums of income, bequest, and spending values over the duration of the *case*.
Note that all tables are scrollable and can be seen in full-screen mode.
If multiple *cases* were configured and run (most likely through copying and
modifying the parameters), they will be compared in that panel provided they were made
for the same individuals and year spans. Column on the left shows the values for the selected case
while those on the right shows the differences.
The contents of the synopsis can be downloaded as a plain text file by
clicking the button below it.
An additional button allows you to rerun all *cases*,
ensuring that the table provides an accurate comparison
of the parameters selected for each case.

Another section called **Excel Workbooks** allows
to save the contents of the tables on corresponding pages as a single Excel workbook.
The `Download Financial Profile workbook` will save the data displayed on the
**Wages and Contributions** page
(and the rest of the Financial Profile) while the
`Download Worksheets` will save all tables displayed
on the **Worksheets** page as a single Excel workbook.

Similarly, all parameters used to generate the *case* are collected in *toml* format and displayed.
The `Download Case parameter file` button allows you to save the parameters of the selected scenario
to a *case* file for future use.

With the *case* parameter file and the **Household Financial Profile** workbook,
the same *case* can be reproduced at a later time by uploading the *case* parameter file
through the widget on the Create Case page, and the *Household Financial Profile* workbook
through the uploader on either the Create Case or the Financial Profile page.
""")

# --- Stress Tests tab ---
with tab_sim:
    st.markdown("""
There are two different ways to run multiple scenarios and generate a histogram of results.
""")

    with st.expander(":material/history: Historical Range", expanded=True):
        st.markdown("""
This page is for backtesting your scenario over a selected range of past years,
and generate a histogram of results.
Users can run multiple simulations,
each starting at a different year within a range of historical years.
Each simulation assumes that the rates follow the same sequence that happened in the past,
starting from a selected year in the past, and then offset by one year, and so on.
The **Starting year** and **Ending year** on the page set the year range and thus the number of
runs: one run per year in that range by default.

*Advanced options* add the following:

- **Augmented sampling** – When on, each year in the range is run with every combination of *reverse*
  (forward or reversed sequence) and *roll* (0 to *N*−1 years), so the histogram aggregates many more
  runs (historical years $\\times 2N$, where $N$ is the number of years in the plan)
  and gives a broader view of outcomes. When off, only the default sequence
  (no reverse, no roll) is used—one run per year.
  As the number of rate sequences can reach several thousands,
  **it is recommended to run this options
  only when self-hosting Owl** as it is likely to timeout on the
  Community Cloud server due to the long computing time.
- **Log scale (x-axis)** – When on, the result histogram uses log-spaced bins and a log-scale x-axis
  (log-normal style). Values below $1k are excluded from the histogram. Useful when the
  distribution is right-skewed.
- **Rate sequence** – When augmented sampling is off, **Reverse sequence** and **Roll (years)** can
  be applied to the rate sequence for each run
 (same behavior as on the **Rates Selection** page),
  giving one variant per year.

A histogram of results and a success rate is displayed at the end of the run.
$N$ is the number of runs (from the year range and, if used, augmented sampling),
$P$ the probability of success,
$\\bar{x}$ is the resulting average, and $M$ is the median.

If the `Beneficiary fractions` are not all equal to 1, two histograms will be displayed:
one for the partial bequest left at the passing of the first spouse
and the other for the distribution of values of the objective being optimized,
either maximum net spending or maximum bequest left at the passing
of the surviving spouse, depending on the objective function being optimized.
""")

    with st.expander(":material/finance: Monte Carlo"):
        st.markdown("""
This page runs a Monte Carlo simulation by generating many independent sequences of annual
rates of return and solving the full optimization for each one. At the end of the run a
histogram is displayed together with a probability of success.

The mean outcome $\\bar{x}$ and the median $M$ are provided in the graph, as are the number
of trials $N$ and the probability of success $P$, which is the fraction of trials for which
the optimizer found a feasible solution. Trials that failed are termed *infeasible* — the
optimizer could not simultaneously satisfy all constraints (spending floor, bequest target, etc.)
for that particular rate sequence.

##### Prerequisite: a stochastic rate method
Monte Carlo requires a rate method that generates a new random sequence for each trial.
The eligible methods (set on the **Rates Selection** page) are:
- `histogaussian` — multivariate normal draws with mean and covariance fitted on a historical window.
- `histolognormal` — log-normal draws with parameters fitted on a historical window; returns bounded below −100%.
- `gaussian` — multivariate normal draws using user-supplied mean, volatility, and correlation parameters.
- `lognormal` — log-normal draws using user-supplied arithmetic mean, volatility, and correlation parameters; returns bounded below −100%.
- `bootstrap_sor` — block-bootstrap resampling of the historical window (iid, block,
  circular, or stationary).
- `var` — VAR(1) simulation capturing year-to-year serial correlations fitted on the
  historical window.
- `garch_dcc` — DCC-GARCH(1,1) simulation with time-varying volatility and cross-asset
  correlations fitted on the historical window.

The `historical` method is deterministic (always the same sequence for a given starting
year) and therefore cannot be used for Monte Carlo; the **Run** button is disabled when it
is selected.

##### Choosing the number of trials
A few hundred trials is usually sufficient for a rough success-rate estimate. Increasing $N$
narrows the confidence interval on $P$ but increases run time proportionally. For final
analysis consider 500–1000 trials; for quick exploration 100–200 suffices.

##### Beneficiary fractions
If the `Beneficiary fractions` (set on the **Plan Setup / Account Balances** page) are not
all equal to 1, two histograms will be displayed: one for the partial bequest at the
passing of the first spouse, and one for the distribution of the primary objective
(maximum spending or maximum final bequest) at the passing of the surviving spouse.

##### Performance considerations
Each Monte Carlo trial requires solving a full LP or MIP, which is more expensive than
event-driven forward simulators. To improve throughput:
- Use `Medicare off` or the `self-consistent loop` option — the full MIP Medicare option
  adds binary variables to every trial and can be several times slower.
- Consider installing **Owl** locally — your own hardware may outperform the Community Cloud
  server, which also has a CPU-time quota that may terminate long sessions.
""")

# --- Tools & Help tab ---
with tab_tools:
    st.markdown("This section describes tools available to the user and summarizes the *Help* section.")
    with st.expander(":material/settings: Settings", expanded=True):
        st.markdown("""
This page allows you to select different backends for plotting the graphs.
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

The **Header** section lets you choose whether the case selector bar stays sticky (fixed at the top when
scrolling) or scrolls with the page (static).

###### Full Screen
If you are accessing **Owl** remotely on the Streamlit Community Cloud server through the Chrome browser,
the Chrome performance manager might disable hidden or inactive tabs.
This could cause your **Owl** session to inadvertently reset when idling for too long,
and losing the state of the calculator.
The best way to avoid this situation is to run the web page through the Streamlit app on your device.
This is done by clicking the '+" icon shown at the right end of the browser URL bar,
showing *App available: Install Streamlit*.
The app provides more screen space as it doesn't have a navigation bar.
On a mobile device, saving the page to the home screen will achieve the same result.
A similar timing problem can happen if your simulations
(Monte Carlo) are extremely long.
The Streamlit Community Cloud has a hard resource limit
on CPU time that might stop your calculations before completion.
I could successfully run 1,000 simulations using the Streamlit app while
being hosted on the Streamlit Community Cloud.
However, if you are contemplating running Monte Carlo simulations
with thousands of *cases* routinely,
you should definitely consider installing and running **Owl**
locally on your computer, either natively or through a container.
See instructions on the GitHub repository for how to proceed.

If not using the Streamlit app, going full screen while in the Chrome browser
can also greatly improve the visualization of graphs and worksheets
(achieved by pressing F11 on Windows, or Ctl+Cmd+F on MacOS).

###### App Theme
**Owl**'s default theme is the *Dark* mode but a *Light* theme is also available by
clicking on the three vertical dots located on the upper right of the app
and selecting the **Settings** option.
""")

    with st.expander(":material/error: Logs"):
        st.markdown("""
Messages coming from the underlying **Owl** calculation engine are displayed on this page.
This page is mainly used for debugging purposes.
""")

    with st.expander(":material/campaign: Help pages"):
        st.markdown("""
**Welcome** — The landing page of the application. It shows new users how to quickly get started by using an example *case* file.

**Documentation** — These very pages.

**Parameters Reference** — Displays reference tables for parameter settings. Useful for understanding keys in case configuration files (TOML).

**About Owl** — Credits and disclaimers.
""")

# --- Tips tab ---
with tab_tips:
    st.markdown("Here are a few tips that can help while using **Owl**.")
    with st.expander(":material/lightbulb_2: Recommendations on Optimization and Roth Conversions", expanded=True):
        st.markdown("""
**Owl** can optimize explicitly for Medicare costs but these can sometimes be
costly computations. This approach is included in the current version but
be aware that computing time can be unpredictable
due to the additional complexity and the number of binary variables involved.
As a second option, a self-consistent loop is provided by default which consists in adding
Medicare costs after the optimization step, and then iterate to convergence.
In this case, the suggested Roth conversions can sometimes lead to
smaller net spending or bequest than when no Roth conversions are made.
This is due to higher Medicare costs triggered by the increased MAGI
resulting from Roth conversions
which are factored in during the optimization step.

Whenever possible, one should **always** run comparisons between *cases*
with and without Roth conversions. These comparisons will help quantify
the effects of the suggested conversions. Remember that optimizers
will give the "best" approach even if it means only generating one more dollar.

While considering Roth conversions,
always keep in mind that all projections rely on our current best assumptions.
To account for the effects of potential changes in future income tax rates,
one can use a termination year for current tax rates to revert to higher rates.
""")

    with st.expander(":material/rule_settings: Typical Workflow"):
        st.markdown("""
A typical workflow would look like the following:

1) Create a base *case* representing your basic scenario;
2) Copy the base *case* and modify the parameter you want to investigate;
3) Repeat 2) with other end-member values of the parameter you would like to consider;
4) Run all *cases* and compare them on the **Reports** page.

To make it more concrete, here is an example
where one would like to investigate the effects of Roth conversions
on total net spending.
1) Create a *case* called, say, *2026 - Base case*.
Fill in all parameters representing your goals and situation.
Upload file or fill-in values for Wages and Contributions.
Let's say this *case* allows for Roth conversions up to \\$100k.
2) Copy the base case, call it *2026 - No Roth conversions* and
set maximum Roth conversions to 0.
3) Copy the base *case* again, call it *2026 - No Roth limit* and
set maximum Roth conversions to a very large number, say, \\$800k.
4) Compare all *cases* on the **Reports** page.

As mentioned above, the most actionable information is located on the first few lines
of the **Sources** tables on the Worksheets page.
This is where withdrawals and conversions are displayed for this year and the next few years.
""")

    with st.expander(":material/mindfulness: Scope of Use"):
        st.markdown("""
In general, computer modeling is not about predicting the future,
but rather about exploring possibilities.
**Owl** has been designed to allow users to explore multiple parameters
and their effects on their future financial situation while avoiding the trap of overmodeling.
Overmodeling happens when a computer model has a level of detail
far beyond the uncertainty of the problem, which can lead some users to assume
an unjustified level of certainty in the results.

The main goal of retirement financial planning is to characterize
uncertainty and translate this uncertainty into actionable, near-term decisions.
Therefore, as a deliberate choice in design, state tax and complex federal tax rules were
not included into **Owl**. As can be seen from this
[graph](https://marottaonmoney.com/wp-content/uploads/2023/04/Historical-Effective-Rates-Through-2023.jpg),
income tax rates have varied a lot over the last century. Assuming that current rates will
stay the same for the next 30 years is just unrealistic. But the best assumption
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
