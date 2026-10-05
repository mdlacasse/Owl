"""
Tests for TOML case file loading and execution.

Tests verify reproducibility by checking that example TOML case files
produce consistent objective function values (net spending and bequest)
across multiple runs.

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
import pytest

import owlplanner as owl

pytestmark = pytest.mark.toml


def _active_solver():
    """Resolve OWL_TEST_SOLVER (or 'default') to the actual solver that will be used."""
    env = os.getenv("OWL_TEST_SOLVER", "default").lower()
    if env == "highs":
        return "HiGHS"
    if env == "mosek":
        return "MOSEK"
    # This is "default" path.
    try:
        import mosek  # noqa: F401

        if "MOSEKLM_LICENSE_FILE" in os.environ:
            return "MOSEK"
    except ImportError:
        pass
    return "HiGHS"


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
# Updated Mar 2026: cases enhanced for broader feature coverage (HSA, pension survivor,
# fixed assets, debts).
# Updated after HFP dollar conversion ($ not $k) in update_hfp_coverage.py
# Updated after Medicare Part D inclusion (Part D IRMAA increases Medicare cost when MAGI > bracket 0,
# reducing optimal bequest relative to Part B-only baseline).
# Updated after HSA QME in kim+sam examples: both kim+sam cases now include
# other_medical_expenses=2.0 ($2k/year), which slightly changes bequest baselines.
# Updated after taxable_cost_basis added to jack+jill, joe, robin: proper unrealized-gain
# tracking increases LTCG tax, reducing max spending for those three cases.
# Updated after fixing the LTCG bracket-partition LP degeneracy (companion upper bound on
# q[0]+q[1]+q[2] in _configure_ltcg_constraints): jack+jill's SC loop now lands on a better
# (higher) best-of-oscillation spending value, 102_867 -> 103_015.
# Updated after dropping unused state-tax LP vars for no-income-tax states (st_lp now
# requires a nonzero bracket rate): jack+jill is state="TX", so its SC loop's best-of-
# oscillation fixed point shifted again, 103_015 -> 102_978.
# Updated after the MAGI SS-basis fix (IRMAA/NIIT/OBBBA now use AGI-basis MAGI = taxable SS
# only; ACA and SS-taxability keep full-SS MAGI_aca_n): jack+jill net 102_978 -> 102_880
# (darwin, verified); the same -98 delta was carried to linux/win32 as an estimate.
# Updated after removing the explicit HSA deduction (wages are now entered net of all
# contributions, HSA included): all six cases carry HSA contributions, so every value
# shifted slightly down (darwin, verified); jack+jill carried the same -259 delta to
# linux/win32 as an estimate.
# Updated after the AMO exclusion binaries were removed (restored by post-processing instead).
# Only john+sally moved: same spending basis, bequest 82_934 -> 84_252 under HiGHS, i.e. the
# same plan with more left over. That case converges oscillatory, so the self-consistent loop
# settles on a best-of-cycle iterate and the removal shifted which one. MOSEK still lands on
# 82_934, hence the override below. Every other case is unchanged to the cent.
# Those linux/win32 estimates were finally measured on a native Windows run (2026-08-28):
# jack+jill comes back at 102_515, i.e. exactly the darwin/linux value, so the estimated
# deltas were wrong and win32 never diverged at all. With that corrected, all three
# platforms agree to the cent under HiGHS and the per-platform tables collapse into one.
# Platform still matters under MOSEK -- see the override block in test_reproducibility.
# Updated after the 2026-09 state bracket audit (CA brackets moved from 2023 to 2025 values):
# only the two CA cases moved (darwin, verified under both solvers). kim+sam-spending
# 186_498 -> 186_583 (HiGHS), 186_403 -> 186_456 (MOSEK); kim+sam-bequest 1_972_270 ->
# 1_976_280 under HiGHS, and MOSEK now lands on the same value.
#
# Re-measured on darwin under both solvers when the residual exit test was merged with that
# bracket audit. The two changes move the same cases for unrelated reasons, so neither branch's
# pins survived the merge and hand-reconciling them would have produced numbers right for
# neither: jack+jill 102_515 -> 102_577 (the loop now waits for its fed-back quantities to
# settle) and kim+sam-spending 186_583 -> 186_590 under HiGHS.
#
# jack+jill, joe and robin moved (-42, -469, -56) when taxable cost basis started counting taxed,
# reinvested dividends and interest and putting the unrealized gain in the equity share.
# kim+sam-spending returned to 186_583 under HiGHS when residualTol became a per-year bar: at
# $50/yr it converges where it did before the exit test, while MOSEK still settles at 186_519.
EXPECTED_OBJECTIVE_VALUES = {
    "Case_john+sally": {
        "net_spending_basis": 145_000,
        "bequest": 16_803,
    },
    "Case_jack+jill": {
        "net_spending_basis": 102_535,
        "bequest": 400_000,
    },
    "Case_joe": {
        "net_spending_basis": 92_575,
        "bequest": 300_000,
    },
    "Case_kim+sam-spending": {
        "net_spending_basis": 185_952,
        "bequest": 0,
    },
    "Case_kim+sam-bequest": {
        "net_spending_basis": 145_000,
        "bequest": 1_944_071,
    },
    "Case_robin": {
        "net_spending_basis": 44_013,
        "bequest": 50_000,
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
    # No case needs a MOSEK override any more; HiGHS and MOSEK agree within rel_tol on all of them.
    # History of the overrides that used to live here:
    # - john+sally: gone when the default epsilon became 5e-7 (re-measured on darwin); the two
    #   solvers agreed at 82_934 where they used to differ by 1,318. Stronger tie-breaking leaves
    #   fewer near-equivalent optima for a solver to choose between, so some of the
    #   solver-to-solver spread was degeneracy rather than anything about the solvers.
    # - jack+jill: gone once the loop waits for its quantities to settle (both 102_577).
    # - kim+sam-bequest: gone after the CA bracket update (both 1_976_280 then). It also used to
    #   carry a win32 split of ~1_014 below darwin, measured 2026-08-28; win32 has not been
    #   re-measured since, so no platform override is kept for it.
    # - kim+sam-spending (MOSEK 186_315): gone 2026-09-28 when the state base stopped also
    #   deducting the federal standard deduction. The solvers now land at 185_390 (HiGHS) and
    #   185_400 (MOSEK). That change re-pinned john+sally, kim+sam-* and robin (MN, CA, NY);
    #   jack+jill and joe live in no-income-tax states and did not move.
    # - kim+sam-* re-pinned 2026-10-03 when CA's $153 personal credit per filer, and its $153 senior
    #   credit per filer 65+, were modeled. kim+sam-spending 185_390 -> 185_952 (HiGHS 185_948.93,
    #   MOSEK 185_955.12): +$302/yr from the personal credit, then +$257/yr from the senior one,
    #   which the couple (born 1964/1965) only reaches after three years. kim+sam-bequest
    #   1_917_689 -> 1_944_071 (both solvers 1_944_071.20): the same credits compounding into the
    #   estate (1_917_623.62 with them switched off).

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
        assert hfp != "", f"Could not find HFP file for {case}. Expected file: {expected_path}"
        assert os.path.exists(hfp), f"HFP file does not exist: {hfp} for case {case}"

        # Load HFP file and verify it was loaded successfully
        try:
            p.readHFP(hfp)
        except Exception as e:
            raise AssertionError(f"Failed to load HFP file {hfp} for case {case}: {e}") from e

        # Verify that HFP data was actually loaded
        assert hasattr(p, "timeLists") and p.timeLists is not None, (
            f"HFP file {hfp} was not loaded for case {case}: timeLists is missing"
        )
        assert hasattr(p, "houseLists") and p.houseLists is not None, (
            f"HFP file {hfp} was not loaded for case {case}: houseLists is missing"
        )
        assert len(p.timeLists) > 0, f"HFP file {hfp} was loaded but contains no time list data for case {case}"

        p.solverOptions["absTol"] = 50
        p.solverOptions["relTol"] = 2e-5

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
                abs=50,
            )
            assert net_spending_basis == comparison_value, (
                f"{case}: Net spending basis mismatch — got {net_spending_basis!r}, expected {comparison_value}"
            )

        if expected["bequest"] is not None:
            assert bequest == pytest.approx(
                expected["bequest"],
                rel=rel_tol,
                abs=rel_tol,
            ), f"{case}: Bequest mismatch."


@pytest.mark.toml
def test_robin_fixed_assets_bequest():
    """
    Verify that Robin's primary home (yod=0 → past plan end) appears as a
    non-zero fixed-asset bequest value. Spending/bequest reproducibility is
    covered by test_reproducibility via EXPECTED_OBJECTIVE_VALUES.
    """
    exdir = "./examples/"
    p = owl.readConfig(os.path.join(exdir, "Case_robin.toml"))
    p.readHFP(os.path.join(exdir, "HFP_robin.xlsx"))
    p.resolve()
    home_bequest = p.getFixedAssetsBequestValueInTodaysDollars()
    assert home_bequest == pytest.approx(285_000, rel=1e-3), (
        f"Home bequest mismatch: {home_bequest:.2f} (deterministic, solver-independent)"
    )
