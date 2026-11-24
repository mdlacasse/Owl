"""
Run Options: the year fields accept a year past the plan, but not an extra digit.

A year past the plan is a legitimate "never" (and survives a change of longevity), so the
fields are not bounded by the plan's last year. They stop at last_year_entered(), past any
plan, which refuses a typo such as 20300 for 2030.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "examples" / "Case_jack+jill.toml"

LABELS = (
    "Year to start considering Roth conversions",
    "Year to stop considering Roth conversions",
    "Year to switch converters",
    "ACA start year",
)


@pytest.mark.toml
def test_year_fields_reach_past_the_plan(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    from owlplanner import readConfig
    from owlplanner.config import config_to_ui, load_toml

    # AppTest has no multipage context: st.page_link cannot resolve the pages.
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    plan = readConfig(str(CASE), verbose=False, logstreams=[io.StringIO()])
    diconf, _, _ = load_toml(str(CASE))
    dic = config_to_ui(diconf)
    lastyear = date.today().year + 120
    dic.update({
        "plan": plan, "id": "t1", "name": "jj", "caseStatus": "modified", "summaryDf": None,
        "stopRothConversionsEnabled": True, "swapRothConvertersEnabled": True, "noRothConversions": "none",
        "startRothConversions": 2100, "stopRothConversions": lastyear,
    })
    at = AppTest.from_file(str(ROOT / "ui" / "Run_Options.py"), default_timeout=60)
    at.session_state["cases"] = {"jj": dic}
    at.session_state["currentCase"] = "jj"
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    fields = {label: next(w for w in at.number_input if w.label.startswith(label)) for label in LABELS}
    assert all(f.max == lastyear for f in fields.values()), {k: f.max for k, f in fields.items()}
    assert fields[LABELS[0]].value == 2100 and fields[LABELS[1]].value == lastyear
