import streamlit as st

import sskeys as k
import owlbridge as owb

ret = k.titleBar('worksheets')
st.divider()
st.write('## Case Worksheets')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    owb.showWorkbook()

    download2 = st.download_button(
        label="Download data as Excel workbook...",
        data=owb.saveWorkbook(),
        file_name='workbook_'+k.getKey('name')+'.xlsx',
        mime='application/vnd.ms-excel'
    )

    download3 = st.download_button(
        label="Download configuration file...",
        data=owb.saveConfig(),
        file_name=k.getKey('name')+'.ini',
        mime='txt/plain'
    )
