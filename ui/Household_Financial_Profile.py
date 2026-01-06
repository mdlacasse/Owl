"""
Household Financial Profile page for Owl retirement planner Streamlit UI.

This module provides the interface for entering household financial profile
information including wages and contributions.

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
import tomlexamples as tomlex
import case_progress as cp


def loadWCExample(file):
    if file:
        # Use normalized HFP name for the file parameter to match the actual filename
        hfp_name = tomlex.getHFPName(file)
        mybytesio = tomlex.loadWagesExample(file)
        if mybytesio is not None:
            owb.readContributions(mybytesio, file=hfp_name)


ret = kz.titleBar(":material/home: Household Financial Profile")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.getCaseKey("timeList0") is None:
        kz.runOncePerCase(owb.resetTimeLists)
    kz.initCaseKey("stTimeLists", None)
    # Initialize houseLists if they don't exist
    kz.initCaseKey("houseListDebts", None)
    kz.initCaseKey("houseListFixedAssets", None)
    n = 2 if kz.getCaseKey("status") == "married" else 1

    if kz.getCaseKey("stTimeLists") is None:
        original = kz.getCaseKey("timeListsFileName")
        if original is None or original == "None":
            st.info(
                f"Case *'{kz.currentCaseName()}'* makes no reference to a Household Financial Profile.\n\n"
                "You can build your own HPF by directly filling the table(s) below. "
                "Once a case has been successfully run, values can be saved on the **Output Files** page. "
                "Alternatively, you can start from this Excel "
                "[template](https://github.com/mdlacasse/Owl/blob/main/examples/HFP_template.xlsx?raw=true) "
                "and upload the file using the widget below."
            )
        elif original != "edited values":
            st.info(f"""Case *'{kz.currentCaseName()}'* refers to file *'{original}'*
that has not yet been uploaded.""")

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### :orange[Upload *Household Financial Profile* Workbook]")
        kz.initCaseKey("_xlsx", 0)
        stTimeLists = st.file_uploader(
            "Upload values from a Household Financial Profile (HFP) workbook...",
            key="_stTimeLists" + str(kz.getCaseKey("_xlsx")),
            type=["xlsx", "ods"],
        )
        if stTimeLists is not None:
            if owb.readContributions(stTimeLists):
                kz.setCaseKey("stTimeLists", stTimeLists)
                # Change key to reset uploader.
                kz.storeCaseKey("_xlsx", kz.getCaseKey("_xlsx") + 1)
                st.rerun()
    with col2:
        tomlexcase = kz.getCaseKey("tomlexcase")
        if tomlexcase is not None and tomlex.hasHFPExample(tomlexcase):
            st.markdown("#### :orange[Load Example HFP Workbook]")
            st.markdown("Read associated HFP workbook.")
            helpmsg = "Load associated HFP workbook from GitHub"
            st.button("Load workbook associated with example case", help=helpmsg,
                      on_click=loadWCExample, args=[tomlexcase])

    st.divider()
    st.markdown("### :material/work_history: :orange[Wages and Contributions]")
    st.markdown("""Wages and contributions for each individual.
Previous five years are only used to track past Roth account contributions and conversions.
This information is needed to enforce the five-year maturation rule in Roth savings accounts.""")

    with st.expander("*Expand Wages and Contributions Timetables*"):
        for i in range(n):
            st.markdown("#### :orange[" + kz.getCaseKey("iname" + str(i)) + "'s Timetable]")
            df = kz.getCaseKey("timeList" + str(i))
            formatdic = {"year": st.column_config.NumberColumn(None, format="%d", disabled=True)}
            cols = list(df.columns)
            for col in cols[1:-1]:
                formatdic[col] = st.column_config.NumberColumn(None, min_value=0.0, format="accounting")
            formatdic[cols[-1]] = st.column_config.NumberColumn(None, format="accounting")

            newdf = st.data_editor(
                df,
                column_config=formatdic,
                hide_index=True,
                key=kz.genCaseKey("wages" + str(i)),
            )
            st.caption("Values are in nominal $.")
            newdf = newdf.fillna(0)
            kz.storeCaseKey("_timeList" + str(i), newdf)

            if not df.equals(newdf):
                kz.setCaseKey("timeList" + str(i), newdf)
                st.rerun()

        st.button("Reset Timetables to zero", help="Reset all values to zero.", on_click=owb.resetTimeLists)

    st.divider()
    st.markdown("### :material/account_balance: :orange[Debts and Fixed Assets]")
    st.markdown("""Debts and fixed assets are associated with the household.""")

    with st.expander("*Expand Debts and Fixed Assets Tables*"):
        st.markdown("#### :orange[Debts]")

        # Get debt types from owlbridge to ensure consistency with validation logic
        debtTypes = owb.getTableTypes("Debts")

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
                help="Enter original load amount ($)",
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
            )
        }

        edited_debtdf = st.data_editor(
            debtdf,
            column_config=debtconf,
            num_rows="dynamic",
            hide_index=True,
            key=kz.genCaseKey("debts")
        )
        tableCaption = """Values are in nominal $. Additional items can be directly entered
in the tables by clicking :material/add: on the last row.
Items can be deleted by selecting rows in the left margin and hitting *Delete*."""
        st.caption(tableCaption)

        # Store edited debts if changed
        if not debtdf.equals(edited_debtdf):
            edited_debtdf = owb.conditionDebtsAndFixedAssetsDF(edited_debtdf, "Debts")
            kz.setCaseKey("houseListDebts", edited_debtdf)
            st.rerun()

        st.divider()
        st.markdown("#### :orange[Fixed Assets]")

        # Get fixed asset types from owlbridge to ensure consistency with validation logic
        fixedTypes = owb.getTableTypes("Fixed Assets")

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
                help="Enter cost basis ($)",
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
                help="Return rate (%)",
                # default=3.0,
                required=True,
                min_value=0.0,
                step=0.01,
            ),
            "yod": st.column_config.NumberColumn(
                "yod",
                help="Year of disposition (y)",
                min_value=thisyear,
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
            fixeddf,
            column_config=fixedconf,
            hide_index=True,
            num_rows="dynamic",
            key=kz.genCaseKey("fixed_assets")
        )
        st.caption(tableCaption)

        # Store edited fixed assets if changed
        if not fixeddf.equals(edited_fixeddf):
            edited_fixeddf = owb.conditionDebtsAndFixedAssetsDF(edited_fixeddf, "Fixed Assets")
            kz.setCaseKey("houseListFixedAssets", edited_fixeddf)
            st.rerun()

    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar()
