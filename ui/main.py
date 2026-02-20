"""
Main Streamlit application entry point for Owl retirement planner UI.

This module sets up the Streamlit page configuration and defines the
navigation structure for the Owl retirement planning web application.

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

# Pick one for narrow or wide graphs. That can also be changed in upper-right settings menu.
st.set_page_config(layout="wide", page_title="Owl Retirement Planner")
# st.set_page_config(layout="centered", page_title="Owl Retirement Planner")

kz.init()

# Use URL-based logo from ui folder for simplicity and reliability
st.logo("https://raw.githubusercontent.com/mdlacasse/Owl/main/ui/owl.png", size="large")

pages = {
    "Plan Setup": [
        st.Page("Create_Case.py", icon=":material/person_add:"),
        st.Page("Household_Financial_Profile.py", title="Financial Profile", icon=":material/home:"),
        st.Page("Fixed_Income.py", icon=":material/currency_exchange:"),
        st.Page("Savings_Assets.py", title="Account Balances", icon=":material/savings:"),
        st.Page("Asset_Allocation.py", icon=":material/percent:"),
        st.Page("Rates_Selection.py", icon=":material/monitoring:"),
        st.Page("Optimization_Parameters.py", title="Run Options", icon=":material/tune:"),
    ],
    "Results": [
        st.Page("Graphs.py", icon=":material/stacked_line_chart:"),
        st.Page("Worksheets.py", icon=":material/data_table:"),
        st.Page("Output_Files.py", title="Reports", icon=":material/description:"),
    ],
    "Simulations": [
        st.Page("Historical_Range.py", icon=":material/history:"),
        st.Page("Monte_Carlo.py", icon=":material/finance:"),
    ],
    "Tools": [
        st.Page("Settings.py", icon=":material/settings:"),
        st.Page("Logs.py", icon=":material/error:"),
    ],
    "Help": [
        st.Page("Welcome.py", icon=":material/campaign:", default=True),
        st.Page("Documentation.py", icon=":material/help:"),
        st.Page("Parameters_Reference.py", icon=":material/tune:"),
        st.Page("About_Owl.py", icon=":material/info:"),
    ],
}

pg = st.navigation(pages, position=kz.getGlobalKey("menuLocation"))

pg.run()
