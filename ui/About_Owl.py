import streamlit as st

st.write("## About Owl 🦉")

st.write('This version of Owl was released in December 2024.')
st.write('Running on Streamlit %s.' % st.__version__)

st.write('''
- This code was released under GPL Licence through a publicly available
repository on [github](github.com/mdlacasse/owl).

- This code does not store or forward any information. It fully respects you privacy.
All source code is provided and can be inspected in the repository.

- Mathematical formulation of the linear optimization problem can be
found in a PDF document [here](https://raw.github.com/mdlacasse/Owl/main/docs/owl.pdf).

Copyright &copy; 2024 - Martin-D. Lacasse

---------------------------------------------------------------------
#### :orange[Credits]
- Historical rates are from [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/)
- Owl image is from [freepik](freepik.com)
- Optimization solver is from [HiGHS](highs.dev)
- Owl relies on the following [Python](python.org) packages: [Numpy](numpy.org), [Matplotlib](matplotlib.org),
  [Pandas](pandas.pydata.org), [Seaborn](seaborn.pydata.org), [Streamlit](streamlit.io).


#### :orange[Disclaimers]
- I am not a financial planner.
- You make your own decisions.
- This program comes with no guarantee.
- Use at your own risk.
''')
