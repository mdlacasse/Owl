import streamlit as st

import sskeys as k
import owlbridge as owb


def getIntInput(i, j, keybase, text, defval=0):
    nkey = keybase+str(j)+'_'+str(i)
    k.initKey(nkey, defval)
    st.number_input(text, min_value=0, step=1, max_value=100,
                    value=k.getKey(nkey),
                    on_change=k.setpull, args=[nkey], key='_'+nkey)


def getAllocs(i, title, deco):
    iname = k.getKey('iname'+str(i))
    st.write("%s's %s allocations (%%)" % (iname, title))
    col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='top')
    with col1:
        getIntInput(i, 0, deco, 'S&P 500', 60)
    with col2:
        getIntInput(i, 1, deco, 'Corp Bonds', 20)
    with col3:
        getIntInput(i, 2, deco, 'T-Notes', 10)
    with col4:
        getIntInput(i, 3, deco, 'Cash Assets', 10)
    checkAllocs(i, deco)


def checkAllocs(i, deco):
    tot = 0
    for j in range(4):
        tot += int(k.getKey(deco+str(j)+'_'+str(i)))
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
    k.initKey(key, choices[0])
    k.getRadio('Gliding interpolation method', choices, key)

    if k.getKey(key) == choices[1]:
        col1, col2 = st.columns(2, gap='large')
        with col1:
            key = 'center'
            k.initKey('center', 15.)
            ret = k.getNum('Center', key, step=1., max_value=30., format='%.0f')
        with col2:
            key = 'width'
            k.initKey('width', 5.)
            ret = k.getNum('Width', key, step=1., max_value=15., format='%.0f')

    # st.write('####')
    if checkAllAllocs():
        if k.getKey('caseStatus') != 'solved':
            owb.setInterpolationMethod()
            owb.setAllocationRatios()
        owb.showAllocations()
