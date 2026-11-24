"""
Tests for the SSA earnings test under ``withSSAges``.

Since #195 the claiming-age search solves the plan at fixed ages for every open month,
each candidate on a clone of the plan, and keeps the best. The earnings test then reaches
every candidate through the fixed-age path, provided each clone carries the earnings
columns. These tests guard that:

- every candidate the search solves equals an independent fixed-age solve of a freshly
  loaded plan at the same ages, with the test on (and the candidate's ARF months show
  the test was applied on the clone);
- without the test (the test run on zero earnings) the same candidates are the no-test
  ones;
- the search keeps the best candidate, and the plan it returns carries that candidate's
  streams and earnings-test outputs.

The search is limited to a few of Jill's open months (``_ssaOpenAges`` patched) to keep
the run short: the clones, the options and the comparison are the search's own. Expected
values come from independent solves, not from the search.

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

import contextlib
import io
import os
import threading

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import socialsecurity as ss
from owlplanner.plan import Plan

_EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")

# Jill (jack+jill, born 1966-01-15) claims 62y1m in the case and earns $85k in 2028, her
# last work year: at 62y1m the whole 2028 is withheld (11 ARF months, step 3), at 63 (Jan
# 2029, no earnings) nothing is. 64, 67 and 70 are later claims the test never reaches.
JILL = 1
OPEN_MONTHS = [62 * 12 + 1, 63 * 12, 64 * 12, 67 * 12, 70 * 12]


def _load():
    p = owl.readConfig(os.path.join(_EXAMPLES, "Case_jack+jill.toml"), verbose=False, logstreams=[io.StringIO()])
    p.readHFP(os.path.join(_EXAMPLES, "HFP_jack+jill.xlsx"))
    return p


def _opts(p, **extra):
    return dict(p.solverOptions or {}, **extra)


@contextlib.contextmanager
def _test(test_on):
    """With the earnings test (always applied), or without it: the test run on zero
    earnings withholds nothing, so the plan keeps compute_social_security_benefits'
    streams."""
    if test_on:
        yield
        return
    real = ss.earnings_test

    def zero(*a, **k):
        a = list(a)
        a[8] = np.zeros_like(np.asarray(a[8], dtype=float))
        return real(*a, **k)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ss, "earnings_test", zero)
        yield


def _months(ages):
    return tuple(int(round(a * 12)) for a in ages)


def _search(test_on):
    """Search Jill's age over OPEN_MONTHS; return the plan and what each candidate solved."""
    seen = {}
    lock = threading.Lock()
    open_ages = Plan._ssaOpenAges
    objective_value = Plan._objectiveValue

    def _open(self, i):
        return [m / 12 for m in OPEN_MONTHS] if i == JILL else open_ages(self, i)

    def _record(self, objective):
        value = objective_value(self, objective)
        with lock:
            seen[_months(self.ssecAges)] = {
                "value": value,
                "arf": self.ss_arf_months_i.copy(),
                "withheld": float(np.sum(self.ss_withheld_in)),
            }
        return value

    p = _load()
    with pytest.MonkeyPatch.context() as mp, _test(test_on):
        mp.setattr(Plan, "_ssaOpenAges", _open)
        mp.setattr(Plan, "_objectiveValue", _record)
        p.solve(p.objective, _opts(p, withSSAges=["Jill"]))
    assert p.caseStatus == "solved"
    return p, seen


def _fixed(ages, test_on):
    """An independent fixed-age solve of a freshly loaded plan."""
    p = _load()
    with _test(test_on):
        p.setSocialSecurity(list(p.ssecAmounts), list(ages))
        p.solve(p.objective, _opts(p))
    assert p.caseStatus == "solved"
    return p


@pytest.fixture(scope="module")
def runs():
    out = {}
    for test_on in (True, False):
        searched, seen = _search(test_on)
        jack = float(searched.ssecAges[0])
        fixed = {m: _fixed([jack, m / 12], test_on) for m in OPEN_MONTHS}
        out[test_on] = (searched, seen, fixed)
    return out


