import streamlit as st

# Uncomment for wide graphs
# st.set_page_config(layout='wide')

# ret = k.titleBar('main')
# st.divider()

pages = {
          'Case setup': [st.Page('Basic_Info.py', icon=':material/person_add:'),
                         st.Page('Assets.py', icon=':material/savings:'),
                         st.Page('Wages_And_Contributions.py', icon=':material/event_list:'),
                         st.Page('Fixed_Income.py', icon=':material/currency_exchange:'),
                         st.Page('Rate_Selection.py', icon=':material/show_chart:'),
                         st.Page('Asset_Allocations.py', icon=':material/data_table:'),
                         st.Page('Optimization_Parameters.py', icon=':material/cycle:')],
          'Single scenarios': [st.Page('Case_Results.py', icon=':material/ssid_chart:'),
                               st.Page('Case_Worksheets.py', icon=':material/data_table:'),
                               st.Page('Case_Summary.py', icon=':material/description:')],
          'Multiple scenarios': [st.Page('Historical_Range.py', icon=':material/earthquake:'),
                                 st.Page('Monte_Carlo.py', icon=':material/stacked_bar_chart:')],
          'Resources': [st.Page('Logs.py', icon=':material/error:'),
                        st.Page('Documentation.py', icon=':material/question_mark:'),
                        st.Page('About_Owl.py', icon=':material/nature:')],
           }

pg = st.navigation(pages)
pg.run()
