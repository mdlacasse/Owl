"""
Tests for the workbook download buffers.

These pin the buffer contract: a saver returns a rewound, readable workbook. Streamlit's
download_button rewinds and uses getvalue() itself, so this is not what makes downloads work --
it just keeps the functions usable by any other consumer, and catches a truncated workbook.

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

from io import StringIO

import pytest

import owlplanner as owl
import ui.owlbridge as owb

CASE = "examples/Case_jack+jill.toml"


@pytest.fixture(scope="module")
def solved_plan():
    p = owl.readConfig(CASE, verbose=False)
    p.solve("maxSpending", options={"solver": "HiGHS"})
    assert p.caseStatus == "solved"
    return p


def _as_current_case(monkeypatch, plan):
    """Point the bridge's @_checkPlan lookup at this plan."""
    monkeypatch.setattr(owb.kz, "getCaseKey", lambda key: plan if key == "plan" else None)


@pytest.mark.toml
@pytest.mark.parametrize("fn_name", ["saveContributions", "saveWorkbook"])
def test_download_buffer_is_readable_from_the_start(monkeypatch, solved_plan, fn_name):
    """
    The buffer must be positioned at 0 and contain a complete xlsx payload.
    """
    _as_current_case(monkeypatch, solved_plan)
    buffer = getattr(owb, fn_name)()

    assert buffer.tell() == 0, "stream left at EOF: a plain read() would yield nothing"
    payload = buffer.read()
    assert len(payload) > 0
    assert payload[:2] == b"PK", "not a zip/xlsx payload"
    assert len(payload) == len(buffer.getvalue())


def test_getCaseString_is_empty_for_a_plan_that_has_never_run(monkeypatch):
    """
    Financial_Profile offers the HFP download on a case that cannot run, and refreshes the
    stored case file right after it. The session Plan is only populated by prepareRun(),
    so that path handed saveConfig() a Plan with beta_ij still None and the page died on a
    TypeError. getCaseString() must decline instead, and the "" it returns is what the
    call sites already test for.
    """
    log = StringIO()
    bare = owl.Plan(["Joe"], ["1960-01-01"], [90], "unrun", verbose=False, logstreams=[log, log])
    _as_current_case(monkeypatch, bare)
    # Visiting the Goals page is enough to set the objective, so the pre-existing
    # getSolveParameters() guard does not fire: exercise the readiness guard itself.
    monkeypatch.setattr(owb.kz, "getSolveParameters", lambda: ("maxSpending", {}))

    assert owb.getCaseString() == ""


@pytest.mark.toml
def test_getCaseString_still_returns_a_case_file_for_a_solved_plan(monkeypatch, solved_plan):
    _as_current_case(monkeypatch, solved_plan)
    monkeypatch.setattr(owb.kz, "getSolveParameters", lambda: ("maxSpending", {}))

    buffer = owb.getCaseString()
    assert "[basic_info]" in buffer.getvalue()
