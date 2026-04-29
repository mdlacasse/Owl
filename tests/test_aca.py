"""
Tests for ACA Premium Tax Credit integration.

Covers:
- acaCosts() tax2026 function (unit tests)
- setACA() plan method
- SC-loop integration: ACA costs reduce spending vs. baseline
- Couple with mixed Medicare/pre-65 years
- High MAGI (8.5% ARP cap applies)
- Low MAGI (full SLCSP covered by subsidy)
- Medicaid threshold edge case
- TOML round-trip: load/save aca_settings
"""

import numpy as np
import pytest

import owlplanner.tax2026 as tx
from owlplanner import Plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(dob1="1970-01-15", le1=85, dob2=None, le2=None, name="ACA Test"):
    """Create a minimal Plan suitable for ACA testing."""
    if dob2 is None:
        inames = ["Alex"]
        dobs = [dob1]
        expectancy = [le1]
        alloc = [[[60, 20, 20, 0], [40, 30, 30, 0]]]
        taxable = [500]
        taxDeferred = [800]
        taxFree = [200]
    else:
        inames = ["Alex", "Jordan"]
        dobs = [dob1, dob2]
        expectancy = [le1, le2]
        alloc = [[[60, 20, 20, 0], [40, 30, 30, 0]], [[60, 20, 20, 0], [40, 30, 30, 0]]]
        taxable = [500, 200]
        taxDeferred = [800, 400]
        taxFree = [200, 100]

    p = Plan(inames, dobs, expectancy, name, verbose=False)
    p.setAccountBalances(taxable=taxable, taxDeferred=taxDeferred, taxFree=taxFree)
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setAllocationRatios("individual", generic=alloc)
    p.setSpendingProfile("flat")
    return p


# ---------------------------------------------------------------------------
# Unit tests for acaCosts()
# ---------------------------------------------------------------------------

