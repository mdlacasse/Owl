"""
Streamlit session state key management module.

This module provides utilities for managing keys and data in Streamlit's
session state, including case management and data persistence.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
# flake8: noqa: E402

import streamlit as st
import pandas as pd
from datetime import date
import copy
import re
import json
import sys

sys.path.insert(0, "./src")
sys.path.insert(0, "../src")

from owlplanner.rate_models.constants import STOCHASTIC_METHODS


ss = st.session_state
newCase = "New Case..."
loadCaseFile = "Upload Case File..."
help1000 = "Values are in thousands of dollars (\\$k)."


def initGlobalKey(key, val):
    if key not in ss:
        ss[key] = val


def init():
    """
    Initialize variables through a function as it will only happen once through module.
    """
    # Dictionary of dictionaries for each case.
    global ss
    ss = st.session_state
    if "cases" not in ss:
        ss.cases = {}

    # Variable for storing name of current case.
    if "currentCase" not in ss:
        ss.currentCase = None

    initGlobalKey("plotGlobalBackend", "plotly")
    initGlobalKey("menuLocation", "top")
    initGlobalKey("position", "sticky")


init()


def genCaseKey(key):
    """
    This function is to generate global keys that are uniquely associated with a case.
    Uses case name when 'id' is not set (e.g. before a plan exists) to avoid "None_key" keys.
    """
    case_id = getCaseKey("id") or ss.currentCase
    return f"{case_id}_{key}"


def getKeyInCase(key, casename):
    if casename in ss.cases and key in ss.cases[casename]:
        return ss.cases[casename][key]
    return None


def onlyCaseNames() -> list:
    return list(ss.cases)


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


def has_current_case() -> bool:
    """True if a current case is set and exists in ss.cases (guards against reconnect state)."""
    return ss.currentCase is not None and ss.currentCase in ss.cases


def switchToCase(key):
    name = ss[key]
    # format_func adds 🔻 for display only; strip it if it leaked into the stored value.
    if isinstance(name, str) and name.endswith("🔻"):
        name = name[:-1]
    # Only set currentCase if the case exists (guards against reconnect/stale widget state).
    if name in ss.cases:
        ss.currentCase = name
    elif ss.currentCase is not None and ss.currentCase not in ss.cases:
        ss.currentCase = list(ss.cases)[0] if ss.cases else None


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
    Check that rates are set to a stochastic method before MC run.
    """
    return (caseIsNotRunReady() or getCaseKey("rateType") != "varying"
            or getCaseKey("varyingType") not in STOCHASTIC_METHODS)


def currentCaseDic() -> dict:
    return ss.cases[ss.currentCase]


def setCurrentCase(case):
    if case not in ss.cases:
        raise RuntimeError(f"Case {case} not found in dictionary")
    ss.currentCase = case


def copyCase():
    if ss.currentCase is None or ss.currentCase not in ss.cases:
        return
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
    st.toast("Case copied but not yet created.")


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

    from owlplanner.config import config_to_ui, default_config

    logs_strio = StringIO()
    base = {"name": casename, "caseStatus": "unknown", "logs": logs_strio, "id": None}
    # Eagerly populate all config keys from default_config so scratch-built cases
    # have complete config independent of which pages the user visits.
    defaults_ui = config_to_ui(default_config(ni=1))
    base.update(defaults_ui)
    base["name"] = casename  # Override case name from user input
    # Match createCaseFromFile / genDic: runtime keys not produced by config_to_ui.
    base.setdefault("plan", None)
    base["summaryDf"] = None
    base.setdefault("casetoml", "")
    ss.cases[casename] = base
    setCurrentCase(casename)


def renameCase(key):
    if ss.currentCase is None:
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
    if ss.currentCase is None:
        return
    del ss.cases[ss.currentCase]
    remaining = list(ss.cases)
    ss.currentCase = remaining[0] if remaining else None


def dumpSession():
    print("State Dump:", ss)


def dumpCase(case=None):
    if case is None:
        case = ss.currentCase
    print("Case Dump:", ss.cases[case])


def setpull(key):
    if ss.currentCase is None or ss.currentCase not in ss.cases:
        return None
    gen_key = genCaseKey(key)
    if gen_key not in ss:
        return None
    return setCaseKey(key, ss[gen_key])


def storepull(key):
    if ss.currentCase is None or ss.currentCase not in ss.cases:
        return None
    gen_key = genCaseKey(key)
    if gen_key not in ss:
        return None
    return storeCaseKey(key, ss[gen_key])


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
    if ss.currentCase is None or ss.currentCase not in ss.cases:
        return None
    ss.cases[ss.currentCase][key] = val
    return val


