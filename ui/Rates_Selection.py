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

    rates = FXRATES[fxType]
    for j in range(4):
        kz.setKey("fxRate" + str(j), rates[j])
    owb.setRates()


def updateRates(key):
    kz.setpull(key)
    if kz.getKey(key) == "fixed":
        updateFixedRates(kz.getKey("fixedType"), False)
    else:
        owb.setRates()


def initRates():
    if kz.getKey("rateType") == rateChoices[0] and kz.getKey("fixedType") == fixedChoices[0]:
        updateFixedRates(fixedChoices[0], False)
    else:
        owb.setRates()
    kz.flagModified()


kz.initKey("rateType", rateChoices[0])
kz.initKey("fixedType", fixedChoices[0])
kz.initKey("varyingType", varyingChoices[0])

ret = kz.titleBar(":material/monitoring: Rates Selection")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    kz.runOncePerCase(initRates)
    kz.initKey("yfrm", owb.FROM)
    kz.initKey("yto", owb.TO)
    helpmsgSP500 = """Rate also includes dividends.
Unless historical, S&P 500 can represent any mix of equities
(domestic, international, emerging, ...).
"""
    helpFixed = """A 2025 roundup of expert opinions on stock and bond return
forecasts for the next decade can be found
[here](https://www.morningstar.com/portfolios/experts-forecast-stock-bond-returns-2025-edition)."""
    helpCash = """Here, "Cash Assets" are TIPS-like securities assumed to track inflation."""

    st.write("#### :orange[Type of Rates]")
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        kz.getRadio("## Annual rates type", rateChoices, "rateType", updateRates)

    if kz.getKey("rateType") == "fixed":
        with col2:
            fxType = kz.getRadio("Select fixed rates", fixedChoices, "fixedType", updateFixedRates,
                                 help=helpFixed)

        st.divider()
        ro = fxType != "user"

        st.write("#### :orange[Fixed Rate Values (%)]")
        rates = FXRATES[fxType]
        for j in range(4):
            kz.initKey("fxRate" + str(j), rates[j])

        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.getNum("S&P 500", "fxRate0", ro, step=1.0, help=helpmsgSP500, callback=updateRates)

        with col2:
            kz.getNum("Corporate Bonds Baa", "fxRate1", ro, step=1.0, callback=updateRates)

        with col3:
            kz.getNum("10-y Treasury Notes", "fxRate2", ro, step=1.0, callback=updateRates)

        with col4:
            kz.getNum("Cash Assets/Inflation", "fxRate3", ro, step=1.0, help=helpCash, callback=updateRates)

    elif kz.getKey("rateType") == "varying":
        with col2:
            kz.getRadio("Select varying rates", varyingChoices, "varyingType", callback=updateRates)

    else:
        st.error("Logic error")

    if (kz.getKey("rateType") == "fixed" and "hist" in kz.getKey("fixedType")) or (
        kz.getKey("rateType") == "varying" and "hist" in kz.getKey("varyingType")
    ):

        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col3:
            maxValue = owb.TO if kz.getKey("varyingType") == "historical" else kz.getKey("yto") - 1
            st.number_input(
                "Starting year",
                min_value=owb.FROM,
                max_value=maxValue,
                value=kz.getKey("yfrm"),
                on_change=updateRates,
                args=["yfrm"],
                key=kz.genCaseKey("yfrm"),
            )

        with col4:
            ishistorical = kz.getKey("rateType") == "varying" and kz.getKey("varyingType") == "historical"
            st.number_input(
                "Ending year",
                max_value=owb.TO,
                min_value=kz.getKey("yfrm") + 1,
                value=kz.getKey("yto"),
                disabled=ishistorical,
                on_change=updateRates,
                args=["yto"],
                key=kz.genCaseKey("yto"),
            )

    if kz.getKey("rateType") == "varying":
        st.divider()
        st.write("#### :orange[Stochastic Parameters]")
        ro = kz.getKey("varyingType") != "stochastic"
        st.write("##### Means (%)")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initKey("mean0", 0)
            kz.getNum("S&P 500", "mean0", ro, step=1.0, help=helpmsgSP500, min_value=-9.0, callback=updateRates)

        with col2:
            kz.initKey("mean1", 0)
            kz.getNum("Corporate Bonds Baa", "mean1", ro, step=1.0, min_value=-9.0, callback=updateRates)

        with col3:
            kz.initKey("mean2", 0)
            kz.getNum("10-y Treasury Notes", "mean2", ro, step=1.0, min_value=-9.0, callback=updateRates)

        with col4:
            kz.initKey("mean3", 0)
            kz.getNum("Cash Assets/Inflation", "mean3", ro, step=1.0, min_value=-9.0, callback=updateRates)

        st.write("##### Volatility (%)")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initKey("stdev0", 0)
            kz.getNum("S&P 500", "stdev0", ro, step=1.0, callback=updateRates)

        with col2:
            kz.initKey("stdev1", 0)
            kz.getNum("Corporate Bonds Baa", "stdev1", ro, step=1.0, callback=updateRates)

        with col3:
            kz.initKey("stdev2", 0)
            kz.getNum("10-y Treasury Notes", "stdev2", ro, step=1.0, callback=updateRates)

        with col4:
            kz.initKey("stdev3", 0)
            kz.getNum("Cash Assets/Inflation", "stdev3", ro, step=1.0, callback=updateRates)

        st.write("##### Correlation matrix")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initKey("diag1", 1)
            kz.getNum("S&P 500", "diag1", True, format="%.2f", callback=None)

        with col2:
            kz.initKey("corr1", 0.0)
            kz.getNum("(1,2)", "corr1", ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initKey("diag2", 1.0)
            kz.getNum("Corporate Bonds Baa", "diag2", True, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=None)

        with col3:
            kz.initKey("corr2", 0.0)
            kz.getNum("(1,3)", "corr2", ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initKey("corr4", 0.0)
            kz.getNum("(2,3)", "corr4", ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initKey("diag3", 1.0)
            kz.getNum("10-y Treasury Notes", "diag3", True, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=None)

        with col4:
            kz.initKey("corr3", 0.0)
            kz.getNum("(1,4)", "corr3", ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initKey("corr5", 0.0)
            kz.getNum("(2,4)", "corr5", ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initKey("corr6", 0.0)
            kz.getNum("(3,4)", "corr6", ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initKey("diag4", 1.0)
            kz.getNum("Cash Assets/Inflation", "diag4", True, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=None)

    st.divider()
    if kz.getKey("rateType") == "varying":
        col1, col2 = st.columns(2, gap="medium")
        owb.showRatesCorrelations(col2)
    else:
        col1, col2 = st.columns([0.6, 0.4], gap="medium")

    owb.showRates(col1)

    # st.divider()
    st.write("#### :orange[Other Rates]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        kz.initKey("divRate", 1.8)
        helpmsg = "Average annual (qualified) dividend return rate on stock portfolio for income tax purposes."
        ret = kz.getNum("Dividend rate (%)", "divRate", max_value=100.0, format="%.2f", help=helpmsg, step=1.0)

    st.write("#####")
    st.write("#### :orange[Income taxes]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        kz.initKey("heirsTx", 30)
        helpmsg = "Marginal tax rate that heirs would have to pay on inherited tax-deferred balance."
        ret = kz.getNum("Heirs marginal tax rate (%)", "heirsTx", max_value=100.0, help=helpmsg, step=1.0)

    with col2:
        kz.initKey("yOBBBA", 2032)
        helpmsg = "Year at which the OBBBA tax rates are speculated to be expired and return to pre-TCJA rates."
        ret = kz.getIntNum("OBBBA expiration year", "yOBBBA", help=helpmsg)
