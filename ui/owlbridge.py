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
# flake8: noqa: E402

import streamlit as st
import pandas as pd
from io import StringIO, BytesIO
from functools import wraps
from datetime import datetime, date
import sys

sys.path.insert(0, "./src")
sys.path.insert(0, "../src")

import owlplanner as owl
from owlplanner.utils import drop_all_zero_numeric_columns, worksheet_age_on_dec_31_or_blank, get_monetary_option
from owlplanner.rates import FROM, TO, get_fixed_rate_values
from owlplanner.timelists import conditionDebtsAndFixedAssetsDF, getTableTypes
from owlplanner.mylogging import Logger
from owlplanner.rate_models.constants import (
    FIXED_TYPE_UI,
    HISTORICAL_RANGE_METHODS,
    STOCHASTIC_METHODS,
    VARYING_TYPE_UI,
)
from moseklicense import hasMOSEK

import sskeys as kz
import progress


def getFixedRates(method):
    """
    Return canonical fixed rate values (percent) for conservative, optimistic, trailing-30.

    Single source of truth: values come from owlplanner.rates to stay in sync
    with the backend. Use this instead of duplicating FXRATES in the UI.
    """
    return get_fixed_rate_values(method)


def getMethodDescription(method):
    from owlplanner.rate_models.loader import get_rate_model_metadata
    return get_rate_model_metadata(method).get("description", "")


def createPlan():
    if not kz.has_current_case():
        st.error("No case selected or current case no longer exists. Please select or create a case.")
        return
    name = kz.currentCaseName()
    inames = [kz.getCaseKey("iname0")]
    description = kz.getCaseKey("description")
    dobs = [kz.getCaseKey("dob0")]
    life = [kz.getCaseKey("life0")]
    sexes = [kz.getCaseKey("sex0") or "M"]
    if kz.getCaseKey("status") == "married":
        inames.append(kz.getCaseKey("iname1"))
        dobs.append(kz.getCaseKey("dob1"))
        life.append(kz.getCaseKey("life1"))
        sexes.append(kz.getCaseKey("sex1") or "F")

    # Get existing logs StringIO or create a new one
    strio = kz.getCaseKey("logs")
    if strio is None:
        strio = StringIO()
        kz.storeCaseKey("logs", strio)
    try:
        plan = owl.Plan(inames, dobs, life, name,
                        verbose=True, logstreams=[strio, strio])
        plan.setSexes(sexes)
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

    plan.setWorksheetShowAges(bool(kz.getCaseKey("worksheetShowAges")))
    plan.setWorksheetHideZeroColumns(bool(kz.getCaseKey("worksheetHideZeroColumns")))
    plan.setWorksheetRealDollars(bool(kz.getCaseKey("worksheetRealDollars")))

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
            st.error(f"Plan not yet created. Cannot execute method {func.__name__}().")
            return None
        return func(plan, *args, **kwargs)

    return wrapper


def prepareRun(plan):
    from owlplanner.config import apply_config_to_plan, ui_to_config

    try:
        uidic = kz.currentCaseDic()
        diconf = ui_to_config(uidic)
        apply_config_to_plan(plan, diconf)
    except Exception as e:
        st.error(f"Failed to apply configuration: {e}")
        return

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
        # Write optimal SS claiming ages back to UI for individuals the optimizer chose.
        if hasattr(plan, "ssecAges") and hasattr(plan, "_ssa_optimize_set"):
            for i in plan._ssa_optimize_set:
                if i < plan.N_i:
                    kz.storeCaseKey(f"ssAge_y{i}", int(plan.ssecAges[i]))
                    kz.storeCaseKey(f"ssAge_m{i}", round((plan.ssecAges[i] % 1.0) * 12))
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
    reverse = kz.getCaseKey("reverse_sequence")
    reverse = False if reverse is None else bool(reverse)
    roll = kz.getCaseKey("roll_sequence")
    roll = 0 if roll is None else int(roll)
    log_x = kz.getCaseKey("histogram_log_x_historical")
    log_x = False if log_x is None else bool(log_x)

    objective, options = kz.getSolveParameters()
    try:
        mybar = progress.Progress()
        fig, summary, fig2 = plan1.runHistoricalRange(
            objective, options, hyfrm, hyto, figure=True, progcall=mybar,
            reverse=reverse, roll=roll, augmented=augmented, log_x=log_x)
        kz.storeCaseKey("histoPlot", fig)
        kz.storeCaseKey("histoSummary", summary)
        kz.storeCaseKey("histoBarPlot", fig2)
    except Exception as e:
        kz.storeCaseKey("histoPlot", None)
        kz.storeCaseKey("histoSummary", None)
        kz.storeCaseKey("histoBarPlot", None)
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
        mybar = progress.Progress()
        fig, summary = plan1.runMC(objective, options, N, figure=True, progcall=mybar, log_x=log_x)
        kz.storeCaseKey("monteCarloPlot", fig)
        kz.storeCaseKey("monteCarloSummary", summary)
    except Exception as e:
        kz.storeCaseKey("monteCarloPlot", None)
        kz.storeCaseKey("monteCarloSummary", None)
        st.error(f"Monte Carlo solution failed: {e}")


