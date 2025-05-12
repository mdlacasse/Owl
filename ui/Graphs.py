import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar("Graphs")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.caseIsRunReady():
        owb.runPlan()

    st.write("Optimize a single scenario based on the parameters selected in the **Case Setup** section.")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="bottom")
    with col1:
        choices = ["nominal", "today"]
        kz.initKey("plots", choices[0])
        helpmsg = "Plot can be in today's dollars or in nominal value."
        ret = kz.getRadio("Dollar amounts in plots", choices, "plots", help=helpmsg, callback=owb.setDefaultPlots)

    with col2:
        choices = ["matplotlib", "plotly"]
        kz.initKey("plotBackend", choices[0])
        helpmsg = "Select the plotting library to use (still experimental)."
        kz.getRadio("Plot Backend", choices, "plotBackend", callback=owb.setPlotBackend, help=helpmsg)

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
