"""
Tests for the sequential (relax-and-fix) MIP decomposition mode.

Covers:
- Sequential decomposition produces a feasible solution (heuristic).
- Fallback to monolithic when no bracket binaries are present.
- Regression: Medicare + LTCG sequential must not collapse spending.

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

from datetime import date

import owlplanner as owl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_simple_plan(name="DecompTest"):
    """Single-person plan for fast decomposition tests."""
    thisyear = date.today().year
    inames = ["Alex"]
    dobs = [f"{thisyear - 62}-01-15"]
    expectancy = [82]
    p = owl.Plan(inames, dobs, expectancy, name, verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[200], taxDeferred=[800], taxFree=[100])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setSocialSecurity([2000], [67])
    return p


def _make_older_two_person(name="AlexJamie"):
    """Two-person plan where both individuals are near/past Medicare age (nm=0).
    This triggers fixed zm binary columns in _configure_Medicare_binary_variables
    (years n < 2 with prevMAGI known).
    """
    thisyear = date.today().year
    inames = ["Alex", "Jamie"]
    dobs = [f"{thisyear - 66}-01-15", f"{thisyear - 63}-01-16"]  # ages 66 and 63 → nm=0
    expectancy = [85, 87]
    p = owl.Plan(inames, dobs, expectancy, name, verbose=False)
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[90, 60], taxDeferred=[600, 150], taxFree=[70, 40])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]])
    p.setSocialSecurity([2333, 2083], [67, 70])
    return p


def _make_jack_jill(name="JackJill"):
    """Two-person plan matching test_repro.py jack+jill setup."""
    thisyear = date.today().year
    inames = ["Jack", "Jill"]
    dobs = [f"{thisyear - 62}-01-15", f"{thisyear - 59}-01-16"]
    expectancy = [82, 79]
    p = owl.Plan(inames, dobs, expectancy, name, verbose=False)
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[90, 60], taxDeferred=[600, 150], taxFree=[70, 40], startDate="1-1")
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setInterpolationMethod("s-curve")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0, 10], [65, 65])
    p.setSocialSecurity([2333, 2083], [67, 70])
    return p


# ---------------------------------------------------------------------------
# Sequential decomposition tests
# ---------------------------------------------------------------------------


class TestSequentialDecomposition:
    """Tests for withDecomposition='sequential' (relax-and-fix heuristic)."""

    def test_sequential_feasible_no_optimize(self):
        """Sequential mode with no binary bracket families falls back to monolithic."""
        p = _make_simple_plan("seq_no_optimize")
        p.solve(
            "maxSpending",
            options={
                "withMedicare": "loop",
                "withDecomposition": "sequential",
            },
        )
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_sequential_with_medicare_optimize(self):
        """Sequential mode with Medicare optimize should produce a feasible result."""
        p = _make_simple_plan("seq_medi_opt")
        p.solve(
            "maxSpending",
            options={
                "withMedicare": "optimize",
                "withDecomposition": "sequential",
            },
        )
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_sequential_jack_jill(self):
        """Sequential decomposition on jack+jill with Medicare optimize."""
        p = _make_jack_jill("seq_jj")
        p.solve(
            "maxSpending",
            options={
                "withMedicare": "optimize",
                "withDecomposition": "sequential",
            },
        )
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_sequential_ltcg_only(self):
        """Sequential + only LTCG optimize must yield feasible integer solution.

        When only zl (LTCG) binaries are present, relax-and-fix may fail from LP rounding;
        the code then falls back to monolithic MIP so we never return a non-integral solution.
        Regression test for LTCG sequential bug.
        """
        p = _make_simple_plan("seq_ltcg_only")
        p.solve(
            "maxSpending",
            options={
                "withLTCG": "optimize",
                "withDecomposition": "sequential",
                "withMedicare": "loop",
            },
        )
        assert p.caseStatus == "solved"
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_medicare_ltcg_sequential_spending_reasonable(self):
        """Medicare + LTCG sequential must not collapse net spending (regression for zl rounding).

        When both withMedicare=optimize and withLTCG=optimize are used with sequential
        decomposition, zl is no longer rounded from the LP; it is left free in the final
        MIP. This test asserts that sequential spending stays within 95% of the loop
        baseline. Without the fix, sequential could drop to ~67k vs ~94k (loop).
        """
        p_loop = _make_jack_jill("med_ltcg_loop")
        p_loop.solve(
            "maxSpending",
            options={
                "withMedicare": "loop",
                "withLTCG": "loop",
            },
        )
        assert p_loop.caseStatus == "solved", "Baseline (loop) should solve."
        spending_loop = p_loop.g_n[0]

        p_seq = _make_jack_jill("med_ltcg_seq")
        p_seq.solve(
            "maxSpending",
            options={
                "withMedicare": "optimize",
                "withLTCG": "optimize",
                "withDecomposition": "sequential",
            },
        )
        assert p_seq.caseStatus == "solved", "Medicare+LTCG sequential should solve."
        spending_seq = p_seq.g_n[0]

        assert spending_seq >= 0.95 * spending_loop, (
            f"Medicare+LTCG sequential spending {spending_seq:.0f} should be >= 95% of "
            f"loop baseline {spending_loop:.0f} (regression: zl rounding collapsed spending)."
        )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


