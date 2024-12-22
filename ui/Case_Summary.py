import streamlit as st

import sskeys as k

ret = k.titleBar('summary')
st.divider()
st.write('## Summary')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    lines = k.getKey('summary')
    if lines != '':
        st.text(lines)
        st.download_button('Download Summary',
                           data=lines,
                           file_name='Summary_'+k.getKey('name')+'.txt',
                           mime='text/plain;charset=UTF-8')
