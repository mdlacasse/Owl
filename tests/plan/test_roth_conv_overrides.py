"""
Tests for per-cell Roth conversion overrides (GitHub discussion #129).

The "Roth conv" column of the Wages and Contributions / HFP table (read into
plan.myRothX_in, in raw $) can be used as a per-cell override of the Roth
conversion decision variable x[i,n] when options["useRothConvOverrides"] is
True:
  - 0 (default): x[i,n] is left free, subject to the usual policy options
    (maxRothConversion cap, noRothConversions, startRothConversions,
    swapRothConverters, last-2-years zeroing).
  - > 0: x[i,n] is pinned to that exact value, bypassing the cap.
  - < 0 (any magnitude): x[i,n] is forced to 0.

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

from datetime import date

import numpy as np

import owlplanner as owl


THISYEAR = date.today().year


def _make_plan(name, horizon_years=12):
    """Single-person plan with a large tax-deferred balance, ample for Roth conversions."""
    age = 65
    yobs = THISYEAR - age
    expectancy = horizon_years + age - 1   # gives horizons[0] = horizon_years
    p = owl.Plan([name], [f"{yobs}-06-15"], [expectancy], name, verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[1000], taxFree=[50], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setSocialSecurity([0], [70])
    p.setRates("historical", 2000)
    return p


_BASE_OPTIONS = {"withMedicare": "None", "withDecomposition": "none", "withSCLoop": False}


def test_pin_positive_bypasses_cap():
    """A positive override pins x[i,n] to that exact value, even above the maxRothConversion cap."""
    p = _make_plan("roth_pin_positive")
    p.myRothX_in[0, 0] = 200_000
    options = dict(_BASE_OPTIONS, maxRothConversion=50, useRothConvOverrides=True)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    assert p.x_in[0, 0] == 200_000


def test_negative_forces_zero_any_magnitude():
    """Any negative override forces x[i,n] to 0, regardless of its magnitude."""
    for magnitude in (-1, -50_000):
        p = _make_plan(f"roth_force_zero_{abs(magnitude)}")
        p.myRothX_in[0, 0] = magnitude
        options = dict(_BASE_OPTIONS, maxRothConversion=100, useRothConvOverrides=True)
        p.solve("maxSpending", options)
        assert p.caseStatus == "solved"
        assert p.x_in[0, 0] == 0


def test_zero_cells_unaffected_by_overrides_flag():
    """All-zero overrides must reproduce the non-override solution exactly."""
    p1 = _make_plan("roth_baseline")
    p1.solve("maxSpending", dict(_BASE_OPTIONS, maxRothConversion=50))

    p2 = _make_plan("roth_with_unused_overrides")
    p2.solve("maxSpending", dict(_BASE_OPTIONS, maxRothConversion=50, useRothConvOverrides=True))

    assert p1.caseStatus == "solved"
    assert p2.caseStatus == "solved"
    np.testing.assert_allclose(p1.x_in[0, :], p2.x_in[0, :], atol=1e-6)


def test_mixed_pin_year0_optimize_rest():
    """Use case #2: pin an already-executed year-0 conversion, optimize the remaining years."""
    p = _make_plan("roth_mixed")
    p.myRothX_in[0, 0] = 30_000
    options = dict(_BASE_OPTIONS, maxRothConversion=50, useRothConvOverrides=True)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    assert p.x_in[0, 0] == 30_000
    # Remaining years stay within the cap (in raw $).
    assert np.all(p.x_in[0, 1:] <= 50_000 + 1e-6)


def test_pin_in_last_two_years_overrides_zeroing():
    """A positive override in the last two years of life takes precedence over the policy zeroing."""
    p = _make_plan("roth_pin_last_year", horizon_years=12)
    last = p.horizons[0] - 1
    p.myRothX_in[0, last] = 25_000
    options = dict(_BASE_OPTIONS, maxRothConversion=50, useRothConvOverrides=True)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    assert p.x_in[0, last] == 25_000


def test_all_years_pinned_above_cap():
    """When every year's override exceeds maxRothConversion, every x[i,n] is still pinned
    exactly -- the cap never clips a pinned cell, no matter how many cells are pinned."""
    p = _make_plan("roth_all_pinned_above_cap", horizon_years=6)
    override = 70_000
    p.myRothX_in[0, :p.horizons[0]] = override
    options = dict(_BASE_OPTIONS, maxRothConversion=50, useRothConvOverrides=True)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    np.testing.assert_allclose(p.x_in[0, :p.horizons[0]], override)
