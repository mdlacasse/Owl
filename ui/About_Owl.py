import streamlit as st

import sskeys as kz
import owlbridge as owb


st.write("# :material/info: About Owl - Optimal Wealth Lab🦉")
kz.divider("orange")

st.write(f"This is Owl version {owb.version()} running on Streamlit {st.__version__}.")
# st.balloons()

st.write(
    """
- Owl is an open-source retirement financial planner capable of optimization through linear programming.
- Source code is available from a repository on [GitHub](https://github.com/mdlacasse/owl).
- Mathematical formulation of the linear optimization problem can be
found in this [document](https://github.com/mdlacasse/Owl/blob/main/papers/owl.pdf?raw=true).

Copyright &copy; 2025 - Martin-D. Lacasse

#### :orange[Credits]
- Contributors:
 Robert E. Anderson (NH-RedAnt) for bug fixes and suggestions,
 Clark Jefcoat (hubcity) for fruitful interactions,
 kg333 for fixing an error in Docker's instructions,
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

#### :orange[Bugs and Feature Requests]
Please submit bugs and feature requests through
[GitHub](https://github.com/mdlacasse/owl/issues) if you have a GitHub account
or directly by [email](mailto:martin.d.lacasse@gmail.com).
Or just drop me a line to report your experience with the tool. &#x1F44D;

#### :orange[Privacy]
This app does not store or forward any information. All data entered is lost
after a session is closed. However, you can choose to download selected parts of your
own data to your computer before closing the session. These data will be stored strictly on
your computer and can be used to reproduce a case at a later time.

#### :orange[License]
This software is released under the
[Gnu General Public License v3](https://www.gnu.org/licenses/gpl-3.0.html#license-text).

#### :orange[Disclaimer]
This program is for educatonal purposes only and does not constitute financial advice.

"""
)
