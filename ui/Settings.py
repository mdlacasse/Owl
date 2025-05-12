import streamlit as st

import sskeys as kz
import owlbridge as owb


st.write("## Settings")
kz.orangeDivider()

col1, col2, col3 = st.columns(3, gap="large")
with col1:
    choices = ["matplotlib", "plotly"]
    kz.initKey("plotBackend", choices[0])
    st.write("#### Graphs appearance")
    helpmsg = "Select the plotting library to use."
    kz.getRadio("Plot Backend", choices, "plotBackend", oncall=owb.setPlotBackend, help=helpmsg)

st.write("""
#### App theme
The color theme for the whole app can be adjusted using the *Settings* options in the dropdown
menu under the three dots in the upper right corner. Choose *Light* or *Dark*.

More information on theming can be found from the Streamlit documentation
[here](https://docs.streamlit.io/develop/concepts/configuration/theming).
""")
