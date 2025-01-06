import streamlit as st

st.write("## About Owl 🦉")

st.write('This version of Owl was released in January 2025.')
st.write('Running on Streamlit %s.' % st.__version__)
st.snow()

st.write('''
- This code was released under GPL Licence through a publicly available
repository on [github](https://github.com/mdlacasse/owl).

- This code does not store or forward any information. It fully respects you privacy.
All source code is provided and can be inspected in the repository.

- Mathematical formulation of the linear optimization problem can be
found in a PDF document [here](https://raw.github.com/mdlacasse/Owl/main/docs/owl.pdf).

Copyright &copy; 2024 - Martin-D. Lacasse

---------------------------------------------------------------------
#### :orange[Credits]
- Historical rates are from [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/).
- Owl image is from [freepik](https://freepik.com).
- Optimization solver is from [HiGHS](https://highs.dev).
- Owl planner relies on the following [Python](https://python.org) packages:
    - [Numpy](https://numpy.org), [Matplotlib](https://matplotlib.org),
    [Pandas](https://pandas.pydata.org),
    [Seaborn](https://seaborn.pydata.org), and [Streamlit](https://streamlit.io) for the front-end.


#### :orange[Disclaimers]
- I am not a financial planner.
- You make your own decisions.
- This program comes with no guarantee.
- Use at your own risk.
''')
