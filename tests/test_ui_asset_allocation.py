"""
Tests for ui.Asset_Allocation module - asset allocation validation.

Tests verify that asset allocation percentages are correctly validated
and sum to 100% as required.

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

import ui.Asset_Allocation as aa


def test_checkAccountAllocs_valid(monkeypatch):
    # Mock kz.getKey to return 25 for each call (4*25=100)
    monkeypatch.setattr(aa.kz, "getCaseKey", lambda key: 25)
    assert aa.checkAccountAllocs(0, "") is True


def test_checkAccountAllocs_invalid(monkeypatch):
    # Mock kz.getCaseKey to return 20 for each call (4*20=80)
    monkeypatch.setattr(aa.kz, "getCaseKey", lambda key: 20)
    # Should trigger error and return False
    assert aa.checkAccountAllocs(0, "") is False
