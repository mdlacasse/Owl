"""
Tests for the Wages and Contributions editors on the Financial Profile page.

The table is one DataFrame in session state and one sheet in the workbook, but it
is rendered as two stacked editors: the five lead-in years, and the plan years.
The split exists because Streamlit can only disable whole columns, so the only way
to disable "Roth conv fixed" on the past rows -- where conversions have already
happened and the flag is meaningless -- is to give those rows an editor of their
own, where the column and the rows are the same thing.

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

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from owlplanner import readConfig

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
CASE = EXAMPLES / "Case_jack+jill.toml"
THISYEAR = date.today().year


def _render(monkeypatch, plan):
    """Render Financial_Profile.py with a two-person case already loaded."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    # AppTest has no multipage context, so st.page_link raises KeyError('url_pathname').
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)

    case = {
        "plan": plan,
        "name": "t",
        "id": "t1",
        "iname0": "Jack",
        "iname1": "Jill",
        "status": "married",
        "timeList0": plan.timeLists["Jack"],
        "timeList1": plan.timeLists["Jill"],
        "houseListDebts": plan.houseLists["Debts"],
        "houseListFixedAssets": plan.houseLists["Fixed Assets"],
        "hfpAbsentCols": dict(getattr(plan, "hfpAbsentCols", {})),
        "hfpFileName": "HFP_jack+jill.xlsx",
        "stHFP": None,
        "caseStatus": "modified",
        "summaryDf": None,
    }
    at = AppTest.from_file(str(UI_DIR / "Financial_Profile.py"), default_timeout=120)
    at.session_state["cases"] = {"t": case}
    at.session_state["currentCase"] = "t"
    at.run()
    return at


@pytest.fixture
def rendered(monkeypatch):
    return _render(monkeypatch, readConfig(str(CASE), verbose=False))


def test_page_renders_without_exception(rendered):
    assert not rendered.exception, [str(e.message) for e in rendered.exception]


def test_two_editors_per_individual(rendered):
    """Each person gets a lead-in editor and a plan-year editor, each under its own label
    and above its own caption. Two of each for a couple is the signal that the split
    rendered, and the labels are what tell a reader which table is which."""
    labels = [str(m.value) for m in rendered.markdown]
    assert labels.count("*Past five years*") == 2, labels
    assert labels.count("*Plan years*") == 2, labels

    captions = [str(c.value) for c in rendered.caption]
    past = [c for c in captions if "kept in your workbook" in c]
    plan = [c for c in captions if "Roth conv fixed" in c]
    assert len(past) == 2, captions
    assert len(plan) == 2, captions


def test_split_and_recombine_is_lossless():
    """The editors slice by year and the write-back concatenates. That round trip has
    to be the identity, including row order: setContributions() and checkQCDColumn()
    both slice the recombined frame positionally."""
    plan = readConfig(str(CASE), verbose=False)
    for iname, df in plan.timeLists.items():
        past = df[df["year"] < THISYEAR]
        future = df[df["year"] >= THISYEAR]
        rebuilt = pd.concat([past, future], ignore_index=True)
        assert len(past) == 5, iname
        assert df.reset_index(drop=True).equals(rebuilt), iname
        assert rebuilt["year"].is_monotonic_increasing, iname


def test_recombined_frame_needs_a_reset_index_to_compare():
    """The stored frame can carry a permuted index -- _conditionTimetables sorts by
    year without reindexing -- while the recombined one is always 0..h+4. Comparing
    them without normalizing would report an edit on every rerun and loop forever."""
    plan = readConfig(str(EXAMPLES / "Case_dana.toml"), verbose=False)
    df = plan.timeLists["Dana"]
    rebuilt = pd.concat([df[df["year"] < THISYEAR], df[df["year"] >= THISYEAR]], ignore_index=True)
    assert not df.index.equals(rebuilt.index)  # the permuted index this guards against
    assert not df.equals(rebuilt)
    assert df.reset_index(drop=True).equals(rebuilt)


