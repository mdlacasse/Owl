"""
Tests for socialsecurity module - Social Security benefit calculations.

Tests verify Social Security rules including full retirement age calculations
and benefit computations.

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

from owlplanner import socialsecurity as ss


def test_FRA():
    years = range(1954, 1960)
    for i, y in enumerate(years):
        yfra = ss.getFRAs([y])
        assert yfra[0] % 1 == pytest.approx(2*i/12)

    yfra = ss.getFRAs([1940])
    assert yfra[0] == 66
    yfra = ss.getFRAs([1954])
    assert yfra[0] == 66
    yfra = ss.getFRAs([1960])
    assert yfra[0] == 67
    yfra = ss.getFRAs([1969])
    assert yfra[0] == 67


def test_selfFactor():
    ages = range(62, 71)
    factors66 = [0.75, 0.80, 0.866667, 0.9333333, 1.0, 1.08, 1.16, 1.24, 1.32]
    factors67 = [0.70, 0.75, 0.80, 0.866667, 0.9333333, 1.0, 1.08, 1.16, 1.24]
    for i, a in enumerate(ages):
        assert ss.getSelfFactor(66, a, False) == pytest.approx(factors66[i], 0.001)
        assert ss.getSelfFactor(67, a, False) == pytest.approx(factors67[i], 0.001)
        if a > 62:
            assert ss.getSelfFactor(66, a - 1/12, True) == pytest.approx(factors66[i], 0.001)
            assert ss.getSelfFactor(67, a - 1/12, True) == pytest.approx(factors67[i], 0.001)

    # Example from SSA: https://www.ssa.gov/benefits/retirement/planner/1955-delay.html
    assert ss.getSelfFactor(66 + 2/12, 66 + 2/12, False) == pytest.approx(1.00, 0.001)
    assert ss.getSelfFactor(66 + 2/12, 67, False) == pytest.approx(1.06667, 0.001)
    assert ss.getSelfFactor(66 + 2/12, 68, False) == pytest.approx(1.14667, 0.001)
    assert ss.getSelfFactor(66 + 2/12, 69, False) == pytest.approx(1.22667, 0.001)
    assert ss.getSelfFactor(66 + 3/12, 69 + 1/12, False) == pytest.approx(1.22667, 0.001)
    assert ss.getSelfFactor(66 + 2/12, 70, False) == pytest.approx(1.30667, 0.001)


def test_spousalFactor():
    ages = range(62, 71)
    factors66 = [0.70, 0.75, 0.833333, 0.9166667, 1.0, 1.0, 1.0, 1.0, 1.0]
    factors67 = [0.65, 0.70, 0.75, 0.833333, 0.9166667, 1.0, 1.0, 1.0, 1.0]
    for i, a in enumerate(ages):
        assert ss.getSpousalFactor(66, a, False) == pytest.approx(factors66[i], 0.001)
        assert ss.getSpousalFactor(67, a, False) == pytest.approx(factors67[i], 0.001)
        if a > 62:
            assert ss.getSpousalFactor(66, a - 1/12, True) == pytest.approx(factors66[i], 0.001)
            assert ss.getSpousalFactor(67, a - 1/12, True) == pytest.approx(factors67[i], 0.001)

    # Individual born in 1955.
    assert ss.getSpousalFactor(66 + 2/12, 66 + 2/12, False) == pytest.approx(1.00, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 66, False) == pytest.approx(2*0.4931, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 65, False) == pytest.approx(2*0.4514, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 64, False) == pytest.approx(2*0.4097, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 63, False) == pytest.approx(2*0.3708, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 62, False) == pytest.approx(2*0.3458, 0.001)


def test_SpousalBenefits():
    pias = [2800]
    benefits = ss.getSpousalBenefits(pias)
    assert np.array_equal(benefits, [0])

    pias = [2800, 1400]
    benefits = ss.getSpousalBenefits(pias)
    assert np.array_equal(benefits, [0, 0])

    pias = [2800, 1000]
    benefits = ss.getSpousalBenefits(pias)
    assert np.array_equal(benefits, [0, 400])

    pias = [1000, 3000]
    benefits = ss.getSpousalBenefits(pias)
    assert np.array_equal(benefits, [500, 0])