def _apply_stochastic_target(result, target_sr, plotter, plan=None):
    """Recompute g_opt and regenerate plots from cached scenario data and a new target rate."""
    import numpy as np
    g_opt, lam = owl.g_for_success_rate(
        target_sr, result["lambdas"], result["frontier_g"], result["frontier_prob"])
    lam_idx = int(np.argmin(np.abs(result["lambdas"] - lam)))
    actual_sr = 1.0 - float(result["frontier_prob"][lam_idx])

    kz.storeCaseKey("stochResult", {
        "g_opt": g_opt,
        "lam": lam,
        "target_success_rate": target_sr,
        "actual_success_rate": actual_sr,
    })
    with_longevity = result.get("with_longevity", False)
    fig_frontier = plotter.plot_stochastic_frontier(
        result["frontier_prob"], result["frontier_g"], result["frontier_shortfall"],
        target_sr, g_opt, result["year_n"], result["start_years"],
        with_longevity=with_longevity)
    fig_outcomes = plotter.plot_stochastic_outcomes(
        result["start_years"], result["bases"], g_opt,
        target_sr, result["year_n"],
        with_longevity=with_longevity)
    kz.storeCaseKey("stochFrontierPlot", fig_frontier)
    kz.storeCaseKey("stochOutcomePlot", fig_outcomes)
    bases = result["bases"]
    is_historical = result["start_years"] is not None
    median_spending = float(np.median(bases))
    exp_shortfall = float(np.mean(np.maximum(0.0, g_opt - bases)))
    exp_shortfall_pct = exp_shortfall / g_opt if g_opt > 0 else 0.0
    cvar = exp_shortfall / (1 - actual_sr) if actual_sr < 1.0 else 0.0
    cvar_pct = cvar / g_opt if g_opt > 0 else 0.0
    if is_historical:
        tail_spending = float(np.min(bases))
        tail_shortfall_pct = max(0.0, g_opt - tail_spending) / g_opt if g_opt > 0 else 0.0
        # tail_label = "Worst-case scenario spending:  "
        tail_label = "Historical spending floor   :  "
    else:
        tail_spending = float(np.percentile(bases, 5))
        tail_shortfall_pct = max(0.0, g_opt - tail_spending) / g_opt if g_opt > 0 else 0.0
        # tail_label = "5th percentile spending:       "
        tail_label = "Synthetic spending floor:      "

    if with_longevity:
        mt = result.get("mortality_table", "SSA2025")
        longevity_line = f"Longevity risk:                  {mt}\n"
    else:
        longevity_line = ""

    n_infeasible = result.get("n_infeasible", 0)
    n_total = len(bases)

    if n_infeasible:
        scenarios_line = f"Scenarios:                       {n_total}  ({n_infeasible} infeasible)\n"
    else:
        scenarios_line = f"Scenarios:                       {n_total}\n"

    rate_method = result.get("rate_method", "")
    rate_line = f"Rate method:                     {rate_method}\n" if (rate_method and rate_method != "historical") else ""
    ratio_line = ""
    if plan is not None:
        after_tax = plan._after_tax_savings()
        if after_tax > 0 and g_opt > 0:
            etr_pct = int(round(plan.effectiveTaxRate * 100))
            spending_ratio = g_opt / after_tax
            ratio_line = f"Spending-to-savings ratio:       {spending_ratio:.2%}  (ETR ratio {etr_pct}%)\n"

            _, solve_options = kz.getSolveParameters()
            if "bequest" in solve_options:
                configured_bequest = get_monetary_option(solve_options, "bequest", 0)
                if configured_bequest > 0:
                    bequest_k = configured_bequest / 1000
                    ratio_line += f"Spending-to-savings note:        understated due to bequest of ${bequest_k:,.0f}k\n"

    kz.storeCaseKey("stochSummary", (
        f"Committed spending (today's $):  ${g_opt:,.0f}/yr\n"
        f"{ratio_line}"
        f"Target success rate:             {target_sr:.0%}  (actual: {actual_sr:.0%})\n"
        f"Median scenario spending:        ${median_spending:,.0f}/yr\n"
        f"{tail_label}  ${tail_spending:,.0f}/yr  ({tail_shortfall_pct:.1%} shortfall)\n"
        f"Mean shortfall:                  ${exp_shortfall:,.0f}/yr  ({exp_shortfall_pct:.1%} of committed)\n"
        f"CVaR (avg loss | failure):       ${cvar:,.0f}/yr  ({cvar_pct:.1%} of committed)\n"
        f"{rate_line}"
        f"{longevity_line}"
        f"{scenarios_line}"
    ).rstrip())


