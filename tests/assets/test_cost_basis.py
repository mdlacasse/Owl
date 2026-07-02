"""
Tests for setCostBasis() — proper unrealized-gain tracking for taxable account withdrawals.

When a cost basis is provided, each withdrawal from the taxable account triggers
gain_fraction × withdrawal as capital gains instead of only this year's price appreciation.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

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
from datetime import date

import owlplanner as owl
from owlplanner.config import apply_config_to_plan, config_to_plan, plan_to_config


def _make_plan(name, taxable_k, tax_deferred_k, tax_free_k, rate_year=2000):
    thisyear = date.today().year
    p = owl.Plan(["Jack"], [f"{thisyear - 66}-01-15"], [80], name)
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[taxable_k], taxDeferred=[tax_deferred_k], taxFree=[tax_free_k], startDate="1-1")
    p.setInterpolationMethod("s-curve")
    p.setAllocationRatios("individual", generic=[[[80, 20, 0, 0], [80, 20, 0, 0]]])
    p.setPension([0], [65])
    p.setSocialSecurity([2000], [66])
    p.setRates("historical", rate_year)
    return p


class TestCostBasisNoRegression:
    """Without setCostBasis the solver must produce identical results to before."""

    def test_solves_without_basis(self):
        p = _make_plan("no_basis", taxable_k=500, tax_deferred_k=500, tax_free_k=100)
        p.solve("maxSpending")
        assert p.caseStatus == "solved"

    def test_q_n_positive_without_basis(self):
        """Taxable account with equity holdings should generate positive LTCG."""
        p = _make_plan("no_basis_qn", taxable_k=1000, tax_deferred_k=0, tax_free_k=0)
        p.solve("maxSpending")
        assert p.caseStatus == "solved"
        assert np.any(p.Q_n > 0), "Expected positive LTCG from taxable-only portfolio"


class TestCostBasisHighGain:
    """With 80% unrealized gain, Q_n must be materially larger than the no-basis case."""

    def test_higher_q_n_with_high_basis(self):
        taxable_k = 1000
        basis_k = 200  # $200k basis on $1M account → 80% gain fraction

        p_no_basis = _make_plan("hg_no_basis", taxable_k=taxable_k, tax_deferred_k=0, tax_free_k=0)
        p_no_basis.solve("maxSpending")

        p_with_basis = _make_plan("hg_with_basis", taxable_k=taxable_k, tax_deferred_k=0, tax_free_k=0)
        p_with_basis.setCostBasis([basis_k])
        p_with_basis.solve("maxSpending")

        assert p_with_basis.caseStatus == "solved"
        total_no_basis = float(np.sum(p_no_basis.Q_n))
        total_with_basis = float(np.sum(p_with_basis.Q_n))
        # With 80% gain fraction, capital gains should be substantially larger.
        assert total_with_basis > total_no_basis * 3, (
            f"Expected Q_n with basis (total={total_with_basis:,.0f}) to be >> no-basis (total={total_no_basis:,.0f})"
        )

    def test_lower_spending_with_higher_ltcg(self):
        """More LTCG tax burden should reduce max spending relative to no-basis case."""
        taxable_k = 1000

        p_no_basis = _make_plan("spend_no_basis", taxable_k=taxable_k, tax_deferred_k=0, tax_free_k=0)
        p_no_basis.solve("maxSpending")

        p_with_basis = _make_plan("spend_with_basis", taxable_k=taxable_k, tax_deferred_k=0, tax_free_k=0)
        p_with_basis.setCostBasis([200])  # 80% unrealized gain
        p_with_basis.solve("maxSpending")

        assert p_with_basis.caseStatus == "solved"
        # Higher LTCG tax → lower or equal max spending.
        assert p_with_basis.g_n[0] <= p_no_basis.g_n[0] + 1.0, (
            f"Expected spending with high-gain basis ({p_with_basis.g_n[0]:,.0f}) "
            f"<= no-basis spending ({p_no_basis.g_n[0]:,.0f})"
        )


class TestCostBasisEdgeCases:
    """Edge: zero basis (legacy fallback), basis equals balance (no gain), basis > balance (clamped)."""

    def test_zero_basis_means_legacy(self):
        """Zero basis → legacy approximation for that person (not 100% gain fraction)."""
        p_zero = _make_plan("zero_basis", taxable_k=500, tax_deferred_k=200, tax_free_k=0)
        p_zero.setCostBasis([0])
        p_zero.solve("maxSpending")
        assert p_zero.caseStatus == "solved"

        p_legacy = _make_plan("zero_basis_ref", taxable_k=500, tax_deferred_k=200, tax_free_k=0)
        p_legacy.solve("maxSpending")

        # Zero basis should behave identically to no basis (both use legacy approximation).
        np.testing.assert_allclose(p_zero.Q_n, p_legacy.Q_n, rtol=1e-6)

    def test_full_basis_no_extra_gain(self):
        """Basis equals current balance → gain_fraction = 0, same as holding cash (no embedded gain)."""
        taxable_k = 500
        p_full = _make_plan("full_basis", taxable_k=taxable_k, tax_deferred_k=200, tax_free_k=0)
        p_full.setCostBasis([taxable_k])  # basis == balance → gain_fraction = 0
        p_full.solve("maxSpending")

        p_no_basis = _make_plan("full_basis_ref", taxable_k=taxable_k, tax_deferred_k=200, tax_free_k=0)
        p_no_basis.solve("maxSpending")

        assert p_full.caseStatus == "solved"
        # With gain_fraction=0, capital gains from withdrawals collapse to nearly zero;
        # Q_n should be close to or less than the no-basis case (which uses annual appreciation).
        assert np.sum(p_full.Q_n) <= np.sum(p_no_basis.Q_n) + 1000

    def test_basis_exceeds_balance_clamped(self):
        """Basis > balance (e.g. from a loss) → gain_fraction clamped to 0, no tax on withdrawal."""
        p = _make_plan("excess_basis", taxable_k=500, tax_deferred_k=200, tax_free_k=0)
        p.setCostBasis([900])  # basis > balance: underwater position
        p.solve("maxSpending")
        assert p.caseStatus == "solved"


class TestCostBasisMixedCouple:
    """One spouse has known basis; the other's is unknown (zero → legacy)."""

    def test_mixed_basis_couple(self):
        thisyear = date.today().year
        p = owl.Plan(["Jack", "Jill"], [f"{thisyear - 62}-01-15", f"{thisyear - 59}-01-16"], [82, 79], "mixed_couple")
        p.setSpendingProfile("flat", 60)
        p.setAccountBalances(taxable=[500, 300], taxDeferred=[400, 200], taxFree=[50, 30], startDate="1-1")
        p.setInterpolationMethod("s-curve")
        p.setAllocationRatios(
            "individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]], [[60, 40, 0, 0], [60, 40, 0, 0]]]
        )
        p.setPension([0, 0], [65, 65])
        p.setSocialSecurity([2000, 1500], [67, 67])
        p.setRates("historical", 2000)

        # Jack: $100k basis on $500k account (80% gain fraction).
        # Jill: basis unknown → zero → legacy approximation.
        p.setCostBasis([100, 0])
        p.solve("maxSpending")
        assert p.caseStatus == "solved"

        # gain_fraction_in must exist (Jack has tracking) and be NaN for Jill.
        assert p.gain_fraction_in is not None
        assert not np.isnan(p.gain_fraction_in[0, 0]), "Jack should have tracked gain fraction"
        assert np.all(np.isnan(p.gain_fraction_in[1, :])), "Jill should use legacy (NaN)"

        # Q_n must be finite and positive (no NaN leaked into aggregation).
        assert np.all(np.isfinite(p.Q_n)), "Q_n must be finite (no NaN leakage)"
        assert np.any(p.Q_n > 0)


