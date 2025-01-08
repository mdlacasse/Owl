import streamlit as st


col1, col2, col3, col4 = st.columns(4)
with col4:
    st.image("http://raw.github.com/mdlacasse/owl/main/docs/images/owl.png")

st.write('## Owl Retirement Planner')
st.markdown('''
<div style="text-align: justify">

#### A retirement exploration tool based on linear programming

This tool is based on the Owl Python package aimed at providing a retirement modeling
framework for exploring the sensitivity of retirement financial decisions.
Strictly speaking, Owl is not a planning tool, but more an environment for exploring *what if* scenarios.
It provides different realizations of a financial strategy through the rigorous
mathematical optimization of relevant decision variables. Using a linear programming approach,
two major objective goals can be set: either
maximize the net spending amount, or maximize an after-tax bequest, each under various constraints.
Roth conversions are optimized to reduce the tax burden, while federal income tax and Medicare
premiums (including IRMAA) are calculated.
See the full description of the package on [github](https://github.com/mdlacasse/owl) for details.

--------------------------------------------------------------------------------------
### Getting started with the user interface
The functions of each tab are described below in the same order as they appear in the sidebar.
Typically, tabs would be accessed in order, starting from the top.
The `Select case` selection box at the bottom of the margin allows to select an existing case
or create a new one from scratch, or from a *case* file, which
would then populate all parameter values.
This box is present in all relevant tabs and allows to compare different scenarios.
However, two more choices are available when the [Basic Info](#basic-info) tab is selected.

-------------------------------------------------
### :orange[Case Setup]
This section contains the steps for creating and configuring case scenarios.

#### Basic Info
This tab controls the creation of scenarios as the `Select case` menu contains
two additional items: one to create a new case, and the other to create a case from a *case* file.
This tab also allows you to duplicate and/or rename a scenario, and to delete scenarios.

For creating a scenario, the (first) name(s), marital status, birth year(s),
and life expectancies are required. A starting date for the plan determines when the plan
starts in the first year. Plan still ends at the end of the year when all individuals
have passed according to the specified life expectancies.

When duplicating a scenario, all parameters will be copied, but each tab in
the `Case setup` section will need to be revisited in order
to refresh the case. This includes the wages and contributions file which will need to
be uploaded, if any was present.

##### Initializing the life parameters for the realization
Start with the `Select case` box and choose one of `New case...` or `Upload case file...`.

If `Upload case file...` is selected, a *case* file must be uploaded.
These files end with the *.toml* extension, are human readable (and therefore editable),
and contain all the parameters required to characterize a scenario.
An example is provided
[here](https://raw.github.com/mdlacasse/Owl/main/examples/case_jack+jill.toml) and more
can be found in this [directory](https://github.com/mdlacasse/Owl/blob/main/examples/).
Using a *case* file
will populate all the fields required to run a scenario. A *case* file for the case being developed
can be saved under the [Case Results](#case-results) tab and made available to reload at a later time.
Case files can have any name but when saving from the interface, their name will start with *case_*
followed by the case name.

When starting from `New case...`,
one must provide the year of birth of each spouse(s) and their expected lifespan(s).
For selecting your own numbers, there are plenty of longevity predictors on the web. Pick your favorite:
- [longevityillustrator](https://longevityillustrator.org),
- [livingto100](https://www.livingto100.com/calculator),

or just Google *life expectancy calculator*.

Finally, a starting date for the first year of the plan must be provided.
By default, it starts today, but any other date
in the current year can be chosen. This is useful if your numbers are known for a fixed date, or
for reproducibility purposes. This date does not affect when the plan ends, which is at the
end of the year when all individuals have passed according to the life parameters data provided.

#### Assets
This tab allows to enter account balances in all savings accounts.
Notice that all amounts are entered in units of \\$1,000, referred to as (\\$k).

Three types of saving accounts are considered and are tracked separately for spouses:
- Taxable saving accounts,
- Tax-deferred saving accounts,
- Tax-exempt saving accounts.


For married couples, the spousal `Beneficiary fractions` associated with these accounts
can be selected, as well as a surplus deposit fraction. The first one controls
how much is left to the surviving spouse while the second determines
how to split potential surplus budget moneys between the taxable accounts of the spouses.
When the `Beneficiary fractions` are not all 1, it is recommended to deposit all
surplus moneys in the taxable account of the first individual to pass. Otherwise,
the optimizer will find creative solutions that can generate surpluses in order
to maximize the final bequest.

#### Wages and Contributions
This tab allows to enter an optional Excel file containing future wages and contributions.
The values in this spreadsheet are in \\$, not in thousands.
This file must contains 9 columns titled as follows:

<span style="font-size: 10px;">
</span>

|year|anticipated wages|ctrb taxable|ctrb 401k|ctrb Roth 401k|ctrb IRA|ctrb Roth IRA|Roth X|big-ticket items|
|--|--|--|--|--|--|--|--|--|
|2025 | | | | | | | | |
|2026 | | | | | | | | |
| ... | | | | | | | | |
|20XX | | | | | | | | |


Here, 20XX is the last row which could be the last year based on the life expectancy values provided.
Missing years or empty cells will be filled with zero values, while years outside the
span of the plan will be ignored.
For the columns, *anticipated wages* is the annual amount
(gross minus tax-deferred contributions) that you anticipate to receive from employment or other sources
(not including dividends from your taxable investment accounts). Note that column names are case sensitive
and all entries must be in lower case. Best way to start this process is to use the template
file provided [here](https://raw.github.com/mdlacasse/Owl/main/examples/template.xlsx).

For the purpose of planning, there is no clear definition of retirement age. There will be a year,
however, from which you will stop having anticipated income, or diminished income due to decreasing your
work load. This transition can be gradual or sudden, and can be explored through this wages
and contributions file.

Contributions to your savings accounts are marked as *ctrb*. We use 401k as a term which includes
contributions to 403b as well or any other tax-deferred account, with the exception
of IRAs accounts which are treated separately. Contributions to your 401k/403b must
also include your employer's
contributions, if any. As this file is in Excel, one can use the native calculator to enter a percentage
of the anticipated wages for contributions as this can sometimes be easier. For this
purpose, additional columns (on the right) can be used for storing the anticipated total salary and
to derive relevant numbers from there. These columns will be ignored when the file is processed.

Roth conversion can be specified in the column marked *Roth X*.
This column is provided to override the Roth conversion optimization in Owl. When the option
`Convert as in contribution file` is toggled in the [Optimization Parameters](#optimization-parameters) tab,
values from the contributions file will be used and no optimization over Roth conversions
will be performed. This column is provided for flexibility and to allow comparisons
between an optimized solution and your best guesses.

Finally, *big-ticket items* are used for accounting for the sale or purchase of a house, or any
other major expense or money that you would give or receive (e.g., inheritance, or large gifts
to or from you). Therefore, the sign (+/-) of entries in this column is important.
Positive numbers will be considered in the cash flow for that year and the surplus, if any, will be
deposited in the taxable savings accounts. Negative numbers will potentially generate additional
withdrawals and distributions from retirement accounts. This is the only column that can contain
negative numbers: all other column entries should be positive.

The tab name for each spreadsheet represents the name of the spouse for reporting yearly transactions
affecting the plan. For each individual in the plan, there has to be a tab with the same name.
Therefore, when running your own case, you will need to rename the tabs in the template file to
have the same names as those used to create the plan
(i.e., *Jack* and *Jill* in the example files provided).

If a file was originally associated with a *case* file, a message will remind the user to upload the file.

#### Fixed Income
This tab is for entering anticipated fixed income from pensions and social security.
Amounts are in \\$k at the starting date. In the current implementation,
social security is adjusted for inflation while pension is not, and
the income starts on the first day of the year selected, with the value provided.
In other words, the values given are in future \\$, not in today's \\$.

#### Rate Selection
This tab allows you to select the return rates over the
time span of the plan. All rates are annual.
There are two major types of rates:
- *Fixed rates* - staying the same from one year to another
    - *conservative*
    - *optimistic*
    - *historical average* - i.e., average over a range of past years
    - *user* - rates are provided by the user
- *Varying rates* - changing from year to year
    - *historical* - using a rate sequence which happened in the past
    - *histochastic* - using stochastic rates derived from statistics of historical rates
    - *stochastic* - using stochastic rates created from statistical parameters specified by the user.

These rates are the annual rates of return for each of the assets considered. The types of asset are described
in the next section.

#### Asset Allocations
This tab allows you to select how to partition your assets between 4 investment options:
- S&P 500
- Corporate Bonds Baa
- 10-year Treasury Notes
- Cash assets assumed to follow inflation.

Two choices of asset allocations are possible:
*account* and *individual*. For *account* type, each type
of individual savings account is associated with its own asset allocation ratios.
For *individual*, it is assumed that all savings accounts of a given
individual follow the same allocation ratios.
Allocation ratios can vary over the duration of the plan, starting
from an *initial* allocation ratio at the beginning of the plan
to a *final* allocation ratio at the passing of the individual.
It is assumed that the accounts are regularly
rebalanced to maintain the prescribed allocation ratios.

An gliding function (either *linear* or an *s-curve*) interpolates the values
of the allocation ratios from the *initial* values to the *final* values as the plan progresses in time.
When an *s-curve* is selected, two additional parameters controlling the shape of the transition
will appear, one for the timing of the inflection point measured in years from now,
and the other for the width of the transition, measured in +/- years from the center.

### Optimization Parameters
This tab allows you to select the problem to optimize.
One can choose between maximizing the net spending amount subject to a constraint
of a desired bequest, or maximizing a bequest, subject to a constraint of providing
a desired net spending amount.
As one of the two choices (net spending or bequest) is selected as the value to maximize,
the other becomes a constraint to obey.

Maximum amount for Roth conversions and who can execute them need to be
specified. If a contribution file has been uploaded and the `Convert from contributions file`
is toggled, Roth conversions will not be optimized, but will rather be performed according to
the column `RothX` described in the
[Wages and Contributions](#wages-and-contributions) tab.

Calculations of Medicare and IRMAA can be turned on or off. This will typically speed up
the calculations by a factor of 2 to 3, which can be useful when running Monte Carlo simulations.

The time profile of the net spending amount
can be selected to either be *flat* or follow a *smile* shape.
The smile shape has two configurable parameters: a *dip* percentage
and a linear *increase* over the years (apart from inflation).
Values default to 15% and 12% respectively, but they are configurable
for experimentation.

For married couples, a survivor's
net spending percentage is also configurable. A value of 60% is typically used.
The selected profile curve multiplies
the net spending *basis* which sets the resulting spending
amounts over the duration of the plan.
Notice that *smile* curves are re-scaled to have the same total spending as flat curves:
for that reason they do not start at 1.


--------------------------------------------------------------------------------------
### :orange[Single Scenarios]

#### Case Results
Run a single scenario based on the selections made in the [Case Setup](#case-setup) section.
This simulation runs over a single instance of a series of rates, either fixed or varying.
The outcome is optimized according to the chosen parameters: either maximize the
net spending, of maximize the bequest under the constraint of a net spending amount.
If `Convert from contributions file` is not toggled on,
Roth conversions are optimized for maximizing the selected objective function.
Various plots show the results, which can be displayed in today's \\$ or
in nominal value.

Under this tab, one can also save all the parameters used to generate the
outcome in a *case* file that can be uploaded in the future.

#### Case Worksheets
This tab shows the various worksheets containing annual transactions.
A workbook can be downloaded as an Excel file for future reference, and
is better viewed in Excel than through the browser's representation.
All values here (worksheets and workbook) are in \\$, not in thousands.

#### Case Summary
This tab shows a summary of the scenario which was computed.
It displays informative sums of relevant income and spending values.

--------------------------------------------------------------------------------------
### :orange[Multiple Scenarios]
There are two different ways to run multiple scenarios and generate a histogram
of results.

#### Historical Range
This tab allows the user to run multiple simulations over a range of historical time spans.
Each simulation assumes that the rates followed a sequence which happened in the past,
starting from each year in the past, and then offset by one year, and so on.
A histogram of results and a success rate is displayed at the end of the run.
$N$ is the number of runs, $P$ the probability of success,
$\\bar{x}$ is the resulting average, and $M$ is the median.

If the `Beneficiary fractions` are not all unity, two histograms will be displayed:
one for the partial bequest at the passing of the first spouse
and the other for the distribution of values of the objective being optimized.

#### Monte Carlo
This tab runs a Monte Carlo simulation using time sequences of annual rates of return that are generated
using statistical methods. At the end of the run,
a histogram is shown, with a probability of success.

The mean outcome $\\bar{x}$ and the median $M$ are provided in the graph, as are the number
of cases $N$ and the probability of success $P$, which is the percentage of cases that succeeded.

If the `Beneficiary fractions` are not all unity, two histograms will be displayed:
one for the partial bequest at the passing of the first spouse
and the other for the distribution of values of the objective being optimized.

--------------------------------------------------------------------------------------
### :orange[Resources]
#### Documentation
These pages.

#### Logs
Messages coming from the underlying Owl calculation engine are displayed under this tab.

#### About Owl
Credits and disclaimers.

</div>
''', unsafe_allow_html=True)
