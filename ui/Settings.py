import streamlit as st

import sskeys as kz
import owlbridge as owb


st.write("# Settings")
kz.divider("orange")

col1, col2, col3 = st.columns(3, gap="large")
with col1:
    choices = ("matplotlib", "plotly")
    gkey = "plotGlobalBackend"
    # This should point to the default behavior. No point to call back.
    kz.initGlobalKey(gkey, choices[1])
    st.write("#### Graph Appearance")
    helpmsg = "Select the plotting library to use."
    index = choices.index(kz.getGlobalKey(gkey))
    ret = st.radio("Plotting backend", options=choices, index=index, args=[gkey],
                   key="_"+gkey, on_change=owb.setGlobalPlotBackend, help=helpmsg, horizontal=True)

st.divider()
st.write("""
#### Full Screen
Running Owl in full screen provides a more immersive user experience.
Use the F11 key to toggle your browser in full screen mode.
""")

st.divider()
st.write("""
#### App Theme
The color theme for the whole app can be adjusted using the *Settings* options in the dropdown
menu under the three dots in the upper right corner of the page. Choose *Light* or *Dark*.
Default theme is *Dark*.

More information on theming can be found from the Streamlit documentation
[here](https://docs.streamlit.io/develop/concepts/configuration/theming).
""")
