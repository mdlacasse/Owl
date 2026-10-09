"""
Tests for the money scaling of MIP solves (mipScaleOrder, _MoneyScaling, #178).

A MIP is handed to the solver with every amount in units of 10**mipScaleOrder dollars (hundreds by
default): continuous columns and the rows holding them are divided by the scale, binaries and rows
of binaries only are left as they are. The scaled model must be the same model, and the solution
must come back in dollars.

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

import owlplanner as owl
from owlplanner.plan import _MoneyScaling


def _random_mip(seed=0, nrows=40, ncols=30, nint=6):
    rng = np.random.default_rng(seed)
    integrality = np.zeros(ncols, dtype=np.int32)
    integrality[-nint:] = 1
    a_start, a_index, a_value = [], [], []
    for r in range(nrows):
        a_start.append(len(a_index))
        cols = rng.choice(ncols - nint, size=3, replace=False) if r % 5 else rng.choice(
            np.arange(ncols - nint, ncols), size=2, replace=False)  # every fifth row: binaries only
        if r % 7 == 1:
            cols = np.append(cols, ncols - 1)  # a big-M row: money and a binary
        a_index.extend(cols.tolist())
        a_value.extend((rng.normal(size=len(cols)) * 10 ** rng.integers(0, 9, size=len(cols))).tolist())
    x = rng.uniform(0, 1e6, ncols)
    x[-nint:] = rng.integers(0, 2, nint)
    c = rng.normal(size=ncols)
    return integrality, np.array(a_start), np.array(a_index), np.array(a_value), x, c


def _matvec(a_start, a_index, a_value, x):
    starts = np.append(a_start, len(a_index))
    return np.array([a_value[starts[r]:starts[r + 1]] @ x[a_index[starts[r]:starts[r + 1]]]
                     for r in range(len(a_start))])


def test_scaled_model_is_the_same_model():
    integrality, a_start, a_index, a_value, x, c = _random_mip()
    sc = _MoneyScaling(1000.0, integrality, a_start, a_index)
    xs = sc.col_values(x)
    # Each row's activity, in its scaled units.
    np.testing.assert_allclose(
        _matvec(a_start, a_index, sc.coefficients(a_index, a_value), xs),
        sc.row_values(_matvec(a_start, a_index, a_value, x)), rtol=1e-12, atol=1e-9)
    # The objective, back in dollars.
    assert sc.objective_value(sc.objective(np.arange(len(c)), c) @ xs) == pytest.approx(c @ x, rel=1e-12)
    np.testing.assert_allclose(sc.solution(xs), x, rtol=1e-12)
    # Binaries are not scaled, nor are rows that hold binaries only.
    assert np.all(sc.col_s[integrality > 0] == 1.0) and np.all(sc.col_s[integrality == 0] == 1000.0)
    starts = np.append(a_start, len(a_index))
    for r in range(len(a_start)):
        only_int = np.all(integrality[a_index[starts[r]:starts[r + 1]]] > 0)
        assert sc.row_t[r] == (1.0 if only_int else 1e-3)


def test_an_lp_or_a_scale_of_one_is_the_identity():
    integrality, a_start, a_index, a_value, x, c = _random_mip()
    assert _MoneyScaling.for_mip(np.zeros_like(integrality), a_start, a_index).identity
    assert _MoneyScaling.for_mip(integrality, a_start, a_index, {"mipScaleOrder": 0}).identity
    sc = _MoneyScaling.for_mip(integrality, a_start, a_index)
    assert not sc.identity and sc.scale == 100.0  # default order 2
    ident = _MoneyScaling()
    assert ident.coefficients(a_index, a_value) is a_value and ident.col_values(x) is x
    assert ident.solution(x) is x and ident.objective(np.arange(len(c)), c) is c and ident.objective_value(3.5) == 3.5


@pytest.mark.parametrize("order,scale", [(0, 1.0), (3, 1e3), (3.0, 1e3), (6, 1e6)])
def test_scale_order_is_a_power_of_ten(order, scale):
    integrality, a_start, a_index, *_ = _random_mip()
    assert _MoneyScaling.for_mip(integrality, a_start, a_index, {"mipScaleOrder": order}).scale == scale


@pytest.mark.parametrize("order", [-1, 7, 2.5])
def test_scale_order_out_of_range_is_refused(order):
    integrality, a_start, a_index, *_ = _random_mip()
    with pytest.raises(ValueError, match="mipScaleOrder"):
        _MoneyScaling.for_mip(integrality, a_start, a_index, {"mipScaleOrder": order})


def _gated_plan():
    p = owl.Plan(["Sam"], ["1976-04-10"], [70], "scaling", verbose=False)
    p.setAccountBalances(taxable=[3600], taxDeferred=[580], taxFree=[720])
    p.setCostBasis([1380])
    p.setSocialSecurity([3700], [70])
    p.setAllocationRatios(
        "account",
        taxable=[[[94, 0, 6, 0], [94, 0, 6, 0]]],
        taxDeferred=[[[0, 0, 100, 0], [0, 0, 100, 0]]],
        taxFree=[[[0, 0, 100, 0], [0, 0, 100, 0]]],
    )
    p.setSpendingProfile("flat")
    p.setRates("historical", frm=1969)
    return p


def test_highs_answer_does_not_depend_on_the_units():
    opts = {"netSpending": 105, "withdrawalOrder": "taxable_first", "solver": "HiGHS"}
    results = {}
    for order in (0, 3):
        p = _gated_plan()
        p.solve("maxBequest", dict(opts, mipScaleOrder=order))
        assert p.caseStatus == "solved"
        results[order] = (p.bequest, p.b_ijn.copy())
    assert results[3][0] == pytest.approx(results[0][0], rel=1e-3)


def test_mosek_task_holds_the_scaled_model():
    mosek = pytest.importorskip("mosek")
    p = _gated_plan()
    p.solve("maxBequest", {"netSpending": 105, "withdrawalOrder": "taxable_first", "solver": "HiGHS", "maxIter": 1})
    sc = p._mosekMoneyScaling(p.A, p.B, {})
    assert not sc.identity
    try:
        task, ncons, nvars = p._build_mosek_task(p.A, p.B, p.c, int_vars=p.B.integralityList(), scaling=sc)
    except mosek.Error as e:  # no license: the task cannot even be created
        pytest.skip(f"MOSEK unavailable: {e}")
    a_start, a_index, a_value = p.A.to_csr()
    scaled = sc.coefficients(a_index, a_value)
    starts = np.append(a_start, len(a_index))
    for i in range(0, ncons, max(1, ncons // 200)):
        _, idx, val = task.getarow(i)
        got = {int(j): v for j, v in zip(idx, val)}
        want = {int(j): v for j, v in zip(a_index[starts[i]:starts[i + 1]], scaled[starts[i]:starts[i + 1]]) if v != 0}
        assert got.keys() == want.keys()  # MOSEK keeps no explicit zeros
        for j in want:
            assert got[j] == pytest.approx(want[j], rel=1e-12)
        bk, lo, up = task.getconbound(i)
        lb, ub = sc.row_values([p.A.lb[i]])[0], sc.row_values([p.A.ub[i]])[0]
        if np.isfinite(lb):
            assert lo == pytest.approx(lb, rel=1e-12, abs=1e-12)
        if np.isfinite(ub):
            assert up == pytest.approx(ub, rel=1e-12, abs=1e-12)
    cind, cval = p.c.lists()
    expect = sc.objective(cind, cval)
    got = np.array([task.getcj(int(j)) for j in cind])
    np.testing.assert_allclose(got, expect, rtol=1e-12)
