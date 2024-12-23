import streamlit as st

import sskeys as k
import owlbridge as owb


def getIntInput(i, key, text, defval=0):
    nkey = key+str(i)
    k.init(nkey, defval)
    st.number_input(text, min_value=0,
                    value=k.getKey(nkey),
                    on_change=k.pull, args=[nkey], key='_'+nkey)


def getAllocs(i, title, deco):
    tags = ['S&P500', 'Baa', 'T-Notes', 'Cash']
    iname = k.getKey('iname'+str(i))
    st.write("%s's %s allocations (%%)" % (iname, title))
    col1, col2, col3, col4 = st.columns(4, gap='small', vertical_alignment='top')
    with col1:
        getIntInput(i, deco+tags[0], 'S&P 500', 60)
    with col2:
        getIntInput(i, deco+tags[1], 'Corp Bonds', 20)
    with col3:
        getIntInput(i, deco+tags[2], 'T-Notes', 10)
    with col4:
        getIntInput(i, deco+tags[3], 'Cash Assets', 10)
    checkAllocs(i, deco)


def checkAllocs(i, deco):
    tags = ['S&P500', 'Baa', 'T-Notes', 'Cash']
    tot = 0
    for tg in tags:
        tot += int(k.getKey(deco+tg+str(i)))
    if abs(100-tot) > 0:
        st.info('Percentages must add to 100%.')
        return False
    return True


def checkAllAllocs():
    decos = ['init%', 'fin%']
    Ni = 1
    if k.getKey('status') == 'married':
        Ni += 1
    result = True
    for i in range(Ni):
        for deco in decos:
            result = result and checkAllocs(i, deco)
    return result


ret = k.titleBar('allocs')
st.divider()
st.write('## Asset Allocations')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    getAllocs(0, 'initial', 'init%')
    getAllocs(0, 'final', 'fin%')

    if k.getKey('status') == 'married':
        st.divider()
        getAllocs(1, 'initial', 'init%')
        getAllocs(1, 'final', 'fin%')

    st.divider()
    choices = ['linear', 's-curve']
    key = 'interp'
    k.init(key, choices[0])
    k.getRadio('Gliding interpolation method', choices, key)

    st.text(' ')
    plan = k.getKey('plan')
    if plan is not None and checkAllAllocs():
        owb.setInterpolationMethod()
        owb.setAllocationRatios()
        owb.showAllocations()
