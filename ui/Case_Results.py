import streamlit as st

import sskeys as k
import owlbridge as owb


ret = k.titleBar('results')
k.caseHeader("Case Results")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='bottom')
    with col1:
        choices = ['nominal', 'today']
        k.initKey('plots', choices[0])
        ret = k.getRadio("Dollar amounts in plots", choices, 'plots',
                         callback=owb.setDefaultPlots)
    with col3:
        if k.caseHasCompletedRun():
            fileName = 'case_'+k.getKey('name')+'.toml'
            download3 = st.download_button(
                label="Download case file...",
                data=owb.saveCaseFile(),
                file_name=fileName,
                disabled=k.caseHasNotCompletedRun(),
                mime='txt/plain'
            )
    with col4:
        st.button('Run single case', on_click=owb.runPlan, disabled=k.caseIsNotRunReady())

    st.divider()
    if k.caseHasCompletedRun():
        owb.plotSingleResults()
    else:
        st.info("Case status is currently '%s'." % k.getKey('caseStatus'))
