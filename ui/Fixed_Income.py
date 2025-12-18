import streamlit as st

import sskeys as kz


def getIntInput(i, key, thing, defval=0, help=None, min_val=0, max_val=None, prompt=True):
    nkey = key + str(i)
    kz.initCaseKey(nkey, defval)
    if prompt:
        own = f"{kz.getCaseKey('iname' + str(i))}'s "
    else:
        own = ""
    return st.number_input(
        f"{own}{thing}", min_value=min_val, value=kz.getCaseKey(nkey),
        on_change=kz.setpull, help=help, args=[nkey], key=kz.genCaseKey(nkey),
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
    st.markdown("#### :orange[Social Security]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        dob0 = kz.getCaseKey("dob0")
        specialcase0 = dob0.endswith("01") or dob0.endswith("02")
        msg1 = "This is the **monthly** amount at Full Retirement Age (FRA)."
        msg2 = "Starting age of benefits in years and months."
        getIntInput(0, "ssAmt", "**monthly** PIA amount (in today's \\$)", help=msg1)
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
            getIntInput(1, "ssAmt", "**monthly** PIA amount (in today's \\$)", help=msg1)
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

    col1, col2 = st.columns([.67, .33], gap="large", vertical_alignment="top")
    with col1:
        with st.expander("Instructions for determining your monthly Primary Insurance Amount (PIA)"):
            st.markdown("""
The Primary Insurance Amount (PIA) is the monthly Social Security benefit you would receive if
you claim benefits at your full retirement age. It is calculated based on your lifetime
earnings and the contributions you have made to the Social Security program.

The Social Security Administration (SSA) maintains a record of your earnings,
which you can access through the SSA [website](ssa.gov).
To view your personal earnings record, you must create an account and sign in.
Once logged in, you can use the link to ssa.tools below to calculate your PIA using your earnings data.
This tool also allows you to include projections of future earnings
(such as expected salary and remaining years of work), resulting in a more accurate estimate of your PIA.

Owl is designed with a strong commitment to user privacy and does not collect or store any
personal information. The developer of ssa.tools follows the same philosophy:
all calculations are performed locally in your browser, and no data is transmitted
or saved. Since the links will open in a new browser tab,
simply note your calculated PIA and enter it back on this page.

Because the SSA updates its parameters annually and PIA values are expressed in today’s dollars,
PIA estimates are valid for the current year only.
As a result, this process should be repeated each year to maintain accurate estimates.
""")

            col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
            with col1:
                iname0 = kz.getCaseKey("iname0")
                st.markdown(f"""Click
[here](https://ssa.tools/calculator#integration=owlplanner.streamlit.app&dob={dob0}&useridx={iname0})
to estimate {iname0}'s PIA.""")
            if kz.getCaseKey("status") == "married":
                with col2:
                    iname1 = kz.getCaseKey("iname1")
                    st.markdown(f"""Click
[here](https://ssa.tools/calculator#integration=owlplanner.streamlit.app&dob={dob1}&useridx={iname1})
to estimate {iname1}'s PIA.""")

    st.divider()
    st.markdown("#### :orange[Pension]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        getIntInput(0, "pAmt", "**monthly** amount (in today's \\$)", help=msg1)
        incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
        with incol1:
            getIntInput(0, "pAge_y", "starting at age...", 65, msg2)
        with incol2:
            getIntInput(0, "pAge_m", "...and month(s)", 0, msg2, max_val=11, prompt=False)
        getToggleInput(0, "pIdx", "Inflafion adjusted")

    with col2:
        if kz.getCaseKey("status") == "married":
            getIntInput(1, "pAmt", "**monthly** amount (in today's \\$)", help=msg1)
            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
            with incol1:
                getIntInput(1, "pAge", "starting at age...", 65, msg2)
            with incol2:
                getIntInput(1, "pAge_m", "...and month(s)", 0, msg2, max_val=11, prompt=False)
            getToggleInput(1, "pIdx", "Inflafion adjusted")
