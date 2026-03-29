"""
Worksheets page for Owl retirement planner Streamlit UI.

This module provides the interface for viewing detailed worksheet data
from retirement planning optimization results.

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

ret = kz.titleBar(":material/data_table: Worksheets")

if ret is None or kz.caseHasNoPlan():
    st.info("A case must first be created before running this page.")
else:
    if kz.caseIsRunReady():
        owb.runPlan()
    elif kz.caseHasNotRun():
        st.info("Case definition is not yet complete. Please visit all pages in *Case Setup*.")

    if kz.isCaseUnsolved():
        st.info("Case status is currently '%s'." % kz.getCaseKey("caseStatus"))
    else:
        kz.initCaseKey("worksheetShowAges", False)
        kz.initCaseKey("worksheetHideZeroColumns", False)
        kz.initCaseKey("worksheetRealDollars", False)
        with st.expander("*Table display and save options*", expanded=False):
            help_age = (
                "Add per-person age columns (age on December 31 of each row's calendar year)."
            )
            help_hide = (
                "Hide numeric columns where every value is zero."
            )
            help_real = (
                "Display and save all currency values in inflation-adjusted (today's) dollars. "
                "The saved Excel filename will have '_real' appended."
            )
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                kz.getToggle("Show ages", "worksheetShowAges", callback=owb.setWorksheetShowAges, help=help_age)
            with col_b:
                kz.getToggle(
                    "Hide columns that are all zeros",
                    "worksheetHideZeroColumns",
                    callback=owb.setWorksheetHideZeroColumns,
                    help=help_hide,
                )
            with col_c:
                kz.getToggle(
                    "Show/save in real (today's) dollars",
                    "worksheetRealDollars",
                    callback=owb.setWorksheetRealDollars,
                    help=help_real,
                )
        owb.showWorkbook()
