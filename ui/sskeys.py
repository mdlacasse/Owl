"""
Module for storing keys in Streamlit session state.
"""

import streamlit as st
import pandas as pd
from datetime import date
import copy
import re


ss = st.session_state
newCase = "New Case..."
loadCaseFile = "Upload Case File..."
help1000 = "Value is in \\$1,000 denoted \\$k."


def init():
    """
    Initialize variables through a function as it will only happen once through module.
    """
    # Dictionary of dictionaries for each case.
    global ss
    ss = st.session_state
    if "cases" not in ss:
        ss.cases = {
            newCase: {"iname0": "", "status": "unknown", "caseStatus": "new", "id": 0},
            loadCaseFile: {"iname0": "", "status": "unknown", "caseStatus": "new", "id": 1},
        }

    # Variable for storing name of current case.
    if "currentCase" not in ss:
        ss.currentCase = loadCaseFile
        # ss.currentCase = newCase


init()


def genCaseKey(key):
    """
    This function is to generate global keys that are uniquely associated with a case.
    """
    return f"{getCaseKey('id')}_{key}"


def getKeyInCase(key, casename):
    if casename in ss.cases and key in ss.cases[casename]:
        return ss.cases[casename][key]
    return None


def allCaseNames() -> list:
    return list(ss.cases)


def onlyCaseNames() -> list:
    caseList = list(ss.cases)
    caseList.remove(newCase)
    caseList.remove(loadCaseFile)
    return caseList


def runOncePerSession(func):
    key = "oNcE_" + func.__name__
    if getGlobalKey(key) is None:
        func()
        storeGlobalKey(key, 1)


def runOncePerCase(func):
    key = "oNcE_" + func.__name__
    if key not in ss.cases[ss.currentCase]:
        func()
        storeCaseKey(key, 1)


def refreshCase(adic):
    """
    When a case is copied, reset all the runOnce functions.
    """
    for key in list(adic):
        if key.startswith("oNcE_"):
            del adic[key]


def resetTimeLists():
    setCaseKey("stTimeLists", None)
    setCaseKey("timeList0", None)
    if getCaseKey("status") == "married":
        setCaseKey("timeList1", None)


def getIndex(item, choices):
    try:
        i = choices.index(item)
    except ValueError:
        # st.error(f"Value {item} not found in {choices}.")
        return None

    return i


def currentCaseName() -> str:
    return ss.currentCase


def switchToCase(key):
    ss.currentCase = ss[key]


def switchToCaseName(casename):
    if casename not in ss.cases:
        raise RuntimeError(f"No such case {casename}.")
    ss.currentCase = casename


def isIncomplete():
    return (
        currentCaseName() == ""
        or getCaseKey("iname0") in [None, ""]
        or (getCaseKey("status") == "married" and getCaseKey("iname1") in [None, ""])
    )


def caseHasNotRun():
    return getCaseKey("caseStatus") not in ["solved", "unsuccessful"]


def isCaseUnsolved():
    if caseHasNoPlan():
        return True
    return getCaseKey("caseStatus") != "solved"


def caseHasNoPlan():
    return getCaseKey("plan") is None


def caseHasPlan():
    return getCaseKey("plan") is not None


def caseIsRunReady():
    return not caseIsNotRunReady() and getCaseKey("caseStatus") in ["modified", "new"]


def caseIsNotRunReady():
    return (
        getCaseKey("plan") is None
        or getCaseKey("objective") is None
        or getCaseKey("rateType") is None
        or getCaseKey("interpMethod") is None
        or getCaseKey("spendingProfile") is None
        or getCaseKey("allocType") is None
    )


def caseIsNotMCReady():
    """
    Check that rates are  set to some stochastic method before MC run.
    """
    return caseIsNotRunReady() or getCaseKey("rateType") != "varying" or "tochastic" not in getCaseKey("varyingType")


def currentCaseDic() -> dict:
    return ss.cases[ss.currentCase]


def setCurrentCase(case):
    if case not in ss.cases:
        raise RuntimeError(f"Case {case} not found in dictionary")
    ss.currentCase = case


