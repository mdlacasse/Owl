import streamlit as st
import pandas as pd

import key as k
import owlAPI as api


def resetList():
    k.store('timeList', None)
    k.store('timeList0', None)
    if k.getKey('status') == 'married':
        k.store('timeList1', None)


ret = k.titleBar('fixed')
st.divider()
st.write('## Wages and Contributions')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:

    k.init('timeList', None)
    if k.getKey('timeList') is None:
        timeList = st.file_uploader('Upload contribution file')
        k.store('timeList', timeList)
        api.readContributions(timeList)

    if k.getKey('timeList') is not None:
        k.init('timeList0', None)
        if k.getKey('timeList0') is None:
            df0 = pd.read_excel(k.getKey('timeList'), sheet_name=k.getKey('iname0'))
            df0 = df0.fillna(0)
            # print('df0', df0)
            k.store('timeList0', df0)

        st.write(k.getKey('iname0'))
        st.dataframe(k.getKey('timeList0'))

        if k.getKey('status') == 'married':
            k.init('timeList1', None)
            if k.getKey('timeList1') is None:
                df1 = pd.read_excel(k.getKey('timeList'), sheet_name=k.getKey('iname1'))
                df1 = df1.fillna(0)
                k.store('timeList1', df1)

            st.write(k.getKey('iname1'))
            st.dataframe(k.getKey('timeList1'))

    cantdel = (k.getKey('timeList') is None)
    st.button('Reset', on_click=resetList, disabled=cantdel)

