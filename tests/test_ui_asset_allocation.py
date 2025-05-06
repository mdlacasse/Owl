import ui.Asset_Allocation as aa


def test_checkAccountAllocs_valid(monkeypatch):
    # Mock kz.getKey to return 25 for each call (4*25=100)
    monkeypatch.setattr(aa.kz, "getKey", lambda key: 25)
    assert aa.checkAccountAllocs(0, "") is True


def test_checkAccountAllocs_invalid(monkeypatch):
    # Mock kz.getKey to return 20 for each call (4*20=80)
    monkeypatch.setattr(aa.kz, "getKey", lambda key: 20)
    # Should trigger error and return False
    assert aa.checkAccountAllocs(0, "") is False
