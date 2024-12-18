import streamlit as st

import key as k

st.write('## Assets')
st.write('## Account Balances')
accounts = {'txbl':  'taxable', 'txDef': 'tax-deferred', 'txFree': 'tax-exempt'}
col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
with col1:
    iname0 = k.getKey('iname0')
    for key in accounts:
        nkey = key+str(0)
        k.init(nkey, 0)
        ret = k.getNum('%s %s account ($k)' % (iname0, accounts[key]), nkey)

with col2:
    if k.getKey('status') == 'married':
        iname1 = k.getKey('iname1')
        for key in accounts:
            nkey = key+str(1)
            k.init(nkey, 0)
            ret = k.getNum('%s %s account ($k)' % (iname1, accounts[key]), nkey)

if k.getKey('status') == 'married':
    st.write('#### Beneficiary fractions')
    col1, col2, col3 = st.columns(3, gap='small', vertical_alignment='top')
    with col1:
        nkey = 'benf'+str(0)
        k.init(nkey, 1)
        ret = k.getNum('Beneficiary fraction (%s)' % accounts['txbl'], nkey)

    with col2:
        nkey = 'benf'+str(1)
        k.init(nkey, 1)
        ret = k.getNum('Beneficiary fraction (%s)' % accounts['txDef'], nkey)

    with col3:
        nkey = 'benf'+str(2)
        k.init(nkey, 1)
        ret = k.getNum('Beneficiary fraction (%s)' % accounts['txFree'], nkey)
