import streamlit as st
import pandas as pd
import key as k


# k.dump()
st.write('## Wages and Contributions')

if k.getKey('iname0') == '':
    st.info('Basic Information must be filled before loading file.')
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

