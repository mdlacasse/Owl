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
owl_pdf_url = "https://raw.githubusercontent.com/mdlacasse/Owl/refs/heads/main/papers/owl.pdf"

# Value proposition
col1, col2 = st.columns([2.8, 1], gap="large")
with col1:
    st.markdown("# Plan your retirement with confidence")
    st.markdown("**Owl** – *Optimal Wealth Lab*")
    st.markdown("")
    st.markdown("""
### :orange[Stop guessing. Start optimizing.]
Retire with confidence and clarity.
**Owl** builds a sophisticated mathematical model of your entire financial landscape—mapping
everything from taxable accounts to Roth conversions and Medicare premiums.

Unlike basic calculators, **Owl** doesn’t just show you a scenario;
it solves for the optimal one. You’ll receive an actionable roadmap that tells you exactly how much
to spend, when to convert to Roth, and which accounts to draw from first.
Plus, you can stress-test your plan against market volatility and changing regulations
to see exactly how robust your future really is.

### :orange[Built for US Retirees]
**Owl** integrates US federal tax laws, Social Security rules, and 401(k)/Roth regulations
to ensure your plan is grounded in reality.""")

with col2:
    st.image(logofile, width="stretch")
    st.caption("*Retirement planner with great wisdom*")

st.markdown("### :orange[Powered by best-in-class optimizer]")
col1, col2 = st.columns([17, 83], gap="medium")
with col1:
    moseklogo = "https://www.mosek.com/static/images/branding/partnergraphmosekinside.jpg"
    st.image(moseklogo)
    st.caption("*Optimization done right. Since 1999.*")
with col2:
    st.markdown("""
[MOSEK](https://mosek.com)—the industry-leading optimizer behind *"Optimization done right. Since 1999."*—has
generously provided **Owl** with a free license for the Community Cloud deployment. This means you get:
- **Faster, more reliable plans** — Run more cases in less time with a state-of-the-art solver.
- **Professional-grade optimization** — The same technology trusted by financial institutions
and engineering firms worldwide.
- **Freedom to compare** — Benchmark results against other optimizers and choose what works best for you.

We are grateful for MOSEK's support of open-source retirement planning.
""")

st.markdown("""
### :orange[Private by design]
**Owl** is open source. Your data stays private in all cases—we don't store, track,
or resell your financial data, whether cloud-hosted, or self-hosted on your device.
- **No Sign-ups:** Start planning immediately.
- **No Fees:** Professional-grade modeling, free for everyone.
- **Total Privacy:** Your data remains private either way.
""")

kz.divider("orange")

# Benefits
st.markdown("### :orange[How is **Owl** different?]")
st.markdown(
    "Most **retirement calculators** give you one rigid path. **Owl** **optimizes** "
    "your plan given your assumptions so you can:"
)
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""**:material/trending_up: Spend with confidence**
\nKnow exactly how much you can enjoy each year without the fear of outliving your savings.""")
with col2:
    st.markdown("""**:material/account_balance: Minimize lifetime taxes**
\nAutomatically identify Roth conversion windows to lower your total tax bill and Medicare (IRMAA) premiums.""")
with col3:
    st.markdown("""**:material/lock: Keep your data private**
\nPrivacy by design. Whether cloud or self-hosted, we never store, view, or monetize your financial info.""")

kz.divider("orange")
st.markdown("### :orange[Ready for a demo?]")

with st.expander("*Explore some case examples*"):
    # ---- Quick start demo: lead with 3-step journey ----
    st.markdown("#### :orange[Run your first case in 3 steps]")
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

st.markdown("### :orange[Ready to go deeper?]")
with st.expander("*Run your own cases*"):
    st.markdown("""Design your own case and save your progress locally.
Return anytime by uploading your own configuration files—no cloud account required.""")
    st.markdown("#### :orange[Get the sample case files]")
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
    st.markdown("### :orange[How to run **Owl**]")
    st.markdown("""
- Use **Owl** directly as hosted on the Streamlit Community Cloud server
([owlplanner.streamlit.app](https://owlplanner.streamlit.app)),
- Self-host in a Docker container running on your computer
(instructions [here](https://github.com/mdlacasse/Owl/blob/main/docker/README.md)), or
- Run natively on your computer (instructions [here](https://github.com/mdlacasse/Owl/blob/main/INSTALL.md)).""")

kz.divider("orange")

# ---- Social proof / trust ----
st.markdown("### :orange[Get involved]")
st.markdown("""**Owl** is being developed by retired scientists and engineers who are happy
to share their knowledge and remain intellectually engaged and active.\n
- Found a bug or have an idea? Open an [issue](https://github.com/mdlacasse/Owl/issues) (requires a GitHub account).
- Want to share your story? Open a [discussion](https://github.com/mdlacasse/Owl/discussions).
- You use **Owl** and like it? Give the [repo](https://github.com/mdlacasse/Owl) a star.""")

st.markdown("### :orange[Disclaimer]")
st.markdown("""
US retirees and planners use **Owl** to explore spending, Roth conversions, and tax-efficient drawdown strategies.
We use up-to-date US federal tax rules (including 2026) so you can plan with confidence.
Nevertheless, this program is for educational purposes only and does not constitute financial advice.""")

kz.divider("orange")

# ---- Secondary CTAs and resources ----
st.markdown("### :orange[Next steps]")
c0, c1, c2, c3 = st.columns(4)
with c0:
    st.page_link("Create_Case.py", label="Open Create Case", icon=":material/person_add:")
with c1:
    st.page_link("Documentation.py", label="Documentation", icon=":material/help:")
with c2:
    st.page_link("Parameters_Reference.py", label="Parameters reference", icon=":material/tune:")
with c3:
    st.page_link("About_Owl.py", label="About Owl", icon=":material/info:")
