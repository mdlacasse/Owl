"""
Rates page for Owl retirement planner Streamlit UI.

This module provides the interface for selecting rate of return assumptions
for different asset classes, including fixed and varying rate options.

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
from datetime import date

from owlplanner.rate_models.constants import GARCH_DCC_MIN_OBSERVATIONS

import sskeys as kz
import owlbridge as owb
import case_progress as cp


def _get_fx_rates():
    """Build FXRATES from canonical fixed rate methods. Single source of truth."""
    # Use FIXED_TYPE_UI order; values from owlplanner.rates.get_fixed_rate_values
    methods = owb.FIXED_TYPE_UI
    result = {}
    for m in methods:
        if m == "historical average":
            result[m] = [0, 0, 0, 0]  # placeholder; computed at runtime
        elif m == "user":
            result[m] = owb.getFixedRates("conservative")  # default initial values
        elif m in ("trailing-30", "conservative", "optimistic"):
            result[m] = owb.getFixedRates(m)
        else:
            result[m] = owb.getFixedRates("conservative")
    return result


FXRATES = _get_fx_rates()

rateChoices = ["constant", "varying"]
fixedChoices = list(FXRATES)
varyingChoices = list(owb.VARYING_TYPE_UI)


def updateFixedRates(key, pull=True):
    if pull:
        fxType = kz.setpull(key)
    else:
        fxType = key

    if fxType in ("trailing-30", "conservative", "optimistic"):
        rates = FXRATES[fxType]
        for j in range(4):
            kz.pushCaseKey(f"fxRate{j}", rates[j])
    else:
        for j in range(4):
            rname = f"fxRate{j}"
            kz.pushCaseKey(rname, kz.getCaseKey(rname))
    owb.setRates()


def updateRates(key):
    kz.setpull(key)
    if kz.getCaseKey(key) == "constant":
        updateFixedRates(kz.getCaseKey("fixedType"), False)
    else:
        owb.setRates()


def initRates():
    if kz.getCaseKey("rateType") == "constant" and kz.getCaseKey("fixedType") != "historical":
        updateFixedRates(kz.getCaseKey("fixedType"), False)
    else:
        owb.setRates()
    kz.flagModified()


kz.initCaseKey("rateType", rateChoices[0])
kz.initCaseKey("fixedType", fixedChoices[0])
kz.initCaseKey("varyingType", varyingChoices[0])

ret = kz.titleBar(":material/monitoring: Rates")

if ret is None or kz.caseHasNoPlan():
    st.info("A case must first be created before running this page.")
else:
    kz.runOncePerCase(initRates)
    kz.initCaseKey("yfrm", owb.FROM)
    kz.initCaseKey("yto", owb.TO)
    kz.initCaseKey("reverse_sequence", False)
    kz.initCaseKey("roll_sequence", 0)
    helpmsgSP500 = """Rate also includes dividends.
Unless historical, S&P 500 can be used to represent any mix of equities
(domestic, international, emerging, ...).
"""
    helpmsgBaa = "Investment-grade corporate debt from issuers with a moderate risk of default."
    helpmsgTnote = "T-Notes are medium-term, low-risk U.S. government debt, offering state/local tax-exempt interest."
    helpmsgCash = """Here, "Cash Assets" are TIPS-like securities assumed to track inflation."""
    helpFixed = """A 2025 roundup of expert opinions on stock and bond return
