import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar(":material/stacked_line_chart: Graphs")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.caseIsRunReady():
        owb.runPlan()
    elif kz.caseHasNotRun():
        st.info("Case definition is not yet complete. Please visit all pages in *Case Setup*.")

    st.write("Optimize a single scenario based on the parameters selected in the **Case Setup** section.")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="bottom")
    with col1:
        choices = ["nominal", "today"]
        kz.initKey("plots", choices[0])
        helpmsg = "Plot can be in today's dollars or in nominal value."
        ret = kz.getRadio("Dollar amounts in plots", choices, "plots", help=helpmsg,
                          callback=owb.setDefaultPlots)

    with col3:
        helpmsg = "Click on button if graphs are not all showing."
        st.button(
            "Re-run single case",
            help=helpmsg,
            on_click=owb.runPlan,
            disabled=kz.caseIsNotRunReady(),
        )

    st.divider()
    if kz.isCaseUnsolved():
        st.info("Case status is currently '%s'." % kz.getKey("caseStatus"))
    else:
        owb.plotSingleResults()
