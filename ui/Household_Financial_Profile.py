import streamlit as st
import pandas as pd
from datetime import date

import sskeys as kz
import owlbridge as owb
import tomlexamples as tomlex


def loadWCExample(file):
    if file:
        mybytesio = tomlex.loadWagesExample(file)
        owb.readContributions(mybytesio, file=file)


ret = kz.titleBar(":material/home: Household Financial Profile")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.getCaseKey("timeList0") is None:
        kz.runOncePerCase(owb.resetTimeLists)
    kz.initCaseKey("stTimeLists", None)
    n = 2 if kz.getCaseKey("status") == "married" else 1

    if kz.getCaseKey("stTimeLists") is None:
        original = kz.getCaseKey("timeListsFileName")
        if original is None or original == "None":
            st.info(
                f"Case *'{kz.currentCaseName()}'* makes no reference to a Household Financial Profile.\n\n"
                "You can build your own file by directly filling the table(s) below. "
                "Once a case has been successfully run, values can be saved on the **Output Files** page. "
                "Alternatively, you can start from this Excel "
                "[template](https://github.com/mdlacasse/Owl/blob/main/examples/template.xlsx?raw=true) "
                "and upload the file using the widget below."
            )
        elif original != "edited values":
            st.info(
                f"Case *'{kz.currentCaseName()}'* refers to file *'{original}'*"
                " that has not yet been uploaded."
            )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### :orange[Upload a *Household Financial Profile* (HFP)]")
        kz.initCaseKey("_xlsx", 0)
        stTimeLists = st.file_uploader(
            "Upload values from a HFP file...",
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
        if tomlexcase in tomlex.wages:
            st.markdown("#### :orange[Load Example HFP File]")
            st.markdown("Read associated HFP file.")
            helpmsg = "Load associated HFP file from GitHub"
            st.button("Load file associated with example case", help=helpmsg,
                      on_click=loadWCExample, args=[tomlexcase])

    st.divider()
    st.markdown("### :material/work_history: :orange[Wages and Contributions]")
    st.markdown("""Previous five years are used to input past contributions and conversions to Roth accounts.
This information is needed to enforce the five-year maturation rule in Roth savings accounts.""")

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
            key=kz.currentCaseName() + "_wages" + str(i),
        )
        st.caption("Values are in nominal $.")
        newdf.fillna(0, inplace=True)
        kz.storeCaseKey("_timeList" + str(i), newdf)

        if not df.equals(newdf):
            kz.setCaseKey("timeList" + str(i), newdf)
            st.rerun()

    st.button("Reset Timetables to zero", help="Reset all values to zero.", on_click=owb.resetTimeLists)

    st.divider()
    st.markdown("### :material/account_balance: :orange[Debts and Fixed Assets]")
    st.markdown("""Debts and fixed assets are associated with the household.
Additional items can be directly entered in the tables below by clicking :material/add: on the last row.
Items can be deleted by selecting them in the left column and hitting *Delete*.""")

    st.markdown("#### :orange[Debts]")

    debttypes = ["PR mortgage", "mortgage", "loan"]

    # Just an example
    debtdf = pd.DataFrame([
                   {"name": "mortgage",
                    "type": "PR mortgage",
                    "year": 2020,
                    "term": 15,
                    "amount": 500.0,
                    "rate": 2.0}
                      ])

    thisyear = date.today().year
    debtconf = {
        "name": st.column_config.TextColumn(
            "Name of debt",
            help="Give a unique name to your debt",
            required=True,
        ),
        "type": st.column_config.SelectboxColumn(
            "type of debt",
            help="Select the type of debt from dropdown menu",
            required=True,
            options=debttypes,
        ),
        "year": st.column_config.NumberColumn(
            "start year",
            help="Enter the origination year",
            min_value=1950,
            max_value=thisyear-1,
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
            help="Enter original load amount (k$)",
            default=0.0,
            min_value=0.0,
            step=0.1,
        ),
        "rate": st.column_config.NumberColumn(
            "rate",
            help="Enter annual rate (%)",
            default=4.0,
            min_value=0.0,
            step=0.1,
        )
    }

    edited_df = st.data_editor(debtdf, column_config=debtconf, num_rows="dynamic", hide_index=True)

    st.divider()
    st.markdown("#### :orange[Fixed Assets]")

    fixedtypes = ["residence", "real estate", "precious metals", "stocks", "collectibles", "annuity"]

    # Just an example
    fixeddf = pd.DataFrame([
                   {"name": "house",
                    "type": "residence",
                    "basis": 200.0,
                    "value": 500.0,
                    "growth": 2.0,
                    "yod": 2050,
                    "commission": 5.0}
                      ])

    fixedconf = {
        "name": st.column_config.TextColumn(
            "Name of fixed asset",
            help="Give a unique name to your fixed asset",
            required=True,
        ),
        "type": st.column_config.SelectboxColumn(
            "type of asset",
            help="Select the type of fixed asset from dropdown menu",
            # default=1,
            required=True,
            options=fixedtypes,
        ),
        "basis": st.column_config.NumberColumn(
            "basis",
            help="Enter cost basis (k$)",
            min_value=0.0,
            default=0.0,
            step=0.1,
        ),
        "value": st.column_config.NumberColumn(
            "value",
            help="Enter current value (k$)",
            default=0.0,
            min_value=0.0,
            step=0.1,
        ),
        "growth": st.column_config.NumberColumn(
            "growth",
            help="Enter growth rate (%)",
            default=3.0,
            min_value=0.0,
            step=0.1,
        ),
        "yod": st.column_config.NumberColumn(
            "yod",
            help="Year or time frame for disposition (y)",
            min_value=0,
            default=2025,
            step=1,
        ),
        "commission": st.column_config.NumberColumn(
            "commission",
            help="Sale commission (%)",
            min_value=0.0,
            max_value=10.0,
            default=0.0,
            step=0.1,
        ),
    }

    edited_df = st.data_editor(fixeddf, column_config=fixedconf, num_rows="dynamic", hide_index=True)
