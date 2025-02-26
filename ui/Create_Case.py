from datetime import date
from io import StringIO
import streamlit as st

import sskeys as kz
import owlbridge as owb
import tomlexamples as tomlex


caseChoices = kz.allCaseNames()
ret = kz.titleBar("Create Case", caseChoices)

if ret == kz.newCase:
    st.info("#### Starting a new case from scratch.\n\n" "A name for the scenario must first be provided.")
    st.text_input(
        "Case name",
        value="",
        key="_newcase",
        on_change=kz.createNewCase,
        args=["newcase"],
        placeholder="Enter a case name...",
    )
elif ret == kz.loadCaseFile:
    # "<a href="Documentation" target="_self">Documentation</a>", unsafe_allow_html=True)
    st.info(
        "#### Starting a case from a *case* parameter file.\n\n"
        "Upload your own case or select one from multiple examples."
        " Alternatively, you can select `New Case...` in the margin selector box to start a case from scratch.\n\n"
        "Look at the :material/help: [Documentation](Documentation) for more details."
    )
    st.write("#### Upload your own case file")
    file = st.file_uploader("Upload *case* parameter file...", key="_confile", type=["toml"])
    if file is not None:
        mystringio = StringIO(file.read().decode("utf-8"))
        if kz.createCaseFromFile(mystringio):
            st.rerun()

    st.write("#### Load a case example")
    case = st.selectbox("Examples available from GitHub", tomlex.cases, index=None, placeholder="Select a case")
    if case is not None:
        mystringio = tomlex.loadExample(case)
        if kz.createCaseFromFile(mystringio):
            st.rerun()
else:
    helpmsg = "Case name can be changed by editing it directly."
    col1, col2 = st.columns(2, gap="large")
    with col1:
        name = st.text_input(
            "Case name",
            value=kz.currentCaseName(),
            on_change=kz.renameCase,
            args=["caseNewName"],
            key="_caseNewName",
            help=helpmsg,
        )

    diz1 = kz.getKey("plan") is not None
    diz2 = diz1
    # diz2 = (diz1 or len(kz.allCaseNames()) > 3)
    with col2:
        statusChoices = ["single", "married"]
        kz.initKey("status", statusChoices[0])
        st.radio(
            "Marital status",
            statusChoices,
            disabled=diz2,
            index=statusChoices.index(kz.getKey("status")),
            key="_status",
            on_change=kz.setpull,
            args=["status"],
            horizontal=True,
        )

    kz.initKey("description", "")
    helpmsg = "Provide a short distinguishing description for the case."
    description = kz.getLongText("Brief description", "description", help=helpmsg,
                                 placeholder="Enter a brief description...")

    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        kz.initKey("iname0", "")
        if kz.getKey("iname0") == "":
            st.info("First name must be provided.")

        iname0 = kz.getText("Your first name", "iname0", disabled=diz2, placeholder="Enter name...")

        kz.initKey("yob0", 1965)
        ret = kz.getIntNum(f"{iname0}'s birth year", "yob0", disabled=diz2)

        kz.initKey("life0", 80)
        ret = kz.getIntNum(f"{iname0}'s expected longevity", "life0", disabled=diz1)

        today = date.today()
        thisyear = today.year
        kz.initKey("startDate", today)
        ret = st.date_input(
            "Plan's starting date on first year",
            min_value=date(thisyear, 1, 1),
            max_value=date(thisyear, 12, 31),
            value=kz.getKey("startDate"),
            key="_startDate",
            args=["startDate"],
            on_change=kz.setpull,
            disabled=diz2,
        )

    with col2:
        if kz.getKey("status") == "married":
            kz.initKey("iname1", "")
            if kz.getKey("iname1") == "":
                st.info("First name must be provided.")

            iname1 = kz.getText("Your spouse's first name", "iname1", disabled=diz2, placeholder="Enter a name...")

            kz.initKey("yob1", 1965)
            ret = kz.getIntNum(f"{iname1}'s birth year", "yob1", disabled=diz2)

            kz.initKey("life1", 80)
            ret = kz.getIntNum(f"{iname1}'s expected longevity", "life1", disabled=diz1)

    st.divider()
    cantcreate = kz.isIncomplete() or diz1
    if not cantcreate and kz.getKey("plan") is None:
        st.info("Plan needs to be created once all the information needed has been entered.")

    cantmodify = kz.currentCaseName() == kz.newCase or kz.currentCaseName() == kz.loadCaseFile
    cantcopy = cantmodify or kz.caseHasNoPlan()
    col1, col2, col3 = st.columns(3, gap="small", vertical_alignment="top")
    with col1:
        st.button("Create case :material/add:", on_click=owb.createPlan, disabled=cantcreate)
    with col2:
        st.button("Duplicate case :material/content_copy:", on_click=kz.duplicateCase, disabled=cantcopy)
    with col3:
        st.button("Delete case :material/delete:", on_click=kz.deleteCurrentCase, disabled=cantmodify)
