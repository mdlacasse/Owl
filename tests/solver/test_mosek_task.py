"""
Plan._build_mosek_task passes the model to MOSEK in bulk calls (putarowslice and the slices for
bounds); these tests check that the task holds exactly what the former one-call-per-row builder
put in it, for an LP in dollars and a scaled MIP.

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
from owlplanner import abcapi
from owlplanner.plan import _MoneyScaling

mosek = pytest.importorskip("mosek")


def _rowwise_task(A, B, c_obj, int_vars=None, scaling=None):
    """The former builder, one MOSEK call per objective term, bound and row: the reference."""
    bdic = {"fx": mosek.boundkey.fx, "fr": mosek.boundkey.fr, "lo": mosek.boundkey.lo,
            "ra": mosek.boundkey.ra, "up": mosek.boundkey.up}
    Aind, Aval, clb, cub = A.lists()
    ckeys = A.keys()
    vlb, vub = B.arrays()
    vkeys = list(B.keys())
    cind, cval = c_obj.lists()
    task = mosek.Task()
    task.appendcons(A.ncons)
    task.appendvars(A.nvars)
    scaling = scaling or _MoneyScaling()
    cval = scaling.objective(cind, cval)
    vlb, vub = scaling.col_values(vlb), scaling.col_values(vub)
    clb, cub = scaling.row_values(clb), scaling.row_values(cub)
    for ii in range(len(cind)):
        task.putcj(cind[ii], cval[ii])
    for ii in range(A.nvars):
        task.putvarbound(ii, bdic[vkeys[ii]], float(vlb[ii]), float(vub[ii]))
    for ii in int_vars or []:
        task.putvartype(int(ii), mosek.variabletype.type_int)
    if not scaling.identity:
        ends = np.cumsum([len(ind) for ind in Aind])
        flat = scaling.coefficients(np.concatenate(Aind), np.concatenate(Aval))
        Aval = np.split(flat, ends[:-1])
    for i in range(A.ncons):
        task.putarow(i, Aind[i], Aval[i])
        task.putconbound(i, bdic[ckeys[i]], float(clb[i]), float(cub[i]))
    task.putobjsense(mosek.objsense.minimize)
    return task


def _assert_same_task(new, ref):
    m, n = ref.getnumcon(), ref.getnumvar()
    assert (new.getnumcon(), new.getnumvar()) == (m, n)
    for i in range(m):
        _, ji, vi = new.getarow(i)
        _, jr, vr = ref.getarow(i)
        assert dict(zip(ji, vi, strict=True)) == dict(zip(jr, vr, strict=True)), f"row {i}"
    for got, want in zip(new.getconboundslice(0, m), ref.getconboundslice(0, m), strict=True):
        assert list(got) == list(want)
    for got, want in zip(new.getvarboundslice(0, n), ref.getvarboundslice(0, n), strict=True):
        assert list(got) == list(want)
    assert list(new.getc()) == list(ref.getc())
    assert list(new.getvartypelist(range(n))) == list(ref.getvartypelist(range(n)))
    assert new.getobjsense() == ref.getobjsense()


def _built(p, objective, options):
    """The plan's A, B and c after a one-iteration HiGHS solve."""
    p.solve(objective, dict(options, solver="HiGHS", maxIter=1))
    return p


def _scaled_mip_plan():
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


@pytest.mark.toml
def test_lp_task_matches_the_rowwise_build():
    """A couple's LP in dollars (identity scaling, no integer variables)."""
    p = _built(owl.readConfig("examples/Case_jack+jill.toml", verbose=False), "maxSpending", {})
    assert not p.B.integralityList()
    try:
        new, _, _ = p._build_mosek_task(p.A, p.B, p.c)
    except mosek.Error as e:  # no license: the task cannot even be created
        pytest.skip(f"MOSEK unavailable: {e}")
    _assert_same_task(new, _rowwise_task(p.A, p.B, p.c))


def test_scaled_mip_task_matches_the_rowwise_build():
    """A MIP with money scaling: integer columns, scaled rows, bounds and objective."""
    p = _built(_scaled_mip_plan(), "maxBequest", {"netSpending": 105, "withdrawalOrder": "taxable_first"})
    int_vars = p.B.integralityList()
    assert int_vars
    sc = p._mosekMoneyScaling(p.A, p.B, {})
    assert not sc.identity
    try:
        new, _, _ = p._build_mosek_task(p.A, p.B, p.c, int_vars=int_vars, scaling=sc)
    except mosek.Error as e:
        pytest.skip(f"MOSEK unavailable: {e}")
    _assert_same_task(new, _rowwise_task(p.A, p.B, p.c, int_vars=int_vars, scaling=sc))


def test_duplicate_objective_term_keeps_the_last_value():
    """Objective.setElem appends: a column set twice keeps its last value, as putcj did."""
    A, B, c = abcapi.ConstraintMatrix(2), abcapi.Bounds(2, 0), abcapi.Objective(2)
    c.setElem(0, 1.0)
    c.setElem(1, 2.0)
    c.setElem(0, 5.0)
    p = owl.Plan(["Sam"], ["1976-04-10"], [70], "dup", verbose=False)
    try:
        new, ncons, nvars = p._build_mosek_task(A, B, c)
    except mosek.Error as e:
        pytest.skip(f"MOSEK unavailable: {e}")
    assert (ncons, nvars) == (0, 2)  # no rows: the matrix and row-bound calls are skipped
    assert list(new.getc()) == [5.0, 2.0]
    _assert_same_task(new, _rowwise_task(A, B, c))
