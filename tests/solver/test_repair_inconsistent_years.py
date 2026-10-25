"""
After a branch-and-bound solve, the years whose charged costs the plan's own income contradicts are
solved again with every other binary pinned (localsearch.repair_inconsistent_years).

Branch-and-bound stops at a relative gap (3e-3 when Medicare is solved as MILP). In Case_robin its
incumbent (MOSEK) taxed 85% of Social Security in 2042 and 2045, years whose provisional income is
below the base amount: $1.6k of federal tax a year not owed, $47,323 of SS residual. The repair finds
the plan the tighter gap finds, in one small solve.

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
from owlplanner import localsearch

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def _solved(case, **options):
    p = owl.readConfig(os.path.join(EXAMPLES, f"Case_{case}.toml"), verbose=False, logstreams=[io.StringIO()])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p.solve(p.objective, {**p.solverOptions, "breakpointMethod": "branch-and-bound", **options})
    assert p.caseStatus == "solved"
    return p


@pytest.fixture(scope="module")
def robin():
    return _solved("robin")


@pytest.mark.toml
def test_no_year_is_charged_a_social_security_share_its_income_does_not_imply(robin):
    assert robin.fixedPointResidual["SS"]["abs_sum"] < 1.0


def test_a_consistent_plan_is_returned_untouched(robin, monkeypatch):
    x = np.array(robin._highs_warm_start, dtype=float)
    result = (-1.0, x, True, "MIP", 1e-3)
    monkeypatch.setattr(localsearch.LocalSearch, "_inconsistent_columns", lambda self, x: (set(), {}))
    monkeypatch.setattr(localsearch.LocalSearch, "_mip", lambda *a, **k: pytest.fail("solved a consistent plan"))
    assert localsearch.repair_inconsistent_years(robin, result, {}, use_mosek=False) is result


def test_a_repair_that_is_no_better_is_not_kept(robin, monkeypatch):
    x = np.array(robin._highs_warm_start, dtype=float)
    result = (-1.0, x, True, "MIP", 1e-3)
    monkeypatch.setattr(localsearch.LocalSearch, "_inconsistent_columns", lambda self, x: ({0}, {"SS": [2042]}))
    monkeypatch.setattr(localsearch.LocalSearch, "_mip", lambda *a, **k: ((-0.5, x * 0, True, "worse", -1.0), 0.0))
    assert localsearch.repair_inconsistent_years(robin, result, {}, use_mosek=False) is result


def test_a_better_repair_keeps_the_solve_message_and_gap(robin, monkeypatch):
    x = np.array(robin._highs_warm_start, dtype=float)
    y = x + 1.0
    result = (-1.0, x, True, "MIP", 1e-3)
    calls = iter([({0}, {"SS": [2042]}), (set(), {})])
    monkeypatch.setattr(localsearch.LocalSearch, "_inconsistent_columns", lambda self, x: next(calls))
    monkeypatch.setattr(localsearch.LocalSearch, "_mip", lambda *a, **k: ((-2.0, y, True, "repair", -1.0), 0.0))
    obj, z, ok, msg, gap = localsearch.repair_inconsistent_years(robin, result, {}, use_mosek=False)
    assert (obj, ok, msg, gap) == (-2.0, True, "MIP", 1e-3)
    assert np.array_equal(z, y)
