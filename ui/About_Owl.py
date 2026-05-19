"""
About page for Owl retirement planner Streamlit UI.

This module displays information about the Owl application including version,
release notes, credits, and links to documentation and source code.

Copyright (C) 2025-2026 The Owlplanner Authors

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

from pathlib import Path

import streamlit as st

import sskeys as kz
import owlbridge as owb

logofile = "https://raw.githubusercontent.com/mdlacasse/Owl/main/ui/owl.png"

col1, col2 = st.columns([2.8, 1], gap="large")
with col1:
    st.markdown("# :material/info: About Owl — *Optimal wealth lab*")
    st.markdown(f"**Version {owb.version()}** &nbsp;·&nbsp; Streamlit **{st.__version__}**")
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown(
        """
- Owl is an open-source retirement financial planner capable of optimization through
mixed-integer linear programming.
- Source code is available from a repository on [GitHub](https://github.com/mdlacasse/Owl).
- Mathematical formulation of the linear optimization problem can be
found in this [document](https://github.com/mdlacasse/Owl/blob/main/papers/owl.pdf?raw=true).
"""
    )
with col2:
    st.image(logofile, width="stretch")
    st.caption("*Retirement planner with great wisdom*")
kz.divider("orange")

credits_text = (Path(__file__).parent.parent / "CREDITS.md").read_text(encoding="utf-8")
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
This software is released under the
[Gnu General Public License v3](https://www.gnu.org/licenses/gpl-3.0.html#license-text).

Copyright &copy; 2025-2026 - The Owlplanner [Authors](https://github.com/mdlacasse/Owl/blob/main/AUTHORS)
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
