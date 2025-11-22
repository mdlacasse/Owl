
# Owl - Optimal Wealth Lab

## A retirement exploration tool based on linear programming

<img align=right src="https://github.com/mdlacasse/Owl/blob/main/docs/images/owl.png?raw=true" width="250">

-------------------------------------------------------------------------------------

### TL;DR
Owl is a retirement financial planning tool that uses a linear programming
optimization algorithm to provide guidance on retirement decisions
such as contributions, withdrawals, Roth conversions, and more.
Users can select varying return rates to perform historical back testing,
stochastic rates for performing Monte Carlo analyses,
or fixed rates either derived from historical averages, or set by the user.

There are three ways to run Owl:

- **Streamlit Hub:** Run Owl remotely as hosted on the Streamlit Community Server at
[owlplanner.streamlit.app](https://owlplanner.streamlit.app).

- **Docker Container:** Run Owl locally on your computer using a Docker image.
Follow these [instructions](docker/README.md) for using this option.

- **Self-hosting:** Run Owl locally on your computer using Python code and libraries.
Follow these [instructions](INSTALL.md) to install from the source code and self-host on your own computer.

-------------------------------------------------------------------------------------
## Overview
This package is a modeling framework for exploring the sensitivity of retirement financial decisions.
Strictly speaking, it is not a planning tool, but more an environment for exploring *what if* scenarios.
It provides different realizations of a financial strategy through the rigorous
mathematical optimization of relevant decision variables. Two major objective goals can be set: either
maximize net spending, or after-tax bequest under various constraints.
Look at the *Capabilities* section below for more detail.

One can certainly have a savings plan, but due to the volatility of financial investments,
it is impossible to have a certain asset earnings plan. This does not mean one cannot make decisions.
These decisions need to be guided with an understanding of the sensitivity of the parameters.
This is exactly where this tool fits in. Given your savings capabilities and spending desires,
it can generate different future realizations of
your strategy under different market assumptions, helping to better understand your financial situation.

-------------------------------------------------------------------------------------
## Purpose and vision
One goal of Owl is to provide a free and open-source ecosystem that has cutting-edge optimization capabilities,
allowing for the next generation of Python-literate retirees to experiment with their own financial future
while providing a codebase where they can learn and contribute. At the same time, an intuitive and easy-to-use
user interface based on Streamlit allows a broad set of users to benefit from the application as it only requires basic financial knowledge.

There are and were
good retirement optimizers in the recent past, but the vast majority of them are either proprietary platforms
collecting your data, or academic papers that share the results without really sharing the details of
the underlying mathematical models.
The algorithms in Owl rely on the open-source HiGHS linear programming solver but they have also been ported and tested on
other platforms such as Mosek and COIN-OR. The complete formulation and
detailed description of the underlying
mathematical model can be found [here](https://github.com/mdlacasse/Owl/blob/main/docs/owl.pdf).

It is anticipated that most end users will use Owl through the graphical interface
either at [owlplanner.streamlit.app](https://owlplanner.streamlit.app)
or [installed](INSTALL.md) on their own computer.
The underlying Python package can also be used directly through Python scripts or Jupyter Notebooks
as described [here](USER_GUIDE.md).

Not every retirement decision strategy can be framed as an easy-to-solve optimization problem.
In particular, if one is interested in comparing different withdrawal strategies,
[FI Calc](https://ficalc.app) is an elegant application that addresses this need.
If, however, you also want to optimize spending, bequest, and Roth conversions, with
an approach also considering Medicare and federal income tax over the next few years,
then Owl is definitely a tool that can help guide your decisions.

--------------------------------------------------------------------------------------
## Capabilities
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
or along a configurable s-curve over the lifespan of the individual.

Spending profiles are adjusted for inflation, and so are all other indexable quantities. Proflies can be
flat or follow a *smile* curve which is also adjustable through three simple parameters.

Available rates are from 1928 to last year and can be used to test historical performance.
Fixed rates can also be provided, as well as *histochastic* rates, which are generated using
the statistical characteristics (means and covariance matrix) of
a selected historical year range. Pure *stochastic* rates can also be generated
if the user provides means, volatility (expressed as standard deviation), and optionally
the correlations between the different assets return rates provided as a matrix, or a list of
the off-diagonal elements (see documentation for details).
Average rates calculated over a historical data period can also be chosen.

Monte Carlo simulations capabilities are included and provide a probability of success and a histogram of
outcomes. These simulations can be used for either determining the probability distribution of the
maximum net spending amount under
the constraint of a desired bequest, or the probability distribution of the maximum
bequest under the constraint of a desired net spending amount. Unlike discrete-event
simulators, Owl uses an optimization algorithm for every new scenario, which results in more
calculations being performed. As a result, the number of cases to be considered should be kept
to a reasonable number. For a few hundred cases, a few minutes of calculations can provide very good estimates
and reliable probability distributions.

Optimizing each solution is more representative than event-base simulators
in the sense that optimal solutions
will naturally adjust to the return scenarios being considered.
This is more realistic as retirees would certainly re-evaluate
their expectations under severe market drops or gains.
This optimal approach provides a net benefit over event-based simulators,
which maintain a distribution strategy either fixed, or within guardrails for capturing the
retirees' reactions to the market.

Basic input parameters can be entered through the user interface
while optional additional time series can be read from
an Excel spreadsheet that contains future wages, contributions
to savings accounts, and planned *big-ticket items* such as the purchase of a lake house,
the sale of a boat, large gifts, or inheritance.

Three types of savings accounts are considered: taxable, tax-deferred, and tax-free,
which are all tracked separately for married individuals. Asset transition to the surviving spouse
is done according to beneficiary fractions for each type of savings account.
Tax status covers married filing jointly and single, depending on the number of individuals reported.

Maturation rules for Roth contributions and conversions are implemented as constraints
limiting withdrawal amounts to cover Roth account balances for 5 years after the events.
Medicare and IRMAA calculations are performed through a self-consistent loop on cash flow constraints.
They can also be optimized explicitly as an option, but this choice can lead to longer calculations
due to the use of the many additional binary variables required by the formulation.
Future Medicare and IRMAA values are simple projections of current values with the assumed inflation rates.

### Limitations
Owl is work in progress. At the current time:
- Only the US federal income tax is considered (and minimized through the optimization algorithm).
Head of household filing status has not been added but can easily be.
- Required minimum distributions are calculated, but tables for spouses more than 10 years apart are not included.
These cases are detected and will generate an error message.
- Social security rule for surviving spouse assumes that benefits were taken at full retirement age.
- Current version has no optimization of asset allocations between individuals and/or types of savings accounts.
If there is interest, that could be added in the future.
- In the current implementation, social securiy is always taxed at 85%, assuming that your taxable income will be larger than 34 k$ (single) or 44 k$ (married filing jointly).
- When Medicare calculations are done through a self-consistent loop,
the Medicare premiums are calculated after an initial solution is generated,
and then a new solution is re-generated with these premiums as a constraint.
In some situations, when the income (MAGI) is near an IRMAA bracket, oscillatory solutions can arise.
While the solutions generated are very close to one another, Owl will pick the smallest solution
for being conservative. While sometimes computationally costly,
a comparison with a full Medicare optimization should always be performed.
- Part D is not included in the IRMAA calculations. Only Part B is taken into account, 
which is considerably more significant.
- Future tax brackets are pure speculations derived from the little we know now and projected to the next 30 years.
Your guesses are as good as mine.

The solution from an optimization algorithm has only two states: feasible and infeasible.
Therefore, unlike event-driven simulators that can tell you that your distribution strategy runs
out of money in year 20, an optimization-based solver can only tell you that a solution does or does not
exist for the plan being considered. Examples of infeasible solutions include requesting a bequeathed
estate value too large for the savings assets to support, even with zero net spending basis,
or maximizing the bequest subject to a net spending basis that is already too large for the savings
assets to support, even with no estate being left.

---------------------------------------------------------------
## Documentation

- Documentation for the app user interface is available from the interface [itself](https://owlplanner.streamlit.app/Documentation).
- Installation guide and software requirements can be found [here](INSTALL.md).
- User guide for the underlying Python package as used in a Jupyter notebook can be found [here](USER_GUIDE.md).

---------------------------------------------------------------------

## Credits
- Historical rates from [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/)
- Image from [freepik](https://freepik.com)
- Optimization solver from [HiGHS](https://highs.dev)
- Streamlit Community Cloud [Streamlit](https://streamlit.io)
- Contributors: Josh (noimjosh@gmail.com) for Docker image code,
 kg333 for fixing an error in Docker's instructions,
 Dale Seng (sengsational) for great insights and suggestions,
 Robert E. Anderson (NH-RedAnt) for bug fixes and suggestions,
 Clark Jefcoat (hubcity) for fruitful interactions,
 Benjamin Quinn (blquinn) and Gene Wood (gene1wood) for improvements and bug fixes.

---------------------------------------------------------------------

Copyright &copy; 2024 - Martin-D. Lacasse

Disclaimers: This code is for educatonal purposes only and does not constitute financial advice.

Code output has been verified with analytical solutions when applicable, and comparative approaches otherwise.
Nevertheless, accuracy of results is not guaranteed.

--------------------------------------------------------

