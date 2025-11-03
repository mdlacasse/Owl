import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar(":material/history: Historical Range")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    kz.initCaseKey("hyfrm", owb.FROM)
    kz.initCaseKey("hyto", owb.TO)
    kz.initCaseKey("histoPlot", None)
    kz.initCaseKey("histoSummary", None)

    st.write(
        "Generate a histogram of results obtained from backtesting "
        "current scenario with historical data over selected year range."
    )
    col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="bottom")
    with col1:
        st.number_input(
            "Starting year",
            min_value=owb.FROM,
            max_value=kz.getCaseKey("hyto"),
            value=kz.getCaseKey("hyfrm"),
            on_change=kz.storepull,
            args=["hyfrm"],
            key=kz.genCaseKey("hyfrm"),
        )

    with col2:
        st.number_input(
            "Ending year",
            max_value=owb.TO,
            min_value=kz.getCaseKey("hyfrm"),
            value=kz.getCaseKey("hyto"),
            on_change=kz.storepull,
            args=["hyto"],
            key=kz.genCaseKey("hyto"),
        )

    # st.divider()
    # col1, col2 = st.columns(2, gap="small", vertical_alignment="top")
    with col4:
        st.button("Run historical range", on_click=owb.runHistorical, disabled=kz.caseIsNotRunReady())

    st.divider()
    fig = kz.getCaseKey("histoPlot")
    if fig:
        col1, col2 = st.columns(2, gap="medium")
        owb.renderPlot(fig, col1)
        col2.code(kz.getCaseKey("histoSummary"), language=None)
