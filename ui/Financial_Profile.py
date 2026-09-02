"""
Household Financial Profile page for Owl retirement planner Streamlit UI.

This module provides the interface for entering household financial profile
information including wages and contributions.

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

import streamlit as st
import pandas as pd
from datetime import date

from owlplanner.hfp_io import getTableTypes

import sskeys as kz
import owlbridge as owb
import tomlexamples as tomlex
import case_progress as cp


# Bubble help for the Wages and Contributions columns, as the debts and fixed assets
# tables already have. Kept short: the Documentation page carries the full description.
timetableHelp = {
    "year": "Calendar year of this row",
    "anticipated wages": (
        "Employment income you anticipate this year (nominal $), entered net of every "
        "contribution column to the right. Employer contributions were never part of your "
        "wages, so do not subtract those."
    ),
    "other inc": (
        "Other ordinary income that is not wages, pension, or Social Security (nominal $) — "
        "e.g. consulting income, alimony, or rents you treat as ordinary."
    ),
    "net inv": (
        "Net investment income such as rent or trust distributions (nominal $). Taxed as "
        "ordinary income and also counted toward the Net Investment Income Tax."
    ),
    "taxable ctrb": "Contributions to your taxable savings account (nominal $)",
    "401k ctrb": (
        "Contributions to 401k, 403b, and any other tax-deferred account other than an IRA "
        "(nominal $). Include your employer's contributions."
    ),
    "Roth 401k ctrb": "Contributions to your Roth 401k or Roth 403b account (nominal $)",
    "IRA ctrb": "Contributions to your traditional IRA (nominal $), treated as pre-tax",
    "Roth IRA ctrb": "Contributions to your Roth IRA (nominal $)",
    "HSA ctrb": (
        "Contributions to your health savings account (nominal $). Zeroed automatically at "
        "Medicare enrollment (~age 65)."
    ),
    "Roth conv": (
        "Roth conversion amount for this year (nominal $), never negative. Documentation only "
        "unless the year is ticked in the next column."
    ),
    "Roth conv fixed": (
        "Hold this year's conversion at exactly the amount beside it, bypassing the annual cap "
        "and the start and stop years. An amount of 0 then means no conversion that year. "
        "Unticked, Owl optimizes the year."
    ),
    "QCD": (
        "Qualified Charitable Distribution (nominal $): money sent from your tax-deferred "
        "account straight to a charity. Never enters taxable income and counts toward your RMD, "
        "but does not fund spending. Requires age 70½ and is capped per person per year."
    ),
    "big-ticket items": (
        "A major one-time amount (nominal $): the sign matters. Positive is money received, "
        "such as an inheritance or the sale of a house; negative is a major expense."
    ),
}

# The five lead-in rows record what already happened, so two columns mean something else there.
timetableHelpPast = dict(timetableHelp)
timetableHelpPast["Roth conv"] = (
    "A Roth conversion you already performed that year (nominal $). This is what the IRS "
    "five-year maturation rule needs, and is the only column read from this table."
)
timetableHelpPast["Roth conv fixed"] = (
    "Not applicable to past years: a conversion already performed always counts"
)


def timetableColumnConfig(df, helpdic):
    """Column configuration for a Wages and Contributions editor, with bubble help."""
    # Keyed by name, not position: the column list is free to grow.
    # "big-ticket items" can be an expense; every other amount is >= 0.
    negativeOK = ("big-ticket items",)
    formatdic = {"year": st.column_config.NumberColumn(None, help=helpdic.get("year"), format="%d", disabled=True)}
    for col in df.columns:
        if col == "year":
            continue
        if col in owb.booleanTimeHorizonItems():
            formatdic[col] = st.column_config.CheckboxColumn(None, help=helpdic.get(col), default=False)
            continue
        minValue = None if col in negativeOK else 0.0
        formatdic[col] = st.column_config.NumberColumn(
            None, help=helpdic.get(col), min_value=minValue, format="accounting"
        )

    return formatdic


def loadWCExample(file):
    if file:
        # Use normalized HFP name for the file parameter to match the actual filename
        hfp_name = tomlex.getHFPName(file)
        mybytesio = tomlex.loadWagesExample(file)
        if mybytesio is not None:
            owb.readHFP(mybytesio, file=hfp_name)


ret = kz.titleBar(":material/home: Financial Profile")

if ret is None or kz.caseHasNoPlan():
    kz.no_case_info()
else:
    if kz.getCaseKey("timeList0") is None:
        kz.runOncePerCase(owb.resetTimeLists)
    kz.initCaseKey("stHFP", None)
    # Initialize houseLists if they don't exist
    kz.initCaseKey("houseListDebts", None)
    kz.initCaseKey("houseListFixedAssets", None)
    n = 2 if kz.getCaseKey("status") == "married" else 1

    if kz.getCaseKey("stHFP") is None:
        original = kz.getCaseKey("hfpFileName")
        if original is None or original == "None":
            st.info(
                f"Case *'{kz.currentCaseName()}'* makes no reference to a Financial Profile.\n\n"
                "You can build your own HFP by directly filling the table(s) below. "
                "Once a case has been successfully run, values can be saved on the **Reports** page. "
                "Alternatively, you can start from this Excel "
                "[template](https://github.com/mdlacasse/Owl/blob/main/examples/HFP_template.xlsx?raw=true) "
                "and upload the file using the widget below."
            )
        else:
            base = original[:-2] if original.endswith(" *") else original
            st.info(f"""Case *'{kz.currentCaseName()}'* refers to file *'{base}'*
