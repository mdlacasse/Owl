import streamlit as st

import key as k


def getIntInput(i, key, text, defval=0):
    nkey = key+str(i)
    k.init(nkey, defval)
    iname = k.getKey('iname'+str(i))
    ret = st.number_input("%s's %s" % (iname, text), min_value=0,
                          value=k.getKey(nkey),
                          on_change=k.pull, args=[nkey], key='_'+nkey)


def getFloatInput(i, key, text, defval=0.):
    nkey = key+str(i)
    k.init(nkey, defval)
    iname = k.getKey('iname'+str(i))
    ret = st.number_input("%s's %s" % (iname, text), min_value=0.,
                          value=float(k.getKey(nkey)), format='%.1f', step=10.,
                          on_change=k.pull, args=[nkey], key='_'+nkey)


ret = k.titleBar('fixed')
st.divider()
st.write('## Fixed Income')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('### Social Security')
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        getIntInput(0, 'ssAge', 'social security age', 67)
        getFloatInput(0, 'ssAmt', 'social security amount (k$)')

    with col2:
        if k.getKey('status') == 'married':
            getIntInput(1, 'ssAge', 'social security age', 67)
            getFloatInput(1, 'ssAmt', 'social security amount (k$)')
    
    st.write('### Pension')
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        getIntInput(0, 'pAge', 'pension age', 65)
        getFloatInput(0, 'pAmt', 'social security amount (k$)')

    with col2:
        if k.getKey('status') == 'married':
            getIntInput(1, 'pAge', 'pension age', 65)
            getFloatInput(1, 'pAmt', 'social security amount (k$)')

