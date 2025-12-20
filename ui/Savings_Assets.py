from datetime import date
import streamlit as st

import sskeys as kz
import case_progress as cp

ret = kz.titleBar(":material/savings: Savings Assets")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    st.markdown("#### :orange[Savings Account Balances]")
    accounts = {"txbl": "taxable", "txDef": "tax-deferred", "txFree": "tax-free"}
    hdetails = {"txbl": "Brokerage and savings accounts excluding emergency fund. ",
                "txDef": "IRA, 401k, 403b and the like. ",
                "txFree": "Roth IRA, Roth 401k, Roth 403b and the like. "}
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        iname = kz.getCaseKey("iname0")
        for key in accounts:
            nkey = key + str(0)
            kz.initCaseKey(nkey, 0)
            ret = kz.getNum(f"{iname}'s {accounts[key]} account ($k)", nkey,
                            help=hdetails[key]+kz.help1000)

        today = date.today()
        thisyear = today.year
        kz.initCaseKey("startDate", today)
        helpmsg = "Date at which savings balances are known. Values will be back projected to Jan 1st."
        ret = st.date_input("Account balance date", min_value=date(thisyear, 1, 1),
                            max_value=date(thisyear, 12, 31), value=kz.getCaseKey("startDate"),
                            key=kz.genCaseKey("startDate"), args=["startDate"], on_change=kz.setpull, help=helpmsg)

    with col2:
        if kz.getCaseKey("status") == "married":
            iname1 = kz.getCaseKey("iname1")
            for key in accounts:
                nkey = key + str(1)
                kz.initCaseKey(nkey, 0)
                ret = kz.getNum(f"{iname1}'s {accounts[key]} account ($k)", nkey,
                                help=hdetails[key]+kz.help1000)

    if kz.getCaseKey("status") == "married":
        st.divider()
        st.markdown("#### :orange[Survivor's Spousal Beneficiary Fractions]")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
        with col1:
            nkey = "benf" + str(0)
            kz.initCaseKey(nkey, 1)
            helpmsg = "Fraction of account left to surviving spouse."
            ret = kz.getNum(accounts["txbl"].capitalize(), nkey, format="%.2f", max_value=1.0,
                            step=0.05, help=helpmsg)

        with col2:
            nkey = "benf" + str(1)
            kz.initCaseKey(nkey, 1)
            ret = kz.getNum(accounts["txDef"].capitalize(), nkey, format="%.2f", max_value=1.0,
                            step=0.05, help=helpmsg)

        with col3:
            nkey = "benf" + str(2)
            kz.initCaseKey(nkey, 1)
            ret = kz.getNum(accounts["txFree"].capitalize(), nkey, format="%.2f", max_value=1.0,
                            step=0.05, help=helpmsg)

        st.markdown("#####")
        st.markdown("#### :orange[Surplus Deposit Fraction]")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("surplusFraction", 0.5)
            helpmsg = ("When beneficiary fractions are not all 1, "
                       "set cash-flow surplus deposits to entirely go to the account of first spouse to pass.")
            ret = kz.getNum(
                f"Fraction deposited in {iname1}'s taxable account",
                "surplusFraction",
                format="%.2f",
                help=helpmsg,
                max_value=1.0,
                step=0.05,
            )

    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar()
