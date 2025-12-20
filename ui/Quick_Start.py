import streamlit as st
import os

import sskeys as kz

logofile = os.path.join(os.path.dirname(__file__), "./owl.png")

col1, col2, col3 = st.columns([0.69, 0.02, 0.29], gap="large")
with col3:
    st.image(logofile)
    st.caption("Retirement planner with great wisdom")
with col1:
    st.write("""# :orange[Welcome to Owl - Optimal Wealth Lab]
\nA retirement financial exploration tool based on linear programming""")
    kz.divider("orange")
    st.write("### :material/campaign: News")
    st.markdown("""
:mega:
This version includes an improved social security calculator.
As rules for social security can change depending on which
specific day of the month an individual is born,
the full date of birth is now considered in the calculations.

:warning:
**Older case files will generate wrong dates of birth.**

Either edit the *toml* case files to contain the correct dates of birth in the following format.
```
"Date of birth" = [ "1962-01-15", "1966-06-23",]
```
The current entries for year and month are no longer needed and are ignored.
Alternatively, you can
1) `Duplicate` the case,
1) update dates of birth in the interface, then `Create` the case,
1) run the case by going to any page under the **Single Scenario** tab,
1) and then save the case file on the **Output Files** page.

Please report bugs :bug: and suggestions through the
GitHub [channel](http://github.com/mdlacasse/Owl/issues)
or directly by email [:incoming_envelope:](mailto:martin.d.lacasse@gmail.com).

Take the time to give a :star: on GitHub if you use Owl. That's all you have to give!
""")

    kz.divider("orange")
    st.write("### :material/rocket_launch: Quick Start")
    st.markdown("""
To respect your privacy, Owl does not store any information related to a case:
all information is lost after a session is closed. For this reason,
two ancillary files can be used to store the specifications of a case so that it can be reproduced
at a later time:
- A *case* parameter file
specifying account balances, asset allocation, social security and pension, rates,
optimization parameters and related assumptions.
This file is in *toml* format which is editable with a simple text editor.
- A *Wages and Contributions* file containing a
time table with anticipated wages, future contributions
to savings accounts, Roth conversions and contributions for future and last five years,
and anticipated big-ticket items, which can be either expenses or income.
This file is in Excel or LibreOffice format, and has one tab per individual in the plan.
If no file is provided, values will default to zero, but these values can be edited in the app.

With these two files, a scenario can be created and solved with only a few steps. We will use the case
of Jack and Jill provided here as an example:
1) Download these two files from the GitHub repository
 (right-click on the link and select `Save link as...`):
    - *Case* parameter file named
    [case_jack+jill.toml](https://github.com/mdlacasse/Owl/blob/main/examples/case_jack+jill.toml?raw=true)
    in editable *toml* format.
    - *Wages and Contributions* file named
    [jack+jill.xlsx](https://github.com/mdlacasse/Owl/blob/main/examples/jack+jill.xlsx?raw=true)
    in Excel format.
1) Navigate to the **Create Case** page and drag and drop the case parameter file
you just downloaded (*case_jack+jill.toml*).
Alternatively, you can directly select the case of *jack+jill* among the GitHub examples.
1) Navigate to the **Wages and Contributions** page and
drag and drop the *Wages and Contributions* file you downloaded (*jack+jill.xlsx*).
Alternatively, you can directly load the *Wages and Contributions* file from GitHub using the marked button.
1) Move to any page in the **Single Scenario** section to browse the simulation results.

Congratulations! :balloon: You just ran your first case.
:trophy: You can now explore each page and experiment with different parameters.

For creating your own cases, you can start
from scratch by selecting `New Case...` in the selection box while on the **Create Case** page,
and fill in the information needed on each page in the **Case Setup** section.
Alternatively, you can duplicate any existing case by using
the `Duplicate case` button, and then edit its values to fit your situation.

Once a case has been fully parameterized and successfully optimized,
its parameters can be saved by using the `Download case file...` button on the **Output Files** page.
Multiple cases can coexist and can be called and compared using the `Case selector` box
at the top of the page.

More information can be found on the :material/help: **[Documentation](Documentation)**
page located in the **Resources** section.
""")
