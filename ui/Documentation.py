import streamlit as st

import sskeys as kz

col1, col2, col3 = st.columns([0.69, 0.02, 0.29], gap="large")
with col1:
    st.write("# Documentation")
    kz.divider("orange")
    st.write("## Owl Retirement Planner\n-------")
with col3:
    st.image("http://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png")
    st.caption("Retirement planner with great wisdom")

col1, col2 = st.columns([0.80, 0.20], gap="large")
with col1:
    st.markdown("""
#### A retirement financial exploration tool based on linear programming

The goal of Owl is to provide a free and open-source ecosystem that has cutting-edge
optimization capabilities, allowing for the new generation of computer-literate retirees
to experiment with their own financial future while providing a codebase where they can learn and contribute.
Strictly speaking, Owl is not a planning tool, but more an environment for exploring *what if* scenarios.
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
[here](https://raw.github.com/mdlacasse/Owl/main/docs/owl.pdf).

-------------------------------------------------
### :orange[Table of Contents]
[Getting Started with User Interface](#getting-started-with-user-interface)

[Case Setup](#case-setup)
- [Create Case](#create-case)
- [Wages and Contributions](#wages-and-contributions)
- [Fixed Income](#fixed-income)
- [Current Assets](#current-assets)
- [Asset Allocation](#asset-allocation)
- [Rates Selection](#rates-selection)
- [Optimization Parameters](#optimization-parameters)

[Single Scenario](#single-scenario)
- [Graphs](#graphs)
- [Worksheets](#worksheets)
- [Output Files](#output-files)

[Multiple Scenarios](#multiple-scenarios)
- [Historical Range](#historical-range)
- [Monte Carlo](#monte-carlo)

[Resources](#resources)
- [Logs](#logs)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Settings](#settings)
- [About Owl](#about-owl)

[Tips](#tips)
- [Advice on Optimization and Roth Conversions](#advice-on-optimization-and-roth-conversions)
- [Typical Workflow](#typical-workflow)
- [Streamlit App and Theme](#streamlit-app-and-theme)

--------------------------------------------------------------------------------------
### :orange[Getting Started with User Interface]
Functions of each page are described below in the same order as they appear in the left sidebar.
Typically, pages would be accessed in order, starting from the top.

A `Case selector` box located at the top of the page allows to
navigate between the different scenarios created.
When on the [Create Case](#create-case) page, however, the selector box offers two more options:
one to create a new case from scratch, and one to create a case
from a *case* parameter file, which
would then populate values of all parameters found
in the [Case Setup](#case-setup) section.
This box is present in all pages except those in the [Resources](#resource) section.
The case being currently displayed is marked with a small red triangle.

A typical workflow for exploring different scenarios involves starting with a base
case and then duplicating/creating derived scenarios with slight changes in the parameters.
A comparison between the
different resulting outcomes can be found on the [Output Files](#output-files) page.
The [Typical Workflow](#typical-workflow) section below
goes through a more specific example.

Except for the first year, which can potentially be truncated,
Owl uses a full year as the standard unit of time. All values are therefore entered and
reported as yearly values. These include wages, income, rates, social security, etc.
Dollar values are typically entered in thousands, unless in tables, where they
are entered and reported in unit dollars. Graphs report values in thousands.

There are four sections in the user interface:
[Case Setup](#case-setup), [Single Scenario](#single-scenario),
[Multiple Scenarios](#multiple-scenarios), and [Resources](#resources).
The sections below follow the same logical order.

-------------------------------------------------
### :orange[Case Setup]
This section contains the steps for creating and configuring case scenarios.

#### Create Case
The *Create Case* page is where every new scenario begins.
It controls the creation of scenarios as the `Case selector` drop-down menu contains
two additional items when this page is open:
one to create new cases, and the other to create cases from a *case* parameter file.
This page also allows you to duplicate and/or rename scenarios, as well as deleting them.

For creating a scenario from scratch, (first) name(s), marital status, birth year(s),
and life expectancies are required. A starting date for the plan determines when the plan
starts in the first year. Plan still ends at the end of the year when all individuals
have passed according to the specified life expectancies.

Except for the first year of the plan, which can be truncated
by specifying a start date, the unit of time in Owl is a year.
As months are not currently considered in Owl, plans will be more
representative if birth years are rounded to the closest January 1st, i.e.,
rounding up to the following year if born late in the year.

A typical workflow will involve creating
a base case, and duplicating it a few times with slight changes in its parameters
to investigate their effects.
Duplication appends a number counter in parenthesis to the name, just as creating
a copy of a file on Windows.
It is recommended to rename cases to reflect the change in parameters.
When duplicating a scenario, make sure to visit all pages in the [Case Setup](#case-setup)
section and verify that all parameters are as intended.
When all cases have successfully run,
results of the different cases are compared side-by-side with differences
in the [Output Files](#output-files) section.

##### Initializing the life parameters for the realization
Start with the `Case selector` box and choose one of `New case...` or `Upload case file...`.

If `Upload case file...` is selected, a *case* file must be uploaded.
These files end with the *.toml* extension, are human readable (and therefore editable),
and contain all the parameters required to characterize a scenario.
An example is provided
[here](https://raw.github.com/mdlacasse/Owl/main/examples/case_jack+jill.toml) and more
can be found in this [directory](https://github.com/mdlacasse/Owl/blob/main/examples/).
Using a *case* file
will populate all the fields required to run a scenario. A *case* file for the case being developed
can be saved under the [Output Files](#output-files) page and made available to reload at a later time.
Case parameter files can have any name but when saving from the interface,
their name will start with *case_*
followed by the case name.

When starting from `New case...`,
one must provide the year of birth of each spouse(s) and their expected lifespan(s).
For selecting your own numbers, there are plenty of longevity predictors on the Internet.
Pick your favorite:
- [longevityillustrator](https://longevityillustrator.org),
- [livingto100](https://www.livingto100.com/calculator),

or just Google *life expectancy calculator*.

Finally, a starting date for the first year of the plan must be provided.
By default, it starts today, but any other date
in the current year can be chosen. This is useful if your numbers are known for a fixed date, or
for reproducibility purposes. This date does not affect when the plan ends, which is at the
end of the year when all individuals in the plan have passed.

#### Wages and Contributions
This page allows to enter an optional Excel file containing future wages and contributions.
Alternatively, values can be entered and/or edited directly into the corresponding tables.
Values in these tables are all in nominal values, and in \\$, not thousands (\$$k).
The wages and contributions data contains 9 columns titled as follows:

|year|anticipated wages|ctrb taxable|ctrb 401k|ctrb Roth 401k|ctrb IRA|ctrb Roth IRA|Roth conv|big-ticket items|
|--|--|--|--|--|--|--|--|--|
|2025 | | | | | | | | |
|2026 | | | | | | | | |
| ... | | | | | | | | |
|20XX | | | | | | | | |

Note that column names are case sensitive and all entries are in lower case.
The easiest way to complete the process of filling this file is either to start from the template
file provided [here](https://raw.github.com/mdlacasse/Owl/main/examples/template.xlsx) or
to fill in the values using the user interface, but this last approach does not provide
Excel capabilities for cross-column calculations.

Here, year 20XX represents the last row which could be the last year based on the life
expectancy values provided.
While loading an Excel workbook, missing years or empty cells will be filled with zero values,
while years outside the time span of the plan will simply be ignored.

The column *anticipated wages* is the annual amount
(gross minus tax-deferred contributions) that you anticipate to receive from employment
or other sources (e.g., rentals).
This column does not include dividends from your taxable investment accounts,
as they will be calculated based on your return rate assumptions.

For the purpose of planning, there is no clear definition of retirement age. There will be a year,
however, from which you will stop having anticipated income, or diminished income due to decreasing your
work load. This transition can be gradual or sudden, and can be explored through these wages
and contributions tables.

Contributions to your savings accounts are marked as *ctrb*. We use 401k as a term which includes
contributions to 403b as well or any other tax-deferred account, with the exception
of IRAs accounts which are treated separately for clarity.
Contributions to your 401k/403b must also include your employer's
contributions, if any. As these data can exist in Excel,
one can use the native calculator to enter a percentage
of the anticipated wages for contributions as this can sometimes be easier to manage.
For this purpose, additional columns can coexist in the Excel file
and can be used for tracking other quantities from which
to derive the numbers needed. These extra columns will be ignored when the file is processed.

Manual Roth conversions can be specified in the column marked *Roth conv*.
This column is provided to override the Roth conversion optimization in Owl.
When the option `Convert as in contribution file` is toggled
in the [Optimization Parameters](#optimization-parameters) page,
values from the contributions file will be used and no optimization on Roth conversions
will be performed. This column is provided for flexibility and to allow comparisons
between an optimized solution and your best guesses.

Finally, *big-ticket items* are used for accounting for the sale or purchase of a house, or any
other major expense or money that you would give or receive (e.g., inheritance, or large gifts
to or from you). Therefore, the sign (+/-) of entries in this column is important.
Positive numbers will be considered in the cash flow for that year and the surplus, if any, will be
deposited in the taxable savings accounts. Negative numbers will potentially generate additional
withdrawals and distributions from retirement accounts. This is the only column that can contain
negative numbers: all other column entries must be positive.

When loading an Excel workbook, each individual in the plan must have an associated sheet
for reporting yearly transactions affecting the plan. The association is made by having
the individual's name as the sheet name in the workbook.
Therefore, if preparing your own case using a template, you will need to rename the tabs in the file to
match the names used when creating the plan
(i.e., *Jack* and *Jill* in the example files provided).
If a file was originally associated with a *case* file, a message will remind the user to upload the file.

#### Fixed Income
This page is for entering anticipated fixed income from pensions and social security.
Amounts are in thousands (\\$k) in today's \\$. While
social security is always adjusted for inflation, pensions can optionally be
by selecting the corresponding button.
Income starts on the first day of the year selected, with the value provided,
adjusted for inflation if necessary. As months are not currently
considered in Owl, birth years should be rounded up to the following year
if born late in the year.

A great website for guidance on when to start taking social security is
[opensocialsecurity.com](https://opensocialsecurity.com).
And obviously there is [ssa.gov](https://ssa.gov).

#### Current Assets
This page allows to enter account balances in all savings accounts.
Notice that all amounts are entered in units of \\$1,000, referred to as (\\$k).

Three types of savings accounts are considered and are tracked separately for spouses:
- Taxable savings accounts (e.g., investment accounts, CDs),
- Tax-deferred savings accounts (e.g., 401k, 403b, IRA),
- Tax-exempt savings accounts (e.g., Roth 401k, Roth IRA).

For married couples, the spousal `Beneficiary fractions` associated with these accounts
can be selected, as well as a surplus deposit fraction. The first one controls
how much is left to the surviving spouse while the second determines
how to split potential surplus budget moneys between the taxable accounts of the spouses.
When the `Beneficiary fractions` are not all 1, it is recommended to deposit all
surplus moneys in the taxable account of the first individual to pass. Otherwise,
the optimizer will find creative solutions that can generate surpluses in order
to maximize the final bequest. Finally, when fractions are not all equal,
it can take longer to solve (minutes) as these cases trigger the use
of binary variables which involves more complex algorithms.
In some situations, transfers from tax-deferred savings accounts to taxable
savings accounts, through surpluses and deposits, can be part of the optimal solution.

Setting a surplus fraction that deposits some or all surpluses in the survivor's account
can sometimes lead to slow convergence. This is especially noticeable when solving with
varying rates and not so common when using fixed rates.
When using varying rates, it is recommended to set surpluses to be
deposited in the taxable account of first spouse to pass unless exploring specific scenarios.

#### Asset Allocation
This page allows you to select how to partition your assets between 4 investment options,
one equity and three fixed-income securities:
- S&P 500,
- Corporate Bonds Baa,
- 10-year Treasury Notes,
- Cash assets assumed to follow inflation.

When using historical data, the term S&P 500 represents the real index. However,
when selecting fixed rates, the term can represent any mix of stocks or equities.
The main difference is in the tax treatment of gains realized in the taxable account.
Equities will be taxed differently than fixed securities.

Two choices of asset allocations are possible:
`account` and `individual`. For `account` type, each type
of individual savings account is associated with its own asset allocation ratios.
For `individual`, it is assumed that all savings accounts of a given
individual follow the same allocation ratios.
Allocation ratios can vary over the duration of the plan, starting
from an `initial` allocation ratio at the beginning of the plan
to a `final` allocation ratio at the passing of the individual.
It is assumed that the accounts are regularly
rebalanced to maintain the prescribed allocation ratios.

A gliding function (either `linear` or an `s-curve`) interpolates the values
of the allocation ratios from the `initial` values to the `final` values as the plan progresses in time.
When an `s-curve` is selected, two additional parameters controlling the shape of the transition
will appear, one for the timing of the inflection point measured in years from now,
and the other for the width of the transition, measured in +/- years from the inflection point.

#### Rates Selection
This page allows you to select the return rates over the
time span of the plan. All rates are nominal and annual.
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
The types of asset are described
in the previous section. Rates for the S&P 500 equities include dividends.
Cash assets are securities such as Treasury Inflation-Protected Securities (TIPS)
considered to track inflation only and therefore remain at constant value.
As mentioned on the Rates Selection page,
unless historical, S&P 500 can represent any mix of equities (domestic, international, emerging, etc.).
A roundup of expert opinions on stock and bond return forecasts for the next decade can be found
[here](https://www.morningstar.com/portfolios/experts-forecast-stock-bond-returns-2025-edition) for 2025.

#### Optimization Parameters
This page allows you to select the objective to optimize.
One can choose between maximizing the net spending amount subject to the constraint
of a desired bequest, or maximizing a bequest, subject to the constraint of providing
a desired net spending amount.
As one of the two choices (net spending or bequest) is selected as the value to maximize,
the other becomes a constraint to obey.

The maximum amount for Roth conversions and who can execute them is configurable.
Roth conversions are optimized for reducing taxes and maximizing the selected objective function,
unless the `Convert from contributions file`
button is toggled, in which case Roth conversions will not be optimized,
but will rather be performed according to
the *Roth conv* column on the
[Wages and Contributions](#wages-and-contributions) page.
A year from which Roth conversions can begin to be considered can also be selected: no Roth
conversions will be allowed before the year specified.

Calculations of Medicare and IRMAA can be turned on or off. This will typically speed up
the calculations by a factor of 2 to 3, which can be useful when running Monte Carlo simulations.
If the age of individuals makes them eligible for Medicare within the next three years,
additional cells will appear for entering the Modified Adjusted Gross Income (MAGI) for the current
and past 2 years, when applicable. Values default to zero.
These numbers are needed to calculate the Income-Related Monthly Adjusted Amounts (IRMAA).
MAGI for current year is required as it allows plan to start in mid-year for the first year.

Different solvers can be selected. This option is mostly for verification purposes. All solvers
tested (HiGHS, COIN-OR Branch-and-Cut solver, and MOSEK) provided very similar results.
Due to the mixed integer formulation, solver performance is sometimes unpredictable.
In general, CBC will tend to be slower, partly because of the algorithm,
and partly because it solves the problem through a model description saved in
a temporary file requiring I/O.
Selecting `HiGHS` for most cases provides very good results.

The time profile modulating the net spending amount
can be selected to either be `flat` or follow a `smile` shape.
The smile shape has three configurable parameters: a `dip` percentage
a linear `increase` (or decrease if negative), over the time period (apart from inflation),
and a time `delay`, in years from today, before the non-flat behavior starts to act.
Values default to 15%, 12%, and 0 year respectively, but they are fully configurable
for experimentation and to fit your anticipated lifestyle.

A `slack` variable can also be adjusted. This variable allows the net spending to deviate from
the desired profile in order to maximize the objective. This is provided mostly for educational purpose
as maximizing the total net spending will involve leaving the savings invested for as long as possible,
and therefore this will favor smaller spending early in the plan and larger towards the end.
This tension between maximizing a dollar amount and the utility of money then becomes evident.
While the health of the individuals and therefore the utility of money is higher at the beginning
of retirement, maximizing the total spending or bequest will pull in the opposite direction.

For married couples, the survivor's
net spending percentage is also configurable. A value of 60% is typically used.
The selected profile multiplies
the net spending *basis* which sets the resulting spending
amounts over the duration of the plan.
Notice that *smile* curves are re-scaled to have the same total spending as flat curves:
for that reason they do not start at 1. Moreover, if the plan starts later
than on January 1$^{st}$, the value of the first year will be reduced accordingly.

--------------------------------------------------------------------------------------
### :orange[Single Scenario]

#### Graphs
This page displays various plots from a single scenario based on the selections made
in the [Case Setup](#case-setup) section.
This simulation uses a single instance of a series of rates, either fixed or varying,
as selected in the [Case Setup](#case-setup) section.
The outcome is optimized according to the chosen parameters: either maximize the
net spending, of maximize the bequest under the constraint of a net spending amount.
Various plots show the results, which can be displayed in today's \\$ or
in nominal value.

A button allows to re-run the case which would generate a different result
if the chosen rates are `histochastic` or `stochastic`. Each graph can be seen
in full screen, and are interactive when using the `plotly` library.
Graphs can be drawn using the `matplotlib` or `plotly` libraries as
selected in the [Settings](#settings) section described below.

#### Worksheets
This page shows the various worksheets containing annual transactions
and savings account balances in nominal \\$.
Each table can be downloaded separately in csv format, or all tables can be downloaded
together as an Excel workbook by clicking the associated button on the
[Output Files](#output-files) page.
Note that all values here (worksheets and workbook) are in \\$, not in thousands.
The first few lines of the *Sources* worksheets are the most important
as these lines are the only ones that are actionable in the near term.

#### Output Files
This page allows to compare cases and save files for future use.
First, it shows a synopsis of the computed scenario by
displaying sums of income, bequest, and spending values over the duration of the plan.
Note that all tables are scrollable and can be seen in full-screen mode.
If multiple cases were configured and run (most likely through duplication and
modifying the configuration), they will be compared in that panel provided they were made
for the same individuals and years spans. Column on the left shows the values for the selected case
while those on the right will show the differences.
The contents of the synopsis can be downloaded as a plain text file by
clicking the button below it.

Another section called `Excel workbooks` allows
to save the contents of the tables on corresponding pages of a single Excel workbook.
These data are displayed on the [Worksheets](#worksheets) and
the [Wages and Contributions](#wages-and-contributions) pages.

Similarly, all parameters used to generate the case are collected in *toml* format and displayed.
The `Download case file...` button allows to save the parameters of the selected scenario
to a *case* file for future use.

With the case parameter file and the wages and contributions worksheet,
the same case can be reproduced at a later time by uploading
them through the widgets on the [Create Case](#create-case)
and [Wages and Contributions](#wages-and-contributions) pages,
respectively.

--------------------------------------------------------------------------------------
### :orange[Multiple Scenarios]
There are two different ways to run multiple scenarios and generate a histogram
of results.

#### Historical Range
This page allows the user to run multiple simulations over a range of historical years.
Each simulation assumes that the rates follow a sequence that happened in the past,
starting from each selected year in the past, and then offset by one year, and so on.
A histogram of results and a success rate is displayed at the end of the run.
$N$ is the number of runs that could fit in the year range selected,
$P$ the probability of success,
$\\bar{x}$ is the resulting average, and $M$ is the median.

If the `Beneficiary fractions` are not all unity, two histograms will be displayed:
one for the partial bequest left at the passing of the first spouse
and the other for the distribution of values of the objective being optimized,
either maximum net spending or maximum bequest left at the passing
of the surviving spouse.

#### Monte Carlo
This page runs a Monte Carlo simulation using time sequences of
annual rates of return that are generated
using statistical methods. At the end of the run,
a histogram is shown, with a probability of success.

The mean outcome $\\bar{x}$ and the median $M$ are provided in the graph, as are the number
of cases $N$ and the probability of success $P$, which is the percentage of cases that succeeded.
Cases that failed are termed infeasible, as the optimizer could not find
values that could satisty all constraints.

As is the case for [Historical Range](#historical-range),
if the `Beneficiary fractions` are not all unity, two histograms will also be displayed:
one for the partial bequest left at the passing of the first spouse
and the other for the distribution of values of the objective being optimized,
either maximum net spending or maximum bequest left at the passing
of the surviving spouse.

Linear programming solutions are more expensive than event-driven forward simulators.
Therefore, when considering Monte Carlo simulations, consider:
- Turning off Medicare calculations,
- Installing Owl and running on your local computer as it can sometimes be
faster than running on the Streamlit host, depending on your hardware.
Moreover, the community server has a
CPU time limit that will stop a session after the quota is reached.
Most likely, this will not happen unless you devise unusually long Monte Carlo runs.

--------------------------------------------------------------------------------------
### :orange[Resources]
#### Logs
Messages coming from the underlying Owl calculation engine are displayed on this page.
This page is mainly used for debugging purposes.

#### Quick Start
This page is the landing page of the application.
It shows new users how to quickly get started by using an example case file.

#### Documentation
These very pages.

#### Settings
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

#### About Owl
Credits and disclaimers.

--------------------------------------------------------------------------------------
### :orange[Tips]
#### Advice on Optimization and Roth Conversions
Owl does not explicitly optimize for Medicare costs. While this approach
is possible and was tested,
it is not practical due to the unpredictable computing time
required by the additional amount of binary variables involved.
The current approach is to add
Medicare costs after the optimization step.
As a reult, the suggested Roth conversions can sometimes lead to
smaller net spending or bequest than when no conversions are made.
This is due to higher Medicare costs triggered by the increased MAGI
resulting from Roth conversions
which are is factored in during the optimization step.
This is why one should **always** run comparisons between cases with and without Roth conversions.
Also keep in mind that these cases only consider current assumptions and obviously
do not take into account future income tax rate increases.

#### Typical Workflow
A typical workflow would look like the following:
1) Create a base case representing your basic scenario;
2) Duplicate the base case and modify the parameter you want to investigate;
3) Repeat 2) with other end-member values of the parameter you would like to consider;
4) Run all cases and compare them on the [Output Files](#output-files) page.

To make it more concrete, here is an example
where one would like to investigate the effects of Roth conversions
on total net spending.
1) Create a case called, say, *Jan 2025 - Base case*.
Fill in all parameters representing your goals and situation.
Upload file or fill-in values for Wages and Contributions.
Let's say this case allows for Roth conversions up to \\$100k.
2) Duplicate the base case, call it *Jan 2025 - No Roth conversions* and
set maximum Roth conversions to 0.
3) Duplicate the base case again, call it *Jan 2025 - No Roth limit* and
set maximum Roth conversions to a vary large number, say, \\$800k.
4) Compare all cases on the [Output Files](#output-files) page.

As mentionned above, the most actionable information is located on the first few lines
of the *Sources* tables on the [Worksheets](#worksheets) pages.
This is where withdrawals and conversions are displayed for this year and the next few years.

#### Streamlit App and Theme
If you are accessing Owl remotely through the Chrome browser,
the Chrome performance manager might be configured to disable hidden or inactive tabs.
This could cause your Owl session to inadvertently reset when idling for too long,
and losing the state of the calculator.
The best way to avoid this situation is to run the web page through the Streamlit app on your device.
This is done by clicking the '+" icon at the right end of the browser URL bar,
showing *App available: Install Streamlit*.
The app provides more screen space as it doesn't have a navigation bar.
A similar thing can happen if your simulations
(Monte Carlo) are extremely long.
The Streamlit community server has a hard resource limit
on CPU time that might stop your calculations before completion.
I could successfully run 1,000 simulations using the Streamlit app while
being hosted on the Streamlit community server.
However, if you are contemplating running Monte Carlo simulations
with thousands of cases routinely,
you should definitely consider installing and running Owl
locally on your computer, either natively or through a container.
See instructions on the GitHub repository for how to proceed.

In general, collapsing the side menu and going full screen by hitting F11 while in your browser
can greatly improve the visualization of graphs and worksheets.
I also recommend using the *dark* mode as Streamlit's default theme, but a Light theme is
also available.
This selection is accessed through the *Settings* option
after clicking on the three vertical dots
located on the upper right of the app.
""")
