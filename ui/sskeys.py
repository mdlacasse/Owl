"""
Module for storing keys in Streamlit session state.
"""

import streamlit as st
import pandas as pd
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
            newCase: {"iname0": "", "status": "unkown", "caseStatus": "new"},
            loadCaseFile: {"iname0": "", "status": "unkown", "caseStatus": "new"},
        }

    # Variable for storing name of current case.
    if "currentCase" not in ss:
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
    key = "oNcE_" + func.__name__
    if getGlobalKey(key) is None:
        func()
        storeGlobalKey(key, 1)


def runOncePerCase(func):
    key = "oNcE_" + func.__name__
    if getKey(key) is None:
        func()
        storeKey(key, 1)


def refreshCase(adic):
    """
    When a case is duplicated, reset all the runOnce functions.
    """
    for key in list(adic):
        if key.startswith("oNcE_"):
            del adic[key]


def resetTimeLists():
    setKey("stTimeLists", None)
    setKey("timeList0", None)
    if getKey("status") == "married":
        setKey("timeList1", None)


def getIndex(item, choices):
    try:
        i = choices.index(item)
    except ValueError:
        return None

    return i


def currentCaseName() -> str:
    return ss.currentCase


def updateContributions():
    noChange = (getKey("_timeList0") is None or getKey("_timeList0").equals(getKey("timeList0"))) and (
        getKey("_timeList1") is None or getKey("_timeList1").equals(getKey("timeList1"))
    )
    if noChange:
        return True

    setKey("timeList0", getKey("_timeList0"))
    setKey("timeList1", getKey("_timeList1"))


def switchToCase(key):
    # Catch case where switch happens while editing W&W tables.
    if getGlobalKey("currentPageName") == "Wages And Contributions":
        updateContributions()
    ss.currentCase = ss["_" + key]


def isIncomplete():
    return (
        currentCaseName() == ""
        or getKey("iname0") in [None, ""]
        or (getKey("status") == "married" and getKey("iname1") in [None, ""])
    )


def isCaseUnsolved():
    if caseHasNoPlan():
        return True
    return getKey("caseStatus") != "solved"


def caseHasNoPlan():
    return getKey("plan") is None


def caseHasPlan():
    return getKey("plan") is not None


def caseIsRunReady():
    return not caseIsNotRunReady() and getKey("caseStatus") in ["modified", "new"]


def caseIsNotRunReady():
    return (
        getKey("plan") is None
        or getKey("objective") is None
        or getKey("rateType") is None
        or getKey("interpMethod") is None
        or getKey("spendingProfile") is None
        or getKey("allocType") is None
    )


def caseIsNotMCReady():
    """
    Check that rates are  set to some stochastic method before MC run.
    """
    return caseIsNotRunReady() or getKey("rateType") != "varying" or "tochastic" not in getKey("varyingType")


def currentCaseDic() -> dict:
    return ss.cases[ss.currentCase]


def setCurrentCase(case):
    if case not in ss.cases:
        raise RuntimeError(f"Case {case} not found in dictionary")
    ss.currentCase = case


def duplicateCase():
    baseName = re.sub(r"\s*\(\d+\)$", "", ss.currentCase)
    for i in range(1, 10):
        dupname = baseName + f"({i})"
        if dupname not in ss.cases:
            break
    else:
        raise RuntimeError("Exhausted number of duplicates")

    # Copy everything except the plan itself.
    # print(ss.currentCase, "->", ss.cases[ss.currentCase])
    currentPlan = ss.cases[ss.currentCase]["plan"]
    ss.cases[ss.currentCase]["plan"] = None
    ss.cases[dupname] = copy.deepcopy(ss.cases[ss.currentCase])
    ss.cases[ss.currentCase]["plan"] = currentPlan

    ss.cases[dupname]["name"] = dupname
    for key in ["summaryDf", "histoPlot", "histoSummary", "monteCarloPlot", "monteCarloSummary"]:
        ss.cases[dupname][key] = None

    ss.cases[dupname]["duplicate"] = True
    refreshCase(ss.cases[dupname])
    ss.currentCase = dupname
    st.toast("Case duplicated except for Wages and Contributions tables.")


