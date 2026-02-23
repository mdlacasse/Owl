"""
Tests for TOML case file loading and execution.

Tests verify reproducibility by checking that example TOML case files
produce consistent objective function values (net spending and bequest)
across multiple runs.

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
from sys import platform

import owlplanner as owl

pytestmark = pytest.mark.toml


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


# Expected objective function values for reproducibility testing
# Format: {case_name: {"net_spending_basis": value, "bequest": value}}
# Values are in today's dollars and rounded to the nearest dollar
if platform == "darwin":
    EXPECTED_OBJECTIVE_VALUES = {
        "Case_john+sally": {
            "net_spending_basis": 100000,
            "bequest": 8094499,
        },
        "Case_jack+jill": {
            "net_spending_basis": 91776,
            "bequest": 400000,
        },
        "Case_joe": {
            "net_spending_basis": 87461,
            "bequest": 300000,
        },
        "Case_kim+sam-spending": {
            "net_spending_basis": 168294,
            "bequest": 0,
        },
        "Case_kim+sam-bequest": {
            "net_spending_basis": 145000,
            "bequest": 1113254,
        },
    }
elif platform in ["win32", "linux"]:
    EXPECTED_OBJECTIVE_VALUES = {
        "Case_john+sally": {
            "net_spending_basis": 100000,
            "bequest": 8094499,
        },
        "Case_jack+jill": {
            "net_spending_basis": 91757,
            "bequest": 400000,
        },
        "Case_joe": {
            "net_spending_basis": 87461,
            "bequest": 300000,
        },
        "Case_kim+sam-spending": {
            "net_spending_basis": 168294,
            "bequest": 0,
        },
        "Case_kim+sam-bequest": {
            "net_spending_basis": 145000,
            "bequest": 1113254,
        },
    }
else:
    print(f"Unknown platform {platform}")
    assert False


def test_reproducibility():
    """
    Test that all example cases produce reproducible objective function values.

    For each case, extracts net spending basis and bequest values and verifies
    they match expected values. This ensures the solver produces consistent
    results across runs.

    Also verifies that the associated HFP (Household Financial Profile) file
    is successfully loaded for each case.
    """
    exdir = "./examples/"
    rel_tol = 5e-4  # Relative tolerance — widened from 1e-4 to tolerate HiGHS version
    # differences across Python releases (~0.035% max observed variation)

    # Dictionary to store actual results
    actual_results = {}

    # Iterate over cases defined in EXPECTED_OBJECTIVE_VALUES
    for case in EXPECTED_OBJECTIVE_VALUES:
        # Load TOML case file
        file = os.path.join(exdir, case)
        p = owl.readConfig(file)

        # Get and verify HFP file exists
        hfp = getHFP(exdir, case)
        expected_path = getHFP(exdir, case, check_exists=False)
        assert hfp != "", (
            f"Could not find HFP file for {case}. "
            f"Expected file: {expected_path}"
        )
        assert os.path.exists(hfp), (
            f"HFP file does not exist: {hfp} for case {case}"
        )

        # Load HFP file and verify it was loaded successfully
        try:
            p.readHFP(hfp)
        except Exception as e:
            assert False, (
                f"Failed to load HFP file {hfp} for case {case}: {e}"
            )

        # Verify that HFP data was actually loaded
        assert hasattr(p, 'timeLists') and p.timeLists is not None, (
            f"HFP file {hfp} was not loaded for case {case}: timeLists is missing"
        )
        assert hasattr(p, 'houseLists') and p.houseLists is not None, (
            f"HFP file {hfp} was not loaded for case {case}: houseLists is missing"
        )
        assert len(p.timeLists) > 0, (
            f"HFP file {hfp} was loaded but contains no time list data "
            f"for case {case}"
        )

        # Force HiGHS for reproducible results across environments (matches GitHub CI).
        p.solverOptions['solver'] = 'HiGHS'

        # Solve the plan
        p.resolve()

        # Extract objective function values
        # basis is net spending basis in today's dollars
        # bequest is bequest value in today's dollars
        net_spending_basis = p.basis
        bequest = p.bequest

        actual_results[case] = {
            "net_spending_basis": net_spending_basis,
            "bequest": bequest,
        }

        # Check against expected values
        expected = EXPECTED_OBJECTIVE_VALUES[case]

        if expected["net_spending_basis"] is not None:
            comparison_value = pytest.approx(
                expected["net_spending_basis"],
                rel=rel_tol,
                abs=rel_tol,
            )
            assert net_spending_basis == comparison_value, f"{case}: Net spending basis mismatch."
            assert net_spending_basis == comparison_value, f"{case}: Net spending basis: {net_spending_basis}"
            assert net_spending_basis == comparison_value, (
                f"{case}: calculated value: {comparison_value}"
            )

        if expected["bequest"] is not None:
            assert bequest == pytest.approx(
                expected["bequest"],
                rel=rel_tol,
                abs=rel_tol,
            ), f"{case}: Bequest mismatch."
