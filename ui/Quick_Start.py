import streamlit as st

import sskeys as kz

col1, col2, col3 = st.columns([0.69, 0.02, 0.29], gap='large')
with col3:
    st.image("http://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png")
    st.caption("Retirement planner with great wisdom")
with col1:
    st.write('## Quick Start')
    kz.orangeDivider()
    st.markdown('''
Owl uses two files to store the specifications of a case so that its state can be recalled in the future.
A *case* parameter file
contains account balances, asset allocation, social security and pension, optimization
parameter and other specifications.
This file is in *toml* format which is editable with a simple text editor.
A *wages and contributions* file is a
time table containing anticipated wages, future contributions
to savings accounts, and anticipated big-ticket items, which can be either expenses or income.
This file is in Excel or LibreOffice format, and contains one tab per individual in the plan.

With these files, a case can be run in only a few steps. We will use the case
of Jack and Jill provided here as an example:
1) Download these two files from the repository:
    - [case parameter file](https://raw.github.com/mdlacasse/Owl/main/examples/case_jack+jill.toml)
named *case_jack+jill.toml* in editable *toml* format.
    - [wages and contributions file](https://raw.github.com/mdlacasse/Owl/main/examples/jack+jill.xlsx)
named *jack+jill.xlsx* in Excel format.
1) Navigate to the ***Basic Info*** page and drag and drop the case parameter file
you downloaded called *case_jack+jill.toml*.
1) Navigate to the ***Wages and Contributions*** page and
drag and drop the file you downloaded called *jack+jill.xlsx*.
1) Move to the ***Case Results*** page and click `Run single case`.

Congratulations! :balloon: You just ran your first case. You can now explore each page and
experiment with different parameters.

For creating your own case, you can either start from the example files or start
from scratch by selecting `New Case...` while on the ***Basic Info*** page.
Multiple cases can coexist and can be called back from the `Select case` box
at the bottom of the margin.

More information can be found on the :material/help: ***Documentation*** page located in the **Resources** section.
''')
