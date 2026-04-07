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


kz.initCaseKey("computeMedicare", True)
kz.initCaseKey("optimizeMedicare", False)
kz.initCaseKey("slcspAnnual", 0)
kz.initCaseKey("optimizeACA", False)
kz.initCaseKey("optimizeLTCG", False)
kz.initCaseKey("optimizeNIIT", False)
kz.initCaseKey("useDecomposition", "none")
kz.initCaseKey("withSCLoop", True)
kz.initCaseKey("ssTaxabilityMode", "loop")
kz.initCaseKey("ssTaxabilityValue", 0.85)


ret = kz.titleBar(":material/tune: Run Options")

if ret is None or kz.caseHasNoPlan():
    st.info("A case must first be created before running this page.")
else:

    st.markdown("#### :orange[Roth Conversions]")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        iname0 = kz.getCaseKey("iname0")
        helpmsg = "Value is in nominal \\$k."
        kz.initCaseKey("readRothX", False)
        fromFile = kz.getCaseKey("readRothX")
        kz.initCaseKey("maxRothConversion", 50)
        ret = kz.getNum("Maximum annual Roth conversion (\\$k)", "maxRothConversion",
                        disabled=fromFile, help=helpmsg)
        helpmsg = "Convert using values from the *Roth conv* column of the *Wages and Contributions* table."
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
    with col3:
        if kz.getCaseKey("status") == "married":
            iname1 = kz.getCaseKey("iname1")
            choices = ["none", iname0, iname1]
            kz.initCaseKey("noRothConversions", choices[0])
            helpmsg = "`none` means no exclusion. To exclude both spouses, set `Maximum annual Roth conversion` to 0."
            ret = kz.getRadio("Exclude Roth conversions for...", choices, "noRothConversions",
                              disabled=fromFile, help=helpmsg)

    st.divider()
    st.markdown("#### :orange[Medicare]")
    cols = st.columns(3, gap="large", vertical_alignment="top")
    with cols[0]:
        kz.initCaseKey("computeMedicare", True)
        helpmsg = "Compute Medicare and IRMAA premiums."
        medion = kz.getToggle("Medicare and IRMAA calculations", "computeMedicare", help=helpmsg)
        if medion and not kz.getCaseKey("withSCLoop"):
            st.markdown(":material/warning: Medicare is on while self-consistent loop is off.")

    if kz.getCaseKey("computeMedicare"):
        helpmsg = "MAGI in nominal \\$k for current and previous years."
        years = owb.backYearsMAGI()
        for ii in range(2):
            kz.initCaseKey("MAGI" + str(ii), 0)
            if years[ii] > 0:
                with cols[1+ii]:
                    ret = kz.getNum(f"MAGI for {years[ii]} ($k)", "MAGI" + str(ii), help=helpmsg)

        cols = st.columns(3, gap="large", vertical_alignment="top")
        with cols[0]:
            kz.initCaseKey("includeMedicarePartD", True)
            helpmsg_partd = ("Include Medicare Part D premiums (IRMAA surcharges use same MAGI brackets as Part B). "
                             "Turn off if you have other drug coverage (e.g. employer, VA).")
            kz.getToggle("Include Part D premiums", "includeMedicarePartD", help=helpmsg_partd)
        with cols[1]:
            kz.initCaseKey("medicarePartDBasePremium", None)
            helpmsg_partd_base = ("Optional monthly Part D base premium per person (today's \\$). "
                                  "Set to 0 to omit. National average ~\\$$39–47$ per month.")
            kz.getNum("Part D base premium ($/month per person)", "medicarePartDBasePremium",
                      min_value=0., help=helpmsg_partd_base)

    st.divider()
    st.markdown("#### :orange[ACA Marketplace (Pre-65)]")
    helpmsg = ("Annual premium for the second-lowest-cost Silver plan in your area. "
               "Used to compute Premium Tax Credit. Set to 0 to exclude ACA costs. "
               "Applies only in years before Medicare (age 65). "
               "See [Healthcare.gov](https://healthcare.gov) for your SLCSP.")
    cols = st.columns(3, gap="large", vertical_alignment="top")
    with cols[0]:
        kz.getNum("Benchmark Silver plan premium (SLCSP) ($k/year)", "slcspAnnual", min_value=0., help=helpmsg)

    st.divider()
    st.markdown("#### :orange[Social Security Claiming Ages]")
    helpmsg = ("Select which individuals should have their SS claiming month optimized "
               "(any month between age 62 and 70). "
               "For individuals already receiving benefits, the claiming age is always fixed. "
               "Optimal ages are written back to the Fixed Income page after solving.")
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        iname0 = kz.getCaseKey("iname0")
        if kz.getCaseKey("status") == "married":
            iname1 = kz.getCaseKey("iname1")
            choices = ["none", iname0, iname1, "both"]
        else:
            choices = ["none", iname0]

        kz.initCaseKey("ssAgesMode", "none")
        ret = kz.getRadio("Optimize SS claiming age", choices, "ssAgesMode", help=helpmsg)

    st.divider()
    with st.expander("*Advanced options*"):
        st.markdown("#### :orange[Calculations]")
        col1, col2 = st.columns([40, 60], gap="large", vertical_alignment="top")
        with col1:
            helpmsg = ("Option to use a self-consistent loop to adjust additional values such as the net"
                       " investment income tax (NIIT), and capital gain tax rates."
                       "  When Medicare is selected, this will also compute Medicare and IRMAA.")
            ret = kz.getToggle("Self-consistent loop calculations", "withSCLoop", help=helpmsg)
            helpmsg = ("Option to optimize Medicare using binary variables."
                       "  Use with caution as some cases might not converge"
                       " without adjusting additional solver parameters.")
            medioff = not medion
            ret = kz.getToggle("Optimize Medicare (expert)", "optimizeMedicare", help=helpmsg, disabled=medioff)
            acaoff = (kz.getCaseKey("slcspAnnual") or 0) <= 0
            helpmsg_aca = ("Co-optimize ACA bracket selection within the LP. "
                           "More accurate but slower. Only applies when SLCSP > 0.")
            ret = kz.getToggle("Optimize ACA (expert)", "optimizeACA", help=helpmsg_aca, disabled=acaoff)
            helpmsg_ltcg = ("Optimize LTCG bracket selection using binary variables. "
                            "Replaces self-consistent loop for LTCG ordinary income stacking. "
                            "More accurate but slower.")
            ret = kz.getToggle("Optimize LTCG brackets (expert)", "optimizeLTCG", help=helpmsg_ltcg)
            helpmsg_niit = ("Optimize NIIT (Net Investment Income Tax) within the MIP. "
                            "Replaces self-consistent loop for NIIT computation. "
                            "Only effective when Optimize LTCG is also enabled.")
            ret = kz.getToggle("Optimize NIIT (expert)", "optimizeNIIT", help=helpmsg_niit)
            decompoff = not (kz.getCaseKey("optimizeMedicare") or kz.getCaseKey("optimizeACA")
                             or kz.getCaseKey("optimizeLTCG") or kz.getCaseKey("optimizeNIIT"))
            decomp_choices = ["none", "sequential", "benders"]
            helpmsg_decomp = (
                "'none': monolithic MIP (default). "
                "'sequential': relax-and-fix heuristic — fixes Medicare/ACA/SS bracket binaries "
                "sequentially; fast but not guaranteed globally optimal. "
                "'benders': classical Benders decomposition — certified globally optimal within "
                "the MIP gap; slower per iteration but provably correct. "
                "Only applies when Optimize Medicare or Optimize ACA is active."
            )
            ret = kz.getRadio("MIP decomposition (expert)", decomp_choices, "useDecomposition",
                              help=helpmsg_decomp, disabled=decompoff)
        with col2:
            kz.initCaseKey("amoSurplus", True)
            helpmsg = ("Enable at-most-one (AMO) exclusive constraints between surplus deposits"
                       " and withdrawals from taxable or tax-free accounts.")
            ret = kz.getToggle("Disallow same-year surplus deposits and withdrawals from taxable or tax-free accounts",
                               "amoSurplus", help=helpmsg)

            kz.initCaseKey("amoRoth", True)
            helpmsg = ("Enable at-most-one (AMO) exclusive constraints between"
                       " Roth conversions and withdrawals from tax-free accounts.")
            ret = kz.getToggle("Disallow same-year Roth conversions and tax-free withdrawals",
                               "amoRoth", help=helpmsg)

            kz.initCaseKey("noLateSurplus", False)
            helpmsg = ("Disallow cash-flow surpluses in the last two years of the plan."
                       " This avoids sheltering transfers when market goes down in last years.")
            ret = kz.getToggle("Disallow cash-flow surpluses in the last 2 years",
                               "noLateSurplus", help=helpmsg)

        st.divider()
        st.markdown("#### :orange[Social Security Taxability]")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
        with col1:
            choices = ["loop", "value", "optimize"]
            kz.initCaseKey("ssTaxabilityMode", "loop")
            helpmsg = ("’loop’: compute SS taxable fraction dynamically via the self-consistent loop. "
                       "’value’: pin SS taxable fraction to a fixed value (enter in box). "
                       "’optimize’: solve taxable SS exactly within the LP using binary variables (expert).")
            ret = kz.getRadio("SS taxability method", choices, "ssTaxabilityMode", help=helpmsg)
        with col2:
            if kz.getCaseKey("ssTaxabilityMode") == "value":
                kz.initCaseKey("ssTaxabilityValue", 0.85)
                helpmsg = ("SS taxable fraction \u2208 [0, 0.85]. "
                           "Use 0.0 (Provisional income (PI) below lower threshold), "
                           "0.5 (mid-range), or 0.85 (high PI).")
                ret = kz.getNum("Fixed SS taxable fraction", "ssTaxabilityValue",
                                min_value=0.0, max_value=0.85, step=0.05, format="%.2f",
                                help=helpmsg)

        st.divider()
        st.markdown("#### :orange[Solver]")
        choices = ["default", "HiGHS"]
        kz.initCaseKey("solver", choices[0])
        kz.initCaseKey("xtraOptions", "")

        if owb.hasMOSEK():
            choices += ["MOSEK"]
        elif kz.getCaseKey("solver") == "MOSEK":
            kz.setCaseKey("solver", choices[0])

        col1, col2 = st.columns([45, 55], gap="large", vertical_alignment="top")
        with col1:
            helpmsg = ("Select different solvers for comparison purposes."
                       " For best performance, use MOSEK if available. Otherwise use HiGHS."
                       " 'default' automatically picks MOSEK when available, otherwise HiGHS.")
            ret = kz.getRadio("Linear programming solver", choices, "solver", help=helpmsg)
            if kz.getCaseKey("solver") == "default":
                resolved = "MOSEK" if owb.hasMOSEK() else "HiGHS"
                st.caption(f"Will use: **{resolved}**")
        with col2:
            helpmsg = ("Additional solver options as a dictionary (e.g., '{\"key1\": \"value1\", \"key2\": 123}'). "
                       "These options will be merged into the solver options dictionary. "
                       "Leave empty unless experimenting with solver.")
            ret = kz.getText("Extra solver options (expert)", "xtra_options",
                             placeholder='{"key": "value"}', help=helpmsg)

    st.divider()
    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar(divider=False)
