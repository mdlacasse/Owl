"""
Tests for TOML case file historical range analysis.

Tests verify that historical range analysis runs successfully for example cases.

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

import os
import pytest

import owlplanner as owl


def getHFP(exdir, case, check_exists=True):
    """
    Get the HFP file path for a given case.

    Args:
        exdir: Directory containing example files
        case: Case name (e.g., "Case_john+sally", "Case_kim+sam-spending")
        check_exists: If True, only return path if file exists. If False,
                      return path regardless of existence.

    Returns:
        Full path to HFP file, or empty string if check_exists=True and file
        doesn't exist.
    """
    # Convert case name to HFP filename
    hfp_name = case.replace("Case_", "HFP_")
    hfp_name = hfp_name.replace("-spending", "")
    hfp_name = hfp_name.replace("-bequest", "")
    hfp = os.path.join(exdir, hfp_name + ".xlsx")
    if check_exists and not os.path.exists(hfp):
        return ""
    return hfp


def test_historical():
    """Test historical range analysis for jack+jill case."""
    exdir = "./examples/"
    case = "Case_jack+jill"
    file = os.path.join(exdir, case)
    p = owl.readConfig(file)
    hfp = getHFP(exdir, case)
    assert hfp != "", f"Could not find HFP file for {case}"
    assert os.path.exists(hfp), f"HFP file does not exist: {hfp}"
    p.readContributions(hfp)
    # Verify HFP was loaded
    assert hasattr(p, 'timeLists') and p.timeLists is not None, f"HFP file {hfp} was not loaded"
    options = p.solverOptions
    objective = p.objective
    p.runHistoricalRange(objective, options, 1969, 2023)