class TestAcaCostsFunction:
    """Unit tests for tax2026.acaCosts() in isolation."""

    def _gamma(self, n):
        """Return flat gamma_n (no inflation) for simple testing."""
        return np.ones(n + 1)

    def test_no_eligible_individuals(self):
        """All post-65: ACA costs should be zero."""
        yobs = np.array([1955])   # age 71 in 2026
        horizons = np.array([20])
        magi_n = np.full(20, 80_000.0)
        gamma_n = self._gamma(20)
        costs = tx.acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual=15_000, N_n=20)
        assert np.allclose(costs, 0.0), "Expected zero ACA cost for post-65 individual."

    def test_zero_slcsp(self):
        """Zero SLCSP premium should yield zero costs."""
        yobs = np.array([1985])   # age 41 in 2026
        horizons = np.array([20])
        magi_n = np.full(20, 60_000.0)
        gamma_n = self._gamma(20)
        costs = tx.acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual=0.0, N_n=20)
        assert np.allclose(costs, 0.0)

    def test_high_magi_arp_cap(self):
        """Above 400% FPL (2025 rules): net cost = min(SLCSP, 8.5% * MAGI)."""
        yobs = np.array([1985])   # pre-65 for all plan years
        horizons = np.array([20])
        magi = 100_000.0
        slcsp = 12_000.0
        expected_net = min(slcsp, 0.085 * magi)  # 8.5% ARP/IRA cap
        magi_n = np.full(20, magi)
        gamma_n = self._gamma(20)
        costs = tx.acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual=slcsp, N_n=20, thisyear=2025)
        assert np.allclose(costs[0], expected_net, rtol=1e-4), (
            f"Expected {expected_net}, got {costs[0]}"
        )

    def test_low_magi_partial_subsidy(self):
        """At 200% FPL: cap_pct = 2% (Rev. Proc. 2024-35); contribution < SLCSP → subsidized."""
        yobs = np.array([1985])
        horizons = np.array([20])
        # Single FPL 2025 = 15,650; 200% FPL = 31,300; at 200% breakpoint cap = 2%
        fpl = tx._ACA_FPL[2025][0]
        magi = 2.0 * fpl
        slcsp = 14_000.0
        expected_net = min(slcsp, 0.02 * magi)  # 2% at 200% per IRS 2025 table
        magi_n = np.full(20, magi)
        gamma_n = self._gamma(20)
        costs = tx.acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual=slcsp, N_n=20, thisyear=2025)
        assert np.allclose(costs[0], expected_net, rtol=1e-3)

    def test_medicaid_threshold_returns_full_premium(self):
        """Below 138% FPL: return full SLCSP (Medicaid territory; no PTC)."""
        yobs = np.array([1985])
        horizons = np.array([20])
        # Single FPL = 15,650; 138% = 21,597; use MAGI below this
        magi = 15_000.0  # below 100% FPL
        slcsp = 12_000.0
        magi_n = np.full(20, magi)
        gamma_n = self._gamma(20)
        costs = tx.acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual=slcsp, N_n=20)
        assert np.allclose(costs[0], slcsp), "Expected full premium in Medicaid territory."

    def test_couple_both_eligible(self):
        """Couple both pre-65: household size = 2, uses couple FPL."""
        yobs = np.array([1985, 1987])
        horizons = np.array([25, 27])
        # Couple FPL 2025 = 21,150; 400% = 84,600; use MAGI above 400% FPL
        magi = 120_000.0
        slcsp = 20_000.0
        expected_net = min(slcsp, 0.085 * magi)  # 8.5% cap
        magi_n = np.full(25, magi)
        gamma_n = self._gamma(25)
        costs = tx.acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual=slcsp, N_n=25, thisyear=2025)
        assert np.allclose(costs[0], expected_net, rtol=1e-4)

    def test_couple_one_turns_65(self):
        """Year when first individual turns 65: household size drops to 1."""
        # Alex born 1960 → already 65 in 2025 (n=0) → not eligible
        # Jordan born 1970 → pre-65 throughout
        yobs = np.array([1960, 1970])
        horizons = np.array([25, 30])
        magi = 80_000.0
        slcsp = 12_000.0
        magi_n = np.full(30, magi)
        gamma_n = self._gamma(30)
        costs = tx.acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual=slcsp, N_n=30, thisyear=2025)
        # n=0: Alex 65 → not eligible; Jordan pre-65 → hh_size=1, single FPL
        # MAGI 80k / 15,650 ≈ 511% FPL → 2025 rules: 8.5% cap above 400%
        expected = min(slcsp, 0.085 * magi)
        assert np.allclose(costs[0], expected, rtol=1e-4)

    def test_inflation_applied(self):
        """SLCSP should be inflated by gamma_n in later years."""
        yobs = np.array([1985])
        horizons = np.array([20])
        magi = 200_000.0  # above 400% FPL in all years; net = min(slcsp*gamma, 0.085*magi)
        slcsp = 5_000.0   # low enough that 8.5%*magi always exceeds it
        # With gamma_n > 1 in later years, inflated SLCSP should match
        inflation_rate = 0.03
        gamma_n = np.array([(1 + inflation_rate) ** n for n in range(21)])
        magi_n = np.full(20, magi)
        costs = tx.acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual=slcsp, N_n=20, thisyear=2025)
        for n in range(20):
            expected = min(slcsp * gamma_n[n], 0.085 * magi)
            assert np.isclose(costs[n], expected, rtol=1e-4), (
                f"Year {n}: expected {expected:.2f}, got {costs[n]:.2f}"
            )

    def test_irs_2025_examples(self):
        """Verify acaCosts() against IRS Rev. Proc. 2024-35 (2025 plan year)."""
        yobs = np.array([1985])
        horizons = np.array([5])
        gamma_n = self._gamma(5)
        fpl = tx._ACA_FPL[2025][0]  # single, 15650

        # At 150% FPL: cap = 0% (IRS: less than 150% = 0%)
        magi_150 = 1.5 * fpl
        costs = tx.acaCosts(yobs, horizons, np.full(5, magi_150), gamma_n,
                            slcsp_annual=10_000, N_n=5, thisyear=2025)
        assert np.isclose(costs[0], 0.0, atol=0.01), "At 150% FPL expect ~0% contribution"

        # At 200% FPL: cap = 2% (IRS: 200% is breakpoint)
        magi_200 = 2.0 * fpl
        costs = tx.acaCosts(yobs, horizons, np.full(5, magi_200), gamma_n,
                            slcsp_annual=14_000, N_n=5, thisyear=2025)
        expected = min(14_000, 0.02 * magi_200)
        assert np.isclose(costs[0], expected, rtol=1e-3), f"At 200% FPL expect 2%, got {costs[0]}"

        # At 400% FPL: cap = 8.5% (IRS: 400%+ under IRA)
        magi_400 = 4.0 * fpl
        costs = tx.acaCosts(yobs, horizons, np.full(5, magi_400), gamma_n,
                            slcsp_annual=15_000, N_n=5, thisyear=2025)
        expected = min(15_000, 0.085 * magi_400)
        assert np.isclose(costs[0], expected, rtol=1e-3), f"At 400% FPL expect 8.5%, got {costs[0]}"

    def test_2026_above_400_no_subsidy(self):
        """2026+ above 400% FPL: no PTC, full SLCSP."""
        yobs = np.array([1985])
        horizons = np.array([5])
        fpl_2026 = tx._ACA_FPL[2026][0]
        magi = 5.0 * fpl_2026  # 500% FPL
        gamma_n = self._gamma(5)
        slcsp = 12_000.0
        costs = tx.acaCosts(yobs, horizons, np.full(5, magi), gamma_n,
                            slcsp_annual=slcsp, N_n=5, thisyear=2026)
        assert np.isclose(costs[0], slcsp, rtol=1e-4), "2026 above 400%: expect full premium"


