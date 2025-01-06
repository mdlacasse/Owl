import streamlit as st

import sskeys as k

# Pick one for narrow or wide graphs. That can be changed in upper-right settings menu.
# st.set_page_config(layout='wide')
# st.set_page_config(layout='centered')

k.init()

pages = {
          'Case setup': [st.Page('Basic_Info.py', icon=':material/person_add:'),
                         st.Page('Assets.py', icon=':material/savings:'),
                         st.Page('Wages_And_Contributions.py', icon=':material/work_history:'),
                         st.Page('Fixed_Income.py', icon=':material/currency_exchange:'),
                         st.Page('Rate_Selection.py', icon=':material/monitoring:'),
                         st.Page('Asset_Allocations.py', icon=':material/percent:'),
                         st.Page('Optimization_Parameters.py', icon=':material/tune:')],
          'Single scenarios': [st.Page('Case_Results.py', icon=':material/directions_run:'),
                               st.Page('Case_Worksheets.py', icon=':material/data_table:'),
                               st.Page('Case_Summary.py', icon=':material/description:')],
          'Multiple scenarios': [st.Page('Historical_Range.py', icon=':material/history:'),
                                 st.Page('Monte_Carlo.py', icon=':material/finance:')],
          'Resources': [st.Page('Logs.py', icon=':material/error:'),
                        st.Page('Documentation.py', icon=':material/help:'),
                        st.Page('About_Owl.py', icon=':material/info:')],
           }

pg = st.navigation(pages)
pg.run()
