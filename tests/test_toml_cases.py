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


# Expected objective function values for reproducibility testing
# Format: {case_name: {"net_spending_basis": value, "bequest": value}}
# These values are in today's dollars and should remain constant across runs
EXPECTED_OBJECTIVE_VALUES = {
    "Case_john+sally": {
        "net_spending_basis": 100000.0,
        "bequest": 8093727.3,
    },
    "Case_jack+jill": {
        "net_spending_basis": 108771.6,
        "bequest": 500000.0,
    },
    "Case_joe": {
        "net_spending_basis": 87461.2,
        "bequest": 300000.0,
    },
    "Case_kim+sam-spending": {
        "net_spending_basis": 167679.9,
        "bequest": 0.0,
    },
    "Case_kim+sam-bequest": {
        "net_spending_basis": 145000.0,
        "bequest": 1083996.1,
    },
}


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
    rel_tol = 1e-5  # Relative tolerance for floating point comparisons

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
            p.readContributions(hfp)
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
            assert net_spending_basis == pytest.approx(
                expected["net_spending_basis"],
                rel=rel_tol,
                abs=rel_tol,
            ), f"{case}: Net spending basis mismatch."

        if expected["bequest"] is not None:
            assert bequest == pytest.approx(
                expected["bequest"],
                rel=rel_tol,
                abs=rel_tol,
            ), f"{case}: Bequest mismatch."


def test_historical():
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


def test_MC():
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
    p.runMC(objective, options, 20)
