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
Here's how you can run your first case in only a few steps:
1) Download these two files provided as examples for the case of Jack and Jill:
    - [case file](https://raw.github.com/mdlacasse/Owl/main/examples/case_jack+jill.toml)
named *case_jack+jill.toml* in *toml* format
    - [contributions file](https://raw.github.com/mdlacasse/Owl/main/examples/jack+jill.xlsx)
named *jack+jill.xlsx* in Excel format
1) While on the ***Basic Info*** page, select `Upload Case File...` in the `Select case` box at the bottom of the margin
1) Drag and drop the case file you downloaded called *case_jack+jill.toml*
1) Change to the ***Wages and Contributions*** page
1) Drag and drop the file you downloaded called *jack+jill.xlsx*
1) Move to the ***Case Results*** page and click `Run single case`

Congratulations! You just ran your first case. You can now explore each page and
experiment with different configurations.

Alternatively, you can create your own case, you can either start from the example files or start
from `New Case...` while on the ***Basic Info*** page.

More information can be found on the ***Documentation*** page located in the **Resources** section.
'''
    )