@_checkPlan
def runStochasticSpending(plan):
    plan1 = owl.clone(plan)
    prepareRun(plan1)

    scenario_method = kz.getCaseKey("stoch_scenario_method") or "historical"
    target_sr = kz.getCaseKey("stoch_target_success_rate")
    target_sr = 0.85 if target_sr is None else float(target_sr)

    objective, options = kz.getSolveParameters()
    with_longevity = bool(kz.getCaseKey("stoch_with_longevity") or False)
    if with_longevity and scenario_method == "historical":
        with_longevity = False
        ui_log("Longevity risk is not supported with historical scenarios — ignoring.")
    longevity_reproducible = bool(kz.getCaseKey("stoch_longevity_reproducible") or False)
    longevity_seed = kz.getCaseKey("stoch_longevity_seed") if (with_longevity and longevity_reproducible) else None
    sexes = plan1.sexes if with_longevity else None
    mortality_table = kz.getCaseKey("stoch_mortality_table") or "SSA2025"
    if with_longevity:
        plan1.setMortalityTable(mortality_table)
    try:
        mybar = progress.Progress()
        if scenario_method == "historical":
            ystart = kz.getCaseKey("stoch_ystart") or FROM
            yend = kz.getCaseKey("stoch_yend") or TO
            reverse = bool(kz.getCaseKey("stoch_reverse_sequence") or False)
            roll = int(kz.getCaseKey("stoch_roll_sequence") or 0)
            result = plan1.runStochasticSpending(
                options, "historical",
                ystart=ystart, yend=yend, progcall=mybar,
                reverse=reverse, roll=roll,
                with_longevity=with_longevity, sexes=sexes, seed=longevity_seed)
        else:
            N = kz.getCaseKey("stoch_N_mc") or 200
            result = plan1.runStochasticSpending(
                options, "mc",
                N=N, progcall=mybar,
                with_longevity=with_longevity, sexes=sexes, seed=longevity_seed)

        result["with_longevity"] = with_longevity
        result["mortality_table"] = mortality_table
        result["rate_method"] = "historical" if scenario_method == "historical" else (kz.getCaseKey("varyingType") or "stochastic")
        kz.storeCaseKey("stochScenarioData", result)
        _apply_stochastic_target(result, target_sr, plan1._plotter, plan)
    except Exception as e:
        kz.storeCaseKey("stochFrontierPlot", None)
        kz.storeCaseKey("stochOutcomePlot", None)
        kz.storeCaseKey("stochSummary", None)
        kz.storeCaseKey("stochResult", None)
        kz.storeCaseKey("stochScenarioData", None)
        st.error(f"Stochastic spending optimization failed: {e}")


