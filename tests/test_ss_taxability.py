"""
Tests for Social Security taxability (Psi_n) computation via the SC loop.

Validates that the self-consistent loop:
- Produces Psi_n values bounded in [0, 0.85] for all SS-active years
- Correctly assigns Psi_n ≈ 0.85 when provisional income >> P_hi (cap is binding)
- Produces varying Psi_n when income changes across years

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
from datetime import date

import owlplanner as owl
from owlplanner import tax2026 as tx

# Force HiGHS for reproducible results across environments (matches GitHub CI).
solver = 'HiGHS'


def _make_couple_plan(name, taxable, tax_deferred, tax_free, ss_pias, ss_ages,
                      pension=None, pension_ages=None, rate_year=2000, expectancy=None):
    """
    Create a minimal Jack+Jill-style couple plan using historical rates.

    Note: setPension() amounts are monthly $ (same units as SS PIAs).
    expectancy defaults to [80, 80]; pass a shorter value to reduce MIP size.
    """
    thisyear = date.today().year
    inames = ['Jack', 'Jill']
    # Jack 66 (past SS age), Jill 63 — both within expected SS window.
    dobs = [f"{thisyear - 66}-01-15", f"{thisyear - 63}-01-16"]
    if expectancy is None:
        expectancy = [80, 80]

    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile('flat', 60)
    p.setAccountBalances(taxable=taxable, taxDeferred=tax_deferred, taxFree=tax_free, startDate="1-1")
    p.setInterpolationMethod('s-curve')
    p.setAllocationRatios('individual',
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]],
                                   [[50, 50, 0, 0], [70, 30, 0, 0]]])
    if pension is not None:
        p.setPension(pension, pension_ages)
    else:
        p.setPension([0, 0], [65, 65])

    p.setSocialSecurity(ss_pias, ss_ages)   # No tax_fraction → dynamic SC-loop computation
    p.setRates('historical', rate_year)
    return p


def test_ss_feasible_and_bounded():
    """
    Verify that the SC loop produces Psi_n values strictly bounded in [0, 0.85]
    for all SS-active years of a typical couple plan.

    Note: When SS income is below the standard deduction, Psi_n may take any
    value in [0, 0.85] without affecting taxes (degenerate objective), so we
    only assert the valid range.
    """
    p = _make_couple_plan(
        'ss_feasible',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
        pension=[0, 10], pension_ages=[65, 65],
    )
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    assert ss_mask.any(), "Expected some SS-active years"
    psi_ss = p.Psi_n[ss_mask]
    assert np.all(psi_ss <= 0.85 + 1e-6), f"Psi_n exceeded 0.85: {psi_ss.max():.4f}"
    assert np.all(psi_ss >= 0.0 - 1e-6), f"Psi_n went negative: {psi_ss.min():.4f}"


def test_ss_max_bracket():
    """
    High-income household: large monthly pensions push PI well above P_hi=$44k (MFJ)
    during the joint period.

    With pension=$3,500/month each ($42k/year) and SS of $30k+$24k/year:
      - Joint PI: $84k + 0.5*$54k ≈ $111k >> P_hi=$44k → cap binds: Psi_n ≈ 0.85

    We check only the joint SS years (both spouses alive), where PI is clearly above
    the cap.  After the first spouse dies, solo income may be lower.
    """
    p = _make_couple_plan(
        'ss_max',
        taxable=[100, 50], tax_deferred=[500, 200], tax_free=[100, 50],
        ss_pias=[2_500, 2_000], ss_ages=[66, 66],
        # $3,500/month each = $42,000/year each (monthly dollar units for setPension)
        pension=[3_500, 3_500], pension_ages=[65, 65],
    )
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    assert ss_mask.any(), "Expected some SS-active years"
    # Check only joint years (both spouses alive) — solo years may have lower Psi_n.
    joint_mask = np.arange(p.N_n) < p.n_d
    joint_ss_mask = ss_mask & joint_mask
    assert joint_ss_mask.any(), "Expected some joint SS-active years"
    psi_joint = p.Psi_n[joint_ss_mask]
    # During joint years, combined PI >> P_hi, so the 85% cap should be binding.
    assert np.all(psi_joint > 0.84), f"Expected Psi_n≈0.85 for joint SS years, got min={psi_joint.min():.4f}"


def test_ss_partial_bracket():
    """
    Moderate-income household: Psi_n should fall between 0 and 0.85 in some SS years.
    Confirms the SC loop handles the intermediate bracket and produces valid Psi_n values.
    """
    p = _make_couple_plan(
        'ss_partial',
        taxable=[30, 20], tax_deferred=[200, 80], tax_free=[30, 20],
        ss_pias=[1_500, 1_200], ss_ages=[67, 67],
        pension=[5, 0], pension_ages=[65, 65],
    )
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    assert ss_mask.any(), "Expected some SS-active years"
    psi_ss = p.Psi_n[ss_mask]
    assert psi_ss.max() <= 0.85 + 1e-6, f"Psi_n exceeded 0.85: {psi_ss.max():.4f}"
    assert psi_ss.min() >= 0.0 - 1e-6, f"Psi_n went negative: {psi_ss.min():.4f}"


def test_compute_social_security_taxability_override():
    """When ssec_tax_fraction is set, return constant array."""
    N_n = 10
    MAGI_n = np.zeros(N_n)
    ss_n = np.ones(N_n) * 30_000
    psi = tx.compute_social_security_taxability(1, MAGI_n, ss_n, ssec_tax_fraction=0.5)
    assert np.all(psi == 0.5)


def test_compute_social_security_taxability_single_low_pi():
    """Single filer with PI < $25k: 0% taxable."""
    MAGI_n = np.array([20_000.0])
    ss_n = np.array([20_000.0])  # PI = 20k - 10k = 10k < 25k
    psi = tx.compute_social_security_taxability(1, MAGI_n, ss_n)
    assert psi[0] == pytest.approx(0.0)


def test_compute_social_security_taxability_single_high_pi():
    """Single filer with PI >> $34k: 85% cap binding."""
    MAGI_n = np.array([100_000.0])
    ss_n = np.array([30_000.0])  # PI = 100k - 15k = 85k >> 34k
    psi = tx.compute_social_security_taxability(1, MAGI_n, ss_n)
    assert psi[0] == pytest.approx(0.85)


def test_compute_social_security_taxability_mfj_high_pi():
    """MFJ with PI >> $44k: 85% cap binding."""
    MAGI_n = np.array([150_000.0])
    ss_n = np.array([50_000.0])  # PI = 150k - 25k = 125k >> 44k
    psi = tx.compute_social_security_taxability(2, MAGI_n, ss_n)
    assert psi[0] == pytest.approx(0.85)


def test_compute_social_security_taxability_zero_ss():
    """When ss_n is zero, return 0.85 (default, no division)."""
    MAGI_n = np.array([50_000.0])
    ss_n = np.array([0.0])
    psi = tx.compute_social_security_taxability(1, MAGI_n, ss_n)
    assert psi[0] == pytest.approx(0.85)


def test_ss_dynamic_psi_varies():
    """
    Confirm that dynamic SC-loop SS taxability is active when tax_fraction is not set:
      - p.ssecTaxFraction is None
      - Psi_n values vary (not uniformly fixed at the 0.85 default)
    """
    p = _make_couple_plan(
        'ss_dynamic',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
    )
    assert p.ssecTaxFraction is None, "Expected dynamic SC-loop mode (no tax_fraction)"
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    assert ss_mask.any(), "Expected some SS-active years"
    # Psi_n should vary across years (not uniformly 0.85 as in fixed-fraction mode).
    assert not np.all(p.Psi_n[ss_mask] == 0.85), "Expected dynamic Psi_n, not fixed at 0.85"


def test_ss_lp_feasible_and_bounded():
    """
    LP-based SS taxability (withSSTaxability='optimize') should produce
    Psi_n values bounded in [0, 0.85] for all SS-active years.

    Uses a shortened expectancy=[73, 73] (N_n≈10 vs 17) to keep the MIP small:
    Jack (66→73) gets SS from age 67; Jill (63→73) gets SS from age 70.
    """
    p = _make_couple_plan(
        'ss_lp_feasible',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
        pension=[0, 10], pension_ages=[65, 65],
        expectancy=[73, 73],
    )
    p.solve('maxSpending', {'solver': solver, 'withSSTaxability': 'optimize', 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    assert ss_mask.any(), "Expected some SS-active years"
    psi_ss = p.Psi_n[ss_mask]
    assert np.all(psi_ss <= 0.85 + 1e-6), f"Psi_n exceeded 0.85: {psi_ss.max():.4f}"
    assert np.all(psi_ss >= 0.0 - 1e-6), f"Psi_n went negative: {psi_ss.min():.4f}"


def test_ss_lp_max_bracket():
    """
    LP-based SS taxability: high-income household should yield Psi_n ≈ 0.85
    during joint SS years, matching the SC-loop result.

    Uses expectancy=[73, 73] (N_n≈10): Jill's SS starts at year 3 (age 66),
    giving joint SS years 3–6 to verify the 85% cap — without a full 17-year MIP.
    """
    p = _make_couple_plan(
        'ss_lp_max',
        taxable=[100, 50], tax_deferred=[500, 200], tax_free=[100, 50],
        ss_pias=[2_500, 2_000], ss_ages=[66, 66],
        pension=[3_500, 3_500], pension_ages=[65, 65],
        expectancy=[73, 73],
    )
    p.solve('maxSpending', {'solver': solver, 'withSSTaxability': 'optimize', 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    joint_mask = np.arange(p.N_n) < p.n_d
    joint_ss_mask = ss_mask & joint_mask
    assert joint_ss_mask.any(), "Expected some joint SS-active years"
    psi_joint = p.Psi_n[joint_ss_mask]
    assert np.all(psi_joint > 0.84), (
        f"Expected Psi_n≈0.85 for joint SS years, got min={psi_joint.min():.4f}"
    )


def test_ss_lp_vs_loop_consistency():
    """
    LP-based SS taxability should produce an objective no worse than the SC-loop,
    and Psi_n should be in [0, 0.85].

    The LP formulation is exact (MIP), so it may find a better optimum than the
    iterative SC-loop, which can oscillate.  Psi_n values may legitimately differ
    because the LP finds a different (better) allocation.

    Uses expectancy=[73, 73] (N_n≈10) to keep the MIP small: Jack (66→73) has SS
    years 1–6 and Jill (63→73) has SS years 7–9, giving 9/10 SS-active years.
    """
    p = _make_couple_plan(
        'ss_consistency',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
        pension=[500, 200], pension_ages=[65, 65],
        expectancy=[73, 73],
    )
    # SC-loop solve
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"SC-loop solver failed: {p.caseStatus}"
    obj_loop = p.g_n[0]   # nominal spending in year 0 (objective proxy)

    # LP-based solve (exact MIP formulation)
    p.solve('maxSpending', {'solver': solver, 'withSSTaxability': 'optimize', 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"LP solver failed: {p.caseStatus}"
    obj_lp = p.g_n[0]
    psi_lp = p.Psi_n.copy()

    # LP objective should be no worse than the SC-loop (exact ≥ approximate).
    # Allow a small tolerance for numerical noise.
    assert obj_lp >= obj_loop * 0.99, (
        f"LP objective worse than SC-loop by more than 1%: loop={obj_loop:,.0f}, lp={obj_lp:,.0f}"
    )

    # Psi_n from LP must stay in [0, 0.85].
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    if ss_mask.any():
        psi_ss = psi_lp[ss_mask]
        assert np.all(psi_ss <= 0.85 + 1e-6), f"Psi_n (LP) exceeded 0.85: {psi_ss.max():.4f}"
        assert np.all(psi_ss >= 0.0 - 1e-6), f"Psi_n (LP) went negative: {psi_ss.min():.4f}"


def test_historical_crash_years_feasible():
    """
    Regression test: verify that 1973–74 bear-market rates do not cause infeasibility.
    The SC loop must set Psi_n = 0 when provisional income PI < 0 (large capital losses).

    Uses rate_year=1972 so that plan years 1–2 use 1973–74 historical returns
    (-37% and -26% equities), and expectancy=[73, 73] for a small N_n≈10 plan.
    """
    p = _make_couple_plan(
        'ss_crash_years',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
        expectancy=[73, 73],
        rate_year=1972,   # year 1 = 1973 crash (-37%), year 2 = 1974 crash (-26%)
    )
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', (
        f"Solver failed under 1973–74 crash rates: {p.caseStatus}"
    )
    # Psi_n must stay in [0, 0.85] even under extreme negative returns.
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    if ss_mask.any():
        psi_ss = p.Psi_n[ss_mask]
        assert np.all(psi_ss >= 0.0 - 1e-6), f"Psi_n went negative: {psi_ss.min():.4f}"
        assert np.all(psi_ss <= 0.85 + 1e-6), f"Psi_n exceeded 0.85: {psi_ss.max():.4f}"


def test_ss_fixed_fraction():
    """
    Numeric withSSTaxability=0.5 should pin Psi_n to exactly 0.5 for all years
    and produce a different (lower) spending than the SC-loop default.
    """
    p = _make_couple_plan(
        'ss_fixed_half',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
    )
    # SC-loop solve for reference
    p.solve('maxSpending', {'solver': solver, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"SC-loop solver failed: {p.caseStatus}"
    obj_loop = p.g_n[0]

    # Fixed-fraction solve
    p.solve('maxSpending', {'solver': solver, 'withSSTaxability': 0.5, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"Fixed-fraction solver failed: {p.caseStatus}"
    obj_fixed = p.g_n[0]

    # Psi_n must be uniformly 0.5 everywhere
    assert np.allclose(p.Psi_n, 0.5, atol=1e-6), (
        f"Psi_n not pinned to 0.5: min={p.Psi_n.min():.4f}, max={p.Psi_n.max():.4f}"
    )

    # With a fixed mid-range Psi_n, spending should differ from the SC-loop result
    assert obj_fixed != pytest.approx(obj_loop, rel=1e-4), (
        "Expected fixed-fraction spending to differ from SC-loop, but they matched."
    )


def test_ss_fixed_fraction_zero():
    """
    Numeric withSSTaxability=0.0 should pin Psi_n to 0 for all years.
    """
    p = _make_couple_plan(
        'ss_fixed_zero',
        taxable=[90, 60], tax_deferred=[600, 150], tax_free=[70, 40],
        ss_pias=[2_333, 2_083], ss_ages=[67, 70],
    )
    p.solve('maxSpending', {'solver': solver, 'withSSTaxability': 0.0, 'withMedicare': 'None'})
    assert p.caseStatus == 'solved', f"Solver failed: {p.caseStatus}"

    # Psi_n must be uniformly 0.0
    assert np.allclose(p.Psi_n, 0.0, atol=1e-6), (
        f"Psi_n not pinned to 0.0: min={p.Psi_n.min():.4f}, max={p.Psi_n.max():.4f}"
    )