forecasts for the next decade can be found
[here](https://www.morningstar.com/portfolios/experts-forecast-stock-bond-returns-2025-edition)."""
    helpVarying = "Select the method used to generate annual rates of return. See the description on the right."
    helpYfrm = "First year of historical data included in the range. Must be at least 2 years before the ending year."
    helpYto = ("Last year of historical data included in the range. "
               "For *historical* method, fixed by the starting year and plan horizon. "
               "At least 2 years of data are required for statistical calculations.")
    helpBootstrapType = """Resampling strategy used to build synthetic rate sequences:

- **iid**: draw individual years independently at random (no serial structure).
- **block**: draw consecutive fixed-length blocks, preserving short-run serial correlation.
- **circular**: block bootstrap that wraps around the dataset ends to avoid edge effects.
- **stationary**: variable-length blocks drawn from a geometric distribution, \
preserving stationarity."""
    helpCorr = ("Pearson correlation coefficient between the two asset-class returns. "
                "Ranges from -1 (perfectly inversely correlated) to +1 (perfectly correlated). "
                "0 means no linear relationship.")

    st.markdown("#### :orange[Type of Rates]")
    col1, col2, col3 = st.columns([1, 1, 2.07], gap="large", vertical_alignment="bottom")
    with col1:
        helpmsg = "Rates can be constant for the duration of the plan or change annually."
        kz.getRadio("Annual rates type", rateChoices, "rateType", updateRates, help=helpmsg)

    if kz.getCaseKey("rateType") == "constant":
        fxType = kz.getCaseKey("fixedType")
        if fxType != "historical":
            updateFixedRates(fxType, False)

        with col2:
            fxType = kz.getSelectbox("Select constant rates", fixedChoices, "fixedType", updateFixedRates,
                                     help=helpFixed)
        with col3:
            st.caption(owb.getMethodDescription(fxType))

        st.divider()
        ro = fxType != "user"
        min_rate = -100.0 if fxType == "historical average" else 0.0

        st.markdown("#### :orange[Constant Rate Values (%)]")
        rates = FXRATES[fxType]
        for j in range(4):
            kz.initCaseKey(f"fxRate{j}", rates[j])

        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.getNum("S&P 500", "fxRate0", disabled=ro, step=1.0, help=helpmsgSP500,
                      callback=updateRates, min_value=min_rate, max_value=100.0)

        with col2:
            kz.getNum("Bonds Baa", "fxRate1", disabled=ro, step=1.0, help=helpmsgBaa,
                      callback=updateRates, min_value=min_rate, max_value=100.0)

        with col3:
            kz.getNum("10-y Treasury Notes", "fxRate2", disabled=ro, step=1.0, help=helpmsgTnote,
                      callback=updateRates, min_value=min_rate, max_value=100.0)

        with col4:
            kz.getNum("Cash Assets/Inflation", "fxRate3", disabled=ro, step=1.0, help=helpmsgCash,
                      callback=updateRates, min_value=min_rate, max_value=100.0)

    elif kz.getCaseKey("rateType") == "varying":
        with col2:
            varyingType = kz.getSelectbox("Select varying rates", varyingChoices, "varyingType",
                                          callback=updateRates, help=helpVarying)
        with col3:
            st.caption(owb.getMethodDescription(varyingType))

    else:
        st.error("Logic error")

    if (kz.getCaseKey("rateType") == "constant" and "hist" in kz.getCaseKey("fixedType")) or (
        kz.getCaseKey("rateType") == "varying" and kz.getCaseKey("varyingType") in owb.HISTORICAL_RANGE_METHODS
    ):
        is_garch_ui = (
            kz.getCaseKey("rateType") == "varying" and kz.getCaseKey("varyingType") == "garch_dcc"
        )
        min_year_gap = (GARCH_DCC_MIN_OBSERVATIONS - 1) if is_garch_ui else 2
        # Enforce yto >= yfrm + min_year_gap before rendering so neither widget is
        # ever in an invalid state (avoids Streamlit deadlock).
        yfrm_val = kz.getCaseKey("yfrm")
        yto_val = kz.getCaseKey("yto")
        if yfrm_val is not None and yto_val is not None:
            yto_val = min(owb.TO, max(yto_val, yfrm_val + min_year_gap))
            yfrm_val = max(owb.FROM, min(yfrm_val, yto_val - min_year_gap))
            kz.pushCaseKey("yfrm", yfrm_val)
            kz.pushCaseKey("yto", yto_val)
        # Sync case -> widget keys so number_inputs show current values (needed when normalization was skipped).
        kz.pushCaseKey("yfrm")
        kz.pushCaseKey("yto")

        if is_garch_ui:
            help_yfrm = (
                "First year of historical data in the range. "
                f"DCC-GARCH needs at least {GARCH_DCC_MIN_OBSERVATIONS} calendar years inclusive "
                "(ending year − starting year + 1)."
            )
            help_yto = (
                "Last year of historical data in the range. "
                f"DCC-GARCH needs at least {GARCH_DCC_MIN_OBSERVATIONS} calendar years inclusive."
            )
        else:
            help_yfrm = helpYfrm
            help_yto = helpYto

        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col3:
            if kz.getCaseKey("varyingType") == "historical":
                maxValue = owb.TO
            elif is_garch_ui:
                maxValue = kz.getCaseKey("yto") - (GARCH_DCC_MIN_OBSERVATIONS - 1)
            else:
                maxValue = kz.getCaseKey("yto") - 1
            kz.getIntNum(
                "Starting year",
                "yfrm",
                min_value=owb.FROM,
                max_value=maxValue,
                callback=updateRates,
                help=help_yfrm,
            )

        with col4:
            ishistorical = kz.getCaseKey("rateType") == "varying" and kz.getCaseKey("varyingType") == "historical"
            kz.getIntNum(
                "Ending year",
                "yto",
                max_value=owb.TO,
                min_value=kz.getCaseKey("yfrm") + min_year_gap,
                disabled=ishistorical,
                callback=updateRates,
                help=help_yto,
            )

    if kz.getCaseKey("rateType") == "varying" and kz.getCaseKey("varyingType") == "bootstrap_sor":
        kz.initCaseKey("bootstrapType", "iid")
        kz.initCaseKey("blockSize", 1)
        bootstrap_choices = ["iid", "block", "circular", "stationary"]
        col1, col2, col3 = st.columns([2.08, 1, 1], gap="large", vertical_alignment="top")
        with col1:
            kz.getRadio("Bootstrap type", bootstrap_choices, "bootstrapType", callback=updateRates,
                        help=helpBootstrapType)
        with col2:
            bt = kz.getCaseKey("bootstrapType")
            kz.getIntNum("Block size", "blockSize", min_value=1, max_value=50, step=1,
                         disabled=(bt == "iid"), callback=updateRates,
                         help="Block length for block/circular/stationary bootstraps.")

    if kz.getCaseKey("rateType") == "varying":
        st.divider()
        st.markdown("#### :orange[Stochastic Parameters]")
        ro = kz.getCaseKey("varyingType") not in ("gaussian", "lognormal")
        st.markdown("##### Means (%)")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("mean0", 0)
            kz.getNum("S&P 500", "mean0", disabled=ro, help=helpmsgSP500,
                      step=1.0, min_value=-100.0, max_value=100.0, callback=updateRates)

        with col2:
            kz.initCaseKey("mean1", 0)
            kz.getNum("Bonds Baa", "mean1", disabled=ro, help=helpmsgBaa,
                      step=1.0, min_value=-100.0, max_value=100.0, callback=updateRates)

        with col3:
            kz.initCaseKey("mean2", 0)
            kz.getNum("10-y Treasury Notes", "mean2", disabled=ro, step=1.0, help=helpmsgTnote,
                      min_value=-100.0, max_value=100.0, callback=updateRates)

        with col4:
            kz.initCaseKey("mean3", 0)
            kz.getNum("Cash Assets/Inflation", "mean3", disabled=ro, help=helpmsgCash,
                      step=1.0, min_value=-100.0, max_value=100.0, callback=updateRates)

        st.markdown("##### Volatility (%)")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("stdev0", 0)
            kz.getNum("S&P 500", "stdev0", disabled=ro, step=1.0, callback=updateRates,
                      help=helpmsgSP500)

        with col2:
            kz.initCaseKey("stdev1", 0)
            kz.getNum("Bonds Baa", "stdev1", disabled=ro, step=1.0, callback=updateRates,
                      help=helpmsgBaa)

        with col3:
            kz.initCaseKey("stdev2", 0)
            kz.getNum("10-y Treasury Notes", "stdev2", disabled=ro, step=1.0, callback=updateRates,
                      help=helpmsgTnote)

        with col4:
            kz.initCaseKey("stdev3", 0)
            kz.getNum("Cash Assets/Inflation", "stdev3", disabled=ro, step=1.0, callback=updateRates,
                      help=helpmsgCash)

        st.markdown("##### Correlation matrix")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("diag1", 1)
            kz.getNum("S&P 500", "diag1", disabled=True, format="%.2f", callback=None)

        with col2:
            kz.initCaseKey("corr1", 0.0)
            kz.getNum("(1,2)", "corr1", disabled=ro, step=0.01, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates, help=helpCorr)
            kz.initCaseKey("diag2", 1.0)
            kz.getNum("Bonds Baa", "diag2", disabled=True, format="%.2f",
                      callback=None)

        with col3:
            kz.initCaseKey("corr2", 0.0)
            kz.getNum("(1,3)", "corr2", disabled=ro, step=0.01, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates, help=helpCorr)
            kz.initCaseKey("corr4", 0.0)
            kz.getNum("(2,3)", "corr4", disabled=ro, step=0.01, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates, help=helpCorr)
            kz.initCaseKey("diag3", 1.0)
            kz.getNum("10-y Treasury Notes", "diag3", disabled=True, format="%.2f",
                      callback=None)

        with col4:
            kz.initCaseKey("corr3", 0.0)
            kz.getNum("(1,4)", "corr3", disabled=ro, step=0.01, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates, help=helpCorr)
            kz.initCaseKey("corr5", 0.0)
            kz.getNum("(2,4)", "corr5", disabled=ro, step=0.01, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates, help=helpCorr)
            kz.initCaseKey("corr6", 0.0)
            kz.getNum("(3,4)", "corr6", disabled=ro, step=0.01, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates, help=helpCorr)
            kz.initCaseKey("diag4", 1.0)
            kz.getNum("Cash Assets/Inflation", "diag4", disabled=True, format="%.2f",
                      callback=None)

    st.divider()
    if kz.getCaseKey("rateType") == "varying":
        col1, col2 = st.columns(2, gap="medium")
        owb.showRatesCorrelations(col2)
    else:
        col1, col2 = st.columns([0.6, 0.4], gap="medium")

    owb.showRates(col1)

    # st.divider()
    with st.expander("*Advanced options*"):
        # Rate sequence (reverse / roll) — only for varying (non-fixed) methods
        if kz.getCaseKey("rateType") == "varying":
            st.markdown("#### :orange[Rate sequence]")
            plan = kz.getCaseKey("plan")
            N_n = plan.N_n if plan is not None else 50
            help_reverse = "Reverse the rate sequence along the time axis (e.g. run last year first)."
            help_roll = "Roll the rate sequence by this many years (0 = no shift)."
            col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="bottom")
            with col2:
                kz.getToggle("Reverse sequence", "reverse_sequence", callback=updateRates, help=help_reverse)
            with col1:
                kz.initCaseKey("roll_sequence", 0)
                kz.getIntNum("Roll (years)", "roll_sequence", min_value=0, max_value=N_n,
                             step=1, callback=updateRates, help=help_roll)
            # st.markdown("#####")

        st.markdown("#### :orange[Other Rates]")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("divRate", 1.72)
            helpmsg = """Average annual (qualified) dividend yield on stock portfolio in taxable account.
See latest data [here](https://us500.com/tools/data/sp500-dividend-yield)."""
            ret = kz.getNum("Dividend rate (%)", "divRate", max_value=5.0, format="%.2f", help=helpmsg, step=1.0)

        # st.markdown("#####")
        st.markdown("#### :orange[Income taxes]")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("heirsTx", 30)
            helpmsg = "Marginal tax rate that heirs would have to pay on inherited tax-deferred balance."
            ret = kz.getNum("Heirs marginal tax rate (%)", "heirsTx", max_value=100.0, help=helpmsg, step=1.0)

        with col2:
            kz.initCaseKey("yOBBBA", 2032)
            thisyear = date.today().year
            helpmsg = "Year at which the OBBBA tax rates are projected to expire and return to pre-TCJA rates."
            ret = kz.getIntNum("OBBBA expiration year", "yOBBBA",
                               min_value=thisyear, max_value=thisyear+40, help=helpmsg)

        # Reproducibility checkbox - only for stochastic and histochastic methods.
        if kz.getCaseKey("varyingType") in [
            "gaussian", "lognormal", "histogaussian", "histolognormal",
            "bootstrap_sor", "var", "garch_dcc",
        ]:
            st.markdown("#####")
            st.markdown("#### :orange[Rate Generation]")
            kz.initCaseKey("reproducibleRates", False)
            kz.initCaseKey("rateSeed", None)
            helpmsgRepro = """When enabled, the same random seed will be used to generate rates,
ensuring reproducible results across case runs. This is useful for comparing
other parameters while keeping rates constant."""
            st.checkbox(
                "Enable reproducible rates",
                value=kz.getCaseKey("reproducibleRates"),
                on_change=updateRates,
                args=["reproducibleRates"],
                key=kz.genCaseKey("reproducibleRates"),
                help=helpmsgRepro,
            )

    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar()
