import streamlit as st
import sys

import sskeys as kz

# Include owlplanner path directly instead of installing module.
sys.path.insert(0, "../src")

# Pick one for narrow or wide graphs. That can also be changed in upper-right settings menu.
st.set_page_config(layout="wide", page_title="Owl Retirement Planner")
# st.set_page_config(layout="centered", page_title="Owl Retirement Planner")

kz.init()

st.logo("https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png", size="large")

pages = {
    "Case Setup": [
        st.Page("Create_Case.py", icon=":material/person_add:"),
        st.Page("Wages_And_Contributions.py", icon=":material/work_history:"),
        st.Page("Current_Assets.py", icon=":material/savings:"),
        st.Page("Fixed_Income.py", icon=":material/currency_exchange:"),
        st.Page("Rates_Selection.py", icon=":material/monitoring:"),
        st.Page("Asset_Allocation.py", icon=":material/percent:"),
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
        st.Page("Logs.py", icon=":material/error:"),
        # Graph style needs a rewrite of plot() to avoid cross-talk between sessions.
        # st.Page("Settings.py", icon=":material/settings:"),
        st.Page("Quick_Start.py", icon=":material/rocket_launch:", default=True),
        st.Page("Documentation.py", icon=":material/help:"),
        st.Page("About_Owl.py", icon=":material/info:"),
    ],
}

kz.initGlobalKey("prevPageName", None)
kz.initGlobalKey("currentPageName", None)

pg = st.navigation(pages)
kz.storeGlobalKey("currentPageName", pg.title)
# Workaround resetting dataframes for data_editor wierd behavior.
wncPage = "Wages And Contributions"
if pg.title != wncPage and kz.getGlobalKey("prevPageName") == wncPage:
    if kz.caseHasPlan():
        kz.updateContributions()

pg.run()
kz.storeGlobalKey("prevPageName", pg.title)