class TestCostBasisConvergence:
    """SC loop must converge within a reasonable number of iterations with basis tracking."""

    def test_sc_loop_converges(self):
        p = _make_plan("convergence", taxable_k=1500, tax_deferred_k=500, tax_free_k=200)
        p.setCostBasis([300])  # 80% gain fraction
        p.solve("maxSpending", {"withMedicare": "IRMAA"})
        assert p.caseStatus == "solved"
        assert p.convergenceType in ("monotonic", "oscillatory", "stagnation"), (
            f"Unexpected convergence type: {p.convergenceType}"
        )


class TestCostBasisValidation:
    def test_negative_basis_raises(self):
        p = _make_plan("neg_basis", taxable_k=500, tax_deferred_k=200, tax_free_k=0)
        with pytest.raises(ValueError, match="non-negative"):
            p.setCostBasis([-10])

    def test_gain_fraction_capped_at_one(self):
        assert owl.Plan._gain_fraction_from_basis(-100, 500) == 1.0
        assert owl.Plan._gain_fraction_from_basis(900, 500) == 0.0
        assert owl.Plan._gain_fraction_from_basis(200, 1000) == 0.8


class TestCostBasisConfig:
    def test_plan_to_config_roundtrip(self):
        p = _make_plan("rt", taxable_k=500, tax_deferred_k=200, tax_free_k=50)
        p.setCostBasis([200])
        diconf = plan_to_config(p)
        assert diconf["savings_assets"]["taxable_cost_basis"] == [200.0]
        p2 = config_to_plan(diconf, verbose=False, loadHFP=False)
        assert p2.taxable_basis_i is not None
        np.testing.assert_allclose(p2.taxable_basis_i, [200_000.0])

    def test_apply_config_clears_sticky_basis(self):
        p = _make_plan("sticky", taxable_k=500, tax_deferred_k=200, tax_free_k=50)
        p.setCostBasis([200])
        assert p.taxable_basis_i is not None

        diconf = plan_to_config(p)
        del diconf["savings_assets"]["taxable_cost_basis"]
        apply_config_to_plan(p, diconf)
        assert p.taxable_basis_i is None
        assert p.gain_fraction_in is None

    def test_toml_all_zeros_uses_legacy(self):
        p = _make_plan("zeros_toml", taxable_k=500, tax_deferred_k=200, tax_free_k=50)
        diconf = plan_to_config(p)
        diconf["savings_assets"]["taxable_cost_basis"] = [0.0]
        p2 = config_to_plan(diconf, verbose=False, loadHFP=False)
        assert p2.taxable_basis_i is None
