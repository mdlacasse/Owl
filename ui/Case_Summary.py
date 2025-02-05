import streamlit as st

import sskeys as kz
import owlbridge as owb

ret = kz.titleBar('summary')
kz.caseHeader("Case Summary")

if ret is None or kz.caseHasNoPlan():
    st.info('Case(s) must be first created before running this page.')
else:
    if kz.caseIsRunReady():
        owb.runPlan()

    if kz.caseHasNotCompletedRun():
        st.info("Case status is currently '%s'." % kz.getKey('caseStatus'))
    else:
        lines = kz.getKey('summary')
        if lines != '':
            st.write('#### Synopsis')
            st.code(lines, language=None)
            st.download_button('Download synopsis',
                               data=lines,
                               file_name='Synopsis_'+kz.getKey('name')+'.txt',
                               mime='text/plain;charset=UTF-8')

        lines = kz.getKey('casetoml')
        if lines != '':
            st.divider()
            st.write("#### Case parameter file")
            st.code(lines, language='toml')

            st.download_button('Download case parameter file',
                               data=lines,
                               file_name='case_'+kz.getKey('name')+'.toml',
                               mime='application/toml')

        st.divider()
        st.write("#### Wages and contributions file")
        download2 = st.download_button(
            label="Download wages and contributions file",
            help='Download Excel workbook.',
            data=owb.saveContributions(),
            file_name=kz.getKey('name')+'.xlsx',
            disabled=kz.caseHasNotCompletedRun(),
            mime='application/vnd.ms-excel')
