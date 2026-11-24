"""
Every solved plan reports how far it sits from the model its own income implies.

The self-consistent loop exits on the objective, not on the quantities it feeds back, so a plan can
be declared converged while its own income would still move them. `plan.fixedPointResidual` makes
that distance visible instead of leaving it implicit behind the word "solved".

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

FAMILIES = ("SS", "IRMAA", "NIIT", "deduction", "LTCG")


def _plan(name="residual"):
    thisyear = date.today().year
    p = owl.Plan(["Alex"], [f"{thisyear - 66}-01-15"], [84], name, verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[300], taxDeferred=[1200], taxFree=[100])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setSocialSecurity([2000], [67])
    return p


def test_residual_is_reported_and_small_on_a_converged_plan():
    p = _plan()
    p.solve("maxSpending", options={"bequest": 0})
    assert p.caseStatus == "solved"
    assert set(p.fixedPointResidual) >= {"SS", "NIIT", "deduction", "LTCG"}
    for fam, v in p.fixedPointResidual.items():
        assert set(v) == {"sum", "abs_sum", "max_abs"}
        # A converged plan should be nearly self-consistent; this is the claim "solved" implies.
        assert v["abs_sum"] < 1_000.0, f"{fam} residual {v['abs_sum']:,.2f}"


def test_residual_exposes_a_pinned_taxability_that_the_plan_contradicts():
    """Pinning Psi to a value the plan's own provisional income does not support must show up."""
    p = _plan("residual-pinned")
    p.solve("maxSpending", options={"bequest": 0, "withSSTaxability": 0.0})
    assert p.caseStatus == "solved"
    ss = float(np.sum(p.zetaBar_in))
    assert ss > 0
    assert p.fixedPointResidual["SS"]["abs_sum"] > 1_000.0


def test_residual_is_empty_before_a_solve():
    assert _plan("residual-fresh").fixedPointResidual == {}


@pytest.mark.toml
def test_residual_present_on_a_shipped_case():
    p = owl.readConfig("examples/Case_dana.toml", verbose=False)
    p.resolve()
    assert p.caseStatus == "solved"
    assert p.fixedPointResidual
    assert all(np.isfinite(v["abs_sum"]) for v in p.fixedPointResidual.values())
