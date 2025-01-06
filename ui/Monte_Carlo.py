import streamlit as st

import sskeys as k
import owlbridge as owb


ret = k.titleBar('MC')
k.caseHeader()
st.write("## Monte Carlo")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    if (k.getKey('rateType') != 'varying' or
       (k.getKey('varyingType') is None or 'stochastic' not in k.getKey('varyingType'))):
        st.info('Plan must first be set with stochastic or histochastic rates.')
    else:
        col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='bottom')
        with col1:
            k.initKey('MC_cases', 100)
            k.getIntNum('Number of random instances', 'MC_cases', step=10, max_value=10000)
        with col3:
            st.button('Run Simulation', on_click=owb.runMC, disabled=k.caseIsNotMCReady())

    st.divider()
    fig = k.getKey('monteCarloPlot')
    if fig is not None:
        st.pyplot(fig)
