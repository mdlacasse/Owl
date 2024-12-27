import streamlit as st

import sskeys as k

ret = k.titleBar('assets')
# st.divider()
st.write('## Assets')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('### Account Balances')
    accounts = {'txbl':  'taxable', 'txDef': 'tax-deferred', 'txFree': 'tax-exempt'}
    col1, col2 = st.columns(2, gap='large', vertical_alignment='top')
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
        st.write('### Beneficiary fractions')
        col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
        with col1:
            nkey = 'benf'+str(0)
            k.init(nkey, 1)
            ret = k.getNum(accounts['txbl'].capitalize(), nkey)

        with col2:
            nkey = 'benf'+str(1)
            k.init(nkey, 1)
            ret = k.getNum(accounts['txDef'].capitalize(), nkey)

        with col3:
            nkey = 'benf'+str(2)
            k.init(nkey, 1)
            ret = k.getNum(accounts['txFree'].capitalize(), nkey)
