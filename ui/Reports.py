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


def _synopsis_metric_section_style(val):
    """Bold blue for Metric cells that are --- section divider rows."""
    if isinstance(val, str) and val.startswith("---"):
        return "font-weight: bold; color: #1565C0;"
    return ""


def _synopsis_compare_column_config(display_df):
    """Wide first column; explicit width replaces old padded metric keys for Streamlit layout."""
    synopsis_px = 560
    cfg = {
        "Metric": st.column_config.TextColumn(None, width=synopsis_px),
    }
    for c in display_df.columns:
        if c != "Metric":
            cfg[c] = st.column_config.TextColumn(None, width="medium")
    return cfg


ret = kz.titleBar(":material/description: Reports")

if ret is None or kz.caseHasNoPlan():
    kz.no_case_info()
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
        display_df = df.iloc[1:].reset_index(names=["Metric"]) if df is not None else None
        hfp_buffer = owb.saveContributions()
        gcs = owb.getCaseString()
        lines = gcs.getvalue() if gcs else kz.getCaseKey("casetoml")
        if gcs is not None:
            kz.storeCaseKey("casetoml", lines)
        real_suffix = "_real" if kz.getCaseKey("worksheetRealDollars") else ""

        owb.plotSummaryMetrics()
        kz.divider("orange")

        tab1, tab2 = st.tabs(["Synopsis", "Case file"])
        with tab1:
            if display_df is not None:
                case_cols = [c for c in display_df.columns if c != "Metric"]
                styledDf = display_df.style.map(_synopsis_metric_section_style, subset=["Metric"])
                if case_cols:
                    styledDf = styledDf.map(kz.colorBySign, subset=case_cols)
                st.dataframe(
                    styledDf,
                    width="stretch",
                    hide_index=True,
                    column_config=_synopsis_compare_column_config(display_df),
                )
                cap_col, btn_col = st.columns([4, 1], vertical_alignment="top")
                cap_col.caption("» subtotals.")
                btn_col.button("Rerun all cases", on_click=owb.runAllCases,
                               help="Rerun all other cases defined in the case selector.")
            else:
                st.info("No comparison data available yet.")
        with tab2:
            if lines:
                st.markdown("""This file contains the parameters characterizing the current case
and can be used, along with the *Household Financial Profile* workbook, to reproduce it.""")
                st.markdown(
                    "<style>pre, .stCode pre, .highlight pre, pre code "
                    "{ white-space: pre-wrap !important; word-break: break-word !important; }</style>",
                    unsafe_allow_html=True,
                )
                st.code(lines, height=400, language="toml")
            else:
                st.info("No case parameters available yet.")

        kz.divider("orange")
        st.markdown("#### :orange[Downloads]")
        st.caption(
            "Click a button to download. "
            "*Case file* and *Household Financial Profile* (HFP) together can reproduce this run; "
            "*Synopsis* and *Plan workbook* are result outputs."
        )
        col1, col2, col3, col4 = st.columns(4, gap="medium")
        with col1:
            st.download_button(
                "Case file",
                data=lines,
                file_name=f"Case_{caseName}.toml",
                help="TOML file with all parameters to reproduce this run.",
                mime="application/toml",
                disabled=lines == "",
            )
        with col2:
            hfp_clicked = st.download_button(
                "HFP workbook",
                data=hfp_buffer,
                file_name=f"HFP_{caseName}.xlsx",
                help="Excel workbook with household financial input data (HFP).",
                mime="application/vnd.ms-excel",
            )
            if hfp_clicked:
                owb.markHFPAsSaved()
                gcs = owb.getCaseString()
                if gcs is not None:
                    kz.storeCaseKey("casetoml", gcs.getvalue())
                st.rerun()
            if kz.getCaseKey("hfpFileName") and kz.getCaseKey("hfpFileName").endswith(" *"):
                st.caption(
                    ":warning: HFP values were edited. Download both this file and the "
                    "case file to reproduce this run."
                )
        with col3:
            st.download_button(
                "Synopsis",
                data=display_df.to_string(index=False) if display_df is not None else "",
                file_name=f"Synopsis_{caseName}.txt",
                help="Text file with key metrics and case comparison.",
                mime="text/plain;charset=UTF-8",
                disabled=display_df is None,
            )
        with col4:
            st.download_button(
                "Plan workbook",
                data=owb.saveWorkbook(),
                file_name=f"Workbook_{caseName}{real_suffix}.xlsx",
                help="Excel workbook with detailed year-by-year results.",
                mime="application/vnd.ms-excel",
            )
