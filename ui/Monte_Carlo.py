"""
Monte Carlo page for Owl retirement planner Streamlit UI.

This module provides the interface for running Monte Carlo simulations
with stochastic rates to analyze retirement planning outcomes.

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


ret = kz.titleBar(":material/finance: Monte Carlo")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    if kz.getCaseKey("rateType") != "varying" or (
        kz.getCaseKey("varyingType") is None or "stochastic" not in kz.getCaseKey("varyingType")
    ):
        st.info("Rates must be set to *stochastic* or *histochastic* to run Monte Carlo simulations.")
    else:
        st.markdown("Generate a histogram of results obtained from running multiple scenarios with stochastic rates.")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="bottom")
        with col1:
            kz.initCaseKey("MC_cases", 100)
            kz.getIntNum("Number of random instances", "MC_cases", step=10, max_value=10000)
        with col4:
            st.button("Run simulation", on_click=owb.runMC, disabled=kz.caseIsNotMCReady())

    st.divider()
    fig = kz.getCaseKey("monteCarloPlot")
    if fig:
        col1, col2 = st.columns(2, gap="medium")
        owb.renderPlot(fig, col1)
        col2.code(kz.getCaseKey("monteCarloSummary"), language=None)