@_checkPlan
def updateStochasticTarget(plan):
    """Reapply a new target success rate to cached scenario data — no scenarios re-run."""
    result = kz.getCaseKey("stochScenarioData")
    if result is None:
        return  # no data yet; slider fired before first run, silently ignore
    # Read from the widget key directly — on_change fires before storeCaseKey runs.
    widget_key = kz.genCaseKey("stoch_target_sr_slider")
    raw = kz.ss.get(widget_key)
    target_sr = (int(raw) / 100.0) if raw is not None else (kz.getCaseKey("stoch_target_success_rate") or 0.85)
    kz.storeCaseKey("stoch_target_success_rate", target_sr)
    try:
        _apply_stochastic_target(result, target_sr, plan._plotter, plan)
    except Exception as e:
        st.error(f"Failed to update target: {e}")


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

    if rateType == "constant":
        fixedType = kz.getCaseKey("fixedType")
        if fixedType == "historical average":
            if adjusted_range:
                st.warning("Ending year adjusted to be after starting year.")
            plan.setRates("historical average", yfrm, yto)
            # Set fxRates back to computed values.
            for j in range(4):
                kz.pushCaseKey(f"fxRate{j}", 100 * plan.tau_kn[j, -1])
        elif fixedType in ("conservative", "optimistic"):
            # Use backend as single source of truth; sync display from plan
            plan.setRates(fixedType)
            for j in range(4):
                kz.pushCaseKey(f"fxRate{j}", 100 * plan.tau_kn[j, -1])
        else:
            # user: values from UI
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

            # Set reproducibility for histogaussian methods
            if varyingType in ("histogaussian",):
                reproducible = kz.getCaseKey("reproducibleRates")
                seed = kz.getCaseKey("rateSeed") if reproducible else None
                plan.setReproducible(reproducible, seed=seed)

            reverse_seq = kz.getCaseKey("reverse_sequence")
            roll_seq = kz.getCaseKey("roll_sequence")
            reverse_seq = False if reverse_seq is None else bool(reverse_seq)
            roll_seq = 0 if roll_seq is None else int(roll_seq)
            plan.setRates(varyingType, yfrm, yto, reverse=reverse_seq, roll=roll_seq)

            # Store seed, reproducibility, and sequence options back to case keys
            if varyingType in ("histogaussian",):
                kz.setCaseKey("rateSeed", plan.rateSeed)
                kz.setCaseKey("reproducibleRates", plan.reproducibleRates)
            kz.setCaseKey("reverse_sequence", plan.rateReverse)
            kz.setCaseKey("roll_sequence", plan.rateRoll)
            dist = owl.getRatesDistributions(yfrm, yto, plan.mylog)
            # histogaussian is centered on the arithmetic mean (standard Gaussian fit).
            for j in range(4):
                kz.pushCaseKey(f"mean{j}", dist.arith_means[j])
                kz.pushCaseKey(f"stdev{j}", dist.stdev[j])
            # Correlations: Pearson coefficient (-1 to 1), standard representation.
            q = 1
            for k1 in range(plan.N_k):
                for k2 in range(k1 + 1, plan.N_k):
                    kz.pushCaseKey(f"corr{q}", dist.corr[k1, k2])
                    q += 1

        elif varyingType in ("bootstrap_sor", "var", "garch_dcc", "histolognormal"):
            reproducible = kz.getCaseKey("reproducibleRates")
            seed = kz.getCaseKey("rateSeed") if reproducible else None
            plan.setReproducible(reproducible, seed=seed)

            reverse_seq = kz.getCaseKey("reverse_sequence")
            roll_seq = kz.getCaseKey("roll_sequence")
            reverse_seq = False if reverse_seq is None else bool(reverse_seq)
            roll_seq = 0 if roll_seq is None else int(roll_seq)

            kwargs = {}
            if varyingType == "bootstrap_sor":
                bt = kz.getCaseKey("bootstrapType")
                bs = kz.getCaseKey("blockSize")
                if bt is not None:
                    kwargs["bootstrap_type"] = bt
                if bs is not None:
                    kwargs["block_size"] = int(bs)

            try:
                plan.setRates(varyingType, yfrm, yto, reverse=reverse_seq, roll=roll_seq, **kwargs)
            except ValueError as e:
                if varyingType == "garch_dcc":
                    st.error(str(e))
                    return False
                raise

            kz.setCaseKey("rateSeed", plan.rateSeed)
            kz.setCaseKey("reproducibleRates", plan.reproducibleRates)
            kz.setCaseKey("reverse_sequence", plan.rateReverse)
            kz.setCaseKey("roll_sequence", plan.rateRoll)

            dist = owl.getRatesDistributions(yfrm, yto, plan.mylog)
            # bootstrap_sor/var/garch_dcc: arithmetic mean of historical pool for reference.
            # histolognormal: reports equivalent arithmetic statistics after log-space fit.
            for j in range(4):
                kz.pushCaseKey(f"mean{j}", dist.arith_means[j])
                kz.pushCaseKey(f"stdev{j}", dist.stdev[j])
            q = 1
            for k1 in range(plan.N_k):
                for k2 in range(k1 + 1, plan.N_k):
                    kz.pushCaseKey(f"corr{q}", dist.corr[k1, k2])
                    q += 1

        elif varyingType in ("gaussian", "lognormal"):
            means = []
            stdev = []
            corr = []
            for kk in range(plan.N_k):
                means.append(kz.getCaseKey(f"mean{kk}"))
                stdev.append(kz.getCaseKey(f"stdev{kk}"))
            for q in range(1, 7):
                c = kz.getCaseKey(f"corr{q}")
                corr.append(0.0 if c is None else float(c))
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
        plan.readHFP(dicDf)
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
def readHFP(plan, stFile, file=None):
    """
    Load HFP from file -> Plan -> UI.
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
        plan.readHFP(stFile, filename_for_logging=name)
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
def resetWagesAndContributions(plan):
    return plan.zeroWagesAndContributions()


def resetTimeLists():
    tlists = resetWagesAndContributions()
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
            plan.setAllocationRatios("account", taxable=acc[0], taxDeferred=acc[1], taxFree=acc[2], hsa=acc[3])
        except Exception as e:
            st.error(f"Setting asset allocation failed: {e}")
            return
    else:
        st.error(f"Internal error: Unknown account type {kz.getCaseKey('allocType')}.")


@_checkPlan
def plotSingleResults(plan):
    c, n = 0, 2
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

    fig = plan.showTaxes(figure=True)
    if fig:
        tax_title = (
            "Federal Taxes, Medicare, and ACA (+IRMAA)"
            if getattr(plan, "slcsp_annual", 0) > 0
            else "Federal Taxes and Medicare (+IRMAA)"
        )
        cols[c].markdown(f"#### :orange[{tax_title}]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showHSA(figure=True)
    if fig:
        cols[c].markdown("#### :orange[HSA Activity]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    fig = plan.showAccounts(figure=True)
    if fig:
        cols[c].markdown("#### :orange[Savings Balance]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    log_scale = kz.getCaseKey("retention_log_scale")
    log_scale = False if log_scale is None else bool(log_scale)
    fig = plan.showSavingsRetentionRate(figure=True, log_scale=log_scale)
    if fig:
        cols[c].markdown("#### :orange[Savings Retention Rate]")
        renderPlot(fig, cols[c])
        c = (c + 1) % n

    figs = plan.showAssetComposition(figure=True)
    if figs:
        st.markdown("#### :orange[Asset Composition]")
        c, n = 0, 2
        cols = st.columns(n, gap="medium")
        for fig in figs:
            if fig:
                renderPlot(fig, cols[c])
                c = (c + 1) % n


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


@_checkPlan
def setWorksheetShowAges(plan, key):
    val = kz.storepull(key)
    plan.setWorksheetShowAges(val)


@_checkPlan
def setWorksheetHideZeroColumns(plan, key):
    val = kz.storepull(key)
    plan.setWorksheetHideZeroColumns(val)


@_checkPlan
def setWorksheetRealDollars(plan, key):
    val = kz.storepull(key)
    plan.setWorksheetRealDollars(val)


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


def _person_index_for_worksheet(sheet_name, inames):
    """Return individual index if sheet is ``{iname}'s …``; else None (household sheet)."""
    for i, iname in enumerate(inames):
        if sheet_name.startswith(f"{iname}'s "):
            return i
    return None


