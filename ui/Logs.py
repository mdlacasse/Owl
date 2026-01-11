"""
Logs page for Owl retirement planner Streamlit UI.

This module provides the interface for viewing application logs
and debugging information for each case.

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

st.markdown("# :material/error: Logs")
kz.divider("orange")

kz.initGlobalKey("text_filter", "")
current_case = kz.currentCaseName()

case_names = kz.onlyCaseNames()
if not case_names:
    st.info("No cases available. Create a case first to see logs.")
    st.stop()

# Initialize the radio button key with the current case
# If current_case is not in case_names (e.g., "Upload Case File..." or "New Case..."),
# default to the first case (index 0)
try:
    default_index = case_names.index(current_case)
except ValueError:
    default_index = 0

selected_case = st.radio("View logs for case",
                         case_names,
                         index=default_index,
                         horizontal=True,
                         help="Select which case's logs to view",
                         key="logs_case_selector"
                         )

# -------------------------------
# Text controls
# -------------------------------
ctrl_cols = st.columns([4, 2, 1], vertical_alignment="bottom", gap="large")

# Get current filter value for widget initialization
kz.initGlobalKey("active_text_filter", "")
current_filter = kz.getGlobalKey("active_text_filter")

text_input_value = ctrl_cols[0].text_input(
    "Search logs – Enter string to filter log messages.",
    placeholder="Substring match (e.g., warning)",
    value=current_filter,
    key="text_filter_input"
)

if text_input_value != current_filter:
    kz.storeGlobalKey("active_text_filter", text_input_value)

# ---- Clear log button (resets StringIO) ----
if ctrl_cols[2].button(
    "Clear logs",
    type="secondary",
    use_container_width=True,
    help=":warning: This action cannot be undone."
):
    # Clear logs from the selected case
    if selected_case:
        strio = kz.getKeyInCase("logs", selected_case)
        if strio is not None:
            strio.seek(0)
            strio.truncate()

# Get logs from the selected case
if selected_case:
    strio = kz.getKeyInCase("logs", selected_case)
    if strio is not None:
        logmsg = strio.getvalue()
    else:
        logmsg = ""
else:
    logmsg = ""

# Display logs if available
if logmsg:
    # Apply text filter if provided
    actfilter = kz.getGlobalKey("active_text_filter")
    if actfilter:
        # Filter lines that contain the search text
        lines = logmsg.splitlines()
        filtered_lines = [line for line in lines if actfilter in line]
        filtered_logs = "\n".join(filtered_lines)
    else:
        filtered_logs = logmsg

    st.code(filtered_logs, language=None)
else:
    st.info(f"No logs available for case '{selected_case}'. Logs will appear here as you use the application.")

st.caption("""These logs are stored in memory and are only available to you.
They are solely for debugging purposes and disappear after this session is closed.""")
