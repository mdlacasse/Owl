"""
Create Case page for Owl retirement planner Streamlit UI.

This module provides the interface for creating new retirement planning cases
or uploading existing case files.

Copyright (C) 2025-2026 The Owl Authors

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


@st.cache_data
def _state_choices():
    from owlplanner import tax_state as _ts
    return [""] + _ts.valid_states()


def _loadHFPExample(file):
    if file:
        hfp_name = tomlex.getHFPName(file)
        mybytesio = tomlex.loadWagesExample(file)
        if mybytesio is not None:
            owb.readHFP(mybytesio, file=hfp_name)


def _render_case_loader():
    st.markdown("##### Select a tab below to load one of the available case examples,"
                " create a new case, or upload an existing TOML case file.")
    st.caption("Consult the :material/help: [Documentation](Documentation) for more details.")
    tab1, tab2, tab3 = st.tabs(["_Load a Case Example_", "_Create a New Case_", "_Upload Your Own Case File_"])
    with tab1:
        col, hint = st.columns([2, 3], gap="large", vertical_alignment="bottom")
        with col:
            kz.initGlobalKey("_example_case_idx", 0)
            case = st.selectbox(
                "Examples available from GitHub",
                tomlex.cases,
                index=None,
                key="_example_case" + str(kz.getGlobalKey("_example_case_idx")),
                placeholder="Select an example case")
        with hint:
            st.caption("Load a pre-built case from GitHub. Most parameters can be adjusted after loading.")
        if case:
            owb.ui_log(f"Loading example: '{case}'")
            mystringio = tomlex.loadCaseExample(case)
            if kz.createCaseFromFile(mystringio):
                kz.storeGlobalKey("_example_case_idx", kz.getGlobalKey("_example_case_idx") + 1)
                kz.initCaseKey("tomlexcase", case)
                st.rerun()
    with tab2:
        col, hint = st.columns([2, 3], gap="large", vertical_alignment="bottom")
        with col:
            st.text_input(
                "Case name",
                key="_newcase",
                on_change=kz.createNewCase,
                args=["newcase"],
                placeholder="Enter a short case name...",
            )
        with hint:
            st.caption("Enter a short name to start a blank case. Life parameters and financials are filled in next.")
    with tab3:
        col, hint = st.columns([2, 3], gap="large", vertical_alignment="bottom")
        with col:
            kz.initGlobalKey("_confile_idx", 0)
            file = st.file_uploader(
                "Upload *case* parameter file...",
                key="_confile" + str(kz.getGlobalKey("_confile_idx")),
                type=["toml"],
            )
        with hint:
            st.caption("Upload a TOML case file previously saved from Owl.")
        if file is not None:
            owb.ui_log(f"Loading case file: '{file.name}'")
            mystringio = StringIO(file.read().decode("utf-8"))
            if kz.createCaseFromFile(mystringio):
                # Bump uploader key to avoid re-import on rerun.
                kz.storeGlobalKey("_confile_idx", kz.getGlobalKey("_confile_idx") + 1)
                st.rerun()


ret = kz.titleBar(":material/person_add: Create Case")

if ret is None:
    _render_case_loader()
else:
    with st.expander("_Create or load another case_"):
        _render_case_loader()

    st.markdown("#### :orange[Description and Life Parameters]")
    casemsg = "Case name can be changed by editing it directly."
    col1, col2, col3 = st.columns((2, 1, 1), gap="large")
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
    kz.initCaseKey("state", "")
    _state_help = (
        "Select your state to include state income taxes in the plan. "
        "Leave blank to model federal taxes only. "
        "No-income-tax states (AK, FL, NV, NH, SD, TN, TX, WA, WY) are listed too and produce zero state tax. "
        "See the documentation for the details and limitations of state-tax modeling."
    )
    with col3:
        kz.getSelectbox("State of residence (for state taxes)", _state_choices(), "state",
                        help=_state_help)


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
See SSA documentation for details.
"""
        longmsg = "See the documentation for suggested resources on estimating longevity."
        sexmsg = "Sex is a required input for stochastic lifespan modeling."
        if iname0:
            incol1, incol2, incol3 = st.columns((1, 1, .7), gap="large", vertical_alignment="top")
            with incol1:
                kz.initCaseKey("dob0", "1965-01-15")
                ret = kz.getDate(f"{iname0}'s date of birth", "dob0",
                                 min_value="1945-01-01", max_value="2000-12-31", help=datemsg, disabled=diz2)

            with incol2:
                kz.initCaseKey("life0", 89)
                ret = kz.getIntNum(f"{iname0}'s expected longevity", "life0",
                                   max_value=120, help=longmsg, disabled=diz1)

            with incol3:
                kz.initCaseKey("sex0", "F")
                kz.getSelectbox(f"{iname0}'s sex", ["M", "F"], "sex0",
                                help=sexmsg, disabled=diz2)

    with col2:
        if kz.getCaseKey("status") == "married":
            kz.initCaseKey("iname1", "")
            if kz.getCaseKey("iname1") == "":
                st.info("First name must be provided.")

            iname1 = kz.getText("Your spouse's first name", "iname1", help=namehelp,
                                disabled=diz2, placeholder="Enter a name...")

            if iname1:
                incol1, incol2, incol3 = st.columns((1, 1, .7), gap="large", vertical_alignment="top")
                with incol1:
                    kz.initCaseKey("dob1", "1965-01-15")
                    ret = kz.getDate(f"{iname1}'s date of birth", "dob1",
                                     min_value="1945-01-01", max_value="2000-12-31", help=datemsg, disabled=diz2)

                with incol2:
                    kz.initCaseKey("life1", 89)
                    ret = kz.getIntNum(f"{iname1}'s expected longevity", "life1",
                                       max_value=120, help=longmsg, disabled=diz1)

                with incol3:
                    kz.initCaseKey("sex1", "M")
                    kz.getSelectbox(f"{iname1}'s sex", ["M", "F"], "sex1",
                                    help=sexmsg, disabled=diz2)

    st.divider()
    cantcreate = kz.isIncomplete() or diz1
    if not cantcreate and kz.getCaseKey("plan") is None:
        st.info("""Any parameter on this page can now be changed, including the case name.
Once changes are complete, click the `Create case` button."""
                )

    cantcopy = kz.caseHasNoPlan()

    # HFP uploader section: shown when plan exists but no HFP has been loaded yet.
    if kz.caseHasPlan() and kz.getCaseKey("stHFP") is None:
        st.markdown("#### :orange[Upload Financial Profile (Optional)]")
        hfp_col1, hfp_col2 = st.columns(2, gap="large")
        with hfp_col1:
            st.markdown("##### :orange[Upload *Household Financial Profile* Workbook]")
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
                    kz.storeCaseKey("_xlsx", kz.getCaseKey("_xlsx") + 1)
                    st.rerun()
        with hfp_col2:
            tomlexcase = kz.getCaseKey("tomlexcase")
            if tomlexcase is not None and tomlex.hasHFPExample(tomlexcase):
                st.markdown("##### :orange[Load Example HFP Workbook]")
                st.markdown("Read associated HFP workbook.")
                helpmsg = "Load associated *Household Financial Profile* workbook from GitHub."
                st.button("Load example workbook", help=helpmsg, type="primary",
                          key="create_hfp_example_btn",
                          on_click=_loadHFPExample, args=[tomlexcase])
        st.divider()

    col1, col2, col3 = st.columns(3, gap="small", vertical_alignment="top")
    with col1:
        helpmsg = """`Copy parameters` carries over all parameters to a new case.
Then, click on the `Create case` button once all parameters on this page are set."""
        st.button("Copy parameters :material/content_copy:", on_click=kz.copyCase,
                  disabled=cantcopy, help=helpmsg)
    with col2:
        helpmsg = "`Create case` opens up all other pages in the **Case Setup** section."
        st.button("Create case :material/add:", on_click=owb.createPlan, disabled=cantcreate,
                  type='primary', help=helpmsg)

    with col3:
        helpmsg = "`Delete case` removes all parameters associated with the case."
        with st.popover("Delete case :material/delete:", help=helpmsg):
            st.warning("This cannot be undone.", icon=":material/warning:")
            if st.button("Confirm delete", type="primary"):
                kz.deleteCurrentCase()
                st.rerun()

# Show progress bar at bottom (only when a case is selected)
if ret is not None:
    cp.show_progress_bar()
