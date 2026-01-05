"""
Output Files page for Owl retirement planner Streamlit UI.

This module provides the interface for downloading output files including
Excel workbooks and summary reports from retirement planning results.

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

ret = kz.titleBar(":material/description: Output Files")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.caseIsRunReady():
        owb.runPlan()
    elif kz.caseHasNotRun():
        st.info("Case definition is not yet complete. Please visit all pages in *Case Setup*.")

    if kz.isCaseUnsolved():
        st.info("Case status is currently '%s'." % kz.getCaseKey("caseStatus"))
    else:
        caseName = kz.getCaseKey("name")
        df = kz.compareSummaries()
        if df is not None:
            st.markdown("""#### :orange[Synopsis]\nThis table provides a summary of the current
case and compares it with other similar cases that ran successfully.""")
            styledDf = df[1:].style.map(kz.colorBySign)
            st.dataframe(styledDf, width="stretch")
            st.caption("Values with [legend] are nominal, otherwise in today's \\$. "
                       "Lines starting with » indicate itemized subtotals.")
            col1, col2 = st.columns(2, gap="large")
            helpmsg = "Download synopsis and comparisons as a text file."
            col1.download_button("Download Synopsis", data=df[1:].to_string(),
                                 file_name=f"Synopsis_{caseName}.txt", help=helpmsg,
                                 mime="text/plain;charset=UTF-8")

            helpmsg = "Rerun all other cases defined in the case selector."
            col2.button("Rerun all cases", on_click=owb.runAllCases, help=helpmsg)

        lines = kz.getCaseKey("casetoml")
        if lines != "":
            st.divider()
            st.markdown("""#### :orange[Case Parameter File]\nThis file contains the parameters
characterizing the current case and can be used, along with the *Household Financial Profile*
workbook, to reproduce it in the future.""")
            st.code(lines, height=400, language="toml")

            st.download_button(
                "Download Case parameter file", data=lines,
                file_name=f"Case_{caseName}.toml", mime="application/toml"
            )

        st.divider()
        st.markdown("""#### :orange[Excel Workbooks]\nThese workbooks contain time tables
describing the flow of money, the first one as input to the case, and the following as its output.""")
        col1, col2 = st.columns(2, gap="large")
        with col1:
            download2 = st.download_button(
                label="Download Household Financial Profile workbook",
                help="Download Household Financial Profile as an Excel workbook.",
                data=owb.saveContributions(),
                file_name=f"HFP_{caseName}.xlsx",
                disabled=kz.isCaseUnsolved(),
                mime="application/vnd.ms-excel",
            )

        with col2:
            download2 = st.download_button(
                label="Download Worksheets",
                help="Download Worksheets as an Excel workbook.",
                data=owb.saveWorkbook(),
                file_name=f"Workbook_{caseName}.xlsx",
                mime="application/vnd.ms-excel",
                disabled=kz.isCaseUnsolved(),
            )
