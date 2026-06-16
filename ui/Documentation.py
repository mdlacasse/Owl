"""
Documentation page for Owl retirement planner Streamlit UI.

This module provides the interface for viewing application documentation,
user guides, and help information.

Copyright (C) 2025-2026 The Owl Authors

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
import owlbridge as owb

kz.initGlobalKey("docExpandAll", False)

col1, col2 = st.columns([2.8, 1], gap="large", vertical_alignment="top")
with col1:
    st.markdown("# :material/help: Documentation")
    st.markdown("### **Owl** - *Optimal wealth lab*")
    kz.divider("orange")
    st.markdown(f"**Version {owb.version()}**")
    st.markdown("<div style='height: 3.5em;'></div>", unsafe_allow_html=True)
    sub_toc, sub_toggle = st.columns([5, 1], vertical_alignment="bottom")
    with sub_toc:
        st.markdown("## :orange[Table of Contents]")
        _help = "Expand all sections across all tabs. Tip: expand before using Ctrl+F (or ⌘F) to search within the active tab."
    with sub_toggle:
        expand_all = st.toggle("Expand all", key="docExpandAll", help=_help)
with col2:
    logofile = kz.LOGOFILE
    st.image(logofile)
    st.caption("Retirement planner with great wisdom")

st.markdown("<style>div[data-testid='stTabs'] { margin-top: -50px; }</style>", unsafe_allow_html=True)

# Tabs for bite-sized navigation
tab_overview, tab_plan, tab_results, tab_sim, tab_tools, tab_help, tab_tips = st.tabs([
    "Overview",
    "Case Setup",
    "Results",
    "Stress Tests",
    "Tools",
    "Help",
    "Tips",
])

# --- Overview tab ---
with tab_overview:
    st.markdown("""
#### Getting Started with Owl
The menu at the top allows you to navigate through the different pages of the application.
Typically, pages under the *Case Setup* tab would be accessed successively in order,
starting from the top down. Once completed, the user would move to the second tab, *Results*,
to visualize the results.

A `Case selector` box located at the top of each page allows you
to navigate between the different cases created.
This box is present on all pages in **Case Setup** and **Results** sections.
The *case* being currently displayed is marked with a small red triangle 🔻.

A typical workflow for exploring different cases involves starting with a base
case and then copying + creating derived cases with slight changes in the parameters.
A comparison between the different resulting outcomes can be found on the **Reports** page.
The **Typical Workflow** section (Tips tab) goes through a specific example.

**Owl** uses a full year as the standard unit of time. Most values are therefore entered and
reported as yearly values. These include wages, income, rates, etc. To better align
with numbers from the Social Security Administration, Social Security
and pensions are entered as monthly values.
Dollar values are typically entered in thousands, unless in tables, where they
are entered and reported in unit dollars.
Graphs report values in thousands, either in nominal value or in today's \\$, as selected.

Looking at the top of the window, there are five sections in the menu bar:
**Case Setup**, **Results**, **Stress Tests**, **Tools**, and **Help**.
The documentation is structured along the same menus.

For better describing the flow of information, we provide here a few definitions of the terms used.
""")

    with st.expander(":orange[**Definitions**]", expanded=True, type="compact"):
        st.markdown("""
**Case**
> A *case* is a complete planning configuration that fully specifies an optimization problem.
It contains the individual's demographics, state of residence, savings account balances, asset allocation ratios,
fixed income sources (Social Security, pensions), spending goals, Roth conversion strategy,
solver options, and structural tax-law assumptions (brackets, Medicare rules, etc.).
It also includes the rate method and its parameters; for deterministic methods (constant presets or
`historical` replay), the actual rate values are part of the *case*.
Scalar parameters are stored in a `Case_<name>.toml` file.
Year-by-year time-series data (wages, contributions, Roth conversions, big-ticket items,
debts, and fixed assets) are held in an optional ancillary *Household Financial Profile*
(`HFP_<name>.xlsx`) workbook. Together, these two files fully reproduce a *case*.

**Household Financial Profile**
> A *Household Financial Profile* (HFP) is an
optional Excel workbook with one **Wages and Contributions** sheet per person
and optional household sheets *Debts* and *Fixed Assets*. Time-series fields include wages, *other inc*, *net inv*,
tax-deferred and Roth contributions (*ctrb* columns), *HSA ctrb*, *Roth conv*, and *big-ticket items*.
When no HFP is provided, wages and contributions are assumed to be zero.
See *Input and Output Files* below and *Case Setup* -> *Financial Profile* below for more detail.

**Scenario**
> A *scenario* is a specific realization of future economic conditions — primarily a year-by-year
sequence of asset-class return rates. For stochastic rate methods (`historical_gaussian`, `lognormal`,
`historical_bootstrap`, `vector_ar`, `garch_dcc`, `gmm`, etc.), each Monte Carlo trial draws a fresh *scenario*
from the model specified in the *case*. For the `historical` method, each starting year defines
one historical *scenario*. For constant rate methods, the *case* itself fully determines the
single implicit deterministic *scenario*. When stochastic lifespan is enabled in the Spending
Optimization analysis, a *scenario* also includes a random draw of individual lifespans.

**Run**
> A *run* is the execution of a *case* against one *scenario*, producing a complete set of
optimized results: spending plan, account trajectories, tax breakdown, etc.
For deterministic *cases*, a single *run* yields one result.
For stochastic *cases*, a Monte Carlo or Historical Range analysis runs the same *case* across
many *scenarios* and aggregates the results.
The Graphs and Worksheets pages show the output of the most recent single *run*,
while the *Stress Tests* tab groups methods running on an ensemble of scenarios.

The three concepts form a natural hierarchy: a ***case*** is configured and stored;
a ***scenario*** provides the economic realization; a ***run*** solves the optimization and produces results.

**Owl** helps the planner to create and run *cases*. By carefully selecting and modifying parameters,
the planner can explore the impacts of differing assumptions and strategies on their financial situation.
""")

    with st.expander(":orange[**Input and Output Files**]", expanded=expand_all, type="compact"):
        st.markdown("""
Every *case* in **Owl** is fully described by two input files and produces three output files.
Together they capture the complete data flow from configuration to results.
In the file names below, `<case_name>` stands for the *case* name and `<individual>` stands
for an individual's first name (e.g., *Jack* or *Jill*).

##### Input Files

**`Case_<case_name>.toml`** — *Case parameter file*

This human-readable text file encodes all the scalar parameters of a *case*:
individual demographics (names, birth dates, life expectancies),
savings account balances, asset allocation ratios,
fixed income sources (Social Security, pensions, SPIAs),
run options (objective, Roth conversion strategy, solver options),
the rates selection, and the filename of the associated *HFP* workbook (if any).
It does **not** contain the time-series data from the *Household Financial Profile* itself.

In practice, **users do not need to write or edit this file by hand** — the interface
generates it automatically as parameters are entered across the **Case Setup** pages.
Many ready-to-use example cases can be loaded directly from the **Create Case** page,
making it easy to get started without any manual file preparation.
Once a *case* has run successfully, its case file can be downloaded from the **Reports** page
and reloaded at any future session to restore the exact same configuration.
When uploaded on the **Create Case** page,
all fields in **Case Setup** are populated automatically.
The naming convention when saving from the interface is `Case_<case_name>.toml`.

**`HFP_<case_name>.xlsx`** — *Household Financial Profile workbook*

This Excel workbook holds year-by-year data that are not stored in the case TOML file.
It must contain **one sheet per individual**, with a tab name that **exactly** matches that person in the *case*
(e.g., *Jack* and *Jill*). Each person sheet is a **Wages and Contributions** table: **all** of the following
headers must be present (lowercase; column order may vary); enter `0` where a column does not apply:
`year`, `anticipated wages`, `other inc`, `net inv`, `taxable ctrb`, `401k ctrb`, `Roth 401k ctrb`, `IRA ctrb`,
`Roth IRA ctrb`, `HSA ctrb`, `Roth conv`, `big-ticket items`. The legacy header `other inc.` is read as `other inc`.
Numeric cells are **nominal dollars** (not thousands), independent of spending/bequest *units* in the case file.
On load, the planner keeps rows from five calendar years before the **current** year through each person's
last plan year (from demographics). Years outside that window are ignored; **every missing year inside the window,
including the last plan year, is added with zeros**—you need not type every year in Excel. **Any other column**
on a person sheet (including scratch/helper columns) is
**dropped** when the file is read and is not used in the model.

Two optional **worksheets** (separate tabs) extend the workbook:
- **`Debts`** — columns `active`, `name`, `type` (`loan` or `mortgage`), `year`, `term`, `amount`, `rate`.
- **`Fixed Assets`** — columns `active`, `name`, `type`, `year`, `basis`, `value`, `rate`, `yod`, `commission`
  (allowed `type` values are listed under *Financial Profile → Debts and Fixed Assets*).

