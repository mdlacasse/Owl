import streamlit as st

import sskeys as kz
import owlbridge as owb


def getPercentInput(i, j, keybase, text, defval=0):
    nkey = f"{keybase}{j}_{i}"
    kz.initKey(nkey, defval)
    st.number_input(
        text,
        min_value=0,
        step=1,
        max_value=100,
        value=kz.getKey(nkey),
        on_change=kz.setpull,
        args=[nkey],
        key="_" + nkey,
    )


ACC = ["taxable", "tax-deferred", "tax-free"]
ASSET = ["S&P 500", "Corp Bonds Baa", "T-Notes", "Cash Assets"]
DEFALLOC = [60, 20, 10, 10]


def getIndividualAllocs(i, title, deco):
    mydeco = "j3_" + deco
    iname = kz.getKey("iname" + str(i))
    st.write(f"###### {iname}'s {title} allocation for all accounts (%)")
    cols = st.columns(4, gap="large", vertical_alignment="top")
    for k1 in range(4):
        with cols[k1]:
            getPercentInput(i, k1, mydeco, ASSET[k1], DEFALLOC[k1])
    checkIndividualAllocs(i, mydeco)


def getAccountAllocs(i, j, title, deco):
    iname = kz.getKey("iname" + str(i))
    mydeco = f"j{j}_" + deco
    st.write(f"###### {iname}'s {title} allocation for {ACC[j]} account (%)")
    cols = st.columns(4, gap="large", vertical_alignment="top")
    for k1 in range(4):
        with cols[k1]:
            getPercentInput(i, k1, mydeco, ASSET[k1], DEFALLOC[k1])
    checkAccountAllocs(i, mydeco)


def checkAccountAllocs(i, deco):
    tot = 0
    for k1 in range(4):
        tot += int(kz.getKey(f"{deco}{k1}_{i}"))
    if abs(100 - tot) > 0:
        st.error("Percentages must add to 100%.")
        return False
    return True


def checkIndividualAllocs(i, deco):
    tot = 0
    for k1 in range(4):
        tot += int(kz.getKey(f"{deco}{k1}_{i}"))
    if abs(100 - tot) > 0:
        st.error("Percentages must add to 100%.")
        return False
    return True


def checkAllAllocs():
    if kz.getKey("allocType") == "individual":
        decos = ["j3_init%", "j3_fin%"]
    else:
        decos = ["j0_init%", "j0_fin%", "j1_init%", "j1_fin%", "j2_init%", "j2_fin%"]
    Ni = 1
    if kz.getKey("status") == "married":
        Ni += 1
    result = True
    for i in range(Ni):
        for deco in decos:
            result = result and checkIndividualAllocs(i, deco)
    return result


ret = kz.titleBar("allocs")
kz.caseHeader("Asset Allocation")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    choices = ["individual", "account"]
    key = "allocType"
    kz.initKey(key, choices[0])
    helpmsg = "Allocation ratios can be equal across all accounts or not."
    ret = kz.getRadio("Asset allocation method", choices, key, help=helpmsg)
    if ret == "individual":
        st.divider()
        getIndividualAllocs(0, "initial", "init%")
        getIndividualAllocs(0, "final", "fin%")

        if kz.getKey("status") == "married":
            st.divider()
            getIndividualAllocs(1, "initial", "init%")
            getIndividualAllocs(1, "final", "fin%")
    else:
        for j in range(3):
            st.divider()
            getAccountAllocs(0, j, "initial", "init%")
            getAccountAllocs(0, j, "final", "fin%")
        if kz.getKey("status") == "married":
            st.markdown("###")
            for j in range(3):
                st.divider()
                getAccountAllocs(1, j, "initial", "init%")
                getAccountAllocs(1, j, "final", "fin%")

    st.divider()
    choices = ["linear", "s-curve"]
    key = "interpMethod"
    kz.initKey(key, choices[0])
    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        kz.getRadio("Gliding interpolation method", choices, key)

    if kz.getKey(key) == choices[1]:
        with col2:
            key = "interpCenter"
            kz.initKey("interpCenter", 15.0)
            helpmsg = "Time in future years to the transition's inflection point."
            ret = kz.getNum("Center (in years from now)", key, step=1.0, help=helpmsg, max_value=30.0, format="%.0f")
        with col3:
            key = "interpWidth"
            kz.initKey("interpWidth", 5.0)
            helpmsg = "Half width in years over which the transition happens."
            ret = kz.getNum(
                "Width (in +/- years from center)", key, step=1.0, help=helpmsg, max_value=15.0, format="%.0f"
            )

    if checkAllAllocs():
        if kz.getKey("caseStatus") != "solved":
            owb.setInterpolationMethod()
            owb.setAllocationRatios()
        owb.showAllocations()