that has not yet been uploaded.""")

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### :orange[Upload *Household Financial Profile* Workbook]")
        kz.initCaseKey("_xlsx", 0)
        stHFP = st.file_uploader(
            "Upload values from a Household Financial Profile (HFP) workbook...",
            key="_stHFP" + str(kz.getCaseKey("_xlsx")),
            type=["xlsx", "ods"],
            help=(
                "An Excel (.xlsx) or OpenDocument (.ods) workbook with one sheet per individual "
                "containing year-by-year wages, retirement contributions, Roth conversions, and large expenses, "
                "plus optional household sheets for debts and fixed assets."
            ),
        )
        if stHFP is not None:
            if owb.readHFP(stHFP):
                kz.setCaseKey("stHFP", stHFP)
                # Change key to reset uploader.
                kz.storeCaseKey("_xlsx", kz.getCaseKey("_xlsx") + 1)
                st.rerun()
        stHFP_val = kz.getCaseKey("stHFP")
        if stHFP_val is not None:
            hfp_name = kz.getCaseKey("hfpFileName") or ""
            if hfp_name.endswith(" *"):
                st.caption(f":white_check_mark: *{hfp_name[:-2]}*\\* loaded — values modified.")
            else:
                st.caption(f":white_check_mark: *{hfp_name}* loaded.")
    with col2:
        tomlexcase = kz.getCaseKey("tomlexcase")
        mytype = "primary" if kz.getCaseKey("stHFP") is None else "secondary"
        if tomlexcase is not None and tomlex.hasHFPExample(tomlexcase):
            st.markdown("#### :orange[Load Example HFP Workbook]")
            st.markdown("Read associated HFP workbook.")
            helpmsg = "Load associated HFP workbook from GitHub"
            st.button("Load example workbook", help=helpmsg, type=mytype, on_click=loadWCExample, args=[tomlexcase])

    # An absent column is read as zero. That is usually what the user meant, but it
    # is a change of meaning they never typed, so say it here rather than leaving it
    # to the Logs page. The columns are already in the table by now, so point at
    # saving the workbook rather than asking for them to be added by hand.
    absentCols = kz.getCaseKey("hfpAbsentCols") or {}
    reported = {iname: cols for iname, cols in absentCols.items() if cols}
    if reported:
        lines = "\n".join(f"- **{iname}**: {', '.join(cols)}" for iname, cols in reported.items())
        st.warning(
            "The workbook did not contain the following column(s), which are treated as zero "
            f"for every year:\n\n{lines}\n\nThey have been added to the tables below. Edit them "
            "there if the zeros are not what you intended, then use *Download HFP workbook* at the "
            "foot of this page to save a copy that has them.",
            icon=":material/info:",
        )

    st.divider()
    st.markdown("### :material/work_history: :orange[Wages and Contributions]")
    st.markdown("""Wages and contributions for each individual, in two tables.
