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
Owl uses two files to store the specifications of a case so that it can be recalled at a later time.
- A *case* parameter file
specifies account balances, asset allocation, social security and pension, rates, 
optimization parameters and related assumptions.
This file is in *toml* format which is editable with a simple text editor.
- A *wages and contributions* file contains a
time table describing anticipated wages, future contributions
to savings accounts, and anticipated big-ticket items, which can be either expenses or income.
This file is in Excel or LibreOffice format, and has one tab per individual in the plan.

With these two files, a scenario can be solved in only a few steps. We will use the case
of Jack and Jill provided here as an example:
1) Download these two files from the repository:
    - Case parameter file named
    [case_jack+jill.toml](https://raw.github.com/mdlacasse/Owl/main/examples/case_jack+jill.toml)
    in editable *toml* format.
    - Wages and contributions file named
    [jack+jill.xlsx](https://raw.github.com/mdlacasse/Owl/main/examples/jack+jill.xlsx)
    in Excel format.
1) Navigate to the ***Basic Info*** page and drag and drop the case parameter file
you just downloaded (*case_jack+jill.toml*).
1) Navigate to the ***Wages and Contributions*** page and
drag and drop the wages and contributions file you downloaded (*jack+jill.xlsx*).
1) Move to the ***Case Results*** page and click on the `Run single case` button.

Congratulations! :balloon: You just ran your first case. You can now explore each page and
experiment with different parameters.

For creating your own case, you can either duplicate one of the example cases and
edit the values to fit your situation, or start
from scratch by selecting `New Case...` while on the ***Basic Info*** page.
Multiple cases can coexist and can be called back from the `Select case` box
at the bottom of the margin.

More information can be found on the :material/help: ***Documentation*** page located in the **Resources** section.
''')
