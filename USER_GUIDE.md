# Owl - Optimal Wealth Lab

## A retirement exploration tool based on linear programming

<img align=right src="https://github.com/mdlacasse/Owl/blob/main/docs/images/owl.png?raw=true" width="250">

------------------------------------------------------------------------------------
### About
This document describes the underlying Owl package and how to use it within
Python scripts or in Jupyter notebooks.

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
plan = owl.Plan(['Jack', 'Jill'], ["1963-01-15", "1966-01-15"], [89, 92], 'jack & jill - tutorial')
# On January 1st, Jack has $90.5k in a taxable investment account,
# $600.5k in a tax-deferred account and $70k from 2 tax-free accounts.
# Jill has $60.2k in her taxable account, $150k in a 403b, and $40k in a Roth IRA.
plan.setAccountBalances(taxable=[90.5, 60.2], taxDeferred=[600.5, 150], taxFree=[50.6 + 20, 40.8], startDate="01-01")
t An Excel file contains 2 tabs (one for Jill, one for Jack) describing anticipated wages and contributions.
plan.readContributions('examples/HFP_jack+jill.xlsx')
# Jack will glide an s-curve for asset allocations from a 60/40 -> 70/30  stocks/bonds portfolio.
# Jill will do the same thing but is a bit more conservative from 50/50 -> 70/30 stocks/bonds portfolio.
plan.setInterpolationMethod('s-curve')
plan.setAllocationRatios('individual', generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]])
# Jack has no pension, but Jill will receive $10k per year at 65 yo.
plan.setPension([0, 10.5], [65, 65])
# Jack anticipates receiving social security at age 70 and has a monthly Primary Insurance Amount of $2,360,
# while Jill will claim at age 62 with a PIA of $1,642. All values are in today's $.
plan.setSocialSecurity([2360, 1642], [70, 62.083])
# Instead of a 'flat' profile, we select a 'smile' spending profile, with 60% needs for the survivor.
plan.setSpendingProfile('smile', 60)
# We will reproduce the historical sequence of returns starting in year 1969.
plan.setRates('historical', 1969)
# Jack and Jill want to leave a bequest of $400k, and limit Roth conversions to $100k per year.
# Jill's 403b plan does not support in-plan Roth conversions.
# We solve for the maximum net spending profile under these constraints.
plan.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 400, 'noRothConversions': 'Jill'})
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
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/taxIncomePlot.png?raw=true" width="75%">

