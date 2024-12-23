'''
Module for storing keys in Streamlit session state.
'''
import streamlit as st

ss = st.session_state 
newCase = 'New case...'
loadConfig = 'Load config...'

# Dictionary of dictionaries for each case.
if 'cases' not in ss:
    # print('init cases')
    ss.cases = {newCase: {'iname0': '', 'status': 'unkown', 'summary': ''},
                loadConfig: {'iname0': '', 'status': 'unkown', 'summary': ''}}

# Variable for storing name of current case.
if 'currentCase' not in ss:
    ss.currentCase = newCase


def allCaseNames() -> list:
    # print('all case names')
    return list(ss.cases)


def onlyCaseNames() -> list:
    caseList = list(ss.cases)
    caseList.remove(newCase)
    caseList.remove(loadConfig)
    return caseList


def once(func):
    key = func.__name__
    if getKey(key) is None:
        func()
    init(key, 1)


def getIndex(item, choices):
    try:
        i = choices.index(item)
    except ValueError:
        return None

    return i


def currentCaseName() -> str:
    return ss.currentCase


def switchToCase(key):
    ss.currentCase = ss['_'+key]


def titleBar(nkey, choices=None):
    if choices is None:
        choices = onlyCaseNames()
    return st.selectbox('Select case', choices,
                        index=getIndex(currentCaseName(), choices), key='_'+nkey,
                        on_change=switchToCase, args=[nkey])


def currentCaseDic() -> dict:
    return ss.cases[ss.currentCase]


def setCurrentCase(case):
    if case not in ss.cases:
        raise RuntimeError('Case %s not found in dictionary.' % case)
    ss.currentCase = case


def createCase():
    if ss._newcase != '' and ss._newcase not in ss.cases:
        ss.cases[ss._newcase] = {'name': ss._newcase, 'summary': '', 'logs': None}

    if len(ss.cases) > 3:
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
    if ss.currentCase != newCase:
        del ss.cases[ss.currentCase]
    setCurrentCase(newCase)


def dump():
    print('State Dump:', ss)


def pull(key):
    # print('pulling', key, 'from', '_'+key, 'as', ss['_'+key])
    return setKey(key, ss['_'+key])


def setKey(key, val):
    # print('storing', key, 'as', val)
    ss.cases[ss.currentCase][key] = val
    return val


def init(key, val):
    if key not in ss.cases[ss.currentCase]:
        # print('init', key, 'as', val)
        ss.cases[ss.currentCase][key] = val


def getKey(key):
    if key in ss.cases[ss.currentCase]:
        return ss.cases[ss.currentCase][key]
    else:
        return None


def getDict(key=ss.currentCase):
    return ss.cases[key]


def getIntNum(text, nkey, disabled=False, callback=pull):
    return st.number_input(text,
                           value=int(getKey(nkey)),
                           disabled=disabled,
                           min_value=0,
                           step=1,
                           on_change=callback, args=[nkey], key='_'+nkey)


def getNum(text, nkey, disabled=False, callback=pull, step=10.):
    return st.number_input(text,
                           value=float(getKey(nkey)),
                           disabled=disabled,
                           step=step,
                           min_value=0.,
                           format='%.1f',
                           on_change=callback, args=[nkey], key='_'+nkey)


def getText(text, nkey, disabled=False, callback=pull, placeholder=None):
    return st.text_input(text,
                         value=getKey(nkey),
                         disabled=disabled,
                         on_change=callback, args=[nkey], key='_'+nkey,
                         placeholder=placeholder)


def getRadio(text, choices, nkey, callback=pull):
    return st.radio(text, choices,
                    index=choices.index(getKey(nkey)),
                    on_change=callback, args=[nkey], key='_'+nkey,
                    horizontal=True)


def getToggle(text, nkey, callback=pull):
    return st.toggle(text, value=getKey(nkey),
                     on_change=callback, args=[nkey], key='_'+nkey)
