import streamlit as st

import key as k
import owlAPI as api


ret = k.titleBar('opto')
st.divider()
st.write('## Optimization Parameters')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        iname = k.getKey('iname0')
        k.init('maxX0', 50)
        ret = k.getNum("%s's maximum Roth conversion ($k)" % iname, 'maxX0')

    with col2:
        if k.getKey('status') == 'married':
            iname = k.getKey('iname1')
            k.init('maxX1', 50)
            ret = k.getNum("%s's maximum Roth conversion ($k)" % iname, 'maxX1')

    st.divider()
    k.init('med', True)
    ret = k.getToggle('Medicare and IRMAA calculations', 'med')

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
    api.showProfile()

    st.divider()
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        choices = ['Net spending', 'Bequest']
        k.init('objective', choices[0])
        ret = k.getRadio("Maximize", choices, 'objective')

    with col2:
        if k.getKey('objective') == 'Net spending':
            k.init('bequest', 0)
            ret = k.getNum("Desire bequest ($k)", 'bequest')

        else:
            k.init('spending', 0)
            ret = k.getNum("Desired annual net spending ($k)", 'spending')

