import streamlit as st
import pandas as pd

import key as k
import owlplanner as owl

ret = k.titleBar('MC')
st.divider()
st.write("## Monte Carlo")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('#### What next?')