def _get_default_ui_keys(ni: int) -> dict:
    """Return default UI keys from config (single source of truth)."""
    from owlplanner.config import config_to_ui, default_config

    return config_to_ui(default_config(ni=ni))


def ensureCaseConfigDefaults(ni: int | None = None) -> None:
    """
    Merge missing config-derived keys into the current case.

    Fills any keys present in default_config that are missing from the case,
    e.g. when status switches to married (spouse keys) or for legacy cases.
    Does not overwrite existing keys.
    """
    if ss.currentCase is None or ss.currentCase not in ss.cases:
        return
    if ni is None:
        status = ss.cases[ss.currentCase].get("status", "single")
        ni = 2 if status == "married" else 1
    defaults = _get_default_ui_keys(ni)
    case = ss.cases[ss.currentCase]
    for k, v in defaults.items():
        if k not in case:
            case[k] = v


def initCaseKey(key, val):
    """
    Set the case key if unset. Uses config defaults when the key is
    present in default_config output; otherwise uses the provided val.

    This consolidates default logic so config keys (life expectancy, SS age,
    rates, etc.) come from the config layer rather than scattered page literals.
    """
    if ss.currentCase is None or ss.currentCase not in ss.cases:
        return
    case = ss.cases[ss.currentCase]
    if key in case:
        return
    status = case.get("status", "single")
    ni = 2 if status == "married" else 1
    defaults = _get_default_ui_keys(ni)
    if key in defaults:
        storeCaseKey(key, defaults[key])
    else:
        storeCaseKey(key, val)


def getCaseKey(key):
    if ss.currentCase is None or ss.currentCase not in ss.cases:
        return None
    return ss.cases[ss.currentCase].get(key)


def storeGlobalKey(key, val):
    ss[key] = val
    return val


def getGlobalKey(key):
    return ss.get(key)


def getDict(key=ss.currentCase):
    return ss.cases[key]


def getAccountBalances(ni):
    bal = [[], [], [], []]
    accounts = ["txbl", "txDef", "txFree", "hsa"]
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
    current = currentCaseName()
    # Copy and re-index with the case dict key to guarantee unique row labels.
    df = df.copy()
    df.index = [current]
    for case in onlyCaseNames():
        if case == current:
            continue
        odf = ss.cases[case]["summaryDf"]
        if odf is None or set(odf.columns) != set(df.columns):
            continue
        odf = odf.copy()
        odf.index = [case]
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
    """
    From UI to Plan.
    The UI has a flat dictionary, while the Plan has a separate embedded dictionary for solver options.
    This function only builds the solver camelCase dictionary.
    """

    maximize = getCaseKey("objective")
    if maximize is None:
        return None
    if "spending" in maximize:
        objective = "maxSpending"
    elif "bequest" in maximize.lower():
        objective = "maxBequest"
    else:
        objective = "maxHybrid"

    options = {}
    optList = ["netSpending", "maxRothConversion", "noRothConversions",
               "startRothConversions", "bequest", "solver",
               "spendingSlack", "spendingWeight", "spendingFloor", "timePreference", "oppCostX",
               "amoRoth", "amoSurplus", "withSCLoop", "noLateSurplus",]

    for opt in optList:
        val = getCaseKey(opt)
        if val is not None:
            options[opt] = val

    # These need translation.
    medion = getCaseKey("computeMedicare")
    mediopt = getCaseKey("optimizeMedicare")
    options["withMedicare"] = "none" if not medion else ("optimize" if mediopt else "loop")
    acaopt = getCaseKey("optimizeACA")
    options["withACA"] = "optimize" if acaopt else "loop"
    ltcgopt = getCaseKey("optimizeLTCG")
    options["withLTCG"] = "optimize" if ltcgopt else "loop"
    niitopt = getCaseKey("optimizeNIIT")
    options["withNIIT"] = "optimize" if niitopt else "loop"
    decomp_mode = getCaseKey("useDecomposition") or "none"
    # Treat legacy boolean True as "sequential"; force "none" if no optimize mode is active.
    if decomp_mode is True:
        decomp_mode = "sequential"
    if not (mediopt or acaopt or ltcgopt or niitopt):
        decomp_mode = "none"
    options["withDecomposition"] = decomp_mode

    # SS taxability — "loop", "optimize", or numeric fixed fraction.
    ss_mode = getCaseKey("ssTaxabilityMode")
    if ss_mode == "value":
        options["withSSTaxability"] = getCaseKey("ssTaxabilityValue")
    else:
        options["withSSTaxability"] = ss_mode if ss_mode is not None else "loop"

    if getCaseKey("readRothX"):
        options["maxRothConversion"] = "file"

    # Build minTaxableBalance list from per-spouse UI values (today's $k)
    ni = 2 if getCaseKey("status") == "married" else 1
    min_taxable = [
        float(getCaseKey("minTaxableBalance0") or 0),
        float(getCaseKey("minTaxableBalance1") or 0),
    ][:ni]
    if any(v > 0 for v in min_taxable):
        options["minTaxableBalance"] = min_taxable

    previousMAGIs = getPreviousMAGIs()
    if previousMAGIs[0] > 0 or previousMAGIs[1] > 0:
        options["previousMAGIs"] = previousMAGIs

    # Process extra solver options from JSON string
    xtra_options_str = getCaseKey("xtra_options")
    if xtra_options_str and xtra_options_str.strip():
        try:
            xtra_options = json.loads(xtra_options_str)
            if isinstance(xtra_options, dict):
                options.update(xtra_options)
            else:
                st.warning("Extra solver options must be a JSON object (dictionary).")
        except json.JSONDecodeError as e:
            st.warning(f"Invalid JSON in extra solver options: {e}")

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
    accounts = [[], [], [], []]
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
        # HSA uses "jhsa_" prefix to avoid collision with j3_ (individual mode)
        hsa_initial = []
        hsa_final = []
        for k1 in range(4):
            hsa_initial.append(int(getCaseKey(f"jhsa_init%{k1}_{i}") or 0))
            hsa_final.append(int(getCaseKey(f"jhsa_fin%{k1}_{i}") or 0))
        accounts[3].append([hsa_initial, hsa_final])

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
        # Only mark case modified when the value actually changed.
        if isodate != getCaseKey(nkey):
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
        height="content",
        on_change=callback,
        args=[nkey],
        placeholder=placeholder,
        help=help,
        key=widget_key
    )


