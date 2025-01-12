import streamlit as st
import pandas as pd

import sskeys as kz
import owlbridge as owb


def resetTimeLists():
    kz.resetTimeLists()
    owb.resetContributions()


ret = kz.titleBar('wages')
kz.caseHeader("Wages and Contributions")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    if kz.getKey('stTimeLists') is None:
        original = kz.getKey('timeListsFileName')
        if original is None or original == 'None':
            iname0 = kz.getKey('iname0')
            st.info("Case *'%s'* contains no contributions file.\n\n" % kz.currentCaseName() +
                    "You can build your own contribution file by starting from this "
                    "[template](https://raw.github.com/mdlacasse/Owl/main/examples/template.xlsx). "
                    "Enter your numbers and ensure that the final workbook contains a tab for each "
                    "individual in the plan, "
                    f"i.e., a tab named *{iname0}*, and another one named after the spouse if applicable. "
                    "If no file is uploaded, zero will be used for all values "
                    "(anticipated wages, savings contributions, and big-ticket items)."
                    )
        else:
            st.info("Case *'%s'* contains contributions file *'%s'* that has not yet been uploaded." %
                    (kz.currentCaseName(), original))

    kz.initKey('stTimeLists', None)
    if kz.getKey('stTimeLists') is None:
        col1, col2 = st.columns(2, gap='large')
        with col1:
            stTimeLists = st.file_uploader('Upload optional contribution file...', key='_stTimeLists',
                                           type=['xlsx'])
        if stTimeLists is not None:
            if owb.readContributions(stTimeLists):
                kz.setKey('stTimeLists', stTimeLists)
                st.rerun()
            st.stop()

    if kz.getKey('stTimeLists') is not None:
        kz.initKey('timeList0', None)
        if kz.getKey('timeList0') is None:
            df0 = pd.read_excel(kz.getKey('stTimeLists'), sheet_name=kz.getKey('iname0'))
            df0 = df0.fillna(0)
            df0 = df0.iloc[:, range(9)]
            # print('df0', df0)
            kz.storeKey('timeList0', df0)

        st.write(kz.getKey('iname0'))
        st.dataframe(kz.getKey('timeList0'))

        if kz.getKey('status') == 'married':
            kz.initKey('timeList1', None)
            if kz.getKey('timeList1') is None:
                df1 = pd.read_excel(kz.getKey('stTimeLists'), sheet_name=kz.getKey('iname1'))
                df1 = df1.fillna(0)
                df1 = df1.iloc[:, range(9)]
                kz.storeKey('timeList1', df1)

            st.write(kz.getKey('iname1'))
            st.dataframe(kz.getKey('timeList1'))

    cantdel = (kz.getKey('stTimeLists') is None)
    st.button('Reset', on_click=resetTimeLists, disabled=cantdel)
