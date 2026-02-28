"""
Create Case page for Owl retirement planner Streamlit UI.

This module provides the interface for creating new retirement planning cases
or uploading existing case files.

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

from io import StringIO
import streamlit as st

import sskeys as kz
import owlbridge as owb
import tomlexamples as tomlex
import case_progress as cp


def _loadHFPExample(file):
    if file:
        hfp_name = tomlex.getHFPName(file)
        mybytesio = tomlex.loadWagesExample(file)
        if mybytesio is not None:
            owb.readHFP(mybytesio, file=hfp_name)


ret = kz.titleBar(":material/person_add: Create Case")

if ret is None:
    st.info(
        "#### Start here\n\n"
        "Create a new case by providing a name below, or load one from a TOML case file,"
        " or simply load one of the example files available.\n\n"
        "*Consult at the :material/help: [Documentation](Documentation) for more details.*"
    )
    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown("#### :orange[Create a New Case]")
        st.text_input(
            "Case name",
            key="_newcase",
            on_change=kz.createNewCase,
            args=["newcase"],
            placeholder="Enter a short case name...",
        )
    with col2:
        st.markdown("#### :orange[Upload Your Own Case File]")
        kz.initGlobalKey("_confile_idx", 0)
        file = st.file_uploader(
            "Upload *case* parameter file...",
            key="_confile" + str(kz.getGlobalKey("_confile_idx")),
            type=["toml"],
        )
        if file is not None:
            owb.ui_log(f"Loading case file: '{file.name}'")
            mystringio = StringIO(file.read().decode("utf-8"))
            if kz.createCaseFromFile(mystringio):
                # Bump uploader key to avoid re-import on rerun.
                kz.storeGlobalKey("_confile_idx", kz.getGlobalKey("_confile_idx") + 1)
                st.rerun()
    with col3:
        st.markdown("#### :orange[Load a Case Example]")
        kz.initGlobalKey("_example_case_idx", 0)
        case = st.selectbox(
            "Examples available from GitHub",
            tomlex.cases,
            index=None,
            key="_example_case" + str(kz.getGlobalKey("_example_case_idx")),
            placeholder="Select an example case")
        if case:
            owb.ui_log(f"Loading example: '{case}'")
            mystringio = tomlex.loadCaseExample(case)
            if kz.createCaseFromFile(mystringio):
                kz.storeGlobalKey("_example_case_idx", kz.getGlobalKey("_example_case_idx") + 1)
                kz.initCaseKey("tomlexcase", case)
                st.rerun()
else:
    with st.expander(":material/add: *Create or load another case*"):
        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            st.markdown("#### :orange[Create a New Case]")
            st.text_input(
                "Case name",
                key="_newcase",
                on_change=kz.createNewCase,
                args=["newcase"],
                placeholder="Enter a short case name...",
            )
        with col2:
            st.markdown("#### :orange[Upload Your Own Case File]")
            kz.initGlobalKey("_confile_idx", 0)
            file = st.file_uploader(
                "Upload *case* parameter file...",
                key="_confile" + str(kz.getGlobalKey("_confile_idx")),
                type=["toml"],
            )
            if file is not None:
                owb.ui_log(f"Loading case file: '{file.name}'")
                mystringio = StringIO(file.read().decode("utf-8"))
                if kz.createCaseFromFile(mystringio):
                    kz.storeGlobalKey("_confile_idx", kz.getGlobalKey("_confile_idx") + 1)
                    st.rerun()
        with col3:
            st.markdown("#### :orange[Load a Case Example]")
            kz.initGlobalKey("_example_case_idx", 0)
            case = st.selectbox(
                "Examples available from GitHub",
                tomlex.cases,
                index=None,
                key="_example_case" + str(kz.getGlobalKey("_example_case_idx")),
                placeholder="Select an example case")
            if case:
                owb.ui_log(f"Loading example: '{case}'")
                mystringio = tomlex.loadCaseExample(case)
                if kz.createCaseFromFile(mystringio):
                    kz.storeGlobalKey("_example_case_idx", kz.getGlobalKey("_example_case_idx") + 1)
                    kz.initCaseKey("tomlexcase", case)
                    st.rerun()

    st.markdown("#### :orange[Description and Life Parameters]")
    casemsg = "Case name can be changed by editing it directly."
    col1, col2 = st.columns(2, gap="large")
    with col1:
        kz.storeGlobalKey("caseNewName", kz.currentCaseName())
        name = st.text_input(
            "Case name",
            on_change=kz.renameCase,
            args=["caseNewName"],
            key="caseNewName",
            help=casemsg,
        )

    diz1 = kz.getCaseKey("plan") is not None
    diz2 = diz1
    with col2:
        statusChoices = ["single", "married"]
        kz.initCaseKey("status", statusChoices[0])
        st.radio(
            "Marital status",
            statusChoices,
            disabled=diz2,
            index=statusChoices.index(kz.getCaseKey("status")),
            key=kz.genCaseKey("status"),
            on_change=kz.setpull,
            args=["status"],
            horizontal=True,
        )

    kz.initCaseKey("description", "")
    helpmsg = "Provide a short distinguishing description for the case."
    description = kz.getLongText("Brief description", "description", help=helpmsg,
                                 placeholder="Enter a brief description...")

    namehelp = "Use first name or just a nickname."
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        kz.initCaseKey("iname0", "")
        if kz.getCaseKey("iname0") == "":
            st.info("First name must be provided.")

        iname0 = kz.getText("Your first name", "iname0", help=namehelp,
                            disabled=diz2, placeholder="Enter name...")

        datemsg = """
