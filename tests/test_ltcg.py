"""
Tests for LTCG tax computation.

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


def test_capital_gain_tax_all_ltcg_in_20pct_bracket():
    """When ordinary income alone exceeds the 20% threshold, all LTCG is taxed at 20%."""
    Ni = 1
    Nn = 1
    nd = 1
    gamma_n = np.array([1.0])

    # Ordinary income alone is above the 20% threshold (545,500 for single).
    threshold20 = tx.capGainRates[0][1]  # 545_500
    ltcg = 50_000.0
    ord_income = threshold20 + 10_000.0  # well above threshold20; ltcg15 branch = 0

    tx_income_n = np.array([ord_income + ltcg])
    ltcg_n = np.array([ltcg])

    cg_tax_n = tx.capitalGainTax(Ni, tx_income_n, ltcg_n, gamma_n, nd, Nn)

    # All LTCG is at 20%; the ltcg15 = 0 branch is exercised.
    assert cg_tax_n[0] == pytest.approx(0.20 * ltcg)
