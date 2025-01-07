import streamlit as st

import sskeys as k
import owlbridge as owb


ret = k.titleBar('historicalRange')
k.caseHeader("Historical Range")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    k.initKey('hyfrm', 1928)
    k.initKey('hyto', 2023)
    k.initKey('histoplot', None)

    col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='bottom')
    with col1:
        st.number_input('Starting year', min_value=1928,
                        max_value=k.getKey('hyto'),
                        value=k.getKey('hyfrm'),
                        on_change=k.storepull, args=['hyfrm'], key='_hyfrm')

    with col2:
        st.number_input('Ending year', max_value=2023,
                        min_value=k.getKey('hyfrm'),
                        value=k.getKey('hyto'),
                        on_change=k.storepull, args=['hyto'], key='_hyto')

    # st.divider()
    # col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col4:
        st.button('Run historical range', on_click=owb.runHistorical, disabled=k.caseIsNotRunReady())

    st.divider()
    fig = k.getKey('histoPlot')
    if fig is not None:
        col1, col2 = st.columns(2, gap='small')
        col1.pyplot(fig)
