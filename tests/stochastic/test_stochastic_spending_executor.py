"""
A process pool must give the same stochastic-spending result as the thread pool.

Every random draw (rates, lifespans) happens in the parent before any worker starts,
so the executor only decides where the deterministic solves run. The clones travel to
a worker process by pickling, which the plan's logger has to survive.

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

import io
import os
import pickle
import sys

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import mylogging
from owlplanner.config.plan_bridge import clone
from owlplanner.stresstests import run_stochastic_spending

OPTIONS = {"withMedicare": "loop", "bequest": 1, "units": "k", "solver": "HiGHS"}


def _seeded_plan():
    plan = owl.readConfig(os.path.join("examples", "Case_jack+jill"), verbose=False)
    plan.mylog.setVerbose(False)
    plan.setReproducible(True, seed=2026)
    plan.setRates("histogaussian", frm=1928, to=2025)
    return plan


@pytest.mark.toml
def test_process_pool_reproduces_the_thread_pool():
    threads = _seeded_plan().runStochasticSpending(OPTIONS, "mc", N=4, executor="threads")
    processes = _seeded_plan().runStochasticSpending(OPTIONS, "mc", N=4, executor="processes")
    np.testing.assert_array_equal(threads["bases"], processes["bases"])
    np.testing.assert_array_equal(threads["bases_year1"], processes["bases_year1"])
    np.testing.assert_array_equal(threads["partial_bequests"], processes["partial_bequests"])
    assert threads["year1_decisions"] == processes["year1_decisions"]
    assert processes["n_infeasible"] == 0


@pytest.mark.toml
def test_unknown_executor_is_rejected():
    with pytest.raises(ValueError, match="executor"):
        run_stochastic_spending(_seeded_plan(), OPTIONS, "mc", N=2, executor="fibers")


def test_a_cloned_plan_pickles_and_its_logger_writes_to_the_standard_streams():
    plan = owl.Plan(["Joe"], ["1965-01-15"], [80], "pickle", logstreams=[io.StringIO()])
    copy = pickle.loads(pickle.dumps(clone(plan, verbose=False)))
    assert isinstance(copy.mylog, mylogging.Logger)
    assert copy.mylog._logstreams == [sys.stdout, sys.stderr]
    assert copy.N_n == plan.N_n