def copyCase():
    baseName = re.sub(r"\s*\(\d+\)$", "", ss.currentCase)
    for i in range(1, 10):
        dupname = baseName + f" ({i})"
        if dupname not in ss.cases:
            break
    else:
        raise RuntimeError("Exhausted number of copies")

    # Copy everything except the plan itself.
    # print(ss.currentCase, "->", ss.cases[ss.currentCase])
    currentPlan = ss.cases[ss.currentCase]["plan"]
    ss.cases[ss.currentCase]["plan"] = None
    ss.cases[dupname] = copy.deepcopy(ss.cases[ss.currentCase])
    ss.cases[ss.currentCase]["plan"] = currentPlan

    # If reproducibility is enabled, copy the seed; otherwise generate a new one. Token be False or missing.
    if not ss.cases[dupname].get("reproducibleRates", False):
        # Generate a new seed for non-reproducible rates.
        import time
        ss.cases[dupname]["rateSeed"] = int(time.time() * 1000000) % (2**31)

    ss.cases[dupname]["name"] = dupname
    for key in ["summaryDf", "histoPlot", "histoSummary", "monteCarloPlot", "monteCarloSummary"]:
        ss.cases[dupname][key] = None

    # Create a new StringIO for logs to separate them from the original case
    from io import StringIO
    ss.cases[dupname]["logs"] = StringIO()
    # Reset the logger so a new one gets created when needed
    ss.cases[dupname]["_ui_logger"] = None

    ss.cases[dupname]["copy"] = True
    refreshCase(ss.cases[dupname])
    ss.currentCase = dupname
    st.toast("Case copied but not created.")


def createCaseFromFile(strio):
    import owlbridge as owb
    from io import StringIO

    name, dic = owb.createCaseFromFile(strio)
    if name == "":
        return False
    elif name in ss.cases:
        st.error(f"Case name '{name}' already exists.")
        return False

    # Create logs StringIO when case is created from file
    if "logs" not in dic or dic["logs"] is None:
        dic["logs"] = StringIO()

    ss.cases[name] = dic
    setCurrentCase(name)
    return True


def createNewCase(case):
    if case != "newcase":
        st.error(f"Expected 'newcase' but got '{case}'.")
        return

    # Widget stored case name in _newcase.
    casename = ss._newcase

    if casename == "":
        return

    if casename in ss.cases:
        st.error(f"Case name '{casename}' already exists.")
        return

    # Create logs StringIO when case is created
    from io import StringIO
    logs_strio = StringIO()
    ss.cases[casename] = {"name": casename, "caseStatus": "unknown", "logs": logs_strio, "id": None}
    setCurrentCase(casename)


def renameCase(key):
    if ss.currentCase == newCase or ss.currentCase == loadCaseFile:
        return
    newname = ss[key]
    if newname in ss.cases:
        st.error(f"Case name '{newname}' already exists.")
        return

    plan = getCaseKey("plan")
    ss.cases[newname] = ss.cases.pop(ss.currentCase)
    ss.cases[newname]["name"] = newname
    if plan:
        plan.rename(newname)
        ss.cases[newname]["caseStatus"] = "modified"
    setCurrentCase(newname)


def deleteCurrentCase():
    if ss.currentCase == newCase or ss.currentCase == loadCaseFile:
        return
    del ss.cases[ss.currentCase]
    setCurrentCase(loadCaseFile)


def dumpSession():
    print("State Dump:", ss)


def dumpCase(case=None):
    if case is None:
        case = ss.currentCase
    print("Case Dump:", ss.cases[case])


def setpull(key):
    return setCaseKey(key, ss[genCaseKey(key)])


def storepull(key):
    return storeCaseKey(key, ss[genCaseKey(key)])


def pushCaseKey(key, val=None):
    if val is not None:
        ss.cases[ss.currentCase][key] = val
        ss[genCaseKey(key)] = val
    else:
        val = ss.cases[ss.currentCase][key]
        ss[genCaseKey(key)] = val

    return val


def setCaseKey(key, val):
    ss.cases[ss.currentCase][key] = val
    flagModified()
    return val


def flagModified():
    ss.cases[ss.currentCase]["caseStatus"] = "modified"
    ss.cases[ss.currentCase]["summaryDf"] = None


def storeCaseKey(key, val):
    ss.cases[ss.currentCase][key] = val
    return val


def initCaseKey(key, val):
    """
    Only set the case local key if unset.
    """
    if key not in ss.cases[ss.currentCase]:
        setCaseKey(key, val)


def initGlobalKey(key, val):
    if key not in ss:
        ss[key] = val


def getCaseKey(key):
    return ss.cases[ss.currentCase].get(key)


def storeGlobalKey(key, val):
    ss[key] = val
    return val


def getGlobalKey(key):
    return ss.get(key)


def getDict(key=ss.currentCase):
    return ss.cases[key]


def getAccountBalances(ni):
    bal = [[], [], []]
    accounts = ["txbl", "txDef", "txFree"]
    for j, acc in enumerate(accounts):
        for i in range(ni):
            bal[j].append(getCaseKey(acc + str(i)))

    return bal


