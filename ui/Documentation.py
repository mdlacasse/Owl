import streamlit as st


col1, col2, col3, col4 = st.columns(4)
with col4:
    st.image("../docs/images/owl.jpg")

st.write('## Owl Retirement Planner')
st.markdown('''
#### A retirement exploration tool based on linear programming

This tool is based on the Owl Python package aimed at providing a retirement modeling
framework for exploring the sensitivity of retirement financial decisions.
Strictly speaking, Owl is not a planning tool, but more an environment for exploring *what if* scenarios.
It provides different realizations of a financial strategy through the rigorous
mathematical optimization of relevant decision variables. Using a linear programming approach,
two major objective goals can be set: either
maximize net spending, or after-tax bequest under various constraints.
Roth conversions are optimized to reduce tax burden, while federal income tax and Medicare
premiums (including IRMAA) are calculated.
See the full description of the package on [github](github.com/mdlacasse/owl) for details.

--------------------------------------------------------------------------------------
## Description of the Web-based user interface
The function of each tab is described below. Typically, tabs would be run in order.
### Case Setup
This section contains all the steps for creating case scenarios.
#### Basic Info
This tab controls the creation of scenarios.
In this tab, you can either create a scenario from scratch, load a configuration file
that contains the desired parameters, duplicate and/or rename a scenario, or delete scenarios.
For creating a scenario, the (first) name(s), marital status, birth year(s),
and life expectancies are required. A starting date for the plan is needed to the first year only.
Individuals are assumed to pass at the end of the last year related to the life expectancy specified.
A file called `Jan Plan.ini` is available in the `examples` directory to load and help you get started.

Start with the `Select case` box and choose one of `New case...` or `Load config...`.

#### Assets
This tab allows to enter account balances in all savings accounts and
the spousal beneficiary fraction associated with these accounts.
Notice that all amounts are entered in units of \\$1,000, referred to as (\\$k).

Three types of saving accounts are considered and are tracked separately for spouses:
- Taxable saving accounts
- Tax-deferred saving accounts
- Tax-exempt saving accounts

#### Wages and Contributions
This tab allows to enter an optional Excel file containing wages and contributions.
This file contains columns as titled follows:
-  wages
#### Fixed Income
This tab is for entering anticipated fixed income from pensions and social security.
Amounts are in \\$k at the starting date.
#### Rate Selection
This is the most complex tab which allows you to select the return rates over the
time span of the plan. There are two major types of rates:
- *Fixed rates* - staying fixed from one year to another
	- *conversative*
	- *realistic*
	- *historical average* over a past year range
	- *user* provided
- *Varying rates* - varying from year to year
	- *historical* - using a rate sequence which happened in the past
	- *histochastic* - using stochastic rates derived from historical rates
	- *stochastic* - using stochastic rates created from parameters specified by the user.

These rates are the rates of return for the assets considered. These assets are described
in the next section.

#### Asset Allocations
This tab allows you to select how to partition your assets between 4 investment options:
- S&P 500
- Corporate Bonds Baa
- 10-year Treasury Notes
- Cash assets assumed to follow inflation.

Asset allocations are requested at the beginning and the end of a plan, and
a gliding function (either linear or an s-curve) allows you to glide from the
initial value to the final value.
### Optimization Parameters
This tab allows you to select the optimization parameters.

--------------------------------------------------------------------------------------
### Single Scenarios
#### Case Results 
Run a single scenario based on the selections made in the previous tabs.
This is one instance of a series of rates, either fixed or varying.
The outcome is optimized according to the chosen parameters: either maximize the
net spending, of maximize the bequest under the constrait of a net spending amount. 
Roth conversions are optimized for reducing income taxes on the bequest.
#### Case Worksheets 
This tab shows the various worksheets containing annual transactions.
It can be downloaded as an Excel file which looks better than the web representation.
#### Case Summary 
This tab shows a summary of the scenario which was computed.
It diplays informative sums of relevant income and spending values.

--------------------------------------------------------------------------------------
### Multiple Scenarios
#### Historical Range
This tab allows the user to run multiple similations over a range of historical time spans.
Each simulation assumes that the rates followed a sequence which happened in the past,
starting from each year in th past and then offset by one year.
A histogram of results and a success rate is displayed at the end of the run.
$N$ is the number of runs, and $P$ the probability of success.
#### Monte Carlo
This tab runs a Monte Carlo simulation using sequences of return that were generated
statistically using the parameters provided by the user. At the end of the run,
a histogram is shown, with a probability of success.

--------------------------------------------------------------------------------------
### Resources
#### Documentation
These pages...
#### Logs
The messages coming from the undelying Owl calculation engine. 
#### About Owl
Credits and disclaimers.

'''
)
