"""
Tests for the "Exclude Roth conversions for..." option (`noRothConversions`).

Regression for a bug where `noRothConversions` was silently ignored whenever
`swapRothConverters` was *present* in solver options, regardless of its value.
The UI always writes `swapRothConverters = 0` when the "Swap Roth converters
mid-plan" toggle is off (see config/ui_bridge.py), so the exclusion was
effectively a no-op for every case that went through the UI.

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


def _make_couple_plan(name, horizon_years=12):
    """Two-person plan, both with large tax-deferred balances, ample for Roth conversions."""
    age = 65
    yobs = THISYEAR - age
    expectancy = horizon_years + age - 1   # gives horizons[i] = horizon_years
    p = owl.Plan(["Jack", "Jill"], [f"{yobs}-06-15", f"{yobs}-06-15"], [expectancy, expectancy], name, verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100, 100], taxDeferred=[1000, 1000], taxFree=[50, 50], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]],
                                                 [[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setSocialSecurity([0, 0], [70, 70])
    p.setRates("historical", 2000)
    return p


_BASE_OPTIONS = {"withMedicare": "None", "withDecomposition": "none", "withSCLoop": False}


def test_no_roth_conversions_excludes_spouse():
    """noRothConversions='Jill' zeroes out Jill's conversions for every year, even when
    swapRothConverters=0 is also present -- as the UI always sends it when swap is off."""
    p = _make_couple_plan("roth_exclude_jill")
    options = dict(_BASE_OPTIONS, maxRothConversion=50, noRothConversions="Jill", swapRothConverters=0)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    np.testing.assert_allclose(p.x_in[1, :], 0)
    # Jack remains free to convert up to the cap.
    assert np.any(p.x_in[0, :] > 0)


def test_no_roth_conversions_excludes_spouse_even_with_positive_override():
    """A positive per-cell useRothConvOverrides pin for the excluded individual must not
    bypass noRothConversions -- exclusion takes precedence over per-cell overrides."""
    p = _make_couple_plan("roth_exclude_jill_with_override")
    p.myRothX_in[1, 0] = 30_000
    options = dict(_BASE_OPTIONS, maxRothConversion=50, noRothConversions="Jill", useRothConvOverrides=True)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    np.testing.assert_allclose(p.x_in[1, :], 0)


def test_no_roth_conversions_ignored_when_swap_active():
    """When swapRothConverters is actually active (non-zero), noRothConversions is ignored --
    solving with both set must be identical to solving with only swapRothConverters set."""
    swap_year = THISYEAR + 2

    p1 = _make_couple_plan("roth_exclude_and_swap")
    options1 = dict(_BASE_OPTIONS, maxRothConversion=50, noRothConversions="Jill", swapRothConverters=swap_year)
    p1.solve("maxSpending", options1)

    p2 = _make_couple_plan("roth_swap_only")
    options2 = dict(_BASE_OPTIONS, maxRothConversion=50, swapRothConverters=swap_year)
    p2.solve("maxSpending", options2)

    assert p1.caseStatus == "solved"
    assert p2.caseStatus == "solved"
    np.testing.assert_allclose(p1.x_in, p2.x_in, atol=1e-6)
