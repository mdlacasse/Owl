"""
Loop-invariant constraint blocks are built once per solve and replayed afterwards.

The replay must reproduce exactly what a fresh build would produce: the same rows in
the same order with the same bounds, keys and objective. A builder that starts reading a
quantity the self-consistent loop updates (M_n, Psi_n, G_n, ...) while still carrying the
@_fixedAcrossIterations decorator would fail the comparison below on any case where that
quantity moves between iterations.

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

import numpy as np
import pytest

import owlplanner as owl
import owlplanner.abcapi as abc


def _lp_arrays(plan):
    a_start, a_index, a_value = plan.A.to_csr()
    Lb, Ub = plan.B.arrays()
    return {
        "a_start": a_start,
        "a_index": a_index,
        "a_value": a_value,
        "row_lb": np.array(plan.A.lb),
        "row_ub": np.array(plan.A.ub),
        "col_lb": Lb,
        "col_ub": Ub,
        "integrality": plan.B.integralityArray(),
        "c": plan.c.arrays(),
    }


def _assert_same_lp(fresh, replayed):
    for name in fresh:
        assert fresh[name].shape == replayed[name].shape, name
        np.testing.assert_array_equal(fresh[name], replayed[name], err_msg=name)


@pytest.mark.toml
@pytest.mark.parametrize(
    "case, overrides",
    [
        ("Case_jack+jill", {}),  # Medicare optimize, HSA, fixed asset, debt
        ("Case_jack+jill", {"withMedicare": "loop"}),
        ("Case_joe", {}),
        ("Case_kim+sam-spending", {}),  # state income tax
        ("Case_john+sally", {}),  # maxBequest
    ],
)
def test_replayed_rows_match_a_fresh_build(case, overrides):
    plan = owl.readConfig(os.path.join("examples", case), verbose=False)
    plan.mylog.setVerbose(False)
    options = {**plan.solverOptions, **overrides, "solver": "HiGHS"}
    plan.solve(plan.objective, options)
    assert plan.caseStatus == "solved"
    # The loop ran several iterations, so the loop quantities differ from their starting values
    # and the last build was a replay of the first build's fixed blocks.
    assert plan._fixedRows
    options = plan.solverOptions

    plan._buildConstraints(plan.objective, options)
    replayed = _lp_arrays(plan)
    replayed_tags = list(plan.A.tags)
    plan._fixedRows = {}
    plan._buildConstraints(plan.objective, options)
    fresh_tags = list(plan.A.tags)
    _assert_same_lp(_lp_arrays(plan), replayed)
    assert fresh_tags == replayed_tags


def test_constraint_matrix_rows_since_and_extend():
    cm = abc.ConstraintMatrix(6)
    cm.addNewRow({0: 1.0}, 0, 1, tag="first")
    n = cm.ncons
    cm.addNewRow({1: 2.0, 2: 3.0}, -np.inf, 5, tag="second")
    cm.addNewRow({3: 4.0}, 7, 7, tag="third")
    rows = cm.rowsSince(n)

    other = abc.ConstraintMatrix(6)
    other.addNewRow({5: 9.0}, 0, np.inf)
    other.extendRows(rows)
    assert other.ncons == 3
    assert other.Aind[1:] == [[1, 2], [3]]
    assert other.Aval[1:] == [[2.0, 3.0], [4.0]]
    assert other.lb[1:] == [-np.inf, 7]
    assert other.ub[1:] == [5, 7]
    assert other.keys()[1:] == ["up", "fx"]
    assert other.tags[1:] == ["second", "third"]


def test_bounds_ranges_since_and_extend():
    b = abc.Bounds(5, 1)
    b.setRange(0, 0, 10)
    n = len(b.ind)
    b.setRange(1, 2, 2)
    b.setRange(2, -np.inf, 3)
    ranges = b.rangesSince(n)

    other = abc.Bounds(5, 1)
    other.extendRanges(ranges)
    lb, ub = other.arrays()
    assert lb[1] == 2 and ub[1] == 2
    assert lb[2] == -np.inf and ub[2] == 3
    assert other.keys()[1:3] == ["fx", "up"]
    assert other.keys()[0] == "lo"  # untouched column keeps the default
