"""
Unit tests for owlplanner.cli.set_override.apply_overrides.

Copyright (C) 2025-2026 The Owl Authors
"""

import pytest
from owlplanner.cli.set_override import apply_overrides


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base():
    return {
        "basic_info": {"state": "TX", "name": "test"},
        "rates_selection": {"method": "historical", "from": 1969},
        "solver_options": {"bequest": 0.0, "withMedicare": "loop"},
    }


# ---------------------------------------------------------------------------
# Happy-path parsing
# ---------------------------------------------------------------------------

def test_string_value():
    result = apply_overrides(_base(), ["basic_info.state=CA"])
    assert result["basic_info"]["state"] == "CA"


def test_integer_value():
    result = apply_overrides(_base(), ["rates_selection.from=2000"])
    assert result["rates_selection"]["from"] == 2000
    assert isinstance(result["rates_selection"]["from"], int)


def test_float_value():
    result = apply_overrides(_base(), ["solver_options.bequest=500.5"])
    assert result["solver_options"]["bequest"] == pytest.approx(500.5)
    assert isinstance(result["solver_options"]["bequest"], float)


def test_bool_true():
    result = apply_overrides(_base(), ["solver_options.withMedicare=true"])
    assert result["solver_options"]["withMedicare"] is True


def test_bool_false():
    result = apply_overrides(_base(), ["solver_options.withMedicare=false"])
    assert result["solver_options"]["withMedicare"] is False


def test_json_array():
    result = apply_overrides(_base(), ["rates_selection.values=[7.0,4.5,3.5,2.5]"])
    assert result["rates_selection"]["values"] == [7.0, 4.5, 3.5, 2.5]


def test_json_string_fallback():
    result = apply_overrides(_base(), ["basic_info.state=MN"])
    assert result["basic_info"]["state"] == "MN"
    assert isinstance(result["basic_info"]["state"], str)


def test_string_with_spaces_via_fallback():
    result = apply_overrides(_base(), ["basic_info.name=alice and bob"])
    assert result["basic_info"]["name"] == "alice and bob"


# ---------------------------------------------------------------------------
# Path creation
# ---------------------------------------------------------------------------

def test_creates_new_top_level_section():
    result = apply_overrides(_base(), ["new_section.key=hello"])
    assert result["new_section"]["key"] == "hello"


def test_creates_deeply_nested_path():
    result = apply_overrides(_base(), ["a.b.c.d=99"])
    assert result["a"]["b"]["c"]["d"] == 99


def test_adds_key_to_existing_section():
    result = apply_overrides(_base(), ["solver_options.gap=1e-4"])
    assert result["solver_options"]["gap"] == pytest.approx(1e-4)


# ---------------------------------------------------------------------------
# Multiple overrides
# ---------------------------------------------------------------------------

def test_multiple_overrides_all_applied():
    result = apply_overrides(_base(), [
        "basic_info.state=MN",
        "solver_options.bequest=300",
        "rates_selection.method=conservative",
    ])
    assert result["basic_info"]["state"] == "MN"
    assert result["solver_options"]["bequest"] == 300
    assert result["rates_selection"]["method"] == "conservative"


def test_later_override_wins():
    result = apply_overrides(_base(), [
        "basic_info.state=CA",
        "basic_info.state=OR",
    ])
    assert result["basic_info"]["state"] == "OR"


# ---------------------------------------------------------------------------
# Original dict is not mutated
# ---------------------------------------------------------------------------

def test_original_not_mutated():
    original = _base()
    apply_overrides(original, ["basic_info.state=CA"])
    assert original["basic_info"]["state"] == "TX"


def test_returns_new_dict():
    original = _base()
    result = apply_overrides(original, ["basic_info.state=CA"])
    assert result is not original


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_no_equals_raises():
    with pytest.raises((ValueError, Exception)):
        apply_overrides(_base(), ["basic_info.state"])


def test_empty_key_raises():
    with pytest.raises((ValueError, Exception)):
        apply_overrides(_base(), ["=value"])
