import streamlit as st

import key as k


ret = k.titleBar('logs')
st.divider()
st.write('## Logs')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    if 'logs' in st.session_state:
        st.write(st.session_state.logs)