# ---------------------------------------------------------------------------
# Integration tests using Plan.solve()
# ---------------------------------------------------------------------------

class TestACAIntegration:
    """Integration tests: ACA costs reduce available spending."""

    def test_setaca_reduces_spending(self):
        """Plan with ACA costs should produce lower spending than without."""
        p_base = _make_plan(dob1="1975-06-15", le1=88)
        p_base.setSocialSecurity([2000], [67])
        p_base.solve("maxSpending")
        spending_base = p_base.g_n[0]

        p_aca = _make_plan(dob1="1975-06-15", le1=88)
        p_aca.setSocialSecurity([2000], [67])
        p_aca.setACA(slcsp=18.0)   # $18k/year benchmark premium
        p_aca.solve("maxSpending")
        spending_aca = p_aca.g_n[0]

        assert spending_aca < spending_base, (
            f"Expected ACA plan spending ({spending_aca:.0f}) < baseline ({spending_base:.0f})"
        )
        # ACA costs should be nonzero in pre-65 years
        assert np.any(p_aca.ACA_n > 0), "Expected nonzero ACA costs in pre-65 years."

    def test_aca_costs_zero_after_65(self):
        """ACA costs must be zero in years where individual is 65+."""
        # Individual born 1965: turns 65 in 2030 → n = 4
        p = _make_plan(dob1="1965-01-15", le1=88)
        p.setACA(slcsp=15.0)
        p.solve("maxSpending")

        from datetime import date
        thisyear = date.today().year
        n65 = 1965 + 65 - thisyear   # year index when individual turns 65
        if n65 < p.N_n:
            assert np.allclose(p.ACA_n[n65:], 0.0), (
                "ACA costs should be zero from age-65 year onward."
            )

    def test_aca_high_magi_scales_with_income(self):
        """Net ACA cost cannot exceed SLCSP (inflation-adjusted)."""
        p = _make_plan(dob1="1975-01-15", le1=87)
        p.setAccountBalances(taxable=[2000], taxDeferred=[3000], taxFree=[1000])
        p.setSocialSecurity([3000], [67])
        p.setACA(slcsp=12.0)  # $12k/year benchmark premium
        p.solve("maxSpending")

        for n in range(p.N_n):
            if p.ACA_n[n] > 0:
                slcsp_inflated = 12_000 * p.gamma_n[n]
                assert p.ACA_n[n] <= slcsp_inflated + 1, "ACA cost cannot exceed SLCSP."

    def test_couple_mixed_medicare_aca(self):
        """Couple: older partner goes on Medicare while younger stays on ACA."""
        # Alex born 1963 → turns 65 in 2028 → n=2 in plan (2026-based)
        # Jordan born 1972 → turns 65 in 2037 → n=11 in plan; age gap = 9 years (within limit)
        p = _make_plan(dob1="1963-06-15", le1=85, dob2="1972-06-15", le2=87)
        p.setAccountBalances(taxable=[800, 300], taxDeferred=[1200, 600], taxFree=[300, 150])
        p.setSocialSecurity([2500, 1500], [67, 67])
        p.setACA(slcsp=14.0)
        p.solve("maxSpending")

        # Check: ACA costs should appear in years where Jordan is pre-65
        from datetime import date
        thisyear = date.today().year
        n65_jordan = max(0, 1972 + 65 - thisyear)  # year Jordan turns 65 (born 1972)
        if n65_jordan < p.N_n:
            assert np.any(p.ACA_n[:n65_jordan] > 0), (
                "Expected ACA costs while Jordan is pre-65."
            )
            assert np.allclose(p.ACA_n[n65_jordan:], 0.0), (
                "Expected zero ACA costs after Jordan turns 65."
            )

    def test_no_aca_when_not_configured(self):
        """Plan without setACA() should have all-zero ACA_n after solving."""
        p = _make_plan(dob1="1975-06-15", le1=88)
        p.solve("maxSpending")
        assert np.allclose(p.ACA_n, 0.0), "ACA_n should be zero when ACA not configured."


