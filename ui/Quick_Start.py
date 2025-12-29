import streamlit as st
import os

import sskeys as kz

logofile = os.path.join(os.path.dirname(__file__), "./owl.png")

col1, col2, col3 = st.columns([0.69, 0.02, 0.29], gap="large")
with col3:
    st.image(logofile)
    st.caption("Retirement planner with great wisdom")
with col1:
    st.markdown("""# :orange[Welcome to Owl - Optimal Wealth Lab]
\nA retirement financial exploration tool based on linear programming""")
    kz.divider("orange")
    st.markdown("### :material/campaign: News")
    st.markdown("""
This version introduces several new capabilities:
- Page *Household Financial Profile* now includes *Wages and Contributions*,
*Debts*, and *Fixed Assets*.
- *Debts* support tracking loans and mortgages over time.
- *Fixed Assets* can represent primary residence, other real estate, precious metals,
                    restricted stocks, collectibles, and fixed lump-sum annuities.
- These additions allow assets to be modeled through their expected disposition date.
- Debts and fixed assets remaining at the end of the plan are incorporated into bequest calculations.

This part of the code is still evolving and has not yet received the same level of testing as the rest.
Please report bugs :bug: and suggestions through the
GitHub [channel](http://github.com/mdlacasse/Owl/issues)
or directly by email [:incoming_envelope:](mailto:martin.d.lacasse@gmail.com).
""")

    kz.divider("orange")
    st.markdown("### :material/rocket_launch: Quick Start")
    st.markdown("""
To respect your privacy, Owl does not store any information related to a case:
all information is lost after a session is closed. For this reason,
two ancillary files can be used to store the specifications of a case so that it can be reproduced
at a later time:
- A *case* parameter file
specifying account balances, asset allocation, social security and pension, rates,
optimization parameters and related assumptions.
This file is in *toml* format which is editable with a simple text editor.
- A *Household Financial Profile* (HFP) Workbook containing
a time table for each individual with anticipated wages, future contributions
to savings accounts, Roth conversions and contributions for future and last five years,
and anticipated big-ticket items, which can be either expenses or income.
Two other optional sheets describe debts and fixed assets respectively.
This file is in Excel or LibreOffice format, and must have one tab per individual in the plan,
and optionally one for the household debts, and one for fixed assets.
If no file is provided, values will default to zero, but these values can be edited in the app.

With these two files, a scenario can be created and solved with only a few steps. We will use the case
of Jack and Jill provided here as an example:
1) Download these two files from the GitHub repository
 (right-click on the link and select `Save link as...`):
    - *Case* parameter file named
    [Case_jack+jill.toml](https://github.com/mdlacasse/Owl/blob/main/examples/Case_jack+jill.toml?raw=true)
    in editable *toml* format.
    - *Household FInancial Profile* workbook named
    [HFP_jack+jill.xlsx](https://github.com/mdlacasse/Owl/blob/main/examples/HFP_jack+jill.xlsx?raw=true)
    in Excel format.
1) Navigate to the **Create Case** page and drag and drop the case parameter file
you just downloaded (*Case_jack+jill.toml*).
Alternatively, you can directly select the case of *jack+jill* among the GitHub examples.
1) Navigate to the **Household Financial Profile** page and
drag and drop the *Household Financial Profile* workbook you downloaded (*HFP_jack+jill.xlsx*).
Alternatively, you can load the *Household Financial Profile* workbook directly by using the marked button.
1) Move to any page in the **Single Scenario** section to browse the simulation results.

Congratulations! :balloon: You just ran your first case.
:trophy: You can now explore each page and experiment with different parameters.

For creating your own cases, you can start
from scratch by selecting `New Case...` in the selection box while on the **Create Case** page,
and fill in the information needed on each page in the **Case Setup** section.
Alternatively, you can copy any existing case by using
the `Copy case` button, and then edit its values to fit your situation.
Make sure that the *Household Financial Profile* has been loaded in the
original case before creating a copy.

Once a case has been fully parameterized and successfully optimized,
its parameters can be saved by using the `Download case file...` button on the **Output Files** page.
Multiple cases can coexist and can be called and compared using the `Case selector` box
at the top of the page.

More information can be found on the :material/help: **[Documentation](Documentation)**
page located in the **Resources** section.
""")
