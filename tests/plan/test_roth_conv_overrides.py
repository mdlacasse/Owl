"""
Tests for per-year Roth conversion pins (GitHub discussion #129).

The "Roth conv" column of the Wages and Contributions / HFP table holds the
amount (read into plan.myRothX_in, in raw $) and the "Roth conv fixed" column
holds the flag (read into plan.rothXfixed_in) that decides whether that amount
binds the decision variable x[i,n]:
  - flag False (default): x[i,n] is left free, subject to the usual policy
    options (maxRothConversion cap, noRothConversions, startRothConversions,
    stopRothConversions, swapRothConverters, last-2-years zeroing).
  - flag True: x[i,n] is pinned to the amount exactly, bypassing every one of
    those policy options. An amount of 0 is a pin like any other, holding that
    year at no conversion.
Amounts are non-negative; a negative amount is rejected on load.

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

import numpy as np
import pytest

import owlplanner as owl


THISYEAR = date.today().year


def _make_plan(name, horizon_years=12):
    """Single-person plan with a large tax-deferred balance, ample for Roth conversions."""
    age = 65
    yobs = THISYEAR - age
    expectancy = horizon_years + age - 1  # gives horizons[0] = horizon_years
    p = owl.Plan([name], [f"{yobs}-06-15"], [expectancy], name, verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[1000], taxFree=[50], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setSocialSecurity([0], [70])
    p.setRates("historical", 2000)
    return p


_BASE_OPTIONS = {"withMedicare": "None", "withDecomposition": "none"}


def test_pin_positive_bypasses_cap():
    """A pinned year is held at its exact amount, even above the maxRothConversion cap."""
    p = _make_plan("roth_pin_positive")
    p.myRothX_in[0, 0] = 200_000
    p.rothXfixed_in[0, 0] = True
    options = dict(_BASE_OPTIONS, maxRothConversion=50)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    assert p.x_in[0, 0] == 200_000


def test_pin_zero_forces_no_conversion():
    """An amount of 0 on a pinned year means exactly that: convert nothing."""
    p = _make_plan("roth_pin_zero")
    p.myRothX_in[0, 0] = 0.0
    p.rothXfixed_in[0, 0] = True
    p.solve("maxSpending", dict(_BASE_OPTIONS, maxRothConversion=100))
    assert p.caseStatus == "solved"
    assert p.x_in[0, 0] == 0
    # The pin is confined to the year it names; later years still convert freely.
    assert p.x_in[0, 1:].max() > 0


def test_amount_without_flag_is_only_a_proposal():
    """An amount left unflagged does not constrain the solve, however large."""
    p1 = _make_plan("roth_baseline")
    p1.solve("maxSpending", dict(_BASE_OPTIONS, maxRothConversion=50))

    p2 = _make_plan("roth_with_unflagged_amounts")
    p2.myRothX_in[0, : p2.horizons[0]] = 200_000
    p2.solve("maxSpending", dict(_BASE_OPTIONS, maxRothConversion=50))

    assert p1.caseStatus == "solved"
    assert p2.caseStatus == "solved"
    np.testing.assert_allclose(p1.x_in[0, :], p2.x_in[0, :], atol=1e-6)


def test_mixed_pin_year0_optimize_rest():
    """Use case #2: pin an already-executed year-0 conversion, optimize the remaining years."""
    p = _make_plan("roth_mixed")
    p.myRothX_in[0, 0] = 30_000
    p.rothXfixed_in[0, 0] = True
    options = dict(_BASE_OPTIONS, maxRothConversion=50)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    assert p.x_in[0, 0] == 30_000
    # Remaining years stay within the cap (in raw $).
    assert np.all(p.x_in[0, 1:] <= 50_000 + 1e-6)


def test_pin_in_last_two_years_overrides_zeroing():
    """A pin in the last two years of life takes precedence over the policy zeroing."""
    p = _make_plan("roth_pin_last_year", horizon_years=12)
    last = p.horizons[0] - 1
    p.myRothX_in[0, last] = 25_000
    p.rothXfixed_in[0, last] = True
    options = dict(_BASE_OPTIONS, maxRothConversion=50)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    assert p.x_in[0, last] == 25_000


def test_all_years_pinned_above_cap():
    """When every year's pin exceeds maxRothConversion, every x[i,n] is still pinned
    exactly -- the cap never clips a pinned cell, no matter how many cells are pinned."""
    p = _make_plan("roth_all_pinned_above_cap", horizon_years=6)
    amount = 70_000
    p.myRothX_in[0, : p.horizons[0]] = amount
    p.rothXfixed_in[0, : p.horizons[0]] = True
    options = dict(_BASE_OPTIONS, maxRothConversion=50)
    p.solve("maxSpending", options)
    assert p.caseStatus == "solved"
    np.testing.assert_allclose(p.x_in[0, : p.horizons[0]], amount)


def test_negative_amount_rejected_on_the_in_memory_path():
    """A table can arrive from the UI editor or a caller writing it directly, not just
    from a workbook, so the sign check has to live on that path too."""
    p = _make_plan("roth_negative_amount")
    tl = p.timeLists[p.inames[0]]
    row = tl.index[tl["year"] == THISYEAR + 1][0]
    tl.at[row, "Roth conv"] = -1.0
    with pytest.raises(ValueError, match="Roth conv fixed"):
        p.setContributions(p.timeLists)
