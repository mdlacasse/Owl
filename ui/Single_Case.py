import streamlit as st

import key as k
import owlAPI as api

def isIncomplete():
    return k.getKey('plan') is None


ret = k.titleBar('single')
st.divider()
st.write("## Single Case")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    pass
    # st.button('Run plan', on_click=genPlan, disabled=isIncomplete())


