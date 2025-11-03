import streamlit as st

import sskeys as kz
import owlbridge as owb


st.write("# :material/settings: Settings")
kz.divider("orange")

col1, col2, col3 = st.columns(3, gap="large")
with col1:
    choices = ("matplotlib", "plotly")
    gkey = "plotGlobalBackend"
    # This should point to the default behavior. No point to call back.
    kz.initGlobalKey(gkey, choices[1])
    st.write("#### :orange[Graph Appearance]")
    helpmsg = "Select the plotting library to use."
    index = choices.index(kz.getGlobalKey(gkey))
    ret = st.radio("Plotting backend", options=choices, index=index, args=[gkey],
                   key=gkey, on_change=owb.setGlobalPlotBackend, help=helpmsg, horizontal=True)

with col2:
    choices = ("sidebar", "top")
    mkey = "menuLocation"
    kz.initGlobalKey(mkey, choices[1])
    st.write("#### :orange[Menu]")
    helpmsg = "Select menu appearance."
    index = choices.index(kz.getGlobalKey(mkey))
    ret = st.radio("Menu location", options=choices, index=index,
                   key=mkey, help=helpmsg, horizontal=True)

with col3:
    choices = ("sticky", "static")
    pkey = "position"
    kz.initGlobalKey(pkey, choices[0])
    st.write("#### :orange[Header]")
    helpmsg = "Select header behavior."
    index = choices.index(kz.getGlobalKey(pkey))
    ret = st.radio("Header behavior", options=choices, index=index,
                   key=pkey, help=helpmsg, horizontal=True)

st.divider()
st.write("""
#### :orange[Full Screen]
Running Owl in full screen provides a more immersive user experience.
Use the F11 key to toggle your browser in full screen mode. Or better, use the Streamlit app on your device.
See [documentation](Documentation#settings-settings) for details.
""")

st.divider()
st.write("""
#### :orange[App Theme]
The color theme for the whole app can be adjusted using the *Settings* options in the dropdown
menu under the three dots in the upper right corner of the page. Choose *Light* or *Dark*.
Default theme is *Dark*.

More information on theming can be found from the Streamlit documentation
[here](https://docs.streamlit.io/develop/concepts/configuration/theming).
""")
