"""
Scenario runs hold Social Security claiming ages where the plan has them.

A claiming age is chosen once, by a solve of the plan under the life expectancies entered.
Choosing it again inside each scenario would choose it knowing that scenario's returns and
lifespans. Every scenario driver therefore drops withSSAges; a solve that still searched the
ages would raise here.

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

import numpy as np
import pytest

from owlplanner.config import readConfig
from owlplanner.plan import Plan
from owlplanner.stresstests import run_historical_range, run_spending_bequest_frontier, run_stochastic_spending

OPTS = {"solver": "HiGHS", "withSSAges": "optimize"}


@pytest.fixture
def dana(monkeypatch):
    def no_search(self, *args, **kwargs):
        raise AssertionError("claiming ages searched inside a scenario run")

    monkeypatch.setattr(Plan, "_ssAgeSearch", no_search)
    return readConfig("examples/Case_dana.toml", verbose=False)


def test_historical_range(dana):
    opts = dict(OPTS)
    run_historical_range(dana, "maxSpending", opts, 1966, 1967)
    assert dana.caseStatus == "solved"
    assert opts["withSSAges"] == "optimize", "must not mutate the caller's options"


def test_stochastic_spending(dana):
    """Scenario workers record a raised solve as an infeasible scenario (basis 0)."""
    res = run_stochastic_spending(dana, dict(OPTS), "historical", ystart=1966, yend=1967)
    assert np.all(np.asarray(res["bases"]) > 0)


def test_spending_bequest_frontier(dana):
    res = run_spending_bequest_frontier(dana, dict(OPTS), [0], scenario_method="deterministic")
    assert not np.any(res["level_failed"])
