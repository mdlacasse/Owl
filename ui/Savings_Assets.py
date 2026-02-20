"""
Savings Assets page for Owl retirement planner Streamlit UI.

This module provides the interface for entering savings account balances
across different tax categories (taxable, tax-deferred, tax-free).

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

from datetime import date
import streamlit as st

import sskeys as kz
import case_progress as cp

ret = kz.titleBar(":material/savings: Account Balances")

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
        with st.expander("*Advanced options*"):
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
            st.markdown("#### :orange[Cash Flow Surplus Deposit Fraction]")
            col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
            with col1:
                kz.initCaseKey("surplusFraction", 0.5)
                helpmsg = ("When beneficiary fractions are not all 1, "
                           "assign all cash-flow surplus deposits to the account of the first spouse to pass.")
                ret = kz.getNum(
                    f"Fraction of cash flow surplus deposited in {iname1}'s taxable account",
                    "surplusFraction",
                    format="%.2f",
                    help=helpmsg,
                    max_value=1.0,
                    step=0.05,
                )

    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar()
