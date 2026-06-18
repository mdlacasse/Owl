"""
Savings Assets page for Owl retirement planner Streamlit UI.

This module provides the interface for entering savings account balances
across different tax categories (taxable, tax-deferred, tax-free).

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

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
    kz.no_case_info()
else:
    st.markdown("#### :orange[Savings Account Balances]")
    accounts = {"txbl": "taxable", "txDef": "tax-deferred", "txFree": "tax-free", "hsa": "HSA"}
    hdetails = {"txbl": "Sum of brokerage and savings accounts. ",
                "txDef": "Sum of IRA, 401k, 403b and the like. ",
                "txFree": "Sum of Roth IRA, Roth 401k, Roth 403b and the like. ",
                "hsa": "Sum of Health Savings Account (triple tax-advantaged). "}
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        iname = kz.getCaseKey("iname0")
        for key in accounts:
            nkey = key + str(0)
            kz.initCaseKey(nkey, 0)
            ret = kz.getNum(f"{iname}'s {accounts[key]} accounts ($k)", nkey,
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
                ret = kz.getNum(f"{iname1}'s {accounts[key]} accounts ($k)", nkey,
                                help=hdetails[key]+kz.help1000)

    st.divider()
    st.markdown("#### :orange[Taxable Account Cost Basis] *(optional)*")
    basis_help = (
        "Current cost basis of the taxable account for this person ($k). "
        "When provided, capital gains on withdrawals are computed from the actual "
        "unrealized-gain fraction (average-cost method) rather than only this year's "
        "price appreciation. Leave at 0 if unknown — the legacy approximation will be used."
    )
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
    with col1:
        iname = kz.getCaseKey("iname0")
        nkey = "txblBasis0"
        kz.initCaseKey(nkey, 0.0)
        kz.getNum(f"{iname}'s taxable cost basis ($k)", nkey, help=basis_help)
    with col2:
        if kz.getCaseKey("status") == "married":
            iname1 = kz.getCaseKey("iname1")
            nkey = "txblBasis1"
            kz.initCaseKey(nkey, 0.0)
            kz.getNum(f"{iname1}'s taxable cost basis ($k)", nkey, help=basis_help)

    inames = [kz.getCaseKey("iname0")]
    if kz.getCaseKey("status") == "married":
        inames.append(kz.getCaseKey("iname1"))
    warn_col, _ = st.columns([2, 1])
    for i, iname in enumerate(inames):
        basis = kz.getCaseKey(f"txblBasis{i}") or 0.0
        balance = kz.getCaseKey(f"txbl{i}") or 0.0
        if basis > 0 and balance == 0:
            with warn_col:
                st.warning(f"Set {iname}'s taxable account balance before entering a cost basis.",
                           icon=":material/warning:")
        elif basis > balance > 0:
            with warn_col:
                st.warning(
                    f"{iname}'s cost basis (\\${basis:,.0f}k) exceeds taxable balance (\\${balance:,.0f}k). "
                    "This implies the account has lost value since purchase (unrealized losses). "
                    "If this is unintentional, please check your entries. "
                    "If correct, Owl will assume no capital gains on withdrawals.",
                    icon=":material/warning:",
                )

    if kz.getCaseKey("status") == "married":
        st.divider()
        with st.expander("*Advanced options*"):
            st.markdown("#### :orange[Survivor's Spousal Beneficiary Fractions]")
            helpmsg = "Fraction of account left to surviving spouse."
            hsahelp = ("Fraction of HSA left to surviving spouse. "
                       "IRS rules allow a spouse beneficiary to inherit the HSA intact "
                       "(full tax-advantaged status). Defaults to 1.0.")
            col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
            with col1:
                nkey = "benf" + str(0)
                kz.initCaseKey(nkey, 1)
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
            with col4:
                nkey = "benf" + str(3)
                kz.initCaseKey(nkey, 1)
                ret = kz.getNum("HSA", nkey, format="%.2f", max_value=1.0,
                                step=0.05, help=hsahelp)

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
