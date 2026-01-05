"""
Tests for summary comparison functionality in UI.

Tests verify that summary dataframes can be compared correctly
across different cases in the Streamlit UI.

Copyright (C) 2025-2026 The Owlplanner Authors

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

import pandas as pd
import ui.sskeys as sskeys


def test_compareSummaries(monkeypatch):
    # Setup mock session state and cases
    df1 = pd.DataFrame({'A': ['$100'], 'B': ['$200']})
    df2 = pd.DataFrame({'A': ['$110'], 'B': ['$190']})
    cases = {
        "case1": {"summaryDf": df1},
        "case2": {"summaryDf": df2},
    }
    monkeypatch.setattr(sskeys, "getCaseKey", lambda key: df1 if key == "summaryDf" else None)
    monkeypatch.setattr(sskeys, "onlyCaseNames", lambda: ["case2"])
    monkeypatch.setattr(sskeys, "currentCaseName", lambda: "case1")
    sskeys.ss = type("SS", (), {"cases": cases})()
    result = sskeys.compareSummaries()
    assert result is not None
