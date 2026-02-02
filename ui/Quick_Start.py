"""
Benefit-driven landing page for Owl Retirement Planner.

This module provides a marketing-oriented welcome page focused on user benefits,
clear value proposition, and simplified user journey for improved engagement
and search visibility.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import streamlit as st

import sskeys as kz

# Main app sets layout and page_title in main.py.

logofile = "https://raw.githubusercontent.com/mdlacasse/Owl/main/ui/owl.png"
owl_pdf_url = "https://github.com/mdlacasse/Owl/blob/main/papers/owl.pdf?raw=true"

# Value proposition
col1, col2 = st.columns([2, 1], gap="large")
with col1:
    st.markdown("# :orange[Plan your retirement with confidence]")
    st.markdown("*Owl – Optimal Wealth Lab*")
    st.markdown("")
    st.markdown("""
#### :orange[Stop guessing. Start optimizing.]
Take the guesswork out of retirement with an optimized financial roadmap built just for you.
Owl builds a sophisticated mathematical model ([pdf](../papers/owl.pdf))
of your entire financial life—from taxable accounts to Roth conversions and Medicare premiums.
It doesn't just show you a scenario; it finds the best one based on your goals and shows you exactly
how robust that plan is against market shifts and future regulation based  on your assumptions.
Owl tells you how much you can safely spend, when to do Roth conversions,
and which accounts to draw from.

#### :orange[Built for US Retirees]
Owl integrates US federal tax laws, Social Security rules, and 401(k)/Roth regulations
to ensure your plan is grounded in reality.

#### :orange[Private by design]
Owl is open source and runs entirely on your device.
- **No Sign-ups:** Start planning immediately.
- **No Fees:** Professional-grade modeling, free for everyone.
- **Total Privacy:** Your data stays with you; it’s never tracked or stored on our servers.""")

with col2:
    st.image(logofile, width="stretch")
    st.caption("Retirement planner with great wisdom")

kz.divider("orange")

# Benefits
st.markdown("#### :orange[Why use a retirement spending and tax planner?]")
st.markdown(
    "Most **retirement calculators** give you one rigid path. Owl **optimizes** "
    "your plan given your assumptions so you get:"
)
ben_col1, ben_col2, ben_col3 = st.columns(3)
with ben_col1:
    st.markdown("""**:material/trending_up: Sustainable spending**
 \nSee how much you can spend each year without outliving your savings.""")
with ben_col2:
    st.markdown("""**:material/account_balance: Smarter Roth conversions**
\nReduce taxes and Medicare premiums by timing conversions.""")
with ben_col3:
    st.markdown("""**:material/lock: Your data stays private**
\nEverything runs on your device. We don’t store, view, or resell your financial data.""")

kz.divider("orange")

st.markdown("#### :orange[Ready for a demo?]")

with st.expander("Explore some case  examples."):
    # ---- Quick start demo: lead with 3-step journey ----
    st.markdown("##### :orange[Run your first case in 3 steps]")
    st.markdown("Use the **Jack & Jill** example to see results in under a minute.")

    step1, step2, step3 = st.columns(3)
    with step1:
        st.markdown("**1. Load the case**")
        st.markdown("Go to **Create Case**, then choose **Jack + Jill** from the example dropdown.")
        st.page_link("Create_Case.py", label="Open Create Case", icon=":material/person_add:")
    with step2:
        st.markdown("**2. Load the financial profile**")
        st.markdown("On **Household Financial Profile**, load the Jack & Jill workbook (or use the example button).")
        st.page_link("Household_Financial_Profile.py", label="Open Household Financial Profile", icon=":material/home:")
    with step3:
        st.markdown("**3. View your plan**")
        st.markdown("Check **Graphs**, **Worksheets**, or **Output Files** under Single Scenario.")
        st.page_link("Graphs.py", label="View Graphs", icon=":material/stacked_line_chart:")

    st.markdown("")
    st.caption("You’ve run your first case. Explore other Case Setup pages to change assumptions. Explore other cases.")

kz.divider("orange")

st.markdown("#### :orange[Ready to go deep ?]")
with st.expander("Run your own cases."):
    st.markdown("""Design your own case and save your progress locally.
Return anytime by uploading your own configuration files—no cloud account required.""")
    st.markdown("##### :orange[Get the sample case files]")
    st.markdown("""
Want to edit assumptions in a text editor or spreadsheet? Download the Jack & Jill files and reload them anytime.
You can also copy the case from within the app, modify, and save your changes.""")

    lm1, lm2 = st.columns(2)
    with lm1:
        st.markdown("""- **Case parameters** (TOML):
    [Case_jack+jill.toml](https://github.com/mdlacasse/Owl/blob/main/examples/Case_jack+jill.toml?raw=true)""")
    with lm2:
        st.markdown(
            """- **Household Financial Profile** (Excel):
    [HFP_jack+jill.xlsx](https://github.com/mdlacasse/Owl/blob/main/examples/HFP_jack+jill.xlsx?raw=true)""")
    st.caption("Right-click a link and choose “Save link as…” to download.")

    st.markdown("""
You can also create a case from scratch in the app and save the *case* and *Household Financial Profile* from there.""")
    kz.divider("orange")

    # ---- How to run Owl ----
    st.markdown("#### :orange[How to run Owl]")
    st.markdown("""
- Use Owl directly as hosted on the Streamlit Cloud server
([owlplanner.streamlit.app](https://owlplanner.streamlit.app)),
- Self-host in a Docker container running on your compiuter
(instructions [here](https://github.com/mdlacasse/Owl/blob/main/docker/README.md)), or
- Run natively on your computer (instructions [here](https://github.com/mdlacasse/Owl/blob/main/INSTALL.md)).""")

kz.divider("orange")

# ---- Social proof / trust ----
st.markdown("#### :orange[Getting involved]")
st.markdown("""Owl is being developed by retired scientitsts and engineers happy
to share their knowledge and remain intellectually engaged and active.\n
Found a bug or have an idea? Open an [issue](https://github.com/mdlacasse/Owl/issues).
You use Owl and like it? Give the [repo](https://github.com/mdlacasse/Owl) a star.""")

st.markdown("#### :orange[Disclaimer]")
st.markdown("""
US retirees and planners use Owl to explore spending, Roth conversions, and tax-efficient drawdown strategies.
We use up-to-date US federal tax rules (including 2026) so you can plan with confidence.
Nevertheless, this program is for educational purposes only and does not constitute financial advice.""")

kz.divider("orange")

# ---- Secondary CTAs and resources ----
st.markdown("#### :orange[Next steps]")
c0, c1, c2, c3 = st.columns(4)
with c0:
    st.page_link("Create_Case.py", label="Open Create Case", icon=":material/person_add:")
with c1:
    st.page_link("Documentation.py", label="Documentation", icon=":material/help:")
with c2:
    st.page_link("Parameters_Reference.py", label="Parameters reference", icon=":material/tune:")
with c3:
    st.page_link("About_Owl.py", label="About Owl", icon=":material/info:")
