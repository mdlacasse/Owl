"""
Tests for Medicare Part B and IRMAA calculations (tax2026.mediCosts, mediVals).

Verifies that single individuals are charged the standard Part B basic premium
in eligible years and that values align with CMS published figures (e.g. 2026).

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

import pytest
import numpy as np
from datetime import date

from owlplanner import tax2026 as tx


def test_mediCosts_single_individual_basic_premium():
    """Single individual aged 65+ is charged the Part B basic premium each eligible year."""
    thisyear = date.today().year
    # Single person, born so they are 70 at plan start (thisyear)
    yobs = np.array([thisyear - 70])
    Nn = 10
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn)
    magi = np.zeros(Nn)  # Low MAGI -> no IRMAA surcharge
    prevmagi = np.zeros(2)

    costs = tx.mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn)

    # Annual basic premium = 12 * monthly standard (e.g. 202.90 for 2026)
    basic_annual = tx.irmaaFees[0]
    assert basic_annual == pytest.approx(12 * 202.90)

    # Every year the person is 65+ and in horizon should have at least the basic premium
    for n in range(Nn):
        age_in_year = thisyear + n - yobs[0]
        if age_in_year >= 65 and n < horizons[0]:
            assert costs[n] >= basic_annual, f"Year n={n} (age {age_in_year}) should charge basic premium"
            assert costs[n] == pytest.approx(basic_annual, rel=1e-9), (
                f"Low MAGI: cost should equal basic premium in year n={n}"
            )
        else:
            assert costs[n] == 0


def test_mediCosts_single_irmaa_brackets():
    """Single individual with high MAGI gets IRMAA surcharges (2026 brackets)."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 70])
    Nn = 5
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn)
    prevmagi = np.array([0.0, 0.0])

    # MAGI just above first single bracket (109k) -> basic + first surcharge
    magi = np.full(Nn, 120_000)
    costs = tx.mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn)
    # For n>=2 we use magi[n-2]; for n<2 we use prevmagi[n]
    # Bracket 1 is > 109k: add irmaaFees[1] = 12*81.20
    expected_low = tx.irmaaFees[0] + tx.irmaaFees[1]
    for n in range(2, Nn):
        assert costs[n] == pytest.approx(expected_low), (
            f"Single MAGI 120k: expect basic + first IRMAA in year n={n}"
        )


def test_irmaa_values_2026_cms():
    """IRMAA fees and brackets match CMS 2026 (single: ≤109k, 109–137k, etc.)."""
    # Standard monthly Part B 2026 = $202.90
    assert tx.irmaaFees[0] == pytest.approx(12 * 202.90)
    # Single brackets (index 0): 0, 109000, 137000, 171000, 205000, 500000
    assert tx.irmaaBrackets[0][1] == 109_000
    assert tx.irmaaBrackets[0][2] == 137_000
    assert tx.irmaaBrackets[0][5] == 500_000
    # Cumulative costs = total monthly * 12: 202.90, 284.10, 405.80, 527.50, 649.20, 689.90
    monthly_totals = tx.irmaaCosts / 12
    assert monthly_totals[0] == pytest.approx(202.90)
    assert monthly_totals[1] == pytest.approx(284.10)
    assert monthly_totals[2] == pytest.approx(405.80)
