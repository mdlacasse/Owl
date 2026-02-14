"""
Fixed Income page for Owl retirement planner Streamlit UI.

This module provides the interface for entering fixed income sources
such as pensions and annuities.

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

import sskeys as kz
import case_progress as cp


def getIntInput(i, key, thing, defval=0, help=None, min_val=0, max_val=None, prompt=True):
    """
    Integer input widget. Config stores some values as float (e.g. pension_monthly_amounts)
    and ages use year+month (pAge_y, pAge_m) from _age_float_to_ym in config_to_ui.
    Coerce to int so Streamlit gets consistent types (avoids StreamlitMixedNumericTypesError).
    """
    nkey = key + str(i)
    kz.initCaseKey(nkey, defval)
    stored_value = kz.getCaseKey(nkey)
    # Clamp stored value to valid range if it's outside
    if stored_value is not None:
        stored_value = int(stored_value)
        if min_val is not None and stored_value < min_val:
            stored_value = int(min_val)
            kz.setCaseKey(nkey, stored_value)
        if max_val is not None and stored_value > max_val:
            stored_value = int(max_val)
            kz.setCaseKey(nkey, stored_value)
    else:
        stored_value = int(defval)
    min_val = int(min_val) if min_val is not None else None
    max_val = int(max_val) if max_val is not None else None
    if prompt:
        own = f"{kz.getCaseKey('iname' + str(i))}'s "
    else:
        own = ""
    return st.number_input(
        f"{own}{thing}", min_value=min_val, value=stored_value,
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
        if specialcase0:
            msg2 = ("Claiming age in years and months. "
                    "Minimum: 61 years 11 months (SSA rule for those born on 1st or 2nd). Maximum 70.")
        else:
            msg2 = "Claiming age in years and months. Minimum: 62, maximum: 70."
        getIntInput(0, "ssAmt", "**monthly** PIA amount (in today's \\$)", help=msg1)
        incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
        with incol1:
            kz.initCaseKey("ssAge_y0", 65)
            kz.initCaseKey("ssAge_m0", 0)
            m0 = kz.getCaseKey("ssAge_m0")
            maxyear = 70 if m0 == 0 else 69
            minyear = 61 if specialcase0 else 62
            ret = getIntInput(0, "ssAge_y", "claiming at age...", 67, msg2, min_val=minyear, max_val=maxyear)
        with incol2:
            maxmonth = 0 if ret == 70 else 11
            minmonth = 11 if (ret == 61 and specialcase0) else 0
            getIntInput(0, "ssAge_m", "...and month(s)", 0, msg2, min_val=minmonth, max_val=maxmonth, prompt=False)

    with col2:
        if kz.getCaseKey("status") == "married":
            dob1 = kz.getCaseKey("dob1")
            specialcase1 = dob1.endswith("01") or dob1.endswith("02")
            getIntInput(1, "ssAmt", "**monthly** PIA amount (in today's \\$)", help=msg1)
            if specialcase1:
                msg2_spouse = ("Claiming age in years and months. "
                               "Minimum: 61 years 11 months (SSA rule for those born on 1st or 2nd).")
            else:
                msg2_spouse = "Claiming age in years and months. Minimum: 62 years."
            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
            with incol1:
                kz.initCaseKey("ssAge_y1", 65)
                kz.initCaseKey("ssAge_m1", 0)
                m1 = kz.getCaseKey("ssAge_m1")
                maxyear = 70 if m1 == 0 else 69
                minyear = 61 if specialcase1 else 62
                ret = getIntInput(1, "ssAge_y", "claiming at age...", 67, msg2_spouse, min_val=minyear, max_val=maxyear)
            with incol2:
                maxmonth = 0 if ret == 70 else 11
                minmonth = 11 if (ret == 61 and specialcase1) else 0
                getIntInput(
                    1, "ssAge_m", "...and month(s)", 0, msg2_spouse,
                    min_val=minmonth, max_val=maxmonth, prompt=False
                )

    col1, col2 = st.columns([.67, .33], gap="large", vertical_alignment="top")
    with col1:
        with st.expander("*Instructions for determining your monthly Primary Insurance Amount (PIA)*"):
            st.markdown("""
The Primary Insurance Amount (PIA) is the monthly Social Security benefit you would receive if
you claim benefits at your full retirement age. It is calculated based on your lifetime
earnings, the past contributions made to the Social Security program, and future
contributions based on some basic assumptions.

The Social Security Administration (SSA) maintains a record of your earnings,
which you can access through the SSA [website](https://ssa.gov).
To view your personal earnings record, you must create an account and sign in.
Once logged in, use the ssa.tools link in this section to calculate your PIA using your earnings data.
This tool also allows you to refine the projections of future earnings
(such as expected salary and remaining years of work), resulting in a more accurate estimate of your PIA.
For ease of use, the link will securely pass the individual's DOB and nickname.

Owl is designed with a strong commitment to user privacy and does not collect or store any
personal information. The developer of ssa.tools follows the same philosophy:
all calculations are performed locally in your browser, and no data is transmitted
or saved. Since the links will open in a new browser tab,
simply note your calculated PIA and enter it back on this page.

Because the SSA updates its parameters annually and PIAs are expressed in today’s dollars,
these estimates are valid only for the current year.
As a result, this process should be repeated each year to maintain accurate estimates.
""")

            col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
            with col1:
                iname0 = kz.getCaseKey("iname0")
                st.markdown(f"""Click
[here](https://ssa.tools/calculator#integration=owlplanner.streamlit.app&dob={dob0}&name={iname0})
to estimate {iname0}'s PIA.""")
            if kz.getCaseKey("status") == "married":
                with col2:
                    iname1 = kz.getCaseKey("iname1")
                    st.markdown(f"""Click
[here](https://ssa.tools/calculator#integration=owlplanner.streamlit.app&dob={dob1}&name={iname1})
to estimate {iname1}'s PIA.""")

    st.divider()
    st.markdown("#### :orange[Pension]")
    msg_pension1 = "Monthly benefit received from pension."
    msg_pension2 = "Age at which pension benefits start. In years and months."
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        kz.initCaseKey("pAge_y0", 65)
        kz.initCaseKey("pAge_m0", 0)
        getIntInput(0, "pAmt", "**monthly** amount (in today's \\$)", help=msg_pension1)
        incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
        with incol1:
            getIntInput(0, "pAge_y", "starting at age...", 65, msg_pension2)
        with incol2:
            getIntInput(0, "pAge_m", "...and month(s)", 0, msg_pension2, max_val=11, prompt=False)
        getToggleInput(0, "pIdx", "Inflation adjusted")

    with col2:
        if kz.getCaseKey("status") == "married":
            kz.initCaseKey("pAge_y1", 65)
            kz.initCaseKey("pAge_m1", 0)
            getIntInput(1, "pAmt", "**monthly** amount (in today's \\$)", help=msg_pension1)
            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
            with incol1:
                getIntInput(1, "pAge_y", "starting at age...", 65, msg_pension2)
            with incol2:
                getIntInput(1, "pAge_m", "...and month(s)", 0, msg_pension2, max_val=11, prompt=False)
            getToggleInput(1, "pIdx", "Inflation adjusted")

    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar()
