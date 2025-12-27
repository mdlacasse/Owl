from io import StringIO
import streamlit as st

import sskeys as kz
import owlbridge as owb
import tomlexamples as tomlex
import case_progress as cp

from loguru import logger


ret = kz.titleBar(":material/person_add: Create Case", allCases=True)

if ret == kz.newCase:
    st.info("#### Starting a new case from scratch.\n\n" "A name for the scenario must first be provided.")
    st.text_input(
        "Case name",
        key="_newcase",
        on_change=kz.createNewCase,
        args=["newcase"],
        placeholder="Enter a short case name...",
    )
elif ret == kz.loadCaseFile:
    st.info(
        "#### Starting a case from a *case* parameter file.\n\n"
        "Upload your own case or select one from multiple examples."
        " Alternatively, you can select `New Case...` in the top selector box to start a case from scratch.\n\n"
        "Look at the :material/help: [Documentation](Documentation) for more details."
    )
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### :orange[Upload Your Own Case File]")
        file = st.file_uploader("Upload *case* parameter file...", key="_confile", type=["toml"])
        if file is not None:
            logger.info(f"Loading case file: '{file.name}'")
            mystringio = StringIO(file.read().decode("utf-8"))
            if kz.createCaseFromFile(mystringio):
                st.rerun()

    with col2:
        st.markdown("#### :orange[Load a Case Example]")
        case = st.selectbox("Examples available from GitHub", tomlex.cases, index=None,
                            placeholder="Select an example case")
        if case:
            logger.info(f"Loading example: '{case}'")
            mystringio = tomlex.loadCaseExample(case)
            if kz.createCaseFromFile(mystringio):
                kz.initCaseKey("tomlexcase", case)
                st.rerun()
else:
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
    # diz2 = (diz1 or len(kz.allCaseNames()) > 3)
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

    namehelp = "Use first name or just a nick name."
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        kz.initCaseKey("iname0", "")
        if kz.getCaseKey("iname0") == "":
            st.info("First name must be provided.")

        iname0 = kz.getText("Your first name", "iname0", help=namehelp,
                            disabled=diz2, placeholder="Enter name...")

        if iname0:
            datemsg = """
Calculations are the same if you were born any time after the 2nd of the month.
SS has edge cases for those born on the 1st or the 2nd.
Ask your favorite AI about it if you're curious.
"""
            longmsg = """There are good resources for estimating longevity on the internet.
Look at the documentation for some suggestions."""
            incol1, incol2 = st.columns(2, gap="large", vertical_alignment="top")
            with incol1:
                kz.initCaseKey("dob0", "1965-01-15")
                ret = kz.getDate(f"{iname0}'s date of birth", "dob0",
                                 min_value="1945-01-01", max_value="2000-12-31", help=datemsg, disabled=diz2)

            with incol2:
                kz.initCaseKey("life0", 80)
                ret = kz.getIntNum(f"{iname0}'s expected longevity", "life0", help=longmsg, disabled=diz1)

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
                    ret = kz.getIntNum(f"{iname1}'s expected longevity", "life1", help=longmsg, disabled=diz1)

    st.divider()
    cantcreate = kz.isIncomplete() or diz1
    if not cantcreate and kz.getCaseKey("plan") is None:
        st.info("""Any parameter on this page can now be changed, including the case name.
Once changes are complete hit the `Create case` button."""
                )

    cantmodify = kz.currentCaseName() == kz.newCase or kz.currentCaseName() == kz.loadCaseFile
    cantcopy = cantmodify or kz.caseHasNoPlan()
    if not cantcopy and kz.getCaseKey("stTimeLists") is None:
        st.info("Reminder to upload the *Household Financial Profile* (if any) before creating a copy.")

    col1, col2, col3 = st.columns(3, gap="small", vertical_alignment="top")
    with col1:
        helpmsg = """`Copy case` carries over all parameters to a new case.
Hit the `Create case` button once all parameters on this page are right."""
        st.button("Copy case :material/content_copy:", on_click=kz.copyCase,
                  disabled=cantcopy, help=helpmsg)
    with col2:
        helpmsg = "`Create case` opens up all other pages in the **Case Setup** section."
        st.button("Create case :material/add:", on_click=owb.createPlan, disabled=cantcreate, help=helpmsg)

    with col3:
        helpmsg = ":warning: Caution: The `Delete case` operation cannot be undone."
        st.button("Delete case :material/delete:", on_click=kz.deleteCurrentCase, disabled=cantmodify, help=helpmsg)

# Show progress bar at bottom (always shown on Create Case page)
cp.show_progress_bar()