def createCaseFromFile(strio):
    import owlbridge as owb

    name, dic = owb.createCaseFromFile(strio)
    if name == "":
        return False
    elif name in ss.cases:
        st.error(f"Case name '{name}' already exists.")
        return False

    ss.cases[name] = dic
    setCurrentCase(name)
    return True


def createNewCase(case):
    if case != "newcase":
        st.error(f"Expected 'newcase' but got '{case}'.")
        return

    # Widget stored case name in _newname.
    casename = ss._newcase

    if casename == "":
        return

    if casename in ss.cases:
        st.error(f"Case name '{casename}' already exists.")
        return

    ss.cases[casename] = {"name": casename, "caseStatus": "unknown", "logs": None}
    setCurrentCase(ss._newcase)


def renameCase(key):
    if ss.currentCase == newCase or ss.currentCase == loadCaseFile:
        return
    newname = ss["_" + key]
    plan = getKey("plan")
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
    return setKey(key, ss["_" + key])


def storepull(key):
    return storeKey(key, ss["_" + key])


def setKey(key, val):
    ss.cases[ss.currentCase][key] = val
    flagModified()
    return val


def flagModified():
    ss.cases[ss.currentCase]["caseStatus"] = "modified"
    ss.cases[ss.currentCase]["summaryDf"] = None


def storeKey(key, val):
    ss.cases[ss.currentCase][key] = val
    return val


def initKey(key, val):
    if key not in ss.cases[ss.currentCase]:
        ss.cases[ss.currentCase][key] = val
        # print("initKey", key, val)


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
    accounts = ["txbl", "txDef", "txFree"]
    for j, acc in enumerate(accounts):
        for i in range(ni):
            bal[j].append(getKey(acc + str(i)))

    return bal


def colorBySign(val):
    color = "green" if "\u2191" in val else "red" if "\u2193" in val else None

    return f"color:{color};" if color else ""


def compareSummaries():
    df = getKey("summaryDf")
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
    maximize = getKey("objective")
    if maximize is None:
        return None
    if "spending" in maximize:
        objective = "maxSpending"
    else:
        objective = "maxBequest"

    options = {}
    optList = ["netSpending", "maxRothConversion", "noRothConversions", "startRothConversions",
               "withMedicare", "bequest", "solver", "spendingSlack", "oppCostX"]
    for opt in optList:
        val = getKey(opt)
        if val is not None:
            options[opt] = val

    if getKey("readRothX"):
        options["maxRothConversion"] = "file"

    previousMAGIs = getPreviousMAGIs()
    if previousMAGIs[0] > 0 or previousMAGIs[1] > 0 or previousMAGIs[2] > 0:
        options["previousMAGIs"] = previousMAGIs

    return objective, options


def getIndividualAllocationRatios():
    generic = []
    ni = 2 if getKey("status") == "married" else 1
    for i in range(ni):
        initial = []
        final = []
        for k1 in range(4):
            initial.append(int(getKey(f"j3_init%{k1}_{i}")))
            final.append(int(getKey(f"j3_fin%{k1}_{i}")))
        gen = [initial, final]
        generic.append(gen)

    return generic


def getAccountAllocationRatios():
    accounts = [[], [], []]
    ni = 2 if getKey("status") == "married" else 1
    for i in range(ni):
        for j1 in range(3):
            initial = []
            final = []
            for k1 in range(4):
                initial.append(int(getKey(f"j{j1}_init%{k1}_{i}")))
                final.append(int(getKey(f"j{j1}_fin%{k1}_{i}")))
            tmp = [initial, final]
            accounts[j1].append(tmp)

    return accounts


def getPreviousMAGIs():
    backMAGIs = [0., 0., 0.]
    for ii in range(3):
        val = getKey(f"MAGI{ii}")
        if val:
            backMAGIs[ii] = float(val)

    return backMAGIs


