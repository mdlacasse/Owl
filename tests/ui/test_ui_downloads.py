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
