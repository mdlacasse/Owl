import streamlit as st

import sskeys as kz

ret = kz.titleBar('assets')
kz.caseHeader("Assets")

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    st.write('#### Savings Account Balances')
    accounts = {'txbl':  'taxable', 'txDef': 'tax-deferred', 'txFree': 'tax-exempt'}
    col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
    with col1:
        iname0 = kz.getKey('iname0')
        for key in accounts:
            nkey = key+str(0)
            kz.initKey(nkey, 0)
            ret = kz.getNum("%s's %s account ($k)" % (iname0, accounts[key]), nkey, help=kz.help1000)

    with col2:
        if kz.getKey('status') == 'married':
            iname1 = kz.getKey('iname1')
            for key in accounts:
                nkey = key+str(1)
                kz.initKey(nkey, 0)
                ret = kz.getNum("%s's %s account ($k)" % (iname1, accounts[key]), nkey, help=kz.help1000)

    if kz.getKey('status') == 'married':
        st.divider()
        st.write("##### Survivor's spousal beneficiary fractions")
        col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
        with col1:
            nkey = 'benf'+str(0)
            kz.initKey(nkey, 1)
            helpmsg = 'Fraction of account left to surviving spouse.'
            ret = kz.getNum(accounts['txbl'].capitalize(), nkey, format='%.2f', max_value=1.,
                            step=0.05, help=helpmsg)

        with col2:
            nkey = 'benf'+str(1)
            kz.initKey(nkey, 1)
            ret = kz.getNum(accounts['txDef'].capitalize(), nkey, format='%.2f', max_value=1.,
                            step=0.05, help=helpmsg)

        with col3:
            nkey = 'benf'+str(2)
            kz.initKey(nkey, 1)
            ret = kz.getNum(accounts['txFree'].capitalize(), nkey, format='%.2f', max_value=1.,
                            step=0.05, help=helpmsg)

        st.write('##### Surplus deposit fraction')
        col1, col2, col3 = st.columns(3, gap='large', vertical_alignment='top')
        with col1:
            kz.initKey('surplusFraction', 0.5)
            helpmsg = "When beneficiary fractions are not all 1, set surplus deposits to all go to survivor's account."
            ret = kz.getNum("Fraction deposited in %s's taxable account" % iname1,
                            'surplusFraction', format='%.2f', help=helpmsg, max_value=1.0, step=0.05)
