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
    monkeypatch.setattr(sskeys, "getKey", lambda key: df1 if key == "summaryDf" else None)
    monkeypatch.setattr(sskeys, "onlyCaseNames", lambda: ["case2"])
    monkeypatch.setattr(sskeys, "currentCaseName", lambda: "case1")
    sskeys.ss = type("SS", (), {"cases": cases})()
    result = sskeys.compareSummaries()
    assert result is not None
