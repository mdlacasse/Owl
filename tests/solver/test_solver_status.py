"""
A solve that fails must say whether the plan is impossible or the solver gave up.

Issue #139: HiGHS abandons one case with model status 'Unknown' although the plan is
feasible -- MOSEK solves it, and the failing HiGHS run even prints an objective within
rounding of MOSEK's answer. Reporting that as "unsuccessful", the same word used for a
genuinely infeasible plan, tells the user to fix a plan that was never broken.

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

import os
from pathlib import Path

import pytest

import owlplanner as owl

CASE = str(Path(__file__).resolve().parents[1] / "data" / "case_highs_unknown")
JACK = os.path.join("examples", "Case_jack+jill")


def _solve(name, solver, **opts):
    """Solve with the solver named, not the one OWL_TEST_SOLVER picked: these tests are
    about what each back-end reports, so both must run whichever way the suite is run."""
    p = owl.readConfig(name, verbose=False)
    p.solve(p.objective, dict(p.solverOptions, solver=solver, **opts))
    return p


def test_issue_139_is_a_solver_error_not_an_infeasible_plan():
    """
    The regression from issue #139, and a tripwire for a future highspy.

    Should an upgraded HiGHS simply solve this, the fixture has done its job and the
    test says so out loud rather than passing quietly on a case that no longer bites.
    """
    p = _solve(CASE, "HiGHS")

    assert p.caseStatus != "infeasible", "a feasible plan was reported as infeasible"

    if p.caseStatus == "solved":
        pytest.skip(
            "HiGHS now solves the issue #139 model (highspy was upgraded). This fixture no "
            "longer exercises the solver-error path -- find a new one or drop this test."
        )

    assert p.caseStatus == "solver error"
    # The message is what the user reads, so it has to make the distinction in words.
    assert "not an infeasible plan" in p.solverMessage


def test_issue_139_case_solves_under_mosek():
    """
    The other half of the claim: the model is fine, so a working solver finds the plan.

    Whether MOSEK is usable is decided by trying it, not by looking for the package or
    for MOSEKLM_LICENSE_FILE. Neither answers the question: CI installs MOSEK without a
    license, and a licensed machine may hold that license at the default path with the
    variable unset. A license failure is itself reported as a solver error, so the
    status alone cannot distinguish "no license" from the bug under test.
    """
    pytest.importorskip("mosek")
    p = _solve(CASE, "MOSEK")
    if p.caseStatus != "solved" and "License" in p.solverMessage:
        pytest.skip("MOSEK is installed but not licensed here")
    assert p.caseStatus == "solved"


def test_infeasible_plan_is_reported_as_infeasible():
    """A bequest far beyond the assets is the user's problem, and must still say so."""
    p = _solve(JACK, "default", bequest=5e8)
    assert p.caseStatus == "infeasible"
    assert "No plan satisfies" in p.solverMessage


def test_solved_plan_carries_no_failure_message():
    p = _solve(JACK, "default")
    assert p.caseStatus == "solved"
    assert p.solverMessage == ""


def test_failure_message_is_cleared_on_the_next_solve():
    """A stale verdict from a previous run would misdescribe the current one."""
    p = owl.readConfig(JACK, verbose=False)
    good = dict(p.solverOptions)  # solve() keeps the options it is given
    p.solve("maxSpending", dict(good, bequest=5e8))
    assert p.caseStatus == "infeasible"

    p.solve(p.objective, good)
    assert p.caseStatus == "solved"
    assert p.solverMessage == ""
