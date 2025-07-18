import streamlit as st

import sskeys as kz
import owlbridge as owb

ret = kz.titleBar(":material/data_table: Worksheets")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.caseIsRunReady():
        owb.runPlan()
    elif kz.caseHasNotRun():
        st.info("Case definition is not yet complete. Please visit all pages in *Case Setup*.")

    if kz.isCaseUnsolved():
        st.info("Case status is currently '%s'." % kz.getKey("caseStatus"))
    else:
        owb.showWorkbook()
