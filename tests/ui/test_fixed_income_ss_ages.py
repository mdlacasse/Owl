"""
The Social Security claiming-age fields on the Fixed Income page start at the first month one is 62
throughout (POMS RS 00201.001): 62 years for those born on the 1st or 2nd, 62 years 1 month for
everyone else, the minimums the engine applies (#212).

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


def _render(monkeypatch, day, years, months):
    """Render Fixed_Income.py with Jack born on `day` of his birth month and a stored claiming age."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    plan = readConfig(str(CASE), verbose=False, logstreams=[io.StringIO()])
    diconf, _, _ = load_toml(str(CASE))
    case = config_to_ui(diconf)
    case["dob0"] = case["dob0"][:-2] + f"{day:02d}"
    case.update({
        "plan": plan, "id": "t1", "name": "t", "caseStatus": "modified", "summaryDf": None,
        "timeList0": plan.timeLists["Jack"], "timeList1": plan.timeLists["Jill"],
        "houseListDebts": plan.houseLists["Debts"], "houseListFixedAssets": plan.houseLists["Fixed Assets"],
        "hfpAbsentCols": dict(getattr(plan, "hfpAbsentCols", {})), "logs": io.StringIO(),
        "ssAge_y0": years, "ssAge_m0": months, "ssAgesMode": "none",
    })
    at = AppTest.from_file(str(UI_DIR / "Fixed_Income.py"), default_timeout=120)
    at.session_state["cases"] = {"t": case}
    at.session_state["currentCase"] = "t"
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    return at


def _jack_age_fields(at):
    years = next(w for w in at.number_input if w.label == "Jack's claiming at age...")
    # The months field has no name prefix; Jack's is the first one.
    months = next(w for w in at.number_input if w.label == "...and month(s)")
    return years, months


@pytest.mark.toml
@pytest.mark.parametrize(
    "day, stored, shown, min_year, min_month_at_62",
    [
        (1, (61, 11), (62, 0), 62, 0),  # born on the 1st: 62 throughout the birth month
        (2, (61, 11), (62, 0), 62, 0),
        (15, (62, 0), (62, 1), 62, 1),  # any other day: the month after
    ],
)
def test_claiming_age_minimum(monkeypatch, day, stored, shown, min_year, min_month_at_62):
    at = _render(monkeypatch, day, *stored)
    years, months = _jack_age_fields(at)
    assert years.proto.min == min_year
    assert (years.value, months.value) == shown  # a stored age below the minimum is raised to it
    assert months.proto.min == min_month_at_62
