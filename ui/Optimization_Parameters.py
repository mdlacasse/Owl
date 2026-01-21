"""
Optimization Parameters page for Owl retirement planner Streamlit UI.

This module provides the interface for setting optimization parameters
including spending profiles, Medicare options, and other optimization settings.

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


profileChoices = ["flat", "smile"]
kz.initCaseKey("spendingProfile", profileChoices[1])
kz.initCaseKey("survivor", 60)
kz.initCaseKey("smileDip", 15)
kz.initCaseKey("smileIncrease", 12)
kz.initCaseKey("smileDelay", 0)
kz.initCaseKey("computeMedicare", True)
kz.initCaseKey("optimizeMedicare", False)
kz.initCaseKey("withSCLoop", True)


def initProfile():
    owb.setProfile(None)


ret = kz.titleBar(":material/tune: Optimization Parameters")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    kz.runOncePerCase(initProfile)

    st.markdown("#### :orange[Objective]")
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        choices = ["Net spending", "Bequest"]
        helpmsg = "Value is in today's \\$k."
        kz.initCaseKey("objective", choices[0])
        helpmsg = "Pick one value to optimize. By choosing one of the two, the other becomes a constraint."
        ret = kz.getRadio("Maximize", choices, "objective", help=helpmsg)

    with col2:
        if kz.getCaseKey("objective") == "Net spending":
            kz.initCaseKey("bequest", 0)
            helpmsg_bequest = ("Desired bequest from savings accounts only (in today's \\$k). "
                               "Fixed assets liquidated at end of plan are added separately.")
            ret = kz.getNum("Desired bequest from savings accounts (\\$k)", "bequest",
                            help=helpmsg_bequest)

            # Get fixed assets bequest value in today's dollars to inform the user
            fixed_assets_bequest = owb.getFixedAssetsBequestValue(in_todays_dollars=True)
            fixed_assets_bequest_k = fixed_assets_bequest / 1000.0

            if fixed_assets_bequest_k > 0:
                st.info(f"Fixed assets contribute an additional"
                        f" \\${fixed_assets_bequest_k:,.0f}k to bequest (in today's \\$).")

        else:
            kz.initCaseKey("netSpending", 0)
            ret = kz.getNum("Desired annual net spending (\\$k)", "netSpending", help=helpmsg)

    st.divider()
    st.markdown("#### :orange[Roth Conversions]")
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        iname0 = kz.getCaseKey("iname0")
        helpmsg = "Value is in nominal \\$k."
        kz.initCaseKey("readRothX", False)
        fromFile = kz.getCaseKey("readRothX")
        kz.initCaseKey("maxRothConversion", 50)
        ret = kz.getNum("Maximum annual Roth conversion (\\$k)", "maxRothConversion",
                        disabled=fromFile, help=helpmsg)
        helpmsg = "Use the Roth conversion values in the *Wages and Contributions* file to override"
        ret = kz.getToggle("Convert as in Wages and Contributions tables", "readRothX", help=helpmsg)
        # kz.initCaseKey("oppCostX", 0.)
        # helpmsg = "Estimated opportunity cost for paying estimated tax on Roth conversions."
        # ret = kz.getNum("Opportunity cost for conversion (%)", "oppCostX", step=0.01, format="%.2f",
        #                min_value=0., max_value=5., help=helpmsg)

    with col2:
        helpmsg = "Do not perform Roth conversions before that year."
        thisyear = date.today().year
        kz.initCaseKey("startRothConversions", thisyear)
        ret = kz.getIntNum("Year to start considering Roth conversions", "startRothConversions",
                           min_value=thisyear, disabled=fromFile, help=helpmsg)
        if kz.getCaseKey("status") == "married":
            iname1 = kz.getCaseKey("iname1")
            choices = ["None", iname0, iname1]
            kz.initCaseKey("noRothConversions", choices[0])
            helpmsg = "`None` means no exclusion. To exclude both spouses, set `Maximum Roth conversion` to 0."
            ret = kz.getRadio("Exclude Roth conversions for...", choices, "noRothConversions", help=helpmsg)

    st.divider()
    st.markdown("#### :orange[Medicare]")
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        kz.initCaseKey("computeMedicare", True)
        helpmsg = "Compute Medicare and IRMAA premiums"
        medion = kz.getToggle("Medicare and IRMAA calculations", "computeMedicare", help=helpmsg)
        if medion and not kz.getCaseKey("withSCLoop"):
            st.markdown(":material/warning: Medicare on while self-consistent loop is off.")
    with col2:
        if kz.getCaseKey("computeMedicare"):
            helpmsg = "MAGI in nominal $k for current and previous years."
            years = owb.backYearsMAGI()
            for ii in range(2):
                kz.initCaseKey("MAGI" + str(ii), 0)
                if years[ii] > 0:
                    ret = kz.getNum(f"MAGI for year {years[ii]} ($k)", "MAGI" + str(ii), help=helpmsg)

    st.divider()
    with st.expander("*Advanced Options*"):
        st.markdown("#### :orange[Calculations]")
        col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
        with col1:
            helpmsg = ("Option to use a self-consistent loop to adjust additional values such as the net"
                       " investment income tax (NIIT), and capital gain tax rates."
                       "  When Medicare is selected, this will also compute Medicare and IRMAA.")
            ret = kz.getToggle("Self-consistent loop calculations", "withSCLoop", help=helpmsg)
            helpmsg = ("Option to optimize Medicare using binary variables."
                       "  Use with caution as some cases do not converge without adjusting additional parameters.")
            medioff = not medion
            ret = kz.getToggle("Optimize Medicare (expert)", "optimizeMedicare", help=helpmsg, disabled=medioff)
        with col2:
            kz.initCaseKey("xorSurplus", True)
            helpmsg = ("Enable mutually exclusive constraints between surplus deposits"
                       " and withdrawals from taxable accounts")
            ret = kz.getToggle("XOR constraints on surplus deposits and withdrawals from taxable accounts",
                               "xorSurplus", help=helpmsg)

            kz.initCaseKey("xorRoth", True)
            helpmsg = ("Enable mutually exclusive constraints between"
                       " Roth conversions and withdrawals from tax-free accounts.")
            ret = kz.getToggle("XOR constraints on Roth conversions and tax-free withdrawals",
                               "xorRoth", help=helpmsg)

        st.divider()
        st.markdown("#### :orange[Solver]")
        choices = ["HiGHS", "PuLP/CBC", "PuLP/HiGHS"]
        kz.initCaseKey("solver", choices[0])
        kz.initCaseKey("xtraOptions", "")

        if owb.hasMOSEK():
            choices += ["MOSEK"]
        elif kz.getCaseKey("solver") == "MOSEK":
            kz.setCaseKey("solver", choices[0])

        col1, col2 = st.columns([1, 1], gap="large", vertical_alignment="top")
        with col1:
            helpmsg = "Select different solvers for comparison purposes. Use HiGHS for best performance."
            ret = kz.getRadio("Linear programming solver", choices, "solver", help=helpmsg)
        with col2:
            helpmsg = ("Additional solver options as a dictionary (e.g., '{\"key1\": \"value1\", \"key2\": 123}'). "
                       "These options will be merged into the solver options dictionary. "
                       "Leave empty unless experimenting with solver.")
            ret = kz.getText("Extra solver options (expert)", "xtra_options",
                             placeholder='{"key": "value"}', help=helpmsg)

    st.divider()
    st.markdown("#### :orange[Spending Profile]")
    col1, col2, col3 = st.columns(3, gap="medium", vertical_alignment="top")
    with col1:
        helpmsg = "Spending can be constant during the duration of the plan or be adjusted for lifestyle."
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
