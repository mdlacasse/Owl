import streamlit as st

import sskeys as kz
import plots as plots


st.write("## Settings")
kz.orangeDivider()

col1, col2, col3 = st.columns(3, gap="large")
with col1:
    st.write("#### Graphs appearance style")
    key = "plot_style"
    kz.initGlobalKey(key, plots.styles[0])
    helpmsg = "Select color style for graphs."
    st.selectbox(
        "Select plot style",
        plots.styles,
        help=helpmsg,
        index=kz.getIndex(kz.getGlobalKey(key), plots.styles),
        key="_" + key,
        on_change=plots.changeStyle,
        args=[key],
    )

st.write("""
#### App theme
The color theme for the whole app can be adjusted using the *Settings* options in the dropdown
menu under the three dots in the upper right corner. Choose *Light* or *Dark*.

More information on theming can be found from the Streamlit documentation
[here](https://docs.streamlit.io/develop/concepts/configuration/theming).
""")
