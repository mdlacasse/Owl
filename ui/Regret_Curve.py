"""
Roth conversion regret curve page for Owl retirement planner Streamlit UI.

Shows what committing to a fixed first-year Roth conversion costs, measured against what
each historical scenario would have chosen with perfect foresight, and against the value
of converting at all.

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


ret = kz.titleBar(":material/trending_down: Conversion Regret")

if ret is None or kz.caseHasNoPlan():
    kz.no_case_info()
else:
    kz.initCaseKey("regret_preset", "Standard")
    kz.initCaseKey("regret_ystart", owb.FROM)
    kz.initCaseKey("regret_yend", owb.TO)
    kz.initCaseKey("regret_band_pct", 2)
    kz.initCaseKey("regret_seed", 1)
    kz.initCaseKey("regret_grid_pad", 45)
    kz.initCaseKey("regret_person", 0)
    kz.initCaseKey("regretPlot", None)
    kz.initCaseKey("regretSummary", None)
    kz.initCaseKey("regretSummaryDict", None)
    kz.initCaseKey("regretScenarioData", None)
    kz.initCaseKey("regretObjective", None)

    objective = kz.getCaseKey("objective") or "Net spending"
    outcome = "net spending" if objective == "Net spending" else "final bequest"

    st.markdown(f"""
How much does it cost to commit to a first-year Roth conversion *now*, before knowing what
markets will do? Each historical scenario is first solved with perfect foresight, then
re-solved with the first year's conversion pinned at each amount on a grid, leaving every
later year free to adapt. The gap between the two is the **regret** of that commitment,
measured here in **{outcome}** because that is this case's objective.

The curve answers two questions at once: how much you lose by committing to the wrong
amount, and — on the right-hand axis — how that compares with what converting is worth at
all.
""")

    yend_max = owb.histYendMax()
    if kz.getCaseKey("regret_yend") > yend_max:
        kz.storeCaseKey("regret_yend", yend_max)

    col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="bottom")
    with col1:
        presets = owb.regretPresetNames()
        # A case saved with a preset that no longer exists must fall back, not crash.
        if kz.getCaseKey("regret_preset") not in presets:
            kz.storeCaseKey("regret_preset", "Standard")
        st.selectbox(
            "Resolution",
            presets,
            index=presets.index(kz.getCaseKey("regret_preset")),
            on_change=kz.storepull,
            args=["regret_preset"],
            key=kz.genCaseKey("regret_preset"),
            help="Cutting the grid is much cheaper than cutting scenarios. Quick look and "
            "Standard also solve the tax brackets in loop mode instead of as a MIP.",
        )
    with col2:
        st.number_input(
            "Starting year",
            min_value=owb.FROM,
            max_value=yend_max,
            value=kz.getCaseKey("regret_ystart"),
            on_change=kz.storepull,
            args=["regret_ystart"],
            key=kz.genCaseKey("regret_ystart"),
        )
    with col3:
        st.number_input(
            "Ending year",
            min_value=kz.getCaseKey("regret_ystart"),
            max_value=yend_max,
            value=min(kz.getCaseKey("regret_yend"), yend_max),
            on_change=kz.storepull,
            args=["regret_yend"],
            key=kz.genCaseKey("regret_yend"),
        )
    preset = kz.getCaseKey("regret_preset")
    ystart, yend = kz.getCaseKey("regret_ystart"), min(kz.getCaseKey("regret_yend"), yend_max)
    nsolves = owb.estimateRegretSolves(preset, ystart, yend)
    nscen = owb.regretScenarioCount(preset, ystart, yend)
    per_scenario = nsolves // nscen if nscen else 0
    allowed, cost = owb.costOfRun(
        nsolves, nscen, detail=f"**{preset}**: {nscen} scenarios x {per_scenario} solves"
    )

    with col4:
        st.button(
            "Run sweep",
            on_click=owb.runConversionRegret,
            disabled=not allowed or kz.caseIsNotRegretReady(),
        )
    st.caption(cost)

    with st.expander("*Advanced options*"):
        st.caption("Changing these options will only affect the next run.")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="bottom")
        with col1:
            plan = kz.getCaseKey("plan")
            names = list(plan.inames) if plan is not None else ["you"]
            if len(names) > 1:
                idx = st.selectbox(
                    "Whose conversion is pinned",
                    range(len(names)),
                    format_func=lambda i: names[i],
                    index=int(kz.getCaseKey("regret_person") or 0),
                    key=kz.genCaseKey("regret_person_sel"),
                    help="The other person's conversions stay free to optimize.",
                )
                kz.storeCaseKey("regret_person", idx)
        with col2:
            kz.getIntNum(
                "Grid headroom ($k)",
                "regret_grid_pad",
                min_value=0,
                step=5,
                callback=kz.setpull,
                help="How far past the largest conversion any scenario chose the grid "
                "extends. Raise it when the summary says the curve is still falling at "
                "the grid edge, so the best commitment is only a lower bound.",
            )
        with col3:
            kz.getIntNum(
                "Subsample seed",
                "regret_seed",
                min_value=1,
                step=1,
                callback=kz.setpull,
                help="Presets that sweep a subset of windows draw them at random, never by "
                "stride: a stride lands on a correlated run of overlapping windows and "
                "biases the answer.",
            )

    st.divider()
    fig = kz.getCaseKey("regretPlot")
    if fig:
        # The graph is the deliverable, so it goes first and gets the full width; the
        # tolerance control sits under it, and the figures it cannot carry below that.
        owb.renderPlot(fig)

        sd = kz.getCaseKey("regretSummaryDict") or {}
        if sd.get("pct_axis_ok"):
            col_slider, _ = st.columns([1, 2], gap="large")
            with col_slider:
                band_pct = st.slider(
                    ":orange[Commit band tolerance]",
                    min_value=1,
                    max_value=25,
                    value=int(kz.getCaseKey("regret_band_pct") or 2),
                    step=1,
                    format="%d%%",
                    key=kz.genCaseKey("regret_band_slider"),
                    on_change=owb.updateRegretBand,
                    help="Share of the value of converting you are willing to give up. The "
                    "shaded band spans every commitment that stays within it.",
                )
                kz.storeCaseKey("regret_band_pct", band_pct)
        else:
            st.caption(
                "Converting is worth little or nothing in this case, so there is no "
                "meaningful percentage to measure a commitment against."
            )

        summary = kz.getCaseKey("regretSummary")
        if summary:
            st.code(summary, language=None, wrap_lines=True)
