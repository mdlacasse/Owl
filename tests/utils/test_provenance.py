"""
Tests for run provenance: engine commit, case-input hash, paper-repo commit.

The engine commit alone provably cannot identify a run. On 2026-11-25 an audit of 93
Cost_of_Committing artifacts found 26 produced with a taxable cost basis and 31 without, with
36 unclassifiable, because taxable_cost_basis sat uncommitted in the case files for weeks;
adding it moved one reference conversion by -38.5% while the engine stamp said nothing. These
tests pin the property that makes that detectable: a change to any case input changes the hash.

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

from datetime import date

import owlplanner as owl
from owlplanner.version import CASE_INPUT_FIELDS, case_provenance, engine_provenance, run_provenance


THISYEAR = date.today().year


def _plan(name="prov", taxable=100, nu=0.30, state=""):
    p = owl.Plan([name], [f"{THISYEAR - 65}-06-15"], [91], name, verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[taxable], taxDeferred=[1000], taxFree=[50], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setSocialSecurity([0], [70])
    p.setRates("historical", 1990)
    p.setHeirsTaxRate(100 * nu)
    if state:
        p.setStateTax(state)
    return p


def _hash(p):
    return next(iter(case_provenance(p)["cases"].values()))


def test_the_same_case_hashes_the_same():
    assert _hash(_plan()) == _hash(_plan())


def test_a_changed_balance_changes_the_hash():
    assert _hash(_plan(taxable=100)) != _hash(_plan(taxable=200))


def test_a_changed_heirs_rate_changes_the_hash():
    assert _hash(_plan(nu=0.30)) != _hash(_plan(nu=0.40))


def test_a_changed_state_changes_the_hash():
    assert _hash(_plan(state="")) != _hash(_plan(state="CA"))


def test_a_roth_pin_changes_the_hash():
    """The pins are inputs: the same household with a year pinned is a different run."""
    a = _plan()
    b = _plan()
    b.myRothX_in[0, 0] = 40_000.0
    b.rothXfixed_in[0, 0] = True
    assert _hash(a) != _hash(b)


def test_each_plan_is_reported_separately():
    prov = case_provenance(_plan("dana"), _plan("devon", taxable=4000))
    assert set(prov["cases"]) == {"dana", "devon"}
    assert len(set(prov["cases"].values())) == 2
    assert prov["fields"] == len(CASE_INPUT_FIELDS)


def test_run_provenance_carries_the_engine_and_the_cases():
    prov = run_provenance(_plan())
    assert prov["engine"] == engine_provenance()
    assert "version" in prov["engine"]
    assert len(next(iter(prov["cases"].values()))) == 12


def test_a_missing_pubs_dir_is_recorded_as_none_not_dropped():
    prov = run_provenance(_plan(), pubs_dir="/nonexistent/path/for/this/test")
    assert "pubs_commit" in prov and prov["pubs_commit"] is None
