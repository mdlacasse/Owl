import streamlit as st

import sskeys as k
import owlbridge as owb

ret = k.titleBar('worksheets')
k.caseHeader("Case Worksheets")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    owb.showWorkbook()

    st.divider()
    # if not owb.isCaseUnsolved():
    download2 = st.download_button(
        label="Download data as an Excel workbook...",
        data=owb.saveWorkbook(),
        file_name='Workbook_'+k.getKey('name')+'.xlsx',
        mime='application/vnd.ms-excel',
        disabled=owb.isCaseUnsolved()
    )
