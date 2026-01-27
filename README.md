
# Owl - Optimal Wealth Lab

## A retirement exploration tool based on linear programming

<img align="right" src="papers/images/owl.png" width="250">

-------------------------------------------------------------------------------------

### TL;DR
Owl is a retirement financial planning tool that uses a linear programming
optimization algorithm to provide guidance on retirement decisions
such as contributions, withdrawals, Roth conversions, and more.
Users can select varying return rates to perform historical back testing,
stochastic rates for performing Monte Carlo analyses,
or fixed rates either derived from historical averages, or set by the user.

Owl is designed for US retirees as it considers US federal tax laws,
Medicare premiums, rules for 401k including required minimum distributions,
maturation rules for Roth accounts and conversions, social security rules, etc.

There are three ways to run Owl:

- **Streamlit Hub:** Run Owl remotely as hosted on the Streamlit Community Server at
[owlplanner.streamlit.app](https://owlplanner.streamlit.app).

- **Docker Container:** Run Owl locally on your computer using a Docker image.
Follow these [instructions](docker/README.md) for using this option.

- **Self-hosting:** Run Owl locally on your computer using Python code and libraries.
Follow these [instructions](INSTALL.md) to install from the source code and self-host on your own computer.


---------------------------------------------------------------
## Documentation

- Documentation for the app user interface is available from the interface [itself](https://owlplanner.streamlit.app/Documentation).
- Installation guide and software requirements can be found [here](INSTALL.md).
- User guide for the underlying Python package as used in a Jupyter notebook can be found [here](USER_GUIDE.md).

---------------------------------------------------------------------

## Credits
- Contributors:
 Robert E. Anderson (NH-RedAnt) for bug fixes and suggestions,
 Clark Jefcoat (hubcity) for fruitful interactions,
 kg333 for fixing an error in Docker's instructions,
 John Leonard (jleonard99) for great suggestions, website, and more to come,
 Benjamin Quinn (blquinn) for improvements and bug fixes,
 Dale Seng (sengsational) for great insights, testing, and suggestions,
 Josh Williams (noimjosh) for Docker image code,
 Gene Wood (gene1wood) for improvements and bug fixes.
- Greg Grothaus for developing [ssa.tools](https://ssa.tools) and providing an integration with Owl.
- Owl image is from [freepik](https://freepik.com).
- Historical rates are from [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/).
- Linear programming optimization solvers are from
[HiGHS](https://highs.dev) and [PuLP](https://coin-or.github.io/pulp/).
It can also run on [MOSEK](https://mosek.com) if available on your computer.
- Owl planner relies on the following [Python](https://python.org) packages:
    - [highspy](https://highs.dev),
    [loguru](https://github.com/Delgan/loguru),
    [Matplotlib](https://matplotlib.org),
    [Numpy](https://numpy.org),
    [odfpy](https://https://pypi.org/project/odfpy),
    [openpyxl](https://openpyxl.readthedocs.io),
    [Pandas](https://pandas.pydata.org),
    [Plotly](https://plotly.com),
    [PuLP](https://coin-or.github.io/pulp),
    [Scipy](https://scipy.org),
    [Seaborn](https://seaborn.pydata.org),
    [toml](https://toml.io),
 and [Streamlit](https://streamlit.io) for the front-end.

## Bugs and Feature Requests
Please submit bugs and feature requests through
[GitHub](https://github.com/mdlacasse/owl/issues) if you have a GitHub account
or directly by [email](mailto:martin.d.lacasse@gmail.com).
Or just drop me a line to report your experience with the tool.

## Privacy
This app does not store or forward any information. All data entered is lost
after a session is closed. However, you can choose to download selected parts of your
own data to your computer before closing the session. These data will be stored strictly on
your computer and can be used to reproduce a case at a later time.

---------------------------------------------------------------------

Copyright &copy; 2024-2026 - Martin-D. Lacasse

Disclaimers: This code is for educatonal purposes only and does not constitute financial advice.

Code output has been verified with analytical solutions when applicable, and comparative approaches otherwise.
Nevertheless, accuracy of results is not guaranteed.

--------------------------------------------------------

