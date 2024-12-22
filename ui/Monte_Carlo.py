import streamlit as st

import sskeys as k


ret = k.titleBar('MC')
st.divider()
st.write("## Monte Carlo")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('#### Coming soon!')
