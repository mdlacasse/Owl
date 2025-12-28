import streamlit as st
import sskeys as kz

st.markdown("# :material/error: Logs")
kz.divider("orange")

# -------------------------------
# Session state initialization
# -------------------------------
kz.initGlobalKey("active_case_filter", None)
kz.initGlobalKey("text_filter", "")

# -------------------------------
# Text controls
# -------------------------------
ctrl_cols = st.columns([4, 1], vertical_alignment="bottom", gap="large")

# Get current filter value for widget initialization
current_filter = kz.getGlobalKey("text_filter") or ""

# Create widget with separate key
text_input_value = ctrl_cols[0].text_input(
    "Search logs – Enter string and/or select case name.",
    placeholder="Substring match (e.g., Case1)",
    value=current_filter,
    key="text_filter_input"
)

# Sync widget value back to internal filter state
if text_input_value != current_filter:
    kz.storeGlobalKey("text_filter", text_input_value)

# ---- Clear log button (resets StringIO) ----
if ctrl_cols[1].button(
    "Clear logs",
    type="secondary",
    use_container_width=True,
    help="Clear all logs"
):
    strio = kz.getGlobalKey("loguruLogger")
    if strio is not None:
        strio.seek(0)
        strio.truncate(0)

# -------------------------------
# Can case name buttons scale to multiple cases?
# -------------------------------
case_names = kz.onlyCaseNames()
case_names.insert(0, "All")

ret = st.radio("Filter by case",
               case_names,
               index=0,
               horizontal=True,
               help="Filter logs by case name"
               )

name = None if ret == "All" else ret
kz.storeGlobalKey("active_case_filter", name)

# -------------------------------
# Apply filters to logs
# -------------------------------
strio = kz.getGlobalKey("loguruLogger")
if strio is not None:
    logmsg = strio.getvalue()
    lines = logmsg.splitlines()

    # Single case filter. Include separators for better separation.
    actcase = kz.getGlobalKey("active_case_filter")
    if actcase:
        casestr = "| " + actcase + " |"
        lines = [line for line in lines if casestr in line]

    # Text filter
    actfilter = kz.getGlobalKey("text_filter")
    if actfilter:
        lines = [line for line in lines if actfilter in line]

    st.code("\n".join(lines), language=None)
