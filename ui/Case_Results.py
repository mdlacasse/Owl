import streamlit as st

import sskeys as k
import owlbridge as owb


ret = k.titleBar('results')
st.write("## Case Results")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        st.button('Run single case', on_click=owb.runPlan, disabled=owb.caseIsNotRunReady())
    with col2:
        if owb.caseIsSolved():
            download3 = st.download_button(
                label="Download case file...",
                data=owb.saveCaseFile(),
                file_name = 'case_' + k.getKey('name')+'.toml',
                disabled=k.caseHasNotCompletedRun(),
                mime='txt/plain'
            )
    with col3:
        choices = ['nominal', 'today']
        k.initKey('plots', choices[0])
        ret = k.getRadio("Dollar amounts in plots", choices, 'plots',
                         callback=owb.setDefaultPlots)

    st.divider()
    if owb.caseHasFailed():
        st.info("Case status is currently '%s'." % owb.caseStatus())
    else:
        owb.plotSingleResults()
