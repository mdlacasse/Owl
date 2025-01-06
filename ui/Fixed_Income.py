import streamlit as st

import sskeys as k


def getIntInput(i, key, text, defval=0):
    nkey = key+str(i)
    k.initKey(nkey, defval)
    inamex = k.getKey('iname'+str(i))
    st.number_input("%s's %s" % (inamex, text), min_value=0,
                    value=k.getKey(nkey),
                    on_change=k.setpull, args=[nkey], key='_'+nkey)


def getFloatInput(i, key, text, defval=0.):
    nkey = key+str(i)
    k.initKey(nkey, defval)
    inamex = k.getKey('iname'+str(i))
    st.number_input("%s's %s" % (inamex, text), min_value=0., help=k.help1000,
                    value=float(k.getKey(nkey)), format='%.1f', step=10.,
                    on_change=k.setpull, args=[nkey], key='_'+nkey)


ret = k.titleBar('fixed')
k.caseHeader()
st.write("## Fixed Income")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('### Social Security')
    col1, col2 = st.columns(2, gap='large', vertical_alignment='top')
    with col1:
        getFloatInput(0, 'ssAmt', 'social security annual amount (k$)')
        getIntInput(0, 'ssAge', 'social security age', 67)

    with col2:
        if k.getKey('status') == 'married':
            getFloatInput(1, 'ssAmt', 'social security annual amount (k$)')
            getIntInput(1, 'ssAge', 'social security age', 67)

    st.write('### Pension')
    col1, col2 = st.columns(2, gap='large', vertical_alignment='top')
    with col1:
        getFloatInput(0, 'pAmt', 'pension annual amount (k$)')
        getIntInput(0, 'pAge', 'pension age', 65)

    with col2:
        if k.getKey('status') == 'married':
            getFloatInput(1, 'pAmt', 'pension annual amount (k$)')
            getIntInput(1, 'pAge', 'pension age', 65)
