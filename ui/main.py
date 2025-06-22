import streamlit as st

import sskeys as kz

# Pick one for narrow or wide graphs. That can also be changed in upper-right settings menu.
st.set_page_config(layout="wide", page_title="Owl Retirement Planner")
# st.set_page_config(layout="centered", page_title="Owl Retirement Planner")

kz.init()

st.logo("https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png", size="large")

pages = {
    "Case Setup": [
        st.Page("Create_Case.py", icon=":material/person_add:"),
        st.Page("Wages_and_Contributions.py", icon=":material/work_history:"),
        st.Page("Fixed_Income.py", icon=":material/currency_exchange:"),
        st.Page("Current_Assets.py", icon=":material/savings:"),
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
        st.Page("Logs.py", icon=":material/error:"),
        st.Page("Quick_Start.py", icon=":material/rocket_launch:", default=True),
        st.Page("Documentation.py", icon=":material/help:"),
        st.Page("Settings.py", icon=":material/settings:"),
        st.Page("About_Owl.py", icon=":material/info:"),
    ],
}

pg = st.navigation(pages, position="top")

pg.run()
