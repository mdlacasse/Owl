"""
Spending Optimization page for Owl retirement planner Streamlit UI.

This module provides the interface for running stochastic spending optimization,
computing an efficient frontier between committed spending and shortfall risk,
and selecting a committed spending level based on a target success rate.

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

import sskeys as kz
import owlbridge as owb


ret = kz.titleBar(":material/query_stats: Spending Optimization")

if ret is None or kz.caseHasNoPlan():
    st.info("A case must first be created before running this page.")
else:
    kz.initCaseKey("stoch_scenario_method", "historical")
    kz.initCaseKey("stoch_target_success_rate", 0.85)
    kz.initCaseKey("stoch_ystart", owb.FROM)
    kz.initCaseKey("stoch_yend", owb.TO)
    kz.initCaseKey("stoch_N_mc", 200)
    kz.initCaseKey("stoch_reverse_sequence", False)
    kz.initCaseKey("stoch_roll_sequence", 0)
    kz.initCaseKey("stoch_with_longevity", False)
    kz.initCaseKey("stoch_longevity_reproducible", False)
    kz.initCaseKey("stoch_longevity_seed", 1)
    kz.initCaseKey("stoch_mortality_table", "SSA2025")
    kz.initCaseKey("stochFrontierPlot", None)
    kz.initCaseKey("stochOutcomePlot", None)
    kz.initCaseKey("stochSummary", None)
    kz.initCaseKey("stochResult", None)
    kz.initCaseKey("stochScenarioData", None)

    st.markdown("""
