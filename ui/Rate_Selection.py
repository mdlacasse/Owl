import streamlit as st
import key as k

FXRATES = {
    'conservative': [8, 5, 4, 3],
    'realistic': [11, 6, 5, 3],
    'historical average': [0, 0, 0, 0],
    'user': [0, 0, 0, 0]
}


def update_rates(key):
    # print('updating rates', key)
    k.push(key)
    fxType = st.session_state[key]
    rates = FXRATES[fxType]
    for j in range(4):
        k.store('fxRate'+str(j), rates[j])


st.write('# Rate Selection')

choices1 = ['fixed', 'varying']
k.init('rateType', choices1[0])
ret = k.getRadio('## Rate type', choices1, 'rateType')

if st.session_state.rateType == 'fixed':
    choices2 = ['conservative', 'realistic', 'historical average', 'user']
    k.init('fixedType', choices2[0])
    ret = k.getRadio('Select fixed rates', choices2, 'fixedType', update_rates)

    st.write('#### Fixed rate values (%)')
    for j in range(4):
        rates = FXRATES[ret]
        k.init('fxRate'+str(j), rates[j])

    ro = ret  != 'user'
    col1, col2, col3, col4 = st.columns(4, gap='small', vertical_alignment='top')
    with col1:
        ret = k.getNum('S&P 500', 'fxRate0', ro)
    
    with col2:
        ret = k.getNum('Corporate Bonds Baa', 'fxRate1', ro)
    
    with col3:
        ret = k.getNum('10-y Treasury Notes', 'fxRate2', ro)
    
    with col4:
        ret = k.getNum('Common Assets / Inflation', 'fxRate3', ro)
    

elif st.session_state.rateType == 'varying':
    choices3 = ['historical', 'histochastic', 'stochastic']
    k.init('varyingType', choices3[0])
    ret = k.getRadio('Select varying rates', choices3, 'varyingType')

else:
    st.info('Logic error')

if ((st.session_state.rateType == 'fixed' and 'hist' in st.session_state.fixedType)
   or (st.session_state.rateType == 'varying' and 'hist' in st.session_state.varyingType)):
    k.init('yfrm', 1922)
    k.init('yto', 2023)

    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        ret = st.number_input('Starting year', min_value=1922,
                              max_value=st.session_state['yto'],
                              value=st.session_state['yfrm'],
                              on_change=k.push, args=['yfrm'], key='_yfrm')

    with col2:
        ret = st.number_input('Ending year', max_value=2023,
                              min_value=st.session_state['yfrm'],
                              value=st.session_state['yto'],
                              on_change=k.push, args=['yto'], key='_yto')

st.write('### Other rates')

k.init('divRate', 2)
ret = k.getNum('Dividends return rate (%)', 'divRate')

st.write('### Income taxes')

k.init('gainTx', 15)
ret = k.getNum('Long-term capital gain income tax rate (%)', 'gainTx')

k.init('heirsTx', 30)
ret = k.getNum('Heirs income tax rate (%)', 'heirsTx')


