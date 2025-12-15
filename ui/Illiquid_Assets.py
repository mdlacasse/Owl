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

    alltypes = ["residence", "stocks", "precious metal", "art", "annuity"]

    df = pd.DataFrame([
                   {"name": "house",
                    "type": "residence",
                   "basis": 200.0,
                   "value": 500.0,
                  "growth": 2.0,
                     "yod": 2050,
              "commission": 5.0,}
                      ])

    conf = {
        "name": st.column_config.TextColumn(
            "Name of asset",
            help="Give a unique name to your asset",
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
            help="Year of disposition, or time frame (y)",
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

    edited_df = st.data_editor(df, column_config=conf, num_rows="dynamic", hide_index=True)
