import streamlit as st

import sskeys as k

ret = k.titleBar('worksheets')
st.divider()
st.write('## Case Worksheets')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('Coming soon...')
