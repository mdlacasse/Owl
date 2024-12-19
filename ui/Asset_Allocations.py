import streamlit as st
import key as k

ret = k.titleBar('allocs')
st.divider()
st.write('## Asset Allocations')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('#### What next?')
