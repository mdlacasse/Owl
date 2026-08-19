"""
Spending vs Bequest page for Owl retirement planner Streamlit UI.

Traces the trade-off between net spending and the estate left behind, by sweeping
the bequest floor under the maximum-spending objective. Every point on the curve is
a full optimization, so the plot shows a real trade-off rather than a single
operating point.

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

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar(":material/balance: Spending vs Bequest")

if ret is None or kz.caseHasNoPlan():
    kz.no_case_info()
else:
    kz.initCaseKey("frontier_scenario_method", "deterministic")
    kz.initCaseKey("frontier_bequest_grid", "0, 500, 1000, 2000, 4000")
    kz.initCaseKey("frontier_ystart", owb.FROM)
    kz.initCaseKey("frontier_yend", owb.TO)
    kz.initCaseKey("frontier_N_mc", 100)
    kz.initCaseKey("frontier_seed", None)
    kz.initCaseKey("frontier_with_duals", False)
    kz.initCaseKey("frontierPlot", None)
    kz.initCaseKey("frontierSummary", None)
    kz.initCaseKey("frontierData", None)

    st.markdown("""
Every dollar reserved for an estate is a dollar not spent. This page traces that
trade-off directly: it re-optimizes the plan at each bequest level you list, and
plots the net spending each one permits.

Read it to answer *what does leaving this inheritance cost me?*, or the reverse —
*if I spend this much, what is left behind?*
""")

    st.markdown("#### :orange[Scenario method]")
    scenario_method = st.radio(
        "Solve each level using",
        options=["deterministic", "historical", "mc"],
        format_func=lambda x: {
            "deterministic": "This case's rates",
            "historical": "Historical range",
            "mc": "Monte Carlo",
        }[x],
        index=["deterministic", "historical", "mc"].index(
            kz.getCaseKey("frontier_scenario_method") or "deterministic"
        ),
        key=kz.genCaseKey("frontier_scenario_method_radio"),
        label_visibility="collapsed",
        horizontal=True,
    )
    kz.storeCaseKey("frontier_scenario_method", scenario_method)

    if scenario_method == "deterministic":
        st.caption(
            "One solve per bequest level, on the rates this case is configured with. "
            "Fast, but it says nothing about how much the answer depends on when returns arrive."
        )
    else:
        st.caption(
            "Each bequest level is solved across every scenario, so spending is reported at "
            "several success rates. The spread between those curves is sequence-of-returns risk. "
            "This costs one solve per level per scenario, so keep the list of levels short."
        )

    st.markdown("####")
    col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="bottom")
    with col1:
        st.text_input(
            "Bequest levels ($k, comma-separated)",
            value=kz.getCaseKey("frontier_bequest_grid"),
            on_change=kz.storepull,
            args=["frontier_bequest_grid"],
            key=kz.genCaseKey("frontier_bequest_grid"),
            help="Today's dollars, in $k. Each becomes one point on the curve.",
        )
    with col3:
        st.button(
            "Trace frontier",
            on_click=owb.runSpendingBequestFrontier,
            disabled=kz.caseIsNotRunReady(),
        )

    if scenario_method != "deterministic":
        st.markdown("####")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="bottom")
        if scenario_method == "historical":
            yend_max = owb.histYendMax()
            if (kz.getCaseKey("frontier_yend") or 0) > yend_max:
                kz.storeCaseKey("frontier_yend", yend_max)
            with col1:
                st.number_input(
                    "Starting year",
                    min_value=owb.FROM,
                    max_value=kz.getCaseKey("frontier_yend"),
                    value=kz.getCaseKey("frontier_ystart"),
                    on_change=kz.storepull,
                    args=["frontier_ystart"],
                    key=kz.genCaseKey("frontier_ystart"),
                )
            with col2:
                st.number_input(
                    "Ending year",
                    min_value=kz.getCaseKey("frontier_ystart"),
                    max_value=yend_max,
                    value=kz.getCaseKey("frontier_yend"),
                    on_change=kz.storepull,
                    args=["frontier_yend"],
                    key=kz.genCaseKey("frontier_yend"),
                )
        else:
            with col1:
                kz.getIntNum(
                    "Scenarios per level",
                    "frontier_N_mc",
                    callback=kz.storepull,
                    step=50,
                    min_value=10,
                    max_value=2000,
                )

    st.markdown("####")
    with st.expander("*Advanced options*"):
        st.caption("Changing these options will only affect the next run.")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
        with col1:
            kz.getToggle(
                "Report the bequest shadow price",
                "frontier_with_duals",
                callback=kz.storepull,
                help="Costs one extra solve per level. The shadow price is the plan's own "
                "marginal exchange rate between bequest and lifetime spending.",
            )

    if kz.getCaseKey("frontierPlot") is not None:
        st.markdown("---")
        owb.renderPlot(kz.getCaseKey("frontierPlot"))

    if kz.getCaseKey("frontierSummary"):
        st.markdown("#### :orange[Frontier]")
        st.code(kz.getCaseKey("frontierSummary"), language=None)
        st.caption(
            "**Bequest** here means the savings accounts left after the heirs' tax, net of "
            "any remaining debt. It does **not** include the house or other fixed assets, "
            "so the estate your heirs actually receive is larger by their value. "
            "*$/yr per $* is the annual spending given up for each dollar of estate; it is "
            "read off a single curve, so in the stochastic modes it is reported per curve. "
            "*short* counts the scenarios that could not reach that level at all — each is "
            "recorded as a full shortfall, which is what pulls the high-confidence curves down."
        )