Enter *anticipated wages* net of all contribution columns (see the Documentation page for details).
The first table holds the five years before this one. Only its Roth entries are read, to comply with the IRS
five-year maturation rule, but every column is yours to keep: the figures stay in your workbook as the history
you carry forward and extrapolate from. Because those conversions have already happened, *Roth conv fixed*
does not apply there and is shown disabled.
The second table starts at the current year and covers the rest of the plan.""")

    with st.expander("*Expand Wages and Contributions timetables*"):
        for i in range(n):
            st.markdown("#### :orange[" + kz.getCaseKey("iname" + str(i)) + "'s Timetable]")
            df = kz.getCaseKey("timeList" + str(i))
            if df is None:
                continue
            # One table, two editors. Streamlit can only disable whole columns, so the
            # only way to disable a flag on the past rows alone is to give them an editor
            # of their own: there, the column and the rows are the same thing.
            thisyear = date.today().year
            pastdf = df[df["year"] < thisyear]
            plandf = df[df["year"] >= thisyear]

            st.markdown("*Past five years*")
            editedpast = st.data_editor(
                pastdf,
                column_config=timetableColumnConfig(df, timetableHelpPast),
                hide_index=True,
                disabled=owb.booleanTimeHorizonItems(),
                key=kz.genCaseKey("wagesPast" + str(i)),
            )
            st.caption(
                "Only the Roth columns are read here, but the rest is kept in your workbook as the "
                "record you carry forward."
            )
            st.markdown("*Plan years*")
            editedplan = st.data_editor(
                plandf,
                column_config=timetableColumnConfig(df, timetableHelp),
                hide_index=True,
                key=kz.genCaseKey("wages" + str(i)),
            )
            st.caption(
                "Values are in nominal \\$. Tick *Roth conv fixed* to hold that year's "
                "*Roth conv* amount instead of letting **Owl** optimize it; an amount of 0 "
                "then means no conversion that year."
            )
            # Back to one table. ignore_index restores the 0..h+4 row numbering that
            # setContributions() and checkQCDColumn() slice positionally.
            newdf = pd.concat([editedpast, editedplan], ignore_index=True)
            newdf = newdf.fillna(0)
            newdf = owb.conditionTimeListFlags(newdf)
            kz.storeCaseKey("_timeList" + str(i), newdf)

            # Report a bad QCD entry against this table, not later at run time.
            qcdError = owb.checkQCDColumn(newdf, i)
            if qcdError:
                st.error(qcdError, icon=":material/error:")

            if not df.reset_index(drop=True).equals(newdf):
                kz.setCaseKey("timeList" + str(i), newdf)
                if kz.getCaseKey("stHFP") is not None:
                    fname = kz.getCaseKey("hfpFileName") or ""
                    if fname and not fname.endswith(" *"):
                        kz.storeCaseKey("hfpFileName", fname + " *")
                st.rerun()

        st.button("Reset to zero", help="Reset all values to zero.", on_click=owb.resetTimeLists)

    st.divider()
    st.markdown("### :material/account_balance: :orange[Debts and Fixed Assets]")
    st.markdown("""Debts and fixed assets are associated with the household.""")

    with st.expander("*Expand Debts and Fixed Assets tables*"):
        st.markdown("#### :orange[Debts]")

        # Get debt types from owlbridge to ensure consistency with validation logic
        debtTypes = getTableTypes("Debts")

        # Get existing debts or create empty DataFrame
        debtdf = owb.conditionDebtsAndFixedAssetsDF(kz.getCaseKey("houseListDebts"), "Debts")

        thisyear = date.today().year
        debtconf = {
            "active": st.column_config.CheckboxColumn(
                "active",
                help="Check box for item to be considered in plan",
                default=True,
                required=True,
            ),
            "name": st.column_config.TextColumn(
                "name",
                help="Give a unique name to your debt",
                required=True,
            ),
            "type": st.column_config.SelectboxColumn(
                "type",
                help="Select the type of debt from dropdown menu",
                required=True,
                options=debtTypes,
            ),
            "year": st.column_config.NumberColumn(
                "year",
                help="Enter the origination year",
                min_value=1950,
                required=True,
                step=1,
            ),
            "term": st.column_config.NumberColumn(
                "term",
                help="Enter loan term (y)",
                min_value=1,
                max_value=30,
                required=True,
                step=1,
            ),
            "amount": st.column_config.NumberColumn(
                "amount",
                help="Enter original loan amount ($)",
                format="dollar",
                required=True,
                min_value=0,
                step=1,
            ),
            "rate": st.column_config.NumberColumn(
                "rate",
                help="Enter annual rate (%)",
                required=True,
                min_value=0.0,
                step=0.01,
            ),
        }

        edited_debtdf = st.data_editor(
            debtdf, column_config=debtconf, num_rows="dynamic", hide_index=True, key=kz.genCaseKey("debts")
        )
        debtsCaption = """Amounts are in nominal $. Additional items can be directly entered
