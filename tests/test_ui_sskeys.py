
import ui.sskeys as sskeys


def test_getIndex_found():
    choices = ['a', 'b', 'c']
    assert sskeys.getIndex('b', choices) == 1


def test_getIndex_not_found():
    choices = ['a', 'b', 'c']
    assert sskeys.getIndex('z', choices) is None


def test_caseHasNoPlan(monkeypatch):
    # Mock getKey to return None
    monkeypatch.setattr(sskeys, "getCaseKey", lambda key: None)
    assert sskeys.caseHasNoPlan() is True


def test_caseHasPlan(monkeypatch):
    # Mock getKey to return a non-None value
    monkeypatch.setattr(sskeys, "getCaseKey", lambda key: "something")
    assert sskeys.caseHasNoPlan() is False