def getFixedIncome(ni, what):
    amounts = []
    ages = []
    indexed = []
    for i in range(ni):
        amounts.append(getKey(what + "Amt" + str(i)))
        ages.append(getKey(what + "Age" + str(i)))
        if what == "p":
            indexed.append(getKey(what + "Idx" + str(i)))

    return amounts, ages, indexed


def getIntNum(text, nkey, disabled=False, callback=setpull, step=1, help=None, min_value=0, max_value=None):
    return st.number_input(
        text,
        value=int(getKey(nkey)),
        disabled=disabled,
        min_value=min_value,
        max_value=max_value,
        step=step,
        help=help,
        on_change=callback,
        args=[nkey],
        key="_" + nkey,
    )


def getNum(
    text, nkey, disabled=False, callback=setpull, step=10.0, min_value=0.0, max_value=None, format="%.1f", help=None
):
    return st.number_input(
        text,
        value=float(getKey(nkey)),
        disabled=disabled,
        step=step,
        help=help,
        min_value=min_value,
        max_value=max_value,
        format=format,
        on_change=callback,
        args=[nkey],
        key="_" + nkey,
    )


def getText(text, nkey, disabled=False, callback=setpull, placeholder=None, help=None):
    return st.text_input(
        text,
        value=getKey(nkey),
        disabled=disabled,
        on_change=callback,
        args=[nkey],
        key="_" + nkey,
        placeholder=placeholder,
        help=help,
    )


def getLongText(text, nkey, disabled=False, callback=setpull, placeholder=None, help=None):
    return st.text_area(
        text,
        value=getKey(nkey),
        disabled=disabled,
        on_change=callback,
        args=[nkey],
        key="_" + nkey,
        placeholder=placeholder,
        help=help,
    )


def getRadio(text, choices, nkey, callback=setpull, disabled=False, help=None):
    return st.radio(
        text,
        choices,
        index=choices.index(getKey(nkey)),
        on_change=callback,
        args=[nkey],
        key="_" + nkey,
        disabled=disabled,
        horizontal=True,
        help=help,
    )


def getToggle(text, nkey, callback=setpull, disabled=False, help=None):
    return st.toggle(
        text, value=getKey(nkey), on_change=callback, args=[nkey], disabled=disabled, key="_" + nkey, help=help
    )


def divider(color, width="auto"):
    st.html("<style> hr {border-color: %s;width: %s}</style><hr>" % (color, width))


def getColors():
    def_theme = "dark"
    bc = "#0E1117" if def_theme == "dark" else "#FFFFFF"
    fc = "#FAFAFA" if def_theme == "dark" else "#31333F"

    return bc, fc


def titleBar(txt, choices=None):
    if choices is None:
        choices = onlyCaseNames()
        helpmsg = "Select an existing case."
    else:
        helpmsg = "Select an existing case, or create a new one from scratch or from a *case* parameter file."

    header = st.container()
    # header.title("Here is a sticky header")
    header.write("""<div class='fixed-header'/>""", unsafe_allow_html=True)

    bc, fc = getColors()

    # Custom CSS for the sticky header
    st.markdown(
        """<style>
    div[data-testid="stVerticalBlock"] div:has(div.fixed-header) {
        border-radius: 10px;
        position: sticky;
        background: linear-gradient(to right, #551b1b, #909090);
        /* background-color: %s; */
        color: %s;
        top: 2.875rem;
        z-index: 100;
    }
</style>""" % (bc, fc), unsafe_allow_html=True
    )
    with header:
        col1, col2, col3, col4 = st.columns([0.005, 0.6, 0.4, 0.01], gap="small")
        with col2:
            st.write("## " + txt)
        with col3:
            nkey = txt
            ret = st.selectbox(
                "Case selector",
                choices,
                help=helpmsg,
                index=getIndex(currentCaseName(), choices),
                key="_" + nkey,
                on_change=switchToCase,
                args=[nkey],
            )

        divider("white", "99%")

    return ret