def _last_alive_calendar_year(plan, i):
    """Last calendar year included in the plan horizon for individual ``i`` (same rule as Plan vprint)."""
    return int(plan.year_n[0]) + int(plan.horizons[i]) - 1


def _worksheet_age_int_cell(y, plan, i, last_alive_year):
    """Nullable integer age for one row, or ``pd.NA`` when year missing or individual deceased."""
    if pd.isna(y):
        return pd.NA
    yi = int(y)
    v = worksheet_age_on_dec_31_or_blank(
        yi, int(plan.yobs[i]), int(plan.mobs[i]), int(plan.tobs[i]), last_alive_year
    )
    if v is None:
        return pd.NA
    return int(v)


def _insert_worksheet_age_columns(df, plan, sheet_name):
    """Insert age columns immediately after ``year``. Returns (df_copy, list of age column names)."""
    years = pd.to_numeric(df["year"], errors="coerce")
    idx = df.columns.get_loc("year") + 1
    dfc = df.copy()
    age_cols = []
    pi = _person_index_for_worksheet(sheet_name, plan.inames)
    if pi is not None:
        col = f"age ({plan.inames[pi]})"
        last_y = _last_alive_calendar_year(plan, pi)
        vals = [_worksheet_age_int_cell(y, plan, pi, last_y) for y in years]
        dfc.insert(idx, col, pd.Series(vals, dtype="Int64", index=dfc.index))
        age_cols.append(col)
    else:
        for i in range(plan.N_i):
            col = f"age ({plan.inames[i]})"
            last_y = _last_alive_calendar_year(plan, i)
            vals = [_worksheet_age_int_cell(y, plan, i, last_y) for y in years]
            dfc.insert(idx + i, col, pd.Series(vals, dtype="Int64", index=dfc.index))
            age_cols.append(col)
    return dfc, age_cols