A blank template is available
[here](https://github.com/mdlacasse/Owl/blob/main/examples/HFP_template.xlsx?raw=true).
The naming convention when saving from the interface is `HFP_<case_name>.xlsx`.
The case file stores the HFP filename internally; matching `<case_name>` names simply makes the pair easy to identify.

---

##### Output Files

After a *case* has been solved, the **Reports** page offers the following downloads:

**`Case_<case_name>.toml`** — *Saved case parameter file*

Identical in format to the input case file and fully round-trips: re-uploading it
recreates the exact same *case* configuration. If the HFP data were edited directly
in the UI (rather than loaded from a file), this file alone is not sufficient to
reproduce the run — the HFP workbook must also be saved.

**`HFP_<case_name>.xlsx`** — *Saved Household Financial Profile workbook*

The HFP workbook as currently loaded or edited in the session. Saving it alongside
`Case_<case_name>.toml` guarantees a fully reproducible *case*.

**`Synopsis_<case_name>.txt`** — *Case summary*

A plain-text table of key metrics (spending, bequest, taxes, etc.) for the solved *case*.
When multiple *cases* sharing the same individuals' names have been solved, additional columns
show the differences between cases for a quick side-by-side comparison.

**`Workbook_<case_name>.xlsx`** — *Plan workbook*

The primary numerical output of a solved *case*. Contains one worksheet per topic,
most indexed by year:
- **Income** — net spending, taxable ordinary income, taxable capital gains and dividends,
  total tax bills and Medicare premiums.
- **Cash Flow** — full breakdown of household inflows and outflows that balance to net spending.
- **HSA** — HSA-specific detail: Medicare, QME, total HSA withdrawals, the
  `HSA→Medicare` / `HSA→QME` split, and per-individual HSA balances/contributions/withdrawals.
- **`<individual>`'s Sources** *(one sheet per individual)* — year-by-year sources of spending
  (wages, other income, net inv, Social Security, pension, taxable/tax-deferred/tax-free/HSA withdrawals, RMDs,
  Roth conversions, big-ticket items).
- **Household Sources** — fixed-asset proceeds (ordinary income, capital gains, tax-free)
  and debt payments.
- **`<individual>`'s Accounts** *(one sheet per individual)* — balances, contributions,
  deposits, withdrawals, and Roth conversions for each of the four account types
  (taxable, tax-deferred, tax-free, HSA).
- **Taxes** — income allocated to each federal tax bracket, NIIT, LTCG tax,
  early-withdrawal penalty, state income tax (when applicable), and the fraction of Social Security that is taxable.
- **`<individual>`'s Allocations** *(one sheet per individual)* — asset allocation percentages
  (stocks, corporate bonds, T-notes, cash assets) for each account type over time.
- **Rates** — year-by-year return rates used in this run (stocks, bonds, T-notes, cash assets).
- **Summary** — aggregate totals over the planning horizon: spending, taxes, Medicare,
  Roth conversions, and bequests (not indexed by year).
""")

# --- Case Setup tab ---
with tab_plan:
    st.markdown("""
This section contains the steps for creating and configuring *cases*.
For new *cases*, every page of this section should be visited and parameters
entered according to your personal situation. To make this process easier,
a progress bar tracking which page has been visited is shown at the bottom of the page.
This bar can also be used to navigate between the pages of the *Case Setup* section.
The sections below describe the pages under the *Case Setup* tab and follow the same logical order.
""")

    with st.expander(":orange[**Create Case**]", expanded=True, type="compact"):
        st.markdown("""
The **Create Case** page is where every new case begins.
When no case is yet selected, the page shows three tabs for starting a case:
- **Load a Case Example** — pick a pre-built example from GitHub.
- **Create a New Case** — type a short name to start a blank case.
- **Upload Your Own Case File** — upload a TOML case file previously saved from Owl.

When a case is already selected, the same three-tab panel is tucked inside a
*"Create or load another case"* expander at the top of the page,
keeping the screen uncluttered while still allowing you to add or switch cases.
The page also allows you to copy, rename, and delete cases.

Once a case exists but no *Household Financial Profile* (HFP) has been loaded,
an **Upload Financial Profile** section appears directly on this page, so the case file
and the HFP workbook can both be loaded without leaving **Create Case**.
The HFP can alternatively be uploaded (or re-uploaded) at any time from the
**Financial Profile** page.

##### Load a Case Example
Select a pre-built example from the dropdown to load it directly from GitHub.
A representative example is available
[here](https://github.com/mdlacasse/Owl/blob/main/examples/Case_jack+jill.toml?raw=true),
and more can be found in the examples
[directory](https://github.com/mdlacasse/Owl/blob/main/examples/).
Loading an example populates all fields in the **Case Setup** section; most parameters
can be adjusted afterwards. If the example has an associated HFP, a
**Load example workbook** button appears so it can be loaded on the same page.

##### Create a New Case
Enter a name in the text box and press Enter, then fill in the marital status,
biological sex (`M`/`F`), birth date, and expected lifespan for each individual.
Cases start on Jan 1st of this year and end on December 31st of the year in which
the last individual passes according to the specified life expectancies.

You can also choose a state of residence to include state income taxes in the plan; leave it
blank to model federal taxes only. The no-income-tax states (AK, FL, NV, NH, SD, TN, TX, WA, WY)
are listed as well and produce zero state tax. State brackets, deductions, and any
retirement-income, pension, or Social Security exemptions are applied automatically based on the
state you choose; see the [*Modeling Capabilities*](https://github.com/mdlacasse/Owl/blob/main/info/modeling-capabilities.md)
reference for the details and limitations of
state-tax modeling.

Birth date is required because Social Security has special rules for people born on
the 1st or 2nd of the month; any other day of the month produces the same results.

For estimating longevity, several online calculators are available:
- [longevityillustrator](https://longevityillustrator.org)
- [livingto100](https://www.livingto100.com/calculator)


##### Upload Your Own Case File
Upload a *case* parameter file (`.toml` extension) previously saved from **Owl**.
These files are human-readable and contain all the scalar parameters of a *case*.
Loading one populates all fields in the **Case Setup** section, except for the
*Household Financial Profile* data, which is loaded separately (see next section).

##### Typical Workflow
A typical workflow involves creating a base *case* and copying it a few times,
each time changing one parameter to explore its effect.
Copying appends a number in parentheses to the case name (as on Windows);
it is good practice to then rename each copy to reflect what changed, and to
visit all **Case Setup** pages to confirm the parameters are as intended.
Once all *cases* have run, their results can be compared side-by-side on the **Reports** page.
Cases are considered related when they share the same individuals' names.
""")

    with st.expander(":orange[**Financial Profile**]", expanded=expand_all, type="compact"):
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

##### Wages and Contributions
Values in the *Wages and Contributions* tables are all in nominal values, and in \\$, not thousands (\\$k).
The **Wages and Contributions** table contains 12 columns titled as follows:

|year|anticipated wages|other inc|net inv|taxable ctrb|401k ctrb|Roth 401k ctrb|IRA ctrb|Roth IRA ctrb|HSA ctrb|Roth conv|big-ticket items|
|--|--|--|--|--|--|--|--|--|--|--|--|
|2021 | | | | | | | | | | |
| ... | | | | | | | | | | |
|2026 | | | | | | | | | | |
|2027 | | | | | | | | | | |
| ... | | | | | | | | | | |
|20XX | | | | | | | | | | |

All twelve columns **must be present** on each person's sheet; fill a column with 0 or leave it blank where it does not apply.
Any other column on that sheet is dropped on read (see *Input and Output Files*).
The *HSA ctrb* column holds HSA contributions in nominal dollars; they are pre-tax and reduce AGI. Values are automatically zeroed at Medicare enrollment (~age 65); entries past age 65 are ignored.
Note that column names are case sensitive and headers use lower case (the legacy header *other inc.* is read as *other inc*).
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

In the table above, year 20XX illustrates the last plan year for that person (from life expectancy in the *case*).
While loading a workbook, missing years or empty cells in the allowed window are filled with zeros; years outside
each person's plan span (plus the five-year lookback) are ignored.
After loading, each person's table always runs through that individual's final plan year—even if you omitted
those rows in the file.

The column *anticipated wages* is the annual amount
(gross minus tax-deferred contributions) that you anticipate to receive from employment.
This column is not meant to include all your ordinary income. For
example, interests from your taxable investment accounts
will be automatically calculated based on the assumptions you made for future return rates.

The *other inc* column is next in the table (after *anticipated wages*):
use it for other **ordinary** income that is not wages, pension, or Social Security—e.g. part-time or consulting income,
alimony, or rental flows you treat as ordinary. It is included in cash flow and ordinary-income tax logic like wages.

The *net inv* column follows *other inc*: use it for net investment income such as rent or trust distributions that the
model counts as ordinary income for cash flow and taxable income, and that also enter the Net Investment Income Tax
(NIIT, 3.8% surtax) when applicable. Use `0` if you do not model that income separately.

For the purpose of planning, there is no clear definition of retirement age. There will be a year,
however, from which you will stop having anticipated income, or diminished income due to decreasing your
work load. This transition can be gradual or sudden, and can be explored through these wages
and contributions tables. The only *hard* dates are the years when you intend to receive
a pension or collect Social Security, and these years are entered elsewhere on the
**Fixed Income** page.

Contributions to your savings accounts are marked as *ctrb*. We use 401k as a term that includes
contributions to 403b as well or any other tax-deferred account, with the exception
of IRA accounts which are treated separately to facilitate data entry.
Contributions to your 401k/403b **must** also include your employer's
contributions, if any. As these data can be entered in Excel,
one can use the native calculator to enter a percentage
of the anticipated wages for contributions to savings accounts as an easier way to enter the data.
For scratch space or Excel formulas, you can use **separate worksheets** or extra columns on a person sheet:
the reader **drops** every column on a person sheet whose header is not in the canonical list above
(blank and `Unnamed` columns are removed as well). Only columns with the headers described above
are loaded into the planner.

The column marked *Roth conv* lets you override **Owl**'s Roth conversion optimization on a
year-by-year, individual-by-individual basis, when the toggle `Use Roth conversion overrides
from Wages and Contributions tables` is enabled on the **Run Options** page. Each cell can take
one of three kinds of values:
- `0` (the default): let **Owl** optimize that year's conversion as usual, subject to the other
  Roth conversion settings on the **Run Options** page.
- A positive value: pin that year's conversion to exactly this amount (e.g., a conversion you've
  already made, or a value computed with another tool), bypassing the maximum annual conversion
  cap.
- A negative value: force *no* conversion that year. The magnitude is ignored, so you can flip
  the sign of a value you are considering without losing it -- handy for comparing an optimized
  run against "what if I skip this year?"

This column is provided for flexibility, e.g. to compare an optimized solution against your own
guesses or a previously executed conversion.

Finally, *big-ticket items* are used for accounting for the sale or purchase of a house, or any
other major expense or money that you would give or receive (e.g., inheritance, or large gifts
to or from you). Therefore, the sign (+/-) of entries in this column is important.
Positive numbers will be considered in the cash flow for that year and the surplus, if any, will be
deposited in the taxable savings accounts. Negative numbers will potentially generate additional
withdrawals and distributions from retirement accounts. Along with *Roth conv*, this is one of
the only two columns that can contain negative numbers: all other column entries must be positive.

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

##### Debts and Fixed Assets
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
- *basis* is the **cost basis** of the asset — the actual purchase price or adjusted tax basis in nominal dollars
  (what you paid, not inflation-adjusted to the reference year). For future acquisitions, enter the expected
  purchase price in the nominal dollars of the acquisition year. The basis is used to calculate capital gains
  or losses upon disposition.
- *value* is the **value in reference-year dollars**. This value represents the asset's worth
  at the beginning of the reference year, and it grows from the reference year to the disposition
  year using the specified growth rate.
- *rate* is the **annual growth rate** (percentage). The interpretation depends on the asset type:

  | Asset type | Rate interpretation | `rate = 0` means |
  |---|---|---|
  | *residence* | Real (above inflation) | Tracks inflation — maintains purchasing power |
  | *real estate* | Real (above inflation) | Tracks inflation — maintains purchasing power |
  | *collectibles* | Real (above inflation) | Tracks inflation — maintains purchasing power |
  | *precious metals* | Real (above inflation) | Tracks inflation — maintains purchasing power |
  | *stocks* | Nominal | Zero nominal growth (loses real value over time) |
  | *fixed annuity* | Nominal | Flat lump-sum payout — no growth |

  For physical assets, Shiller's long-run US data suggests real house price appreciation of roughly
  0–0.5\\%/year, so `rate = 0` is a reasonable starting point. A rate of `1` means the asset beats
  inflation by 1\\%/year. For stocks or annuities the rate is nominal and independent of inflation.
  (Shiller, *Irrational Exuberance*, 3rd ed., Princeton University Press, 2015;
  data at [shillerdata.com](http://www.shillerdata.com).)
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

    with st.expander(":orange[**Fixed Income**]", expanded=expand_all, type="compact"):
        st.markdown("""
This page is for entering data related to the individual's anticipated fixed income
from Social Security, pensions, and Single Premium Immediate Annuities (SPIAs).
Unlike other parts of the user interface, amounts on this page are
monthly amounts in today's \\$ and not in thousands.
The monthly amounts to be entered for Social Security are the Primary Insurance Amounts (PIA)
which are a critical part used by the Social Security Administration (SSA) for calculating benefits.
The PIA monthly amounts are always in today's \\$: this means that PIA numbers need to
be updated every year as they are modified by cost of living adjustments (COLA).

##### Inflation assumptions

All fixed income amounts are entered in today's dollars.
**Owl** scales them forward using the simulation's inflation rate as a single unified proxy
for all CPI-based cost-of-living adjustments. The table below summarizes how each item
is treated and where Owl's model diverges from the actual law:

| Item | Owl treatment | Real-world rule | Gap |
|---|---|---|---|
| Social Security benefits | Always inflation-adjusted | CPI-W COLA | Small: CPI-W ≈ CPI-U − 0.1–0.3%/yr |
| CSRS / military pensions (indexed) | Inflation-adjusted | Full CPI-W COLA | Small |
| FERS pension (indexed) | Inflation-adjusted | "Diet COLA": CPI-W−1pp (2–3%), cap 2% (>3%) | Meaningful in high-inflation years |
| Private/state pensions (not indexed) | Fixed | Fixed | None — use *Not indexed* toggle |
| Income tax brackets & standard deduction | Inflation-adjusted | Chained CPI-U (≈ CPI-U − 0.2–0.3%/yr) | Small |
| LTCG & capital gains thresholds | Inflation-adjusted | Chained CPI-U | Small |
| Medicare IRMAA thresholds | Inflation-adjusted | CPI-U | Negligible |
| ACA Federal Poverty Level thresholds | Inflation-adjusted | HHS annual update ≈ CPI-U | Negligible |
| SS taxability thresholds (\\$25k/\\$32k, \\$34k/\\$44k) | **Fixed** (not inflation-adjusted) | Fixed by law since 1984 | None — correctly modeled |

The most significant real-world deviation is for the Federal Employee Retirement System (FERS)
with the so-called **diet COLA**: when inflation is high
(e.g., 2022, CPI-W ~8.7%), FERS retirees received only 7.7% while **Owl** would apply the full
rate. FERS retirees planning under high-inflation scenarios may wish to model their pension
as *Not indexed* and enter a conservatively reduced monthly amount.

The frozen **Social Security taxability thresholds** deserve special mention: because they
have not been adjusted since 1984, nominal income growth due to inflation causes progressively
more of your Social Security benefits to become taxable over time — a "stealth tax" that
is correctly captured in **Owl**'s model.

Using a single inflation rate is a standard simplification in retirement planning.
The CPI-variant differences (0.1–0.3%/yr) are small relative to long-term inflation uncertainty
and tend to partially offset each other across different items.

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

By default, **Owl** uses the claiming ages you enter and does not change them.
However, on the **Run Options** page, under *Optimize SS claiming age*, you can select which
individuals should have their SS claiming month optimized (any month between age 62 and 70,
i.e., 97 monthly choices).
For a single individual the choices are `none` and the individual's name.
For couples the choices are `none`, each spouse's name, and `both` —
which is particularly useful when one spouse has already started collecting and only
the other's age should be optimized.
The optimizer will choose the claiming month that maximizes the plan objective (spending or bequest),
taking into account the interaction with taxes, Medicare, and Roth conversion strategy.
After solving, the optimal claiming ages are written back to this page for reference,
and the corresponding input fields are shown as read-only while that individual is being optimized.

**Already-claiming individuals:** if an individual's current age equals or exceeds the age entered
in the *claiming at age...* fields, **Owl** always treats that person's claiming age as fixed —
regardless of the optimize setting. For a couple where one spouse is already receiving benefits,
enter that spouse's *actual* claiming age here so the solver can recognize them as already claimed;
their age fields will remain editable as reference values, while the other spouse's age can still be optimized.
Selecting `none` always uses the entered ages as-is for all individuals.
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
For married couples, a joint-and-survivor option can be specified: enter the
percentage (0–100) that the surviving spouse will receive after your death.
Use 0 for a single-life annuity; common values for joint-and-survivor J+S are 50%, 75%, or 100%.
As for Social Security, the exact age in years and months, combined with your birth month,
determines the exact time benefits start in the first year and the total
annual amount for the first year is adjusted accordingly.

##### Single Premium Immediate Annuity (SPIA)

A SPIA converts a lump-sum payment into a guaranteed stream of lifetime income starting
immediately after purchase. **Owl** supports SPIAs funded through an IRA rollover, which is a
non-taxable transfer: the premium is deducted directly from the annuitant's tax-deferred account
in the year of purchase without triggering income tax. All subsequent payments are fully taxable
as ordinary income, and they count toward MAGI — affecting Medicare IRMAA surcharges and
Social Security taxability.

The table on this page accepts one row per SPIA. The columns are:

- **Annuitant** — the individual whose tax-deferred account funds the premium and whose life
  determines the payment duration.
- **Buy year** — the calendar year of purchase. For an already-purchased SPIA, enter the original
  purchase year: the premium is ignored (the account deduction already happened), and income
  begins at year 0 of the plan. For a future purchase, the premium is deducted from the
  tax-deferred balance in that year.
- **Premium (\\$k)** — lump-sum cost in thousands of nominal dollars. Ignored for past purchases.
- **Monthly (\\$)** — monthly benefit in nominal dollars at the time of purchase.
- **CPI-linked** — check if payments are inflation-adjusted (rare); leave unchecked for the
  more common fixed nominal payment.
- **Survivor (%)** — for couples, the fraction of the benefit that continues to the surviving
  spouse after the annuitant's death. Use 0 for a single-life annuity; common values are 50%,
  75%, or 100%.

**Owl** assumes the full annual payment is received in the buy year (12 monthly payments).
Multiple SPIAs are supported; add one row per contract.
""")

    with st.expander(":orange[**Account Balances**]", expanded=expand_all, type="compact"):
        st.markdown("""
This page allows you to enter account balances in all savings accounts.
Notice that all amounts are entered in units of \\$1,000, referred to as (\\$k).

Four types of savings accounts are considered and are tracked separately for spouses:
- Taxable savings accounts (e.g., investment accounts, CDs),
- Tax-deferred savings accounts (e.g., 401k, 403b, IRA),
- Tax-free savings accounts (e.g., Roth 401k, Roth IRA),
- Health Savings Accounts (HSA) — triple tax-advantaged: contributions are pre-tax, growth is tax-free, and qualified medical withdrawals (including Medicare Parts B/D and Medigap premiums) are tax-free.

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
The HSA beneficiary fraction defaults to 1.0: a surviving spouse inherits an HSA intact,
preserving its full triple tax-advantaged status (IRS rules). Non-spouse heirs must include
the full inherited HSA balance as ordinary income.
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

#### Taxable Account Cost Basis (optional)

The optional **cost basis** fields improve capital gains accuracy for the taxable account.
By default (when left at 0), Owl approximates capital gains on withdrawals using only the
current year's price appreciation — which significantly underestimates gains for accounts
with substantial embedded appreciation. When you supply a basis, Owl instead uses the
**average-cost method**: each dollar withdrawn from the taxable account is treated as
realizing a gain equal to the *unrealized-gain fraction* of the account,
where gain fraction = (current balance − cost basis) / current balance.
The gain fraction evolves each year as the SC loop tracks how basis changes
(withdrawals reduce it proportionally; new contributions restore it at full value).

The cost basis to enter is the total **adjusted cost basis** of the taxable account as
reported by your brokerage — the sum of what you paid for all lots currently held,
adjusted for reinvested dividends and return-of-capital distributions.
All amounts are in \\$k.
Leave the field at **0** if your basis is unknown — Owl treats zero (or blank) as *no basis
supplied* and uses the legacy approximation. Enter a **positive** value to enable average-cost
tracking. (In TOML or the Python API, an all-zero list or `setCostBasis([0])` follows the same
rules: all zeros in a case file means legacy mode; `setCostBasis([0])` in code explicitly models
100% embedded gain.)
A higher gain fraction means more capital gains tax per dollar withdrawn from the taxable account,
increasing total tax drag and reducing the maximum achievable spending or bequest.
""")

    with st.expander(":orange[**Asset Allocation**]", expanded=expand_all, type="compact"):
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
of individual savings account is associated with its own asset allocation ratios,
including a separate allocation for the HSA account (defaults to the same as tax-free if not set).
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
programming solver.

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

    with st.expander(":orange[**Rates**]", expanded=expand_all, type="compact"):
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
- `trailing_30` — constant rates equal to the 30-year trailing geometric mean of annual returns. A long-run backward-looking assumption.
- `conservative` — a pessimistic but plausible set of forecasts.
- `optimistic` — a more bullish set of forecasts.
- `historical_average` — geometric means computed over a selectable historical window
  (1928–present by default). Because averages can be negative when the window is narrow,
  the rate fields allow negative values in this mode.
- `user` — enter your own values for each asset class.

A roundup of expert stock and bond return forecasts can be found
[here](https://www.morningstar.com/markets/experts-forecast-stock-bond-returns-2026-edition).

> **Note:** Constant rates produce a single deterministic outcome and do not capture
> **sequence-of-returns risk** — the danger that poor returns early in retirement can
> permanently deplete a portfolio even if the long-run average is favorable. For a more
> realistic assessment of that risk, use one of the varying stochastic methods below.

---
##### Varying rates
Varying rates change year by year, enabling realistic uncertainty modeling.
There are nine methods:

**`historical`** — Replays the exact year-by-year returns from a selected historical window
in chronological order. Each year of the plan receives the return from one calendar year of
history; the plan horizon must fit within the selected window.
This is deterministic (no randomness) and is the right choice for backtesting: *"how would
this strategy have performed starting in 1970?"*

**`historical_gaussian`** — Computes the **arithmetic** mean returns, volatilities, and cross-asset covariance
from the selected historical window, then draws samples from the **fitted multivariate
normal distribution**. Each year of the plan is an independent draw from that distribution.
Unlike `historical_bootstrap`, no actual historical years are resampled — only their statistical
summary (arithmetic mean and covariance) is used. The result is parametric and Gaussian, but with
parameters grounded in history rather than supplied by the user.
*Inflation correction:* because historical inflation rates are right-skewed, a piecewise-linear
(PWL) transform is automatically applied to the inflation dimension before fitting to reduce this
skewness; its inverse is applied to generated samples so outputs remain in actual inflation units.
The transform slopes are auto-calibrated from the selected date window.

**`gaussian`** — Draws independently from a multivariate normal distribution each year.
The **arithmetic** mean returns, volatilities, and cross-asset correlations are **user-supplied** in the
*Stochastic Parameters* panel. Use this when you have a specific return/risk view that
differs from any historical period.

**`lognormal`** — Like `gaussian`, the **arithmetic** mean returns, volatilities, and cross-asset
correlations are **user-supplied**. However, samples are drawn from a **log-normal**
distribution: the arithmetic parameters are converted to log-space ($\\mu_Z$, $\\Sigma_Z$), a multivariate
normal is sampled in log-space, and returns are recovered as $R = \\exp(Z) - 1$. Advantages
over `gaussian`: returns are strictly bounded below by −100% (no total-loss artifacts),
the distribution is naturally right-skewed (large gains more probable than large losses),
and it is consistent with **Geometric Brownian Motion** — the foundation of most option
pricing theory.

**`historical_lognormal`** — Like `historical_gaussian` but fits a **log-normal** model to the
historical window. Log-returns $\\ln(1 + r)$ are computed from history; their **log-space** mean and
covariance are estimated directly, and samples are drawn from that fitted
distribution and exponentiated. The displayed statistics are the equivalent arithmetic means and
volatilities, converted back from log-space. Inherits all the right-skew and lower-bound advantages
of `lognormal` while deriving its parameters from history rather than user input.
*Inflation correction:* the PWL skewness normalization (see `historical_gaussian`) is applied
to inflation log-returns before the Gaussian fit in log-space, and its inverse is applied to
generated log-return samples before exponentiation.

**`historical_bootstrap`** *(Sequence-of-Returns bootstrap)* — Resamples **actual historical years**
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

The block size is adjustable (all three variants collapse to iid when block size is 1;
larger values preserve more serial structure).
For `block` and `circular` it is a fixed length; for `stationary` it is the *expected* length
of the geometrically distributed blocks. For annual return data, values of **3–5** are
well-supported: market cycles run 3–7 years, but annual autocorrelation decays quickly, so
larger values reduce sample diversity without meaningfully reducing bias.
`historical_bootstrap` is well-suited for Monte Carlo stress-testing when you want history-derived
randomness that respects multi-year market cycles.

**`vector_ar`** *(Vector Autoregression, order 1)* — Fits a VAR(1) model to the selected
historical window and then simulates new rate paths from that model. A VAR(1) captures
explicit year-to-year relationships across all four asset classes simultaneously: each
year's return depends linearly on last year's returns plus a multivariate normal shock.
This means momentum (positive serial correlation) and mean-reversion (negative serial
correlation) observed in the historical data are naturally reproduced. `vector_ar` is the most
statistically sophisticated method and is particularly appropriate when the sequence and
persistence of returns matter, as is often the case for sequence-of-returns risk analysis.
*Inflation correction:* the PWL skewness normalization (see `historical_gaussian`) is applied
to the inflation dimension before OLS fitting and inverted on generated samples.

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
*Inflation correction:* the PWL skewness normalization (see `historical_gaussian`) is applied
to the inflation dimension before GARCH/DCC fitting and inverted on generated samples.

**`gmm`** *(Gaussian Mixture Model)* — Fits a **K-component multivariate Gaussian mixture** to the
selected historical window using the Expectation-Maximization (EM) algorithm. Rather than
describing the joint return distribution as a single Gaussian, a GMM represents it as a
weighted sum of K full-covariance Gaussians, each corresponding to a distinct **market regime**
(e.g. bull market, bear market, crisis). Cross-asset correlations are captured *within each
regime*, so the model can represent, for instance, a crisis component where equities and bonds
fall together (correlation breakdown) alongside a bull-market component with the normal
negative stock–bond relationship. Each simulated year is drawn by first sampling a regime
from the mixture weights, then drawing from that regime's multivariate normal. Independent
draws — no serial autocorrelation. The number of components K is configurable (default 3).

**`hmm`** *(Hidden Markov Model)* — Extends the GMM by adding **temporal autocorrelation**
through a K×K Markov **transition matrix** between regimes, fitted via the Baum-Welch
algorithm (EM for HMMs). Each simulated year begins in a hidden regime state that persists
or switches according to the fitted transition probabilities, then draws returns from that
regime's multivariate Gaussian. Because regimes are Markov-correlated across years, the model
naturally reproduces **multi-year bull and bear runs** — a key driver of sequence-of-returns
risk. Fitted on annual US data, the diagonal transition probabilities typically exceed 0.6,
meaning a regime is more likely to continue than to switch in any given year. The number
of components K is configurable (default 3); `reg_trans` (default 0.001) applies Laplace
smoothing to prevent zero-probability transitions; `init_regime` pins the starting regime
(default: draw from the stationary distribution).

**`historical_copula`** *(Gaussian Copula)* — Fits a **4×4 Gaussian copula** to the selected
historical window and generates synthetic rate sequences from it. The algorithm maps each
asset's returns to a uniform distribution via a rank-based empirical CDF, fits the copula
correlation matrix in that normal space, samples from it, and maps back through the empirical
quantile function. Key property: each asset's **marginal distribution is preserved exactly** —
S&P 500 retains its left skew, T-Notes their right skew, inflation its right skew — unlike
`historical_gaussian` or `historical_lognormal` which impose a Gaussian (or log-normal) shape
on every marginal. Joint dependence is captured by the full 4×4 Pearson rank correlation
matrix. Generated values are bounded to the historical `[min, max]` of each asset class —
no extrapolation beyond observed data. The empirical quantile resolution equals the number
of years T in the selected window; a wider window gives finer resolution.
Inflation is floored at −5% to exclude Great Depression tail artefacts.

---
##### Method comparison

| Method | Rate type | Character | Pros | Cons |
|---|---|---|---|---|
| `trailing_30` | Constant | Deterministic | Backward-looking 30-year trailing geometric mean; no parameters | Single outcome; no uncertainty modeling |
| `conservative` | Constant | Deterministic | Simple; clearly stress-tests the downside | Single outcome; no uncertainty modeling |
| `optimistic` | Constant | Deterministic | Simple; tests bullish scenario | Single outcome; no uncertainty modeling |
| `historical_average` | Constant | Deterministic | Grounded in a specific historical period | Sensitive to choice of historical window |
| `user` | Constant | Deterministic | Full control over all return assumptions | Accuracy depends entirely on user inputs |
| `historical_bootstrap` | Varying | Stochastic | Preserves fat tails and extreme historical events | IID (independent and identically distributed) mode discards year-to-year serial structure |
| `garch_dcc` | Varying | Stochastic | Realistic volatility clustering and time-varying correlations | Higher per-trial cost; requires ≥ 15 years of history |
| `gaussian` | Varying | Stochastic | Full control over arithmetic means, volatilities, and correlations | Accuracy depends entirely on user inputs; unbounded downside |
| `historical_gaussian` | Varying | Stochastic | History-grounded statistics; no user parameters needed | Assumes normally distributed returns; draws are independent |
| `historical_lognormal` | Varying | Stochastic | History-grounded log-normal; bounded below −100%; right-skewed | Draws are independent; log-normal approximation |
| `historical` | Varying | Deterministic | Exact historical replay; no modeling assumptions | No Monte Carlo; one path per start year |
| `lognormal` | Varying | Stochastic | User-specified parameters; bounded below −100%; right-skewed; GBM-consistent | Accuracy depends entirely on user inputs |
| `vector_ar` | Varying | Stochastic | Captures momentum and mean-reversion across all asset classes | More complex; sensitive to choice of historical window |
| `historical_copula` | Varying | Stochastic | Preserves exact marginal distributions (no Gaussian shape imposed); captures full rank-correlation structure | Bounded to historical `[min, max]`; resolution limited to T years; no serial autocorrelation |
| `gmm` | Varying | Stochastic | Captures regime-dependent cross-asset correlations (bull/bear/crisis) | Independent draws; no serial autocorrelation |
| `hmm` | Varying | Stochastic | Regime-dependent correlations **plus** year-to-year persistence; best for sequence-of-returns risk | More parameters to fit; sensitive to choice of historical window and K |

---
##### Historical range
For all methods that reference history (`historical`, `historical_gaussian`, `historical_lognormal`,
`historical_bootstrap`, `historical_copula`, `historical_average`, `vector_ar`, `garch_dcc`, `gmm`, and `hmm`), a **Starting year / Ending year** selector appears.
The range determines which calendar years are included in the dataset from which rates
are drawn or statistics are computed. At least two years are required. For `historical`,
the ending year is fixed by the starting year plus the plan horizon.

---
##### Constrain mean
For history-fitted stochastic methods (`historical_gaussian`, `historical_lognormal`,
`historical_copula`, `garch_dcc`, `gmm`, `hmm`), a **Constrain mean** checkbox appears
next to the year-range selectors.

When checked, each generated rate series is post-processed so its arithmetic mean
exactly matches the historical arithmetic mean of the selected window. The correction
is a simple additive shift applied per asset column: the shape of the distribution
(variance, skew, volatility clustering, cross-asset correlations) is fully preserved
— only the mean is adjusted.

**When to use it:**
- When you want to isolate *sequence-of-returns risk* — the variability in outcomes
  caused by the *ordering* of good and bad years — while removing any noise in the
  *average* return of each synthetic scenario.
- When comparing methods: without this option, short plan horizons (30–40 years) can
  produce scenarios whose sample means drift noticeably above or below the historical
  window average, mixing sequence risk with mean estimation noise.

**When to leave it off:**
- When you specifically want the full distribution of possible mean outcomes, including
  scenarios where average returns happen to be lower or higher than the historical
  window suggests. This is the default behavior and is appropriate for most Monte
  Carlo analyses.

Note: bootstrap methods (`historical_bootstrap`) preserve the mean naturally because
they resample from the actual historical pool — this option has no effect there and
the checkbox does not appear.

---
##### Stochastic parameters
When `gaussian` or `lognormal` is selected, a panel with three sub-sections appears:
- **Arithmetic Means (%)** — expected annual (single-year) return for each asset class.
- **Volatility (%)** — standard deviation of annual returns for each asset class.
- **Correlation matrix** — Pearson correlations between every pair of asset classes.
  Values range from −1 (perfect inverse) to +1 (perfect co-movement); 0 means no
  linear relationship. The diagonal is always 1. The matrix must be positive semi-definite,
  i.e., you cannot set correlations to arbitrary values — the optimizer will warn if the
  matrix is invalid.

For the other varying methods, these fields are displayed but disabled; the statistical
parameters are derived automatically from the historical data.

---
##### Rate plots
Three graphs are displayed at the bottom of the Rates page (varying methods) or one graph
for constant methods.

**Selected Rates Over Time Horizon** shows the actual year-by-year rate sequence that will
be used in the current plan run. For stochastic methods this is one specific realization
drawn when you last changed a setting; re-running the case (or changing any parameter)
draws a fresh sequence. For constant and `historical` methods the sequence is always the same.

**Rate CDFs vs. Historical Range** (varying methods only) shows the empirical cumulative
distribution function (CDF) of each asset class's generated rates, one panel per asset class.
For historical methods (`historical_gaussian`, `historical_lognormal`, `historical_bootstrap`,
etc.), the CDF of the actual historical data from the selected frm–to window is overlaid as a
dashed gray line, making it easy to see how closely the fitted model reproduces the historical
sample. The same 2 000-sample representative draw used for the correlation graph is used here,
so the CDF reflects the model's true distribution rather than the short plan-horizon realization.

The CDF plot is useful in two complementary ways:

*Goodness-of-fit check.* For historical methods, the colored model CDF and the dashed
historical CDF should track closely. Divergence reveals where the fitted model departs from
history — e.g. a `gaussian` fit often underestimates the left tail of equity returns because
real-world return distributions are heavier-tailed than a normal distribution.

*Tail-probability reading.* The y-axis at any x-value gives the cumulative probability
directly, with no binning artifact. For example, if the S&P 500 CDF crosses 10% at −20%,
the model assigns a 1-in-10 chance of a loss worse than −20% in any given year. Practical
uses include: verifying that the inflation model is neither too tight nor too wide before
running Monte Carlo; checking whether `constrain_mean` realigned the model median with the
historical window; or comparing two historical windows to see how the distribution shifted
between, say, 1950–1980 and 1990–2020.

**Correlations Between Return Rates** (varying methods only) shows the statistical
properties of the selected rate model across all four asset classes: histograms on the
diagonal, scatter plots in the upper triangle, and kernel-density contours in the lower
triangle. To make this graph representative of the method's distributional properties
— rather than the noisy statistics of a single plan-horizon realization of 30–50 points —
the underlying data source varies by method:

| Method(s) | Data shown in the correlation and CDF graphs |
|---|---|
| `historical`, constant presets | The actual plan-horizon sequence (deterministic — no need for a larger sample) |
| `historical_bootstrap` | The **full historical pool** (frm–to window) that the bootstrap draws from — exact source distribution, no sampling noise |
| `historical_gaussian`, `historical_lognormal` | 2 000 synthetic draws from the parametric distribution fitted to the selected historical window |
| `gaussian`, `lognormal` | 2 000 synthetic draws from the user-supplied arithmetic means, volatilities, and correlations |
| `historical_copula`, `vector_ar`, `garch_dcc`, `gmm`, `hmm` | 2 000 synthetic draws from the fitted model |

The sample count **N** shown in the graph title reflects the actual number of data points
plotted, so it will differ from the plan horizon for stochastic methods.

---
##### Which method enables Monte Carlo?
Monte Carlo simulations (see the **Stress Tests** page) require a **stochastic** method —
one that generates a fresh random sample for each simulation trial. The methods that
support Monte Carlo are: `historical_gaussian`, `historical_lognormal`, `gaussian`,
`lognormal`, `historical_bootstrap`, `historical_copula`, `vector_ar`, `garch_dcc`, `gmm`, and `hmm`.
The `historical` method is deterministic (it always produces the same sequence for a
given starting year) and therefore cannot be used for Monte Carlo.

---
##### Dividend rate and tax settings
An option to set the dividend rate for your stock portfolio is available under
*Advanced options*. This [reference](https://us500.com/tools/data/sp500-dividend-yield)
provides historical S&P 500 dividend yields over different periods.

Two tax-related settings are also accessible:
- **Heirs marginal tax rate** — the marginal rate your beneficiaries would pay on
  inherited tax-deferred and HSA balances. Used to compute the after-tax value of a bequest.
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
For the stochastic methods (`historical_gaussian`, `historical_lognormal`, `gaussian`, `lognormal`, `historical_bootstrap`, `historical_copula`, `vector_ar`, `garch_dcc`, `gmm`, `hmm`),
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
  *(Basis for the `vector_ar` method.)*
- Efron, B., & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap.*
  Chapman & Hall/CRC. *(Foundation for `historical_bootstrap` resampling methods.)*
- Hull, J. C. (2017). *Options, Futures, and Other Derivatives* (10th ed.). Pearson.
  *(Basis for the `lognormal` and `historical_lognormal` log-normal / GBM framework.)*
- Rabiner, L. R. (1989). *A tutorial on hidden Markov models and selected applications in
  speech recognition.* Proceedings of the IEEE, 77(2), 257–286.
  *(Foundational reference for the `hmm` method and Baum-Welch algorithm.)*
- Sklar, A. (1959). *Fonctions de répartition à n dimensions et leurs marges.*
  Publications de l'Institut de Statistique de l'Université de Paris, 8, 229–231.
  *(Original paper introducing copulas; theoretical foundation for the `historical_copula` method.)*
""")

    with st.expander(":orange[**Goals**]", expanded=expand_all, type="compact"):
        st.markdown("""
The **Goals** page is where you define the optimization objective and spending preferences.

##### Objective
Choose which quantity to maximize. Two objectives are available:
- **Net spending** — maximize net spending subject to a desired bequest constraint. Enter the
  **Desired bequest from savings accounts** in today's \\$k. Fixed assets liquidated at the end of
  the plan are added to bequest separately; the page shows their contribution when applicable.
- **Bequest** — maximize after-tax bequest subject to a desired annual net spending constraint.
  Enter the **Desired annual net spending** in today's \\$k.

All objective and constraint values are in today's dollars (thousands).

##### Safety Net
You can enforce a **minimum taxable balance** (today's \\$k) for each spouse from year 2 through
life expectancy. The amount is inflation-adjusted over the plan. This should ideally be smaller
than each spouse's initial taxable balance; the page shows a warning if the minimum exceeds 60%
of initial taxable balance or if it is larger than the desired bequest when maximizing spending.

##### Spending Profile
The **type of profile** can be *flat* (constant real spending over time) or *smile* (adjusted for
lifestyle: a dip in the “slow-go” years, then an increase or decrease over the plan). For *smile*,
you can set the **smile delay** (years before the dip starts), **smile dip** (%), and **smile increase** (%).
**Profile slack** controls how far spending can deviate from the profile shape. Spending stays
within ±slack% of the profile (bilateral bound); set to 0 to pin spending exactly to the profile.
**Time preference** (0–10 %/year) applies an exponentially decaying weight to future spending
in the objective function — it does *not* force spending itself to decrease over time.
Instead, the optimizer assigns progressively less importance to spending in later years,
which shifts the optimal solution toward higher spending earlier in the plan and reduces
end-of-life back-loading. The actual spending trajectory remains free to take any shape
allowed by the profile and slack settings. Applies to *Net spending*; has no effect on *Bequest*.
For married couples, **Survivor's spending (%)** sets the spending level for the surviving spouse
(typically 60%). A preview of the selected profile is shown on the page.

These settings determine the *basis* for net spending or the constraint level; they work together
with the options on the **Run Options** page (Roth conversions, Medicare, solver, etc.).
""")

    with st.expander(":orange[**Run Options**]", expanded=expand_all, type="compact"):
        st.markdown("""
This page configures Roth conversions, health insurance costs, the self-consistent loop, and solver options.
The **objective**, **safety net**, and **spending profile** are set on the **Goals** page.

The maximum amount for Roth conversions and which spouse can execute them is configurable.
Roth conversions are optimized for reducing taxes and maximizing the selected objective function.
A year from which Roth conversions can begin to be considered can also be selected:
no Roth conversions will be allowed before the year specified.

Turning on the `Use Roth conversion overrides from Wages and Contributions tables` toggle lets
the *Roth conv* column on the **Wages and Contributions** page pin or block conversions for
individual years -- see the description of that column on the **Wages and Contributions** page
for the full semantics. Years left at `0` continue to be optimized subject to the cap, start
year, and exclusion settings above, while a pinned (positive) year bypasses the cap, even if
it exceeds the **Maximum annual Roth conversion** set above.

For married couples, the **Swap Roth converters mid-plan** toggle lets one spouse perform Roth
conversions up to a given year, after which the other spouse takes over for the remainder of the
plan. This is useful when, e.g., one spouse retires (and thus has a lower tax bracket) before the
other. This setting overrides the **Exclude Roth conversions for...** selection above.

The **Health Insurance** section groups three related subsections:

**Other Qualified Medical Expenses** sets annual non-Medicare qualified medical expenses
(dental, vision, co-pays, deductibles, etc.) in today's dollars.
IRS rules allow HSA withdrawals only up to total qualified medical expenses (QMEs).
This field, combined with Medicare costs, caps tax-free HSA withdrawals each year.
If zero, HSA withdrawals are limited to Medicare costs only.
Field is ignored if plan has no HSA.
Note: these expenses are treated as part of general living costs in the cash flow — they do not
appear separately in the *Healthcare* slice of the spending pie chart, which covers insurance
premiums only.

**ACA Marketplace (Pre-65)** allows entering the annual benchmark Silver plan (SLCSP) premium
for years before Medicare. Set to 0 to omit ACA costs.
For couples, enter the **combined household premium** (both spouses on the same marketplace plan).
When the older spouse transitions to Medicare, the tool automatically scales the SLCSP down to the
remaining spouse's individual plan using the CMS age rating curve (45 CFR 147.102), so no manual
adjustment is needed. The scaling factor is approximately 37–48% of the couple's combined premium,
depending on the age gap between spouses.
The **ACA start year** field specifies the calendar year when ACA coverage begins (e.g. the year of
retirement). Years before that are treated as employer-covered and incur no ACA cost. Leave at 0 for
ACA to apply from the first year of the plan.
*Optimize ACA (expert)* in *Advanced options*
co-optimizes ACA bracket selection within the LP, enabling the optimizer to shift MAGI across ACA brackets
for improved plan objectives (can be slower; applies 2026 rules only); it only applies when SLCSP > 0.

**Medicare** has a toggle *Medicare and IRMAA calculations* (Part B and Part D).
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
IRMAA surcharges. Values default to zero.
*Include Part D premiums* is on by default; Part B and Part D IRMAA surcharges (same MAGI brackets) are then included.
Turn it off if you have other drug coverage (e.g. employer, VA).
*Part D base premium (\\$/month per person)* is optional (default 0 = IRMAA only);
use it to add a monthly base (e.g. national average ~\\$39–47).
A warning appears if Medicare is on while the self-consistent loop is off,
since Medicare in loop mode requires the loop to compute premiums iteratively.

A **self-consistent loop** is an iterative method used for values that depend on the
solution itself and are therefore difficult to integrate directly into the linear program.
These include: the net investment income tax (NIIT, a 3.8% surtax on investment income
above $200k/$250k single/MFJ); the long-term capital gains rate (0%, 15%, or 20%,
determined by ordinary taxable income); the phase-out of the additional standard
deduction for seniors; the taxable fraction of Social Security benefits — which depends
on *provisional income* (PI), defined as adjusted gross income plus half of SS benefits
plus tax-exempt interest: 0% of SS is taxable below \\$25k PI (single) or \\$32k (MFJ),
up to 50% between those thresholds and \\$34k (single) / \\$44k (MFJ), and up to 85%
above the upper threshold — Medicare/IRMAA when Medicare is enabled, and ACA marketplace
premiums when ACA is enabled. The loop solves, recalculates these values from the solution,
re-solves, and repeats until convergence.
The *Self-consistent loop calculations* toggle in *Advanced options* turns this on or off;
turning it off defaults all these values to their worst-case upper bounds (e.g. 85% SS
taxability every year, maximum capital gains rate), which simplifies the model but
produces a more conservative (lower spending / lower bequest) estimate.

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
  phase out of senior exemptions, the taxable fraction of SS benefits, Medicare/IRMAA
  (when Medicare is enabled), and ACA premiums (when ACA is enabled).
- *Optimize Medicare (expert)* – integrates Medicare into the optimization; enabled only when
  Medicare and IRMAA calculations are on.
- *Optimize ACA (expert)* – co-optimizes ACA bracket selection within the LP, enabling the optimizer
  to shift MAGI across brackets for improved objectives (can be slower; applies 2026 rules only);
  enabled only when SLCSP > 0.

These two optimize modes operate on nearly disjoint time ranges — ACA covers pre-65 years,
Medicare covers 65+ years (with a 2-year MAGI lag) — and can be enabled independently or together
without conflict. Setting both simultaneously allows the LP to optimally balance the brief overlap
period where pre-Medicare MAGI also determines early IRMAA amounts.
*Guidance*: enable *Optimize ACA* for early retirees with long pre-65 periods where ACA costs dominate;
enable *Optimize Medicare* for high-income retirees where IRMAA surcharges are significant;
enable both when retiring in the early 60s with high income, so the LP can trade off ACA costs
against future IRMAA simultaneously.
- *Optimize LTCG brackets (expert)* – replaces the self-consistent loop for LTCG ordinary income
  stacking with an exact MILP formulation. Binary variables select the 0%/15%/20% bracket each year,
  so the optimizer simultaneously finds the best withdrawal strategy and bracket assignment.
  Can be slower due to additional binary variables; most useful for high-income plans where LTCG bracket
  placement significantly affects the objective.
- *Optimize NIIT (expert)* – replaces the self-consistent loop for NIIT with an exact MILP formulation.
  Binary variables determine whether MAGI exceeds the NIIT threshold (\\$200k single / \\$250k MFJ) each year.
  Most effective when *Optimize LTCG* is also enabled, since MAGI depends on ordinary income stacking.
- *Disallow same-year surplus deposits and withdrawals from taxable or tax-free accounts*
- *Disallow same-year Roth conversions and tax-free withdrawals*
- *Disallow cash-flow surpluses in the last two years of the plan*
- *Social Security taxability method* (loop, value, or optimize) and, when `value`, fixed SS tax fraction $\\Psi$.
- *MIP decomposition* (expert): when any of Optimize Medicare, Optimize ACA, Optimize LTCG, or Optimize NIIT is active, an alternative solve strategy can be selected. *Sequential* (relax-and-fix) fixes bracket binary variables one family at a time from an LP relaxation — fast but not globally optimal. *Benders* uses classical Benders decomposition to certify global optimality within the MIP gap via accumulated dual cuts — slower per iteration but convergence is typically reached in 1–3 iterations.
- *Solver* selection (default, HiGHS, or MOSEK if available), plus optional extra solver options.

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
Both solvers (HiGHS and MOSEK) provide very similar results.
In most cases, `MOSEK` will provide the best performance.
Selecting `HiGHS` will provide comparable results in a little more time.
Both solvers support all decomposition modes (sequential and Benders).
""")

# --- Results tab ---
with tab_results:
    st.markdown("Results from a case can be visualized in three different ways.")
    with st.expander(":orange[**Graphs**]", expanded=True, type="compact"):
        st.markdown("""
This page displays various plots from the most recent *run* of the active *case*,
using the rate *scenario* selected in the **Case Setup** section.
Each run applies one scenario — a single series of rates, either constant or varying —
as configured in the **Case Setup** section.
The outcome is optimized according to the chosen parameters: either maximize the
net spending, or maximize the bequest under the constraint of a net spending amount.
All plots can be displayed in today's \\$ or in nominal value using the radio buttons at the top.

A **Re-run** button re-executes the *case*, which generates a different result
if the chosen rate method is stochastic (`historical_gaussian`, `historical_lognormal`, `gaussian`,
`lognormal`, `historical_bootstrap`, `historical_copula`, `vector_ar`, `garch_dcc`, `gmm`, or `hmm`). Each graph can be seen
in full screen, and are interactive when using the `plotly` library.
Graphs can be drawn using the `matplotlib` or `plotly` libraries as
selected in the Settings section (Tools tab).

Graphs are organized into four tabs:

**Spending** — income and cash-flow perspective:
- *Lifetime Cash Flow* — pair of pie charts (in today's \\$): left shows where money comes from
  (portfolio, Social Security, pension, wages, SPIA, other); right shows where it goes
  (living expenses, federal taxes, state taxes when configured, healthcare, debt, bequest).
  *Taxes* is federal only (ordinary income, LTCG/dividends, NIIT); *State taxes* appears as a
  separate slice when a state of residence is configured.
  *Healthcare* covers insurance premiums only (Medicare Part B/D + IRMAA surcharges, ACA marketplace premiums);
  non-Medicare qualified medical expenses (QMEs) are embedded in the *living expenses* slice.
- *Annual Cash Flow Mix* — year-by-year normalized stacked-area charts showing how the composition
  of income sources and outflows evolves over the plan horizon. Colors match the pie charts,
  including a separate *State taxes* band when configured.
  Bequest is excluded as it is a lump-sum event rather than an annual flow.
- *Net Available Spending* — year-by-year spending trajectory.
- *Income, Big-Ticket Items, and Debts* — stacked breakdown of income sources (wages, Social Security, pension, withdrawals, etc.), big-ticket item cash flows, and debt payments.

**Taxes** — tax and health insurance costs:
- *Taxable Ordinary Income* — ordinary income, LTCG, and bracket allocation.
- *Taxes and Medicare (+IRMAA)* — federal (and state, when configured) tax bill, Medicare Part B/D premiums, IRMAA surcharges, and ACA premiums (when applicable).
- *HSA Activity* *(when HSA is present)* — annual HSA balance, contributions, and withdrawals by individual.

**Portfolio** — savings and asset-mix evolution:
- *Savings Balance* — per-account balances over time.
- *Savings Retention Margin* — how far the savings retention rate sits above or below the real break-even threshold each year.
  The retention rate is `1 − net draw / balance`; the real break-even is `(1 + inflation) / (1 + portfolio return) × 100%`.
  **Blue bars** (above zero) mean real wealth is growing; **red bars** (below zero) mean it is shrinking.
- *Asset Composition* — allocation-weighted asset mix across all accounts over time.
- *Balance Sheet* — assets (taxable, tax-deferred, tax-free, HSA, fixed assets) stacked above zero and
  liabilities (debt, deferred income tax, fixed-asset disposition costs) below, with the traditional and
  liquid net-worth lines overlaid. The graph companion to the **Balance Sheets** worksheets.

**Rates** — return and rate assumptions used for this run:
- *Selected Rates Over Time Horizon* — the rate sequence used for this run.
- *Rate CDFs vs. Historical Range* *(varying methods only)* — empirical CDF of each asset class's rate distribution; for historical methods, the historical window CDF is overlaid as a dashed line for comparison.
- *Correlations Between Return Rates* *(varying methods only)* — correlation matrix of asset returns.

""")

    with st.expander(":orange[**Worksheets**]", expanded=expand_all, type="compact"):
        st.markdown("""
This page shows the various worksheets containing annual transactions
and savings account balances in nominal \\$.
Savings balances are values at the beginning of the year, while other quantities
are for the full year.
Withdrawals are also assumed to occur at the beginning of the year,
so that the retiree has funds available to cover expenses throughout the year.
Each table can be downloaded separately in csv format, or all tables can be downloaded
jointly as a single Excel workbook by clicking on the `Download Worksheets` on the
**Reports** page.
Note that all values here (worksheets and workbook) are in \\$, not in thousands.

Worksheets are organized into five tabs:

**Accounts** *(shown first as most actionable)* — per-individual savings account detail:
- *`<individual>`'s Accounts* — balances, contributions, deposits, withdrawals, and Roth conversions
  for each of the four account types (taxable, tax-deferred, tax-free, HSA). Opening balance as of
  Jan 1st of that year. The current-year row is highlighted in blue.
- *HSA* *(when HSA is present)* — HSA diagnostics: `Medicare`, `QME`, `HSA total wdrwl`,
  `HSA→Medicare`, `HSA→QME`, and per-individual HSA balances, contributions, and withdrawals.
  Presented separately so the **Cash Flow** table remains a balancing identity.

**Balance Sheets** — consolidated wealth (savings accounts, fixed assets, and debts) at the
beginning of each year, plus a final end-of-plan (bequest) row:
- *Balance Sheet* — traditional accounting at gross market value: assets (taxable, tax-deferred,
  tax-free, HSA, and fixed assets), `total assets`, `debt`, and `net worth` (= total assets − debt).
- *Liquid Balance Sheet* — the same gross assets, but with future obligations shown as liabilities to
  estimate realizable wealth: `debt`, `deferred income tax` (tax-deferred + HSA balances times the
  *Liquidation tax rate* set on the **Rates** page), `disposition costs` (fixed-asset commission plus
  capital-gains tax at the *Liquidation cap-gains rate*, with the primary-residence exclusion applied),
  `total liabilities`, and `liquid net worth` (= total assets − total liabilities). Taxable savings are
  shown at face value (no per-year unrealized capital gains are modeled), and HSA balances are treated
  as ordinary-taxable at the liquidation rate (a conservative estimate).

**Cash Flow** — household cash flow:
- *Cash Flow* — full breakdown of inflows and outflows that balance to net spending.
- *`<individual>`'s Sources* — per-person year-by-year income sources (wages, Social Security, pension,
  account withdrawals, RMDs, Roth conversions, big-ticket items). The first row is highlighted in blue
  to mark actionable items for the current year.
- *Household Sources* — fixed-asset proceeds (ordinary income, capital gains, tax-free) and debt payments.

**Income & Taxes** — income summary and tax detail:
- *Income* — net spending, taxable ordinary income, taxable capital gains and dividends, total tax bills and Medicare.
- *Taxes* — income allocated to each federal tax bracket, NIIT, LTCG tax, early-withdrawal penalty,
  state income tax (when applicable), and the fraction of Social Security that is taxable.

**Allocations & Rates** — asset mix and return rates:
- *`<individual>`'s Allocations* — asset allocation percentages (stocks, corporate bonds, T-notes, cash assets)
  for each account type over time.
- *Rates* — the year-by-year return rates used in this run.

Use the toggles at the top of the page to control how worksheets are shown and saved:
- **Show ages**: adds a per-person age column (integer age on December 31 of each row's calendar year,
  blank after that person's plan horizon). Applies to both the on-screen tables and the saved Excel workbook.
- **Hide columns that are all zeros**: omits all-zero numeric columns from the on-screen tables only;
  the saved Excel workbook always retains all columns.
- **Show/save in real (today's) dollars**: divides all currency values by the cumulative inflation factor,
  converting nominal to today's dollars. Applies to both the on-screen tables and the saved Excel workbook;
  the saved filename gains a `_real` suffix.

These settings are saved in the case parameter file under `[results]` (see
**Help → Parameters Reference** for `worksheet_show_ages`, `worksheet_hide_zero_columns`,
and `worksheet_real_dollars`).
""")

    with st.expander(":orange[**Reports**]", expanded=expand_all, type="compact"):
        st.markdown("""
This page provides a summary of the most recent *run* and offers file downloads.

Key metrics are shown at the top: yearly spending (or spending target), liquid bequest
(or target), fixed-assets bequest (when applicable), partial bequest at the passing of the
first spouse (when `Beneficiary fractions` are not all 1 and the plan has two individuals),
and planning horizon — all in today's \\$.

The page is organized into two tabs:

**Synopsis** — comparison table summarizing income, spending, taxes, and bequest over the plan
duration, with all values shown in both nominal and today's \\$.
If multiple *cases* share the same individuals and year span, they are compared side-by-side:
the left column shows the selected *case* and the remaining columns show differences.
A **Rerun all cases** button re-executes all *cases* to ensure the comparison is up to date.
Tables are scrollable and can be viewed in full-screen mode.

**Case file** — displays the full TOML parameter file for the current *case*.

The **Downloads** section at the bottom of the page provides four buttons:
- **Case file** — TOML file with all parameters characterizing this *case*.
- **HFP workbook** — Excel workbook with the household financial input data.
- **Synopsis** — plain-text file with key metrics and the comparison table.
- **Plan workbook** — Excel workbook with all year-by-year result tables from the **Worksheets** page.

The *Case file* and *HFP workbook* together are sufficient to reproduce the *case* at a later
time: upload the case file on the **Create Case** page and the HFP workbook on either
the **Create Case** or **Financial Profile** page.
""")

# --- Stress Tests tab ---
with tab_sim:
    st.markdown("""
There are three pages for stress-testing your plan under different market scenarios.
""")

    with st.expander(":orange[**Historical Range**]", expanded=True, type="compact"):
        st.markdown("""
This page is for backtesting your *case* across a range of historical *scenarios*.
Users can run multiple simulations,
each starting at a different year within a range of historical years.
Each simulation applies one historical *scenario*: the year-by-year rate sequence that
actually occurred starting from a selected year in the past, then offset by one year, and so on.
The **Starting year** and **Ending year** on the page set the year range and thus the number of
runs: one run per year in that range by default.

*Advanced options* add the following:

- **Augmented sampling** – When on, each year in the range is run with every combination of *reverse*
  (forward or reversed sequence) and *roll* (0 to *N*−1 years), so the histogram aggregates many more
  runs (historical years $\\times 2N$, where $N$ is the number of years in the plan)
  and gives a broader view of outcomes. When off, only the default sequence
  (no reverse, no roll) is used—one run per year.
  As the number of rate sequences can reach several thousands,
  **it is recommended to run this option
  only when self-hosting Owl** as it is likely to timeout on the
  Community Cloud server due to the long computing time.
- **Log scale (x-axis)** – When on, the result histogram uses log-spaced bins and a log-scale x-axis
  (log-normal style). Values below $1k are excluded from the histogram. Useful when the
  distribution is right-skewed.
- **Rate sequence** – When augmented sampling is off, **Reverse sequence** and **Roll (years)** can
  be applied to the rate sequence for each run
 (same behavior as on the **Rates** page),
  giving one variant per year.

A histogram of results and a success rate is displayed at the end of the run.
$N$ is the number of runs (from the year range and, if used, augmented sampling),
$P$ the probability of success,
$\\bar{x}$ is the resulting average, and $M$ is the median.

When augmented sampling is **off**, a bar chart is also displayed showing the optimal
spending or bequest for each historical start year (in today's dollars). This gives a
compact view of which starting periods were most and least favorable.

If the `Beneficiary fractions` are not all equal to 1, two histograms will be displayed:
one for the partial bequest left at the passing of the first spouse
and the other for the distribution of values of the objective being optimized,
either maximum net spending or maximum bequest left at the passing
of the surviving spouse, depending on the objective function being optimized.
""")

    with st.expander(":orange[**Monte Carlo**]", expanded=expand_all, type="compact"):
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
The eligible methods (set on the **Rates** page) are:
- `historical_gaussian` — multivariate normal draws with arithmetic mean and covariance fitted on a historical window.
- `historical_lognormal` — log-normal draws with log-space parameters fitted on a historical window; reported statistics are arithmetic equivalents; returns bounded below −100%.
- `gaussian` — multivariate normal draws using user-supplied arithmetic mean, volatility, and correlation parameters.
- `lognormal` — log-normal draws using user-supplied arithmetic mean, volatility, and correlation parameters; returns bounded below −100%.
- `historical_bootstrap` — block-bootstrap resampling of the historical window (iid, block,
  circular, or stationary).
- `historical_copula` — Gaussian copula fitted to the historical window; preserves each
  asset's exact empirical marginal distribution while capturing joint rank correlations.
- `vector_ar` — VAR(1) simulation capturing year-to-year serial correlations fitted on the
  historical window.
- `garch_dcc` — DCC-GARCH(1,1) simulation with time-varying volatility and cross-asset
  correlations fitted on the historical window.
- `gmm` — Gaussian Mixture Model: a weighted mix of regime-specific multivariate Gaussians
  fitted on the historical window; draws are independent across years (no serial structure).
- `hmm` — Hidden Markov Model simulation with regime-dependent Gaussian emissions and a
  fitted Markov transition matrix; produces temporally correlated multi-year regime runs.

The `historical` method is deterministic (always the same sequence for a given starting
year) and therefore cannot be used for Monte Carlo; the **Run** button is disabled when it
is selected.

##### Choosing the number of trials
A few hundred trials is usually sufficient for a rough success-rate estimate. Increasing $N$
narrows the confidence interval on $P$ but increases run time proportionally. For final
analysis consider 500–1000 trials; for quick exploration 100–200 suffices.

##### Beneficiary fractions
If the `Beneficiary fractions` (set on the **Case Setup / Account Balances** page) are not
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

    with st.expander(":orange[**Spending Optimization**]", expanded=expand_all, type="compact"):
        st.markdown("""
This page finds a **committed first-year spending level** (in today's dollars) that is
robust across a set of historical or Monte Carlo scenarios. Unlike the histogram pages,
which show the distribution of *optimal* outcomes, this page answers a different question:

> *Given that I must commit to the same spending level today regardless of which market
> scenario actually unfolds, what is the highest amount I can commit while keeping the
> probability of falling short below a chosen threshold?*

##### How it works

For each scenario (historical start year or Monte Carlo draw), the optimizer solves the
full plan and records the optimal spending basis $g_s$. These $N_s$ per-scenario bases are then
passed to a **stochastic recourse linear program (LP)** that finds a common commitment $g^*$ maximizing

$$
\\max_{g,\\,\\sigma} \\ g - \\frac{\\lambda}{N_s}\\sum_s \\sigma_s
\\quad\\text{s.t.}\\quad \\sigma_s \\ge g - g_s,\\; \\sigma_s \\ge 0
$$

where $\\sigma_s$ is the shortfall in scenario $s$ and $\\lambda$ controls risk aversion.
The LP is swept over a range of $\\lambda$ values to trace the **efficient frontier**.

##### Controls

- **Scenario method** — *Historical range*: uses historical rate sequences over the
  selected year range (one run per year). *Monte Carlo*: uses the active stochastic rate
  method; requires a stochastic method to be set on the **Rates** page.
- **Stochastic lifespan** — available with Monte Carlo scenarios. When enabled, each
  scenario also draws lifespan(s) from the selected mortality table using each individual's
  sex (`M`/`F`) and current age; the scenario horizon becomes the last-survivor horizon.
  This captures joint market and lifespan uncertainty — roughly half of scenarios end
  before the median age (freeing assets earlier), and half after. Historical scenarios
  with stochastic lifespan are intentionally disabled.

  **Mortality tables** — eight actuarial tables are provided, covering different population
  sub-groups. Choose the one that best matches your situation:

  | Table | Population | When to use |
  |-------|-----------|-------------|
  Tables are ordered shortest to longest life expectancy at age 65 (average M+F).

  | Table | LE@65 | Population | When to use |
  |-------|-------|-----------|-------------|
  | `VBT2015-SM` | 82 | Smoking life insurance policyholders (SOA VBT 2015) | Smokers have meaningfully shorter life expectancy; use if you are a current or long-term smoker |
  | `SSA2025` *(default)* | 83 | Average US population (2025 SSA Period Life Table) | Good starting point for most people; reflects typical life expectancy across all income levels and health conditions |
  | `Pub2010-Safety` | 85 | Public safety retirees — police, firefighters, correctional officers (SOA Pub-2010) | Safety personnel tend to retire earlier with somewhat shorter post-retirement life expectancy than other public-sector groups |
  | `Pub2010-General` | 86 | General government employees — state/local public sector (SOA Pub-2010) | Use if you worked in a government role outside teaching or public safety |
  | `RP2014` | 86 | Private pension recipients (SOA RP-2014 Healthy Annuitant) | Pension recipients live longer on average; use if you have a private defined-benefit pension |
  | `VBT2015-NS` | 87 | Non-smoking life insurance policyholders (SOA VBT 2015) | Slightly longer-lived than the general population; a reasonable choice if you are in good health and have never smoked |
  | `IAM2012` | 87 | Individual annuity purchasers (SOA IAM 2012) | People who buy annuities tend to be in excellent health; represents an optimistic longevity scenario |
  | `Pub2010-Teacher` | 87 | Public school teachers and college professors (SOA Pub-2010) | Teachers have the longest life expectancy of all public-sector groups |

- **Lifespan reproducibility** — optional seed control for lifespan sampling. When set,
  identical lifespan draws are reproduced across runs; rate reproducibility remains controlled
  separately on the **Rates** page.
- **Target success rate** — the minimum fraction of scenarios that must meet the
  commitment with no shortfall. The page finds the least conservative $\\lambda$ that
  achieves this rate.
- **Advanced options** (historical only) — *Roll* and *Reverse sequence* apply the same
  rate-sequence transforms available on the **Historical Range** page, useful for
  exploring sensitivity to sequence order.

##### Spending Floors

The key output of this page is a **spending floor** — the highest spending level you can
commit to while keeping your probability of falling short below the chosen threshold.
Two variants are reported depending on the scenario method:

- **Historical spending floor (HSF)** — produced when using the *Historical range* method.
  It is the highest real spending level that survives every historical return sequence in the
  selected range, personalized to your specific plan. Think of it as the retirement equivalent
  of Bengen's four-percent rule, but calculated for your actual accounts, taxes, Social Security,
  and spending profile rather than a generic portfolio.

- **Synthetic spending floor (SSF)** — produced when using *Monte Carlo* scenarios.
  It is the highest real spending level that survives at least 95% of a set of synthetic
  return sequences generated by the selected rate model. Because the model can be calibrated
  to current return conditions rather than the historical_average, the SSF serves as a
  forward-looking stress test: if prospective returns are expected to be lower than the
  historical_average, the SSF will fall below the HSF, flagging the risk. When the two agree,
  it signals that the model anticipates conditions similar to the historical record.

##### Summary Line

A text summary above the charts reports the following metrics:

- **Committed spending** — the floor amount in today's dollars, at the chosen success rate.
- **Target / actual success rate** — the fraction of scenarios where spending meets the commitment.
  The actual rate may be slightly above the target due to how the frontier is sampled.
- **Median scenario spending** — the median outcome across all scenarios. This is typically
  well above the committed level, since most scenarios are better than the floor scenario.
- **Historical / Synthetic spending floor** — the conservative anchor of the frontier: the
  minimum spending across all historical scenarios (HSF), or the 5th-percentile spending
  across Monte Carlo scenarios (SSF). The percentage shown is how far this floor falls below
  the committed level — a measure of downside severity in the worst-case scenario.
- **Mean shortfall** — the average shortfall across *all* scenarios, including the many where
  there is no shortfall (shortfall = 0 in those cases). A small mean shortfall means that
  even averaging over failing scenarios dilutes the risk.
- **CVaR (avg loss | failure)** — the average shortfall *conditional on being in a failing
  scenario*. This is the mean shortfall divided by the fraction of failing scenarios, so it
  gives a clearer picture of how bad things are when they go wrong. A CVaR of \\$5,000/yr means
  that in the scenarios where you do fall short, the average gap is \\$5,000/yr — regardless
  of how many such scenarios there are.

##### Charts

Three charts are always displayed after a run:

- **Success rate curve** — committed spending vs. shortfall probability. The target point
  is marked; moving left increases spending but also increases shortfall risk.
- **Efficient frontier** — committed spending vs. expected shortfall magnitude (in today's
  dollars). This is a Pareto trade-off between spending ambition and downside risk, analogous
  to the Markowitz mean-variance frontier in portfolio theory. The spending floor anchors
  the conservative (zero-shortfall) end.
- **Outcome chart** — shows the achieved spending for each individual scenario.
  For *Historical range*: a bar chart by start year, colored green when the scenario meets
  the commitment and red when it falls short. For *Monte Carlo*: scenarios sorted by
  percentile (0–100%), using the same color scheme. The committed level $g^*$ is marked
  with a dashed horizontal line.

When **stochastic lifespan** is enabled (Monte Carlo only), two additional charts appear below:

- **Survival curves** — shows P(alive at age X) for each individual, conditional on their
  current age and the selected mortality table. For couples, a dashed joint curve shows
  P(at least one person alive), i.e. the last-survivor probability. These curves are
  derived analytically from the mortality table and do not depend on the scenario run —
  they provide context for interpreting the lifespan draws.
- **Drawn lifespans** — histogram of the ages at death sampled across all scenarios, one
  series per individual and one for the joint last-survivor horizon. The median age at death
  for each series is shown in a text box in the upper-left corner.

##### Retirement Efficiency Score (RES) — *experimental*

An optional **experimental** expander offers a Sharpe-ratio–style efficiency metric for
choosing the target success rate. It computes a **Retirement Efficiency Score**,
RES = (committed spending − floor) / CVaR, and finds the success rate that maximizes it —
the point where each extra dollar of committed spending is best compensated for the downside
risk it adds. A radio selects the **floor**: the historical spending floor (HSF) or a custom
value. Two extra charts appear: **CVaR vs. probability** and **RES vs. CVaR**, with the
optimal point marked. This feature is most meaningful in *Historical range* mode and is not
validated for production use; see the [*Modeling Capabilities*](https://github.com/mdlacasse/Owl/blob/main/info/modeling-capabilities.md)
reference for details.
""")

# --- Tools tab ---
with tab_tools:
    st.markdown("This section describes tools available to the user.")
    with st.expander(":orange[**Settings**]", expanded=True, type="compact"):
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
**Owl**’s default Streamlit look is set in the repository’s `.streamlit/config.toml` (for example
`base = "dark"`). To change light/dark or colors, adjust that configuration when you run the app
yourself, and follow Streamlit’s
[theming documentation](https://docs.streamlit.io/develop/concepts/configuration/theming).
""")

    with st.expander(":orange[**Logs**]", expanded=True, type="compact"):
        st.markdown("""
Messages coming from the underlying **Owl** calculation engine are displayed on this page.
This page is mainly used for debugging purposes.
""")

# --- Help tab ---
with tab_help:
    st.markdown("Help resources in the application menu.")
    with st.expander(":orange[**Welcome**]", expanded=True, type="compact"):
        st.markdown("""
The landing page of the application. It shows new users how to quickly get started by using an example *case* file.
""")
    with st.expander(":orange[**Documentation**]", expanded=True, type="compact"):
        st.markdown("""
These very pages. Full user guide and reference for all sections of the application.
""")
    with st.expander(":orange[**Parameters Reference**]", expanded=True, type="compact"):
        st.markdown("""
Displays reference tables for parameter settings. Useful for understanding keys in case configuration files (TOML).
""")
    with st.expander(":orange[**About Owl**]", expanded=True, type="compact"):
        st.markdown("""
Credits, changelog, and legal information.
""")

# --- Tips tab ---
with tab_tips:
    st.markdown("Here are a few tips that can help while using **Owl**.")
    with st.expander(":orange[**Recommendations on Optimization and Roth Conversions**]", expanded=True, type="compact"):
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

    with st.expander(":orange[**Typical Workflow**]", expanded=expand_all, type="compact"):
        st.markdown("""
A typical workflow involves creating a base *case* and copying it a few times,
each time changing one parameter to explore its effect:

1. Create a base *case* representing your baseline situation.
2. Copy the base *case* and modify the parameter you want to investigate.
3. Repeat step 2 for other values of that parameter, or for other parameters.
4. Run all *cases* and compare them on the **Reports** page.

Copying appends a number in parentheses to the case name; rename each copy to reflect
what changed, and revisit all **Case Setup** pages to confirm parameters are as intended.
Cases are considered related — and will be compared side-by-side on **Reports** —
when they share the same individuals' names.

Here is a concrete example investigating the effect of Roth conversions on net spending:

1. Create a *case* called *2026 - Base case*. Fill in all parameters for your situation,
   including wages and contributions. Set the maximum Roth conversion to \\$100k.
2. Copy the base *case*, rename it *2026 - No Roth conversions*, and set the maximum Roth conversion to \\$0.
3. Copy the base *case* again, rename it *2026 - No Roth limit*, and set the maximum Roth conversion to a
   large number such as \\$800k.
4. Run all three *cases* and compare results on the **Reports** page.

The most actionable information is on the first few lines of each individual's **Sources**
worksheet (Worksheets page → **Cash Flow** tab), where withdrawals and Roth
conversions for the current and upcoming years are listed.
""")

    with st.expander(":orange[**Scope of Use**]", expanded=expand_all, type="compact"):
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
Therefore, as a deliberate choice in design, complex federal tax rules were
not included into **Owl**. State income taxes can be enabled through the
*State of residence* field in **Case Setup**.
As can be seen from this
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

kz.divider("orange")
st.markdown("### :orange[Next steps]")
c1, c2, c3 = st.columns(3)
with c1:
    st.page_link("Create_Case.py", label="Create Case", icon=":material/person_add:")
with c2:
    st.page_link("Parameters_Reference.py", label="Parameters Reference", icon=":material/menu_book:")
with c3:
    st.page_link("About_Owl.py", label="About Owl", icon=":material/info:")
