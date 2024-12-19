import streamlit as st

pg = st.navigation([st.Page('Introduction.py'),
                    st.Page('Case_Setup.py'),
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
