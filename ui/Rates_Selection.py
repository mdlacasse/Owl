import streamlit as st

import sskeys as kz
import owlbridge as owb


FXRATES = {
    "conservative": [7, 4, 3.3, 2.8],
    "optimistic": [10, 6, 5, 3],
    "historical average": [0, 0, 0, 0],
    "user": [7, 4, 3.3, 2.8],
}

rateChoices = ["fixed", "varying"]
fixedChoices = list(FXRATES)
varyingChoices = ["historical", "histochastic", "stochastic"]


def updateFixedRates(key, pull=True):
    if pull:
        fxType = kz.setpull(key)
    else:
        fxType = key

    if fxType in ["conservative", "optimistic"]:
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
    if kz.getCaseKey(key) == "fixed":
        updateFixedRates(kz.getCaseKey("fixedType"), False)
    else:
        owb.setRates()


def initRates():
    if kz.getCaseKey("rateType") == "fixed" and kz.getCaseKey("fixedType") != "historical":
        updateFixedRates(kz.getCaseKey("fixedType"), False)
    else:
        owb.setRates()
    kz.flagModified()


kz.initCaseKey("rateType", rateChoices[0])
kz.initCaseKey("fixedType", fixedChoices[0])
kz.initCaseKey("varyingType", varyingChoices[0])