def _worksheet_df_for_streamlit_display(df):
    """Match legacy string rendering for non-age columns; keep ages as nullable integers."""
    out = df.copy()
    for col in out.columns:
        if isinstance(col, str) and col.startswith("age ("):
            continue
        out[col] = out[col].astype(str)
    return out


def _prepare_worksheet_dataframe(df, plan, sheet_name):
    """
    Optionally drop all-zero numeric columns.
    Age columns are included upstream by plan_to_excel when worksheetShowAges=True.
    Federal sheet: caller formats ``SS % taxed`` after this returns.
    """
    dfc = df.copy()
    if plan.worksheetHideZeroColumns and "year" in dfc.columns:
        # Protect age columns from zero-column filtering
        protected = {"year"} | {c for c in dfc.columns if isinstance(c, str) and c.startswith("age (")}
        dfc = drop_all_zero_numeric_columns(dfc, protected=protected)
    return dfc


def _worksheet_column_config(columns, dollars, pct_sheets, federal_tax_sheet):
    colfor = {}
    num_format = "%.2f" if pct_sheets else "%.3f"
    for col in columns:
        if col == "year":
            colfor[col] = st.column_config.NumberColumn(None, format="%d", width="small")
        elif isinstance(col, str) and col.startswith("age ("):
            colfor[col] = st.column_config.NumberColumn(None, format="%d", width="small")
        elif federal_tax_sheet and col == "SS % taxed":
            colfor[col] = st.column_config.TextColumn(None)
        elif dollars:
            colfor[col] = st.column_config.NumberColumn(None, format="accounting", step=1)
        else:
            colfor[col] = st.column_config.NumberColumn(None, format=num_format)
    return colfor


