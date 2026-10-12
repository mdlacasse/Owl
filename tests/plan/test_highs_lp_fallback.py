"""
An LP that HiGHS's default path ends without a verdict is solved again before it is
called a solver failure.

HiGHS's dual simplex can break down numerically on an LP with no feasible point and report
"Solve error" or "Unknown" instead of infeasible. Owl then said the solver failed, when the
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
    """A HiGHS whose first run reports the given status, as the dual simplex sometimes does."""

    first_status = highspy.HighsModelStatus.kSolveError

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._broken = True

    def clearSolver(self):
        self._broken = False
        return super().clearSolver()

    def getModelStatus(self):
        return self.first_status if self._broken else super().getModelStatus()


def _solve(monkeypatch, row_lb, row_ub, status):
    """One continuous variable x in [0, 10] and one row, row_lb <= x <= row_ub."""
    monkeypatch.setattr(highspy, "Highs", type("H", (_BreaksOnce,), {"first_status": status}))
    plan = owl.Plan(["Joe"], ["1961-01-15"], [80], "fallback")
    return plan, plan._run_highs(
        np.array([1.0]), np.array([0.0]), np.array([10.0]), np.array([row_lb]), np.array([row_ub]),
        np.array([0]), np.array([0]), np.array([1.0]), np.array([0]), {},
    )


@pytest.mark.parametrize("status", [highspy.HighsModelStatus.kSolveError, highspy.HighsModelStatus.kUnknown])
def test_infeasible_lp_is_reported_infeasible(monkeypatch, status):
    plan, (obj, _, success, msg, _) = _solve(monkeypatch, 20.0, 30.0, status)
    assert not success
    assert plan._infeasible
    assert msg == "Infeasible"


@pytest.mark.parametrize("status", [highspy.HighsModelStatus.kSolveError, highspy.HighsModelStatus.kUnknown])
def test_feasible_lp_is_solved(monkeypatch, status):
    plan, (obj, xx, success, msg, _) = _solve(monkeypatch, 2.0, 30.0, status)
    assert success
    assert not plan._infeasible
    assert xx[0] == pytest.approx(2.0)
