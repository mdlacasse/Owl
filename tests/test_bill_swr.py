"""
Analytical validation of Case_bill: pure Roth, no taxes, no SS, no Medicare.

Starting from $1M in a Roth account invested 50% SP500 / 50% T-Notes using
historical rates 1966-1995 (30 years), the LP optimal spending must match the
inflation-adjusted annuity formula derived from the start-of-period balance recursion:

    B_{n+1} = (B_n - g * gamma_n) * (1 + r_n)

Solving B_N = 0 for g gives:

    g = B_0 / sum_{m=0}^{N-1} gamma_m / cum_r_m

where cum_r_m = prod_{k=0}^{m-1} (1 + r_k)  (product of returns *before* year m).

Note on timing convention
--------------------------
Owl uses start-of-period withdrawals: spending is deducted from the balance
*before* the annual return is applied.  The standard end-of-period annuity
formula (B_{n+1} = B_n*(1+r_n) - g*gamma_n) gives a higher result because the
full balance earns a return before anything is withdrawn.

Owl (start-of-period, 50% SP500 + 50% T-Notes, 1966-1995):  ~3.67%
End-of-period formula (same data):                            ~3.99%

Note on Bengen's 4% rule
--------------------------
Bengen (1994) quoted ~4.15% as the worst-case 30-year SWR from his dataset.
Two differences explain why his number is higher:

  1. Timing convention: Bengen used end-of-period withdrawals (+0.32%).
  2. Bond series: Bengen used 5-year intermediate Treasury bonds, which have
     shorter duration than Owl's 10-year T-Notes.  During the rising-rate
     period of 1966-1981, shorter-duration bonds outperformed: their average
     return was ~5.3% vs. ~3.8% for 10-year notes, adding ~0.16% to the SWR.

  3.67% (Owl) + 0.32% (timing) + 0.16% (bond duration) ≈ 4.15% (Bengen)

Note on full-options case
--------------------------
Running Case_bill with its default solver options (withACA='loop', withLTCG='loop',
amoSurplus=True, etc.) gives a lower SWR (~3.42%) because ACA health-insurance
costs are computed for the pre-Medicare year and other SC-loop interactions add
constraints.  The test below uses stripped-down options to isolate the pure
annuity math.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np
import pytest

import owlplanner as owl

# Expected SWR for Case_bill.toml solved with its own solver options.
# All loops are disabled in the TOML (pure Roth, no SS, no taxable income —
# none of the SC-loop features have any effect), so this matches the
# analytical formula result.  Update if Case_bill.toml changes intentionally.
BILL_FULL_OPTIONS_BASIS = 36665.93


def _annuity_spending(B0, r_n, gamma_n):
    """
    Compute the maximum constant real spending (today's dollars) that exactly
    exhausts B0 over N years under sequence-of-returns r_n and inflation
    multipliers gamma_n.

    Balance recursion (withdrawal at start of year):
        B_{n+1} = (B_n - g * gamma_n) * (1 + r_n)

    Setting B_N = 0 yields:
        g = B0 / sum_{m=0}^{N-1} gamma_m / cum_r_m
    where cum_r_m = prod_{k=0}^{m-1} (1 + r_k)  (excludes year-m return).
    """
    N = len(r_n)
    cum_r = 1.0
    total_pv = 0.0
    for m in range(N):
        total_pv += gamma_n[m] / cum_r
        cum_r *= 1.0 + r_n[m]
    return B0 / total_pv


def test_bill_matches_annuity_formula():
    """LP result for Case_bill must match the start-of-period annuity formula to within 0.01%.

    Real-world features (ACA, LTCG loop, SC loop) are disabled so the LP reduces
    to a pure annuity problem and the analytical formula applies exactly.
    Expected SWR: ~3.67% (see module docstring for why this differs from Bengen's 4.15%).
    """
    p = owl.readConfig("examples/Case_bill", verbose=False, loadHFP=False)

    # Disable all real-world features so the LP is a pure annuity problem.
    options = {
        'withSCLoop': False,
        'withACA': 'none',
        'withMedicare': 'none',
        'withLTCG': 'none',
        'withSSTaxability': 'none',
        'withNIIT': 'none',
    }
    p.solve("maxSpending", options=options)

    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"

    N = p.N_n
    # Portfolio return per year: 50% SP500 (k=0) + 50% T-Notes (k=2).
    # Use the allocation actually stored in the plan for robustness.
    r_n = np.einsum("kn,kn->n", p.alpha_ijkn[0, 2, :, :N], p.tau_kn[:, :N])
    gamma_n = p.gamma_n[:N]

    g_formula = _annuity_spending(1_000_000.0, r_n, gamma_n)

    assert p.basis == pytest.approx(g_formula, rel=1e-4), (
        f"LP basis {p.basis:,.0f} != start-of-period annuity formula {g_formula:,.0f}"
    )


@pytest.mark.toml
def test_bill_full_options_regression():
    """Regression test: Case_bill.toml solved with its own options must reproduce a known SWR.

    Case_bill is a pure Roth case with no SS, no taxable income, and Medicare-eligible
    from the start — all SC-loop features are disabled in the TOML because they have
    no effect.  The expected basis therefore matches the analytical formula (~$36,666).
    If this test breaks, check whether Case_bill.toml or the LP structure changed.
    """
    p = owl.readConfig("examples/Case_bill", verbose=False, loadHFP=False)
    p.solve("maxSpending", options=p.solverOptions)

    assert p.caseStatus == "solved", f"Solve failed: {p.caseStatus}"
    assert p.basis == pytest.approx(BILL_FULL_OPTIONS_BASIS, rel=1e-3), (
        f"Full-options basis {p.basis:,.2f} != expected {BILL_FULL_OPTIONS_BASIS:,.2f}. "
        "Update BILL_FULL_OPTIONS_BASIS if the change is intentional."
    )
