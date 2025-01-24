import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar('historicalRange')
kz.caseHeader("Historical Range")

if ret is None or kz.caseHasNoPlan():
    st.info('Case(s) must be first created before running this page.')
else:
    kz.initKey('hyfrm', owb.FROM)
    kz.initKey('hyto', owb.TO)
    kz.initKey('histoplot', None)
    kz.initKey('histoSummary', None)

    st.write("Generate a histogram of results obtained from backtesting "
             "current scenario with historical data over selected year range.")
    col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='bottom')
    with col1:
        st.number_input('Starting year', min_value=owb.FROM,
                        max_value=kz.getKey('hyto'),
                        value=kz.getKey('hyfrm'),
                        on_change=kz.storepull, args=['hyfrm'], key='_hyfrm')

    with col2:
        st.number_input('Ending year', max_value=owb.TO,
                        min_value=kz.getKey('hyfrm'),
                        value=kz.getKey('hyto'),
                        on_change=kz.storepull, args=['hyto'], key='_hyto')

    # st.divider()
    # col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col4:
        st.button('Run historical range', on_click=owb.runHistorical, disabled=kz.caseIsNotRunReady())

    st.divider()
    fig = kz.getKey('histoPlot')
    if fig is not None:
        col1, col2 = st.columns(2, gap='small')
        col1.pyplot(fig)
        col2.code(kz.getKey('histoSummary'), language=None)