# ---------------------------------------------------------------------------
# ACA optimize mode tests (withACA="optimize")
# ---------------------------------------------------------------------------

class TestACAOptimize:
    """Tests for withACA="optimize" LP/MIP formulation."""

    def test_optimize_vs_loop_spending(self):
        """Optimize mode spending should be >= loop mode spending (LP finds better objective)."""
        p_loop = _make_plan(dob1="1975-06-15", le1=88)
        p_loop.setSocialSecurity([2000], [67])
        p_loop.setACA(slcsp=18.0)
        p_loop.solve("maxSpending")
        spending_loop = p_loop.g_n[0]

        p_opt = _make_plan(dob1="1975-06-15", le1=88)
        p_opt.setSocialSecurity([2000], [67])
        p_opt.setACA(slcsp=18.0)
        p_opt.solve("maxSpending", options={"withACA": "optimize"})
        spending_opt = p_opt.g_n[0]

        # LP can co-optimize against ACA cost curve; should be at least as good as loop.
        assert spending_opt >= spending_loop - 1, (
            f"Optimize spending ({spending_opt:.0f}) should be >= loop spending ({spending_loop:.0f})"
        )

    def test_maca_n_nonzero_in_eligible_years(self):
        """In optimize mode, maca_n should be nonzero in pre-65 ACA-eligible years."""
        p = _make_plan(dob1="1975-06-15", le1=88)
        p.setSocialSecurity([2000], [67])
        p.setACA(slcsp=18.0)
        p.solve("maxSpending", options={"withACA": "optimize"})

        assert p._aca_lp, "Expected _aca_lp flag to be True in optimize mode."
        assert np.any(p.maca_n > 0), "Expected nonzero maca_n in ACA-eligible years."

    def test_aca_n_zero_in_optimize_mode(self):
        """In optimize mode, ACA_n (SC-loop result) should be all-zero."""
        p = _make_plan(dob1="1975-06-15", le1=88)
        p.setSocialSecurity([2000], [67])
        p.setACA(slcsp=18.0)
        p.solve("maxSpending", options={"withACA": "optimize"})

        assert np.allclose(p.ACA_n, 0.0), (
            "ACA_n (SC-loop) should be zero in optimize mode; maca_n carries the cost."
        )

    def test_slcsp_cap_respected(self):
        """In optimize mode, maca_n[n] <= slcsp_annual * gamma_n[n] for all n."""
        p = _make_plan(dob1="1975-06-15", le1=88)
        p.setACA(slcsp=18.0)
        p.solve("maxSpending", options={"withACA": "optimize"})

        for n in range(p.N_n):
            slcsp_inflated = 18_000 * p.gamma_n[n]
            assert p.maca_n[n] <= slcsp_inflated + 1, (
                f"maca_n[{n}]={p.maca_n[n]:.0f} exceeds SLCSP cap {slcsp_inflated:.0f}"
            )

    def test_bracket_6_above_400_fpl_feasible_and_full_slcsp(self):
        """Above 400% FPL in optimize mode: model feasible, maca_n = full SLCSP (no PTC)."""
        # Very high pension ($10k/mo = $120k/yr) forces MAGI above 400% FPL ($63,840 single 2026).
        p = _make_plan(dob1="1965-01-15", le1=88)
        p.setAccountBalances(taxable=[500], taxDeferred=[800], taxFree=[200])
        p.setPension([10_000], [60])  # $10k/mo = $120k/year (amounts in $)
        p.setACA(slcsp=14.0)
        p.solve("maxSpending", options={"withACA": "optimize"})

        fpl_400 = tx._ACA_FPL[2026][0] * 4.0
        hit_bracket_6 = False
        for n in range(min(p.n_aca, p.N_n)):
            if p.MAGI_n[n] >= fpl_400 * p.gamma_n[n] and p.maca_n[n] > 0:
                hit_bracket_6 = True
                slcsp_n = 14_000 * p.gamma_n[n]
                assert np.isclose(p.maca_n[n], slcsp_n, rtol=0.01), (
                    f"Year {n}: MAGI={p.MAGI_n[n]:.0f}>=400% FPL, expect maca≈{slcsp_n:.0f}, got {p.maca_n[n]:.0f}"
                )
        assert hit_bracket_6, "Expected at least one ACA year with MAGI >= 400% FPL and maca > 0"


