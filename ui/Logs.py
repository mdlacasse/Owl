import streamlit as st

import sskeys as k


ret = k.titleBar('logs')
st.write('## Logs')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    strio = k.getKey('logs')
    if strio is not None:
        logmsg = strio.getvalue()
        st.text(logmsg)
