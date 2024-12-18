'''
Module for storing keys in Streamlit session state.
'''
import streamlit as st

ss = st.session_state

# Dictionary of dictionaries for each case.
if 'cases' not in ss:
    # print('init cases')
    ss.cases = {'New case': {'iname0': '', 'status': 'unkown'}}

# Variable for storing name of current case.
if 'currentCase' not in ss:
    ss.currentCase = 'New case'


def allCaseNames():
    # print('all case names')
    return list(ss.cases)


def currentCaseName():
    return ss.currentCase


def currentCaseDic():
    return ss.cases[ss.currentCase]


def switchToCase():
    ss.currentCase = ss._case


def setCurrentCase(case):
    if case not in ss.cases:
        raise RuntimeError('Case %s not found in dictionary.' % case)
    ss.currentCase = case


def createCase():
    if ss._newcase != '' and ss._newcase not in ss.cases:
        ss.cases[ss._newcase] = {'name': ss._newcase}

    if len(ss.cases) > 2:
        othercase = list(ss.cases)[-2]
        for key in ['iname0', 'status', 'yob0', 'life0']:
            ss.cases[ss._newcase][key] = ss.cases[othercase][key]
        if ss.cases[othercase]['status'] == 'married':
            for key in ['iname1', 'yob1', 'life1']:
                ss.cases[ss._newcase][key] = ss.cases[othercase][key]

    setCurrentCase(ss._newcase)


def renameCase(oldcase, newcase):
    if oldcase not in ss.cases:
        raise RuntimeError('Case %s not found in dictionary.' % oldcase)
    ss.cases[newcase] = ss.cases.pop(oldcase)


def deleteCurrentCase():
    if ss.currentCase != 'New case':
        del ss.cases[ss.currentCase]
    setCurrentCase('New case')


def dump():
    print('Dump:', ss)


def pull(key):
    # print('pulling', key, 'from', '_'+key, 'as', ss['_'+key])
    store(key, ss['_'+key])
    # dump()


def store(key, val):
    # print('storing', key, 'as', val)
    ss.cases[ss.currentCase][key] = val
    # dump()


def init(key, val):
    if key not in ss.cases[ss.currentCase]:
        # print('init', key, 'as', val)
        ss.cases[ss.currentCase][key] = val
        # dump()


def getKey(key):
    return ss.cases[ss.currentCase][key]


def getDict(key=ss.currentCase):
    return ss.cases[key]


def getNum(text, nkey, disabled=False, callback=pull):
    return st.number_input(text,
                           value=getKey(nkey),
                           disabled=disabled,
                           on_change=callback, args=[nkey], key='_'+nkey)


def getText(text, nkey, disabled=False, callback=pull):
    return st.text_input(text,
                         value=getKey(nkey),
                         disabled=disabled,
                         on_change=callback, args=[nkey], key='_'+nkey)


def getRadio(text, choices, nkey, callback=pull):
    return st.radio(text, choices,
                    index=choices.index(getKey(nkey)),
                    on_change=callback, args=[nkey], key='_'+nkey,
                    horizontal=True)


def getToggle(text, nkey, callback=pull):
    return st.toggle(text, value=getKey(nkey),
                     on_change=callback, args=[nkey], key='_'+nkey)