@_checkPlan
def showWorkbook(plan):
    wb = plan.saveWorkbook(saveToFile=False)
    if wb is None:
        return

    currencySheets = ["Income", "Cash Flow", "Sources", "Accounts"]
    for name in wb.sheetnames:
        if name == "Summary" or name.startswith("Config"):
            continue

        dollars = False
        for word in currencySheets:
            if word in name:
                dollars = True
                break

        pct_sheets = "Allocations" in name or name == "Rates"
        federal_tax_sheet = name == "Federal Income Tax"

        ws = wb[name]
        df = pd.DataFrame(ws.values)
        new_header = df.iloc[0]
        df = df[1:]
        df.columns = new_header

        if federal_tax_sheet:
            df = _prepare_worksheet_dataframe(df, plan, name)
            if "SS % taxed" in df.columns:
                df = df.copy()
                df["SS % taxed"] = (100 * df["SS % taxed"].astype(float)).map(lambda x: f"{x:.1f}%")
        else:
            df = _prepare_worksheet_dataframe(df, plan, name)

        colfor = _worksheet_column_config(df.columns, dollars, pct_sheets, federal_tax_sheet)

        st.markdown(f"#### :orange[{name}]")
        if "Accounts" in name:
            acct_note = " Opening balance as of Jan 1st of that year."
            display_df = df.style.apply(highlight_year_row, axis=1)
            st.dataframe(display_df, width="stretch", column_config=colfor,
                         hide_index=True, placeholder="-")
        else:
            acct_note = ""
            st.dataframe(
                _worksheet_df_for_streamlit_display(df),
                width="stretch",
                column_config=colfor,
                hide_index=True,
                placeholder="-",
            )

        dollar_label = "real (today's) $" if getattr(plan, "worksheetRealDollars", False) else "nominal $"
        age_note = (
            " Ages are as of December 31 of each row's calendar year; "
            "blank after an individual's plan horizon."
        ) if plan.worksheetShowAges else ""

        if federal_tax_sheet:
            cap = (
                f"Values are in {dollar_label}, rounded to the nearest dollar. "
                "SS % taxed is the fraction of Social Security benefits subject to federal tax."
            )
            st.caption(cap + age_note)
        elif dollars:
            st.caption(f"Values are in {dollar_label}, rounded to the nearest dollar." + acct_note + age_note)
        elif pct_sheets:
            st.caption("Values are in percent, with 2 decimal places." + age_note)
        else:
            st.caption("Values are fractional." + age_note)


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
def markHFPAsSaved(plan):
    """
    Update timeListsFileName from "edited values" to HFP_{caseName}.xlsx.
    Call this only when the user has actually downloaded the HFP workbook.
    """
    current_filename = kz.getCaseKey("timeListsFileName")
    if current_filename == "edited values":
        case_name = kz.getCaseKey("name")
        if case_name:
            suggested_filename = f"HFP_{case_name}.xlsx"
            kz.storeCaseKey("timeListsFileName", suggested_filename)
            plan.timeListsFileName = suggested_filename


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
    from owlplanner.config import load_toml
    from owlplanner.config import config_to_plan
    from owlplanner.config import config_to_ui

    logstrio = StringIO()
    try:
        diconf, dirname, _ = load_toml(strio, log_stream=logstrio)
        plan = config_to_plan(
            diconf,
            dirname,
            verbose=True,
            logstreams=[logstrio, logstrio],
            loadHFP=False,
        )
    except Exception as e:
        st.error(f"Failed to parse case file: {e}")
        return "", {}

    mydic = config_to_ui(diconf)
    mydic["plan"] = plan
    mydic["id"] = plan._id
    mydic["summaryDf"] = None
    mydic["casetoml"] = ""
    mydic["caseStatus"] = "new"
    mydic["logs"] = logstrio
    mydic["config"] = diconf  # Store canonical config for round-trip of user keys

    val = kz.getGlobalKey("plotGlobalBackend")
    if val:
        plan.setPlotBackend(val)

    return plan._name, mydic


