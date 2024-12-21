import streamlit as st

import key as k
import owlAPI as api


FXRATES = {
    'conservative': [8, 5, 4, 3],
    'realistic': [11, 6, 5, 3],
    'historical average': [0, 0, 0, 0],
    'user': [0, 0, 0, 0]
}


def update_rates(key):
    # print('updating rates', key)
    k.pull(key)
    fxType = k.getKey(key)
    rates = FXRATES[fxType]
    for j in range(4):
        k.store('fxRate'+str(j), rates[j])


ret = k.titleBar('rates')
st.divider()
st.write('## Rate Selection')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    choices1 = ['fixed', 'varying']
    k.init('rateType', choices1[0])
    ret = k.getRadio('## Rate type', choices1, 'rateType')

    if k.getKey('rateType') == 'fixed':
        choices2 = ['conservative', 'realistic', 'historical average', 'user']
        k.init('fixedType', choices2[0])
        ret = k.getRadio('Select fixed rates', choices2, 'fixedType', update_rates)

        st.write('#### Fixed rate values (%)')
        for j in range(4):
            rates = FXRATES[ret]
            k.init('fxRate'+str(j), rates[j])

        ro = (ret != 'user')
        col1, col2, col3, col4 = st.columns(4, gap='small', vertical_alignment='top')
        with col1:
            ret = k.getNum('S&P 500', 'fxRate0', ro, step=1.)

        with col2:
            ret = k.getNum('Corporate Bonds Baa', 'fxRate1', ro, step=1.)

        with col3:
            ret = k.getNum('10-y Treasury Notes', 'fxRate2', ro, step=1.)

        with col4:
            ret = k.getNum('Common Assets / Inflation', 'fxRate3', ro, step=1.)

    elif k.getKey('rateType') == 'varying':
        choices3 = ['historical', 'histochastic', 'stochastic']
        k.init('varyingType', choices3[0])
        ret = k.getRadio('Select varying rates', choices3, 'varyingType')

    else:
        st.info('Logic error')

    if ((k.getKey('rateType') == 'fixed' and 'hist' in k.getKey('fixedType'))
       or (k.getKey('rateType') == 'varying' and 'hist' in k.getKey('varyingType'))):
        k.init('yfrm', 1928)
        k.init('yto', 2023)

        col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
        with col1:
            ret = st.number_input('Starting year', min_value=1928,
                                  max_value=k.getKey('yto'),
                                  value=k.getKey('yfrm'),
                                  on_change=k.pull, args=['yfrm'], key='_yfrm')

        with col2:
            ret = st.number_input('Ending year', max_value=2023,
                                  min_value=k.getKey('yfrm'),
                                  value=k.getKey('yto'),
                                  on_change=k.pull, args=['yto'], key='_yto')

    st.text(' ')
    api.setRates()
    api.showRates()

    st.divider()
    st.write('### Other rates')
    k.init('divRate', 2)
    ret = k.getNum('Dividends return rate (%)', 'divRate')
    
    st.write('#### Income taxes')
    k.init('gainTx', 15)
    ret = k.getNum('Long-term capital gain income tax rate (%)', 'gainTx')

    k.init('heirsTx', 30)
    ret = k.getNum('Heirs income tax rate (%)', 'heirsTx')


