"""
Tests for pension module - pension benefit timing calculations.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import numpy as np
import pytest
from datetime import date

from owlplanner import pension


def test_compute_pension_benefits_single():
    """Single individual: pi_in has correct shape and non-zero where expected."""
    thisyear = date.today().year
    yob = thisyear - 66  # 66 years old now
    amounts = np.array([1000.0])
    ages = np.array([65.0])
    yobs = np.array([yob])
    mobs = np.array([1])
    horizons = np.array([20])
    N_i, N_n = 1, 20

    pi_in = pension.compute_pension_benefits(
        amounts, ages, yobs, mobs, horizons, N_i, N_n, thisyear=thisyear
    )
    assert pi_in.shape == (1, 20)
    assert np.sum(pi_in) > 0
    assert np.sum(pi_in) == pytest.approx(12 * 1000 * 20, rel=0.01)  # ~full 20 years


def test_compute_pension_benefits_couple():
    """Two individuals: pi_in has correct shape."""
    thisyear = date.today().year
    yobs = np.array([thisyear - 66, thisyear - 63])
    amounts = np.array([500.0, 0.0])
    ages = np.array([65.0, 65.0])
    mobs = np.array([1, 6])
    horizons = np.array([20, 20])
    N_i, N_n = 2, 20

    pi_in = pension.compute_pension_benefits(
        amounts, ages, yobs, mobs, horizons, N_i, N_n, thisyear=thisyear
    )
    assert pi_in.shape == (2, 20)
    assert np.sum(pi_in[0]) > 0
    assert np.sum(pi_in[1]) == 0


def test_compute_pension_benefits_zero_amounts():
    """All zero amounts: pi_in is all zeros."""
    thisyear = date.today().year
    amounts = np.array([0.0, 0.0])
    ages = np.array([65.0, 65.0])
    yobs = np.array([thisyear - 66, thisyear - 63])
    mobs = np.array([1, 1])
    horizons = np.array([20, 20])
    N_i, N_n = 2, 20

    pi_in = pension.compute_pension_benefits(
        amounts, ages, yobs, mobs, horizons, N_i, N_n, thisyear=thisyear
    )
    assert np.all(pi_in == 0)


def test_compute_pension_benefits_annual_conversion():
    """Output is annual (monthly × 12)."""
    thisyear = date.today().year
    amounts = np.array([100.0])  # $100/month
    ages = np.array([50.0])  # Start in past
    yobs = np.array([thisyear - 55])  # 55 now, started at 50
    mobs = np.array([1])
    horizons = np.array([10])
    N_i, N_n = 1, 10

    pi_in = pension.compute_pension_benefits(
        amounts, ages, yobs, mobs, horizons, N_i, N_n, thisyear=thisyear
    )
    # Should be 100*12 = 1200 per year for years 0-9 (already started)
    assert np.all(pi_in[0] == 1200)
