import streamlit as st

import sskeys as k
import owlbridge as owb


ret = k.titleBar('historicalRange')
# st.divider()
st.write("## Historical Range")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    k.init('hyfrm', 1928)
    k.init('hyto', 2023)
    k.init('histoplot', None)

    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='bottom')
    with col1:
        st.number_input('Starting year', min_value=1928,
                        max_value=k.getKey('hyto'),
                        value=k.getKey('hyfrm'),
                        on_change=k.pull, args=['hyfrm'], key='_hyfrm')

    with col2:
        st.number_input('Ending year', max_value=2023,
                        min_value=k.getKey('hyfrm'),
                        value=k.getKey('hyto'),
                        on_change=k.pull, args=['hyto'], key='_hyto')

    # st.divider()
    # col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col3:
        st.button('Run historical range', on_click=owb.runHistorical, disabled=owb.caseIsNotRunReady())

    st.divider()
    fig = k.getKey('histoPlot')
    if fig is not None:
        st.pyplot(fig)
