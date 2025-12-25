import streamlit as st
import sskeys as kz
import io

ret = kz.titleBar(":material/error: Logs2")

# -------------------------------
# Session state initialization
# -------------------------------
if "active_case_filter" not in st.session_state:
    st.session_state.active_case_filter = None

if "text_filter" not in st.session_state:
    st.session_state.text_filter = ""

# -------------------------------
# Top controls
# -------------------------------
ctrl_cols = st.columns([3, 1])

st.session_state.text_filter = ctrl_cols[0].text_input(
    "Search logs – Enter string or select filter by case name.",
    value=st.session_state.text_filter,
    placeholder="Substring match (e.g. Case1)"
)

# ---- Clear log button (resets StringIO) ----
if ctrl_cols[1].button(
    "Clear log",
    type="secondary",
    use_container_width=True,
):
    strio = kz.getGlobalKey("loguruLogger")
    if strio is not None:
        strio.seek(0)
        strio.truncate(0)

# -------------------------------
# Case name buttons
# -------------------------------
case_names = kz.onlyCaseNames()
cols = st.columns(len(case_names) + 1)

for i, name in enumerate(case_names):
    active = (st.session_state.active_case_filter == name)

    if cols[i].button(
        name,
        key=f"case_{name}",
        type="secondary" if active else "primary",
        disabled=active,                 # 👈 cannot be clicked again
        use_container_width=True,
    ):
        st.session_state.active_case_filter = name
        st.session_state.text_filter = ""  # 👈 reset text filter

# -------------------------------
# Clear filters button
# -------------------------------
if cols[-1].button(
    "Clear filters",
    type="secondary",
    use_container_width=True,
):
    st.session_state.active_case_filter = None
    st.session_state.text_filter = ""

# -------------------------------
# Apply filters to logs
# -------------------------------
strio = kz.getGlobalKey("loguruLogger")
if strio is not None:
    logmsg = strio.getvalue()
    lines = logmsg.splitlines()

    # Text filter
    if st.session_state.text_filter:
        lines = [
            line for line in lines
            if st.session_state.text_filter in line
        ]

    # Single case filter
    if st.session_state.active_case_filter:
        case = st.session_state.active_case_filter
        lines = [line for line in lines if case in line]

    st.code("\n".join(lines), language=None)
