import streamlit as st
import pandas as pd
from io import StringIO, BytesIO
from functools import wraps
from datetime import datetime, date
import importlib
import sys

sys.path.insert(0, "./src")
sys.path.insert(0, "../src")

import owlplanner as owl                      # noqa: E402
from owlplanner.rates import FROM, TO         # noqa: E402

import sskeys as kz         # noqa: E402
import progress             # noqa: E402


def hasMOSEK():
    spec = importlib.util.find_spec("mosek")
    return spec is not None


def createPlan():
    name = kz.currentCaseName()
    inames = [kz.getKey("iname0")]
    description = kz.getKey("description")
    yobs = [kz.getKey("yob0")]
    life = [kz.getKey("life0")]
    if kz.getKey("status") == "married":
        inames.append(kz.getKey("iname1"))
        yobs.append(kz.getKey("yob1"))
        life.append(kz.getKey("life1"))

    strio = StringIO()
    kz.storeKey("logs", strio)
    try:
        plan = owl.Plan(inames, yobs, life, name,
                        verbose=True, logstreams=[strio, strio])
        kz.setKey("plan", plan)
    except Exception as e:
        st.error(f"Failed creation of plan '{name}': {e}")
        return

    plan.setDescription(description)

    val = kz.getGlobalKey("plotGlobalBackend")
    if val:
        plan.setPlotBackend(val)

    # Set default plot value from case settings.
    plot_val = kz.getKey("plots")
    if plot_val:
        plan.setDefaultPlots(plot_val)

    # Force to pull key and set profile if key was defined.
    if kz.getKey("spendingProfile"):
        setProfile(None)

    if kz.getKey("duplicate"):
        _setContributions(plan, "copy")
    else:
        resetTimeLists()

    st.toast(f"Created new case *'{name}'*. You can now move to the next page.")


