"""
Parameters reference page for Owl retirement planner Streamlit UI.

This module renders the PARAMETERS.md documentation as markdown.

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

import re
from pathlib import Path

import streamlit as st
import sskeys as kz
import owlbridge as owb

logofile = kz.LOGOFILE

parameters_path = Path(__file__).resolve().parents[1] / "info" / "PARAMETERS.md"
try:
    content = parameters_path.read_text(encoding="utf-8")
except FileNotFoundError:
    st.error(f"Unable to locate `{parameters_path.name}` in the project root.", icon=":material/error:")
    st.stop()

# Split preamble from ## sections
parts = re.split(r'\n(?=## )', content)
preamble = parts[0].strip().rstrip('-').strip()
sections = parts[1:]

kz.initGlobalKey("paramsExpandAll", False)

col1, col2 = st.columns([2.8, 1], gap="large", vertical_alignment="top")
with col1:
    st.markdown("# :material/menu_book: Parameters Reference")
    st.markdown("### Owl - *Optimal wealth lab*")
    kz.divider("orange")
    st.markdown(f"**Version {owb.version()}**")
    sub_text, sub_toggle = st.columns([5, 1], vertical_alignment="bottom")
    with sub_text:
        st.markdown("Complete reference for all parameters in Owl TOML configuration files.")
    with sub_toggle:
        _help = "Expand all sections. Tip: expand before using Ctrl+F (or ⌘F) to search within this page."
        expand_all = st.toggle("Expand all", key="paramsExpandAll", help=_help)
    if preamble:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(preamble)
with col2:
    st.image(logofile, width="stretch")
    st.caption("*Retirement planner with great wisdom*")

# st.divider()
for i, section in enumerate(sections):
    heading, _, body = section.partition('\n')
    # Strip trailing horizontal rules added as separators in the source
    body = body.strip().rstrip('-').strip()
    # Extract label: remove "## " prefix, add bold inside any :orange[...] wrapper
    label = re.sub(r'^##\s+', '', heading)
    label = re.sub(r':orange\[(.+?)\]', r':orange[**\1**]', label)
    if not label.startswith(':orange['):
        label = f":orange[**{label}**]"
    with st.expander(label, expanded=expand_all or (i == 0), type="compact"):
        st.markdown(body)

kz.divider("orange")
st.markdown("### :orange[Next steps]")
c1, c2, c3 = st.columns(3)
with c1:
    st.page_link("Create_Case.py", label="Create Case", icon=":material/person_add:")
with c2:
    st.page_link("Documentation.py", label="Documentation", icon=":material/help:")
with c3:
    st.page_link("About_Owl.py", label="About Owl", icon=":material/info:")
