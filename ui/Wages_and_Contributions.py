import streamlit as st

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar(":material/work_history: Wages and Contributions")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.getKey("timeList0") is None:
        kz.runOncePerCase(owb.resetTimeLists)
    kz.initKey("stTimeLists", None)
    n = 2 if kz.getKey("status") == "married" else 1

    if kz.getKey("stTimeLists") is None:
        original = kz.getKey("timeListsFileName")
        if original is None or original == "None":
            st.info(
                f"Case *'{kz.currentCaseName()}'* makes no reference to a wages and contributions file.\n\n"
                "You can build your own file by directly filling the table(s) below. "
                "Once a case has been successfully run, values can be saved on the **Output Files** page. "
                "Alternatively, you can start from this Excel "
                "[template](https://raw.github.com/mdlacasse/Owl/main/examples/template.xlsx) "
                "and upload the file using the widget below."
            )
        elif original != "edited values":
            st.info(
                f"Case *'{kz.currentCaseName()}'* refers to Wages and Contributions file *'{original}'*"
                " that has not yet been uploaded."
            )

    st.write("#### :orange[Upload a *Wages and Contributions* File]")
    kz.initKey("_xlsx", 0)
    stTimeLists = st.file_uploader(
        "Upload values from a Wages and Contributions file...",
        key="_stTimeLists" + str(kz.getKey("_xlsx")),
        type=["xlsx", "ods"],
    )
    if stTimeLists is not None:
        if owb.readContributions(stTimeLists):
            kz.setKey("stTimeLists", stTimeLists)
            # Change key to reset uploader.
            kz.storeKey("_xlsx", kz.getKey("_xlsx") + 1)
            st.rerun()

    st.divider()
    for i in range(n):
        st.write("#### :orange[" + kz.getKey("iname" + str(i)) + "'s Timetable]")
        st.write("""Previous 5 years are used to input past contributions and conversions to Roth accounts.
 This information is needed to enforce the 5-year maturation rule in Roth savings accounts.""")
        df = kz.getKey("timeList" + str(i))
        formatdic = {"year": st.column_config.NumberColumn(None, format="%d", disabled=True)}
        cols = list(df.columns)
        for col in cols[1:-1]:
            formatdic[col] = st.column_config.NumberColumn(None, min_value=0.0, format="accounting")
        formatdic[cols[-1]] = st.column_config.NumberColumn(None, format="accounting")

        newdf = st.data_editor(
            df,
            column_config=formatdic,
            hide_index=True,
            key=kz.currentCaseName() + "_wages" + str(i),
        )
        st.caption("Values are in nominal $.")
        newdf.fillna(0, inplace=True)
        kz.storeKey("_timeList" + str(i), newdf)

        if not df.equals(newdf):
            kz.setKey("timeList" + str(i), newdf)
            st.rerun()

    st.button("Reset to zero", help="Reset all values to zero.", on_click=owb.resetTimeLists)
