import streamlit as st

import sskeys as kz
import owlbridge as owb

ret = kz.titleBar('worksheets')
kz.caseHeader("Worksheets")

if ret is None or kz.caseHasNoPlan():
    st.info('Case(s) must be first created before running this page.')
else:
    if kz.caseIsRunReady():
        owb.runPlan()

    if kz.caseHasNotCompletedRun():
        st.info("Case status is currently '%s'." % kz.getKey('caseStatus'))
    else:
        owb.showWorkbook()
        st.divider()
        if kz.caseHasPlan():
            download2 = st.download_button(
                label="Download data as an Excel workbook...",
                data=owb.saveWorkbook(),
                file_name='Workbook_'+kz.getKey('name')+'.xlsx',
                mime='application/vnd.ms-excel',
                disabled=kz.isCaseUnsolved()
            )
