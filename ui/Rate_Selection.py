import streamlit as st

import sskeys as k
import owlbridge as owb


FXRATES = {
    'conservative': [8, 5, 4, 3],
    'optimistic': [11, 6, 5, 3],
    'historical average': [0, 0, 0, 0],
    'user': [0, 0, 0, 0]
}

rateChoices = ['fixed', 'varying']
fixedChoices = list(FXRATES)
varyingChoices = ['historical', 'histochastic', 'stochastic']


def updateFixedRates(key, pull=True):
    if pull:
        fxType = k.setpull(key)
    else:
        fxType = key

    rates = FXRATES[fxType]
    for j in range(4):
        k.setKey('fxRate'+str(j), rates[j])
    owb.setRates()


def updateRates(key):
    k.setpull(key)
    owb.setRates()


def initRates():
    if k.getKey('rateType') == rateChoices[0] and k.getKey('fixedType') == fixedChoices[0]:
        updateFixedRates(fixedChoices[0], False)
    else:
        owb.setRates()


k.initKey('rateType', rateChoices[0])
k.initKey('fixedType', fixedChoices[0])
k.initKey('varyingType', varyingChoices[0])

k.runOncePerCase(initRates)

ret = k.titleBar('rates')
st.write('## Rate Selection')

if ret is None:
    st.info('Case(s) must be first created before running this page.')
else:
    k.initKey('yfrm', 1928)
    k.initKey('yto', 2023)

    k.getRadio('## Rate type', rateChoices, 'rateType', updateRates)

    if k.getKey('rateType') == 'fixed':
        fxType = k.getRadio('Select fixed rates', fixedChoices, 'fixedType', updateFixedRates)

        st.write('#### Fixed rate values (%)')
        for j in range(4):
            rates = FXRATES[fxType]
            k.initKey('fxRate'+str(j), rates[j])

        ro = (fxType != 'user')
        col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='top')
        with col1:
            k.getNum('S&P 500', 'fxRate0', ro, step=1., callback=updateRates)

        with col2:
            k.getNum('Corporate Bonds Baa', 'fxRate1', ro, step=1., callback=updateRates)

        with col3:
            k.getNum('10-y Treasury Notes', 'fxRate2', ro, step=1., callback=updateRates)

        with col4:
            k.getNum('Cash Assets/Inflation', 'fxRate3', ro, step=1., callback=updateRates)

    elif k.getKey('rateType') == 'varying':
        k.getRadio('Select varying rates', varyingChoices, 'varyingType', callback=updateRates)

    else:
        st.error('Logic error')

    if ((k.getKey('rateType') == 'fixed' and 'hist' in k.getKey('fixedType'))
       or (k.getKey('rateType') == 'varying' and 'hist' in k.getKey('varyingType'))):

        col1, col2 = st.columns(2, gap='large', vertical_alignment='top')
        with col1:
            st.number_input('Starting year', min_value=1928,
                            max_value=k.getKey('yto'),
                            value=k.getKey('yfrm'),
                            on_change=updateRates, args=['yfrm'], key='_yfrm')

        with col2:
            st.number_input('Ending year', max_value=2023,
                            min_value=k.getKey('yfrm'),
                            value=k.getKey('yto'),
                            on_change=updateRates, args=['yto'], key='_yto')

    if k.getKey('rateType') == 'varying':
        st.write('#### Stochastic parameters')
        ro = k.getKey('varyingType') != 'stochastic'
        st.write('##### Means')
        col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='top')
        with col1:
            k.initKey('mean0', 0)
            k.getNum('S&P 500', 'mean0', ro, step=1., callback=updateRates)

        with col2:
            k.initKey('mean1', 0)
            k.getNum('Corporate Bonds Baa', 'mean1', ro, step=1., callback=updateRates)

        with col3:
            k.initKey('mean2', 0)
            k.getNum('10-y Treasury Notes', 'mean2', ro, step=1., callback=updateRates)

        with col4:
            k.initKey('mean3', 0)
            k.getNum('Cash Assets/Inflation', 'mean3', ro, step=1., callback=updateRates)

        st.write('##### Volatility')
        col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='top')
        with col1:
            k.initKey('stdev0', 0)
            k.getNum('S&P 500', 'stdev0', ro, step=1., callback=updateRates)

        with col2:
            k.initKey('stdev1', 0)
            k.getNum('Corporate Bonds Baa', 'stdev1', ro, step=1., callback=updateRates)

        with col3:
            k.initKey('stdev2', 0)
            k.getNum('10-y Treasury Notes', 'stdev2', ro, step=1., callback=updateRates)

        with col4:
            k.initKey('stdev3', 0)
            k.getNum('Cash Assets/Inflation', 'stdev3', ro, step=1., callback=updateRates)

        st.write('##### Correlation Matrix')
        col1, col2, col3, col4 = st.columns(4, gap='large', vertical_alignment='top')
        with col1:
            k.initKey('diag1', 1)
            k.getNum('S&P 500', 'diag1', True, format='%.2f', callback=None)

        with col2:
            k.initKey('corr1', 0.)
            k.getNum('(1,2)', 'corr1', ro, step=.1, format='%.2f', min_value=-1., max_value=1.,
                     callback=updateRates)
            k.initKey('diag2', 1.)
            k.getNum('Corporate Bonds Baa', 'diag2', True, format='%.2f', min_value=-1., max_value=1.,
                     callback=None)

        with col3:
            k.initKey('corr2', 0.)
            k.getNum('(1,3)', 'corr2', ro, step=.1, format='%.2f', min_value=-1., max_value=1.,
                     callback=updateRates)
            k.initKey('corr4', 0.)
            k.getNum('(2,3)', 'corr4', ro, step=.1, format='%.2f', min_value=-1., max_value=1.,
                     callback=updateRates)
            k.initKey('diag3', 1.)
            k.getNum('10-y Treasury Notes', 'diag3', True, format='%.2f', min_value=-1., max_value=1.,
                     callback=None)

        with col4:
            k.initKey('corr3', 0.)
            k.getNum('(1,4)', 'corr3', ro, step=.1, format='%.2f', min_value=-1., max_value=1.,
                     callback=updateRates)
            k.initKey('corr5', 0.)
            k.getNum('(2,4)', 'corr5', ro, step=.1, format='%.2f', min_value=-1., max_value=1.,
                     callback=updateRates)
            k.initKey('corr6', 0.)
            k.getNum('(3,4)', 'corr6', ro, step=.1, format='%.2f', min_value=-1., max_value=1.,
                     callback=updateRates)
            k.initKey('diag4', 1.)
            k.getNum('Cash Assets/Inflation', 'diag4', True, format='%.2f', min_value=-1., max_value=1.,
                     callback=None)

        st.write('#### Correlations between return rates')
        owb.showRatesCorrelations()

    st.write('#### Selected rates over time horizon')
    owb.showRates()

    st.divider()
    st.write('### Other rates')
    k.initKey('divRate', 2)
    ret = k.getNum('Dividends return rate (%)', 'divRate', max_value=100., format='%.2f',
                   callback=owb.setDividendRate, step=1.)

    st.write('#### Income taxes')
    col1, col2 = st.columns(2, gap='large', vertical_alignment='top')
    with col1:
        k.initKey('gainTx', 15)
        ret = k.getNum('Long-term capital gain income tax rate (%)', 'gainTx', max_value=100.,
                       callback=owb.setLongTermCapitalTaxRate, step=1.)

    with col2:
        k.initKey('heirsTx', 30)
        ret = k.getNum('Heirs income tax rate (%)', 'heirsTx', max_value=100.,
                       callback=owb.setHeirsTaxRate, step=1.)
