"""
Binaries are snapped to exactly 0 or 1 after every mixed-integer solve (Plan._snapBinaries).

A solver accepts a binary within its integrality tolerance of 0 or 1; times a big-M in the millions,
that lets dollars into a bracket whose binary counts as off. In Case_jordan+taylor, IRMAA's top tier
held $17-$287 of MAGI at z = 1e-6 (MOSEK, local search), so years a few dollars past a tier edge paid
the tier below: $63,522 of IRMAA residual. The snap re-solves the LP with the rounded binaries pinned.

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

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def _solved(case, **options):
    p = owl.readConfig(os.path.join(EXAMPLES, f"Case_{case}.toml"), verbose=False, logstreams=[io.StringIO()])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p.solve(p.objective, {**p.solverOptions, **options})
    assert p.caseStatus == "solved"
    return p


@pytest.fixture(scope="module")
def plan_with_binaries():
    """A case solved with its tax families exact, so its last problem carries binaries."""
    return _solved("dana", breakpointMethod="local-search")


def test_a_fractional_binary_is_pinned_at_its_rounded_value(plan_with_binaries, monkeypatch):
    p = plan_with_binaries
    bins = np.nonzero(p.B.integralityArray())[0]
    assert len(bins), "test setup: the problem has binaries"
    x = np.array(p._highs_warm_start, dtype=float)
    x[bins] = np.round(x[bins])
    x[bins[0]] += 1e-6 if x[bins[0]] == 0 else -1e-6  # within a solver's integrality tolerance

    seen = {}

    def fake_run_mip(A, B, c, options, lp_relax=False, col_overrides=None, update_warm=True):
        seen.update(lp_relax=lp_relax, overrides=dict(col_overrides))
        return -1.0, np.zeros_like(x), True, "pinned LP", -1.0

    monkeypatch.setattr(p, "_run_mip", fake_run_mip)
    obj, y, ok, msg, gap = p._snapBinaries((-2.0, x, True, "MIP", 1e-4), {})
    assert seen["lp_relax"] is True
    pins = seen["overrides"]
    assert all(pins[int(j)] == (float(np.round(x[j])),) * 2 for j in bins)
    # The pinned LP's answer replaces the MIP's; the MIP's message and gap are kept.
    assert (obj, ok, msg, gap) == (-1.0, True, "MIP", 1e-4)
    assert np.all(y == 0)


def test_exact_binaries_are_not_solved_again(plan_with_binaries, monkeypatch):
    p = plan_with_binaries
    x = np.array(p._highs_warm_start, dtype=float)
    bins = np.nonzero(p.B.integralityArray())[0]
    x[bins] = np.round(x[bins])
    monkeypatch.setattr(p, "_run_mip", lambda *a, **k: pytest.fail("re-solved exact binaries"))
    result = (-2.0, x, True, "MIP", 1e-4)
    assert p._snapBinaries(result, {}) is result


@pytest.mark.toml
def test_no_irmaa_tier_is_paid_below_the_magi(plan_with_binaries):
    """Case_jordan+taylor under local search: with the binaries snapped, every year pays the IRMAA tier
    its own MAGI implies, and no top-tier bracket holds MAGI while its binary is off."""
    p = _solved("jordan+taylor", breakpointMethod="local-search")
    assert p.fixedPointResidual["IRMAA"]["abs_sum"] < 1.0
    for nn in range(p.h_qn.shape[0]):
        if np.argmax(p.h_qn[nn]) != p.N_irmaa - 1:
            assert p.h_qn[nn, -1] < 1e-6
