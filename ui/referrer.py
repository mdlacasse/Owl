"""
Anonymous referrer-domain logging for the Streamlit Community Cloud deployment.

When a new session starts, the domain (and only the domain) of the HTTP
Referer header is printed to stdout, where it appears in the Community Cloud
app logs ("Manage app" panel). This tells the maintainers where visitors are
coming from (e.g., a forum or a video) without recording any IP address, URL
path, query string, or user data, consistent with Owl's privacy commitment.

Logging is active only on the Streamlit Community Cloud, detected by the
platform-specific /mount/src directory under which it mounts the app
repository. Self-hosted, Docker (WORKDIR /app), and local installations
never log anything.

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

import os
from urllib.parse import urlparse

import streamlit as st


def onCommunityCloud():
    """True only when running on the Streamlit Community Cloud."""
    return os.path.abspath(__file__).startswith("/mount/src/")


def logReferrerDomain():
    """Print the referring domain of a new session to the app logs, Community Cloud only."""
    if st.session_state.get("_referrerLogged", False):
        return
    st.session_state["_referrerLogged"] = True

    if not onCommunityCloud():
        return

    try:
        referer = st.context.headers.get("Referer", "")
    except Exception:
        # st.context is unavailable outside a real session (e.g., bare script runs).
        return

    domain = urlparse(referer).netloc or "direct-or-email"
    # Internal navigation within the app is not an external referrer.
    if domain.endswith("streamlit.app"):
        return

    print(f"[owl-referrer] {domain}", flush=True)
