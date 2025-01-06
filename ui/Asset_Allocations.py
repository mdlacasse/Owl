import streamlit as st

import sskeys as k
import owlbridge as owb


def getPercentInput(i, j, keybase, text, defval=0):
    nkey = keybase+str(j)+'_'+str(i)
    k.initKey(nkey, defval)
    st.number_input(text, min_value=0, step=1, max_value=100,
                    value=k.getKey(nkey),
                    on_change=k.setpull, args=[nkey], key='_'+nkey)


ACC = ['taxable', 'tax-deferred', 'tax-free']
ASSET = ['S&P 500', 'Corp Bonds Baa', 'T-Notes', 'Cash Assets']
DEF = [60, 20, 10, 10]


def getIndividualAllocs(i, title, deco):
    mydeco = 'j3_' + deco
    iname = k.getKey('iname'+str(i))
    st.write("%s's %s allocations for all accounts (%%)" % (iname, title))
    cols = st.columns(4, gap='large', vertical_alignment='top')
    for k1 in range(4):
        with cols[k1]:
            getPercentInput(i, k1, mydeco, ASSET[k1], DEF[k1])
    checkIndividualAllocs(i, mydeco)


def getAccountAllocs(i, j, title, deco):
    iname = k.getKey('iname'+str(i))
    mydeco = f'j{j}_' + deco
    st.write("%s's %s allocations for %s account (%%)" % (iname, title, ACC[j]))
    cols = st.columns(4, gap='large', vertical_alignment='top')
    for k1 in range(4):
        with cols[k1]:
            getPercentInput(i, k1, mydeco, ASSET[k1], DEF[k1])
    checkAccountAllocs(i, mydeco)


def checkAccountAllocs(i, deco):
    tot = 0
    for k1 in range(4):
        tot += int(k.getKey(deco+str(k1)+'_'+str(i)))
    if abs(100-tot) > 0:
        st.error('Percentages must add to 100%.')
        return False
    return True


def checkIndividualAllocs(i, deco):
    tot = 0
    for k1 in range(4):
        tot += int(k.getKey(deco+str(k1)+'_'+str(i)))
    if abs(100-tot) > 0:
        st.error('Percentages must add to 100%.')
        return False
    return True


def checkAllAllocs():
    if k.getKey('allocType') == 'individual':
        decos = ['j3_init%', 'j3_fin%']
    else:
        decos = ['j0_init%', 'j0_fin%', 'j1_init%', 'j1_fin%', 'j2_init%', 'j2_fin%']
    Ni = 1
    if k.getKey('status') == 'married':
        Ni += 1
    result = True
    for i in range(Ni):
        for deco in decos:
            result = result and checkIndividualAllocs(i, deco)
    return result


ret = k.titleBar('allocs')
k.caseHeader()
st.write("## Asset Allocations")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    choices = ['individual', 'account']
    key = 'allocType'
    k.initKey(key, choices[0])
    ret = k.getRadio('Asset allocation method', choices, key)
    if ret == 'individual':
        st.divider()
        getIndividualAllocs(0, 'initial', 'init%')
        getIndividualAllocs(0, 'final', 'fin%')

        if k.getKey('status') == 'married':
            st.divider()
            getIndividualAllocs(1, 'initial', 'init%')
            getIndividualAllocs(1, 'final', 'fin%')
    else:
        for j in range(3):
            st.divider()
            getAccountAllocs(0, j, 'initial', 'init%')
            getAccountAllocs(0, j, 'final', 'fin%')
        if k.getKey('status') == 'married':
            st.markdown('###')
            for j in range(3):
                st.divider()
                getAccountAllocs(1, j, 'initial', 'init%')
                getAccountAllocs(1, j, 'final', 'fin%')

    st.divider()
    choices = ['linear', 's-curve']
    key = 'interpMethod'
    k.initKey(key, choices[0])
    k.getRadio('Gliding interpolation method', choices, key)

    if k.getKey(key) == choices[1]:
        col1, col2 = st.columns(2, gap='large')
        with col1:
            key = 'interpCenter'
            k.initKey('interpCenter', 15.)
            ret = k.getNum('Center (in years from now)', key, step=1., max_value=30., format='%.0f')
        with col2:
            key = 'interpWidth'
            k.initKey('interpWidth', 5.)
            ret = k.getNum('Width (in +/- years from center)', key, step=1., max_value=15., format='%.0f')

    # st.write('####')
    if checkAllAllocs():
        if k.getKey('caseStatus') != 'solved':
            owb.setInterpolationMethod()
            owb.setAllocationRatios()
        owb.showAllocations()
