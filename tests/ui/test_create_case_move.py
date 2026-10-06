"""
The change-of-state controls on the Create Case page (#159).

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

from pathlib import Path

import pytest

from owlplanner.config import config_to_ui, load_toml

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
CASE = Path(__file__).resolve().parents[2] / "examples" / "Case_jack+jill.toml"


def _render(monkeypatch, moves):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    # AppTest has no multipage context, so st.page_link raises KeyError('url_pathname').
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)

    diconf, _, _ = load_toml(str(CASE))
    diconf["basic_info"]["state"] = "NY"
    if moves:
        diconf["basic_info"]["moves"] = moves
    case = config_to_ui(diconf)
    case.update({"plan": None, "id": "t1", "caseStatus": "new", "summaryDf": None})
    at = AppTest.from_file(str(UI_DIR / "Create_Case.py"), default_timeout=120)
    at.session_state["cases"] = {"t": case}
    at.session_state["currentCase"] = "t"
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    return at


@pytest.mark.toml
def test_move_fields_hidden_without_a_move(monkeypatch):
    at = _render(monkeypatch, None)
    toggle = [t for t in at.toggle if t.label == "Move to another state during the plan"]
    assert len(toggle) == 1 and toggle[0].value is False
    assert not [s for s in at.selectbox if s.label == "New state"]


@pytest.mark.toml
def test_move_fields_show_the_move(monkeypatch):
    at = _render(monkeypatch, [{"year": 2031, "state": "FL"}])
    toggle = [t for t in at.toggle if t.label == "Move to another state during the plan"]
    assert toggle[0].value is True
    assert [n.value for n in at.number_input if n.label == "Year of the move"] == [2031]
    assert [s.value for s in at.selectbox if s.label == "New state"] == ["FL"]
