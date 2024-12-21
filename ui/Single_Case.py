import streamlit as st

import sskeys as k
import owlbridge as owb


def isIncomplete():
    return k.getKey('plan') is None


ret = k.titleBar('single')
st.divider()
st.write("## Single Case")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.button('Run plan', on_click=owb.runPlan, disabled=isIncomplete())

    owb.plotSingleResults()
