import streamlit as st

import sskeys as k
import owlbridge as owb


def isIncomplete():
    return k.getKey('plan') is None


ret = k.titleBar('results')
st.divider()
st.write("## Case Results")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        st.button('Run plan', on_click=owb.runPlan, disabled=isIncomplete())
    with col2:
        choices = ['nominal', 'today']
        k.init('plots', choices[0])
        ret = k.getRadio("Dollar amounts in plots", choices, 'plots',
                         callback=owb.setDefaultPlots)

    st.divider()
    owb.plotSingleResults()
