import streamlit as st
import pandas as pd
import key as k


ret = k.titleBar('fixed')
st.divider()
st.write('## Wages and Contributions')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:

    timeList = st.file_uploader('Upload contribution file')
    if timeList:
        df0 = pd.read_excel(timeList, sheet_name=k.getKey('iname0'))
        st.write(k.getKey('iname0'))
        st.write(df0)
        if k.getKey('status') == 'married':
            df1 = pd.read_excel(timeList, sheet_name=k.getKey('iname1'))
            st.write(k.getKey('iname1'))
            st.write(df1)

