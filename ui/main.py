import streamlit as st
import key as k

k.init('iname0', '')
k.init('iname1', '')
k.init('status', 'single')

pg = st.navigation([st.Page('Introduction.py'),
                    st.Page('Basic_Information.py'),
                    st.Page('Assets.py'),
                    st.Page('Wages_And_Contributions.py'),
                    st.Page('Fixed_Income.py'),
                    st.Page('Rate_Selection.py'),
                    st.Page('Asset_Allocations.py'),
                    st.Page('Optimization_Parameters.py'),
                    st.Page('Single_Case.py'),
                    st.Page('Monte_Carlo.py'),
                    st.Page('Summary.py'),
                    st.Page('Logs.py'),
                    ])
pg.run()
