import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar('results')
kz.caseHeader("Case Results")

if ret is None or kz.caseHasNoPlan():
    st.info('Case(s) must be first created before running this page.')
else:
    st.write("Optimize a single scenario based on the parameters selected in the *Case setup* section.")
    col1, col2 = st.columns(2, gap='large', vertical_alignment='bottom')
    with col1:
        choices = ['nominal', 'today']
        kz.initKey('plots', choices[0])
        ret = kz.getRadio("Dollar amounts in plots", choices, 'plots',
                          callback=owb.setDefaultPlots)

    with col2:
        st.button('Run single case', help='Optimize single scenario.',
                  on_click=owb.runPlan, disabled=kz.caseIsNotRunReady())

    st.divider()
    if kz.caseHasNotCompletedRun():
        st.info("Case status is currently '%s'." % kz.getKey('caseStatus'))
    else:
        owb.plotSingleResults()

        st.divider()
        col1, col2 = st.columns(2, gap='large', vertical_alignment='bottom')
        with col1:
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
            download2 = st.download_button(
                label="Download wages and contributions file...",
                help='Download Excel workbook.',
                data=owb.saveContributions(),
                file_name=kz.getKey('name')+'.xlsx',
                disabled=kz.caseHasNotCompletedRun(),
                mime='application/vnd.ms-excel'
            )
