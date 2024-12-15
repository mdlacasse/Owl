import streamlit as st

st.write('# Logs')

if 'logs' in st.session_state:
    st.write(st.session_state.logs)