def test_legacy_workbook_notice_points_at_saving(monkeypatch, tmp_path):
    """A workbook written before "Roth conv fixed" existed still loads: the column is
    filled with zeros and nothing is pinned. The notice must not tell the user to add a
    column that is already sitting in the table -- the way to keep it is to save."""
    import owlplanner as owl

    legacy = tmp_path / "HFP_legacy.xlsx"
    sheets = pd.read_excel(EXAMPLES / "HFP_jack+jill.xlsx", sheet_name=None)
    with pd.ExcelWriter(legacy) as xl:
        for name, df in sheets.items():
            df.drop(columns=["Roth conv fixed"], errors="ignore").to_excel(xl, sheet_name=name, index=False)

    plan = owl.Plan(["Jack", "Jill"], ["1963-01-15", "1966-01-15"], [89, 92], "legacy", verbose=False)
    plan.readHFP(str(legacy))
    assert plan.hfpAbsentCols["Jack"] == ["Roth conv fixed"]
    assert "Roth conv fixed" in plan.timeLists["Jack"].columns
    assert not plan.rothXfixed_in.any()

    at = _render(monkeypatch, plan)
    assert not at.exception, [str(e.message) for e in at.exception]
    notices = [str(w.value) for w in at.warning if "Roth conv fixed" in str(w.value)]
    assert len(notices) == 1, [str(w.value) for w in at.warning]
    text = notices[0]
    assert "added to the tables below" in text
    assert "Download HFP workbook" in text
    assert "Add them to the workbook" not in text


def test_workbook_download_does_not_need_a_solve(monkeypatch, tmp_path):
    """The notice above sends the user to a download, so that download must be reachable
    from an unsolved case. The Reports page copy is gated on caseStatus == "solved",
    which is no help to someone who has just loaded a workbook -- or whose case is
    infeasible. Building it needs only the tables, so this one is ungated."""
    import owlplanner as owl

    legacy = tmp_path / "HFP_legacy.xlsx"
    sheets = pd.read_excel(EXAMPLES / "HFP_jack+jill.xlsx", sheet_name=None)
    with pd.ExcelWriter(legacy) as xl:
        for name, df in sheets.items():
            df.drop(columns=["Roth conv fixed"], errors="ignore").to_excel(xl, sheet_name=name, index=False)

    plan = owl.Plan(["Jack", "Jill"], ["1963-01-15", "1966-01-15"], [89, 92], "legacy", verbose=False)
    plan.readHFP(str(legacy))
    assert plan.caseStatus != "solved"

    at = _render(monkeypatch, plan)
    labels = [b.label for b in at.get("download_button")]
    assert "Download HFP workbook" in labels, labels

    # One workbook holds every table on the page, so it is offered below all of them.
    heads = [str(m.value) for m in at.markdown if str(m.value).startswith("### ")]
    titles = ["Wages and Contributions", "Debts and Fixed Assets", "Save your Financial Profile"]
    assert [i for t in titles for i, h in enumerate(heads) if t in h] == [0, 1, 2], heads

    # And the workbook it would hand over carries the column that was missing.
    buffer = plan.saveContributions()
    assert buffer is not None
    out = tmp_path / "roundtrip.xlsx"
    buffer.save(out)
    assert "Roth conv fixed" in pd.read_excel(out, sheet_name="Jack", nrows=0).columns


def test_condition_time_list_flags_normalizes_and_clears_the_past():
    """The backstop behind the two editors. The data editor hands a flag back as a bool or,
    for a cell nobody touched, as the 0 left by the NaN fill; and a flag on a lead-in row is
    meaningless because those conversions already happened."""
    import owlbridge as owb

    df = pd.DataFrame(
        {
            "year": [THISYEAR - 2, THISYEAR - 1, THISYEAR, THISYEAR + 1],
            "Roth conv": [10_000.0, 0.0, 0.0, 50_000.0],
            "Roth conv fixed": [True, 0, 1, True],
        }
    )
    out = owb.conditionTimeListFlags(df.copy())

    assert out["Roth conv fixed"].dtype == bool
    # Past rows cleared whatever they held; plan rows kept, including the untouched 1.
    assert out["Roth conv fixed"].tolist() == [False, False, True, True]
    # Amounts are never touched by the flag pass.
    assert out["Roth conv"].tolist() == df["Roth conv"].tolist()


def test_condition_time_list_flags_tolerates_a_missing_column():
    """A frame without the flag column passes through untouched rather than raising."""
    import owlbridge as owb

    df = pd.DataFrame({"year": [THISYEAR], "Roth conv": [0.0]})
    out = owb.conditionTimeListFlags(df.copy())
    assert list(out.columns) == ["year", "Roth conv"]
