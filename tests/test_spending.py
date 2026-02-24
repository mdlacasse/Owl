"""
Tests for spending module - spending profile generation.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import numpy as np
import pytest

from owlplanner import spending


def test_gen_spending_profile_flat():
    """Flat profile: ones, with survivor fraction from n_d."""
    xi = spending.gen_spending_profile("flat", 0.5, 10, 20)
    assert len(xi) == 20
    assert np.all(xi[:10] == 1.0)
    assert np.all(xi[10:] == 0.5)


def test_gen_spending_profile_flat_n_d_at_end():
    """Flat profile with n_d >= N_n: no reduction."""
    xi = spending.gen_spending_profile("flat", 0.6, 20, 20)
    assert np.all(xi == 1.0)


def test_gen_spending_profile_smile_nonnegative():
    """Smile profile produces non-negative values."""
    xi = spending.gen_spending_profile("smile", 0.6, 15, 30, dip=15, increase=12, delay=5)
    assert np.all(xi >= 0)


def test_gen_spending_profile_smile_shape():
    """Smile profile has correct length."""
    xi = spending.gen_spending_profile("smile", 0.6, 10, 25)
    assert len(xi) == 25
