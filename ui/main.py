"""
Main Streamlit application entry point for Owl retirement planner UI.

This module sets up the Streamlit page configuration and defines the
navigation structure for the Owl retirement planning web application.

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

import streamlit as st

import sskeys as kz
import moseklicense

# Provision the MOSEK license at app startup (Streamlit Cloud reads it from secrets).
# Done here explicitly rather than as an import side effect so that merely importing a
# ui module (e.g. in the test suite) does not set MOSEKLM_LICENSE_FILE and silently
# switch owlplanner's default solver from HiGHS to MOSEK.
moseklicense.createLicense()

# Default page width is set here; switch to layout="centered" in this file if you prefer.
st.set_page_config(layout="wide", page_title="Owl — Optimal wealth lab")
# st.set_page_config(layout="centered", page_title="Owl — Optimal wealth lab")

kz.init()

# Logo path is centralized in sskeys (single source of truth, repo-root /assets).
st.logo(kz.FAVICONFILE, size="large")

pages = {
    "Case Setup": [
        st.Page("Create_Case.py", icon=":material/person_add:"),
        st.Page("Financial_Profile.py", icon=":material/home:"),
        st.Page("Fixed_Income.py", icon=":material/currency_exchange:"),
        st.Page("Account_Balances.py", icon=":material/savings:"),
        st.Page("Asset_Allocation.py", icon=":material/percent:"),
        st.Page("Rates.py", icon=":material/monitoring:"),
        st.Page("Goals.py", icon=":material/target:"),
        st.Page("Run_Options.py", icon=":material/tune:"),
    ],
    "Results": [
        st.Page("Graphs.py", icon=":material/stacked_line_chart:"),
        st.Page("Worksheets.py", icon=":material/data_table:"),
        st.Page("Reports.py", icon=":material/description:"),
    ],
    "Stress Tests": [
        st.Page("Historical_Range.py", icon=":material/history:"),
        st.Page("Monte_Carlo.py", icon=":material/finance:"),
        st.Page("Spending_Optimization.py", icon=":material/query_stats:"),
    ],
    "Tools": [
        st.Page("Connect_your_AI.py", icon=":material/smart_toy:"),
        st.Page("Settings.py", icon=":material/settings:"),
        st.Page("Logs.py", icon=":material/error:"),
    ],
    "Help": [
        st.Page("Welcome.py", icon=":material/campaign:", default=True),
        st.Page("Documentation.py", icon=":material/help:"),
        st.Page("Parameters_Reference.py", icon=":material/menu_book:"),
        st.Page("About_Owl.py", icon=":material/info:"),
    ],
}

pg = st.navigation(pages, position=kz.getGlobalKey("menuLocation"))

pg.run()
