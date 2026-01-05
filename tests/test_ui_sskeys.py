"""
Tests for ui.sskeys module - Streamlit session state key management.

Tests verify functions for managing keys and data in Streamlit's
session state for the UI components.

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
