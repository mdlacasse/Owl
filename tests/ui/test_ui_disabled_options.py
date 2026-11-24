"""
Options that do not apply stay on the page, disabled, rather than disappearing.

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


def _render(monkeypatch, page, **case_keys):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    diconf, _, _ = load_toml(str(CASE))
    case = config_to_ui(diconf)
    case.update({"plan": readConfig(str(CASE), verbose=False), "id": "t1", "caseStatus": "new", "summaryDf": None})
    case.update(case_keys)
    at = AppTest.from_file(str(UI_DIR / page), default_timeout=120)
    at.session_state["cases"] = {"t": case}
    at.session_state["currentCase"] = "t"
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    return at


def _rerun(at):
    # The sidebar's case selector decorates the case name in its options; keep it on that option.
    for box in at.selectbox:
        if box.label == "Case selector":
            box.set_value(box.options[0])
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]


def _checkbox(at, label):
    found = [c for c in at.checkbox if c.label == label]
    assert len(found) == 1, [c.label for c in at.checkbox]
    return found[0]


@pytest.mark.toml
def test_ss_ages_are_chosen_per_person(monkeypatch):
    at = _render(monkeypatch, "Run_Options.py")
    _checkbox(at, "Jill").check()
    _rerun(at)
    assert at.session_state["cases"]["t"]["ssAgesMode"] == "Jill"
    _checkbox(at, "Jack").check()
    _rerun(at)
    assert at.session_state["cases"]["t"]["ssAgesMode"] == "both"


@pytest.mark.toml
def test_a_past_claiming_age_is_disabled_not_hidden(monkeypatch):
    # Jack, born in 1963, entered 62: that age is past, so he cannot be optimized.
    at = _render(monkeypatch, "Run_Options.py", ssAge_y0=62, ssAge_m0=0, ssAgesMode="both")
    jack = _checkbox(at, "Jack")
    assert jack.disabled is True and jack.value is False
    assert _checkbox(at, "Jill").value is True
    assert at.session_state["cases"]["t"]["ssAgesMode"] == "Jill"


def test_an_optimized_deposit_split_round_trips_through_the_ui():
    from owlplanner.config import ui_to_config

    diconf, _, _ = load_toml(str(CASE))
    diconf["savings_assets"]["spousal_surplus_deposit_fraction"] = "optimize"
    uidic = config_to_ui(diconf)
    assert uidic["surplusFractionOptimize"] is True and uidic["surplusFraction"] == 0.5
    assert ui_to_config(uidic)["savings_assets"]["spousal_surplus_deposit_fraction"] == "optimize"
    uidic["surplusFractionOptimize"] = False
    uidic["surplusFraction"] = 0.25
    assert ui_to_config(uidic)["savings_assets"]["spousal_surplus_deposit_fraction"] == 0.25
