import streamlit as st

import sskeys as kz


ret = kz.titleBar('logs')
kz.caseHeader("Logs")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    strio = kz.getKey('logs')
    if strio is not None:
        logmsg = strio.getvalue()
        st.code(logmsg, language=None)
