"""
Tests for Medicare Part B, Part D, and IRMAA calculations (tax2026.mediCosts, mediVals).

Verifies that single individuals are charged the standard Part B basic premium
in eligible years, that values align with CMS published figures (e.g. 2026),
and that Part D (base + IRMAA) is included when enabled.
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

    # With Part D included, low MAGI still has no Part D IRMAA; cost = Part B only
    costs = tx.mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn)

    # Annual basic premium = 12 * monthly standard (e.g. 202.90 for 2026)
    basic_annual = tx.partB_irmaa_fees[0]
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
    """Single individual with high MAGI gets Part B IRMAA surcharges (2026 brackets)."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 70])
    Nn = 5
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn)
    prevmagi = np.array([0.0, 0.0])

    # MAGI just above first single bracket (109k) -> basic + first surcharge (Part B only for this test)
    magi = np.full(Nn, 120_000)
    costs = tx.mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn, include_part_d=False)
    # For n>=2 we use magi[n-2]; for n<2 we use prevmagi[n]
    # Bracket 1 is > 109k: add partB_irmaa_fees[1] = 12*81.20
    expected_low = tx.partB_irmaa_fees[0] + tx.partB_irmaa_fees[1]
    for n in range(2, Nn):
        assert costs[n] == pytest.approx(expected_low), (
            f"Single MAGI 120k: expect basic + first IRMAA in year n={n}"
        )


def test_irmaa_values_2026_cms():
    """IRMAA fees and brackets match CMS 2026 (single: ≤109k, 109–137k, etc.)."""
    # Standard monthly Part B 2026 = $202.90
    assert tx.partB_irmaa_fees[0] == pytest.approx(12 * 202.90)
    # Single brackets (index 0): 0, 109_000, 137_000, 171_000, 205_000, 500_000
    assert tx.irmaaBrackets[0][1] == 109_000
    assert tx.irmaaBrackets[0][2] == 137_000
    assert tx.irmaaBrackets[0][5] == 500_000
    monthly_totals = tx.partB_irmaa_costs / 12
    assert monthly_totals[0] == pytest.approx(202.90)
    assert monthly_totals[1] == pytest.approx(284.10)
    assert monthly_totals[2] == pytest.approx(405.80)


def test_mediCosts_part_d_irmaa_increases_cost():
    """With Part D included, high MAGI yields higher total than Part B only."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 70])
    Nn = 5
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn)
    prevmagi = np.array([0.0, 0.0])
    magi = np.full(Nn, 120_000)  # Above first bracket

    costs_part_b_only = tx.mediCosts(
        yobs, horizons, magi, prevmagi, gamma_n, Nn, include_part_d=False
    )
    costs_with_part_d = tx.mediCosts(
        yobs, horizons, magi, prevmagi, gamma_n, Nn, include_part_d=True
    )
    # Part D first bracket surcharge = 12 * 14.50
    expected_extra = 12 * 14.50
    for n in range(2, Nn):
        assert costs_with_part_d[n] == pytest.approx(costs_part_b_only[n] + expected_extra), (
            f"Year n={n}: Part D should add first-bracket surcharge"
        )


def test_mediCosts_part_d_base_premium():
    """Part D base premium increases cost by expected amount per eligible person per year."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 70])
    Nn = 4
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn)
    magi = np.zeros(Nn)
    prevmagi = np.zeros(2)
    base_monthly = 40.0
    base_annual = base_monthly * 12

    costs_no_base = tx.mediCosts(
        yobs, horizons, magi, prevmagi, gamma_n, Nn,
        include_part_d=True, part_d_base_annual_per_person=0.0,
    )
    costs_with_base = tx.mediCosts(
        yobs, horizons, magi, prevmagi, gamma_n, Nn,
        include_part_d=True, part_d_base_annual_per_person=base_annual,
    )
    for n in range(Nn):
        if thisyear + n - yobs[0] >= 65 and n < horizons[0]:
            assert costs_with_base[n] == pytest.approx(costs_no_base[n] + base_annual), (
                f"Year n={n}: Part D base should add {base_annual} for one person"
            )


def test_mediVals_combined_costs_increase_by_bracket():
    """Combined Part B + Part D cumulative costs are strictly increasing by bracket."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 65])  # 65 at plan start
    Nn = 3
    horizons = np.array([Nn])
    gamma_n = np.ones(Nn + 1)
    Nq = 6

    nm, Lbar, Cbar = tx.mediVals(
        yobs, horizons, gamma_n, Nn, Nq,
        include_part_d=True, part_d_base_annual_per_person=0.0,
    )
    assert nm == 0
    for nn in range(Cbar.shape[0]):
        for q in range(1, Nq):
            assert Cbar[nn, q] > Cbar[nn, q - 1], (
                f"Year nn={nn}: bracket {q} cost should exceed bracket {q-1}"
            )