Optimize committed first-year spending across a set of historical or Monte Carlo scenarios.
The **efficient frontier** shows the trade-off between spending level and shortfall risk.
Select a target success rate to find the committed spending that meets it.
""")

    objective = kz.getCaseKey("objective") or "Net spending"
    if objective != "Net spending":
        st.warning(
            "Spending optimization requires **Net spending** as the objective. "
            "For *Bequest* or *Hybrid* cases, spending is not the primary decision variable — "
            "use the **Historical Range** or **Monte Carlo** pages to analyze outcome distributions."
        )
        st.stop()

    st.markdown("#### :orange[Scenario method]")
    scenario_method = st.radio(
        "Generate scenarios using",
        options=["historical", "mc"],
        format_func=lambda x: "Historical range" if x == "historical" else "Monte Carlo",
        index=0 if kz.getCaseKey("stoch_scenario_method") == "historical" else 1,
        key=kz.genCaseKey("stoch_scenario_method_radio"),
        label_visibility="collapsed",
        horizontal=True,
    )
    kz.storeCaseKey("stoch_scenario_method", scenario_method)

    st.markdown("####")
    if scenario_method == "historical":
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="bottom")
        with col1:
            st.number_input(
                "Starting year",
                min_value=owb.FROM,
                max_value=kz.getCaseKey("stoch_yend"),
                value=kz.getCaseKey("stoch_ystart"),
                on_change=kz.storepull,
                args=["stoch_ystart"],
                key=kz.genCaseKey("stoch_ystart"),
            )
        with col2:
            st.number_input(
                "Ending year",
                min_value=kz.getCaseKey("stoch_ystart"),
                max_value=owb.TO,
                value=kz.getCaseKey("stoch_yend"),
                on_change=kz.storepull,
                args=["stoch_yend"],
                key=kz.genCaseKey("stoch_yend"),
            )
        with col4:
            st.button(
                "Run optimization",
                on_click=owb.runStochasticSpending,
                disabled=kz.caseIsNotStochReady(),
            )
        st.markdown("####")
        with st.expander("*Advanced options*"):
            st.caption("Changing these options will only affect the next run.")
            st.markdown("#### :orange[Rate sequence]")
            plan = kz.getCaseKey("plan")
            N_n = plan.N_n if plan is not None else 50
            help_reverse = "Reverse the rate sequence along the time axis (e.g. run last year first)."
            help_roll = "Roll the rate sequence by this many years (0 = no shift)."
            col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="bottom")
            with col1:
                kz.getIntNum("Roll (years)", "stoch_roll_sequence", min_value=0, max_value=N_n,
                             step=1, callback=kz.setpull, help=help_roll)
            with col2:
                kz.getToggle("Reverse sequence", "stoch_reverse_sequence",
                             callback=kz.setpull, help=help_reverse)
    else:
        if kz.caseIsNotMCReady():
            st.warning(
                "Monte Carlo scenarios require rates set to a stochastic method. "
                "Change the rate type on the **Rates** page."
            )
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="bottom")
        with col1:
            kz.getIntNum("Number of MC scenarios", "stoch_N_mc", step=50, min_value=10, max_value=5000)
        with col4:
            st.button(
                "Run optimization",
                on_click=owb.runStochasticSpending,
                disabled=kz.caseIsNotStochReady(),
            )
        st.markdown("####")
        with st.expander("*Advanced options*"):
            st.caption("Changing these options will only affect the next run.")
            st.markdown("#### :orange[Longevity risk]")
            help_longevity = (
                "Draw a random plan horizon from SSA period life tables for each scenario. "
                "For couples, uses the last-survivor horizon max(τ₁, τ₂). "
                "Sex is set on the **Create Case** page."
            )
            help_repro = ("When enabled, the same random seed will be used for all longevity draws, "
                          "ensuring reproducible results across runs.")
            help_seed = ("Integer seed ≥ 1 for the random number generator. "
                         "Change this value to explore different lifespan draws while keeping results reproducible.")
            col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="bottom")
            with col1:
                kz.getToggle("Include longevity risk", "stoch_with_longevity",
                             callback=kz.setpull, help=help_longevity)
            if kz.getCaseKey("stoch_with_longevity"):
                with col2:
                    kz.getToggle("Reproducible draws", "stoch_longevity_reproducible",
                                 callback=kz.setpull, help=help_repro)
                if kz.getCaseKey("stoch_longevity_reproducible"):
                    with col3:
                        kz.getIntNum("Longevity seed", "stoch_longevity_seed",
                                     min_value=1, max_value=2**31 - 1,
                                     step=1, callback=kz.setpull, help=help_seed)
                from owlplanner.data.mortality_tables import MORTALITY_TABLE_KEYS, MORTALITY_DESCRIPTIONS
                st.markdown("#### :orange[Mortality table]")
                help_table = ("Actuarial life table used to sample random lifespans. "
                              "Choose the table that best reflects the health profile of the individuals in the plan.")
                col1, col2 = st.columns([1, 3.2], gap="large", vertical_alignment="bottom")
                with col1:
                    selected_table = kz.getSelectbox(
                        "Mortality table", MORTALITY_TABLE_KEYS, "stoch_mortality_table",
                        callback=kz.setpull, help=help_table,
                    )
                with col2:
                    st.caption(MORTALITY_DESCRIPTIONS.get(selected_table, ""))

    st.divider()
    fig_frontier = kz.getCaseKey("stochFrontierPlot")
    fig_outcomes = kz.getCaseKey("stochOutcomePlot")
    if fig_frontier or fig_outcomes:
        result = kz.getCaseKey("stochResult")
        if result:
            col_msg, col_slider = st.columns([2, 1.5], gap="large")
            with col_msg:
                summary = kz.getCaseKey("stochSummary")
                if summary:
                    st.code(summary, language=None)
            with col_slider:
                target_sr = st.slider(
                    ":orange[Target success rate]",
                    min_value=50,
                    max_value=100,
                    value=int(round(kz.getCaseKey("stoch_target_success_rate") * 100)),
                    step=1,
                    format="%d%%",
                    key=kz.genCaseKey("stoch_target_sr_slider"),
                    on_change=owb.updateStochasticTarget,
                )
                kz.storeCaseKey("stoch_target_success_rate", target_sr / 100.0)

        col1, col2 = st.columns(2, gap="medium")
        if fig_frontier:
            owb.renderPlot(fig_frontier, col1)
        if fig_outcomes:
            owb.renderPlot(fig_outcomes, col2)
