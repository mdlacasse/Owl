import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar('MC')
kz.caseHeader("Monte Carlo")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    if (kz.getKey('rateType') != 'varying' or
       (kz.getKey('varyingType') is None or 'stochastic' not in kz.getKey('varyingType'))):
        st.info('Rates must be set to *stochastic* or *histochastic* to run Monte Carlo simulations.')
    else:
        col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='bottom')
        with col1:
            kz.initKey('MC_cases', 100)
            kz.getIntNum('Number of random instances', 'MC_cases', step=10, max_value=10000)
        with col4:
            st.button('Run Simulation', on_click=owb.runMC, disabled=kz.caseIsNotMCReady())

    st.divider()
    fig = kz.getKey('monteCarloPlot')
    if fig is not None:
        col1, col2 = st.columns(2, gap='small')
        col1.pyplot(fig)
        col2.code(kz.getKey('monteCarloSummary'), language=None)
