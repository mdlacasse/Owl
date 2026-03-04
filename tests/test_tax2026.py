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
# Helper: extract OBBBA bonus from taxParams() for a single person aged 65.
# ---------------------------------------------------------------------------

def _obbba_bonus_single(magi):
    """Return the OBBBA $6k bonus added to sigmaBar[0] for a 65-year-old single filer."""
    thisyear = date.today().year
    yobs = [thisyear - 65]
    gamma_n = np.ones(1)
    magi_n = np.array([float(magi)])
    N_n = 1
    sigmaBar, _, _ = tx.taxParams(yobs, 0, N_n, N_n, gamma_n, magi_n)
    # Subtract standard deduction and 65+ additional deduction to isolate the bonus.
    return sigmaBar[0] - float(tx.stdDeduction_OBBBA[0]) - float(tx.extra65Deduction[0])


def _obbba_bonus_mfj_total(magi):
    """Return total OBBBA bonus added to sigmaBar[0] for a MFJ couple both aged 65."""
    thisyear = date.today().year
    yobs = [thisyear - 65, thisyear - 65]
    gamma_n = np.ones(1)
    magi_n = np.array([float(magi)])
    N_n = 1
    sigmaBar, _, _ = tx.taxParams(yobs, 0, N_n, N_n, gamma_n, magi_n)
    # Subtract standard deduction and both 65+ additional deductions.
    return sigmaBar[0] - float(tx.stdDeduction_OBBBA[1]) - 2 * float(tx.extra65Deduction[1])


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


# ---------------------------------------------------------------------------
# OBBBA 65+ bonus deduction phaseout (OBBBA §1002)
# Phaseout: $6 per $100 of MAGI above threshold. Full phaseout at threshold + $100k.
# Single threshold: $75,000. MFJ threshold: $150,000.
# ---------------------------------------------------------------------------

def test_obbba_bonus_at_threshold():
    """Single filer at exactly the $75k threshold receives the full $6,000 bonus."""
    assert _obbba_bonus_single(75_000) == pytest.approx(6000)


def test_obbba_bonus_phaseout_midpoint():
    """Single filer $50k above threshold ($125k MAGI) receives half the bonus ($3,000)."""
    assert _obbba_bonus_single(125_000) == pytest.approx(3000)


def test_obbba_bonus_fully_phased_out():
    """Single filer at threshold + $100k ($175k MAGI) receives no bonus."""
    assert _obbba_bonus_single(175_000) == pytest.approx(0)


def test_obbba_bonus_below_threshold():
    """Single filer below threshold ($50k MAGI) receives the full $6,000 bonus."""
    assert _obbba_bonus_single(50_000) == pytest.approx(6000)


def test_obbba_bonus_mfj_threshold():
    """MFJ couple at $100k MAGI (above $75k single threshold, below $150k MFJ threshold)
    each receives the full $6,000 bonus, confirming the MFJ threshold is used."""
    assert _obbba_bonus_mfj_total(100_000) == pytest.approx(12000)
