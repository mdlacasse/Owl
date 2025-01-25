import streamlit as st

import sskeys as kz

ret = kz.titleBar('summary')
kz.caseHeader("Case Summary")

if ret is None or kz.caseHasNoPlan():
    st.info('Case(s) must be first created before running this page.')
else:
    if kz.caseHasNotCompletedRun():
        st.info("Case status is currently '%s'." % kz.getKey('caseStatus'))
    else:
        lines = kz.getKey('summary')
        if lines != '':
            st.code(lines, language=None)
            st.divider()
            st.download_button('Download Summary',
                               data=lines,
                               file_name='Summary_'+kz.getKey('name')+'.txt',
                               mime='text/plain;charset=UTF-8')
