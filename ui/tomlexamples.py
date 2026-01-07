"""
Example case file loading utilities for Streamlit UI.

This module provides functions to load example case files and wage data
from the examples directory for demonstration and testing purposes.

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

# import requests
import streamlit as st
import os
from io import StringIO, BytesIO


cases = ["jack+jill", "joe", "john+sally", "jon+jane", "kim+sam-bequest",
         "kim+sam-spending", "drawdowncalc-comparison-1"]


wages = ["jack+jill", "joe", "john+sally", "jon+jane", "kim+sam"]


whereami = os.path.dirname(__file__)


def getHFPName(case):
    """
    Normalize case name to HFP file name by removing common suffixes.

    This function maps case names like 'kim+sam-bequest' or 'kim+sam-spending'
    to their corresponding HFP file name 'kim+sam'. It removes suffixes
    like '-bequest' and '-spending' that are used to distinguish different
    case variants that share the same HFP file.

    Args:
        case: Case name (e.g., 'kim+sam-bequest', 'kim+sam-spending', 'jack+jill')

    Returns:
        Normalized HFP name (e.g., 'kim+sam', 'jack+jill')
    """
    hfp_name = case
    # Remove common suffixes that distinguish case variants
    hfp_name = hfp_name.replace("-spending", "")
    hfp_name = hfp_name.replace("-bequest", "")
    return hfp_name


def loadCaseExample(case):
    file = os.path.join(whereami, f"../examples/Case_{case}.toml")
    with open(file, "r") as f:
        text = f.read()
        return StringIO(text)

    st.error(f"Failed to load case parameter file: {case}.")
    return None


def loadWagesExample(case):
    """
    Load HFP workbook example file.

    Args:
        case: Case name (will be normalized to HFP name if needed)

    Returns:
        BytesIO object containing the HFP file data, or None if file not found
    """
    # Normalize case name to get the correct HFP file name
    hfp_name = getHFPName(case)
    file = os.path.join(whereami, f"../examples/HFP_{hfp_name}.xlsx")
    if os.path.exists(file):
        with open(file, "rb") as f:
            data = f.read()
            return BytesIO(data)
    else:
        st.error(f"Failed to load Household Financial Profile {hfp_name}.xlsx.")
        return None


def hasHFPExample(case):
    """
    Check if an HFP example file exists for the given case name.

    Args:
        case: Case name (will be normalized to HFP name if needed)

    Returns:
        True if HFP file exists, False otherwise
    """
    hfp_name = getHFPName(case)
    file = os.path.join(whereami, f"../examples/HFP_{hfp_name}.xlsx")
    return os.path.exists(file)
