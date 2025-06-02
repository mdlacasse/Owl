# Owl

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png" width="250">

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
plan = owl.Plan(['Jack', 'Jill'], [1962, 1965], [89, 92], 'jack & jill - tutorial', startDate='01-01')
# Jack has $90.5k in a taxable investment account, $600.5k in a tax-deferred account and $70k from 2 tax-free accounts.
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
The summary also contains some details:
```
SUMMARY ================================================================
Net yearly spending basis in 2025$: $91,812
Net yearly spending for year 2025: $100,448
Net spending remaining in year 2025: $100,448
Total net spending in 2025$: $2,809,453 ($7,757,092 nominal)
Total Roth conversions in 2025$: $320,639 ($456,454 nominal)
Total income tax paid on ordinary income in 2025$: $247,788 ($469,522 nominal)
Total tax paid on gains and dividends in 2025$: $3,313 ($3,768 nominal)
Total Medicare premiums paid in 2025$: $117,660 ($343,388 nominal)
Spousal wealth transfer from Jack to Jill in year 2051 (nominal): taxable: $0  tax-def: $57,224  tax-free: $2,102,173
Sum of spousal bequests to Jill in year 2051 in 2025$: $499,341 ($2,159,397 nominal)
Post-tax non-spousal bequests from Jack in year 2051 (nominal): taxable: $0  tax-def: $0  tax-free: $0
Sum of post-tax non-spousal bequests from Jack in year 2051 in 2025$: $0 ($0 nominal)
Post-tax account values at the end of final plan year 2057 (nominal): taxable: $0  tax-def: $0  tax-free: $2,488,808
Total estate value at the end of final plan year 2057 in 2025$: $500,000 ($2,488,808 nominal)
Plan starting date: 01-01
Cumulative inflation factor from start date to end of plan: 4.98
        Jack's 27-year life horizon: 2025 -> 2051
        Jill's 33-year life horizon: 2025 -> 2057
Plan name: jack & jill - tutorial
Number of decision variables: 996
Number of constraints: 867
Case executed on: 2025-02-04 at 22:55:03

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

<img src="https://raw.github.com/mdlacasse/Owl/main/docs/images/OwlUI.png" width="100%">

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

