"""
About page for Owl retirement planner Streamlit UI.

This module displays information about the Owl application including version,
release notes, credits, and links to documentation and source code.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import platform
from pathlib import Path

import streamlit as st

import sskeys as kz
import owlbridge as owb

logofile = kz.LOGOFILE

col1, col2 = st.columns([2.8, 1], gap="large")
with col1:
    st.markdown("# :material/info: About Owl")
    st.markdown("### Owl - *Optimal wealth lab*")
    kz.divider("orange")
    st.markdown(
        f"**Version {owb.version()}** running on Streamlit **{st.__version__}** "
        f"and Python **{platform.python_version()}**"
    )
    st.markdown("### :orange[The **Owl** Retirement Planner]")
    st.markdown("""
##### A retirement financial exploration tool based on mathematical optimization

The goal of **Owl** is to provide a free and open-source ecosystem that has cutting-edge
optimization capabilities, allowing for the new generation of computer-literate retirees
to experiment with their own financial future while providing a codebase where they can learn and contribute.
At the same time, Streamlit provides an intuitive and easy-to-use
interface which allows a broad set of users to benefit from the application
as it only requires basic financial knowledge.

Strictly speaking, **Owl** is not a planning tool, but more an environment for exploring *what if* scenarios.
It provides different realizations of a financial strategy through the rigorous
mathematical optimization of relevant decision variables.
**Owl** is designed for US retirees as it considers US federal tax laws,
Medicare premiums, rules for 401k including required minimum distributions,
maturation rules for Roth accounts and conversions, Social Security rules, etc.
Using a mixed-integer linear programming approach,
two different objectives can currently be optimized: maximize net spending subject to a desired bequest;
or maximize an after-tax bequest subject to a desired net spending amount.
In each case, Roth conversions are optimized to reduce the tax burden,
while federal income tax and Medicare premiums (including IRMAA — Income-Related Monthly Adjustment
Amounts, which impose income-based surcharges on Medicare Parts B and D) are calculated.
""")
    st.markdown(
        """
- **Owl** is an open-source retirement financial planner capable of optimization through
mixed-integer linear programming.
- Source code is available from a repository on [GitHub](https://github.com/mdlacasse/Owl).
- Mathematical formulation of the linear optimization problem can be
found in this [document](https://github.com/mdlacasse/Owl/blob/main/papers/owl.pdf?raw=true).
"""
    )
with col2:
    st.image(logofile, width="stretch")
    st.caption("*Retirement planner with great wisdom*")
st.divider()

credits_text = (Path(__file__).parent.parent / "CREDITS.md").read_text(encoding="utf-8")
credits_text = kz.stripLicenseHeader(credits_text)
credits_text = credits_text.replace("## Owl — Optimal wealth lab: Credits and Acknowledgements\n", "", 1)
split_marker = "- [MOSEK]"
if split_marker in credits_text:
    people_part, deps_part = credits_text.split(split_marker, 1)
    deps_part = split_marker + deps_part
else:
    people_part, deps_part = credits_text, ""

st.markdown("#### :orange[Credits and Acknowledgements]")
col1, col2 = st.columns(2, gap="large")
with col1:
    st.markdown(people_part)
with col2:
    st.markdown(deps_part)

rn_path = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
try:
    rn_text = rn_path.read_text(encoding="utf-8")
except OSError:
    rn_text = None

st.markdown("#### :orange[Changelog]")
if rn_text:
    with st.expander("*View changelog*", expanded=False):
        st.markdown(rn_text)

st.markdown(
    """
#### :orange[Bugs and Feature Requests]
Please submit bugs and feature requests through
[GitHub](https://github.com/mdlacasse/Owl/issues) if you have a GitHub account
or directly by [email](mailto:martin.d.lacasse@gmail.com).
Or just drop me a line to report your experience with the tool. &#x1F44D;

#### :orange[Privacy]
This app does not store or forward any information. All data entered is lost
after a session is closed. However, you can choose to download selected parts of your
own data to your computer before closing the session. These data will be stored strictly on
your computer and can be used to reproduce a case at a later time.

#### :orange[License]
This project is distributed under three separate licenses depending on the type of file:

- **Source code** is licensed under the
  [GNU General Public License v3](https://www.gnu.org/licenses/gpl-3.0.html#license-text).
- **Documentation** is licensed under the
  [Creative Commons Attribution-NonCommercial-ShareAlike 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
  license (CC-BY-NC-SA-4.0).
- The **Owl - Optimal wealth lab** name and the logo/icon images are **all rights reserved**,
  Copyright &copy; 2024-2026 Martin-D. Lacasse. They are **not** covered by the GPLv3 and may
  not be reproduced or modified without permission
  ([details](https://github.com/mdlacasse/Owl/blob/main/assets/LICENSE)).

Copyright &copy; 2024-2026 Martin-D. Lacasse and The **Owl**
[Authors](https://github.com/mdlacasse/Owl/blob/main/AUTHORS)
"""
)

kz.divider("orange")
st.markdown("### :orange[Next steps]")
c1, c2, c3 = st.columns(3)
with c1:
    st.page_link("Create_Case.py", label="Create Case", icon=":material/person_add:")
with c2:
    st.page_link("Documentation.py", label="Documentation", icon=":material/help:")
with c3:
    st.page_link("Parameters_Reference.py", label="Parameters Reference", icon=":material/menu_book:")
