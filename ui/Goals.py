"""
Goals page for Owl retirement planner Streamlit UI.

This module provides the interface for setting the optimization objective
(spending vs. bequest), safety net constraints, and spending profile (flat or smile).

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
import owlbridge as owb
import case_progress as cp


profileChoices = ["flat", "smile"]
kz.initCaseKey("spendingProfile", profileChoices[1])
kz.initCaseKey("survivor", 60)
kz.initCaseKey("smileDip", 15)
kz.initCaseKey("smileIncrease", 12)
kz.initCaseKey("smileDelay", 0)


def initProfile():
    owb.setProfile(None)


ret = kz.titleBar(":material/target: Goals")

if ret is None or kz.caseHasNoPlan():
    st.info("A case must first be created before running this page.")
else:
    kz.runOncePerCase(initProfile)

    st.markdown("#### :orange[Objective]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        choices = ["Net spending", "Bequest"]
        helpmsg = "Value is in today's \\$k."
        kz.initCaseKey("objective", choices[0])
        helpmsg = "Choose one quantity to maximize; the other is then treated as a constraint."
        ret = kz.getRadio("Maximize", choices, "objective", help=helpmsg)

    with col2:
        if kz.getCaseKey("objective") == "Net spending":
            kz.initCaseKey("bequest", 0)
            helpmsg_bequest = ("Desired bequest from savings accounts only (in today's \\$k). "
                               "Fixed assets liquidated at the end of the plan are added separately.")
            bequest = kz.getNum("Desired bequest from savings accounts (\\$k)", "bequest",
                                help=helpmsg_bequest)

            # Get fixed assets bequest value in today's dollars to inform the user
            fixed_assets_bequest = owb.getFixedAssetsBequestValue(in_todays_dollars=True)
            fixed_assets_bequest_k = fixed_assets_bequest / 1000.0

            if fixed_assets_bequest_k > 0:
                st.info(f"Fixed assets contribute an additional"
                        f" \\${fixed_assets_bequest_k:,.0f}k to bequest (in today's \\$).")

        else:
            kz.initCaseKey("netSpending", 0)
            helpmsg_spending = "Desired annual net spending in today's \\$k (the constraint when maximizing bequest)."
            ret = kz.getNum("Desired annual net spending (\\$k)", "netSpending", help=helpmsg_spending)

    st.divider()
    st.markdown("#### :orange[Safety Net]")
    helpmsg = ("Maintain a minimum inflation-adjusted taxable balance (today’s \\$k)"
               " from year 2 through life expectancy. This should ideally be less than the initial balance.")
    ni = 2 if kz.getCaseKey("status") == "married" else 1
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        kz.initCaseKey("minTaxableBalance0", 0)
        iname0 = kz.getCaseKey("iname0")
        net0 = kz.getNum(f"Minimum taxable balance for {iname0} (\\$k)", "minTaxableBalance0",
                         min_value=0., help=helpmsg)
    with col2:
        net1 = 0
        if ni == 2:
            kz.initCaseKey("minTaxableBalance1", 0)
            iname1 = kz.getCaseKey("iname1")
            net1 = kz.getNum(f"Minimum taxable balance for {iname1} (\\$k)", "minTaxableBalance1",
                             min_value=0., help=helpmsg)

    if kz.getCaseKey("objective") == "Net spending" and (net0 + net1) > bequest:
        st.caption(":warning: When maximizing spending with a bequest target, the desired bequest should be at least "
                   "as large as the survivor's safety net (in today's \\$), otherwise optimization may be infeasible.")

    txbl0 = kz.getCaseKey("txbl0") or 0
    if txbl0 > 0 and net0 > 0.60 * txbl0:
        st.caption(f":warning: {iname0}'s minimum taxable balance (\\${net0:.0f}k) exceeds 60% of their"
                   f" initial taxable balance (\\${txbl0:.0f}k)."
                   f" The problem may become infeasible during market downturns.")
    if ni == 2:
        txbl1 = kz.getCaseKey("txbl1") or 0
        if txbl1 > 0 and net1 > 0.60 * txbl1:
            st.caption(f":warning: {iname1}'s minimum taxable balance (\\${net1:.0f}k) exceeds 60% of their"
                       f" initial taxable balance (\\${txbl1:.0f}k)."
                       f" The problem may become infeasible during market downturns.")

    st.divider()
    st.markdown("#### :orange[Spending Profile]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        helpmsg = "Spending can be constant for the duration of the plan or be adjusted for lifestyle."
        ret = kz.getRadio("Type of profile", profileChoices, "spendingProfile", help=helpmsg, callback=owb.setProfile)
        if kz.getCaseKey("spendingProfile") == "smile":
            helpmsg = "Time in year before spending starts decreasing."
            ret = kz.getIntNum("Smile delay (in years from now)", "smileDelay", max_value=30,
                               help=helpmsg, callback=owb.setProfile)
    with col2:
        kz.initCaseKey("spendingSlack", 0)
        helpmsg = "Percentage allowed to deviate from spending profile."
        ret = kz.getIntNum("Profile slack (%)", "spendingSlack", max_value=50, help=helpmsg)
        if kz.getCaseKey("spendingProfile") == "smile":
            helpmsg = "Percentage to decrease for the slow-go years."
            ret = kz.getIntNum("Smile dip (%)", "smileDip", max_value=100, help=helpmsg,
                               callback=owb.setProfile)
    with col3:
        if kz.getCaseKey("status") == "married":
            helpmsg = "Percentage of spending required for the surviving spouse."
            ret = kz.getIntNum("Survivor's spending (%)", "survivor", max_value=100,
                               help=helpmsg, callback=owb.setProfile)
        if kz.getCaseKey("spendingProfile") == "smile":
            helpmsg = "Percentage to increase (or decrease) over time period."
            ret = kz.getIntNum("Smile increase (%)", "smileIncrease",
                               min_value=-100, max_value=100, help=helpmsg, callback=owb.setProfile)

    st.divider()
    col1, col2 = st.columns([0.6, 0.4], gap="small")
    with col1:
        owb.showProfile(col1)

    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar(divider=False)
