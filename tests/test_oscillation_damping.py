"""
Regression tests for oscillation handling in the self-consistent loop.

These tests focus on the control flow when oscillation is detected, and
verify that damping changes the exit behavior.
"""

import numpy as np

import owlplanner as owl
import owlplanner.plan as plan


def _make_minimal_plan():
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "oscillation_test")
    p.setSpendingProfile("flat", 100)
    p.gamma_n = np.ones(p.N_n + 1)
    p.nvars = 4
    p.nbals = 2
    return p


def _wire_sc_mocks(monkeypatch):
    iter_state = {"n": 0}

    def fake_compute(self, x, includeMedicare):
        if x is None:
            self.MAGI_n = np.zeros(self.N_n)
            self.J_n = np.zeros(self.N_n)
            self.M_n = np.zeros(self.N_n)
            self.psi_n = np.zeros(self.N_n)
            self.Q_n = np.ones(self.N_n)
            return
        iter_state["n"] += 1
        self.MAGI_n = np.ones(self.N_n) * iter_state["n"]
        self.J_n = np.ones(self.N_n) * iter_state["n"]
        self.M_n = np.ones(self.N_n) * iter_state["n"]
        self.psi_n = np.ones(self.N_n) * 0.1
        self.Q_n = np.ones(self.N_n)

    def fake_detect(self, history, tol, max_cycle_length=15):
        return 2 if len(history) >= 4 else None

    monkeypatch.setattr(plan.Plan, "_computeNLstuff", fake_compute)
    monkeypatch.setattr(plan.Plan, "_detectOscillation", fake_detect)
    monkeypatch.setattr(plan.Plan, "_aggregateResults", lambda self, x, short=False: None)
    return iter_state


def _make_solver(plan_instance):
    calls = {"n": 0}

    def solver_method(objective, options):
        calls["n"] += 1
        objfn = float(calls["n"])
        xx = np.zeros(plan_instance.nvars)
        return objfn, xx, True, "ok", 0.0

    return solver_method, calls


def test_oscillation_breaks_without_damping(monkeypatch):
    p = _make_minimal_plan()
    _wire_sc_mocks(monkeypatch)
    solver_method, calls = _make_solver(p)

    options = {
        "absTol": 0.0,
        "relTol": 0.0,
        "gap": 0.0,
        "maxIter": 10,
        "scDamping": 0.0,
        "scDampingOnOsc": 0.0,
    }

    p._scSolve("maxSpending", options, solver_method)

    assert p.convergenceType == "oscillatory (cycle length 2)"
    assert calls["n"] == 4


def test_oscillation_continues_with_damping(monkeypatch):
    p = _make_minimal_plan()
    _wire_sc_mocks(monkeypatch)
    solver_method, calls = _make_solver(p)

    options = {
        "absTol": 0.0,
        "relTol": 0.0,
        "gap": 0.0,
        "maxIter": 4,
        "scDamping": 0.0,
        "scDampingOnOsc": 0.5,
    }

    p._scSolve("maxSpending", options, solver_method)

    assert p.convergenceType == "max iteration"
    assert calls["n"] == 5
