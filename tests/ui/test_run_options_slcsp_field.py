"""
Run Options: the health-cost fields show two decimals and step by one unit.

With `sskeys.getNum`'s defaults the benchmark premium (SLCSP) showed 20.84 as 20.8 and its +/-
moved the premium by $10k a year; other medical expenses and the Part D base premium had the
same defaults.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "examples" / "Case_riley+casey.toml"

LABELS = (
    "Benchmark Silver plan premium",
    "Other medical expenses",
    "Part D base premium",
)


def test_health_cost_fields_show_two_decimals_and_step_by_one(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    from owlplanner import readConfig
    from owlplanner.config import config_to_ui, load_toml

    # AppTest has no multipage context: st.page_link cannot resolve the pages.
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    plan = readConfig(str(CASE), verbose=False, logstreams=[io.StringIO()])
    diconf, _, _ = load_toml(str(CASE))
    dic = config_to_ui(diconf)
    dic.update({"plan": plan, "id": "t1", "name": "rc", "caseStatus": "modified", "summaryDf": None})
    at = AppTest.from_file(str(ROOT / "ui" / "Run_Options.py"), default_timeout=60)
    at.session_state["cases"] = {"rc": dic}
    at.session_state["currentCase"] = "rc"
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    for label in LABELS:
        field = next(w for w in at.number_input if w.label.startswith(label))
        assert field.proto.format == "%.2f" and field.proto.step == 1.0, label
    slcsp = next(w for w in at.number_input if w.label.startswith(LABELS[0]))
    assert slcsp.value == 22.0