in the table by clicking :material/add: on the last row.
Items can be deleted by selecting rows in the left margin and pressing the *Delete* key."""
        st.caption(debtsCaption)

        # Store edited debts if changed
        if not debtdf.equals(edited_debtdf):
            edited_debtdf = owb.conditionDebtsAndFixedAssetsDF(edited_debtdf, "Debts")
            kz.setCaseKey("houseListDebts", edited_debtdf)
            if kz.getCaseKey("stHFP") is not None:
                fname = kz.getCaseKey("hfpFileName") or ""
                if fname and not fname.endswith(" *"):
                    kz.storeCaseKey("hfpFileName", fname + " *")
            st.rerun()

        st.divider()
        st.markdown("#### :orange[Fixed Assets]")

        # Get fixed asset types from owlbridge to ensure consistency with validation logic
        fixedTypes = getTableTypes("Fixed Assets")

        # Get existing fixed assets or create empty DataFrame
        fixeddf = owb.conditionDebtsAndFixedAssetsDF(kz.getCaseKey("houseListFixedAssets"), "Fixed Assets")

        fixedconf = {
            "active": st.column_config.CheckboxColumn(
                "active",
                help="Check box for item to be considered in plan",
                default=True,
                required=True,
            ),
            "name": st.column_config.TextColumn(
                "name",
                help="Give a unique name to your fixed asset",
                required=True,
            ),
            "type": st.column_config.SelectboxColumn(
                "type",
                help="Select the type of fixed asset from dropdown menu",
                required=True,
                options=fixedTypes,
            ),
            "year": st.column_config.NumberColumn(
                "year",
                help="Reference year (this year or after)",
                min_value=thisyear,
                required=True,
                step=1,
            ),
            "basis": st.column_config.NumberColumn(
                "basis",
                help="Actual cost basis — what you paid (nominal dollars, not inflation-adjusted)",
                min_value=0,
                required=True,
                format="dollar",
                step=1,
            ),
            "value": st.column_config.NumberColumn(
                "value",
                help="Enter value at reference year ($)",
                min_value=0,
                required=True,
                format="dollar",
                step=1,
            ),
            "rate": st.column_config.NumberColumn(
                "rate",
                help=(
                    "Annual growth rate (%). "
                    "For physical assets (residence, real estate, collectibles, precious metals): "
                    "real rate above inflation — rate=0 means the asset tracks inflation. "
                    "For stocks: nominal rate. "
                    "For fixed annuity: nominal rate (0 = flat lump-sum payout)."
                ),
                # default=3.0,
                required=True,
                min_value=0.0,
                step=0.01,
            ),
            "yod": st.column_config.NumberColumn(
                "yod",
                help="Year of disposition (y); negative counts from plan end",
                # min_value=thisyear,    # Can be zero or negative
                required=True,
                step=1,
            ),
            "commission": st.column_config.NumberColumn(
                "commission",
                help="Sale commission (%)",
                min_value=0.0,
                max_value=10.0,
                required=True,
                default=0.0,
                step=0.01,
            ),
        }

        edited_fixeddf = st.data_editor(
            fixeddf, column_config=fixedconf, hide_index=True, num_rows="dynamic", key=kz.genCaseKey("fixed_assets")
        )
        fixedCaption = """Value is in reference-year $ (at the start of the reference year). \
Basis is the actual cost basis in nominal dollars (what you paid, not inflation-adjusted).
Additional items can be directly entered in the table by clicking :material/add:
on the last row. Items can be deleted by selecting rows in the left margin and
pressing the *Delete* key."""
        st.caption(fixedCaption)

        # Store edited fixed assets if changed
        if not fixeddf.equals(edited_fixeddf):
            edited_fixeddf = owb.conditionDebtsAndFixedAssetsDF(edited_fixeddf, "Fixed Assets")
            kz.setCaseKey("houseListFixedAssets", edited_fixeddf)
            if kz.getCaseKey("stHFP") is not None:
                fname = kz.getCaseKey("hfpFileName") or ""
                if fname and not fname.endswith(" *"):
                    kz.storeCaseKey("hfpFileName", fname + " *")
            st.rerun()

    st.divider()
    # One workbook holds every table on this page, so it is offered below all of them
    # rather than under the first. Building it needs the tables, not a solved plan, so
    # this stays available even for a case that cannot run -- unlike the same download
    # on the Reports page, which is gated behind a successful solve.
    if not kz.caseHasNoPlan():
        caseName = kz.getCaseKey("name")
        st.markdown("### :material/download: :orange[Save your Financial Profile]")
        st.markdown(
            """Download every table on this page as one **Household Financial Profile** workbook:
the *Wages and Contributions* sheet for each individual, plus *Debts* and *Fixed Assets*."""
        )
        hfpClicked = st.download_button(
            "Download HFP workbook",
            data=owb.saveContributions(),
            file_name=f"HFP_{caseName}.xlsx",
            help="Excel workbook holding every table on this page, including any column Owl added on load.",
            mime="application/vnd.ms-excel",
            icon=":material/download:",
        )
        st.caption(
            "Your browser chooses where the file lands. To be asked each time, turn on "
            "*Ask where to save each file before downloading* (Chrome, Edge), "
            "*Always ask you where to save files* (Firefox), or *Ask for each download* (Safari)."
        )
        if hfpClicked:
            owb.markHFPAsSaved()
            gcs = owb.getCaseString()
            if gcs:
                kz.storeCaseKey("casetoml", gcs.getvalue())
            # See Reports.py: an st.rerun() here would delete the media file mid-download.

    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar()
