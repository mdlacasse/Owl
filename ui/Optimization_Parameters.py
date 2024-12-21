import streamlit as st

import sskeys as k
import owlbridge as owb


ret = k.titleBar('opto')
st.divider()
st.write('## Optimization Parameters')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        iname0 = k.getKey('iname0')
        k.init('maxRothConversion', 50)
        ret = k.getNum("Maximum Roth conversion ($k)", 'maxRothConversion')

    with col2:
        if k.getKey('status') == 'married':
            iname1 = k.getKey('iname1')
            choices = ['None', iname0, iname1]
            k.init('noRothConversions', choices[0])
            ret = k.getRadio("Exclude Roth conversions for...", choices, 'noRothConversions')

    st.divider()
    k.init('withMedicare', True)
    ret = k.getToggle('Medicare and IRMAA calculations', 'withMedicare')

    st.divider()
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        choices = ['flat', 'smile']
        k.init('profile', choices[1])
        ret = k.getRadio("Spending profile", choices, 'profile')

    with col2:
        k.init('survivor', 60)
        ret = k.getIntNum("Survivor's spending (%)", 'survivor')

    st.divider()
    owb.showProfile()

    st.divider()
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        choices = ['Net spending', 'Bequest']
        k.init('objective', choices[0])
        ret = k.getRadio("Maximize", choices, 'objective')

    with col2:
        if k.getKey('objective') == 'Net spending':
            k.init('bequest', 0)
            ret = k.getNum("Desired bequest ($k)", 'bequest')

        else:
            k.init('netSpending', 0)
            ret = k.getNum("Desired annual net spending ($k)", 'netSpending')