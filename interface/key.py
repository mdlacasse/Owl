import streamlit as st

def dump():
    pass
    # print('Dump:', st.session_state)

def push(key):
    # print('pushing', key, 'as', st.session_state['_'+key])
    st.session_state[key] = st.session_state['_'+key]
    dump()

def store(key, val):
    # print('storing', key, 'as', val)
    st.session_state[key] = val
    dump()

def init(key, val):
    if key not in st.session_state:
        # print('init', key, 'as', val)
        st.session_state[key] = val
        dump()

def getNum(text, nkey, disabled=False, callback=push):
    return st.number_input(text, 
                       value=st.session_state[nkey],
                       disabled=disabled,
                       on_change=callback, args=[nkey], key='_'+nkey)

def getText(text, nkey, disabled=False, callback=push):
    return st.text_input(text, 
                       value=st.session_state[nkey],
                       disabled=disabled,
                       on_change=callback, args=[nkey], key='_'+nkey)

def getRadio(text, choices, nkey, callback=push):
    return st.radio(text, choices,
                    index=choices.index(st.session_state[nkey]),
                    on_change=callback, args=[nkey], key='_'+nkey,
                    horizontal=True)

def getToggle(text, nkey, callback=push):
    return st.toggle(text, value=st.session_state[nkey],
                    on_change=callback, args=[nkey], key='_'+nkey)
