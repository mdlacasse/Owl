"""
The partial bequest is weighted in the objective (partialBequestWeight, default max(0.01, 2 x gap)).

Without a weight, money the first spouse leaves to non-spouse heirs is worth nothing to the
objective, so wherever the household does not need it the solver is indifferent to how much
remains, and the partial bequest is arbitrary. The weight breaks that tie.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import pathlib
from datetime import date

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import plan as P

_EXAMPLES = pathlib.Path(__file__).resolve().parents[2] / "examples"


def _couple(fractions):
    thisyear = date.today().year
    p = owl.Plan(["Ann", "Bob"], [f"{thisyear - 70}-01-15", f"{thisyear - 68}-01-16"], [78, 88], "pbw",
                 verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[300, 100], taxDeferred=[800, 400], taxFree=[100, 50], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]], [[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setSocialSecurity([2500, 2000], [70, 70])
    p.setBeneficiaryFractions(fractions)
    p.setRates("conservative")
    return p


def _weighted_columns(p):
    """Columns of the first spouse's last-year balances that carry an objective coefficient."""
    nx = p.n_d - 1
    cols = [p.vm["b"].idx(p.i_d, j, nx) for j in range(p.N_j)]
    c_ind, c_val = p.c.lists()
    coef = dict(zip(c_ind, c_val))
    return [j for j, col in enumerate(cols) if coef.get(col, 0) < 0]


def test_weight_on_the_accounts_that_leave_the_household():
    p = _couple([0, 0, 1, 1])
    p.solve("maxSpending", {"bequest": 0})
    assert p.caseStatus == "solved"
    assert _weighted_columns(p) == [0, 1]  # taxable and tax-deferred go to other heirs


@pytest.mark.parametrize("fractions, opts", [([1, 1, 1, 1], {}), ([0, 0, 0, 0], {"partialBequestWeight": 0})])
def test_no_weight_without_a_partial_bequest_or_when_turned_off(fractions, opts):
    p = _couple(fractions)
    p.solve("maxSpending", {"bequest": 0, **opts})
    assert p.caseStatus == "solved"
    assert _weighted_columns(p) == []


def test_default_weight():
    assert P.PARTIAL_BEQUEST_WEIGHT == 0.01


@pytest.mark.parametrize("gap, expected", [(1e-4, 0.01), (3e-3, 0.01), (3e-2, 0.06)])
def test_default_weight_is_at_least_twice_the_gap(gap, expected):
    """A weight below the gap leaves the partial bequest invisible to the solver."""
    def coef(opts):
        p = _couple([0, 0, 1, 1])
        p.solve("maxSpending", {"bequest": 0, "maxIter": 1, **opts})
        c_ind, c_val = p.c.lists()
        return dict(zip(c_ind, c_val))[p.vm["b"].idx(p.i_d, 0, p.n_d - 1)]

    assert coef({"gap": gap}) == pytest.approx(coef({"gap": gap, "partialBequestWeight": expected}))


@pytest.mark.toml
def test_weight_does_not_change_a_case_with_fractions_of_28_percent():
    """jordan+taylor ships with beneficiary fractions of 0.28: the default weight leaves it as it was."""
    res = []
    for w in (0.0, P.PARTIAL_BEQUEST_WEIGHT):
        p = owl.readConfig(str(_EXAMPLES / "Case_jordan+taylor.toml"), verbose=False, logstreams=[io.StringIO()])
        assert np.any(p.phi_j < 1)
        p.solve(p.objective, options={**p.solverOptions, "partialBequestWeight": w})
        assert p.caseStatus == "solved"
        res.append((p.bequest, p.partialBequest))
    assert res[1][0] == pytest.approx(res[0][0], rel=1e-6)
    assert res[1][1] == pytest.approx(res[0][1], rel=1e-4)
