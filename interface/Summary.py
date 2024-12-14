import streamlit as st
import key as k

st.write('# Summary')

k.init('summary', '')

st.write(st.session_state.summary)
