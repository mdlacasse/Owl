import streamlit as st

import sskeys as kz
import owlbridge as owb

ret = kz.titleBar("Output Files")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.caseIsRunReady():
        owb.runPlan()

    if kz.isCaseUnsolved():
        st.info("Case status is currently '%s'." % kz.getKey("caseStatus"))
    else:
        caseName = kz.getKey("name")
        lines = kz.getKey("summary")
        if lines != "":
            st.write("#### Synopsis")
            st.code(lines, language=None)
            st.download_button(
                "Download synopsis", data=lines, file_name=f"Synopsis_{caseName}.txt",
                mime="text/plain;charset=UTF-8"
            )

        st.divider()
        st.write("#### Excel workbooks")
        col1, col2 = st.columns(2, gap="large")
        with col1:
            download2 = st.download_button(
                label="Download wages and contributions file",
                help="Download wages and contributions as an Excel workbook.",
                data=owb.saveContributions(),
                file_name=f"{caseName}.xlsx",
                disabled=kz.isCaseUnsolved(),
                mime="application/vnd.ms-excel",
            )

        with col2:
            download2 = st.download_button(
                label="Download worksheets",
                help="Download worksheets as an Excel workbook.",
                data=owb.saveWorkbook(),
                file_name=f"Workbook_{caseName}.xlsx",
                mime="application/vnd.ms-excel",
                disabled=kz.isCaseUnsolved(),
            )

        lines = kz.getKey("casetoml")
        if lines != "":
            st.divider()
            st.write("#### Case parameter file")
            st.code(lines, language="toml")

            st.download_button(
                "Download case parameter file", data=lines,
                file_name=f"case_{caseName}.toml", mime="application/toml"
            )
