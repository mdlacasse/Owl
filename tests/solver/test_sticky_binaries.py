"""
Inside a branch-and-bound loop, the previous iteration's binaries are kept when they tie the new plan
(Plan._stickyBinaries), and convergence is judged on the fed-back parameters.

Branch-and-bound returns any plan within its gap of the optimum (3e-3 when Medicare is solved as
MILP). When the loop changed the problem by a few dollars, it returned a different plan along a
direction where the objective is nearly flat, so the loop never settled although its parameters had:
Case_jack+jill and Case_avery+quinn ran to the iteration limit, 30 iterations, with $10k-$17k of
residual. Keeping tied binaries removes that noise at no loss: a tie, not anything inside the gap.

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
    log = io.StringIO()
    p = owl.readConfig(os.path.join(EXAMPLES, f"Case_{case}.toml"), verbose=True, logstreams=[log])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p.solve(p.objective, {**p.solverOptions, "breakpointMethod": "branch-and-bound", **options})
    assert p.caseStatus == "solved"
    return p, log.getvalue()


@pytest.fixture(scope="module")
def plan():
    """A case solved by branch-and-bound, so its last problem carries binaries."""
    return _solved("dana")[0]


def _with_prev(p, flip):
    """A plan vector with every binary at 0 as the new solve, the same one as the previous iterate,
    one binary flipped when flip is True. Only the problem's binary columns matter here."""
    x = np.zeros(p.nvars)
    bins = np.nonzero(p.B.integralityArray())[0]
    assert len(bins), "test setup: the problem has binaries"
    prev = x.copy()
    if flip:
        prev[bins[0]] = 1.0 - prev[bins[0]]
    p._bb_strategy = True
    p._stickyPrev = prev
    p._sticky_tol = 5e-5
    return x, prev, bins


def test_a_tie_keeps_the_previous_binaries(plan, monkeypatch):
    x, prev, bins = _with_prev(plan, flip=True)
    seen = {}

    def lp(A, B, c, options, lp_relax=False, col_overrides=None, update_warm=True):
        seen.update(lp=lp_relax, pins=dict(col_overrides))
        return -1.0 + 1e-6, prev, True, "pinned LP", -1.0  # within 5e-5 of the new plan's -1.0

    monkeypatch.setattr(plan, "_run_mip", lp)
    obj, z, ok, msg, gap = plan._stickyBinaries((-1.0, x, True, "MIP", 2e-3), {"gap": 3e-3}, use_mosek=False)
    assert seen["lp"] is True
    assert all(seen["pins"][int(j)] == (prev[j],) * 2 for j in bins)
    assert np.array_equal(z, prev) and ok and msg == "MIP"
    assert gap == pytest.approx(2e-3 + 1e-6, rel=1e-3)  # the same bound, against the kept plan
    assert np.array_equal(plan._stickyPrev, prev)


def test_a_tie_does_not_leave_the_requested_gap(plan, monkeypatch):
    """#233: the solve met its 1e-5 gap (9.9e-6) and the tie, 2e-5 worse, is within the loop's
    5e-5, but against the same bound the kept plan would be about 3e-5 from it: refused."""
    x, prev, _ = _with_prev(plan, flip=True)
    monkeypatch.setattr(plan, "_run_mip", lambda *a, **k: (-1.0 + 2e-5, prev, True, "pinned LP", -1.0))
    result = (-1.0, x, True, "MIP", 9.9e-6)
    assert plan._stickyBinaries(result, {"gap": 1e-5}, use_mosek=False) is result
    assert np.array_equal(plan._stickyPrev, x)


def test_a_tie_is_kept_when_the_solve_stopped_above_the_gap(plan, monkeypatch):
    """A solve stopped by a limit above the requested gap proved nothing within it: the tie is kept
    as before, so the loop keeps its convergence aid where it matters most."""
    x, prev, _ = _with_prev(plan, flip=True)
    monkeypatch.setattr(plan, "_run_mip", lambda *a, **k: (-1.0 + 2e-5, prev, True, "pinned LP", -1.0))
    obj, z, ok, msg, gap = plan._stickyBinaries((-1.0, x, True, "MIP", 5e-3), {"gap": 3e-3}, use_mosek=False)
    assert np.array_equal(z, prev) and gap == pytest.approx(5e-3 + 2e-5, rel=1e-3)


def test_a_worse_plan_does_not_keep_them(plan, monkeypatch):
    x, prev, _ = _with_prev(plan, flip=True)
    monkeypatch.setattr(plan, "_run_mip", lambda *a, **k: (-1.0 + 1e-3, prev, True, "pinned LP", -1.0))
    result = (-1.0, x, True, "MIP", 2e-3)
    assert plan._stickyBinaries(result, {}, use_mosek=False) is result
    assert np.array_equal(plan._stickyPrev, x)


def test_the_same_binaries_are_not_solved_again(plan, monkeypatch):
    x, _, _ = _with_prev(plan, flip=False)
    monkeypatch.setattr(plan, "_run_mip", lambda *a, **k: pytest.fail("re-solved identical binaries"))
    result = (-1.0, x, True, "MIP", 2e-3)
    assert plan._stickyBinaries(result, {}, use_mosek=False) is result


def test_nothing_under_local_search(plan, monkeypatch):
    x, _, _ = _with_prev(plan, flip=True)
    plan._bb_strategy = False
    monkeypatch.setattr(plan, "_run_mip", lambda *a, **k: pytest.fail("sticky under local search"))
    result = (-1.0, x, True, "MIP", 2e-3)
    assert plan._stickyBinaries(result, {}, use_mosek=False) is result


@pytest.mark.toml
@pytest.mark.deep
@pytest.mark.parametrize("case", ["joe", "jack+jill", "avery+quinn"])
def test_pathological_cases_settle(case):
    """Under MOSEK all three ran to the 30-iteration limit; now joe and jack+jill settle in 4 and
    avery+quinn in 7, at the same value (about 6 s, 15 s and 49 s). The noise is MOSEK's: HiGHS
    already settled them in 3-5 iterations, and its branch-and-bound takes 22-114 s on them, so
    the test runs under MOSEK only."""
    if os.getenv("OWL_TEST_SOLVER", "").lower() != "mosek":
        pytest.skip("MOSEK's incumbent noise; HiGHS settled these cases before the change")
    p, log = _solved(case)
    assert "max iteration" not in p.convergenceType
    assert log.count("Iter: ") <= 10