def _checkPlan(func):
    """
    Decorator to check if plan was created properly.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        plan = kz.getKey("plan")
        if plan is None:
            st.error(f"Plan not yet created. Preventing to execute method {func.__name__}().")
            return None
        return func(plan, *args, **kwargs)

    return wrapper


def prepareRun(plan):
    ni = 2 if kz.getKey("status") == "married" else 1

    startDate = kz.getKey("startDate")
    bal = kz.getAccountBalances(ni)
    try:
        plan.setAccountBalances(taxable=bal[0], taxDeferred=bal[1], taxFree=bal[2], startDate=startDate)
    except Exception as e:
        st.error(f"Setting account balances failed: {e}")
        return

    amounts, ages, indexed = kz.getFixedIncome(ni, "p")
    try:
        plan.setPension(amounts, ages, indexed)
    except Exception as e:
        st.error(f"Failed setting pensions: {e}")
        return

    amounts, ages, indexed = kz.getFixedIncome(ni, "ss")
    try:
        plan.setSocialSecurity(amounts, ages)
    except Exception as e:
        st.error(f"Failed setting social security: {e}")
        return

    if ni == 2:
        benfrac = [kz.getKey("benf0"), kz.getKey("benf1"), kz.getKey("benf2")]
        try:
            plan.setBeneficiaryFractions(benfrac)
        except Exception as e:
            st.error(f"Failed setting beneficiary fractions: {e}")
            return

        surplusFrac = kz.getKey("surplusFraction")
        try:
            plan.setSpousalDepositFraction(surplusFrac)
        except Exception as e:
            st.error(f"Failed setting beneficiary fractions: {e}")
            return

    plan.setDescription(kz.getKey("description"))
    plan.setHeirsTaxRate(kz.getKey("heirsTx"))
    plan.setLongTermCapitalTaxRate(kz.getKey("gainTx"))
    plan.setDividendRate(kz.getKey("divRate"))
    plan.setExpirationYearTCJA(kz.getKey("yTCJA"))

    _setInterpolationMethod(plan)
    _setAllocationRatios(plan)
    _setRates(plan)
    _setContributions(plan, "set")


def runAllCases():
    currentCase = kz.currentCaseName()
    for case in kz.onlyCaseNames():
        # Being here, current case must be fine.
        if case != currentCase:
            kz.switchToCaseName(case)
            runPlan()
    kz.switchToCaseName(currentCase)


@_checkPlan
def runPlan(plan):
    prepareRun(plan)

    objective, options = kz.getSolveParameters()
    try:
        plan.solve(objective, options=options)
    except Exception as e:
        st.error(f"Solution failed: {e}")
        kz.storeKey("caseStatus", "exception")
        kz.storeKey("summaryDf", None)
        return

    kz.storeKey("caseStatus", plan.caseStatus)
    if plan.caseStatus == "solved":
        kz.storeKey("summaryDf", plan.summaryDf())
        kz.storeKey("casetoml", getCaseString().getvalue())
    else:
        kz.storeKey("summaryDf", None)
        kz.storeKey("casetoml", "")


@_checkPlan
def runHistorical(plan):
    plan1 = owl.clone(plan)
    prepareRun(plan1)

    hyfrm = kz.getKey("hyfrm")
    hyto = kz.getKey("hyto")

    objective, options = kz.getSolveParameters()
    try:
        mybar = progress.Progress(None)
        fig, summary = plan1.runHistoricalRange(objective, options, hyfrm, hyto, figure=True, progcall=mybar)
        kz.storeKey("histoPlot", fig)
        kz.storeKey("histoSummary", summary)
    except Exception as e:
        kz.storeKey("histoPlot", None)
        kz.storeKey("histoSummary", None)
        st.error(f"Historical solution failed: {e}")
        return


@_checkPlan
def runMC(plan):
    plan1 = owl.clone(plan)
    prepareRun(plan1)

    N = kz.getKey("MC_cases")

    objective, options = kz.getSolveParameters()
    try:
        mybar = progress.Progress(None)
        fig, summary = plan1.runMC(objective, options, N, figure=True, progcall=mybar)
        kz.storeKey("monteCarloPlot", fig)
        kz.storeKey("monteCarloSummary", summary)
    except Exception as e:
        kz.storeKey("monteCarloPlot", None)
        kz.storeKey("monteCarloSummary", None)
        st.error(f"Monte Carlo solution failed: {e}")


@_checkPlan
def setRates(plan):
    _setRates(plan)


def _setRates(plan):
    yfrm = kz.getKey("yfrm")
    yto = kz.getKey("yto")

    if kz.getKey("rateType") == "fixed":
        if kz.getKey("fixedType") == "historical average":
            plan.setRates("historical average", yfrm, yto)
            # Set fxRates back to computed values.
            for j in range(4):
                kz.storeKey("fxRate" + str(j), 100 * plan.tau_kn[j, -1])
        else:
            plan.setRates(
                "user",
                values=[
                    float(kz.getKey("fxRate0")),
                    float(kz.getKey("fxRate1")),
                    float(kz.getKey("fxRate2")),
                    float(kz.getKey("fxRate3")),
                ],
            )
    else:
        varyingType = kz.getKey("varyingType")
        if varyingType.startswith("histo"):
            if varyingType == "historical":
                yfrm2 = min(yfrm, TO - plan.N_n + 1)
                kz.storeKey("yfrm", yfrm2)
                if yfrm != yfrm2:
                    yfrm = yfrm2
                    st.warning(f"Using {yfrm} as starting year.")
                yto = min(TO, yfrm + plan.N_n - 1)
                kz.storeKey("yto", yto)
            plan.setRates(varyingType, yfrm, yto)
            mean, stdev, corr, covar = owl.getRatesDistributions(yfrm, yto, plan.mylog)
            for j in range(4):
                kz.storeKey("mean" + str(j), 100 * mean[j])
                kz.storeKey("stdev" + str(j), 100 * stdev[j])
            q = 1
            for k1 in range(plan.N_k):
                for k2 in range(k1 + 1, plan.N_k):
                    kz.storeKey("corr" + str(q), corr[k1, k2])
                    q += 1

        elif varyingType == "stochastic":
            means = []
            stdev = []
            corr = []
            for kk in range(plan.N_k):
                means.append(kz.getKey("mean" + str(kk)))
                stdev.append(kz.getKey("stdev" + str(kk)))
            for q in range(1, 7):
                corr.append(kz.getKey("corr" + str(q)))
            plan.setRates(varyingType, values=means, stdev=stdev, corr=corr)
        else:
            raise RuntimeError("Logic error in setRates()")

    return True


@_checkPlan
def showAllocations(plan):
    figures = plan.showAllocations(figure=True)
    st.divider()
    st.markdown("#### :orange[Asset Allocation]")
    # n = 3 if kz.getKey("allocType") == "account" else 2
    n = 2
    c = 0
    cols = st.columns(n, gap="medium")
    for fig in figures:
        renderPlot(fig, cols[c])
        c = (c + 1) % n


@_checkPlan
def showProfile(plan, col):
    fig = plan.showProfile(figure=True)
    if fig:
        col.write("#### :orange[Spending Profile]")
        renderPlot(fig, col)


@_checkPlan
def showRates(plan, col):
    fig = plan.showRates(figure=True)
    if fig:
        col.write("#### :orange[Selected Rates Over Time Horizon]")
        renderPlot(fig, col)


@_checkPlan
def showRatesCorrelations(plan, col):
    fig = plan.showRatesCorrelations(figure=True)
    if fig:
        col.write("#### :orange[Correlations Between Return Rates]")
        renderPlot(fig, col)


@_checkPlan
def showIncome(plan):
    fig = plan.showIncome(figure=True)
    if fig:
        renderPlot(fig)


@_checkPlan
def showSources(plan):
    fig = plan.showSources(figure=True)
    if fig:
        renderPlot(fig)


@_checkPlan
def setInterpolationMethod(plan):
    _setInterpolationMethod(plan)


def _setInterpolationMethod(plan):
    plan.setInterpolationMethod(kz.getKey("interpMethod"), kz.getKey("interpCenter"),
                                kz.getKey("interpWidth"))


@_checkPlan
def setContributions(plan, reset=True):
    _setContributions(plan, "reset")


def _setContributions(plan, action):
    """
    Set from UI -> Plan.
    """
    if kz.getKey("timeList0") is None:
        return

    dicDf = {kz.getKey("iname0"): kz.getKey("timeList0")}
    if kz.getKey("status") == "married":
        dicDf[kz.getKey("iname1")] = kz.getKey("timeList1")

    try:
        plan.readContributions(dicDf)
    except Exception as e:
        st.error(f"Failed to parse Wages and Contributions: {e}")
        return False

    if action == "copy":
        # Possible reconditionned data due to delta in year span.
        kz.setKey("timeList0", plan.timeLists[kz.getKey("iname0")])
        if kz.getKey("status") == "married":
            kz.setKey("timeList1", plan.timeLists[kz.getKey("iname1")])
    elif action == "reset":
        kz.setKey("timeListsFileName", "edited values")
    elif action == "set":
        kz.storeKey("timeListsFileName", "edited values")

    plan.timeListsFileName = "edited values"


@_checkPlan
def readContributions(plan, stFile):
    """
    Set from file -> Plan -> UI.
    """
    if stFile is None:
        return False

    try:
        plan.readContributions(stFile)
        kz.setKey("timeListsFileName", stFile.name)
        kz.setKey("timeList0", plan.timeLists[kz.getKey("iname0")])
        kz.setKey("_timeList0", plan.timeLists[kz.getKey("iname0")])
        if kz.getKey("status") == "married":
            kz.setKey("timeList1", plan.timeLists[kz.getKey("iname1")])
            kz.setKey("_timeList1", plan.timeLists[kz.getKey("iname1")])
        plan.timeListsFileName = stFile.name
    except Exception as e:
        st.error(f"Failed to parse contributions file 'stFile.name': {e}")
        return False

    return True


@_checkPlan
def resetContributions(plan):
    return plan.zeroContributions()


def resetTimeLists():
    tlists = resetContributions()
    for i, iname in enumerate(tlists):
        kz.setKey("timeList" + str(i), tlists[iname])


@_checkPlan
def setAllocationRatios(plan):
    _setAllocationRatios(plan)


def _setAllocationRatios(plan):
    if kz.getKey("allocType") == "individual":
        try:
            generic = kz.getIndividualAllocationRatios()
            plan.setAllocationRatios("individual", generic=generic)
        except Exception as e:
            st.error(f"Setting asset allocation failed: {e}")
            return
    elif kz.getKey("allocType") == "account":
        try:
            acc = kz.getAccountAllocationRatios()
            plan.setAllocationRatios("account", taxable=acc[0], taxDeferred=acc[1], taxFree=acc[2])
        except Exception as e:
            st.error(f"Setting asset allocation failed: {e}")
            return
    else:
        st.error(f"Internal error: Unknown account type {kz.getKey('allocType')}.")


@_checkPlan
def plotSingleResults(plan):
    c = 0
    n = 2
    cols = st.columns(n, gap="medium")
    fig = plan.showRates(figure=True)
    if fig:
        cols[c].write("#### :orange[Annual Rates]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showNetSpending(figure=True)
    if fig:
        cols[c].write("#### :orange[Net Available Spending]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showGrossIncome(figure=True)
    if fig:
        cols[c].write("#### :orange[Taxable Ordinary Income]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    # st.divider()
    # cols = st.columns(n, gap="medium")
    fig = plan.showSources(figure=True)
    if fig:
        cols[c].write("#### :orange[Raw Income Sources]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showAccounts(figure=True)
    if fig:
        cols[c].write("#### :orange[Savings Balance]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showTaxes(figure=True)
    if fig:
        cols[c].write("#### :orange[Taxes and Medicare (+IRMAA)]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    c = 0
    figs = plan.showAssetComposition(figure=True)
    if figs:
        # st.divider()
        st.write("#### :orange[Asset Composition]")
        col1, col2, _ = st.columns([0.6, 0.2, 0.2], gap="medium")
        for fig in figs:
            if fig:
                renderPlot(fig, col1)
            else:
                col1.write("#\n<div style='text-align: center'> This plot is empty </div>",
                           unsafe_allow_html=True)
            # c = (c + 1) % n


@_checkPlan
def setProfile(plan, key):
    if key is not None:
        kz.setpull(key)
    else:
        kz.flagModified()
    profile = kz.getKey("spendingProfile")
    survivor = kz.getKey("survivor")
    dip = kz.getKey("smileDip")
    increase = kz.getKey("smileIncrease")
    delay = kz.getKey("smileDelay")
    plan.setSpendingProfile(profile, survivor, dip, increase, delay)


@_checkPlan
def setDefaultPlots(plan, key):
    val = kz.storepull(key)
    plan.setDefaultPlots(val)


def setGlobalPlotBackend(key):
    val = kz.getGlobalKey("_"+key)
    kz.storeGlobalKey(key, val)
    # Apply to all existing cases.
    for casename in kz.onlyCaseNames():
        plan = kz.getKeyInCase("plan", casename)
        if plan:
            plan.setPlotBackend(val)


@_checkPlan
def showWorkbook(plan):
    wb = plan.saveWorkbook(saveToFile=False)
    if wb is None:
        return

    currencySheets = ["Income", "Cash Flow", "Sources", "Accounts"]
    for name in wb.sheetnames:
        if name == "Summary":
            continue

        dollars = False
        for word in currencySheets:
            if word in name:
                dollars = True
                break

        ws = wb[name]
        df = pd.DataFrame(ws.values)
        new_header = df.iloc[0]
        df = df[1:]
        df.columns = new_header
        if dollars:
            colfor = {}
            for col in df.columns:
                if col == "year":
                    colfor[col] = st.column_config.NumberColumn(None, format="%d", width="small")
                else:
                    # colfor[col] = st.column_config.NumberColumn(None, format="$ %,.0f")
                    colfor[col] = st.column_config.NumberColumn(None, format="accounting", step=1)
        else:
            colfor = {}
            for col in df.columns:
                if col == "year":
                    colfor[col] = st.column_config.NumberColumn(None, format="%d", width="small")
                else:
                    colfor[col] = st.column_config.NumberColumn(None, format="%.3f")

        st.write(f"##### :orange[{name}]")
        st.dataframe(df.astype(str), use_container_width=True, column_config=colfor, hide_index=True)

        if dollars:
            st.caption("Values are in nominal $, rounded to the nearest dollar.")
        else:
            st.caption("Values are fractional.")


@_checkPlan
def saveWorkbook(plan):
    wb = plan.saveWorkbook(saveToFile=False)
    buffer = BytesIO()
    if wb is None:
        return buffer
    try:
        wb.save(buffer)
    except Exception as e:
        raise Exception(f"Unanticipated exception: {e}.") from e

    return buffer


@_checkPlan
def saveContributions(plan):
    wb = plan.saveContributions()
    buffer = BytesIO()
    if wb is None:
        return buffer
    try:
        wb.save(buffer)
    except Exception as e:
        raise Exception(f"Unanticipated exception: {e}.") from e

    return buffer


@_checkPlan
def getCaseString(plan):
    stringBuffer = StringIO()
    if kz.getSolveParameters() is None:
        return ""
    plan.saveConfig(stringBuffer)

    return stringBuffer


@_checkPlan
def saveCaseFile(plan):
    stringBuffer = getCaseString()
    encoded_data = stringBuffer.getvalue().encode("utf-8")

    return BytesIO(encoded_data)


def createCaseFromFile(strio):
    logstrio = StringIO()
    try:
        plan = owl.readConfig(strio, logstreams=[logstrio], readContributions=False)
    except Exception as e:
        st.error(f"Failed to parse case file: {e}")
        return "", {}

    name, mydic = genDic(plan)
    mydic["logs"] = logstrio

    val = kz.getGlobalKey("plotGlobalBackend")
    if val:
        plan.setPlotBackend(val)

    return name, mydic


def genDic(plan):
    accName = ["txbl", "txDef", "txFree"]
    dic = {}
    dic["plan"] = plan
    dic["name"] = plan._name
    dic["description"] = plan._description
    dic["summaryDf"] = None
    dic["casetoml"] = ""
    dic["caseStatus"] = "new"
    dic["status"] = ["unknown", "single", "married"][plan.N_i]
    # Prepend year if not there.
    tdate = plan.startDate.replace("/", "-").split("-")
    if len(tdate) == 2:
        mystartDate = str(date.today().year) + "-" + plan.startDate
    elif len(tdate) == 3:
        mystartDate = str(date.today().year) + "-" + tdate[-2] + "-" + tdate[-1]
    else:
        raise ValueError(f"Wrong date format: {plan.startDate}")
    try:
        startDate = datetime.strptime(mystartDate, "%Y-%m-%d").date()
    except Exception as e:
        raise ValueError(f"Wrong date format {plan.startDate}: {e}") from e
    dic["startDate"] = startDate
    dic["interpMethod"] = plan.interpMethod
    dic["interpCenter"] = plan.interpCenter
    dic["interpWidth"] = plan.interpWidth
    dic["spendingProfile"] = plan.spendingProfile
    if plan.spendingProfile == "smile":
        dic["smileDip"] = plan.smileDip
        dic["smileIncrease"] = plan.smileIncrease
        dic["smileDelay"] = plan.smileDelay
    else:
        dic["smileDip"] = 15
        dic["smileIncrease"] = 12
        dic["smileDelay"] = 0
    dic["survivor"] = 100 * plan.chi
    dic["gainTx"] = 100 * plan.psi
    dic["divRate"] = 100 * plan.mu
    dic["heirsTx"] = 100 * plan.nu
    dic["yTCJA"] = plan.yTCJA
    dic["surplusFraction"] = plan.eta
    dic["plots"] = plan.defaultPlots
    dic["allocType"] = plan.ARCoord
    dic["timeListsFileName"] = plan.timeListsFileName
    for j1 in range(plan.N_j):
        dic["benf" + str(j1)] = plan.phi_j[j1]

    for i in range(plan.N_i):
        dic["iname" + str(i)] = plan.inames[i]
        dic["yob" + str(i)] = plan.yobs[i]
        dic["life" + str(i)] = plan.expectancy[i]
        dic["ssAge" + str(i)] = plan.ssecAges[i]
        dic["ssAmt" + str(i)] = plan.ssecAmounts[i] / 1000
        dic["pAge" + str(i)] = plan.pensionAges[i]
        dic["pAmt" + str(i)] = plan.pensionAmounts[i] / 1000
        dic["pIdx" + str(i)] = plan.pensionIsIndexed[i]
        for j1 in range(plan.N_j):
            dic[accName[j1] + str(i)] = plan.beta_ij[i, j1] / 1000

        if plan.ARCoord == "individual":
            for k1 in range(plan.N_k):
                dic[f"j3_init%{k1}_{i}"] = int(plan.boundsAR["generic"][i][0][k1])
                dic[f"j3_fin%{k1}_{i}"] = int(plan.boundsAR["generic"][i][1][k1])
        elif plan.ARCoord == "account":
            longAccName = ["taxable", "tax-deferred", "tax-free"]
            for j2 in range(3):
                for k2 in range(plan.N_k):
                    dic[f"j{j2}_init%{k2}_{i}"] = int(plan.boundsAR[longAccName[j2]][i][0][k2])
                    dic[f"j{j2}_fin%{k2}_{i}"] = int(plan.boundsAR[longAccName[j2]][i][1][k2])
        else:
            st.error("Only 'individual' and 'account' asset allocations are currently supported")
            return None

    optionKeys = list(plan.solverOptions)
    for key in ["maxRothConversion", "noRothConversions", "withMedicare", "netSpending", "bequest"]:
        if key in optionKeys:
            dic[key] = plan.solverOptions[key]

    if "previousMAGIs" in optionKeys:
        dic["MAGI0"] = plan.solverOptions["previousMAGIs"][0]
        dic["MAGI1"] = plan.solverOptions["previousMAGIs"][1]

    if plan.objective == "maxSpending":
        dic["objective"] = "Net spending"
    else:
        dic["objective"] = "Bequest"

    if plan.rateMethod in ["default", "conservative", "optimistic", "historical average", "user"]:
        dic["rateType"] = "fixed"
        dic["fixedType"] = plan.rateMethod
    elif plan.rateMethod in ["histochastic", "historical", "stochastic"]:
        dic["rateType"] = "varying"
        dic["varyingType"] = plan.rateMethod

    # Initialize in both cases.
    for k1 in range(plan.N_k):
        dic["fxRate" + str(k1)] = 100 * plan.rateValues[k1]

    if plan.rateMethod in ["historical average", "histochastic", "historical"]:
        dic["yfrm"] = plan.rateFrm
        dic["yto"] = plan.rateTo
    else:
        dic["yfrm"] = FROM
        # Rates availability are trailing by 1 year.
        dic["yto"] = date.today().year - 1

    if plan.rateMethod in ["stochastic", "histochastic"]:
        qq = 1
        for k1 in range(plan.N_k):
            dic["mean" + str(k1)] = 100 * plan.rateValues[k1]
            dic["stdev" + str(k1)] = 100 * plan.rateStdev[k1]
            for k2 in range(k1 + 1, plan.N_k):
                dic["corr" + str(qq)] = plan.rateCorr[k1, k2]
                qq += 1

    return plan._name, dic


@_checkPlan
def backYearsMAGI(plan):
    thisyear = date.today().year
    backyears = [0, 0]
    goatyear = min(plan.yobs)
    if thisyear - goatyear >= 65:
        backyears[0] = thisyear - 2
        backyears[1] = thisyear - 1
    elif thisyear - goatyear >= 64:
        backyears[0] = thisyear - 1

    return backyears


def renderPlot(fig, col=None):
    """
    Render a plot using the appropriate Streamlit function based on the backend type

        Args:
        fig: The figure object from either matplotlib or plotly
        col: Optional Streamlit column to render in
    """
    if fig is None:
        return

    # Check if it's a plotly figure.
    if hasattr(fig, 'to_dict'):  # plotly figures have to_dict method.
        if col:
            col.plotly_chart(fig, use_container_width=True)
        else:
            st.plotly_chart(fig, use_container_width=True)
    else:  # matplotlib figure.
        if col:
            col.pyplot(fig)
        else:
            st.pyplot(fig)

    # Add a space below each figure
    if col:
        # col.write("####")
        col.divider()
    else:
        st.divider()
        # st.write("####")


def version():
    return owl.__version__
