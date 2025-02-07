import streamlit as st

import sskeys as kz


def getIntInput(i, key, thing, defval=0):
    nkey = key+str(i)
    kz.initKey(nkey, defval)
    inamex = kz.getKey('iname'+str(i))
    st.number_input(f"{inamex}'s {thing}", min_value=0,
                    value=kz.getKey(nkey),
                    on_change=kz.setpull, args=[nkey], key='_'+nkey)


def getFloatInput(i, key, thing, defval=0.):
    nkey = key+str(i)
    kz.initKey(nkey, defval)
    inamex = kz.getKey('iname'+str(i))
    st.number_input(f"{inamex}'s {thing}", min_value=0., help=kz.help1000,
                    value=float(kz.getKey(nkey)), format='%.1f', step=10.,
                    on_change=kz.setpull, args=[nkey], key='_'+nkey)


def getToggleInput(i, key, thing):
    nkey = key+str(i)
    kz.initKey(nkey, False)
    defval = kz.getKey(nkey)
    st.toggle(thing, on_change=kz.setpull, value=defval, args=[nkey], key='_'+nkey)


ret = kz.titleBar('fixed')
kz.caseHeader("Fixed Income")

if ret is None or kz.caseHasNoPlan():
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('#### Social Security')
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        getFloatInput(0, 'ssAmt', 'social security annual amount (\\$k)')
        getIntInput(0, 'ssAge', 'social security age', 67)

    with col2:
        if kz.getKey('status') == 'married':
            getFloatInput(1, 'ssAmt', 'social security annual amount (\\$k)')
            getIntInput(1, 'ssAge', 'social security age', 67)

    st.divider()
    st.write('#### Pension')
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        getFloatInput(0, 'pAmt', 'pension annual amount (\\$k)')
        getIntInput(0, 'pAge', 'pension age', 65)
        getToggleInput(0, 'pIdx', 'Inflafion adjusted')

    with col2:
        if kz.getKey('status') == 'married':
            getFloatInput(1, 'pAmt', 'pension annual amount (\\$k)')
            getIntInput(1, 'pAge', 'pension age', 65)
            getToggleInput(1, 'pIdx', 'Inflafion adjusted')