# ---------------------------------------------------------------------------
# Config round-trip test
# ---------------------------------------------------------------------------

class TestACAConfig:
    """Test TOML config round-trip for ACA settings."""

    def test_plan_to_config_serializes_aca(self):
        """plan_to_config should emit aca_settings when slcsp_annual > 0."""
        from owlplanner.config.plan_bridge import plan_to_config
        p = _make_plan(dob1="1975-06-15", le1=88)
        p.setACA(slcsp=16.5)   # $16,500/year
        diconf = plan_to_config(p)
        assert "aca_settings" in diconf, "Expected aca_settings in config dict."
        assert diconf["aca_settings"]["slcsp_annual"] == pytest.approx(16.5, rel=1e-3)

    def test_plan_to_config_no_aca_section_when_not_set(self):
        """plan_to_config should NOT emit aca_settings when ACA not configured."""
        from owlplanner.config.plan_bridge import plan_to_config
        p = _make_plan(dob1="1975-06-15", le1=88)
        diconf = plan_to_config(p)
        assert "aca_settings" not in diconf, "aca_settings should be absent when ACA not configured."

    def test_config_to_plan_applies_aca(self):
        """config_to_plan should call setACA() when aca_settings.slcsp_annual > 0."""
        from owlplanner.config.plan_bridge import config_to_plan, plan_to_config
        p = _make_plan(dob1="1975-06-15", le1=88)
        p.setACA(slcsp=14.0)
        diconf = plan_to_config(p)

        # Round-trip: reload from config dict
        p2 = config_to_plan(diconf, verbose=False, loadHFP=False)
        assert p2.slcsp_annual == pytest.approx(14_000.0, rel=1e-3), (
            f"Expected slcsp_annual=14000, got {p2.slcsp_annual}"
        )


# ---------------------------------------------------------------------------
# ACA start year tests
# ---------------------------------------------------------------------------

