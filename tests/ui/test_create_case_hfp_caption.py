"""
Create Case confirms a workbook read, as Financial Profile does (#246).

Once a workbook is read the uploader on Create Case is hidden; the caption takes its place.

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
from pathlib import Path

import pytest

from owlplanner import readConfig
from owlplanner.config import config_to_ui, load_toml

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
CASE = Path(__file__).resolve().parents[2] / "examples" / "Case_jack+jill.toml"


def _captions(monkeypatch, **hfp):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    # AppTest has no multipage context, so st.page_link raises KeyError('url_pathname').
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)

    plan = readConfig(str(CASE), verbose=False, logstreams=[io.StringIO()])
    diconf, _, _ = load_toml(str(CASE))
    case = config_to_ui(diconf)
    case.update({"plan": plan, "id": "t1", "caseStatus": "modified", "summaryDf": None, **hfp})
    at = AppTest.from_file(str(UI_DIR / "Create_Case.py"), default_timeout=120)
    at.session_state["cases"] = {"t": case}
    at.session_state["currentCase"] = "t"
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    return [c.value for c in at.caption if "loaded" in c.value]


@pytest.mark.toml
def test_create_case_confirms_the_workbook_read(monkeypatch):
    shown = _captions(monkeypatch, stHFP="HFP_jack+jill.xlsx", hfpFileName="HFP_jack+jill.xlsx")
    assert shown == [":white_check_mark: *HFP_jack+jill.xlsx* loaded."]


@pytest.mark.toml
def test_create_case_says_the_values_were_modified(monkeypatch):
    shown = _captions(monkeypatch, stHFP="HFP_jack+jill.xlsx", hfpFileName="HFP_jack+jill.xlsx *")
    assert shown == [":white_check_mark: *HFP_jack+jill.xlsx*\\* loaded — values modified."]


@pytest.mark.toml
def test_create_case_says_nothing_before_a_workbook_is_read(monkeypatch):
    assert _captions(monkeypatch, stHFP=None) == []
