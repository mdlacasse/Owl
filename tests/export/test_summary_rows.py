"""
The Summary has the same rows for every plan of a household, whatever its numbers.

The side-by-side comparison (ui/sskeys.compareSummaries) keeps only the rows all its cases have,
so a row reported only when nonzero -- wages, a pension, giving, a state tax, the earnings test --
dropped out of the comparison of every case as soon as one variant lacked it: Case_jordan+taylor-qcd,
built to be compared with Case_jordan+taylor, lost its QCD rows. Only the plan's shape may change
the rows: the people's names, a first death inside the plan (the partial bequest), a summary
shorter than the plan (no final bequest).

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import os
import warnings

import pytest

import owlplanner as owl
from owlplanner.export import build_summary_dic

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def _solved(case, change=None):
    p = owl.readConfig(os.path.join(EXAMPLES, f"Case_{case}.toml"), verbose=False, logstreams=[io.StringIO()])
    if change is not None:
        change(p)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p.solve(p.objective, p.solverOptions)
    assert p.caseStatus == "solved"
    return p


def _no_wages(p):
    p.omega_in[:, :] = 0.0


def _california(p):
    p.setStateTax("CA")


def _no_benefit(p):
    p.setSocialSecurity([0, 0], list(p.ssecAges))


@pytest.mark.toml
def test_variants_of_a_household_have_the_same_rows():
    """jack+jill (Tennessee, wages, the earnings test) against itself without wages, in
    California, and with no Social Security: the same rows in the same order."""
    base = list(build_summary_dic(_solved("jack+jill")))
    for change in (_no_wages, _california, _no_benefit):
        assert list(build_summary_dic(_solved("jack+jill", change))) == base, change.__name__


@pytest.mark.toml
def test_giving_and_not_giving_have_the_same_rows():
    """Case_jordan+taylor-qcd is jordan+taylor with QCDs: both report the QCD rows, at $0 without."""
    give = build_summary_dic(_solved("jordan+taylor-qcd"))
    keep = build_summary_dic(_solved("jordan+taylor"))
    assert list(give) == list(keep)
    qcd = [k for k in keep if "qualified charitable distributions" in k]
    assert qcd and all(keep[k] == "$0" for k in qcd)
    assert all(give[k] != "$0" for k in qcd)


@pytest.mark.toml
def test_rows_that_were_conditional_now_read_zero():
    """A Tennessee household pays no state tax and reports $0; a spouse without a benefit of either
    kind reports no claiming age."""
    dic = build_summary_dic(_solved("jack+jill", _no_benefit))
    state = [k for k in dic if k.startswith("Total state income tax paid")]
    assert len(state) == 2 and all(dic[k] == "$0" for k in state)
    ages = [k for k in dic if k.endswith("'s SS claiming age")]
    assert len(ages) == 2 and all(dic[k] == "none" for k in ages)