def colorBySign(val):
    color = "green" if "\u2191" in val else "red" if "\u2193" in val else None

    return f"color:{color};" if color else ""


def compareSummaries():
    df = getCaseKey("summaryDf")
    if df is None:
        return None
    for case in onlyCaseNames():
        if case == currentCaseName():
            continue
        odf = ss.cases[case]["summaryDf"]
        if odf is None or set(odf.columns) != set(df.columns):
            continue
        df = pd.concat([df, odf])

    if df.shape[0] > 1:
        # Unroll to subtract $tring representation of numbers.
        for col in range(1, df.shape[1] - 5):
            strval = df.iloc[0, col]
            if isinstance(strval, str) and strval[0] == "$":
                f0val = float(strval[1:].replace(",", ""))
                for row in range(1, df.shape[0]):
                    fnval = float(df.iloc[row, col][1:].replace(",", ""))
                    diff = fnval - f0val
                    sign = "\u2191" if diff > 0 else "\u2193" if diff < 0 else "\u2192"
                    df.iloc[row, col] = f"{sign} ${abs(diff):,.0f}"

    return df.transpose()


def getSolveParameters():
    maximize = getCaseKey("objective")
    if maximize is None:
        return None
    if "spending" in maximize:
        objective = "maxSpending"
    else:
        objective = "maxBequest"

    options = {}
    optList = ["netSpending", "maxRothConversion", "noRothConversions",
               "startRothConversions", "withMedicare", "bequest", "solver",
               "spendingSlack", "oppCostX", "xorConstraints", "withSCLoop",]
    for opt in optList:
        val = getCaseKey(opt)
        if val is not None:
            options[opt] = val

    if getCaseKey("readRothX"):
        options["maxRothConversion"] = "file"

    previousMAGIs = getPreviousMAGIs()
    if previousMAGIs[0] > 0 or previousMAGIs[1] > 0:
        options["previousMAGIs"] = previousMAGIs

    return objective, options


def getIndividualAllocationRatios():
    generic = []
    ni = 2 if getCaseKey("status") == "married" else 1
    for i in range(ni):
        initial = []
        final = []
        for k1 in range(4):
            initial.append(int(getCaseKey(f"j3_init%{k1}_{i}")))
            final.append(int(getCaseKey(f"j3_fin%{k1}_{i}")))
        gen = [initial, final]
        generic.append(gen)

    return generic


def getAccountAllocationRatios():
    accounts = [[], [], []]
    ni = 2 if getCaseKey("status") == "married" else 1
    for i in range(ni):
        for j1 in range(3):
            initial = []
            final = []
            for k1 in range(4):
                initial.append(int(getCaseKey(f"j{j1}_init%{k1}_{i}")))
                final.append(int(getCaseKey(f"j{j1}_fin%{k1}_{i}")))
            tmp = [initial, final]
            accounts[j1].append(tmp)

    return accounts


def getPreviousMAGIs():
    backMAGIs = [0., 0.]
    for ii in range(2):
        val = getCaseKey(f"MAGI{ii}")
        if val:
            backMAGIs[ii] = float(val)

    return backMAGIs


def getFixedIncome(ni, what):
    amounts = []
    ages = []
    indexed = []
    for i in range(ni):
        amounts.append(getCaseKey(f"{what}Amt{i}"))
        age_y = getCaseKey(f"{what}Age_y{i}")
        age_m = getCaseKey(f"{what}Age_m{i}")
        age = age_y + age_m/12
        ages.append(age)
        if what == "p":
            indexed.append(getCaseKey(f"{what}Idx{i}"))

    return amounts, ages, indexed


def getDate(text, nkey, disabled=False, callback=setpull, help=None, min_value=None, max_value=None):
    widget_key = genCaseKey(nkey)
    kval = getCaseKey(nkey)
    value = date.fromisoformat(kval) if isinstance(kval, str) else date.today()
    initGlobalKey(widget_key, value)

    mydate = st.date_input(
        text,
        disabled=disabled,
        min_value=min_value,
        max_value=max_value,
        help=help,
        on_change=callback,
        args=[nkey],
        key=widget_key
    )
    if mydate is None:
        st.error("A date must be set.")
        return None
    else:
        isodate = mydate.strftime("%Y-%m-%d")
        setCaseKey(nkey, isodate)
        return isodate


def getIntNum(text, nkey, disabled=False, callback=setpull, step=1, help=None, min_value=0, max_value=None):
    widget_key = genCaseKey(nkey)
    kval = getCaseKey(nkey)
    value = 0 if kval is None else int(kval)
    initGlobalKey(widget_key, value)

    return st.number_input(
        text,
        disabled=disabled,
        min_value=min_value,
        max_value=max_value,
        step=step,
        help=help,
        on_change=callback,
        args=[nkey],
        key=widget_key,
    )


