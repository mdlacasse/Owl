"""
An LP that HiGHS's default path ends without a verdict is solved again before it is
called a solver failure.

HiGHS's dual simplex can break down numerically on an LP with no feasible point and report
"Solve error", "Unknown" or no status at all instead of infeasible. Owl then said the solver failed, when the
plan simply cannot be paid for. These tests make the first run end that way and check that
the fallback reaches the true verdict.

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

import highspy
import numpy as np
import pytest

import owlplanner as owl


class _BreaksOnce(highspy.Highs):
    """A HiGHS whose first run reports the given status, as the dual simplex sometimes does, with
    or without a feasible point."""

    first_status = highspy.HighsModelStatus.kSolveError
    first_has_point = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._broken = True
        self.runs = 0

    def run(self):
        self.runs += 1
        self.settings = (self.getOptionValue("solver")[1], self.getOptionValue("presolve")[1])
        return super().run()

    def clearSolver(self):
        self._broken = False
        return super().clearSolver()

    def getModelStatus(self):
        return self.first_status if self._broken else super().getModelStatus()

    def getInfoValue(self, name):
        if self._broken and name == "primal_solution_status" and not self.first_has_point:
            return highspy.HighsStatus.kOk, highspy.kSolutionStatusNone
        return super().getInfoValue(name)


def _solve(monkeypatch, row_lb, row_ub, status, has_point=False):
    """One continuous variable x in [0, 10] and one row, row_lb <= x <= row_ub."""
    made = []

    class H(_BreaksOnce):
        first_status = status
        first_has_point = has_point

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            made.append(self)

    monkeypatch.setattr(highspy, "Highs", H)
    plan = owl.Plan(["Joe"], ["1961-01-15"], [80], "fallback")
    result = plan._run_highs(
        np.array([1.0]), np.array([0.0]), np.array([10.0]), np.array([row_lb]), np.array([row_ub]),
        np.array([0]), np.array([0]), np.array([1.0]), np.array([0]), {},
    )
    _solve.last = made[0]
    return plan, result, made[0].runs


NO_VERDICT = [
    highspy.HighsModelStatus.kNotset,
    highspy.HighsModelStatus.kSolveError,
    highspy.HighsModelStatus.kUnknown,
    highspy.HighsModelStatus.kPresolveError,
    highspy.HighsModelStatus.kPostsolveError,
    highspy.HighsModelStatus.kUnboundedOrInfeasible,
]


@pytest.mark.parametrize("status", NO_VERDICT)
def test_infeasible_lp_is_reported_infeasible(monkeypatch, status):
    plan, (obj, _, success, msg, _), runs = _solve(monkeypatch, 20.0, 30.0, status)
    assert not success
    assert plan._infeasible
    assert msg == "Infeasible"
    assert runs == 2


@pytest.mark.parametrize("status", NO_VERDICT)
def test_feasible_lp_is_solved(monkeypatch, status):
    plan, (obj, xx, success, msg, _), runs = _solve(monkeypatch, 2.0, 30.0, status)
    assert success
    assert not plan._infeasible
    assert xx[0] == pytest.approx(2.0)
    assert runs == 2


def test_lp_with_a_feasible_point_is_not_solved_again(monkeypatch):
    """A feasible point already counts as success; solving again could only change an answer."""
    plan, (obj, xx, success, msg, _), runs = _solve(
        monkeypatch, 2.0, 30.0, highspy.HighsModelStatus.kUnknown, has_point=True
    )
    assert success
    assert xx[0] == pytest.approx(2.0)
    assert runs == 1


@pytest.mark.parametrize(
    "status", [highspy.HighsModelStatus.kTimeLimit, highspy.HighsModelStatus.kIterationLimit]
)
def test_lp_stopped_by_a_limit_is_not_solved_again(monkeypatch, status):
    """Solving again after a limit would only spend the budget twice more."""
    plan, (obj, _, success, msg, _), runs = _solve(monkeypatch, 20.0, 30.0, status)
    assert not success
    assert not plan._infeasible
    assert runs == 1


def test_fallback_is_the_interior_point_method_without_presolve(monkeypatch):
    _solve(monkeypatch, 20.0, 30.0, highspy.HighsModelStatus.kSolveError)
    assert _solve.last.settings == ("ipm", "off")
