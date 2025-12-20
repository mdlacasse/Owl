import streamlit as st
from datetime import date

import sskeys as kz
import owlbridge as owb


profileChoices = ["flat", "smile"]
kz.initCaseKey("spendingProfile", profileChoices[1])
kz.initCaseKey("survivor", 60)
kz.initCaseKey("smileDip", 15)
kz.initCaseKey("smileIncrease", 12)
kz.initCaseKey("smileDelay", 0)
mediChoices = ["None", "loop", "optimize"]
kz.initCaseKey("withMedicare", mediChoices[1])


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
        ret = kz.getRadio("Maximize", choices, "objective")

    with col2:
        if kz.getCaseKey("objective") == "Net spending":
            kz.initCaseKey("bequest", 0)
            ret = kz.getNum("Desired bequest (\\$k)", "bequest", help=helpmsg)

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
    st.markdown("#### :orange[Calculations]")
    kz.initCaseKey("withSCLoop", True)
    kz.initCaseKey("xorConstraints", True)
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        helpmsg = ("Option to use a self-consistent loop to adjust additional values such as the net"
                   " investment income tax (NIIT), and capital gain tax rates."
                   "  If selected below, this loop will also compute Medicare and IRMAA.")
        ret = kz.getToggle("Self-consistent loop calculations", "withSCLoop", help=helpmsg)
    with col2:
        helpmsg = ("Enable mutually exclusive constraints between surplus deposits,"
                   " Roth conversions, and withdrawals from taxable and/or tax-free accounts.")
        ret = kz.getToggle("XOR constraints on deposits, conversions, and withdrawals",
                           "xorConstraints", help=helpmsg)

    st.divider()
    st.markdown("#### :orange[Medicare]")
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        helpmsg = ("How to compute Medicare and IRMAA premiums:"
                   " ignore, use self-consistent loop, or use additional variables in optimization.")
        ret = kz.getRadio("Medicare and IRMAA calculations", mediChoices, "withMedicare", help=helpmsg)
        if ret == "optimize":
            st.markdown(":material/warning: Medicare optimization can sometimes have slow convergence -"
                        " time for :coffee: ?")
        elif ret == "loop" and not kz.getCaseKey("withSCLoop"):
            st.markdown(":material/warning: Medicare set to 'loop' while self-consistent loop is off.")
    with col2:
        medi = kz.getCaseKey("withMedicare")
        if medi == "optimize" or (medi == "loop" and kz.getCaseKey("withSCLoop")):
            helpmsg = "MAGI in nominal $k for current and previous years."
            years = owb.backYearsMAGI()
            for ii in range(2):
                kz.initCaseKey("MAGI" + str(ii), 0)
                if years[ii] > 0:
                    ret = kz.getNum(f"MAGI for year {years[ii]} ($k)", "MAGI" + str(ii), help=helpmsg)

    st.divider()
    st.markdown("#### :orange[Solver]")
    choices = ["HiGHS", "PuLP/CBC", "PuLP/HiGHS"]
    if owb.hasMOSEK():
        choices += ["MOSEK"]
    kz.initCaseKey("solver", choices[0])
    helpmsg = "Select different solvers for comparison purposes. Use HiGHS for best performance."
    ret = kz.getRadio("Linear programming solver", choices, "solver", help=helpmsg)

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
