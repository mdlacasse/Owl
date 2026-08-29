"""
Tests for the Roth conversion window options `startRothConversions` and
`stopRothConversions`.

`stopRothConversions` is the mirror of `startRothConversions`: the former
disallows conversions *before* a year, the latter *from* a year onward, so the
two together bound conversions to a closed window. A stop year lets a user say
"no conversions after 2028" with one number instead of pinning every remaining
year at zero.

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
TOL = 1e-6


def test_stop_year_zeroes_conversions_from_that_year_on():
    """stopRothConversions=Y allows conversions through Y-1 and none from Y."""
    stop = THISYEAR + 4
    p = _make_plan("roth_stop")
    p.solve("maxSpending", dict(_BASE_OPTIONS, maxRothConversion=100, stopRothConversions=stop))
    assert p.caseStatus == "solved"
    n_stop = stop - THISYEAR
    np.testing.assert_allclose(p.x_in[0, n_stop:], 0, atol=TOL)
    # The years the option leaves alone are still used.
    assert p.x_in[0, :n_stop].sum() > 0


def test_start_and_stop_bound_a_closed_window():
    """Conversions happen only within [start, stop-1]."""
    start, stop = THISYEAR + 2, THISYEAR + 5
    p = _make_plan("roth_window")
    p.solve(
        "maxSpending",
        dict(_BASE_OPTIONS, maxRothConversion=100, startRothConversions=start, stopRothConversions=stop),
    )
    assert p.caseStatus == "solved"
    lo, hi = start - THISYEAR, stop - THISYEAR
    np.testing.assert_allclose(p.x_in[0, :lo], 0, atol=TOL)
    np.testing.assert_allclose(p.x_in[0, hi:], 0, atol=TOL)
    assert p.x_in[0, lo:hi].sum() > 0


def test_stop_year_in_the_past_means_never_convert():
    """A stop year at or before this year disallows every conversion, rather than erroring."""
    p = _make_plan("roth_stop_past")
    p.solve("maxSpending", dict(_BASE_OPTIONS, maxRothConversion=100, stopRothConversions=THISYEAR - 3))
    assert p.caseStatus == "solved"
    np.testing.assert_allclose(p.x_in[0, :], 0, atol=TOL)


def test_stop_before_start_yields_no_conversions():
    """An inverted window is empty, not an error."""
    p = _make_plan("roth_inverted_window")
    p.solve(
        "maxSpending",
        dict(
            _BASE_OPTIONS,
            maxRothConversion=100,
            startRothConversions=THISYEAR + 6,
            stopRothConversions=THISYEAR + 2,
        ),
    )
    assert p.caseStatus == "solved"
    np.testing.assert_allclose(p.x_in[0, :], 0, atol=TOL)


def test_pin_survives_the_stopped_range():
    """A pinned year binds even when the stop year would otherwise zero it."""
    stop = THISYEAR + 3
    n_pin = 5  # inside the stopped range
    p = _make_plan("roth_pin_past_stop")
    p.myRothX_in[0, n_pin] = 40_000
    p.rothXfixed_in[0, n_pin] = True
    p.solve("maxSpending", dict(_BASE_OPTIONS, maxRothConversion=100, stopRothConversions=stop))
    assert p.caseStatus == "solved"
    assert p.x_in[0, n_pin] == 40_000
    # Every other stopped year is still zero.
    others = [n for n in range(stop - THISYEAR, p.horizons[0]) if n != n_pin]
    np.testing.assert_allclose(p.x_in[0, others], 0, atol=TOL)
