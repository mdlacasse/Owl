
# Owl   

## A retirement exploration tool based on linear programming

<img align=right src="https://github.com/mdlacasse/Owl/blob/main/docs/owl.jpg" width="250">


This package is a retirement modeling framework for exploring the sensitivity of retirement financial decisions.
Strictly speaking, it is not a planning tool, but more an environment for exploring what if scenarios.
It provides different realizations of a financial strategy. One can certainly have a savings plan, but due to the volatility of financial investments,
it is impossible to have a certain asset earnings plan. This does not mean one cannot make decisions.
These decisions need to be guided with an understanding of the sensitivity of the parameters.
This is exactly where this tool fits it. Given your savings and spending desires, it can generate different future realizations of
your strategy under different market assumptions, helping to better understand your financial situation.

The algorithm in Owl is using the open-source HIGHS linear programming solver. The complete formulation and
detailed description of the undelying
mathematical model can be found [here](https://github.com/mdlacasse/Owl/tree/main/docs/lp.pdf).

Copyright - Martin-D. Lacasse (2024)

Disclaimers: I am not a financial planner. You make your own decisions. This program comes with no guarantee. Use at your own risk.

-------------------------------------------------------------------------------------
## Requirements

It is assumed that you have some familiarity with using a jupyter notebook or jupyterLab, and some very basic programming skills in Python.
If not, a simple tutorial can guide you to the basic skills needed.

By far, the easiest way to run a Jupiter notebook is to use Google Colab.

- Step 1. Go to [Google Colab](https://colab.research.google.com).
- Step 2. Click on the File-> Open Notebook and drop the ipynb you would like to run.
- Step 3. Then, upload (or drag and drop) all files in this repository (except the docs directory) from your computer to the Colab Notebooks Files panel on the left (opened though the folder icon). You will get a warning that all these files are deleted at the end of the session. This is true!
- Step 4. Run the notebook (Runtime-> Run All)

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

For simulating your own realizations, use the files beginning with template.
Make a copy and rename them with your own names while keeping the same extension.
Then you'll be able to personalize a case with your own numbers and start experimenting with Owl.

## Basic capabilities
Owl can optimize for either maximum net income under the constraint of a given bequest, or maximize the
bequest under the constraint of a desired net income profile. Roth conversions are also considered
and optimized under the assumption of a heirs marginal tax rate and subject to an optional maximum
conversion amount. All calculations are indexed for inflation, which is provided as a fixed rate,
or through historical values, as are all other rates used for the calculations.

Current version has no optimization of asset allocation ratios between savings accounts.
If there is interest,
that could be added in the future. Also, only US federal income tax is considered.

## Let's explore Owl's functionality through a specific example
With about 10 lines of code, one can generate a full case study.
Here is a typical plan without comments:
```python
import owl
owl.setVerbose(True)
plan = owl.Plan([1962, 1965], [89, 92], 'jack & jill - tutorial')
plan.setAccountBalances(taxable=[90, 60], taxDeferred=[600, 150], taxFree=[50 + 20, 40])
plan.readContributions('jack+jill.xlsx')
plan.setInterpolationMethod('s-curve')
plan.setAllocationRatios('individual', generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]])
plan.setPension([0, 10], [65, 65])
plan.setSocialSecurity([28, 25], [70, 70])
plan.setSpendingProfile('smile')
plan.setRates('historical', 1969)
plan.solve('maxIncome', options={'maxRothConversion': 100, 'estate': 500})
```
Dollar amounts are in k\$ and ratios in percentage.
The output can be seen using the following commands that display plots of the various variables in time.
```python
plan.showNetIncome()
plan.showGrossIncome()
plan.showTaxes()
plan.showSources()
plan.showAccounts()
```
Typical plots look like the following. This plot shows the account balances in all savings accounts owned by Jack and Jill,

<img src="https://github.com/mdlacasse/Owl/blob/main/docs/savingsPlot.png" width="800">

while this plot shows the cash flow from all sources.

<img src="https://github.com/mdlacasse/Owl/blob/main/docs/sourcesPlot.png" width="800">

These plots are irregular because we used historical rates from 1969. These rates can be displayed by:
```
plan.showRates()
```
<img src="https://github.com/mdlacasse/Owl/blob/main/docs/ratesPlot.png" width="800">

A short text summary of the outcome of the optimization can be displayed through using:
```python
plan.summary()
```
The output of the last command looks like:
```
SUMMARY ======================================================
Plan name: jack & jill - tutorial
Individuals: Jack Jill
Contribution file: jack+jill.xlsx
Return rates: historical
Optimized for: maxIncome
Solver options: {'maxRothConversion': 100, 'estate': 500}
Spending profile: smile
Net yearly income in 2024$: $99,687
Total net income in 2024$: $2,879,706 ($8,127,728 nominal)
Total income tax paid in 2024$: $300,653 ($476,166 nominal)
Assumed heirs tax rate: 30%
Final account post-tax nominal values: $0 $0 $500,000
Final estate value in 2024$: $100,318 ($500,000 nominal)
--------------------------------------------------------------
```
And an Excel workbook can be saved with all the amounts over the years by using the following command:
```
plan.saveInstance('jack+jill-1969', True)
```
A notebook with detailed explanations on this case can be found [here](https://github.com/mdlacasse/Owl/blob/main/jack+jill.ipynb).



