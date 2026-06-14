"""
Tests for the two MAGI flavors and the Social Security treatment in each.

Owl distinguishes:
  - MAGI_n      : AGI-basis MAGI (taxable SS only) used by IRMAA, NIIT, and the
                  OBBBA 65+ senior-deduction phaseout.
  - MAGI_aca_n  : full-SS MAGI (adds back non-taxable SS) used by the ACA premium
                  credit (IRC §36B) and Social Security provisional income.

These guard the fix that IRMAA/NIIT no longer overstate MAGI by including the
non-taxable portion of Social Security (SSA POMS HI 01101.010 defines IRMAA MAGI
as AGI + tax-exempt interest, i.e. taxable SS only).
"""

from datetime import date

import numpy as np

import owlplanner as owl


def _couple_with_ss(name, sstax="loop", medicare="loop"):
    thisyear = date.today().year
    # Both already at/near Medicare age so IRMAA is active and SS is being collected.
    p = owl.Plan(["Pat", "Sam"], [f"{thisyear - 67}-01-15", f"{thisyear - 66}-01-16"],
                 [88, 90], name, verbose=False)
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[150, 100], taxDeferred=[700, 300], taxFree=[60, 40], startDate="1-1")
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setInterpolationMethod("s-curve")
    p.setAllocationRatios("individual",
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]],
                                   [[50, 50, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0, 0], [65, 65])
    p.setSocialSecurity([3500, 3000], [67, 67])   # sizeable SS so the non-taxable slice matters
    opts = {"withMedicare": medicare}
    if sstax != "loop":
        opts["withSSTaxability"] = sstax
    p.solve("maxSpending", options=opts)
    return p


def test_magi_two_flavors_identity():
    """MAGI_aca_n - MAGI_n equals the non-taxable SS portion (1-Psi)*zetaBar exactly."""
    p = _couple_with_ss("magi_identity")
    assert p.caseStatus == "solved"
    nontaxable = np.sum((1 - p.Psi_n) * p.zetaBar_in, axis=0)
    np.testing.assert_allclose(p.MAGI_aca_n - p.MAGI_n, nontaxable, atol=1.0)


def test_irmaa_magi_is_agi_basis():
    """The IRMAA/NIIT MAGI excludes the non-taxable SS that the ACA MAGI includes."""
    p = _couple_with_ss("magi_agi_basis")
    assert p.caseStatus == "solved"
    # There must be at least one year with non-taxable SS for this to be a real test.
    nontaxable = np.sum((1 - p.Psi_n) * p.zetaBar_in, axis=0)
    assert np.any(nontaxable > 1.0), "test setup should leave some SS non-taxable"
    # ACA MAGI must be strictly larger wherever non-taxable SS exists; never smaller.
    assert np.all(p.MAGI_aca_n >= p.MAGI_n - 1.0)
    yrs = nontaxable > 1.0
    assert np.all(p.MAGI_aca_n[yrs] > p.MAGI_n[yrs] + 1.0)


def test_loop_vs_optimize_medicare_agree():
    """Loop and optimize Medicare modes agree now that both use the AGI-basis MAGI."""
    p_loop = _couple_with_ss("magi_med_loop", medicare="loop")
    p_opt = _couple_with_ss("magi_med_opt", medicare="optimize")
    assert p_loop.caseStatus == "solved" and p_opt.caseStatus == "solved"
    rel = abs(p_loop.basis - p_opt.basis) / max(p_loop.basis, 1.0)
    assert rel <= 5e-3, f"loop basis {p_loop.basis:.0f} vs optimize {p_opt.basis:.0f} (rel {rel:.4f})"


def test_ss_taxability_uses_full_ss_magi():
    """Provisional income (PI = MAGI_aca - 0.5 SS) must reference the full-SS MAGI.

    If SS taxability accidentally used the AGI MAGI, Psi would be understated.
    Cross-check that loop-mode Psi matches the IRS formula evaluated on MAGI_aca_n.
    """
    import owlplanner.tax_federal as tx
    p = _couple_with_ss("magi_ss_pi")
    assert p.caseStatus == "solved"
    ss_n = np.sum(p.zetaBar_in, axis=0)
    expected_psi = tx.compute_social_security_taxability(p.N_i, p.MAGI_aca_n, ss_n, n_d=p.n_d)
    # Loop Psi is damped across SC iterations; at convergence it should track the formula
    # on MAGI_aca_n far better than on the AGI MAGI_n.
    err_aca = np.max(np.abs(p.Psi_n - expected_psi)[ss_n > 0])
    psi_on_agi = tx.compute_social_security_taxability(p.N_i, p.MAGI_n, ss_n, n_d=p.n_d)
    err_agi = np.max(np.abs(p.Psi_n - psi_on_agi)[ss_n > 0])
    assert err_aca <= err_agi + 1e-9, "Psi should track the full-SS (ACA) MAGI, not the AGI MAGI"
