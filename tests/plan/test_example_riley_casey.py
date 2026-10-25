"""
Case_riley+casey: bridging to Medicare on the ACA in Georgia, a state without the Medicaid expansion.

The example gathers several rules no other example reaches: the Social Security earnings test's grace
year (Riley claims in July after six months of work), Roth 401(k) contributions paid from pay (#221),
an HSA contribution from savings deducted through a negative other inc (#225), and ACA pricing in a
non-expansion state (#202). The loop-mode checks run with the suite; the deep one compares the loop
with the exact ACA pricing of local search, which takes minutes, and runs with `pytest -m deep`.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import os
import warnings

import numpy as np
import pytest

import owlplanner as owl

CASE = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "Case_riley+casey.toml")
RILEY, CASEY = 0, 1


def _load():
    return owl.readConfig(CASE, verbose=False, logstreams=[io.StringIO()])


def _solve(p, **options):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p.solve(p.objective, {**p.solverOptions, **options})
    assert p.caseStatus == "solved"
    return p


@pytest.fixture(scope="module")
def loop_plan():
    return _solve(_load())


@pytest.mark.toml
def test_the_grace_year_pays_the_months_after_work(loop_plan):
    """Riley works January to June 2026 and claims in July, before full retirement age, with wages well
    above the exempt amount. 2026 is the initial grace year, and every month of entitlement in it comes
    after work stops, so nothing is withheld and no month is credited at FRA."""
    p = loop_plan
    assert p.etMonths_in[RILEY, 0] == 6
    assert np.all(p.ss_withheld_in == 0)
    assert list(p.ss_arf_months_i) == [0, 0]
    # Riley is paid from July: half a year of benefits in 2026, a full year after.
    assert 0 < p.zeta_in[RILEY, 0] < p.zeta_in[RILEY, 1]


@pytest.mark.toml
def test_without_months_worked_the_whole_entitlement_is_withheld():
    """Without "months worked", the year counts as twelve months of work: no month after July is a
    non-service month, so the annual test withholds the 2026 benefits, credited at FRA."""
    p = _load()
    p.etMonths_in[RILEY, 0] = 0
    _solve(p)
    assert p.ss_withheld_in[RILEY, 0] > 0
    assert p.ss_arf_months_i[RILEY] == 6


@pytest.mark.toml
def test_the_hsa_contribution_is_entered_as_a_deduction(loop_plan):
    """Casey contributes from savings: HSA ctrb deposits it, and the same amount as a negative other inc
    deducts it and pays for it (#225). Riley's Roth 401(k) contribution is paid for by a negative
    big-ticket item, the wages staying as they enter AGI (#221)."""
    p = loop_plan
    # The deduction matches what is contributed, the year Medicare starts included: Owl keeps only the
    # months before it (2036: 8 of 12 for a September birthday), and the workbook enters that share.
    hsa = p.kappa_ijn[CASEY, 3, : p.N_n]
    assert hsa[0] > 0 and 0 < p.hsaFrac_in[CASEY, 10] < 1
    np.testing.assert_allclose(p.other_inc_in[CASEY, : p.N_n], -hsa, atol=1.0)
    assert p.kappa_ijn[RILEY, 2, 0] == pytest.approx(-p.Lambda_in[RILEY, 0])


@pytest.mark.toml
@pytest.mark.deep
def test_exact_aca_pricing_manages_the_400_percent_cliff(loop_plan):
    """Loop mode converts across the 400% FPL cliff and pays the full benchmark in 2026-2028; local
    search prices the cliff exactly, keeps MAGI under it in several years, pays less in premiums and
    spends more. Recorded 2026-10-24 (MOSEK): loop $116,758/yr and $148k of premiums, local search
    $119,117/yr (+2.0%) and $90k (HiGHS: $119,151/yr, in 273 s against MOSEK's 120 s)."""
    loop = loop_plan
    ls = _solve(_load(), breakpointMethod="local-search")
    assert "->" not in ls.breakpointMethodUsed, ls.breakpointMethodUsed
    g = loop.gamma_n[: loop.N_n]
    assert ls.basis > 1.01 * loop.basis
    assert np.sum(ls.aca_costs_n / g) < 0.8 * np.sum(loop.aca_costs_n / g)
