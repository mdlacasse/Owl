"""
Settings page for Owl retirement planner Streamlit UI.

This module provides the interface for configuring global application
settings including plotting backend preferences.

Copyright (C) 2025-2026 The Owl Authors

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


def setKey(key):
    val = kz.getGlobalKey("_"+key)
    if val is not None:
        kz.storeGlobalKey(key, val)


st.markdown("# :material/settings: Settings")
kz.divider("orange")

col1, col2, col3 = st.columns(3, gap="large")
with col1:
    choices = ("matplotlib", "plotly")
    gkey = "plotGlobalBackend"
    st.markdown("#### :orange[Graph Appearance]")
    helpmsg = "Select the plotting library to use."
    index = choices.index(kz.getGlobalKey(gkey))
    ret = st.radio("Plotting backend", options=choices, index=index, args=[gkey],
                   key="_"+gkey, on_change=owb.setGlobalPlotBackend, help=helpmsg, horizontal=True)

with col2:
    choices = ("sidebar", "top")
    mkey = "menuLocation"
    st.markdown("#### :orange[Menu]")
    helpmsg = "Select menu appearance."
    index = choices.index(kz.getGlobalKey(mkey))
    ret = st.radio("Menu location", options=choices, index=index, args=[mkey],
                   key="_"+mkey, on_change=setKey, help=helpmsg, horizontal=True)

with col3:
    choices = ("sticky", "static")
    pkey = "position"
    st.markdown("#### :orange[Header]")
    helpmsg = "Select header behavior."
    index = choices.index(kz.getGlobalKey(pkey))
    ret = st.radio("Header behavior", options=choices, index=index, args=[pkey],
                   key="_"+pkey, on_change=setKey, help=helpmsg, horizontal=True)

st.divider()
st.markdown("""
#### :orange[Full Screen]
Running Owl in full screen provides a more immersive user experience.
Use the F11 key to toggle your browser in full screen mode. Or better, use the Streamlit app on your device.
See [documentation](Documentation#settings-settings) for details.
""")

st.divider()
st.markdown("""
#### :orange[App Theme]
Streamlit's theme is set at launch time and cannot be changed from within the app.
By default, **Owl** inherits the light or dark theme configured on the system where it runs.
To override this behavior, use the following commands:

**Local install** — pass `--theme.base` to the launcher script:
```
owlplanner.sh --theme.base=light
owlplanner.cmd --theme.base=light
```
**Docker** — set the `STREAMLIT_THEME_BASE` environment variable via the Docker Desktop GUI,
via `docker-compose.yml`, or on the command line:
```
docker run -p 8501:8501 -e STREAMLIT_THEME_BASE=light --rm owlplanner/owldocker.static
```

See Streamlit's guide to [theming](https://docs.streamlit.io/develop/concepts/configuration/theming)
for all available options.
""")
