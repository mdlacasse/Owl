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

import json
import time
import traceback

import streamlit as st

import sskeys as kz

# region agent log
def _agent_log(hypothesis_id, location, message, data=None):
    payload = {
        "sessionId": "debug-session",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    with open("/Users/mdlacasse/Owl/.cursor/debug.log", "a", encoding="utf-8") as logf:
        logf.write(json.dumps(payload) + "\n")
# endregion

# region agent log
_agent_log(
    "H1",
    "ui/main.py:34",
    "main_imported",
    {"pages_defined": True},
)
# endregion

# Pick one for narrow or wide graphs. That can also be changed in upper-right settings menu.
st.set_page_config(layout="wide", page_title="Owl Retirement Planner")
# st.set_page_config(layout="centered", page_title="Owl Retirement Planner")

kz.init()

# region agent log
_agent_log(
    "H2",
    "ui/main.py:50",
    "kz_init_complete",
    {"case_name": kz.currentCaseName()},
)
# endregion

# Use URL-based logo from ui folder for simplicity and reliability
st.logo("https://raw.githubusercontent.com/mdlacasse/Owl/main/ui/owl.png", size="large")

pages = {
    "Case Setup": [
        st.Page("Create_Case.py", icon=":material/person_add:"),
        st.Page("Household_Financial_Profile.py", icon=":material/home:"),
        st.Page("Fixed_Income.py", icon=":material/currency_exchange:"),
        st.Page("Savings_Assets.py", icon=":material/savings:"),
        st.Page("Asset_Allocation.py", icon=":material/percent:"),
        st.Page("Rates_Selection.py", icon=":material/monitoring:"),
        st.Page("Optimization_Parameters.py", icon=":material/tune:"),
    ],
    "Single Scenario": [
        st.Page("Graphs.py", icon=":material/stacked_line_chart:"),
        st.Page("Worksheets.py", icon=":material/data_table:"),
        st.Page("Output_Files.py", icon=":material/description:"),
    ],
    "Multiple Scenarios": [
        st.Page("Historical_Range.py", icon=":material/history:"),
        st.Page("Monte_Carlo.py", icon=":material/finance:"),
    ],
    "Resources": [
        st.Page("Quick_Start.py", icon=":material/rocket_launch:", default=True),
        st.Page("Documentation.py", icon=":material/help:"),
        st.Page("Parameters_Reference.py", icon=":material/tune:"),
        st.Page("Settings.py", icon=":material/settings:"),
        st.Page("Logs.py", icon=":material/error:"),
        st.Page("About_Owl.py", icon=":material/info:"),
    ],
}

kz.initGlobalKey("menuLocation", "top")
kz.initGlobalKey("position", "sticky")

pg = st.navigation(pages, position=kz.getGlobalKey("menuLocation"))

# region agent log
_agent_log(
    "H3",
    "ui/main.py:88",
    "pg_run_start",
    {"menu_location": kz.getGlobalKey("menuLocation"), "page_groups": list(pages.keys())},
)
# endregion
try:
    pg.run()
except Exception as exc:  # noqa: BLE001 - debug instrumentation
    # region agent log
    _agent_log(
        "H1",
        "ui/main.py:96",
        "pg_run_exception",
        {"error": str(exc), "traceback": traceback.format_exc()},
    )
    # endregion
    raise
else:
    # region agent log
    _agent_log(
        "H3",
        "ui/main.py:105",
        "pg_run_complete",
        {},
    )
    # endregion
