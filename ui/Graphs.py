"""
Graphs page for Owl retirement planner Streamlit UI.

This module provides the interface for visualizing retirement planning results
through various charts and graphs.

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


ret = kz.titleBar(":material/stacked_line_chart: Graphs")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.caseIsRunReady():
        owb.runPlan()
    elif kz.caseHasNotRun():
        st.info("Case definition is not yet complete. Please visit all pages in *Case Setup*.")

    st.markdown("Optimize a single scenario based on the parameters selected in the **Case Setup** section.")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="bottom")
    with col1:
        choices = ["nominal", "today"]
        kz.initCaseKey("plots", choices[0])
        helpmsg = "Plot can be in today's dollars or in nominal value."
        ret = kz.getRadio("Dollar amounts in plots", choices, "plots", help=helpmsg,
                          callback=owb.setDefaultPlots)

    with col3:
        helpmsg = "Click to refresh if some graphs are not showing."
        st.button(
            "Re-run single case",
            help=helpmsg,
            on_click=owb.runPlan,
            disabled=kz.caseIsNotRunReady(),
        )

    st.divider()
    if kz.isCaseUnsolved():
        st.info("Case status is currently '%s'." % kz.getCaseKey("caseStatus"))
    else:
        owb.plotSingleResults()
