"""
Timing benchmarks for the LP build and solve path.

Not part of the regular test run: pytest.ini limits collection to tests/, so
these only run when the directory is named explicitly::

    uv run pytest benchmarks --benchmark-only

CONTRIBUTING.md ("Benchmarks") covers saving a baseline and comparing against it.

Every benchmark works on a clone of a shipped example, so timings do not depend
on anything outside the repository, and every round starts from a fresh clone
because a solved plan carries state (warm starts, loop quantities) into the
next solve on the same object.

Results are local for now. Saved runs stay on the machine that produced them
(.benchmarks/ is gitignored) because absolute timings only compare within one
machine, and CI does not run this suite. How to make benchmarks part of CI is
left for the project to decide: comparing the base branch and the PR in the
same CI job, an instruction-counting service such as CodSpeed, or a dedicated
benchmark machine that keeps history.

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

import pytest

import owlplanner as owl
from owlplanner.config.plan_bridge import clone
from owlplanner.stresstests import run_stochastic_spending

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")

# Every self-consistent quantity handled by the loop rather than in the MILP, which is
# how the stress tests solve each scenario, so this is the path a Monte Carlo run pays for.
LOOP_OPTIONS = {
    "withMedicare": "loop",
    "withACA": "loop",
    "withLTCG": "loop",
    "withNIIT": "loop",
    "withSSTaxability": "loop",
    "bequest": 1,
    "units": "k",
    "startRothConversions": 2028,
    "solver": "HiGHS",
}

MC_SCENARIOS = 32


def _load(case):
    plan = owl.readConfig(os.path.join(EXAMPLES, case), verbose=False)
    plan.mylog.setVerbose(False)
    return plan


def _loop_options(plan):
    return {**plan.solverOptions, **LOOP_OPTIONS}


@pytest.fixture(scope="module")
def couple():
    """Two individuals, HSA, pension, fixed asset, debt, state tax; deterministic 1969 rates."""
    return _load("Case_jack+jill")


@pytest.fixture(scope="module")
def single():
    """One individual on historical-average rates."""
    return _load("Case_joe")


def _solve_loop(plan):
    plan.solve("maxSpending", _loop_options(plan))
    assert plan.caseStatus == "solved"


def test_lp_build(benchmark, couple):
    """A full build, as on the first iteration of the self-consistent loop."""
    plan = clone(couple, verbose=False)
    _solve_loop(plan)

    def build():
        plan._fixedRows = {}
        plan._buildConstraints("maxSpending", plan.solverOptions)

    benchmark(build)


def test_lp_rebuild(benchmark, couple):
    """A later iteration's build, which replays the loop-invariant blocks."""
    plan = clone(couple, verbose=False)
    _solve_loop(plan)
    benchmark(plan._buildConstraints, "maxSpending", plan.solverOptions)


def test_solve_loop_couple(benchmark, couple):
    benchmark.pedantic(_solve_loop, setup=lambda: ((clone(couple, verbose=False),), {}), rounds=10, warmup_rounds=1)


def test_solve_loop_single(benchmark, single):
    benchmark.pedantic(_solve_loop, setup=lambda: ((clone(single, verbose=False),), {}), rounds=10, warmup_rounds=1)


def test_stochastic_spending_mc(benchmark, couple):
    def setup():
        plan = clone(couple, verbose=False)
        plan.setReproducible(True, seed=2026)
        plan.setRates("histogaussian", frm=1928, to=2025)
        return (plan,), {}

    def run(plan):
        result = run_stochastic_spending(plan, _loop_options(plan), "mc", N=MC_SCENARIOS)
        assert result["n_infeasible"] == 0

    benchmark.pedantic(run, setup=setup, rounds=3, warmup_rounds=1)