Calculations are the same if you were born on any day after the 2nd of the month.
Social Security has special rules for those born on the 1st or 2nd.
Ask your favorite AI about it if you're curious.
"""
        longmsg = """See the documentation for suggested resources on estimating longevity."""
        if iname0:
            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
            with incol1:
                kz.initCaseKey("dob0", "1965-01-15")
                ret = kz.getDate(f"{iname0}'s date of birth", "dob0",
                                 min_value="1945-01-01", max_value="2000-12-31", help=datemsg, disabled=diz2)

            with incol2:
                kz.initCaseKey("life0", 80)
                ret = kz.getIntNum(f"{iname0}'s expected longevity", "life0",
                                   max_value=120, help=longmsg, disabled=diz1)

    with col2:
        if kz.getCaseKey("status") == "married":
            kz.initCaseKey("iname1", "")
            if kz.getCaseKey("iname1") == "":
                st.info("First name must be provided.")

            iname1 = kz.getText("Your spouse's first name", "iname1", help=namehelp,
                                disabled=diz2, placeholder="Enter a name...")

            if iname1:
                incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
                with incol1:
                    kz.initCaseKey("dob1", "1965-01-15")
                    ret = kz.getDate(f"{iname1}'s date of birth", "dob1",
                                     min_value="1945-01-01", max_value="2000-12-31", help=datemsg, disabled=diz2)

                with incol2:
                    kz.initCaseKey("life1", 80)
                    ret = kz.getIntNum(f"{iname1}'s expected longevity", "life1",
                                       max_value=120, help=longmsg, disabled=diz1)

    st.divider()
    cantcreate = kz.isIncomplete() or diz1
    if not cantcreate and kz.getCaseKey("plan") is None:
        st.info("""Any parameter on this page can now be changed, including the case name.
Once changes are complete click the `Create case` button."""
                )

    cantcopy = kz.caseHasNoPlan()

    # HFP uploader section: shown when plan exists but no HFP has been loaded yet.
    if kz.caseHasPlan() and kz.getCaseKey("stTimeLists") is None:
        st.markdown("#### :orange[Upload Financial Profile (Optional)]")
        hfp_col1, hfp_col2 = st.columns(2, gap="large")
        with hfp_col1:
            st.markdown("##### :orange[Upload *Household Financial Profile* Workbook]")
            kz.initCaseKey("_xlsx", 0)
            stTimeLists = st.file_uploader(
                "Upload values from a Household Financial Profile (HFP) workbook...",
                key="_stTimeLists" + str(kz.getCaseKey("_xlsx")),
                type=["xlsx", "ods"],
                help=(
                    "An Excel (.xlsx) or OpenDocument (.ods) workbook with one sheet per individual "
                    "containing year-by-year wages, retirement contributions, Roth conversions, and large expenses, "
                    "plus optional household sheets for debts and fixed assets."
                ),
            )
            if stTimeLists is not None:
                if owb.readHFP(stTimeLists):
                    kz.setCaseKey("stTimeLists", stTimeLists)
                    kz.storeCaseKey("_xlsx", kz.getCaseKey("_xlsx") + 1)
                    st.rerun()
        with hfp_col2:
            tomlexcase = kz.getCaseKey("tomlexcase")
            if tomlexcase is not None and tomlex.hasHFPExample(tomlexcase):
                st.markdown("##### :orange[Load Example HFP Workbook]")
                st.markdown("Read associated HFP workbook.")
                helpmsg = "Load associated HFP workbook from GitHub"
                st.button("Load workbook associated with example case", help=helpmsg,
                          key="create_hfp_example_btn",
                          on_click=_loadHFPExample, args=[tomlexcase])
        st.divider()

    col1, col2, col3 = st.columns(3, gap="small", vertical_alignment="top")
    with col1:
        helpmsg = """`Copy parameters` carries over all parameters to a new case.
Click the `Create case` button once all parameters on this page are right."""
        st.button("Copy parameters :material/content_copy:", on_click=kz.copyCase,
                  disabled=cantcopy, help=helpmsg)
    with col2:
        helpmsg = "`Create case` opens up all other pages in the **Plan Setup** section."
        st.button("Create case :material/add:", on_click=owb.createPlan, disabled=cantcreate,
                  type='primary', help=helpmsg)

    with col3:
        kz.initGlobalKey("delete_confirmation_active", False)

        # Show confirmation buttons if delete was activated
        if kz.getGlobalKey("delete_confirmation_active"):
            conf_col1, conf_col2 = st.columns(2, gap="small")
            with conf_col1:
                helpmsg = ":warning: Caution: The `Delete case` operation cannot be undone."
                if st.button("Delete :material/delete:", type="primary", help=helpmsg):
                    kz.storeGlobalKey("delete_confirmation_active", False)
                    kz.deleteCurrentCase()
                    st.rerun()
            with conf_col2:
                helpmsg = "Click to cancel `Delete` operation."
                if st.button("Cancel", help=helpmsg):
                    kz.storeGlobalKey("delete_confirmation_active", False)
                    st.rerun()
        else:
            # Show initial delete button
            helpmsg = "Click to delete current case."
            if st.button("Delete case :material/delete:", help=helpmsg):
                kz.storeGlobalKey("delete_confirmation_active", True)
                st.rerun()

# Show progress bar at bottom (only when a case is selected)
if ret is not None:
    cp.show_progress_bar()
