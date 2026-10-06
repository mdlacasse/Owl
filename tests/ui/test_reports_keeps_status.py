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


@pytest.mark.toml
def test_reports_leaves_a_solved_case_solved(monkeypatch):
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
    at = AppTest.from_file(str(UI_DIR / "Reports.py"), default_timeout=120)
    at.session_state["cases"] = {"t": case}
    at.session_state["currentCase"] = "t"
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    assert at.session_state["cases"]["t"]["caseStatus"] == "solved"
