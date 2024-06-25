
# Owl   

## A retirement exploration tool based on linear programming

<img align=right src="https://github.com/mdlacasse/Owl/blob/main/docs/owl.jpg" width="250">


This package is a retirement modeling framework for exploring the sensitivity of retirement financial decisions.
Strictly speaking, it is not a planning tool, but more an environment for exploring *what if* scenarios.
It provides different realizations of a financial strategy. One can certainly have a savings plan, but due to the volatility of financial investments,
it is impossible to have a certain asset earnings plan. This does not mean one cannot make decisions.
These decisions need to be guided with an understanding of the sensitivity of the parameters.
This is exactly where this tool fits it. Given your savings and spending desires, it can generate different future realizations of
your strategy under different market assumptions, helping to better understand your financial situation.

Disclaimers: I am not a financial planner. You make your own decisions. This program comes with no guarantee. Use at your own risk.

More disclaimers: While some output of the code has been verified with other approaches, this code is still under development and I cannot
guarantee the accuracy of the results. Use at your own risk.

-------------------------------------------------------------------------------------
## Purpose and vision
The goal of Owl is to create a free and open-source ecosystem that has cutting-edge optimization capabilitiesi, allowing
for the next generation of Python-literate retirees to experiment with their financial future while providing a codebase
where they can learn and contribute. There are and were
good retirement optimizers in the recent past, but the vast majority of them are either proprietary platforms
collecting your data, or academic papers that share the results without really sharing the details of the underlying mathematical models.
The algorithm in Owl is using the open-source HiGHS linear programming solver. The complete formulation and
detailed description of the undelying
mathematical model can be found [here](https://raw.github.com/mdlacasse/Owl/main/docs/owl.pdf).

Owl is currently implemented through jupyter notebooks, but it can also easily serve as the back-end of a Web application
facilitating its use by allowing easier input of user-selected constraints for exploring the optimality of different scenarios.
Contributors with good front-end skills are therefore more than welcome to join the project.

Not every retirement decision strategy can be framed as an easy-to-solve optimization problem. In particular, if one
is interested in comparing different withdrawal strategies, [FI Calc](ficalc.app) is a more appropriate and elegant
application that addresses this need. If, however, you also want to optimize spending, bequest, or Roth conversions over the next few years,
then Owl is definitely a tool that can help guide your decisions.

--------------------------------------------------------------------------------------
## Basic capabilities
Owl can optimize for either maximum net spending under the constraint of a given bequest, or maximize the
bequest under the constraint of a desired net spending profile. Roth conversions are also considered
and optimized under the assumption of a heirs marginal tax rate and subject to an optional maximum
conversion amount. All calculations are indexed for inflation, which is provided as a fixed rate,
or through historical values, as are all other rates used for the calculations. These historical, fixed,
and stochastic rates can be used for backtesting different scenarios.

Portfolios available for experimenting include assets from the S&P 500, Corporate Bonds Baa, Treasury 10-y Notes,
and cash assets assumed to just follow inflation which is represented by the Consumer Price Index.
Other asset classes can easily be added, but would add complexity while only providing diminishing insights.
Data used are from
[Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/) at the Sterm School of Business.
Asset allocations are selected
for the duration of the plan, and these can glide linearly or along a configurable s-curve from now
to the last year of the plan.

Spending profiles are adjusted for inflation, and so are all other indexable quantities. Proflies can be
flat or follow a *smile* curve which is also adjustable.

Available rates are from 1928
to last year and can be used to test historical performance. Fixed rates can also be provided, as
well as stochastic rates, which are generated using the statistical characteristics of
a selected historical year range. Mean rates over a data period can also be chosen.

Basic input parameters are given through function calls while optional additional time series can be read from
an Excel spreadsheet than contains wages, contributions
to savings accounts, and planned *big ticket items* such as the purchase of a lake house or the sale of a boat.

Three types of savings accounts are considered: taxable, tax-deferred, and tax-exempt savings accounts
which are tracked separately for married individuals. Asset transition to the surviving spouse
is done according to beneficiary fractions for each account type.
Tax status covers married filing jointly and single, depending on the number of individuals reported.

See one of the notebooks for a tutorial and representative user cases.

### Limitations
Owl is work in progress. At the current time:
- Only the US federal income tax is considered (and minimized through the optimization algorithm).
Head of household filing status has not been added but can easily be.
- Required minimum distributions are calculated, but tables for spouses more than 10 years apart are not.
- Social security rule for surviving spouse assumes that benefits were taken at full retirement age.
- Current version has no optimization of asset allocations between individuals and/or types of savings accounts.
If there is interest, that could be added in the future.
- In the current implementation, social securiy is always taxed at 85%.
- There are no IRMAA calculations. However, this could probably be added in the future.
- Future tax brackets are pure speculation derived from the little we know now and projected to the next 30 years. Your guesses are as good as mine.
Having a knob to adjust future rates might be an interesting feature to add for measuring the impact on Roth conversions.

-----------------------------------------------------------------------
## An example of Owl's functionality
With about 10 lines of Python code, one can generate a full case study.
Here is a typical plan without comments.
A plan starts with birth years and life expectancies.
Dollar amounts are in k\$ and ratios in percentage.
```python
import owl
plan = owl.Plan([1962, 1965], [89, 92], 'jack & jill - tutorial')
plan.setAccountBalances(taxable=[90, 60], taxDeferred=[600, 150], taxFree=[50 + 20, 40])
plan.readContributions('jack+jill.xlsx')
plan.setInterpolationMethod('s-curve')
plan.setAllocationRatios('individual', generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]])
plan.setPension([0, 10], [65, 65])
plan.setSocialSecurity([28, 25], [70, 70])
plan.setSpendingProfile('smile')
plan.setRates('historical', 1969)
plan.solve('maxSpending', options={'maxRothConversion': 100, 'estate': 500})
```
The output can be seen using the following commands that display various plots of the decision variables in time.
```python
plan.showNetSpending()
plan.showGrossIncome()
plan.showTaxes()
plan.showSources()
plan.showAccounts()
...
```
Typical plots look like the following. The optimal spending profile looks like this in nominal dollars. Notice
the 40% drop (configurable) at the passing of the first spouse.

<img src="https://raw.github.com/mdlacasse/Owl/main/docs/spendingPlot.png" width="800">

The following plot shows the account balances in all savings accounts owned by Jack and Jill,

<img src="https://raw.github.com/mdlacasse/Owl/main/docs/savingsPlot.png" width="800">

while this plot shows the complex cash flow from all sources,

<img src="https://github.com/mdlacasse/Owl/blob/main/docs/sourcesPlot.png" width="800">

and this one shows the taxable ordinary income over the duration of the plan,
along with extrapolated tax brackets. Notice how the optimized income is surfing
the boundaries of tax brackets.

<img src="https://raw.github.com/mdlacasse/Owl/main/docs/taxIncomePlot.png" width="800">

These plots are irregular because we used historical rates from 1969. The volatility of
the rates offers Roth conversion benefits which are exploited by the optimizer.
The rates used can be displayed by:
```
plan.showRates()
```
<img src="https://raw.github.com/mdlacasse/Owl/main/docs/ratesPlot.png" width="800">

A short text summary of the outcome of the optimization can be displayed through using:
```python
plan.summary()
```
The output of the last command looks like:
```
SUMMARY ======================================================
Plan name: jack & jill - tutorial
        Jack's life horizon: 2024 -> 2051
        Jill's life horizon: 2024 -> 2057
Contributions file: jack+jill.xlsx
Return rates: historical
Rates used: from 1969 to 2002
Optimized for: maxSpending
Solver options: {'maxRothConversion': 150, 'estate': 500}
Solver used: milp
Number of decision variables: 1027
Number of constraints: 982
Spending profile: smile
Survivor percent income: 60%
Net yearly spending in 2024$: $96,005
Total net spending in 2024$: $2,773,329 ($7,827,488 nominal)
Total Roth conversions in 2024$: $464,029 ($992,842 nominal)
Total income tax paid in 2024$: $251,923 ($581,555 nominal)
Assumed heirs tax rate: 30%
Final account post-tax nominal values:
    taxable: $0  tax-def: $0  tax-free: $2,492,067
Total estate value in 2024$: $500,000 ($2,492,067 nominal)
Final inflation factor: 498.4%
--------------------------------------------------------------
```
And an Excel workbook can be saved with all the detailed amounts over the years by using the following command:
```
plan.saveWorkbook('jack+jill-1969')
```

---------------------------------------------------------------
## Requirements

It is assumed that you have some familiarity with using a jupyter notebook or jupyterLab, and some very basic programming skills in Python.
If not, a simple tutorial can guide you to the basic skills needed.

By far, the easiest way to run a Jupiter notebook is to use Google Colab.

- Step 1. Go to [Google Colab](https://colab.research.google.com).
- Step 2. Click on the File-> Open Notebook and drop the ipynb you would like to run.
- Step 3. Then, upload (or drag and drop) all files in this repository (except the docs directory) from your computer to the Colab Notebooks Files panel on the left (opened though the folder icon). You will get a warning that all these files are deleted at the end of the session. This is true!
- Step 4. Run the notebook (Runtime-> Run All).

Alternatively, a better way is to perform an installation of Anaconda on your computer.
This will allow you to run Jupyter notebooks directly on your computer, and save all outputs and modifications to the notebooks. 
It can be found at [anaconda.com](https://anaconda.com).
Follow the instructions in the Jupyter tutorial included (link below) for installing anaconda on your computer.
The Jupyter Notebook interface is a browser-based application for authoring documents that combines live-code with narrative text, equations and visualizations.
Jupyter will run in your default web browser, from your computer to your browser, and therefore no data is ever transferred on the Internet
(your computer, i.e., `localhost`, is the server).

You will also need the capability to read and edit Excel files. One can have an Excel license, or use the LibreOffice free alternative. You can also use Google docs.

The intent of using a notebook is that one can configure calculations that suit one's needs.
Moreover, running calculations in *jupyter* is made to be relatively easy.
There are many tutorials on this topic and a summary including installation procedures is
given [here](https://github.com/mdlacasse/ARP-Lab/blob/main/Jupyter_tutorial.md).

For simulating your own realizations, use the files beginning with the word *template*.
Make a copy and rename them with your own names while keeping the same extension.
Then you'll be able to personalize a case with your own numbers and start experimenting with Owl.
A notebook with detailed explanations on this case can be found [here](https://github.com/mdlacasse/Owl/blob/main/jack+jill.ipynb).

---------------------------------------------------------------------
## Credits
- Historical rates from [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/)
- Image from [freepik](freepik.com)
- Optimization solver from [HiGHS](highs.dev)

---------------------------------------------------------------------

Copyright - Martin-D. Lacasse (2024)

Disclaimers: I am not a financial planner. You make your own decisions. This program comes with no guarantee. Use at your own risk.

--------------------------------------------------------

