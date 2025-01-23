import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar('results')
kz.caseHeader("Case Results")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write("Optimize a single scenario based on the parameters selected in the *Case setup* section.")
    col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='bottom')
    with col1:
        choices = ['nominal', 'today']
        kz.initKey('plots', choices[0])
        ret = kz.getRadio("Dollar amounts in plots", choices, 'plots',
                          callback=owb.setDefaultPlots)
    with col4:
        if kz.caseHasCompletedRun():
            download2 = st.download_button(
                label="Download wages and contributions...",
                help='Download Excel workbook.',
                data=owb.saveContributions(),
                file_name=kz.getKey('name')+'.xlsx',
                mime='application/vnd.ms-excel'
            )
    with col3:
        if kz.caseHasCompletedRun():
            fileName = 'case_'+kz.getKey('name')+'.toml'
            download3 = st.download_button(
                label="Download case file...",
                help='Download TOML file.',
                data=owb.saveCaseFile(),
                file_name=fileName,
                disabled=kz.caseHasNotCompletedRun(),
                mime='txt/plain'
            )
    with col2:
        st.button('Run single case', help='Optimize single scenario.',
                  on_click=owb.runPlan, disabled=kz.caseIsNotRunReady())

    st.divider()
    if kz.caseHasCompletedRun():
        owb.plotSingleResults()
    else:
        st.info("Case status is currently '%s'." % kz.getKey('caseStatus'))
