import streamlit as st

import sskeys as k
import owlbridge as owb


ret = k.titleBar('MC')
st.write("## Monte Carlo")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    if (k.getKey('rateType') != 'varying' and
       (k.getKey('varyingType') is None or 'histo' not in k.getKey('varyingType'))):
        st.info('Plan must first be set with stochastic or histochastic rates.')
    else:
        col1, col2 = st.columns(2, gap='large', vertical_alignment='bottom')
        with col1:
            k.init('MC_cases', 100)
            k.getIntNum('Number of random instances', 'MC_cases', step=10, max_value=10000)
        with col2:
            st.button('Run Simulation', on_click=owb.runMC, disabled=owb.caseIsNotMCReady())

    st.divider()
    fig = k.getKey('monteCarloPlot')
    if fig is not None:
        st.pyplot(fig)