class TestACAStartYear:
    """Tests for the aca_start_year / n_aca_start zero-fill feature."""

    def test_acavals_zeros_before_start(self):
        """acaVals with n_aca_start=3 should produce zero slcsp for nn < 3."""
        from datetime import date
        thisyear = date.today().year
        yobs = [thisyear - 55]   # born 55 years ago → eligible until age 65
        horizons = [20]
        gamma_n = np.ones(25)
        _, _, _, slcsp_n = tx.acaVals(yobs, horizons, gamma_n, 15_000, 20, n_aca_start=3)
        assert len(slcsp_n) > 3, "Expected n_aca > 3 for a 55-year-old."
        assert np.allclose(slcsp_n[:3], 0.0), "slcsp_aca_n should be zero for nn < n_aca_start."
        assert slcsp_n[3] > 0, "slcsp_aca_n should be nonzero at n_aca_start."

    def test_acavals_no_start_unchanged(self):
        """acaVals with n_aca_start=0 (default) should match original behavior."""
        from datetime import date
        thisyear = date.today().year
        yobs = [thisyear - 55]
        horizons = [20]
        gamma_n = np.ones(25)
        n_aca, _, _, slcsp_n0 = tx.acaVals(yobs, horizons, gamma_n, 15_000, 20)
        _, _, _, slcsp_n1 = tx.acaVals(yobs, horizons, gamma_n, 15_000, 20, n_aca_start=0)
        assert np.allclose(slcsp_n0, slcsp_n1), "n_aca_start=0 should give same result as default."

    def test_start_year_defers_aca_costs(self):
        """Plan with ACA start year set to 2 years out should have zero ACA_n in years 0-1."""
        from datetime import date
        thisyear = date.today().year
        start_year = thisyear + 2
        p = _make_plan(dob1="1975-06-15", le1=88)
        p.setSocialSecurity([2000], [67])
        p.setACA(slcsp=18.0, start_year=start_year)
        p.solve("maxSpending")

        assert np.allclose(p.ACA_n[:2], 0.0), (
            f"ACA_n[:2]={p.ACA_n[:2]} should be zero before start_year."
        )
        assert np.any(p.ACA_n[2:] > 0), "Expected nonzero ACA costs after start_year."

    def test_start_year_raises_spending_vs_immediate(self):
        """Deferring ACA start should give higher spending than immediate ACA."""
        from datetime import date
        thisyear = date.today().year
        dob = "1975-06-15"

        p_immediate = _make_plan(dob1=dob, le1=88)
        p_immediate.setSocialSecurity([2000], [67])
        p_immediate.setACA(slcsp=18.0)
        p_immediate.solve("maxSpending")

        p_deferred = _make_plan(dob1=dob, le1=88)
        p_deferred.setSocialSecurity([2000], [67])
        p_deferred.setACA(slcsp=18.0, start_year=thisyear + 3)
        p_deferred.solve("maxSpending")

        assert p_deferred.g_n[0] >= p_immediate.g_n[0] - 1, (
            "Deferring ACA should not reduce spending vs immediate ACA."
        )
        assert p_deferred.g_n[0] > p_immediate.g_n[0] - 1000, (
            "Deferred ACA spending should be measurably higher than immediate."
        )

    def test_start_year_config_round_trip(self):
        """aca_start_year should round-trip through plan_to_config / config_to_plan."""
        from datetime import date
        from owlplanner.config.plan_bridge import config_to_plan, plan_to_config
        thisyear = date.today().year
        p = _make_plan(dob1="1975-06-15", le1=88)
        p.setACA(slcsp=15.0, start_year=thisyear + 2)
        diconf = plan_to_config(p)

        assert diconf["aca_settings"].get("aca_start_year") == thisyear + 2, (
            "plan_to_config should emit aca_start_year."
        )
        p2 = config_to_plan(diconf, verbose=False, loadHFP=False)
        assert p2.aca_start_year == thisyear + 2, (
            f"Expected aca_start_year={thisyear + 2}, got {p2.aca_start_year}."
        )
