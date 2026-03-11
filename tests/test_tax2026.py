"""
Tests for tax2026.py: taxBrackets() and rho_in() edge cases.

Coverage targets:
  - taxBrackets() — single, MFJ, spouse-death transition, OBBBA→preTCJA transition,
    invalid N_i, and past yOBBBA error paths
  - rho_in() — Table II (Joint Life) for >10 year age gap, Table III otherwise,
    and RuntimeError guard for longevity > 120

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

def test_rho_in_longevity_over_120_raises():
    thisyear = date.today().year
    yobs = [thisyear - 60]
    with pytest.raises(RuntimeError, match="over 120"):
        tx.rho_in(yobs, [121], 20)


# ---------------------------------------------------------------------------
# rho_in() — Table II (Joint and Last Survivor) vs Table III (Uniform Lifetime)
# Reference values from IRS Publication 590-B, Appendix B, Table II (2022+).
# ---------------------------------------------------------------------------

def test_rho_in_table_ii_used_when_gap_over_10():
    """Owner with spouse >10 years younger uses Table II (lower RMD fraction)."""
    thisyear = date.today().year
    # Owner age 73, spouse age 58 → gap = 15 → Table II applies
    owner_yob = thisyear - 73
    spouse_yob = thisyear - 58
    rho = tx.rho_in([owner_yob, spouse_yob], [90, 90], 1)
    # Table II factor for owner=73, spouse=58 is larger than Table III (26.5),
    # so the RMD fraction should be smaller than 1/26.5.
    table_iii_fraction = 1.0 / 26.5
    assert rho[0][0] < table_iii_fraction


def test_rho_in_table_iii_used_when_gap_exactly_10():
    """Age gap of exactly 10 years uses Table III (the rule is 'more than 10')."""
    thisyear = date.today().year
    # Owner age 73, spouse age 63 → gap = 10 → Table III applies
    owner_yob = thisyear - 73
    spouse_yob = thisyear - 63
    rho = tx.rho_in([owner_yob, spouse_yob], [90, 90], 1)
    # Table III factor for age 73 is 26.5
    assert rho[0][0] == pytest.approx(1.0 / 26.5)


def test_rho_in_table_iii_used_when_gap_under_10():
    """Age gap under 10 years uses Table III."""
    thisyear = date.today().year
    owner_yob = thisyear - 73
    spouse_yob = thisyear - 68  # gap = 5
    rho = tx.rho_in([owner_yob, spouse_yob], [90, 90], 1)
    assert rho[0][0] == pytest.approx(1.0 / 26.5)


def test_rho_in_table_iii_used_when_spouse_older():
    """Spouse older than owner (negative gap) uses Table III."""
    thisyear = date.today().year
    owner_yob = thisyear - 73
    spouse_yob = thisyear - 80  # spouse is older
    rho = tx.rho_in([owner_yob, spouse_yob], [90, 90], 1)
    assert rho[0][0] == pytest.approx(1.0 / 26.5)


def test_rho_in_table_ii_spot_check_owner73_spouse58():
    """Spot-check: owner=73, spouse=58 → Table II factor from IRS Pub 590-B."""
    thisyear = date.today().year
    rho = tx.rho_in([thisyear - 73, thisyear - 58], [90, 90], 1)
    from owlplanner.data.irs_590b import JOINT_LIFE_TABLE
    expected = 1.0 / JOINT_LIFE_TABLE[73][58]
    assert rho[0][0] == pytest.approx(expected)


def test_rho_in_table_ii_no_longer_raises_for_large_gap():
    """Plan creation with >10 year age gap should no longer raise RuntimeError."""
    thisyear = date.today().year
    yobs = [thisyear - 72, thisyear - 48]  # 24-year gap
    rho = tx.rho_in(yobs, [90, 90], 5)
    assert rho.shape == (2, 5)
    assert np.any(rho[0] > 0)


def test_rho_in_table_ii_reverts_to_table_iii_after_spouse_dies():
    """Table II must NOT be used after the younger spouse's planning horizon ends."""
    thisyear = date.today().year
    # Owner born 20 years before spouse; owner is 73 now.
    yobs = [thisyear - 73, thisyear - 53]  # 20-year gap → Table II eligible
    # Spouse dies at age 60 (horizon = 7 years from now).
    longevity = [95, 60]
    spouse_horizon = yobs[1] + longevity[1] - thisyear + 1  # = 8 years

    N_n = 25
    rho = tx.rho_in(yobs, longevity, N_n)

    # Before spouse dies: owner should use Table II (lower fraction than Table III).
    rho_table3_before = 1.0 / tx.UNIFORM_LIFETIME_DIVISOR_BY_AGE[73]
    assert rho[0, 0] < rho_table3_before, "Expected Table II (lower RMD) before spouse death"

    # After spouse dies: owner must switch to Table III.
    rho_table3_after = 1.0 / tx.UNIFORM_LIFETIME_DIVISOR_BY_AGE[73 + spouse_horizon]
    assert rho[0, spouse_horizon] == pytest.approx(rho_table3_after), (
        "Expected Table III after spouse death"
    )


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
