"""
Analytical validation of Case_bill: pure Roth, no taxes, no SS, no Medicare.

Starting from $1M in a Roth account invested 50% SP500 / 50% T-Notes using
historical rates 1966-1994 (29 years), the LP optimal spending must match the
inflation-adjusted annuity computed by direct balance simulation:

    B_{n+1} = (B_n - g * gamma_n) * (1 + r_n)

Solving B_N = 0 for g gives:

    g = B_0 / sum_{m=0}^{N-1} gamma_m / cum_r_m

where cum_r_m = prod_{k=0}^{m-1} (1 + r_k).

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np
import pytest

import owlplanner as owl


def _annuity_spending(B0, r_n, gamma_n):
    """
    Compute the maximum constant real spending (today's dollars) that exactly
    exhausts B0 over N years under sequence-of-returns r_n and inflation
    multipliers gamma_n.

    Balance recursion (withdrawal at start of year):
        B_{n+1} = (B_n - g * gamma_n) * (1 + r_n)

    Setting B_N = 0 yields g = B0 / sum_{m} gamma_m / cum_r_m.
    """
    N = len(r_n)
    cum_r = 1.0
    total_pv = 0.0
    for m in range(N):
        total_pv += gamma_n[m] / cum_r
        cum_r *= 1.0 + r_n[m]
    return B0 / total_pv


def test_bill_matches_annuity_formula():
    """LP result for Case_bill must match the direct annuity loop to within 0.01%."""
    p = owl.readConfig("examples/Case_bill", verbose=False, loadHFP=False)
    options = p.solverOptions
    p.solve("maxSpending", options=options)

    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"

    N = p.N_n
    # Portfolio return per year: 50% SP500 (k=0) + 50% T-Notes (k=2)
    # Use the allocation actually stored in the plan for robustness.
    r_n = np.einsum("kn,kn->n", p.alpha_ijkn[0, 2, :, :N], p.tau_kn[:, :N])
    gamma_n = p.gamma_n[:N]

    g_formula = _annuity_spending(1_000_000.0, r_n, gamma_n)

    assert p.basis == pytest.approx(g_formula, rel=1e-4), (
        f"LP basis {p.basis:,.0f} != annuity formula {g_formula:,.0f}"
    )
