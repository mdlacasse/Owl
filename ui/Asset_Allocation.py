import streamlit as st

import sskeys as kz
import owlbridge as owb


def getPercentInput(i, j, keybase, text, defval=0):
    nkey = f"{keybase}{j}_{i}"
    kz.initCaseKey(nkey, defval)
    st.number_input(
        text,
        min_value=0,
        step=1,
        max_value=100,
        value=kz.getCaseKey(nkey),
        on_change=kz.setpull,
        args=[nkey],
        key=kz.genCaseKey(nkey),
    )


ACC = ["taxable", "tax-deferred", "tax-free"]
ASSET = ["S&P 500", "Corp Bonds Baa", "T-Notes", "Cash Assets"]
DEFALLOC = [60, 20, 10, 10]


def getIndividualAllocs(i, iname, title, deco):
    mydeco = "j3_" + deco
    st.markdown(f"###### {iname}'s {title} allocation for all accounts (%)")
    cols = st.columns(4, gap="large", vertical_alignment="top")
    for k1 in range(4):
        with cols[k1]:
            getPercentInput(i, k1, mydeco, ASSET[k1], DEFALLOC[k1])
    checkIndividualAllocs(i, mydeco)


def getAccountAllocs(i, iname, j, title, deco):
    mydeco = f"j{j}_" + deco
    st.markdown(f"###### {iname}'s {title} allocation for {ACC[j]} account (%)")
    cols = st.columns(4, gap="large", vertical_alignment="top")
    for k1 in range(4):
        with cols[k1]:
            getPercentInput(i, k1, mydeco, ASSET[k1], DEFALLOC[k1])
    checkAccountAllocs(i, mydeco)


def checkAccountAllocs(i, deco):
    tot = 0
    for k1 in range(4):
        tot += int(kz.getCaseKey(f"{deco}{k1}_{i}"))
    if abs(100 - tot) > 0:
        st.error("Percentages must add to 100%.")
        return False
    return True


def checkIndividualAllocs(i, deco):
    tot = 0
    for k1 in range(4):
        tot += int(kz.getCaseKey(f"{deco}{k1}_{i}"))
    if abs(100 - tot) > 0:
        st.error("Percentages must add to 100%.")
        return False
    return True


def checkAllAllocs():
    if kz.getCaseKey("allocType") == "individual":
        decos = ["j3_init%", "j3_fin%"]
    else:
        decos = ["j0_init%", "j0_fin%", "j1_init%", "j1_fin%", "j2_init%", "j2_fin%"]
    Ni = 1
    if kz.getCaseKey("status") == "married":
        Ni += 1
    result = True
    for i in range(Ni):
        for deco in decos:
            result = result and checkIndividualAllocs(i, deco)
    return result


ret = kz.titleBar(":material/percent: Asset Allocation")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    st.markdown("#### :orange[Type of Allocation]")
    choices = ["individual", "account"]
    key = "allocType"
    kz.initCaseKey(key, choices[0])
    helpmsg = "Allocation ratios can be equal across all accounts or not."
    ret = kz.getRadio("Asset allocation method", choices, key, help=helpmsg)
    st.divider()
    if ret == "individual":
        iname0 = kz.getCaseKey("iname0")
        st.markdown(f"#### :orange[Individual Asset Allocation ({iname0})]")
        getIndividualAllocs(0, iname0, "initial", "init%")
        getIndividualAllocs(0, iname0, "final", "fin%")
        st.divider()

        if kz.getCaseKey("status") == "married":
            iname1 = kz.getCaseKey("iname1")
            st.markdown(f"#### :orange[Individual Asset Allocation ({iname1})]")
            getIndividualAllocs(1, iname1, "initial", "init%")
            getIndividualAllocs(1, iname1, "final", "fin%")
            st.divider()
    else:
        iname0 = kz.getCaseKey("iname0")
        st.markdown(f"#### :orange[Account Asset Allocation ({iname0})]")
        for j in range(3):
            getAccountAllocs(0, iname0, j, "initial", "init%")
            getAccountAllocs(0, iname0, j, "final", "fin%")
            st.divider()
        if kz.getCaseKey("status") == "married":
            iname1 = kz.getCaseKey("iname1")
            st.markdown(f"#### :orange[Account Asset Allocation ({iname1})]")
            for j in range(3):
                getAccountAllocs(1, iname1, j, "initial", "init%")
                getAccountAllocs(1, iname1, j, "final", "fin%")
                st.divider()

    st.markdown("#### :orange[Interpolation]")
    choices = ["linear", "s-curve"]
    key = "interpMethod"
    kz.initCaseKey(key, choices[0])
    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        kz.getRadio("Gliding interpolation method", choices, key)

    if kz.getCaseKey(key) == choices[1]:
        with col2:
            key = "interpCenter"
            kz.initCaseKey("interpCenter", 15.0)
            helpmsg = "Time in future years to the transition's inflection point."
            ret = kz.getNum("Center (in years from now)", key, step=1.0, help=helpmsg, max_value=30.0, format="%.0f")
        with col3:
            key = "interpWidth"
            kz.initCaseKey("interpWidth", 5.0)
            helpmsg = "Half width in years over which the transition happens."
            ret = kz.getNum(
                "Width (in +/- years from center)", key, step=1.0, help=helpmsg, max_value=15.0, format="%.0f"
            )

    if checkAllAllocs():
        if kz.getCaseKey("caseStatus") != "solved":
            owb.setInterpolationMethod()
            owb.setAllocationRatios()
        owb.showAllocations()
