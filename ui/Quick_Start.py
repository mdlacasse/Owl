import streamlit as st

import sskeys as kz

col1, col2, col3 = st.columns([0.69, 0.02, 0.29], gap='large')
with col3:
    st.image("http://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png")
    st.caption("Retirement planner with great wisdom")
with col1:
    st.write('# Owl Retirement Planner\nA retirement exploration tool based on linear programming')
    kz.orangeDivider()
    st.write('### Quick Start')
    st.markdown('''
Owl does not store any information related to a case:
all is lost after a session is closed. For that reason,
two files can be used to store the specifications of a case so that it can be recalled at a later time.
- A *case* parameter file
specifying account balances, asset allocation, social security and pension, rates,
optimization parameters and related assumptions.
This file is in *toml* format which is editable with a simple text editor.
- A *wages and contributions* file containing a
time table with anticipated wages, future contributions
to savings accounts, and anticipated big-ticket items, which can be either expenses or income.
This file is in Excel or LibreOffice format, and has one tab per individual in the plan.

With these two files, a scenario can be created and solved in only a few steps. We will use the case
of Jack and Jill provided here as an example:
1) Download these two files from the GitHub repository
 (right-click on the link and select `Save link as...`):
    - Case parameter file named
    [case_jack+jill.toml](https://raw.github.com/mdlacasse/Owl/main/examples/case_jack+jill.toml)
    in editable *toml* format.
    - Wages and contributions file named
    [jack+jill.xlsx](https://raw.github.com/mdlacasse/Owl/main/examples/jack+jill.xlsx)
    in Excel format.
1) Navigate to the **Create Case** page and drag and drop the case parameter file
you just downloaded (*case_jack+jill.toml*).
1) Navigate to the **Wages and Contributions** page and
drag and drop the wages and contributions file you downloaded (*jack+jill.xlsx*).
1) Move to the **Single Scenario** section to browse results.

Congratulations! :balloon: You just ran your first case. You can now explore each page and
experiment with different parameters.

For creating your own cases, you can start
from scratch by selecting `New Case...` in the selection box while on the **Create Case** page,
and fill in the information needed on each page of the `Case Setup` section.
Once a case has been fully parameterized and successfully optimized,
its parameters can be saved by using the `Download case file...` button on the `Output Files` page.

Alternatively, you can duplicate any existing case by using
the `Duplicate case` button, and then edit its values to fit your situation.

Multiple cases can coexist and can be called using the `Select case` box
at the bottom of the margin.

More information can be found on the :material/help: **Documentation** page located in the **Resources** section.
''')
