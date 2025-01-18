import streamlit as st

import sskeys as kz
import owlbridge as owb


st.write("## About Owl 🦉")
kz.orangeDivider()

st.write('This version of Owl was released in January 2025 (version %s).' % owb.version())
st.write('Running on Streamlit %s.' % st.__version__)
st.snow()

st.write('''
- This code was released under GPL Licence through a publicly available
repository on [github](https://github.com/mdlacasse/owl).

- This code does not store or forward any information. It fully respects privacy.
All source code is provided and can be inspected in the repository.

- Mathematical formulation of the linear optimization problem can be
found [here](https://raw.github.com/mdlacasse/Owl/main/docs/owl.pdf).

Copyright &copy; 2024 - Martin-D. Lacasse

---------------------------------------------------------------------
#### :orange[Credits]
- Historical rates are from [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/).
- Owl image is from [freepik](https://freepik.com).
- Optimization solver is from [HiGHS](https://highs.dev).
- Owl planner relies on the following [Python](https://python.org) packages:
    - [Numpy](https://numpy.org), [Matplotlib](https://matplotlib.org),
    [Pandas](https://pandas.pydata.org),
    [Seaborn](https://seaborn.pydata.org),
    [Scipy](https://scipy.org),
    [openpyxl](https://openpyxl.readthedocs.io),
    [toml](https://toml.io),
 and [Streamlit](https://streamlit.io) for the front-end.
- The :streamlit: [Streamlit Community Cloud](https://streamlit.io/cloud) for hosting.

#### :orange[Disclaimers]
- I am not a financial planner.
- You make your own decisions.
- This program comes with no guarantee.
- Use at your own risk.
''')
