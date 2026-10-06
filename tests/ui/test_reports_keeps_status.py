"""
Visiting Reports must not mark a solved case as modified.

Reports syncs the Financial Profile tables on every visit, to offer the workbook download. That
sync used to store a display flag (hfpAbsentCols) through a setter that marks the case modified,
so leaving Reports for Graphs re-solved a case nothing had changed.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
from pathlib import Path

import pytest

from owlplanner import readConfig
from owlplanner.config import config_to_ui, load_toml

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
CASE = Path(__file__).resolve().parents[2] / "examples" / "Case_jack+jill.toml"


def _render_reports(monkeypatch, edit_wages=False):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    plan = readConfig(str(CASE), verbose=False, logstreams=[io.StringIO()])
    plan.solve(plan.objective, options=dict(plan.solverOptions))
    assert plan.caseStatus == "solved"

    diconf, _, _ = load_toml(str(CASE))
    case = config_to_ui(diconf)
    case.update({
        "plan": plan, "id": "t1", "name": "t", "caseStatus": "solved", "summaryDf": None,
        "timeList0": plan.timeLists["Jack"], "timeList1": plan.timeLists["Jill"],
        "houseListDebts": plan.houseLists["Debts"], "houseListFixedAssets": plan.houseLists["Fixed Assets"],
        "hfpAbsentCols": dict(getattr(plan, "hfpAbsentCols", {})), "logs": io.StringIO(),
    })
    if edit_wages:
        edited = plan.timeLists["Jack"].copy()
        edited.loc[edited.index[-1], "anticipated wages"] += 1000.0
        case["timeList0"] = edited
    at = AppTest.from_file(str(UI_DIR / "Reports.py"), default_timeout=120)
    at.session_state["cases"] = {"t": case}
    at.session_state["currentCase"] = "t"
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    return at, plan


@pytest.mark.toml
def test_reports_leaves_a_solved_case_solved(monkeypatch):
    at, plan = _render_reports(monkeypatch)
    assert at.session_state["cases"]["t"]["caseStatus"] == "solved"
    # The plan too: its plotting methods refuse to run unless it is solved, so a sync of
    # unchanged tables that marked it modified left Graphs without images.
    assert plan.caseStatus == "solved"


@pytest.mark.toml
def test_an_edited_table_still_marks_the_plan_modified(monkeypatch):
    _, plan = _render_reports(monkeypatch, edit_wages=True)
    assert plan.caseStatus == "modified"
