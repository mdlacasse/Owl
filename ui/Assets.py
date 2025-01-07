import streamlit as st

import sskeys as k

ret = k.titleBar('assets')
k.caseHeader("Assets")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('#### Savings Account Balances')
    accounts = {'txbl':  'taxable', 'txDef': 'tax-deferred', 'txFree': 'tax-exempt'}
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        iname0 = k.getKey('iname0')
        for key in accounts:
            nkey = key+str(0)
            k.initKey(nkey, 0)
            ret = k.getNum("%s's %s account ($k)" % (iname0, accounts[key]), nkey, help=k.help1000)

    with col2:
        if k.getKey('status') == 'married':
            iname1 = k.getKey('iname1')
            for key in accounts:
                nkey = key+str(1)
                k.initKey(nkey, 0)
                ret = k.getNum("%s's %s account ($k)" % (iname1, accounts[key]), nkey, help=k.help1000)

    if k.getKey('status') == 'married':
        st.divider()
        st.write("##### Survivor's spousal beneficiary fractions")
        col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
        with col1:
            nkey = 'benf'+str(0)
            k.initKey(nkey, 1)
            helpmsg = 'Fraction of account left to surviving spouse.'
            ret = k.getNum(accounts['txbl'].capitalize(), nkey, format='%.2f', max_value=1.,
                           step=0.05, help=helpmsg)

        with col2:
            nkey = 'benf'+str(1)
            k.initKey(nkey, 1)
            ret = k.getNum(accounts['txDef'].capitalize(), nkey, format='%.2f', max_value=1.,
                           step=0.05, help=helpmsg)

        with col3:
            nkey = 'benf'+str(2)
            k.initKey(nkey, 1)
            ret = k.getNum(accounts['txFree'].capitalize(), nkey, format='%.2f', max_value=1.,
                           step=0.05, help=helpmsg)

        st.write('##### Surplus deposit fraction')
        col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
        with col1:
            k.initKey('surplusFraction', 0.5)
            helpmsg = "When beneficiary fractions are not all 1, set surplus deposits to all go to survivor's account."
            ret = k.getNum("Fraction deposited in %s's taxable account" % iname1,
                           'surplusFraction', format='%.2f', help=helpmsg, max_value=1.0, step=0.05)
