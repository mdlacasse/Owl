import streamlit as st

import sskeys as kz

# Pick one for narrow or wide graphs. That can be changed in upper-right settings menu.
st.set_page_config(layout='wide', page_title="Owl Retirement Planner")
# st.set_page_config(layout='centered', page_title="Owl Retirement Planner")

kz.init()

st.logo('https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png', size='large')

pages = {
          'Case Setup': [st.Page('Basic_Info.py', icon=':material/person_add:'),
                         st.Page('Assets.py', icon=':material/savings:'),
                         st.Page('Wages_And_Contributions.py', icon=':material/work_history:'),
                         st.Page('Fixed_Income.py', icon=':material/currency_exchange:'),
                         st.Page('Rates_Selection.py', icon=':material/monitoring:'),
                         st.Page('Asset_Allocation.py', icon=':material/percent:'),
                         st.Page('Optimization_Parameters.py', icon=':material/tune:')],
          'Single Scenario': [st.Page('Case_Results.py', icon=':material/directions_run:'),
                              st.Page('Case_Worksheets.py', icon=':material/data_table:'),
                              st.Page('Case_Summary.py', icon=':material/description:')],
          'Multiple Scenarios': [st.Page('Historical_Range.py', icon=':material/history:'),
                                 st.Page('Monte_Carlo.py', icon=':material/finance:')],
          'Resources': [st.Page('Logs.py', icon=':material/error:'),
                        st.Page('Settings.py', icon=':material/settings:'),
                        st.Page('Quick_Start.py', icon=':material/rocket_launch:', default=True),
                        st.Page('Documentation.py', icon=':material/help:'),
                        st.Page('About_Owl.py', icon=':material/info:')],
           }

kz.initGlobalKey('prevPageName', None)
kz.initGlobalKey('currentPageName', None)

pg = st.navigation(pages)
kz.storeGlobalKey('currentPageName', pg.title)
# Workaround resetting dataframes for data_editor wierd behavior.
if pg.title != kz.getGlobalKey('prevPageName') and kz.getGlobalKey('prevPageName') == 'Wages And Contributions':
    if kz.caseHasPlan():
        kz.updateContributions()

pg.run()
kz.storeGlobalKey('prevPageName', pg.title)