def getSlider(text, nkey, min_value=0.0, max_value=1.0, step=0.05, disabled=False, help=None):
    widget_key = genCaseKey(nkey)
    kval = getCaseKey(nkey)
    value = min_value if kval is None else float(kval)
    initGlobalKey(widget_key, value)

    return st.slider(
        text,
        disabled=disabled,
        min_value=min_value,
        max_value=max_value,
        step=step,
        help=help,
        on_change=setpull,
        args=[nkey],
        key=widget_key,
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

    # Coerce legacy boolean values (True → first non-"none" choice, False → first choice).
    if isinstance(widget_value, bool):
        widget_value = choices[1] if widget_value and len(choices) > 1 else choices[0]

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


def getSelectbox(text, choices, nkey, callback=setpull, disabled=False, help=None):
    widget_key = genCaseKey(nkey)
    case_value = getCaseKey(nkey)
    if widget_key in ss:
        widget_value = ss[widget_key]
    elif case_value is not None:
        widget_value = case_value
    else:
        widget_value = choices[0]
    try:
        index = choices.index(widget_value)
    except ValueError:
        st.error(f"Value '{widget_value}' not available. Defaulting to '{choices[0]}'.")
        widget_value = choices[0]
        index = 0
    return st.selectbox(text, choices, index=index, on_change=callback, args=[nkey],
                        disabled=disabled, help=help, key=widget_key)


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


def titleBar(txt):
    choices = onlyCaseNames()
    helpmsg = "Switch to a different case."

    # Ensure current case has all config-derived defaults (handles legacy cases,
    # status changes to married, etc.)
    if currentCaseName() and currentCaseName() in ss.cases:
        ensureCaseConfigDefaults()

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
            # Manage the selectbox value entirely through session state to avoid
            # the "default value + ss API" conflict.  Set ss[nkey] before the
            # widget renders so Streamlit never needs to infer a default.
            current = currentCaseName()
            if current is not None and current in choices:
                ss[nkey] = current
            else:
                ss[nkey] = None  # placeholder: no case, deleted case, or stale state
            ret = st.selectbox(
                "Case selector",
                choices,
                help=helpmsg,
                format_func=flagCurrentCase,
                key=nkey,
                on_change=switchToCase,
                args=[nkey],
            )

        divider("white", "99%")

    return ret
