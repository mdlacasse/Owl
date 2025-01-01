
# Owl   

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.jpg" width="250">

This package is a retirement modeling framework for exploring the sensitivity of retirement financial decisions.
Strictly speaking, it is not a planning tool, but more an environment for exploring *what if* scenarios.
It provides different realizations of a financial strategy through the rigorous
mathematical optimization of relevant decision variables. Two major objective goals can be set: either
maximize net spending, or after-tax bequest under various constraints.
Look at *Basic capabilities* below for more detail.

One can certainly have a savings plan, but due to the volatility of financial investments,
it is impossible to have a certain asset earnings plan. This does not mean one cannot make decisions.
These decisions need to be guided with an understanding of the sensitivity of the parameters.
This is exactly where this tool fits it. Given your savings capabilities and spending desires,
it can generate different future realizations of
your strategy under different market assumptions, helping to better understand your financial situation.

Disclaimers: I am not a financial planner. You make your own decisions. This program comes with no guarantee. Use at your own risk.

More disclaimers: While some output of the code has been verified with other approaches,
this code is still under development and I cannot guarantee the accuracy of the results.
Use at your own risk.

-------------------------------------------------------------------------------------
## Purpose and vision
The goal of Owl is to create a free and open-source ecosystem that has cutting-edge optimization capabilities,
allowing for the next generation of Python-literate retirees to experiment with their own financial future
while providing a codebase where they can learn and contribute. There are and were
good retirement optimizers in the recent past, but the vast majority of them are either proprietary platforms
collecting your data, or academic papers that share the results without really sharing the details of
the underlying mathematical models.
The algorithms in Owl rely on the open-source HiGHS linear programming solver. The complete formulation and
detailed description of the underlying
mathematical model can be found [here](https://raw.github.com/mdlacasse/Owl/main/docs/owl.pdf).

While Owl can be used through a Jupyter notebooks,
its simple API also serves as a back-end for a Web application using Streamlit.
A hosted version of the app can be found at [owlplanner.streamlit.app](https://owlplanner.streamlit.app).
Alternatively, the application can also be run locally by simply running the script
`owlplanner.cmd` once all the dependencies have been installed.

Not every retirement decision strategy can be framed as an easy-to-solve optimization problem.
In particular, if one is interested in comparing different withdrawal strategies,
[FI Calc](ficalc.app) is a more appropriate and elegant application that addresses this need.
If, however, you also want to optimize spending, bequest, and Roth conversions, with
an approach also considering Medicare and federal income tax over the next few years,
then Owl is definitely a tool that can help guide your decisions.

--------------------------------------------------------------------------------------
## Basic capabilities
Owl can optimize for either maximum net spending under the constraint of a given bequest (which can be zero),
or maximize the after-tax value of a bequest under the constraint of a desired net spending profile,
and under the assumption of a heirs marginal tax rate.
Roth conversions are also considered, subject to an optional maximum conversion amount,
and optimized to suit the goals of the selected objective function.
All calculations are indexed for inflation, which is either provided as a fixed rate,
or through historical values, as are all other rates used for the calculations.
These rates can be used for backtesting different scenarios by choosing
*historical* rates, or by choosing *historical average* rates over a historical year range,
or what I coined "*histochastic*" rates which are
generated using the statistical distribution of observed historical rates.

Portfolios available for experimenting include assets from the S&P 500, Corporate Bonds Baa, Treasury 10-y Notes,
and cash assets assumed to just follow inflation which is represented by the Consumer Price Index.
Other asset classes can easily be added, but would add complexity while only providing diminishing insights.
Historical data used are from
[Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/) at the Stern School of Business.
Asset allocations are selected for the duration of the plan, and these can glide linearly
or along a configurable s-curve from now to the last year of the plan.

Spending profiles are adjusted for inflation, and so are all other indexable quantities. Proflies can be
flat or follow a *smile* curve which is also adjustable through two simple parameters.

Available rates are from 1928 to last year and can be used to test historical performance.
Fixed rates can also be provided, as well as *histochastic* rates, which are generated using
the statistical characteristics (means and covariance matrix) of
a selected historical year range. Pure *stochastic* rates can also be generated
if the user provides means, volatility (expressed as standard deviation), and optionally
the correlations between the different assets return rates provided as a matrix, or a list of
the off-diagonal elements (see the notebook tutorial for details).
Average rates calculated over a historical data period can also be chosen.

Monte Carlo simulations capabilities are included  and provide a probability of success and a histogram of
outcomes. These simulations can be used for either determining the probability distribution of the
maximum net spending amount under
the constraint of a desired bequest, or the probability distribution of the maximum
bequest under the constraint of a desired net spending amount. Unlike discrete-event
simulators, Owl uses an optimization algorithm for every new scenario, which results in more
calculations being performed. As a result, the number of cases to be considered should be kept
to a reasonable number. For a few hundred cases, a few minutes of calculations can provide very good estimates
and reliable probability distributions. Optimizing each solution is more representative in the sense that optimal solutions
will naturally adjust to the return scenarios being considered. This is more realistic as retirees would certainly re-evaluate
their expectations under severe market drops or gains. This optimal approach provides a net benefit over event-based simulations,
which maintain a distribution strategy either fixed, or within guardrails for capturing the
 retirees' reactions to the market.

Basic input parameters are given through function calls while optional additional time series can be read from
an Excel spreadsheet that contains future wages, contributions
to savings accounts, and planned *big-ticket items* such as the purchase of a lake house, the sale of a boat,
large gifts, or inheritance.

Three types of savings accounts are considered: taxable, tax-deferred, and tax-exempt,
which are all tracked separately for married individuals. Asset transition to the surviving spouse
is done according to beneficiary fractions for each account type.
Tax status covers married filing jointly and single, depending on the number of individuals reported.

Medicare and IRMAA calculations are performed through a self-consistent loop on cash flow constraints. Future
values are simple projections of current values with the assumed inflation rates.

See one of the notebooks for a tutorial and representative user cases.

### Limitations
Owl is work in progress. At the current time:
- Only the US federal income tax is considered (and minimized through the optimization algorithm).
Head of household filing status has not been added but can easily be.
- Required minimum distributions are calculated, but tables for spouses more than 10 years apart are not included. An error message will be generated for these cases.
- Social security rule for surviving spouse assumes that benefits were taken at full retirement age.
- Current version has no optimization of asset allocations between individuals and/or types of savings accounts.
If there is interest, that could be added in the future.
- In the current implementation, social securiy is always taxed at 85%.
- Medicare calculations are done through a self-consistent loop.
This means that the Medicare premiums are calculated after an initial solution is generated,
and then a new solution is re-generated with these premiums as a constraint.
In some situations, when the income (MAGI) is near an IRMAA bracket, oscillatory solutions can arise.
Owl will detect these cases and inform the user.
While the solutions generated are very close to one another, Owl will pick the smallest one
for being conservative.
- Part D is not included in the IRMAA calculations. Being considerably more, only Part B is taken into account. 
- Future tax brackets are pure speculations derived from the little we know now and projected to the next 30 years. Your guesses are as good as mine.
Having a knob to adjust future rates might be an interesting feature to add for measuring the impact on Roth conversions.

The solution from an optimization algorithm has only two states: feasible and infeasible.
Therefore, unlike event-driven simulators that can tell you that your distribution strategy runs
out of money in year 20, an optimization-based solver can only tell you that a solution does or does not
exist for the plan being considered. Examples of infeasible solutions include requesting a bequeathed
estate value too large for the savings assets to support, even with zero net spending basis,
or maximizing the bequest subject to a net spending basis that is already too large for the savings
assets to support, even with no estate being left.

-----------------------------------------------------------------------
## An example of Owl's functionality
With about 10 lines of Python code, one can generate a full case study.
Here is a typical plan with some comments.
A plan starts with the names of the individuals, their birth years and life expectancies, and a name for the plan.
Dollar amounts are in k\$ (i.e. thousands) and ratios in percentage.
```python
import owlplanner as owl
# Jack was born in 1962 and expects to live to age 89. Jill was born in 1965 and hopes to live to age 92.
# Plan starts on Jan 1st of this year.
plan = owl.Plan(['Jack', 'Jill'], [1962, 1965], [89, 92], 'jack & jill - tutorial', startDate='01-01')
# Jack has $90.5k in a taxable investment account, $600.5k in a tax-deferred account and $70k from 2 tax-exempt accounts.
# Jill has $60.2k in her taxable account, $150k in a 403b, and $40k in a Roth IRA.
plan.setAccountBalances(taxable=[90.5, 60.2], taxDeferred=[600.5, 150], taxFree=[50.6 + 20, 40.8])
# An Excel file contains 2 tabs (one for Jill, one for Jack) describing anticipated wages and contributions.
plan.readContributions('jack+jill.xlsx')
# Jack will glide an s-curve for asset allocations from a 60/40 -> 70/30  stocks/bonds portfolio.
# Jill will do the same thing but is a bit more conservative from 50/50 -> 70/30 stocks/bonds portfolio.
plan.setInterpolationMethod('s-curve')
plan.setAllocationRatios('individual', generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]])
# Jack has no pension, but Jill will receive $10k per year at 65 yo.
plan.setPension([0, 10.5], [65, 65])
# Jack anticipates receiving social security of $28.4k at age 70, and Jill $19.7k at age 62. All values are in today's $.
plan.setSocialSecurity([28.4, 19.7], [70, 62])
# Instead of a 'flat' profile, we select a 'smile' spending profile, with 60% needs for the survivor.
plan.setSpendingProfile('smile', 60)
# We will reproduce the historical sequence of returns starting in year 1969.
plan.setRates('historical', 1969)
# Jack and Jill want to leave a bequest of $500k, and limit Roth conversions to $100k per year.
# Jill's 403b plan does not support in-plan Roth conversions.
# We solve for the maximum net spending profile under these constraints.
plan.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 500, 'noRothConversions': 'Jill'})
```
The output can be seen using the following commands that display various plots of the decision variables in time.
```python
plan.showNetSpending()
plan.showGrossIncome()
plan.showTaxes()
plan.showSources()
plan.showAccounts()
plan.showAssetDistribution()
...
```
By default, all these plots are in nominal dollars. To get values in today's $, a call to
```python
plan.setDefaultPlots('today')
```
would change all graphs to report in today's dollars. Each plot can also override the default by setting the `value`
parameters to either *nominal* or *today*, such as in the following example, which shows the taxable ordinary
income over the duration of the plan,
along with inflation-adjusted extrapolated tax brackets. Notice how the optimized income is surfing
the boundaries of tax brackets.
```python
plan.showGrossIncome(value='nominal')
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/taxIncomePlot.png" width="75%">

The optimal spending profile is shown in the next plot (in today's dollars). Notice the drop
(recall we selected 60% survivor needs) at the passing of the first spouse.
```python
plan.showProfile('today')
```

<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/spendingPlot.png" width="75%">

The following plot shows the account balances in nominal value for all savings accounts owned by Jack and Jill.
It was generated using
```python
plan.showAccounts(value='nominal')
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/savingsPlot.png" width="75%">

while this plot shows the complex cash flow from all sources, which was generated with
```python
plan.showSources(value='nominal')
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/sourcesPlot.png" width="75%">

For taxes, the following call will display Medicare premiums (including Part B IRMAA fees) and federal income tax
```python
plan.showTaxes(value='nominal')
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/taxesPlot.png" width="75%">

For the case at hand, recall that asset allocations were selected above through

```python
plan.setAllocationRatios('individual', generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]])
```
gliding from a 60%/40% stocks/bonds portfolio to 70%/30% for Jack, and 50%/50% -> 70%/30% for Jill.
Assets distribution in all accounts in today's $ over time can be displayed from
```python
plan.showAssetDistribution(value='today')
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/AD-taxable.png" width="75%">
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/AD-taxDef.png" width="75%">
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/AD-taxFree.png" width="75%">

These plots are irregular because we used historical rates from 1969. The volatility of
the rates offers Roth conversion benefits which are exploited by the optimizer.
The rates used can be displayed by:
```python
plan.showRates()
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/ratesPlot.png" width="75%">

Values between brackets <> are the average values and volatility over the selected period. 

For the statisticians, rates distributions and correlations between them can be shown using:
```python
plan.showRatesCorrelations()
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/ratesCorrelations.png" width="75%">

A short text summary of the outcome of the optimization can be displayed through using:
```python
plan.summary()
```
The output of the last command reports that if future rates are exactly like those observed
starting from 1969 and the following years, Jack and Jill could afford an annual spending of
 \\$97k starting this year
(with a basis of \\$88.8k - the basis multiplies the profile which can vary over the course of the plan).
The summary also contains many more details:
```
SUMMARY ================================================================
Plan name: jack & jill - tutorial
        Jack's life horizon: 2024 -> 2051
        Jill's life horizon: 2024 -> 2057
Contributions file: examples/jack+jill.xlsx
Initial balances [taxable, tax-deferred, tax-free]:
        Jack's accounts: ['$90,500', '$600,500', '$70,000']
        Jill's accounts: ['$60,200', '$150,000', '$40,000']
Return rates: historical
Rates used: from 1969 to 2002
This year's starting date: 01-01
Optimized for: maxSpending
Solver options: {'maxRothConversion': 100, 'bequest': 500, 'noRothConversions': 'Jill'}
Number of decision variables: 1026
Number of constraints: 894
Spending profile: smile
Surviving spouse spending needs: 60%
Net yearly spending in year 2024: $97,098
Net spending remaining in year 2024: $97,098
Net yearly spending profile basis in 2024$: $88,763
Assumed heirs tax rate: 30%
Spousal surplus deposit fraction: 0.5
Spousal beneficiary fractions to Jill: [1, 1, 1]
Spousal wealth transfer from Jack to Jill in year 2051 (nominal):
    taxable: $0  tax-def: $63,134  tax-free: $2,583,303
Sum of spousal bequests to Jill in year 2051 in 2024$: $592,103 ($2,646,437 nominal)
Post-tax non-spousal bequests from Jack in year 2051 (nominal):
    taxable: $0  tax-def: $0  tax-free: $0
Sum of post-tax non-spousal bequests from Jack in year 2051 in 2024$: $0 ($0 nominal)
Total net spending in 2024$: $2,804,910 ($7,916,623 nominal)
Total Roth conversions in 2024$: $311,760 ($443,005 nominal)
Total ordinary income tax paid in 2024$: $236,710 ($457,922 nominal)
Total dividend tax paid in 2024$: $3,437 ($3,902 nominal)
Total Medicare premiums paid in 2024$: $117,817 ($346,404 nominal)
Post-tax account values at the end of final plan year 2057: (nominal)
    taxable: $0  tax-def: $0  tax-free: $2,553,871
Total estate value at the end of final plan year 2057 in 2024$: $500,000 ($2,553,871 nominal)
Inflation factor from this year's start date to the end of plan final year: 5.11
Case executed on: 2024-12-09 at 22:11:57
------------------------------------------------------------------------
```
And an Excel workbook can be saved with all the detailed amounts over the years by using the following command:
```python
plan.saveWorkbook(overwrite=True)
```
For Monte Carlo simulations, the mean return rates, their volatility and covariance are specified
and used to generate random scenarios. A histogram of outcomes is generated such as this one for Jack and Jill, which was generated
by selecting *stochastic* rates and using
```
plan.runMC('maxSpending', ...)
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/MC-tutorial2a.png" width="75%">

Similarly, the next one was generated using
```
plan.runMC('maxBequest', ...)
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/MC-tutorial2b.png" width="75%">


See tutorial notebooks [1](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_1.ipynb),
[2](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_2.ipynb), and
[3](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_3.ipynb) for more info.


---------------------------------------------------------------
## Requirements

If you have Python already installed on your computer, Owl can be installed as a package using the following commands:
```shell
python -m build
pip install .
```
These commands need to run from the Owl directory where you downloaded Owl from GitHub either through git or a zip file.
Pip will install all the required dependencies.

Owl relies on common Python modules such as NumPy, Pandas, SciPy, matplotlib, and Seaborn.
Package `odfpy` might be required if one read files created by LibreOffice. Again, these dependencies
will be installed by pip.

The simplest way to get started with Owl is to use the `streamlit` browser-based user interface
that is started by the `owlplanner.cmd` script, which  will start a user interface on your own browser.
Here is a screenshot of one of the multiple tabs of the interface:

<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/OwlUI.png" width="100%">

Alternatively, one can prefer using Owl from Jupyter notebooks. For that purpose, the `examples` directory
contains many files as a tutorial. The Jupyter Notebook interface is a browser-based application for authoring documents that combines live-code with narrative text, equations and visualizations.
Jupyter will run in your default web browser, from your computer to your browser, and therefore no data is ever transferred on the Internet
(your computer, i.e., `localhost`, is the server).

For simulating your own realizations, use the files beginning with the word *template*.
Make a copy and rename them with your own names while keeping the same extension.
Then you'll be able to personalize a case with your own numbers and start experimenting with Owl.
Notebooks with detailed explanations can be found in
[tutorial_1](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_1.ipynb),
[tutorial_2](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_1.ipynb), and
[tutorial_3](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_2.ipynb).

Finally, you will also need the capability to read and edit Excel files. One can have an Excel license, or use the LibreOffice free alternative. You can also use Google docs.

---------------------------------------------------------------------

## Credits
- Historical rates from [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/)
- Image from [freepik](freepik.com)
- Optimization solver from [HiGHS](highs.dev)

---------------------------------------------------------------------

Copyright &copy; 2024 - Martin-D. Lacasse

Disclaimers: I am not a financial planner. You make your own decisions. This program comes with no guarantee. Use at your own risk.

--------------------------------------------------------

