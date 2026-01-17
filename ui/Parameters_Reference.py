"""
Parameters reference page for Owl retirement planner Streamlit UI.

This module renders the PARAMETERS.md documentation as markdown.

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


st.markdown("# :material/tune: Parameters Reference")
kz.divider("orange")

parameters_path = Path(__file__).resolve().parents[1] / "PARAMETERS.md"
try:
    content = parameters_path.read_text(encoding="utf-8")
except FileNotFoundError:
    st.error(f"Unable to locate `{parameters_path.name}` in the project root.")
else:
    st.markdown(content)
