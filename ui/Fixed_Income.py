import streamlit as st

import sskeys as kz


def getIntInput(i, key, text, defval=0):
    nkey = key+str(i)
    kz.initKey(nkey, defval)
    inamex = kz.getKey('iname'+str(i))
    st.number_input("%s's %s" % (inamex, text), min_value=0,
                    value=kz.getKey(nkey),
                    on_change=kz.setpull, args=[nkey], key='_'+nkey)


def getFloatInput(i, key, text, defval=0.):
    nkey = key+str(i)
    kz.initKey(nkey, defval)
    inamex = kz.getKey('iname'+str(i))
    st.number_input("%s's %s" % (inamex, text), min_value=0., help=kz.help1000,
                    value=float(kz.getKey(nkey)), format='%.1f', step=10.,
                    on_change=kz.setpull, args=[nkey], key='_'+nkey)


ret = kz.titleBar('fixed')
kz.caseHeader("Fixed Income")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('### Social Security')
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        getFloatInput(0, 'ssAmt', 'social security annual amount (\\$k)')
        getIntInput(0, 'ssAge', 'social security age', 67)

    with col2:
        if kz.getKey('status') == 'married':
            getFloatInput(1, 'ssAmt', 'social security annual amount (\\$k)')
            getIntInput(1, 'ssAge', 'social security age', 67)

    st.divider()
    st.write('### Pension')
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        getFloatInput(0, 'pAmt', 'pension annual amount (\\$k)')
        getIntInput(0, 'pAge', 'pension age', 65)

    with col2:
        if kz.getKey('status') == 'married':
            getFloatInput(1, 'pAmt', 'pension annual amount (\\$k)')
            getIntInput(1, 'pAge', 'pension age', 65)
