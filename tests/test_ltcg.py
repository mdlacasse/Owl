"""
Tests for LTCG tax computation.
"""

import numpy as np
import pytest

from owlplanner import tax2026 as tx


def test_capital_gain_tax_stacks_over_ordinary_income():
    """Verify LTCG tax stacks over ordinary income thresholds."""
    Ni = 1
    Nn = 1
    nd = 1
    gamma_n = np.array([1.0])

    # Ordinary income below 15% threshold, LTCG pushes above.
    tx_income_n = np.array([60_000.0])
    ltcg_n = np.array([20_000.0])

    cg_tax_n = tx.capitalGainTax(Ni, tx_income_n, ltcg_n, gamma_n, nd, Nn)

    # 15% bracket applies only to the portion above 49,450.
    assert cg_tax_n[0] == pytest.approx(0.15 * (60_000.0 - 49_450.0))


def test_capital_gain_tax_reaches_20_percent_bracket():
    """Verify LTCG tax applies 15% and 20% tiers when applicable."""
    Ni = 1
    Nn = 1
    nd = 1
    gamma_n = np.array([1.0])

    # Ordinary income plus LTCG crosses 20% threshold.
    tx_income_n = np.array([600_000.0])
    ltcg_n = np.array([100_000.0])

    cg_tax_n = tx.capitalGainTax(Ni, tx_income_n, ltcg_n, gamma_n, nd, Nn)

    ltcg20 = 600_000.0 - 545_500.0
    ltcg15 = 100_000.0 - ltcg20
    expected = 0.20 * ltcg20 + 0.15 * ltcg15

    assert cg_tax_n[0] == pytest.approx(expected)
