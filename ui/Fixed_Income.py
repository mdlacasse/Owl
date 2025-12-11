import streamlit as st

import sskeys as kz


def getIntInput(i, key, thing, defval=0, helpmsg=None, min_val=0, max_val=None, prompt=True):
    nkey = key + str(i)
    kz.initCaseKey(nkey, defval)
    if prompt:
        own = f"{kz.getCaseKey('iname' + str(i))}'s "
    else:
        own = ""
    return st.number_input(
        f"{own}{thing}", min_value=min_val, value=kz.getCaseKey(nkey),
        on_change=kz.setpull, help=helpmsg, args=[nkey], key=kz.genCaseKey(nkey),
        max_value=max_val,
    )


def getFloatInput(i, key, thing, defval=0.0):
    nkey = key + str(i)
    kz.initCaseKey(nkey, defval)
    inamex = kz.getCaseKey("iname" + str(i))
    return st.number_input(
        f"{inamex}'s {thing}",
        min_value=0.0,
        help=kz.help1000,
        value=float(kz.getCaseKey(nkey)),
        format="%.1f",
        step=10.0,
        on_change=kz.setpull,
        args=[nkey],
        key=kz.genCaseKey(nkey),
    )


def getToggleInput(i, key, thing):
    nkey = key + str(i)
    kz.initCaseKey(nkey, False)
    defval = kz.getCaseKey(nkey)
    st.toggle(thing, on_change=kz.setpull, value=defval, args=[nkey], key=kz.genCaseKey(nkey))


ret = kz.titleBar(":material/currency_exchange: Fixed Income")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    st.write("#### :orange[Social Security]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        dob0 = kz.getCaseKey("dob0")
        specialcase0 = dob0.endswith("01") or dob0.endswith("02")
        msg1 = "This is the **monthly** amount at Full Retirement Age (FRA)."
        msg2 = "Starting age of benefits in years and months."
        getIntInput(0, "ssAmt", "**monthly** PIA amount (in today's \\$)", helpmsg=msg1)
        iname0 = kz.getCaseKey("iname0")
        st.markdown(f"""Use this
[tool](https://ssa.tools/calculator#integration=owlplanner.streamlit.app&dob={dob0}&useridx={iname0})
to get {iname0}'s PIA.""")
        incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
        with incol1:
            kz.initCaseKey("ssAge_m0", 0)
            m0 = kz.getCaseKey("ssAge_m0")
            maxyear = 70 if m0 == 0 else 69
            minyear = 62 if m0 > 0 or specialcase0 else 63
            ret = getIntInput(0, "ssAge_y", "claiming at age...", 67, msg2, min_val=minyear, max_val=maxyear)
        with incol2:
            maxmonth = 0 if ret == 70 else 11
            minmonth = 1 if ret == 62 else 0
            getIntInput(0, "ssAge_m", "...and month(s)", 0, msg2, min_val=minmonth, max_val=maxmonth, prompt=False)

    with col2:
        if kz.getCaseKey("status") == "married":
            dob1 = kz.getCaseKey("dob1")
            specialcase1 = dob1.endswith("01") or dob1.endswith("02")
            getIntInput(1, "ssAmt", "**monthly** PIA amount (in today's \\$)", helpmsg=msg1)
            iname1 = kz.getCaseKey("iname1")
            st.markdown(f"""Use this
[tool](https://ssa.tools/calculator#integration=owlplanner.streamlit.app&dob={dob1}&useridx={iname1})
to get {iname1}'s PIA.""")
            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
            with incol1:
                kz.initCaseKey("ssAge_m1", 0)
                m1 = kz.getCaseKey("ssAge_m1")
                maxyear = 70 if m1 == 0 else 69
                minyear = 62 if m1 > 0 or specialcase1 else 63
                ret = getIntInput(1, "ssAge_y", "claiming at age...", 67, msg2, min_val=minyear, max_val=maxyear)
            with incol2:
                maxmonth = 0 if ret == 70 else 11
                minmonth = 1 if ret == 62 else 0
                getIntInput(1, "ssAge_m", "...and month(s)", 0, msg2, min_val=minmonth, max_val=maxmonth, prompt=False)

    st.divider()
    st.write("#### :orange[Pension]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        getIntInput(0, "pAmt", "**monthly** amount (in today's \\$)", helpmsg=msg1)
        incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
        with incol1:
            getIntInput(0, "pAge_y", "pension starting at age...", 65, msg2)
        with incol2:
            getIntInput(0, "pAge_m", "...and month(s)", 0, msg2, max_val=11, prompt=False)
        getToggleInput(0, "pIdx", "Inflafion adjusted")

    with col2:
        if kz.getCaseKey("status") == "married":
            getIntInput(1, "pAmt", "**monthly** amount (in today's \\$)", helpmsg=msg1)
            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
            with incol1:
                getIntInput(1, "pAge", "pension starting at age...", 65, msg2)
            with incol2:
                getIntInput(1, "pAge_m", "...and month(s)", 0, msg2, max_val=11, prompt=False)
            getToggleInput(1, "pIdx", "Inflafion adjusted")
