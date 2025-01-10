'''
Module for storing keys in Streamlit session state.
'''
import streamlit as st


ss = st.session_state
newCase = 'New Case...'
loadCaseFile = 'Upload Case File...'
help1000 = "Value is in \\$1,000 denoted \\$k."


def init():
    '''
    Initialize variables through a function as it will only happen once through module.
    '''
    # Dictionary of dictionaries for each case.
    global ss
    ss = st.session_state
    if 'cases' not in ss:
        # print('Initializing keyholder')
        ss.cases = {newCase: {'iname0': '', 'status': 'unkown', 'caseStatus': 'new', 'summary': ''},
                    loadCaseFile: {'iname0': '', 'status': 'unkown', 'caseStatus': 'new', 'summary': ''}}

    # Variable for storing name of current case.
    if 'currentCase' not in ss:
        # ss.currentCase = loadCaseFile
        ss.currentCase = newCase


init()


def allCaseNames() -> list:
    return list(ss.cases)


def onlyCaseNames() -> list:
    caseList = list(ss.cases)
    caseList.remove(newCase)
    caseList.remove(loadCaseFile)
    return caseList


def runOncePerCase(func):
    key = 'oNcE_' + func.__name__
    if getKey(key) is None:
        func()
    initKey(key, 1)


def refreshCase(adic):
    """
    When a case is duplicated, reset all the runOnce functions.
    """
    for key in list(adic):
        if key.startswith('oNcE_'):
            del adic[key]


def resetTimeLists():
    setKey('stTimeLists', None)
    setKey('timeList0', None)
    if getKey('status') == 'married':
        setKey('timeList1', None)


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


def isIncomplete():
    return (currentCaseName() == '' or getKey('iname0') in [None, '']
            or (getKey('status') == 'married' and getKey('iname1') in [None, '']))


def caseHasNoPlan():
    return getKey('plan') is None


def caseHasPlan():
    return getKey('plan') is not None


def caseHasNotCompletedRun():
    return not caseHasCompletedRun()


def caseHasCompletedRun():
    return getKey('caseStatus') == 'solved'


def caseIsNotRunReady():
    return (getKey('plan') is None or
            getKey('objective') is None or
            getKey('rateType') is None or
            getKey('interpMethod') is None or
            getKey('spendingProfile') is None)


def caseIsNotMCReady():
    """
    Check that rates are  set to some stochastic method before MC run.
    """
    return (caseIsNotRunReady() or
            getKey('rateType') != 'varying' or
            'tochastic' not in getKey('varyingType'))


def titleBar(nkey, choices=None):
    if choices is None:
        choices = onlyCaseNames()
    helpmsg = 'Select an existing case, or create a new one from scratch, or from a *case* file.'
    return st.sidebar.selectbox('Select case', choices, help=helpmsg,
                                index=getIndex(currentCaseName(), choices), key='_'+nkey,
                                on_change=switchToCase, args=[nkey])


def currentCaseDic() -> dict:
    return ss.cases[ss.currentCase]


def setCurrentCase(case):
    if case not in ss.cases:
        raise RuntimeError('Case %s not found in dictionary' % case)
    ss.currentCase = case


def duplicateCase():
    for i in range(1, 10):
        dupname = ss.currentCase + '(%d)' % i
        if dupname not in ss.cases:
            break
    else:
        raise RuntimeError('Exhausted number of duplicates')

    # Use copy + create approach instead of cloning.
    ss.cases[dupname] = ss.cases[ss.currentCase].copy()
    ss.cases[dupname]['plan'] = None
    ss.cases[dupname]['name'] = dupname
    ss.cases[dupname]['summary'] = ''
    refreshCase(ss.cases[dupname])
    ss.currentCase = dupname
    resetTimeLists()


def createCaseFromFile(confile):
    import owlbridge as owb
    name, dic = owb.createCaseFromFile(confile)
    if name == '':
        return False
    elif name in ss.cases:
        st.error("Case name '%s' already exists." % name)
        return False

    ss.cases[name] = dic
    setCurrentCase(name)
    return True


def createNewCase(case):
    if case == 'newcase':
        # Widget stored case name in _newname.
        casename = ss._newcase

    if casename == '' or casename in ss.cases:
        return

    ss.cases[casename] = {'name': casename, 'caseStatus': '', 'summary': '', 'logs': None}
    setCurrentCase(ss._newcase)


def renameCase(key):
    if ss.currentCase == newCase or ss.currentCase == loadCaseFile:
        return
    newname = ss['_'+key]
    plan = getKey('plan')
    if plan:
        plan.rename(newname)
    ss.cases[newname] = ss.cases.pop(ss.currentCase)
    ss.cases[newname]['name'] = newname
    setCurrentCase(newname)


def deleteCurrentCase():
    if ss.currentCase == newCase or ss.currentCase == loadCaseFile:
        return
    del ss.cases[ss.currentCase]
    setCurrentCase(loadCaseFile)


def dump():
    print('State Dump:', ss)


def setpull(key):
    return setKey(key, ss['_'+key])


def storepull(key):
    return storeKey(key, ss['_'+key])


def setKey(key, val):
    ss.cases[ss.currentCase][key] = val
    ss.cases[ss.currentCase]['caseStatus'] = 'modified'
    return val


def storeKey(key, val):
    ss.cases[ss.currentCase][key] = val
    return val


def initKey(key, val):
    if key not in ss.cases[ss.currentCase]:
        ss.cases[ss.currentCase][key] = val


def getKey(key):
    if key in ss.cases[ss.currentCase]:
        return ss.cases[ss.currentCase][key]
    else:
        return None


def getDict(key=ss.currentCase):
    return ss.cases[key]


def getIntNum(text, nkey, disabled=False, callback=setpull, step=1, max_value=None):
    return st.number_input(text,
                           value=int(getKey(nkey)),
                           disabled=disabled,
                           min_value=0,
                           max_value=max_value,
                           step=step,
                           on_change=callback, args=[nkey], key='_'+nkey)


def getNum(text, nkey, disabled=False, callback=setpull, step=10.,
           min_value=0., max_value=None, format='%.1f', help=None):
    return st.number_input(text,
                           value=float(getKey(nkey)),
                           disabled=disabled,
                           step=step,
                           help=help,
                           min_value=min_value,
                           max_value=max_value,
                           format=format,
                           on_change=callback, args=[nkey], key='_'+nkey)


def getText(text, nkey, disabled=False, callback=setpull, placeholder=None):
    return st.text_input(text,
                         value=getKey(nkey),
                         disabled=disabled,
                         on_change=callback, args=[nkey], key='_'+nkey,
                         placeholder=placeholder)


def getRadio(text, choices, nkey, callback=setpull, help=None):
    return st.radio(text, choices,
                    index=choices.index(getKey(nkey)),
                    on_change=callback, args=[nkey], key='_'+nkey,
                    horizontal=True, help=help)


def getToggle(text, nkey, callback=setpull, disabled=False, help=None):
    return st.toggle(text, value=getKey(nkey), on_change=callback, args=[nkey],
                     disabled=disabled, key='_'+nkey, help=help)


def orangeDivider():
    st.html('<style> hr {border-color: orange;}</style><hr>')


def caseHeader(txt):
    st.html('<div style="text-align: right;color: orange;font-style: italic;">%s</div>' % currentCaseName())
    st.write('## ' + txt)
    orangeDivider()
