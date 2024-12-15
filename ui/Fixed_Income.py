import streamlit as st

import key as k


def getInput(i, key, text, defval=0):
    nkey = key+str(i)
    k.init(nkey, defval)
    iname = st.session_state['iname'+str(i)]
    ret = st.number_input("%s's %s" % (iname, text), min_value=0,
                          value=st.session_state[nkey],
                          on_change=k.push, args=[nkey], key='_'+nkey)


if st.session_state.iname0 == '':
    st.info('Basic information must be filled before filling this page.')
else:
    st.write('# Fixed Income')

    st.write('### Social Security')
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        getInput(0, 'ssAge', 'social security age', 67)
        getInput(0, 'ssAmt', 'social security amount (k$)')

    with col2:
        if st.session_state.status == 'married':
            getInput(1, 'ssAge', 'social security age', 67)
            getInput(1, 'ssAmt', 'social security amount (k$)')
    
    st.write('### Pension')
    col1, col2 = st.columns(2, gap='small', vertical_alignment='top')
    with col1:
        getInput(0, 'pAge', 'pension age', 65)
        getInput(0, 'pAmt', 'social security amount (k$)')

    with col2:
        if st.session_state.status == 'married':
            getInput(1, 'pAge', 'pension age', 65)
            getInput(1, 'pAmt', 'social security amount (k$)')

