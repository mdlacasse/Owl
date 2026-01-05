"""
Historical Range page for Owl retirement planner Streamlit UI.

This module provides the interface for running historical backtesting
scenarios over selected year ranges to analyze retirement planning outcomes.

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

import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar(":material/history: Historical Range")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    kz.initCaseKey("hyfrm", owb.FROM)
    kz.initCaseKey("hyto", owb.TO)
    kz.initCaseKey("histoPlot", None)
    kz.initCaseKey("histoSummary", None)

    st.markdown("""Generate a histogram of results obtained from backtesting
current scenario with historical data over selected year range.""")
    col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="bottom")
    with col1:
        st.number_input(
            "Starting year",
            min_value=owb.FROM,
            max_value=kz.getCaseKey("hyto"),
            value=kz.getCaseKey("hyfrm"),
            on_change=kz.storepull,
            args=["hyfrm"],
            key=kz.genCaseKey("hyfrm"),
        )

    with col2:
        st.number_input(
            "Ending year",
            max_value=owb.TO,
            min_value=kz.getCaseKey("hyfrm"),
            value=kz.getCaseKey("hyto"),
            on_change=kz.storepull,
            args=["hyto"],
            key=kz.genCaseKey("hyto"),
        )

    # st.divider()
    # col1, col2 = st.columns(2, gap="small", vertical_alignment="top")
    with col4:
        st.button("Run historical range", on_click=owb.runHistorical, disabled=kz.caseIsNotRunReady())

    st.divider()
    fig = kz.getCaseKey("histoPlot")
    if fig:
        col1, col2 = st.columns(2, gap="medium")
        owb.renderPlot(fig, col1)
        col2.code(kz.getCaseKey("histoSummary"), language=None)
