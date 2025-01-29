'''
Module for storing keys in Streamlit session state.
'''
import streamlit as st
import copy


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
        ss.cases = {newCase: {'iname0': '', 'status': 'unkown', 'caseStatus': 'new', 'summary': ''},
                    loadCaseFile: {'iname0': '', 'status': 'unkown', 'caseStatus': 'new', 'summary': ''}}

    # Variable for storing name of current case.
    if 'currentCase' not in ss:
        ss.currentCase = loadCaseFile
        # ss.currentCase = newCase


init()


def allCaseNames() -> list:
    return list(ss.cases)


def onlyCaseNames() -> list:
    caseList = list(ss.cases)
    caseList.remove(newCase)
    caseList.remove(loadCaseFile)
    return caseList


def runOncePerSession(func):
    key = 'oNcE_' + func.__name__
    if getGlobalKey(key) is None:
        func()
        storeGlobalKey(key, 1)


def runOncePerCase(func):
    key = 'oNcE_' + func.__name__
    if getKey(key) is None:
        func()
        storeKey(key, 1)


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


def updateContributions():
    noChange = ((getKey('_timeList0') is None or
                 getKey('_timeList0').equals(getKey('timeList0'))) and
                (getKey('_timeList1') is None or
                 getKey('_timeList1').equals(getKey('timeList1'))))
    if noChange:
        return True

    setKey('timeList0', getKey('_timeList0'))
    setKey('timeList1', getKey('_timeList1'))


def switchToCase(key):
    # Catch case where switch happens while editing W&W tables.
    if getGlobalKey('currentPageName') == 'Wages And Contributions':
        updateContributions()
    ss.currentCase = ss['_'+key]


def isIncomplete():
    return (currentCaseName() == '' or getKey('iname0') in [None, '']
            or (getKey('status') == 'married' and getKey('iname1') in [None, '']))


def isCaseUnsolved():
    if caseHasNoPlan():
        return True
    return getKey('caseStatus') != 'solved'


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
    helpmsg = 'Select an existing case, or create a new one from scratch or from a *case* parameter file.'
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

    # Copy everything except the plan itself.
    # print(ss.currentCase, '->', ss.cases[ss.currentCase])
    currentPlan = ss.cases[ss.currentCase]['plan']
    ss.cases[ss.currentCase]['plan'] = None
    ss.cases[dupname] = copy.deepcopy(ss.cases[ss.currentCase])
    ss.cases[ss.currentCase]['plan'] = currentPlan
    ss.cases[dupname]['name'] = dupname
    ss.cases[dupname]['summary'] = ''
    ss.cases[dupname]['duplicate'] = True
    refreshCase(ss.cases[dupname])
    ss.currentCase = dupname
    # resetTimeLists()
    # print(dupname, '->', ss.cases[dupname])


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
    if case != 'newcase':
        st.error("Expected 'newcase' but got '%s'." % case)
        return

    # Widget stored case name in _newname.
    casename = ss._newcase

    if casename == '':
        return

    if casename in ss.cases:
        st.error("Case name '%s' already exists." % casename)
        return

    ss.cases[casename] = {'name': casename, 'caseStatus': 'unknown', 'summary': '', 'logs': None}
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


def dumpSession():
    print('State Dump:', ss)


def dumpCase(case=None):
    if case is None:
        case = ss.currentCase
    print('Case Dump:', ss.cases[case])


def setpull(key):
    return setKey(key, ss['_'+key])


def storepull(key):
    return storeKey(key, ss['_'+key])


def setKey(key, val):
    ss.cases[ss.currentCase][key] = val
    ss.cases[ss.currentCase]['caseStatus'] = 'modified'
    # print('setKey', key, val)
    return val


def storeKey(key, val):
    ss.cases[ss.currentCase][key] = val
    return val


def initKey(key, val):
    if key not in ss.cases[ss.currentCase]:
        ss.cases[ss.currentCase][key] = val
        # print('initKey', key, val)


def initGlobalKey(key, val):
    if key not in ss:
        ss[key] = val


def getKey(key):
    if key in ss.cases[ss.currentCase]:
        return ss.cases[ss.currentCase][key]
    else:
        return None


def storeGlobalKey(key, val):
    ss[key] = val
    return val


def getGlobalKey(key):
    if key in ss:
        return ss[key]
    else:
        return None


def getDict(key=ss.currentCase):
    return ss.cases[key]


def getAccountBalances(ni):
    bal = [[], [], []]
    accounts = ['txbl', 'txDef', 'txFree']
    for j, acc in enumerate(accounts):
        for i in range(ni):
            bal[j].append(getKey(acc+str(i)))

    return bal


def getSolveParameters():
    maximize = getKey('objective')
    if maximize is None:
        return None
    if 'spending' in maximize:
        objective = 'maxSpending'
    else:
        objective = 'maxBequest'

    options = {}
    optList = ['netSpending', 'maxRothConversion', 'noRothConversions',
               'withMedicare', 'bequest', 'solver']
    for opt in optList:
        val = getKey(opt)
        if val is not None:
            options[opt] = val

    if getKey('readRothX'):
        options['maxRothConversion'] = 'file'

    return objective, options


def getIndividualAllocationRatios():
    generic = []
    initial = []
    final = []
    for k1 in range(4):
        initial.append(int(getKey('j3_init%'+str(k1)+'_0')))
        final.append(int(getKey('j3_fin%'+str(k1)+'_0')))
    gen0 = [initial, final]
    generic = [gen0]

    if getKey('status') == 'married':
        initial = []
        final = []
        for k1 in range(4):
            initial.append(int(getKey('j3_init%'+str(k1)+'_1')))
            final.append(int(getKey('j3_fin%'+str(k1)+'_1')))
        gen1 = [initial, final]
        generic.append(gen1)

    return generic


def getAccountAllocationRatios():
    accounts = [[], [], []]
    for j1 in range(3):
        initial = []
        final = []
        for k1 in range(4):
            initial.append(int(getKey(f'j{j1}_init%'+str(k1)+'_0')))
            final.append(int(getKey(f'j{j1}_fin%'+str(k1)+'_0')))
        tmp = [initial, final]
        accounts[j1].append(tmp)

    if getKey('status') == 'married':
        for j1 in range(3):
            initial = []
            final = []
            for k1 in range(4):
                initial.append(int(getKey(f'j{j1}_init%'+str(k1)+'_1')))
                final.append(int(getKey(f'j{j1}_fin%'+str(k1)+'_1')))
            tmp = [initial, final]
            accounts[j1].append(tmp)

    return accounts


def getPreviousMAGI():
    backMAGI = [0, 0]
    for ii in range(2):
        val = getKey('MAGI'+str(ii))
        if val:
            backMAGI[ii] = val

    return backMAGI


def getFixedIncome(ni, what):
    amounts = []
    ages = []
    for i in range(ni):
        amounts.append(getKey(what+'Amt'+str(i)))
        ages.append(getKey(what+'Age'+str(i)))

    return amounts, ages


def getIntNum(text, nkey, disabled=False, callback=setpull, step=1, help=None, min_value=0, max_value=None):
    return st.number_input(text,
                           value=int(getKey(nkey)),
                           disabled=disabled,
                           min_value=min_value,
                           max_value=max_value,
                           step=step,
                           help=help,
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
