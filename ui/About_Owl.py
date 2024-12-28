import streamlit as st

import sskeys as k

ret = k.titleBar('MC')
st.write("## About Owl 🦉")

st.write('#### This version of Owl was release in December 2024.')

st.divider()
st.write('''
#### Credits
- Historical rates from [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/)
- Image from [freepik](freepik.com)
- Optimization solver from [HiGHS](highs.dev)
- Owl relies on the following packages: [Numpy](numpy.org), [Matplotlib](matplotlib.org),
  [Pandas](pandas.pydata.org), [Seaborn](seaborn.pydata.org), [Streamlit](streamlit.io).

---------------------------------------------------------------------
Copyright &copy; 2024 - Martin-D. Lacasse

- This code was released under GPL Licence in a publicly available
github [repository](github.com/mdlacasse/owl) 

- This code does not store or forward any information. It fully respects you privacy.
All code is provided and can be inspected in repository.

- Mathematical formulation of linear optimization problem can be
found in a PDF document [here](https://raw.github.com/mdlacasse/Owl/main/docs/owl.pdf).

---------------------------------------------------------------------

#### Disclaimers:
- I am not a financial planner.
- You make your own decisions.
- This program comes with no guarantee.
- Use at your own risk.

---------------------------------------------------------------------

'''
)
