"""
Functions to deal with MOSEK license and module.

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

import importlib.util
import os
import streamlit as st


# Environment variable MOSEK expects for the license file path (set before importing mosek)
MOSEKLM_LICENSE_FILE = "MOSEKLM_LICENSE_FILE"


def _streamlit_dir():
    """Return the .streamlit directory path (where secrets.toml lives)."""
    for base in (os.getcwd(), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
        d = os.path.join(base, ".streamlit")
        if os.path.isdir(d):
            return d
    return None


def hasMOSEK():
    spec = importlib.util.find_spec("mosek")
    mosekenv = os.environ.get(MOSEKLM_LICENSE_FILE, None)
    return (spec is not None and mosekenv is not None)


def createLicense():
    streamlit_d = _streamlit_dir()
    if not streamlit_d or not os.path.isfile(os.path.join(streamlit_d, "secrets.toml")):
        return

    try:
        license = st.secrets["license"]
    except (KeyError, FileNotFoundError):
        return

    license_path = os.path.join(streamlit_d, "mosek.lic")
    with open(license_path, "w") as f:
        f.write(license + "\n")

    # print(f"Created MOSEK license file {license_path}")
    os.environ[MOSEKLM_LICENSE_FILE] = os.path.abspath(license_path)


# Create license file once when this module is loaded.
createLicense()
