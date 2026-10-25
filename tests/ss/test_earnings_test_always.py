"""
The SSA earnings test is part of the model:

- every solve applies it;
- where the test withholds nothing, the streams are those of
  ``compute_social_security_benefits`` itself, not the test's copy of
  it, so a case the test does not touch is unchanged by construction;
- the Summary rows appear for a household with earnings the test can reach (a year with
  earnings up to the person's FRA year), $0 / "none" included, so comparing two claiming
  ages of one household keeps them; a household without such earnings gets none;
- ``owlcli explain`` reports what the test withholds, with no flag for whether it applies.

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

import numpy as np

import owlplanner as owl
from owlplanner import socialsecurity as ss
from owlplanner.export import build_summary_dic

_EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")
THISYEAR = 2026  # tests/conftest.py freezes the date


def _load(case):
    p = owl.readConfig(os.path.join(_EXAMPLES, f"Case_{case}.toml"), verbose=False, logstreams=[io.StringIO()])
    p.readHFP(os.path.join(_EXAMPLES, f"HFP_{case}.xlsx"))
    return p


def _solve(p, **extra):
    opts = dict(p.solverOptions or {}, **extra)
    p.solve(p.objective, opts)
    assert p.caseStatus == "solved"
    return p


def _n(p, year):
    return int(year) - int(p.year_n[0])


def test_applied_to_jack_jill_as_shipped():
    """jack+jill as shipped: Jill's 2028, her last work year at $85k
    after a claim at 62y1m, is withheld and comes back as 11 ARF months."""
    p = _solve(_load("jack+jill"))
    assert p.zeta_in[1, _n(p, 2028)] == 0.0
    assert p.ss_withheld_in[1, _n(p, 2028)] > 0
    assert p.ss_arf_months_i[1] == 11


def test_streams_are_the_builders_where_nothing_is_withheld(monkeypatch):
    """Where the test withholds nothing, the plan's streams come from
    compute_social_security_benefits itself: a marker added to its output shows up in
    zeta_in. Jack+jill with no earnings: nothing to withhold."""
    real = ss.compute_social_security_benefits

    def marked(*a, **k):
        zeta, ages = real(*a, **k)
        return zeta + 0.25, ages

    p = _load("jack+jill")
    p.omega_in[:, :] = 0.0
    monkeypatch.setattr(ss, "compute_social_security_benefits", marked)
    _solve(p)
    base, _ = real(p.ssecAmounts, p.ssecAges, p.yobs, p.mobs, p.tobs, p.horizons, p.N_i, p.N_n)
    assert np.allclose(p.zeta_in, base + 0.25, rtol=0.0, atol=1e-9)
    assert np.all(p.ss_withheld_in == 0)


def test_summary_rows_where_earnings_can_meet_the_test():
    """jack+jill has wages before both FRAs: the rows are there, and still there ($0,
    'none') when Jill claims at 67, after her work, so the two claiming ages compare row
    by row. With no earnings at all they are still there, at $0 and 'none': the Summary has
    the same rows for every plan, so working and not working compare row by row too."""
    p = _solve(_load("jack+jill"))
    dic = build_summary_dic(p)
    assert any(k.startswith("SS withheld by the earnings test") for k in dic)
    assert "11" in dic["ARF months"]

    late = _load("jack+jill")
    late.setSocialSecurity(list(late.ssecAmounts), [float(late.ssecAges[0]), 67.0])
    dic = build_summary_dic(_solve(late))
    rows = [k for k in dic if k.startswith("SS withheld by the earnings test")]
    assert len(rows) == 2 and all(dic[k] == "$0" for k in rows)
    assert dic["ARF months"] == "none"

    none = _load("jack+jill")
    none.omega_in[:, :] = 0.0
    dic = build_summary_dic(_solve(none))
    rows = [k for k in dic if k.startswith("SS withheld by the earnings test")]
    assert len(rows) == 2 and all(dic[k] == "$0" for k in rows)
    assert dic["ARF months"] == "none"


def test_explain_block_has_no_applied_flag():
    """`owlcli explain` reports what the test withholds; it always applies."""
    from owlplanner.cli.cmd_explain import _plan_to_explain

    p = _load("jack+jill")
    block = _plan_to_explain(p, "Case_jack+jill.toml", [])["social_security"]
    for entry in block:
        assert "applied" not in entry["earnings_test"]
    assert {e["name"]: e["earnings_test"]["arf_months"] for e in block} == {"Jack": 0, "Jill": 11}
