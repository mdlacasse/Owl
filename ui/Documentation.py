import streamlit as st


col1, col2, col3, col4 = st.columns(4)
with col4:
    st.image("../docs/images/owl.jpg")

st.write('## Owl Retirement Planner')
st.markdown('''
#### A retirement exploration tool based on linear programming

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

--------------------------------------------------------------------------------------
#### Basic capabilities
Owl can optimize for either maximum net spending under the constraint of a given bequest (which can be zero),
or maximize the after-tax value of a bequest under the constraint of a desired net spending profile,
and under the assumption of a heirs marginal tax rate.
Roth conversions are also considered, subject to an optional maximum conversion amount,
and optimized to suit the goals of the selected objective function.
All calculations are indexed for inflation, which is provided as a fixed rate,
or through historical values, as are all other rates used for the calculations.
These rates can be used for backtesting different scenarios by choosing
*historical* rates, or by choosing *average* rates over a historical year range,
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
to a reasonable number. For a few hundred cases, a few minutes of calculations
can provide very good estimates and reliable probability distributions.
Optimizing each solution is more representative in the sense that optimal solutions
will naturally adjust to the return scenarios being considered.
This is more realistic as retirees would certainly re-evaluate
their expectations under severe market drops or gains.
This optimal approach provides a net benefit over event-based simulations,
which maintain a distribution strategy either fixed,
or within guardrails for capturing the retirees' reactions to the market.

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

#### Limitations
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


See tutorial notebooks [1](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_1.ipynb),
[2](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_2.ipynb), and
[3](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_3.ipynb) for more info.


For simulating your own realizations, use the files beginning with the word *template*.
Make a copy and rename them with your own names while keeping the same extension.
Then you'll be able to personalize a case with your own numbers and start experimenting with Owl.
Notebooks with detailed explanations can be found in
[tutorial_1](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_1.ipynb),
[tutorial_2](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_1.ipynb), and
[tutorial_3](https://github.com/mdlacasse/Owl/blob/main/examples/tutorial_2.ipynb).

'''
)
