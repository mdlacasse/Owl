import streamlit as st

import sskeys as k


ret = k.titleBar('logs')
st.write("## Logs\n:orange[*%s*]" % k.currentCaseName())

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    strio = k.getKey('logs')
    if strio is not None:
        logmsg = strio.getvalue()
        st.code(logmsg, language=None)
