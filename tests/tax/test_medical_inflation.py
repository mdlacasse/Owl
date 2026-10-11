"""
Tests for medical prices growing faster than inflation (Plan.setMedicalInflation).

Covers:
- mediVals/mediCosts: premiums follow medical_n, IRMAA thresholds follow gamma_n
- acaVals/acaCosts: the benchmark premium follows medical_n, the poverty line follows gamma_n
- Plan._medical_n compounding, and the default leaving results unchanged
- A solved plan pays more for health care, and the setting round-trips through the case file

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

from datetime import date

import numpy as np
import pytest

import owlplanner.tax_federal as tx
from owlplanner import Plan
from owlplanner.config import config_to_plan, plan_to_config

THISYEAR = date.today().year
N = 20
GAMMA = 1.025 ** np.arange(N + 1)
MEDICAL = GAMMA * 1.02 ** np.arange(N + 1)


def test_medivals_default_matches_gamma():
    yobs = np.array([THISYEAR - 70])
    horizons = np.array([N])
    nm, L0, C0 = tx.mediVals(yobs, horizons, GAMMA, N, 6)
    nm, L1, C1 = tx.mediVals(yobs, horizons, GAMMA, N, 6, medical_n=GAMMA)
    assert np.allclose(C0, C1) and np.allclose(L0, L1)


def test_medivals_premiums_follow_medical_thresholds_follow_gamma():
    yobs = np.array([THISYEAR - 70])
    horizons = np.array([N])
    _, L0, C0 = tx.mediVals(yobs, horizons, GAMMA, N, 6)
    _, L1, C1 = tx.mediVals(yobs, horizons, GAMMA, N, 6, medical_n=MEDICAL)
    assert np.allclose(L0, L1), "IRMAA thresholds must keep following inflation."
    ratio = C1[:, 0] / C0[:, 0]
    assert np.allclose(ratio, 1.02 ** np.arange(N))


def test_medicosts_premiums_follow_medical():
    yobs = np.array([THISYEAR - 70])
    horizons = np.array([N])
    magi = np.full(N, 50_000.0)
    prev = np.full(2, 50_000.0)
    base = tx.mediCosts(yobs, horizons, magi, prev, GAMMA, N)
    fast = tx.mediCosts(yobs, horizons, magi, prev, GAMMA, N, medical_n=MEDICAL)
    assert np.allclose(fast / base, 1.02 ** np.arange(N))


def test_medicosts_irmaa_threshold_stays_with_inflation():
    """An income just above a threshold that follows inflation stays above it."""
    yobs = np.array([THISYEAR - 70])
    horizons = np.array([N])
    magi = GAMMA[:N] * tx.irmaaBrackets[0][1] * 1.01
    prev = np.full(2, magi[0])
    base = tx.mediCosts(yobs, horizons, magi, prev, GAMMA, N)
    fast = tx.mediCosts(yobs, horizons, magi, prev, GAMMA, N, medical_n=MEDICAL)
    # Two-year lookback: compare years whose MAGI and threshold are both indexed.
    assert np.allclose(fast[2:] / base[2:], 1.02 ** np.arange(2, N))


def test_aca_premium_follows_medical_fpl_follows_gamma():
    yobs = np.array([THISYEAR - 40])
    horizons = np.array([N])
    slcsp = 12_000.0
    # Far above 400% FPL: the full benchmark premium is paid every year.
    magi = np.full(N, 1_000_000.0)
    base = tx.acaCosts(yobs, horizons, magi, GAMMA, slcsp, N)
    fast = tx.acaCosts(yobs, horizons, magi, GAMMA, slcsp, N, medical_n=MEDICAL)
    assert np.allclose(fast / base, 1.02 ** np.arange(N))
    n_aca, L0, _, s0 = tx.acaVals(yobs, horizons, GAMMA, slcsp, N)
    _, L1, _, s1 = tx.acaVals(yobs, horizons, GAMMA, slcsp, N, medical_n=MEDICAL)
    assert n_aca == N
    assert np.allclose(s1 / s0, 1.02 ** np.arange(N))
    # The poverty-line brackets below the cap are unchanged.
    assert np.allclose(L0[:, :4], L1[:, :4])


def _plan():
    p = Plan(["Alex"], [f"{THISYEAR - 60}-01-15"], [85], "medical", verbose=False)
    p.setAccountBalances(taxable=[500], taxDeferred=[800], taxFree=[200])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setAllocationRatios("individual", generic=[[[60, 20, 20, 0], [40, 30, 30, 0]]])
    p.setSpendingProfile("flat")
    return p


def test_medical_n_compounds_on_gamma():
    p = _plan()
    p.setMedicalInflation(1.5)
    gamma = 1.03 ** np.arange(10)
    assert np.allclose(p._medical_n(gamma), (1.03 * 1.015) ** np.arange(10))
    p.setMedicalInflation(0)
    assert np.allclose(p._medical_n(gamma), gamma)


def test_set_medical_inflation_rejects_nonsense():
    with pytest.raises(ValueError):
        _plan().setMedicalInflation(-0.5)
    with pytest.raises(ValueError):
        _plan().setMedicalInflation(10.5)
    _plan().setMedicalInflation(10)


def test_solved_plan_pays_more_for_health_care():
    costs = []
    for excess in (0, 3):
        p = _plan()
        p.setACA(12)
        p.setMedicalExpenses(5)
        p.setMedicalInflation(excess)
        p.solve("maxSpending", options={"maxRothConversion": 0})
        assert p.caseStatus == "solved"
        costs.append((p.medicare_n.sum(), p.aca_costs_n.sum(), p.other_medical_n.sum(), p.basis))
    (m0, a0, o0, spend0), (m1, a1, o1, spend1) = costs
    assert m1 > m0 and a1 > a0 and o1 > o0
    assert spend1 < spend0, "Dearer health care leaves less to spend."


def test_config_roundtrip():
    p = _plan()
    p.setMedicalInflation(1.5)
    out = plan_to_config(p)
    assert out["optimization_parameters"]["medical_inflation_excess"] == 1.5
    p2 = config_to_plan(out, verbose=False)
    assert p2.medical_excess == pytest.approx(0.015)


def test_config_default_omitted():
    out = plan_to_config(_plan())
    assert "medical_inflation_excess" not in out["optimization_parameters"]


def test_setters_flag_case_modified():
    for setter, arg in (("setMedicalInflation", 1.5), ("setMedicalExpenses", 5.0)):
        p = _plan()
        p.caseStatus = "solved"
        getattr(p, setter)(arg)
        assert p.caseStatus == "modified", f"{setter} must flag the case as modified."


def test_schema_bounds_excess_to_ui_range():
    from pydantic import ValidationError

    from owlplanner.config.schema import OptimizationParameters

    assert OptimizationParameters(medical_inflation_excess=0).medical_inflation_excess == 0
    with pytest.raises(ValidationError):
        OptimizationParameters(medical_inflation_excess=-0.5)
    with pytest.raises(ValidationError):
        OptimizationParameters(medical_inflation_excess=10.5)
