import streamlit as st

import sskeys as kz


ret = kz.titleBar(":material/error: Logs")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    strio = kz.getCaseKey("logs")
    if strio is not None:
        logmsg = strio.getvalue()
        st.code(logmsg, language=None)
