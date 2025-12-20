import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar(":material/finance: Monte Carlo")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.getCaseKey("rateType") != "varying" or (
        kz.getCaseKey("varyingType") is None or "stochastic" not in kz.getCaseKey("varyingType")
    ):
        st.info("Rates must be set to *stochastic* or *histochastic* to run Monte Carlo simulations.")
    else:
        st.markdown("Generate a histogram of results obtained from running mutliple scenarios with stochastic rates.")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="bottom")
        with col1:
            kz.initCaseKey("MC_cases", 100)
            kz.getIntNum("Number of random instances", "MC_cases", step=10, max_value=10000)
        with col4:
            st.button("Run Simulation", on_click=owb.runMC, disabled=kz.caseIsNotMCReady())

    st.divider()
    fig = kz.getCaseKey("monteCarloPlot")
    if fig:
        col1, col2 = st.columns(2, gap="medium")
        owb.renderPlot(fig, col1)
        col2.code(kz.getCaseKey("monteCarloSummary"), language=None)
