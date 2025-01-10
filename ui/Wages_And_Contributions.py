import streamlit as st
import pandas as pd

import sskeys as k
import owlbridge as owb


def resetTimeLists():
    k.resetTimeLists()
    owb.resetContributions()


ret = k.titleBar('wages')
k.caseHeader("Wages and Contributions")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    if k.getKey('stTimeLists') is None:
        original = k.getKey('timeListsFileName')
        if original is None or original == 'None':
            iname0 = k.getKey('iname0')
            st.info("Case *'%s'* contains no contributions file.\n\n" % k.currentCaseName() +
                    "You can build your own contribution file by starting from this "
                    "[template](https://raw.github.com/mdlacasse/owl/main/examples/template.xlsx). "
                    "Enter your numbers and ensure that the final workbook contains a tab for each "
                    "individual in the plan, "
                    f"i.e., a tab named *{iname0}*, and another one named after the spouse if applicable.")
        else:
            st.info("Case *'%s'* contains contributions file *'%s'* that has not yet been uploaded." %
                    (ik.currentCaseName(), original))

    k.initKey('stTimeLists', None)
    if k.getKey('stTimeLists') is None:
        col1, col2 = st.columns(2, gap='large')
        with col1:
            stTimeLists = st.file_uploader('Upload optional contribution file...', key='_stTimeLists',
                                           type=['xlsx'])
        if stTimeLists is not None:
            if owb.readContributions(stTimeLists):
                k.setKey('stTimeLists', stTimeLists)
                st.rerun()
            st.stop()

    if k.getKey('stTimeLists') is not None:
        k.initKey('timeList0', None)
        if k.getKey('timeList0') is None:
            df0 = pd.read_excel(k.getKey('stTimeLists'), sheet_name=k.getKey('iname0'))
            df0 = df0.fillna(0)
            df0 = df0.iloc[:, range(9)]
            # print('df0', df0)
            k.storeKey('timeList0', df0)

        st.write(k.getKey('iname0'))
        st.dataframe(k.getKey('timeList0'))

        if k.getKey('status') == 'married':
            k.initKey('timeList1', None)
            if k.getKey('timeList1') is None:
                df1 = pd.read_excel(k.getKey('stTimeLists'), sheet_name=k.getKey('iname1'))
                df1 = df1.fillna(0)
                df1 = df1.iloc[:, range(9)]
                k.storeKey('timeList1', df1)

            st.write(k.getKey('iname1'))
            st.dataframe(k.getKey('timeList1'))

    cantdel = (k.getKey('stTimeLists') is None)
    st.button('Reset', on_click=resetTimeLists, disabled=cantdel)
