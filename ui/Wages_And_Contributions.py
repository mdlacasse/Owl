import streamlit as st
import pandas as pd
import key as k


# k.dump()
st.write('## Wages and Contributions')

if st.session_state.iname0 == '':
    st.info('Basic Information must be filled before loading file.')
else:
    timeList = st.file_uploader('Upload contribution file')
    if timeList:
        df0 = pd.read_excel(timeList, sheet_name=st.session_state['iname0'])
        st.write(st.session_state['iname0'])
        st.write(df0)
        if st.session_state['status'] == 'married':
            df1 = pd.read_excel(timeList, sheet_name=st.session_state['iname1'])
            st.write(st.session_state['iname1'])
            st.write(df1)

