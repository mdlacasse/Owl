"""
Bridge module connecting Streamlit UI to Owl planner core functionality.

This module provides functions to create Plan instances, run optimizations,
and manage the interface between the Streamlit web UI and the core planning engine.

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
from owlplanner.timelists import conditionDebtsAndFixedAssetsDF, getTableTypes  # noqa: E402, F401
from owlplanner.mylogging import Logger  # noqa: E402

import sskeys as kz         # noqa: E402
import progress             # noqa: E402


def hasMOSEK():
    spec = importlib.util.find_spec("mosek")
    return spec is not None


def createPlan():
    name = kz.currentCaseName()
    inames = [kz.getCaseKey("iname0")]
    description = kz.getCaseKey("description")
    dobs = [kz.getCaseKey("dob0")]
    life = [kz.getCaseKey("life0")]
    if kz.getCaseKey("status") == "married":
        inames.append(kz.getCaseKey("iname1"))
        dobs.append(kz.getCaseKey("dob1"))
        life.append(kz.getCaseKey("life1"))

    # Get existing logs StringIO or create a new one
    strio = kz.getCaseKey("logs")
    if strio is None:
        strio = StringIO()
        kz.storeCaseKey("logs", strio)
    try:
        plan = owl.Plan(inames, dobs, life, name,
                        verbose=True, logstreams=[strio, strio])
        kz.setCaseKey("plan", plan)
        kz.setCaseKey("id", plan._id)
    except Exception as e:
        st.error(f"Failed creation of plan '{name}': {e}")
        return

    plan.setDescription(description)

    val = kz.getGlobalKey("plotGlobalBackend")
    if val:
        plan.setPlotBackend(val)

    # Set default plot value from case settings.
    plot_val = kz.getCaseKey("plots")
    if plot_val:
        plan.setDefaultPlots(plot_val)

    # Force to pull key and set profile if key was defined.
    if kz.getCaseKey("spendingProfile"):
        setProfile(None)

    if kz.getCaseKey("copy"):
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
        plan = kz.getCaseKey("plan")
        if plan is None:
            st.error(f"Plan not yet created. Preventing to execute method {func.__name__}().")
            return None
        return func(plan, *args, **kwargs)

    return wrapper


def prepareRun(plan):
    ni = 2 if kz.getCaseKey("status") == "married" else 1

    startDate = kz.getCaseKey("startDate")
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
        benfrac = [kz.getCaseKey("benf0"), kz.getCaseKey("benf1"), kz.getCaseKey("benf2")]
        try:
            plan.setBeneficiaryFractions(benfrac)
        except Exception as e:
            st.error(f"Failed setting beneficiary fractions: {e}")
            return

        surplusFrac = kz.getCaseKey("surplusFraction")
        try:
            plan.setSpousalDepositFraction(surplusFrac)
        except Exception as e:
            st.error(f"Failed setting beneficiary fractions: {e}")
            return

    plan.setDescription(kz.getCaseKey("description"))
    plan.setHeirsTaxRate(kz.getCaseKey("heirsTx"))
    plan.setDividendRate(kz.getCaseKey("divRate"))
    plan.setExpirationYearOBBBA(kz.getCaseKey("yOBBBA"))

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
        kz.storeCaseKey("caseStatus", "exception")
        kz.storeCaseKey("summaryDf", None)
        return

    kz.storeCaseKey("caseStatus", plan.caseStatus)
    if plan.caseStatus == "solved":
        kz.storeCaseKey("summaryDf", plan.summaryDf())
        kz.storeCaseKey("casetoml", getCaseString().getvalue())
    else:
        kz.storeCaseKey("summaryDf", None)
        kz.storeCaseKey("casetoml", "")


@_checkPlan
def runHistorical(plan):
    plan1 = owl.clone(plan)
    prepareRun(plan1)

    hyfrm = kz.getCaseKey("hyfrm")
    hyto = kz.getCaseKey("hyto")
    augmented = kz.getCaseKey("augmented_sampling")
    augmented = False if augmented is None else bool(augmented)
    log_x = kz.getCaseKey("histogram_log_x_historical")
    log_x = False if log_x is None else bool(log_x)

    objective, options = kz.getSolveParameters()
    try:
        mybar = progress.Progress(None)
        fig, summary = plan1.runHistoricalRange(
            objective, options, hyfrm, hyto, figure=True, progcall=mybar,
            augmented=augmented, log_x=log_x)
        kz.storeCaseKey("histoPlot", fig)
        kz.storeCaseKey("histoSummary", summary)
    except Exception as e:
        kz.storeCaseKey("histoPlot", None)
        kz.storeCaseKey("histoSummary", None)
        st.error(f"Historical solution failed: {e}")
        return


@_checkPlan
def runMC(plan):
    plan1 = owl.clone(plan)
    prepareRun(plan1)

    N = kz.getCaseKey("MC_cases")
    log_x = kz.getCaseKey("histogram_log_x_mc")
    log_x = False if log_x is None else bool(log_x)

    objective, options = kz.getSolveParameters()
    try:
        mybar = progress.Progress(None)
        fig, summary = plan1.runMC(objective, options, N, figure=True, progcall=mybar, log_x=log_x)
        kz.storeCaseKey("monteCarloPlot", fig)
        kz.storeCaseKey("monteCarloSummary", summary)
    except Exception as e:
        kz.storeCaseKey("monteCarloPlot", None)
        kz.storeCaseKey("monteCarloSummary", None)
        st.error(f"Monte Carlo solution failed: {e}")


@_checkPlan
def setRates(plan):
    return _setRates(plan)


def _setRates(plan):
    rateType = kz.getCaseKey("rateType")
    yfrm = kz.getCaseKey("yfrm")
    yto = kz.getCaseKey("yto")
    adjusted_range = False

    if yfrm is not None and yto is not None and yfrm >= yto:
        if yfrm < TO:
            yto = yfrm + 1
        else:
            yto = TO
            yfrm = TO - 1
        kz.pushCaseKey("yfrm", yfrm)
        kz.pushCaseKey("yto", yto)
        adjusted_range = True

    if rateType is None:
        st.info("Rate type not selected yet.")
        return False

    if rateType == "fixed":
        if kz.getCaseKey("fixedType") == "historical average":
            if adjusted_range:
                st.warning("Ending year adjusted to be after starting year.")
            plan.setRates("historical average", yfrm, yto)
            # Set fxRates back to computed values.
            for j in range(4):
                kz.pushCaseKey(f"fxRate{j}", 100 * plan.tau_kn[j, -1])
        else:
            plan.setRates(
                "user",
                values=[
                    float(kz.getCaseKey("fxRate0")),
                    float(kz.getCaseKey("fxRate1")),
                    float(kz.getCaseKey("fxRate2")),
                    float(kz.getCaseKey("fxRate3")),
                ],
            )
    else:
        varyingType = kz.getCaseKey("varyingType")
        if varyingType is None:
            st.info("Varying rate type not selected yet.")
            return False

        if varyingType.startswith("histo"):
            if varyingType == "historical":
                yfrm2 = min(yfrm, TO - plan.N_n + 1)
                kz.pushCaseKey("yfrm", yfrm2)
                if yfrm != yfrm2:
                    yfrm = yfrm2
                    st.warning(f"Using {yfrm} as starting year.")
                yto = min(TO, yfrm + plan.N_n - 1)
                kz.pushCaseKey("yto", yto)
            elif adjusted_range:
                st.warning("Ending year adjusted to be after starting year.")

            # Set reproducibility for histochastic methods
            if varyingType == "histochastic":
                reproducible = kz.getCaseKey("reproducibleRates")
                seed = kz.getCaseKey("rateSeed") if reproducible else None
                plan.setReproducible(reproducible, seed=seed)

            reverse_seq = kz.getCaseKey("reverse_sequence")
            roll_seq = kz.getCaseKey("roll_sequence")
            reverse_seq = False if reverse_seq is None else bool(reverse_seq)
            roll_seq = 0 if roll_seq is None else int(roll_seq)
            plan.setRates(varyingType, yfrm, yto, reverse=reverse_seq, roll=roll_seq)

            # Store seed, reproducibility, and sequence options back to case keys
            if varyingType == "histochastic":
                kz.setCaseKey("rateSeed", plan.rateSeed)
                kz.setCaseKey("reproducibleRates", plan.reproducibleRates)
            kz.setCaseKey("reverse_sequence", plan.rateReverse)
            kz.setCaseKey("roll_sequence", plan.rateRoll)
            mean, stdev, corr, covar = owl.getRatesDistributions(yfrm, yto, plan.mylog)
            for j in range(4):
                kz.pushCaseKey(f"mean{j}", 100 * mean[j])
                kz.pushCaseKey(f"stdev{j}", 100 * stdev[j])
            q = 1
            for k1 in range(plan.N_k):
                for k2 in range(k1 + 1, plan.N_k):
                    kz.pushCaseKey(f"corr{q}", corr[k1, k2])
                    q += 1

        elif varyingType == "stochastic":
            means = []
            stdev = []
            corr = []
            for kk in range(plan.N_k):
                means.append(kz.getCaseKey(f"mean{kk}"))
                stdev.append(kz.getCaseKey(f"stdev{kk}"))
            for q in range(1, 7):
                corr.append(kz.getCaseKey(f"corr{q}"))
            # Set reproducibility for stochastic methods
            reproducible = kz.getCaseKey("reproducibleRates")
            seed = kz.getCaseKey("rateSeed") if reproducible else None
            plan.setReproducible(reproducible, seed=seed)

            reverse_seq = kz.getCaseKey("reverse_sequence")
            roll_seq = kz.getCaseKey("roll_sequence")
            reverse_seq = False if reverse_seq is None else bool(reverse_seq)
            roll_seq = 0 if roll_seq is None else int(roll_seq)
            plan.setRates(varyingType, values=means, stdev=stdev, corr=corr,
                          reverse=reverse_seq, roll=roll_seq)

            # Store seed, reproducibility, and sequence options back to case keys
            kz.setCaseKey("rateSeed", plan.rateSeed)
            kz.setCaseKey("reproducibleRates", plan.reproducibleRates)
            kz.setCaseKey("reverse_sequence", plan.rateReverse)
            kz.setCaseKey("roll_sequence", plan.rateRoll)
        else:
            raise RuntimeError("Logic error in setRates()")

    return True


@_checkPlan
def showAllocations(plan):
    figures = plan.showAllocations(figure=True)
    st.divider()
    st.markdown("#### :orange[Asset Allocation]")
    # n = 3 if kz.getCaseKey("allocType") == "account" else 2
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
        col.markdown("#### :orange[Spending Profile]")
        renderPlot(fig, col)


@_checkPlan
def showRates(plan, col):
    fig = plan.showRates(figure=True)
    if fig:
        col.markdown("#### :orange[Selected Rates Over Time Horizon]")
        renderPlot(fig, col)


@_checkPlan
def showRatesCorrelations(plan, col):
    fig = plan.showRatesCorrelations(figure=True)
    if fig:
        col.markdown("#### :orange[Correlations Between Return Rates]")
        renderPlot(fig, col)


@_checkPlan
def showSources(plan):
    fig = plan.showSources(figure=True)
    if fig:
        renderPlot(fig)


@_checkPlan
def setInterpolationMethod(plan):
    _setInterpolationMethod(plan)


def _setInterpolationMethod(plan):
    plan.setInterpolationMethod(kz.getCaseKey("interpMethod"), kz.getCaseKey("interpCenter"),
                                kz.getCaseKey("interpWidth"))


@_checkPlan
def setContributions(plan, reset=True):
    _setContributions(plan, "reset")


def _setContributions(plan, action):
    """
    Set from UI -> Plan.
    """
    if kz.getCaseKey("timeList0") is None:
        return

    # Save current state to detect changes
    original_timeLists = {}
    for i, iname in enumerate(plan.inames):
        if iname in plan.timeLists:
            original_timeLists[iname] = plan.timeLists[iname].copy()

    # Ensure original_houseLists always has both keys
    original_houseLists = {}
    for key in ["Debts", "Fixed Assets"]:
        if key in plan.houseLists:
            original_houseLists[key] = plan.houseLists[key].copy()
        else:
            # Initialize with empty DataFrame if key doesn't exist
            original_houseLists[key] = conditionDebtsAndFixedAssetsDF(None, key)

    original_filename = kz.getCaseKey("timeListsFileName")

    dicDf = {kz.getCaseKey("iname0"): kz.getCaseKey("timeList0")}
    if kz.getCaseKey("status") == "married":
        dicDf[kz.getCaseKey("iname1")] = kz.getCaseKey("timeList1")

    try:
        plan.readContributions(dicDf)
    except Exception as e:
        st.error(f"Failed to parse Household Financial Profile Workbook: {e}")
        return False

    # Sync houseLists from UI to Plan
    syncHouseLists(plan)

    # Check if data actually changed
    data_changed = False

    # Compare timeLists
    for iname in plan.inames:
        if not plan.timeLists[iname].equals(original_timeLists[iname]):
            data_changed = True
            break

    # Compare houseLists if timeLists haven't changed.
    # Both plan.houseLists and original_houseLists are guaranteed to have both keys.
    if not data_changed:
        for key in ["Debts", "Fixed Assets"]:
            if len(plan.houseLists[key]) == 0 and len(original_houseLists[key]) == 0:
                continue
            elif not plan.houseLists[key].equals(original_houseLists[key]):
                data_changed = True
                break

    if action == "copy":
        # Possible reconditionned data due to delta in year span.
        kz.setCaseKey("timeList0", plan.timeLists[kz.getCaseKey("iname0")])
        if kz.getCaseKey("status") == "married":
            kz.setCaseKey("timeList1", plan.timeLists[kz.getCaseKey("iname1")])
    elif action == "reset":
        kz.setCaseKey("timeListsFileName", "edited values")
        plan.timeListsFileName = "edited values"
    elif action == "set":
        # Only set to "edited values" if data actually changed.
        if data_changed:
            kz.storeCaseKey("timeListsFileName", "edited values")
            plan.timeListsFileName = "edited values"
        else:
            # Preserve original filename if nothing changed.
            if original_filename and original_filename != "edited values" and original_filename != "None":
                kz.storeCaseKey("timeListsFileName", original_filename)
                plan.timeListsFileName = original_filename


@_checkPlan
def readContributions(plan, stFile, file=None):
    """
    Set from file -> Plan -> UI.
    """
    if stFile is None:
        return False

    if file:
        name = file
    elif hasattr(stFile, "name"):
        name = stFile.name
    else:
        name = "unknown"

    try:
        plan.readContributions(stFile, filename_for_logging=name)
    except Exception as e:
        st.error(f"Failed to parse Household Financial Profile Workbook '{name}': {e}")
        return False

    # Set the filename in both case dictionary and plan object
    # This ensures the value is reset even if it was previously "edited values"
    kz.setCaseKey("stTimeLists", name)
    kz.setCaseKey("timeListsFileName", name)
    plan.timeListsFileName = name

    kz.setCaseKey("timeList0", plan.timeLists[kz.getCaseKey("iname0")])
    kz.setCaseKey("_timeList0", plan.timeLists[kz.getCaseKey("iname0")])
    if kz.getCaseKey("status") == "married":
        kz.setCaseKey("timeList1", plan.timeLists[kz.getCaseKey("iname1")])
        kz.setCaseKey("_timeList1", plan.timeLists[kz.getCaseKey("iname1")])

    # Store houseLists (Debts and Fixed Assets). These are guaranteed to be present in the plan object.
    kz.setCaseKey("houseListDebts", plan.houseLists["Debts"])
    kz.setCaseKey("houseListFixedAssets", plan.houseLists["Fixed Assets"])

    return True


@_checkPlan
def resetContributions(plan):
    return plan.zeroContributions()


def resetTimeLists():
    tlists = resetContributions()
    for i, iname in enumerate(tlists):
        kz.setCaseKey(f"timeList{i}", tlists[iname])

    # Reset houseLists to empty DataFrames
    # kz.setCaseKey("houseListDebts",
    #               pd.DataFrame(columns=["name", "type", "year", "term", "amount", "rate"]))
    # kz.setCaseKey("houseListFixedAssets",
    #               pd.DataFrame(columns=["name", "type", "basis", "value", "rate", "yod", "commission"]))


def syncHouseLists(plan):
    """
    Sync houseLists from UI case keys to Plan object.
    Note: This function does NOT use @_checkPlan decorator because it's called
    from _setContributions which already has the plan object. The decorator would
    cause a conflict by trying to inject the plan from case keys.
    """
    if plan is None:
        return False

    plan.houseLists = {}
    logger = plan.logger()
    debts = kz.getCaseKey("houseListDebts")
    fixedAssets = kz.getCaseKey("houseListFixedAssets")

    plan.houseLists["Debts"] = conditionDebtsAndFixedAssetsDF(debts, "Debts", mylog=logger)
    plan.houseLists["Fixed Assets"] = conditionDebtsAndFixedAssetsDF(
        fixedAssets, "Fixed Assets", mylog=logger
    )

    return True


@_checkPlan
def setAllocationRatios(plan):
    _setAllocationRatios(plan)


def _setAllocationRatios(plan):
    if kz.getCaseKey("allocType") == "individual":
        try:
            generic = kz.getIndividualAllocationRatios()
            plan.setAllocationRatios("individual", generic=generic)
        except Exception as e:
            st.error(f"Setting asset allocation failed: {e}")
            return
    elif kz.getCaseKey("allocType") == "account":
        try:
            acc = kz.getAccountAllocationRatios()
            plan.setAllocationRatios("account", taxable=acc[0], taxDeferred=acc[1], taxFree=acc[2])
        except Exception as e:
            st.error(f"Setting asset allocation failed: {e}")
            return
    else:
        st.error(f"Internal error: Unknown account type {kz.getCaseKey('allocType')}.")


@_checkPlan
def plotSingleResults(plan):
    c = 0
    n = 2
    cols = st.columns(n, gap="medium")
    fig = plan.showRates(figure=True)
    if fig:
        cols[c].markdown("#### :orange[Annual Rates]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showNetSpending(figure=True)
    if fig:
        cols[c].markdown("#### :orange[Net Available Spending]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showGrossIncome(figure=True)
    if fig:
        cols[c].markdown("#### :orange[Taxable Ordinary Income]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    # st.divider()
    # cols = st.columns(n, gap="medium")
    fig = plan.showSources(figure=True)
    if fig:
        cols[c].markdown("#### :orange[Raw Income Sources]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showAccounts(figure=True)
    if fig:
        cols[c].markdown("#### :orange[Savings Balance]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showTaxes(figure=True)
    if fig:
        cols[c].markdown("#### :orange[Federal Taxes and Medicare (+IRMAA)]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    c = 0
    figs = plan.showAssetComposition(figure=True)
    if figs:
        # st.divider()
        st.markdown("#### :orange[Asset Composition]")
        col1, col2, _ = st.columns([0.6, 0.2, 0.2], gap="medium")
        for fig in figs:
            if fig:
                renderPlot(fig, col1)
            else:
                col1.markdown("#\n<div style='text-align: center'> This plot is empty </div>",
                              unsafe_allow_html=True)
            # c = (c + 1) % n


@_checkPlan
def setProfile(plan, key):
    if key is not None:
        kz.setpull(key)
    else:
        kz.flagModified()
    profile = kz.getCaseKey("spendingProfile")
    survivor = kz.getCaseKey("survivor")
    dip = kz.getCaseKey("smileDip")
    increase = kz.getCaseKey("smileIncrease")
    delay = kz.getCaseKey("smileDelay")
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


def highlight_year_row(row):
    """Highlight the row where year equals the current year.

    Uses a semi-transparent tint that works in both light and dark theme.
    """
    this_year = date.today().year
    if "year" in row.index:
        try:
            if int(row["year"]) == this_year:
                return ["background-color: rgba(33, 150, 243, 0.25)"] * len(row)
        except (TypeError, ValueError):
            pass
    return [""] * len(row)


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

        st.markdown(f"#### :orange[{name}]")
        if "Accounts" in name:
            display_df = df.style.apply(highlight_year_row, axis=1)
            st.dataframe(display_df, width="stretch", column_config=colfor, hide_index=True)
        else:
            st.dataframe(df.astype(str), width="stretch", column_config=colfor, hide_index=True)

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

    # Update filename if it's currently "edited values" - this indicates the file
    # was edited and is now being saved, so we should update the reference
    current_filename = kz.getCaseKey("timeListsFileName")
    if current_filename == "edited values":
        # Use the suggested download filename format
        case_name = kz.getCaseKey("name")
        if case_name:
            suggested_filename = f"HFP_{case_name}.xlsx"
            kz.storeCaseKey("timeListsFileName", suggested_filename)
            plan.timeListsFileName = suggested_filename

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
    """
    From Plan to to UI.
    """

    accName = ["txbl", "txDef", "txFree"]
    dic = {}
    dic["plan"] = plan
    dic["name"] = plan._name
    dic["id"] = plan._id
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
    dic["divRate"] = 100 * plan.mu
    dic["heirsTx"] = 100 * plan.nu
    dic["yOBBBA"] = plan.yOBBBA
    dic["surplusFraction"] = plan.eta
    dic["plots"] = plan.defaultPlots
    dic["allocType"] = plan.ARCoord
    dic["timeListsFileName"] = plan.timeListsFileName
    for j1 in range(plan.N_j):
        dic[f"benf{j1}"] = plan.phi_j[j1]

    for i in range(plan.N_i):
        dic[f"iname{i}"] = plan.inames[i]
        dic[f"dob{i}"] = plan.dobs[i]
        dic[f"life{i}"] = plan.expectancy[i]
        dic[f"ssAge_y{i}"] = int(plan.ssecAges[i])
        dic[f"ssAge_m{i}"] = round((plan.ssecAges[i] % 1.) * 12)
        dic[f"ssAmt{i}"] = plan.ssecAmounts[i]
        dic[f"pAge_y{i}"] = int(plan.pensionAges[i])
        dic[f"pAge_m{i}"] = round((plan.pensionAges[i] % 1.) * 12)
        dic[f"pAmt{i}"] = plan.pensionAmounts[i]
        dic[f"pIdx{i}"] = plan.pensionIsIndexed[i]
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

    solverOptionKeys = list(plan.solverOptions)
    # Should we ignore expert options that will reset to default?
    optList = ["netSpending", "maxIter", "maxRothConversion", "maxTime", "noRothConversions",
               "startRothConversions", "withMedicare", "bequest", "solver", "noLateSurplus",
               "spendingSlack", "oppCostX", "amoConstraints", "amoRoth", "amoSurplus", "withSCLoop",
               "absTol", "bigMirmaa", "bigMamo", "relTol",]
    for key in optList:
        if key in solverOptionKeys:
            dic[key] = plan.solverOptions[key]

    if "withMedicare" in solverOptionKeys:
        opt = plan.solverOptions["withMedicare"]
        dic["computeMedicare"] = False if opt == "None" else True
        dic["optimizeMedicare"] = True if opt == "optimize" else False

    if "previousMAGIs" in solverOptionKeys:
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
        dic[f"fxRate{k1}"] = 100 * plan.rateValues[k1]

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
            dic[f"mean{k1}"] = 100 * plan.rateValues[k1]
            dic[f"stdev{k1}"] = 100 * plan.rateStdev[k1]
            for k2 in range(k1 + 1, plan.N_k):
                dic[f"corr{qq}"] = plan.rateCorr[k1, k2]
                qq += 1
        # Include reproducibility settings
        dic["reproducibleRates"] = plan.reproducibleRates
        if plan.rateSeed is not None:
            dic["rateSeed"] = plan.rateSeed

    # Reverse and roll sequence (varying rates only; stored for all for consistency)
    dic["reverse_sequence"] = getattr(plan, "rateReverse", False)
    dic["roll_sequence"] = getattr(plan, "rateRoll", 0)

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
        backyears[1] = thisyear - 1

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
        config = {"width": "stretch"}
        if col:
            col.plotly_chart(fig, config=config)
        else:
            st.plotly_chart(fig, config=config)
    else:  # matplotlib figure.
        if col:
            col.pyplot(fig)
        else:
            st.pyplot(fig)

    # Add a space below each figure
    if col:
        # col.markdown("####")
        col.divider()
    else:
        st.divider()
        # st.markdown("####")


def version():
    return owl.__version__


@_checkPlan
def getFixedAssetsBequestValue(plan, in_todays_dollars=False):
    """
    Calculate and return the fixed assets bequest value (assets with yod past plan end).
    This value represents assets that will be liquidated at the end of the plan.
    The plan is automatically retrieved via the @_checkPlan decorator.

    Parameters:
    -----------
    in_todays_dollars : bool, optional
        If True, returns value in today's dollars (requires rates to be set).
        If False, returns value in nominal dollars (default).

    Returns:
    --------
    float
        Total proceeds (after commission) from fixed assets with yod past plan end.
        Returns 0.0 if no plan exists or no such assets.
        If in_todays_dollars=True and rates not set, returns 0.0.
    """
    # Ensure houseLists are synced
    syncHouseLists(plan)

    if "Fixed Assets" in plan.houseLists and not plan.houseLists["Fixed Assets"].empty:
        # First ensure the bequest value is calculated
        plan.processDebtsAndFixedAssets()

        if in_todays_dollars:
            # Ensure rates are set (needed for conversion to today's dollars)
            if plan.rateMethod is None or not hasattr(plan, 'tau_kn'):
                _setRates(plan)

            # Convert to today's dollars using plan method
            return plan.getFixedAssetsBequestValueInTodaysDollars()
        else:
            # Return nominal value
            return plan.fixed_assets_bequest_value
    else:
        return 0.0


# -------------------------------
# UI-level logging helper
# -------------------------------

def _get_case_logger():
    """
    Get or create a Logger instance for the current case.
    Returns None if no valid case exists.

    If a plan exists, uses the plan's logger (which writes to the case's logs StringIO).
    Otherwise, creates/uses a UI logger that writes to the case's logs StringIO.
    This ensures both plan and UI logging use the same StringIO per case.
    """
    # Check if we have a valid case (not the special "New Case..." or "Upload Case File..." cases)
    case_name = kz.currentCaseName()
    if case_name in [kz.newCase, kz.loadCaseFile]:
        return None

    # If a plan exists, use its logger (which already writes to the case's logs StringIO)
    plan = kz.getCaseKey("plan")
    if plan is not None:
        return plan.logger()

    # No plan exists yet - get or create the current case's log stream
    log_stream = kz.getCaseKey("logs")
    if log_stream is None:
        # Create a new StringIO for this case if it doesn't exist
        log_stream = StringIO()
        kz.storeCaseKey("logs", log_stream)

    # Get or create a Logger instance for this case (only used before plan is created)
    # Use a fixed key so it persists through case renames
    logger = kz.getCaseKey("_ui_logger")
    if logger is None:
        logger = Logger(verbose=True, logstreams=[log_stream, log_stream])
        kz.storeCaseKey("_ui_logger", logger)

    return logger


def ui_log(message, level="info"):
    """
    Log a message to the current case's log stream using the Logger class.
    This provides session-safe logging without using the global loguru singleton.
    Creates a log stream and logger for the current case if they don't exist.
    If no valid case exists, the log is silently ignored.

    Args:
        message: The log message to write
        level: Log level (info, debug) - uses print() for info, vprint() for debug
    """
    logger = _get_case_logger()
    if logger is None:
        return

    # Use the Logger's methods which already handle timestamp formatting
    if level.lower() == "debug":
        logger.vprint(message)
    else:
        logger.print(message)