ret = kz.titleBar(":material/monitoring: Rates Selection")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    kz.runOncePerCase(initRates)
    kz.initCaseKey("yfrm", owb.FROM)
    kz.initCaseKey("yto", owb.TO)
    helpmsgSP500 = """Rate also includes dividends.
Unless historical, S&P 500 can represent any mix of equities
(domestic, international, emerging, ...).
"""
    helpmsgBaa = "Investment-grade corporate debt from issuers with a moderate risk of default."
    helpmsgTnote = "T-Notes are medium-term, low-risk U.S. government debt, offering state/local tax-exempt interest."
    helpmsgCash = """Here, "Cash Assets" are TIPS-like securities assumed to track inflation."""
    helpFixed = """A 2025 roundup of expert opinions on stock and bond return
forecasts for the next decade can be found
[here](https://www.morningstar.com/portfolios/experts-forecast-stock-bond-returns-2025-edition)."""

    st.write("#### :orange[Type of Rates]")
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        helpmsg = "Rates can be fixed for the duration of the plan or change annually."
        kz.getRadio("## Annual rates type", rateChoices, "rateType", updateRates, help=helpmsg)

    if kz.getCaseKey("rateType") == "fixed":
        fxType = kz.getCaseKey("fixedType")
        if fxType != "historical":
            updateFixedRates(fxType, False)

        with col2:
            fxType = kz.getRadio("Select fixed rates", fixedChoices, "fixedType", updateFixedRates,
                                 help=helpFixed)

        st.divider()
        ro = fxType != "user"

        st.write("#### :orange[Fixed Rate Values (%)]")
        rates = FXRATES[fxType]
        for j in range(4):
            kz.initCaseKey(f"fxRate{j}", rates[j])

        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.getRateNum("S&P 500", "fxRate0", ro, step=1.0, help=helpmsgSP500, callback=updateRates)

        with col2:
            kz.getRateNum("Corporate Bonds Baa", "fxRate1", ro, step=1.0, help=helpmsgBaa, callback=updateRates)

        with col3:
            kz.getRateNum("10-y Treasury Notes", "fxRate2", ro, step=1.0, help=helpmsgTnote, callback=updateRates)

        with col4:
            kz.getRateNum("Cash Assets/Inflation", "fxRate3", ro, step=1.0, help=helpmsgCash, callback=updateRates)

    elif kz.getCaseKey("rateType") == "varying":
        with col2:
            kz.getRadio("Select varying rates", varyingChoices, "varyingType", callback=updateRates)

    else:
        st.error("Logic error")

    if (kz.getCaseKey("rateType") == "fixed" and "hist" in kz.getCaseKey("fixedType")) or (
        kz.getCaseKey("rateType") == "varying" and "hist" in kz.getCaseKey("varyingType")
    ):

        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col3:
            maxValue = owb.TO if kz.getCaseKey("varyingType") == "historical" else kz.getCaseKey("yto") - 1
            kz.pushCaseKey("yfrm")
            st.number_input(
                "Starting year",
                min_value=owb.FROM,
                max_value=maxValue,
                on_change=updateRates,
                args=["yfrm"],
                key=kz.genCaseKey("yfrm"),
            )

        with col4:
            ishistorical = kz.getCaseKey("rateType") == "varying" and kz.getCaseKey("varyingType") == "historical"
            kz.pushCaseKey("yto")
            st.number_input(
                "Ending year",
                max_value=owb.TO,
                min_value=kz.getCaseKey("yfrm") + 1,
                disabled=ishistorical,
                on_change=updateRates,
                args=["yto"],
                key=kz.genCaseKey("yto"),
            )

    if kz.getCaseKey("rateType") == "varying":
        st.divider()
        st.write("#### :orange[Stochastic Parameters]")
        ro = kz.getCaseKey("varyingType") != "stochastic"
        st.write("##### Means (%)")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("mean0", 0)
            kz.getRateNum("S&P 500", "mean0", ro, help=helpmsgSP500, step=1.0, min_value=-9.0, callback=updateRates)

        with col2:
            kz.initCaseKey("mean1", 0)
            kz.getRateNum("Corporate Bonds Baa", "mean1", ro, help=helpmsgBaa,
                          step=1.0, min_value=-9.0, callback=updateRates)

        with col3:
            kz.initCaseKey("mean2", 0)
            kz.getRateNum("10-y Treasury Notes", "mean2", ro, step=1.0, help=helpmsgTnote,
                          min_value=-9.0, callback=updateRates)

        with col4:
            kz.initCaseKey("mean3", 0)
            kz.getRateNum("Cash Assets/Inflation", "mean3", ro, help=helpmsgCash,
                          step=1.0, min_value=-9.0, callback=updateRates)

        st.write("##### Volatility (%)")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("stdev0", 0)
            kz.getRateNum("S&P 500", "stdev0", ro, step=1.0, callback=updateRates)

        with col2:
            kz.initCaseKey("stdev1", 0)
            kz.getRateNum("Corporate Bonds Baa", "stdev1", ro, step=1.0, callback=updateRates)

        with col3:
            kz.initCaseKey("stdev2", 0)
            kz.getRateNum("10-y Treasury Notes", "stdev2", ro, step=1.0, callback=updateRates)

        with col4:
            kz.initCaseKey("stdev3", 0)
            kz.getRateNum("Cash Assets/Inflation", "stdev3", ro, step=1.0, callback=updateRates)

        st.write("##### Correlation matrix")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("diag1", 1)
            kz.getRateNum("S&P 500", "diag1", True, format="%.2f", callback=None)

        with col2:
            kz.initCaseKey("corr1", 0.0)
            kz.getRateNum("(1,2)", "corr1", ro, step=0.1, format="%.2f",
                          min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("diag2", 1.0)
            kz.getRateNum("Corporate Bonds Baa", "diag2", True, format="%.2f",
                          min_value=-1.0, max_value=1.0, callback=None)

        with col3:
            kz.initCaseKey("corr2", 0.0)
            kz.getRateNum("(1,3)", "corr2", ro, step=0.1, format="%.2f",
                          min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("corr4", 0.0)
            kz.getRateNum("(2,3)", "corr4", ro, step=0.1, format="%.2f",
                          min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("diag3", 1.0)
            kz.getRateNum("10-y Treasury Notes", "diag3", True, format="%.2f",
                          min_value=-1.0, max_value=1.0, callback=None)

        with col4:
            kz.initCaseKey("corr3", 0.0)
            kz.getRateNum("(1,4)", "corr3", ro, step=0.1, format="%.2f",
                          min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("corr5", 0.0)
            kz.getRateNum("(2,4)", "corr5", ro, step=0.1, format="%.2f",
                          min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("corr6", 0.0)
            kz.getRateNum("(3,4)", "corr6", ro, step=0.1, format="%.2f",
                          min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("diag4", 1.0)
            kz.getRateNum("Cash Assets/Inflation", "diag4", True, format="%.2f",
                          min_value=-1.0, max_value=1.0, callback=None)

    st.divider()
    if kz.getCaseKey("rateType") == "varying":
        col1, col2 = st.columns(2, gap="medium")
        owb.showRatesCorrelations(col2)
    else:
        col1, col2 = st.columns([0.6, 0.4], gap="medium")

    owb.showRates(col1)

    # st.divider()
    st.write("#### :orange[Other Rates]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        kz.initCaseKey("divRate", 1.8)
        helpmsg = "Average annual (qualified) dividend return rate on stock portfolio in taxable account."
        ret = kz.getNum("Dividend rate (%)", "divRate", max_value=5.0, format="%.2f", help=helpmsg, step=1.0)

    st.write("#####")
    st.write("#### :orange[Income taxes]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        kz.initCaseKey("heirsTx", 30)
        helpmsg = "Marginal tax rate that heirs would have to pay on inherited tax-deferred balance."
        ret = kz.getNum("Heirs marginal tax rate (%)", "heirsTx", max_value=100.0, help=helpmsg, step=1.0)

    with col2:
        kz.initCaseKey("yOBBBA", 2032)
        helpmsg = "Year at which the OBBBA tax rates are speculated to be expired and return to pre-TCJA rates."
        ret = kz.getIntNum("OBBBA expiration year", "yOBBBA", help=helpmsg)
