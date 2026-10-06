"""
The local-search controls on the Run Options page (expert section).

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

import pytest

from owlplanner import readConfig
from owlplanner.config import config_to_ui, load_toml

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
CASE = Path(__file__).resolve().parents[2] / "examples" / "Case_jack+jill.toml"


def _render(monkeypatch, threshold_preset):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    diconf, _, _ = load_toml(str(CASE))
    if threshold_preset:
        diconf["solver_options"]["breakpointMethod"] = threshold_preset
    case = config_to_ui(diconf)
    case.update({"plan": readConfig(str(CASE), verbose=False), "id": "t1", "caseStatus": "new", "summaryDf": None})
    at = AppTest.from_file(str(UI_DIR / "Run_Options.py"), default_timeout=120)
    at.session_state["cases"] = {"t": case}
    at.session_state["currentCase"] = "t"
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    return at


def _toggle(at, label):
    found = [t for t in at.toggle if t.label == label]
    assert len(found) == 1, [t.label for t in at.toggle]
    return found[0]


@pytest.mark.toml
def test_local_search_off_leaves_the_milp_toggles_alone(monkeypatch):
    at = _render(monkeypatch, None)
    assert _toggle(at, "Solve tax breakpoints by local search (expert)").value is False
    assert _toggle(at, "Solve LTCG brackets with MILP (expert)").disabled is False


@pytest.mark.toml
def test_local_search_on_disables_the_individual_settings(monkeypatch):
    at = _render(monkeypatch, "local-search")
    assert _toggle(at, "Solve tax breakpoints by local search (expert)").value is True
    for label in ("Solve LTCG brackets with MILP (expert)", "Solve NIIT threshold with MILP (expert)"):
        assert _toggle(at, label).disabled is True, label
    strategy = [r for r in at.radio if r.label == "MILP strategy (expert)"]
    assert strategy and strategy[0].disabled is True
