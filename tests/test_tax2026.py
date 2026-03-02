"""
Tests for tax2026.py: taxBrackets() and rho_in() edge cases.

Coverage targets:
  - taxBrackets() — single, MFJ, spouse-death transition, OBBBA→preTCJA transition,
    invalid N_i, and past yOBBBA error paths
  - rho_in() — RuntimeError guards for >10 year age gap and longevity > 120

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


# ---------------------------------------------------------------------------
# taxBrackets()
# ---------------------------------------------------------------------------

def test_taxBrackets_returns_dict_with_correct_keys():
    data = tx.taxBrackets(1, 10, 10)
    assert isinstance(data, dict)
    # Returns one entry per bracket except the top (open-ended) one
    assert set(data.keys()) == set(tx.taxBracketNames[:-1])


def test_taxBrackets_arrays_have_correct_length():
    N_n = 15
    data = tx.taxBrackets(1, N_n, N_n)
    for arr in data.values():
        assert len(arr) == N_n


def test_taxBrackets_single_uses_obbba_brackets_by_default():
    """Default yOBBBA is far future; all years use OBBBA single brackets."""
    data = tx.taxBrackets(1, 10, 10)
    bracket_name = tx.taxBracketNames[0]  # "10%"
    for n in range(10):
        assert data[bracket_name][n] == tx.taxBrackets_OBBBA[0][0]


def test_taxBrackets_mfj_uses_mfj_brackets_while_both_alive():
    """Two-person plan uses MFJ brackets for years before n_d."""
    data = tx.taxBrackets(2, n_d=10, N_n=10)
    bracket_name = tx.taxBracketNames[0]
    for n in range(10):
        assert data[bracket_name][n] == tx.taxBrackets_OBBBA[1][0]


def test_taxBrackets_mfj_switches_to_single_after_nd():
    """After the first spouse dies (n >= n_d), brackets switch from MFJ to single."""
    n_d = 5
    N_n = 10
    data = tx.taxBrackets(2, n_d=n_d, N_n=N_n)
    bracket_name = tx.taxBracketNames[0]
    arr = data[bracket_name]
    # Before n_d: MFJ
    assert arr[0] == tx.taxBrackets_OBBBA[1][0]
    assert arr[n_d - 1] == tx.taxBrackets_OBBBA[1][0]
    # From n_d onward: single
    assert arr[n_d] == tx.taxBrackets_OBBBA[0][0]
    assert arr[N_n - 1] == tx.taxBrackets_OBBBA[0][0]


def test_taxBrackets_switches_to_pretcja_after_yobbba():
    """Years on or after yOBBBA use preTCJA brackets instead of OBBBA."""
    thisyear = date.today().year
    yOBBBA = thisyear + 2  # ytc = 2: years 0,1 use OBBBA; years 2+ use preTCJA
    N_n = 5
    data = tx.taxBrackets(1, n_d=N_n, N_n=N_n, yOBBBA=yOBBBA)
    bracket_name = tx.taxBracketNames[0]
    arr = data[bracket_name]
    assert arr[0] == tx.taxBrackets_OBBBA[0][0]
    assert arr[1] == tx.taxBrackets_OBBBA[0][0]
    assert arr[2] == tx.taxBrackets_preTCJA[0][0]
    assert arr[4] == tx.taxBrackets_preTCJA[0][0]


def test_taxBrackets_invalid_ni_zero_raises():
    with pytest.raises(ValueError, match="Cannot process"):
        tx.taxBrackets(0, 10, 10)


def test_taxBrackets_invalid_ni_three_raises():
    with pytest.raises(ValueError, match="Cannot process"):
        tx.taxBrackets(3, 10, 10)


def test_taxBrackets_past_yobbba_raises():
    thisyear = date.today().year
    with pytest.raises(ValueError, match="cannot be in the past"):
        tx.taxBrackets(1, 10, 10, yOBBBA=thisyear - 1)


# ---------------------------------------------------------------------------
# rho_in()
# ---------------------------------------------------------------------------

def test_rho_in_age_difference_over_10_raises():
    thisyear = date.today().year
    yobs = [thisyear - 60, thisyear - 72]  # 12-year age gap
    with pytest.raises(RuntimeError, match="age difference"):
        tx.rho_in(yobs, [85, 85], 20)


def test_rho_in_longevity_over_120_raises():
    thisyear = date.today().year
    yobs = [thisyear - 60]
    with pytest.raises(RuntimeError, match="over 120"):
        tx.rho_in(yobs, [121], 20)
