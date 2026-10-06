"""
Quantities the MILP rows build from the plan itself rather than from the previous iteration.

- The LTCG bracket partition holds exactly the year's gains when there is no capital loss. It
  once allowed a dollar of room, which the solver took whenever it cost nothing (gains in the 0%
  bracket); the MAGI built from the partition then read a dollar high, and the fixed-point
  residual reported ACA and IRMAA inconsistencies the plan did not have.
- The NIIT row prices the plan's own investment income, not the previous iteration's.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from datetime import date

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import tax_federal as tx


@pytest.fixture(scope="module")
def plan():
    """A couple with large taxable and tax-deferred accounts, short horizon, NIIT and LTCG exact."""
    thisyear = date.today().year
    p = owl.Plan(["Jack", "Jill"], [f"{thisyear - 66}-01-15", f"{thisyear - 63}-01-16"], [72, 72], "lagged")
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[1500, 1000], taxDeferred=[3000, 2000], taxFree=[50, 50], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]], [[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setPension([0, 0], [65, 65])
    p.setSocialSecurity([2000, 1500], [67, 67])
    p.setRates("historical", 2000)
    p.solve("maxSpending", {"withNIIT": "optimize", "withLTCG": "optimize", "maxIter": 5})
    assert p.caseStatus == "solved"
    return p


def _rows(p, name):
    return {tag[1]: k for k, tag in enumerate(p.A.tags) if isinstance(tag, tuple) and tag[0] == name}


def test_partition_has_no_room_without_a_loss(plan):
    lo, hi = _rows(plan, "ltcg_partition_lo"), _rows(plan, "ltcg_partition_hi")
    assert lo and hi
    for n in lo:
        if plan.fixed_assets_capital_gains_n[n] < 0 or plan.Q_n[n] < 0:
            continue
        assert plan.A.ub[hi[n]] == pytest.approx(plan.A.lb[lo[n]], abs=1e-9), n


def test_reported_magi_equals_its_parts(plan):
    np.testing.assert_allclose(plan.MAGI_n, plan.G_n + plan.e_n + plan.Q_n, atol=0.02)


def test_niit_row_prices_the_plans_own_investment_income(plan):
    nii_rows = _rows(plan, "niit_nii")
    b_cols = {plan.vm["b"].idx(i, 0, n): n for i in range(plan.N_i) for n in range(plan.N_n)}
    a_ind, _, _, _ = plan.A.lists()
    fak_n = np.sum(np.maximum(0, plan.tau_kn[1:, : plan.N_n]) * plan.alpha_ijkn[:, 0, 1:, : plan.N_n], axis=(0, 1))
    checked = 0
    for n, k in nii_rows.items():
        if fak_n[n] <= 0:
            continue  # no taxed bond/cash return that year (negative returns): no term to carry
        checked += 1
        assert any(b_cols.get(c) == n for c in a_ind[k]), f"year {n}: NIIT row carries no taxable balance"
    assert checked
    J_ref = tx.computeNIIT(plan.N_i, plan.MAGI_n, plan.I_n, plan.Q_n, plan.n_d, plan.N_n)
    assert np.any(J_ref > 0), "the case should pay NIIT"
    np.testing.assert_allclose(plan.J_n, J_ref, atol=0.05)


def test_niit_never_exceeds_its_cap(plan):
    """NIIT is at most 3.8% of net investment income, whichever branch applies (row niit_nii_cap)."""
    assert _rows(plan, "niit_nii_cap")
    nii = plan.I_n + plan.Q_n
    assert np.all(plan.J_n <= 0.038 * nii + 0.05), np.max(plan.J_n - 0.038 * nii)