The optimal spending profile is shown in the next plot (in today's dollars). Notice the drop
(recall we selected 60% survivor needs) at the passing of the first spouse.
```python
plan.showProfile('today')
```

<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/spendingPlot.png?raw=true" width="75%">

The following plot shows the account balances in nominal value for all savings accounts owned by Jack and Jill.
It was generated using
```python
plan.showAccounts(value='nominal')
```
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/savingsPlot.png?raw=true" width="75%">

while this plot shows the complex cash flow from all sources, which was generated with
```python
plan.showSources(value='nominal')
```
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/sourcesPlot.png?raw=true" width="75%">

For taxes, the following call will display Medicare premiums (including Part B IRMAA fees) and federal income tax
```python
plan.showTaxes(value='nominal')
```
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/taxesPlot.png?raw=true" width="75%">

For the case at hand, recall that asset allocations were selected above through

```python
plan.setAllocationRatios('individual', generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]])
```
gliding from a 60%/40% stocks/bonds portfolio to 70%/30% for Jack, and 50%/50% -> 70%/30% for Jill.
Assets distribution in all accounts in today's $ over time can be displayed from
```python
plan.showAssetDistribution(value='today')
```
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/AD-taxable.png?raw=true" width="75%">
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/AD-taxDef.png?raw=true" width="75%">
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/AD-taxFree.png?raw=true" width="75%">

These plots are irregular because we used historical rates from 1969. The volatility of
the rates offers Roth conversion benefits which are exploited by the optimizer.
The rates used can be displayed by:
```python
plan.showRates()
```
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/ratesPlot.png?raw=true" width="75%">

Values between brackets <> are the average values and volatility over the selected period. 

For the statisticians, rates distributions and correlations between them can be shown using:
```python
plan.showRatesCorrelations()
```
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/ratesCorrelations.png?raw=true" width="75%">

A short text summary of the outcome of the optimization can be displayed through using:
```python
print(plan.summarySting())
```
The output of the last command reports that if future rates are exactly like those observed
starting from 1969 and the following years, Jack and Jill could afford an annual spending of
 \\$97k starting this year
(with a basis of \\$88.8k - the basis multiplies the profile which can vary over the course of the plan).
The summary also contains some details:
```
Synopsis
                                                                    Case name: jack & jill - tutorial
Net yearly spending basis . . . . . . . . . . . . . . . . . . . . . . . . . .: $90,333
                                                   Net spending for year 2026: $98,830
                                          Net spending remaining in year 2026: $98,830
                                                           Total net spending: $2,764,191
                                                         [Total net spending]: $7,632,120
                                                       Total Roth conversions: $342,708
                                                     [Total Roth conversions]: $448,854
                                            Total tax paid on ordinary income: $215,128
                                          [Total tax paid on ordinary income]: $433,372
                                               »  Subtotal in tax bracket 10%: $75,360
                                              » [Subtotal in tax bracket 10%]: $204,198
                                            »  Subtotal in tax bracket 12/15%: $107,740
                                           » [Subtotal in tax bracket 12/15%]: $195,020
                                            »  Subtotal in tax bracket 22/25%: $32,028
                                           » [Subtotal in tax bracket 22/25%]: $34,154
                                            »  Subtotal in tax bracket 24/28%: $0
                                           » [Subtotal in tax bracket 24/28%]: $0
                                            »  Subtotal in tax bracket 32/33%: $0
                                           » [Subtotal in tax bracket 32/33%]: $0
                                               »  Subtotal in tax bracket 35%: $0
                                              » [Subtotal in tax bracket 35%]: $0
                                            »  Subtotal in tax bracket 37/40%: $0
                                           » [Subtotal in tax bracket 37/40%]: $0
                                      »  Subtotal in early withdrawal penalty: $0
                                     » [Subtotal in early withdrawal penalty]: $0
                                        Total tax paid on gains and dividends: $0
                                      [Total tax paid on gains and dividends]: $0
                                         Total net investment income tax paid: $0
                                       [Total net investment income tax paid]: $0
                                                 Total Medicare premiums paid: $129,044
                                               [Total Medicare premiums paid]: $376,613
                                                      Year of partial bequest: 2052
                                              Sum of spousal transfer to Jill: $385,601
                                            [Sum of spousal transfer to Jill]: $1,667,527
                                        »  Spousal transfer to Jill - taxable: $0
                                       » [Spousal transfer to Jill - taxable]: $0
                                        »  Spousal transfer to Jill - tax-def: $20,279
                                       » [Spousal transfer to Jill - tax-def]: $87,695
                                       »  Spousal transfer to Jill - tax-free: $365,322
                                      » [Spousal transfer to Jill - tax-free]: $1,579,832
                                Sum of post-tax non-spousal bequest from Jack: $0
                              [Sum of post-tax non-spousal bequest from Jack]: $0
                          »  Post-tax non-spousal bequest from Jack - taxable: $0
                         » [Post-tax non-spousal bequest from Jack - taxable]: $0
                          »  Post-tax non-spousal bequest from Jack - tax-def: $0
                         » [Post-tax non-spousal bequest from Jack - tax-def]: $0
                         »  Post-tax non-spousal bequest from Jack - tax-free: $0
                        » [Post-tax non-spousal bequest from Jack - tax-free]: $0
                                                        Year of final bequest: 2058
                                       Total after-tax value of final bequest: $400,000
                                          » After-tax value of savings assets: $400,000
                                     » Fixed assets liquidated at end of plan: $0
                                       » With heirs assuming tax liability of: $0
                                            » After paying remaining debts of: $0
                                     [Total after-tax value of final bequest]: $1,991,047
                                        [» After-tax value of savings assets]: $1,991,047
                                   [» Fixed assets liquidated at end of plan]: $0
                                      [» With heirs assuming tax liability of: $0
                                          [» After paying remaining debts of]: $0
                            »  Post-tax final bequest account value - taxable: $0
                           » [Post-tax final bequest account value - taxable]: $0
                            »  Post-tax final bequest account value - tax-def: $0
                           » [Post-tax final bequest account value - tax-def]: $0
                           »  Post-tax final bequest account value - tax-free: $400,000
                          » [Post-tax final bequest account value - tax-free]: $1,991,047
                                                           Case starting date: 01-01
                             Cumulative inflation factor at end of final year: 4.98
                                                          Jack's life horizon: 2026 -> 2052
                                                         Jack's years planned: 27
                                                          Jill's life horizon: 2026 -> 2058
                                                         Jill's years planned: 33
                                                 Number of decision variables: 1029
                                                        Number of constraints: 911
                                                                  Convergence: monotonic
                                                             Case executed on: 2026-01-26 at 23:25:47
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
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/MC-tutorial2a.png?raw=true" width="75%">

Similarly, the next one was generated using
```
plan.runMC('maxBequest', ...)
```
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/MC-tutorial2b.png?raw=true" width="75%">


See tutorial notebooks [1](https://github.com/mdlacasse/Owl/blob/main/notebooks/tutorial_1.ipynb),
[2](https://github.com/mdlacasse/Owl/blob/main/notebooks/tutorial_2.ipynb), and
[3](https://github.com/mdlacasse/Owl/blob/main/notebooks/tutorial_3.ipynb) for more info.


---------------------------------------------------------------
## Requirements

Owl relies on common Python modules such as NumPy, Pandas, SciPy, matplotlib, and Seaborn.
The user front-end was built on Streamlit.
Package `odfpy` might be required if one read files created by LibreOffice. These dependencies
will be installed by pip using the installation guide [here](INSTALL.md)..

The simplest way to get started with Owl is to use the `streamlit` browser-based user interface
that is started by the `owlplanner.cmd` script, which  will start a user interface on your own browser.
Here is a screenshot of one of the multiple tabs of the interface:

<img src="https://github.com/mdlacasse/Owl/blob/main/docs/images/OwlUI.png?raw=true" width="100%">

Alternatively, one can prefer using Owl from Jupyter notebooks. For that purpose, the `examples` directory
contains many files as a tutorial. The Jupyter Notebook interface is a browser-based application
for authoring documents that combines live-code with narrative text, equations and visualizations.
Jupyter will run in your default web browser, from your computer to your browser,
and therefore no data is ever transferred on the Internet (your computer, i.e., `localhost`, is the server).

For simulating your own realizations, use the files beginning with the word *template*.
Make a copy and rename them with your own names while keeping the same extension.
Then you'll be able to personalize a case with your own numbers and start experimenting with Owl.
Notebooks with detailed explanations can be found in
[tutorial_1](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_1.ipynb),
[tutorial_2](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_1.ipynb), and
[tutorial_3](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_2.ipynb).

Finally, you will also need the capability to read and edit Excel files.
One can have an Excel license, or use the LibreOffice free alternative. You can also use Google docs.

---------------------------------------------------------------------

Copyright &copy; 2024 - Martin-D. Lacasse

Disclaimers: I am not a financial planner. You make your own decisions.
This program comes with no guarantee. Use at your own risk.

--------------------------------------------------------