def getNum(text, nkey, disabled=False, callback=setpull, step=10.0, min_value=0.0,
           max_value=None, format="%.1f", help=None):
    widget_key = genCaseKey(nkey)
    kval = getCaseKey(nkey)
    value = 0.0 if kval is None else float(kval)
    initGlobalKey(widget_key, value)

    return st.number_input(
        text,
        disabled=disabled,
        step=step,
        help=help,
        min_value=min_value,
        max_value=max_value,
        format=format,
        on_change=callback,
        args=[nkey],
        key=widget_key
    )


def getText(text, nkey, disabled=False, callback=setpull, placeholder=None, help=None):
    widget_key = genCaseKey(nkey)
    initGlobalKey(widget_key, getCaseKey(nkey))

    return st.text_input(
        text,
        disabled=disabled,
        on_change=callback,
        args=[nkey],
        placeholder=placeholder,
        help=help,
        key=widget_key
    )


def getLongText(text, nkey, disabled=False, callback=setpull, placeholder=None, help=None):
    widget_key = genCaseKey(nkey)
    initGlobalKey(widget_key, getCaseKey(nkey))

    return st.text_area(
        text,
        disabled=disabled,
        on_change=callback,
        args=[nkey],
        placeholder=placeholder,
        help=help,
        key=widget_key
    )


def getRadio(text, choices, nkey, callback=setpull, disabled=False, help=None):
    widget_key = genCaseKey(nkey)
    case_value = getCaseKey(nkey)

    # Determine the value to use: widget state (if exists) > case key > default
    if widget_key in ss:
        # Widget state exists, use it
        widget_value = ss[widget_key]
    elif case_value is not None:
        # No widget state, use case key value
        widget_value = case_value
    else:
        # No value anywhere, use default
        widget_value = choices[0]

    # Find the index for the determined value
    try:
        index = choices.index(widget_value)
    except ValueError:
        st.error(f"Value '{widget_value}' not available. Defaulting to '{choices[0]}'.")
        widget_value = choices[0]
        index = 0

    return st.radio(
        text,
        choices,
        index=index,
        on_change=callback,
        args=[nkey],
        disabled=disabled,
        horizontal=True,
        help=help,
        key=widget_key
    )


def getToggle(text, nkey, callback=setpull, disabled=False, help=None):
    widget_key = genCaseKey(nkey)
    initGlobalKey(widget_key, getCaseKey(nkey))

    return st.toggle(
        text,
        on_change=callback, args=[nkey], disabled=disabled,
        help=help,
        key=widget_key
    )


def divider(color, width="auto"):
    st.html("<style> hr {border-color: %s;width: %s}</style><hr>" % (color, width))


def getColors():
    def_theme = "dark"
    bc = "#0E1117" if def_theme == "dark" else "#FFFFFF"
    fc = "#FAFAFA" if def_theme == "dark" else "#31333F"

    return bc, fc


def flagCurrentCase(caseName):
    if caseName == currentCaseName():
        return caseName + "🔻"
    else:
        return caseName


def titleBar(txt, allCases=False):
    if allCases:
        choices = allCaseNames()
        helpmsg = "Select an existing case, or create a new one from scratch or from a *case* parameter file."
    else:
        choices = onlyCaseNames()
        helpmsg = "Select an existing case."

    header = st.container()
    # header.title("Here is a sticky header")
    header.markdown("""<div class='fixed-header'/>""", unsafe_allow_html=True)

    bc, fc = getColors()

    position = getGlobalKey("position")
    # Custom CSS for the sticky header
    st.markdown(
        f"""<style>
    div[data-testid="stVerticalBlock"] div:has(div.fixed-header) {{
        border-radius: 10px;
        position: {position};
        background: linear-gradient(to right, #551b1b, #EFB761);
        /* background-color: %s; */
        color: %s;
        top: 2.875rem;
        z-index: 100;
    }}
</style>""" % (bc, fc), unsafe_allow_html=True
    )
    with header:
        col1, col2, col3, col4 = st.columns([0.005, 0.6, 0.4, 0.01], gap="small")
        with col2:
            st.markdown("## " + txt)
        with col3:
            nkey = txt
            ret = st.selectbox(
                "Case selector",
                choices,
                help=helpmsg,
                index=getIndex(currentCaseName(), choices),
                format_func=flagCurrentCase,
                key=nkey,
                on_change=switchToCase,
                args=[nkey],
            )

        divider("white", "99%")

    return ret
