import streamlit as st

import sskeys as k


ret = k.titleBar('historicalRange')
st.divider()
st.write("## Historical Range")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('#### Coming soon!')
