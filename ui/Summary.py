import streamlit as st
import key as k

ret = k.titleBar('fixed')
st.divider()
st.write('## Summary')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write(k.getKey('summary'))
