import streamlit as st

import sskeys as kz
import owlbridge as owb


st.write("# About Owl 🦉")
kz.divider("orange")

st.write(f"This is Owl version {owb.version()} running on Streamlit {st.__version__}.")
# st.balloons()

st.write(
    """
- Owl is released under GPL Licence through a publicly available
repository on [GitHub](https://github.com/mdlacasse/owl).

- Mathematical formulation of the linear optimization problem can be
found [here](https://raw.github.com/mdlacasse/Owl/main/docs/owl.pdf).

Copyright &copy; 2024 - Martin-D. Lacasse

#### :orange[Credits]
- Historical rates are from [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/).
- Linear programming optimization solver is from [HiGHS](https://highs.dev).
- Owl planner relies on the following [Python](https://python.org) packages:
    - [Matplotlib](https://matplotlib.org),
    [Numpy](https://numpy.org),
    [odfpy](https://https://pypi.org/project/odfpy),
    [openpyxl](https://openpyxl.readthedocs.io),
    [Pandas](https://pandas.pydata.org),
    [Scipy](https://scipy.org),
    [Seaborn](https://seaborn.pydata.org),
    [toml](https://toml.io),
 and [Streamlit](https://streamlit.io) for the front-end.
- Contributors: Josh Williams (noimjosh) for Docker image code,
 Dale Seng (sengsational) for great insights and suggestions,
 Robert E. Anderson (NH-RedAnt) for bug fixes and suggestions.
- Owl image is from [freepik](https://freepik.com).

#### :orange[Bugs and Feature Requests]
- Please submit bugs and feature requests through
[GitHub](https://github.com/mdlacasse/owl/issues) if you have a GitHub account
or directly by [email](mailto://martin.d.lacasse@gmail.com).

#### :orange[Privacy]
- This app does not store or forward any information. All data entered is lost
after a session is closed. You can choose to download selected parts of your
own data to your computer before closing the session.

#### :orange[Disclaimer]
- This program is provided for educational purposes and comes with no guarantee. Use at your own risk.
"""
)
