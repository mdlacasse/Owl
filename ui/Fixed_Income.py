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
from datetime import date

import sskeys as kz
import owlbridge as owb
import case_progress as cp


def getIntInput(i, key, thing, defval=0, help=None, min_val=0, max_val=None, prompt=True, disabled=False):
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
        max_value=max_val, disabled=disabled,
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
    st.info("A case must first be created before running this page.")
else:
    st.markdown("#### :orange[Social Security]")
    _ss_mode = kz.getCaseKey("ssAgesMode") or "none"
    _iname0 = kz.getCaseKey("iname0")
    _iname1 = kz.getCaseKey("iname1")
    ss_age0_disabled = _ss_mode in ("optimize", "both") or _ss_mode == _iname0
    ss_age1_disabled = _ss_mode in ("optimize", "both") or _ss_mode == _iname1
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
        if ss_age0_disabled:
            msg2 = msg2 + " (Set by optimizer — shown as last solved result.)"
        getIntInput(0, "ssAmt", "**monthly** PIA amount (in today's \\$)", help=msg1)
        incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
        with incol1:
            kz.initCaseKey("ssAge_y0", 67)
            kz.initCaseKey("ssAge_m0", 0)
            m0 = kz.getCaseKey("ssAge_m0")
            maxyear = 70 if m0 == 0 else 69
            minyear = 61 if specialcase0 else 62
            ret = getIntInput(0, "ssAge_y", "claiming at age...", 67, msg2,
                              min_val=minyear, max_val=maxyear, disabled=ss_age0_disabled)
        with incol2:
            maxmonth = 0 if ret == 70 else 11
            minmonth = 11 if (ret == 61 and specialcase0) else 0
            getIntInput(0, "ssAge_m", "...and month(s)", 0, msg2,
                        min_val=minmonth, max_val=maxmonth, prompt=False, disabled=ss_age0_disabled)

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
            if ss_age1_disabled:
                msg2_spouse = msg2_spouse + " (Set by optimizer — shown as last solved result.)"
            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
            with incol1:
                kz.initCaseKey("ssAge_y1", 67)
                kz.initCaseKey("ssAge_m1", 0)
                m1 = kz.getCaseKey("ssAge_m1")
                maxyear = 70 if m1 == 0 else 69
                minyear = 61 if specialcase1 else 62
                ret = getIntInput(1, "ssAge_y", "claiming at age...", 67, msg2_spouse,
                                  min_val=minyear, max_val=maxyear, disabled=ss_age1_disabled)
            with incol2:
                maxmonth = 0 if ret == 70 else 11
                minmonth = 11 if (ret == 61 and specialcase1) else 0
                getIntInput(
                    1, "ssAge_m", "...and month(s)", 0, msg2_spouse,
                    min_val=minmonth, max_val=maxmonth, prompt=False, disabled=ss_age1_disabled
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

    col1, col2 = st.columns([.67, .33], gap="large", vertical_alignment="top")
    with col1:
        st.markdown("")
        with st.expander("*Advanced options*"):
            st.markdown("#### :orange[Social Security benefit reduction]")
            help_trim = (
                "Reduce Social Security benefits by this percentage starting in the given year. "
                "Use to model trust fund shortfall scenarios (e.g. 23% cut from 2035). "
                "0 = no reduction."
            )
            help_trim_year = "Calendar year when the reduction begins."
            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
            with incol1:
                kz.initCaseKey("ssTrimPct", 0)
                kz.getIntNum(
                    "Reduction (%)",
                    "ssTrimPct",
                    min_value=0,
                    max_value=100,
                    step=1,
                    help=help_trim,
                )
            with incol2:
                thisyear = date.today().year
                kz.initCaseKey("ssTrimYear", 2033)
                kz.getIntNum(
                    "Starting year",
                    "ssTrimYear",
                    disabled=(kz.getCaseKey("ssTrimPct") == 0),
                    min_value=thisyear,
                    max_value=thisyear + 50,
                    step=1,
                    help=help_trim_year,
                )

    st.divider()
    st.markdown("#### :orange[Pension]")
    msg_pension1 = "Monthly benefit received from pension."
    msg_pension2 = "Age at which pension benefits start. In years and months."
    msg_surv = ("If you elected a joint-and-survivor (J&S) option, the surviving spouse receives "
                "this percentage of your pension after your death. 0 = single-life annuity.")
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

        incol1, incol2 = st.columns(2, gap="large", vertical_alignment="bottom")
        with incol1:
            getToggleInput(0, "pIdx", "Inflation adjusted")
        with incol2:
            if kz.getCaseKey("status") == "married":
                kz.initCaseKey("pSurv0", 0)
                kz.getIntNum("Survivor (%)", "pSurv0", min_value=0, max_value=100, step=5, help=msg_surv)

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

            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="bottom")
            with incol1:
                getToggleInput(1, "pIdx", "Inflation adjusted")
            with incol2:
                kz.initCaseKey("pSurv1", 0)
                kz.getIntNum("Survivor (%)", "pSurv1", min_value=0, max_value=100, step=5, help=msg_surv)

    st.divider()
    st.markdown("#### :orange[Single Premium Immediate Annuity (SPIA)]")
    st.caption(
        "A qualified SPIA converts a tax-deferred (IRA) lump sum into guaranteed lifetime income. "
        "The premium is a non-taxable IRA rollover; all payments are 100% ordinary income."
    )

    is_married = kz.getCaseKey("status") == "married"
    iname0 = kz.getCaseKey("iname0") or "Person 1"
    iname1 = kz.getCaseKey("iname1") or "Person 2"
    plan_obj = kz.getCaseKey("plan")
    thisyear = date.today().year
    plan_end = int(plan_obj.year_n[-1]) if plan_obj is not None else thisyear + 50

    spiadf = owb.conditionSpiaDF(kz.getCaseKey("spiaDF"), is_married)

    annuitant_options = [iname0, iname1] if is_married else [iname0]
    col_config = {
        "Annuitant": st.column_config.SelectboxColumn(
            "Annuitant", options=annuitant_options, required=True,
        ),
        "Buy year": st.column_config.NumberColumn(
            "Buy year", min_value=thisyear - 50, max_value=plan_end, step=1, format="%d", required=True,
            help="Calendar year of purchase. May be in the past for an already-purchased SPIA.",
        ),
        "Premium ($k)": st.column_config.NumberColumn(
            "Premium ($k)", min_value=0.0, step=10.0, format="%.1f", required=True,
            help="Lump-sum IRA rollover amount in thousands of dollars.",
        ),
        "Monthly ($)": st.column_config.NumberColumn(
            "Monthly ($)", min_value=0, step=50, format="%d", required=True,
            help="Monthly benefit in nominal dollars at the time of purchase.",
        ),
        "CPI-linked": st.column_config.CheckboxColumn(
            "CPI-linked",
            help="Check if payments are inflation-adjusted. Most SPIAs pay a fixed nominal amount.",
        ),
    }
    if is_married:
        col_config["Survivor (%)"] = st.column_config.NumberColumn(
            "Survivor (%)", min_value=0, max_value=100, step=1, format="%d",
            help="Percentage of benefit paid to surviving spouse. 0 = single-life annuity.",
        )

    edited = st.data_editor(
        spiadf,
        column_config=col_config,
        num_rows="dynamic",
        width="content",
        key=kz.genCaseKey("spia_editor"),
        hide_index=True,
    )

    if not spiadf.equals(edited):
        kz.setCaseKey("spiaDF", owb.conditionSpiaDF(edited, is_married))
        st.rerun()

    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar()
