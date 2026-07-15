"""
Anonymous referrer-domain logging for the Streamlit Community Cloud deployment.

When a new session starts, the domain (and only the domain) of the referring
page is printed to stdout, where it appears in the Community Cloud app logs
("Manage app" panel). This tells the maintainers where visitors are coming
from (e.g., a forum or a video) without recording any IP address, URL path,
query string, or user data, consistent with Owl's privacy commitment.

The HTTP Referer header does not survive the WebSocket handshake that
st.context.headers reflects, so the referring page is read in the browser
(document.referrer) by the tiny custom component in referrer_component/ and
sent back to Python. An optional ?ref= query parameter (e.g., a link tagged
?ref=readme) is logged alongside the domain when present.

Self-identified automation (HeadlessChrome, Prerender) makes no privacy
claim: for those sessions only, the log line additionally carries the client
IP taken from the proxy forwarding headers, the landing URL with its query
parameters, and the full (Cookie/Authorization-redacted) handshake headers,
so the bot operator can be identified (whois/ASN).

Logging is active only on the Streamlit Community Cloud, detected by the
platform-specific /mount/src directory under which it mounts the app
repository. Self-hosted, Docker (WORKDIR /app), and local installations
never log anything. For a local end-to-end test, set OWL_REFERRER_TEST=1.

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

import ipaddress
import os
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components

_COMPONENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "referrer_component")
_component_func = None


def onCommunityCloud():
    """True only when running on the Streamlit Community Cloud."""
    return os.path.abspath(__file__).startswith("/mount/src/")


def _enabled():
    return onCommunityCloud() or os.environ.get("OWL_REFERRER_TEST") == "1"


def _getBrowserReferrer():
    """Read document.referrer from the browser; None until the round-trip completes."""
    global _component_func
    if _component_func is None:
        _component_func = components.declare_component("owl_referrer", path=_COMPONENT_DIR)
    return _component_func(default=None)


def _routableIp(candidate):
    """Return the candidate as a public IP string, or None if absent, unparsable, or non-routable."""
    candidate = (candidate or "").strip()
    # The platform proxy reports IPv4 clients as IPv4-mapped IPv6 (::ffff:a.b.c.d).
    if candidate.lower().startswith("::ffff:"):
        candidate = candidate[7:]
    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if parsed.is_loopback or parsed.is_private or parsed.is_unspecified:
        return None
    return candidate


def _clientIp():
    """Best guess at the real client IP from behind the Community Cloud reverse proxy.

    st.context.ip_address sees only the proxy's loopback address, so the
    forwarding headers of the WebSocket handshake are consulted first.
    """
    headers = st.context.headers
    # Leftmost routable address in X-Forwarded-For is the originating client.
    for hop in headers.get("X-Forwarded-For", "").split(","):
        ip = _routableIp(hop)
        if ip:
            return ip
    ip = _routableIp(headers.get("X-Real-Ip", ""))
    if ip:
        return ip
    forwarded = headers.get("Forwarded", "")
    if forwarded:
        # Raw RFC 7239 value; not parsed, but it still names the client.
        return forwarded
    return _routableIp(getattr(st.context, "ip_address", None)) or "?"


def _botForensics():
    """Identifying detail appended for self-identified automation only (no privacy claim)."""
    redacted = ("cookie", "authorization")
    headerDict = {k: v for k, v in st.context.headers.to_dict().items() if k.lower() not in redacted}
    detail = f" | ip={_clientIp()} | url={getattr(st.context, 'url', None)}"
    queryParams = dict(st.query_params)
    if queryParams:
        detail += f" | qs={queryParams}"
    return detail + f" | headers={headerDict}"


def _emit(referrer, refParam="", userAgent=""):
    domain = urlparse(referrer).netloc or "direct-or-email"
    # Internal navigation within the app is not an external referrer.
    if domain.endswith("streamlit.app"):
        return
    suffix = f" ref={refParam}" if refParam else ""
    # The User-Agent distinguishes in-app webviews (FB_IAB, WhatsApp, ...) and
    # headless automation from ordinary browsers when the referrer is absent.
    print(f"[owl-referrer] {domain}{suffix} | ua={userAgent}", flush=True)


def logReferrerDomain():
    """Print the referring domain of a new session to the app logs, Community Cloud only."""
    if not _enabled():
        return
    if st.session_state.get("_referrerLogged", False):
        return

    referrer = _getBrowserReferrer()
    if referrer is None:
        # Component value not delivered yet; the rerun it triggers will bring it.
        return

    st.session_state["_referrerLogged"] = True
    try:
        userAgent = st.context.headers.get("User-Agent", "")
        # Timezone/locale spread separates a human audience (US timezones,
        # en-US) from proxy-fleet automation (uniform or incoherent values).
        tzLocale = f"{getattr(st.context, 'timezone', None)}/{getattr(st.context, 'locale', None)}"
        details = f"{userAgent} | tz={tzLocale}"
        # For self-identified automation only (no privacy claim), add the
        # client IP, landing URL, and handshake headers so the operator can
        # be looked up (whois/ASN).
        if "HeadlessChrome" in userAgent or "Prerender" in userAgent:
            details += _botForensics()
    except Exception:
        details = ""
    _emit(referrer, st.query_params.get("ref", ""), details)