def genDic(plan):
    """
    From Plan to UI.
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
    dic["effectiveTx"] = 100 * plan.effectiveTaxRate
    dic["yOBBBA"] = plan.yOBBBA
    dic["surplusFraction"] = plan.eta
    dic["plots"] = plan.defaultPlots
    dic["worksheetShowAges"] = plan.worksheetShowAges
    dic["worksheetHideZeroColumns"] = plan.worksheetHideZeroColumns
    dic["worksheetRealDollars"] = plan.worksheetRealDollars
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
        frac = plan.pensionSurvivorFraction[i] if hasattr(plan, "pensionSurvivorFraction") else 0.0
        dic[f"pSurv{i}"] = int(round(frac * 100))
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
               "spendingSlack", "spendingWeight", "spendingFloor", "timePreference", "oppCostX",
               "amoConstraints", "amoRoth", "amoSurplus", "withSCLoop",
               "absTol", "bigMamo", "relTol",]
    for key in optList:
        if key in solverOptionKeys:
            dic[key] = plan.solverOptions[key]

    if "minTaxableBalance" in solverOptionKeys:
        mbl = plan.solverOptions["minTaxableBalance"]
        if isinstance(mbl, (list, tuple)) and len(mbl) >= 1:
            dic["minTaxableBalance0"] = mbl[0] if mbl[0] is not None else 0
        if isinstance(mbl, (list, tuple)) and len(mbl) >= 2:
            dic["minTaxableBalance1"] = mbl[1] if mbl[1] is not None else 0

    if "withMedicare" in solverOptionKeys:
        opt = plan.solverOptions["withMedicare"]
        dic["computeMedicare"] = False if opt == "None" else True
        dic["optimizeMedicare"] = True if opt == "optimize" else False

    dic["slcspAnnual"] = getattr(plan, "slcsp_annual", 0.0) / 1000
    dic["optimizeACA"] = plan.solverOptions.get("withACA", "loop") == "optimize"
    dic["useDecomposition"] = plan.solverOptions.get("withDecomposition", "none")

    ss_val = plan.solverOptions.get("withSSTaxability", "loop")
    if isinstance(ss_val, (int, float)):
        dic["ssTaxabilityMode"] = "value"
        dic["ssTaxabilityValue"] = float(ss_val)
    else:
        dic["ssTaxabilityMode"] = ss_val
        dic["ssTaxabilityValue"] = 0.85

    _ssa_opt = plan.solverOptions.get("withSSAges", "fixed")
    ni = plan.N_i
    if isinstance(_ssa_opt, (list, tuple)):
        _ssa_names = set(_ssa_opt)
        if _ssa_names >= set(plan.inames):
            dic["ssAgesMode"] = "both" if ni > 1 else plan.inames[0]
        elif plan.inames[0] in _ssa_names:
            dic["ssAgesMode"] = plan.inames[0]
        elif ni > 1 and plan.inames[1] in _ssa_names:
            dic["ssAgesMode"] = plan.inames[1]
        else:
            dic["ssAgesMode"] = "none"
    elif _ssa_opt == "optimize":
        dic["ssAgesMode"] = "both" if ni > 1 else plan.inames[0]
    else:
        dic["ssAgesMode"] = "none"

    if "previousMAGIs" in solverOptionKeys:
        dic["MAGI0"] = plan.solverOptions["previousMAGIs"][0]
        dic["MAGI1"] = plan.solverOptions["previousMAGIs"][1]

    if plan.objective == "maxSpending":
        dic["objective"] = "Net spending"
    elif plan.objective == "maxHybrid":
        dic["objective"] = "Hybrid"
    else:
        dic["objective"] = "Bequest"

    if plan.rateMethod in ["trailing-30", "conservative", "optimistic", "historical average", "user"]:
        dic["rateType"] = "constant"
        dic["fixedType"] = plan.rateMethod
    elif plan.rateMethod == "dataframe":
        dic["rateType"] = "constant"
        dic["fixedType"] = "user"
    elif plan.rateMethod in ["histogaussian", "historical", "gaussian",
                             "lognormal", "histolognormal", "bootstrap_sor", "var", "garch_dcc"]:
        dic["rateType"] = "varying"
        dic["varyingType"] = plan.rateMethod
        if plan.rateMethod == "bootstrap_sor":
            params = plan.rateModel.params
            dic["bootstrapType"] = params.get("bootstrap_type", "iid")
            dic["blockSize"] = params.get("block_size", 1)

    # Initialize in both cases. Plan stores rateValues in percent when set; else use tau_kn (decimal).
    for k1 in range(plan.N_k):
        if plan.rateValues is not None:
            dic[f"fxRate{k1}"] = plan.rateValues[k1]
        else:
            dic[f"fxRate{k1}"] = 100 * plan.tau_kn[k1, -1]

    if plan.rateMethod in ["historical average", "histogaussian", "historical",
                           "histolognormal", "bootstrap_sor", "var", "garch_dcc"]:
        dic["yfrm"] = plan.rateFrm
        dic["yto"] = plan.rateTo
    elif plan.rateMethod == "dataframe":
        dic["yfrm"] = FROM
        dic["yto"] = date.today().year - 1
    else:
        dic["yfrm"] = FROM
        # Rates availability are trailing by 1 year.
        dic["yto"] = date.today().year - 1

    if plan.rateMethod in ["gaussian", "lognormal", "histogaussian",
                           "bootstrap_sor", "var", "garch_dcc"]:
        qq = 1
        for k1 in range(plan.N_k):
            if plan.rateValues is not None:
                dic[f"mean{k1}"] = plan.rateValues[k1]  # Plan stores percent
                dic[f"stdev{k1}"] = plan.rateStdev[k1] if plan.rateStdev is not None else 0
            else:
                dic[f"mean{k1}"] = 100 * plan.tau_kn[k1, -1]
                dic[f"stdev{k1}"] = plan.rateStdev[k1] if plan.rateStdev is not None else 0
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
    # Check if we have a valid case selected.
    case_name = kz.currentCaseName()
    if case_name is None:
        return None

    # If a plan exists, use its logger (which already writes to the case's logs StringIO)
    plan = kz.getCaseKey("plan")
    if plan is not None:
        return plan.logger()

    # No plan exists yet - get or create the current case's log stream
    log_stream = kz.getCaseKey("logs")
    if log_stream is None:
        # Only create/store if the current case actually exists (e.g. avoid after reconnect)
        if not kz.has_current_case():
            return None
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
