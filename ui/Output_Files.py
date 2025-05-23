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
        df = kz.compareSummaries()
        if df is not None:
            st.write("#### Synopsis\n"
                     "This table provides a summary of the current case and"
                     " compares it with other similar cases that ran successfully.")
            styledDf = df[1:].style.map(kz.colorBySign)
            st.dataframe(styledDf, use_container_width=True)
            st.caption("Values with [legend] are nominal, otherwise in today's \\$. "
                       "Lines starting with » indicate itemized subtotals.")
            col1, col2 = st.columns(2, gap="large")
            col1.download_button("Download synopsis", data=df[1:].to_string(),
                                 file_name=f"Synopsis_{caseName}.txt", mime="text/plain;charset=UTF-8")

            helpmsg = "Rerun all cases."
            col2.button("Rerun all cases", on_click=owb.runAllCases, help=helpmsg)

        st.divider()
        st.write("#### Excel Workbooks\n"
                 "These workbooks contain time tables describing the flow of money,"
                 " the first one as input to the case, and the second as its output.")
        col1, col2 = st.columns(2, gap="large")
        with col1:
            download2 = st.download_button(
                label="Download Wages and Contributions file",
                help="Download Wages and Contributions as an Excel workbook.",
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
            st.write("#### Case Parameter File\n"
                     "This file contains the parameters characterizing the current case"
                     " and can be used, along with the *Wages and Contributions* file, to reproduce it in the future.")
            st.code(lines, language="toml")

            st.download_button(
                "Download case parameter file", data=lines,
                file_name=f"case_{caseName}.toml", mime="application/toml"
            )
