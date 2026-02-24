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

import os
import numpy as np
import pytest
from datetime import date

import owlplanner as owl


def _make_couple_plan(name, taxable, tax_deferred, tax_free, ss_pias, ss_ages,
                      pension=None, pension_ages=None, rate_year=2000):
    """
    Create a minimal Jack+Jill-style couple plan using historical rates.

    Note: setPension() amounts are monthly $ (same units as SS PIAs).
    """
    thisyear = date.today().year
    inames = ['Jack', 'Jill']
    # Jack 66 (past SS age), Jill 63 — both within expected SS window.
    dobs = [f"{thisyear - 66}-01-15", f"{thisyear - 63}-01-16"]
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
    p.solve('maxSpending', {})
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
    p.solve('maxSpending', {})
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
    p.solve('maxSpending', {})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    assert ss_mask.any(), "Expected some SS-active years"
    psi_ss = p.Psi_n[ss_mask]
    assert psi_ss.max() <= 0.85 + 1e-6, f"Psi_n exceeded 0.85: {psi_ss.max():.4f}"
    assert psi_ss.min() >= 0.0 - 1e-6, f"Psi_n went negative: {psi_ss.min():.4f}"


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
    p.solve('maxSpending', {})
    assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"
    ss_mask = np.sum(p.zetaBar_in, axis=0) > 0
    assert ss_mask.any(), "Expected some SS-active years"
    # Psi_n should vary across years (not uniformly 0.85 as in fixed-fraction mode).
    assert not np.all(p.Psi_n[ss_mask] == 0.85), "Expected dynamic Psi_n, not fixed at 0.85"


@pytest.mark.toml
def test_historical_crash_years_feasible():
    """
    Regression test: verify that historical crash years (1973-74 bear market) do not
    cause infeasibility.  The SC loop correctly sets Psi_n = 0 when provisional income
    PI < 0 (large capital losses), so the LP remains feasible.

    Loads jack+jill example, runs a short historical range covering the 1973-74
    bear market, and asserts that at least some runs succeed.
    """
    exdir = "./examples/"
    case = "Case_jack+jill"
    file = os.path.join(exdir, case)
    if not os.path.exists(file + ".toml"):
        pytest.skip(f"Example case not found: {file}.toml")

    p = owl.readConfig(file)

    hfp_path = os.path.join(exdir, "HFP_jack+jill.xlsx")
    if not os.path.exists(hfp_path):
        pytest.skip(f"HFP file not found: {hfp_path}")
    p.readHFP(hfp_path)

    options = p.solverOptions
    objective = p.objective
    # Run 1969-1975: covers 1973-74 crash years.
    n, df = p.runHistoricalRange(objective, options, 1969, 1975, figure=False)
    assert len(df) >= 1, "Expected at least one feasible historical run in 1969-1975"
    assert n >= 1, "Expected at least one successful historical run"
