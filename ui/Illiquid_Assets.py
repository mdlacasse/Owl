import streamlit as st
import pandas as pd

import sskeys as kz
import owlbridge as owb

ret = kz.titleBar(":material/home: Illiquid Assets")

# if ret is None or kz.caseHasNoPlan():
    # st.info("Case(s) must be first created before running this page.")
# else:
if True:
    st.write("#### :orange[Assets]")

    alltypes = ["residence", "stocks", "precious metal", "art"]

    df = pd.DataFrame([
                   {"name": "house",
                    "type": "residence",
                   "basis": 200,
                   "value": 500,
                  "growth": 2,
                     "yod": 2050}
                      ])

    conf = {
        "name": st.column_config.TextColumn(
            "Name of asset",
            required=True,
        ),
        "type": st.column_config.SelectboxColumn(
            "type of asset",
            help="Select type of asset",
            # default=1,
            required=True,
            options=alltypes,
        ),
        "basis": st.column_config.NumberColumn(
            "basis",
            help="Enter number in k$",
            min_value=0,
            default=0,
            step=1.,
        ),
        "value": st.column_config.NumberColumn(
            "value",
            help="Enter number in k$",
            default=0,
            min_value=0,
            step=1.,
        ),
        "growth": st.column_config.NumberColumn(
            "growth",
            help="Enter growth (%)",
            default="3",
            min_value=0,
            step=.1,
        ),
        "yod": st.column_config.NumberColumn(
            "yod",
            help="Year of disposition",
            min_value=0,
            default=2025,
            step=1,
        ),
    }

    edited_df = st.data_editor(df, column_config=conf, num_rows="dynamic", hide_index=True)