@pytest.mark.parametrize("test_on", [True, False])
def test_every_candidate_is_the_fixed_age_solve(runs, test_on):
    """Each candidate's objective and earnings-test outputs are those of a fresh plan solved
    at the same ages, with or without the test: the clone carried the earnings."""
    searched, seen, fixed = runs[test_on]
    jack = int(round(searched.ssecAges[0] * 12))
    for m in OPEN_MONTHS:
        cand = seen[(jack, m)]
        ref = fixed[m]
        assert cand["value"] == pytest.approx(ref._objectiveValue(searched.objective), abs=0.01), m
        assert np.array_equal(cand["arf"], ref.ss_arf_months_i), m
        assert cand["withheld"] == pytest.approx(float(np.sum(ref.ss_withheld_in)), abs=0.01), m


def test_candidates_see_the_test(runs):
    """The 62y1m candidate has the whole 2028 withheld with the test (11 ARF months,
    step 3), and nothing without it; the later claims are the same either way."""
    _, on, _ = runs[True]
    searched, off, _ = runs[False]
    jack = int(round(searched.ssecAges[0] * 12))
    first = (jack, OPEN_MONTHS[0])
    assert on[first]["arf"][JILL] == 11
    assert on[first]["withheld"] > 0
    assert off[first]["arf"][JILL] == 0
    assert off[first]["withheld"] == 0
    assert on[first]["value"] != pytest.approx(off[first]["value"], abs=0.01)
    for m in OPEN_MONTHS[1:]:
        assert on[(jack, m)]["withheld"] == 0
        assert on[(jack, m)]["value"] == pytest.approx(off[(jack, m)]["value"], abs=0.01)


@pytest.mark.parametrize("test_on", [True, False])
def test_search_keeps_the_best_fixed_age_solve(runs, test_on):
    """The pick is the best of the independent fixed-age solves (ties: the search keeps the
    first it met, so only the value is compared), and the plan returned carries that
    solve's streams and earnings-test outputs."""
    searched, _, fixed = runs[test_on]
    objective = searched.objective
    best = max(fixed[m]._objectiveValue(objective) for m in OPEN_MONTHS)
    assert searched._objectiveValue(objective) == pytest.approx(best, abs=0.01)
    pick = int(round(searched.ssecAges[JILL] * 12))
    assert pick in OPEN_MONTHS
    ref = fixed[pick]
    assert fixed[pick]._objectiveValue(objective) == pytest.approx(best, abs=0.01)
    assert np.allclose(searched.zeta_in, ref.zeta_in, rtol=0.0, atol=1e-6)
    assert np.array_equal(searched.ss_arf_months_i, ref.ss_arf_months_i)
    assert np.allclose(searched.ss_withheld_in, ref.ss_withheld_in, rtol=0.0, atol=1e-6)


# --------------------------------------------------------------------------------------
# The test changes the decision
# --------------------------------------------------------------------------------------


def test_the_test_moves_pats_pick():
    """chris+pat: Pat (born 1966-01-15, PIA $1,400) earns $85k in 2028, her last work year.
    Between a claim at 62y3m (April 2028, in that year) and at 63y0m (January 2029, the month
    after it), the search takes the later one with the test, as SSA would withhold
    April-December 2028: 63y0m is ahead by $147/yr with MOSEK and $161/yr with HiGHS (0.13%).
    Without the test the two are within the loop's fixed-point noise (-$7/yr with MOSEK,
    +$53/yr with HiGHS), so that pick is solver-dependent and is not pinned. It checks the
    decision, not only the plan returned: it fails when the candidates lose the earnings even
    though the returned plan is re-solved with them."""
    months = [62 * 12 + 3, 63 * 12]
    open_ages = Plan._ssaOpenAges
    picks = {}
    for test_on in (True,):
        p = owl.readConfig(os.path.join(_EXAMPLES, "Case_chris+pat.toml"), verbose=False, logstreams=[io.StringIO()])
        p.readHFP(os.path.join(_EXAMPLES, "HFP_chris+pat.xlsx"))
        with pytest.MonkeyPatch.context() as mp, _test(test_on):
            mp.setattr(Plan, "_ssaOpenAges", lambda self, i: [m / 12 for m in months] if i == 1 else open_ages(self, i))
            p.solve(p.objective, _opts(p, withSSAges=["Pat"]))
        assert p.caseStatus == "solved"
        picks[test_on] = int(round(p.ssecAges[1] * 12))
        if test_on:
            assert np.all(p.ss_withheld_in == 0)  # the pick claims after the work year
    assert picks == {True: 63 * 12}
