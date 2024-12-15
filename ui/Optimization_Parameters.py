import streamlit as st

import key as k


st.write('# Optimization Parameters')
col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
with col1:
    iname = st.session_state.iname0
    k.init('maxX0', 1000)
    ret = k.getNum("%s's maximum Roth Conversion ($k)" % iname, 'maxX0')

with col2:
    if st.session_state.status == 'married':
        iname = st.session_state.iname1
        k.init('maxX1', 1000)
        ret = k.getNum("%s's maximum Roth Conversion ($k)" % iname, 'maxX1')

k.init('med', True)
ret = k.getToggle('Medicare and IRMAA calculations', 'med')

choices = ['flat', 'smile']
k.init('profile', choices[1])
ret = k.getRadio("Spending profile", choices, 'profile')

choices = ['Net spending', 'Bequest']
k.init('objective', choices[0])
ret = k.getRadio("Maximize", choices, 'objective')

if st.session_state.objective == 'Net spending':
    k.init('bequest', 0)
    ret = k.getNum("Desire bequest ($k)", 'bequest')

else:
    k.init('spending', 0)
    ret = k.getNum("Desired annual net spending ($k)", 'spending')

