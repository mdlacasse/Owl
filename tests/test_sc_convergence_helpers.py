"""
Unit tests for self-consistent convergence helpers in Plan.
"""

from datetime import date

import numpy as np
import owlplanner as owl
from owlplanner import plan as planmod


def _make_plan():
    thisyear = date.today().year
    return owl.Plan(["Pat"], [f"{thisyear - 65}-01-01"], [85], "sc_helpers")


def test_sc_policy_defaults_and_numeric_reltol():
    p = _make_plan()
    opts = {"gap": 9e-4, "relTol": 1e-4, "maxIter": 12}
    policy = p._build_sc_loop_policy(opts)

    assert policy["includeMedicare"] is True
    assert policy["withSCLoop"] is True
    assert policy["fixedPsi"] is None
    assert policy["relTol"] == 1e-4
    assert policy["maxIter"] == 12

    default_policy = p._build_sc_loop_policy({"gap": 9e-4})
    assert default_policy["relTol"] == max(planmod.REL_TOL, 9e-4 / 300)


def test_pick_best_valid_index_respects_medicare_gate():
    p = _make_plan()
    vals = [100.0, 99.0, 105.0, 103.0]
    assert p._pick_best_valid_index(vals, includeMedicare=False) == 2
    assert p._pick_best_valid_index(vals, includeMedicare=True) == 2
    assert p._pick_best_valid_index([100.0], includeMedicare=True) is None


def test_obj_convergence_detects_monotonic_and_oscillatory():
    p = _make_plan()

    monotonic = p._check_obj_convergence(
        it=1,
        abs_obj_diff=2.0,
        tol=5.0,
        includeMedicare=True,
        scaled_obj_history=[120.0, 119.0],
    )
    assert monotonic["reason"] == "converged"
    assert monotonic["convergenceType"] == "monotonic"

    oscillatory = p._check_obj_convergence(
        it=2,
        abs_obj_diff=0.5,
        tol=1.0,
        includeMedicare=False,
        scaled_obj_history=[120.0, 119.0, 120.5],
    )
    assert oscillatory["reason"] == "converged"
    assert oscillatory["convergenceType"] == "oscillatory"

    blocked = p._check_obj_convergence(
        it=0,
        abs_obj_diff=0.0,
        tol=1.0,
        includeMedicare=True,
        scaled_obj_history=[120.0],
    )
    assert blocked is None


def test_cycle_and_stagnation_checks(monkeypatch):
    p = _make_plan()
    monkeypatch.setattr(planmod.u, "detect_oscillation", lambda history, tol: 3)

    cycle = p._check_cycle(it=4, scaled_obj_history=[100.0, 95.0, 96.0, 95.0], tol=1.0)
    assert cycle["reason"] == "cycle"
    assert cycle["cycleLength"] == 3
    assert cycle["cycleOffset"] == 1

    values = [10.0, 9.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0]
    gaps = [0.1, np.inf, np.inf, np.inf, 0.1, 0.1, 0.1, 0.1, 0.1]
    stagnation = p._check_stagnation(it=8, scaled_obj_history=values, gap_history=gaps, includeMedicare=False)
    assert stagnation["reason"] == "stagnation"


def test_max_iteration_check():
    p = _make_plan()
    assert p._check_max_iterations(5, 6) is None
    decision = p._check_max_iterations(6, 6)
    assert decision["reason"] == "max_iter"
