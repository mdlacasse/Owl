"""
Tests for worksheet display helpers (ages, zero-column drop).

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import pandas as pd

from owlplanner.utils import age_on_dec_31, drop_all_zero_numeric_columns, worksheet_age_on_dec_31_or_blank


def test_age_on_dec_31_birthday_before_year_end():
    assert age_on_dec_31(2020, 1965, 6, 15) == 55


def test_age_on_dec_31_birthday_on_dec_31():
    assert age_on_dec_31(2020, 1965, 12, 31) == 55


def test_age_on_dec_31_birthday_after_dec_31_impossible():
    """December 31 reference date: birthday in same calendar year always precedes ref."""
    assert age_on_dec_31(2020, 1965, 1, 1) == 55


def test_drop_all_zero_numeric_columns_removes_zeros():
    df = pd.DataFrame({"year": [2020, 2021], "a": [0.0, 0.0], "b": [1.0, 2.0]})
    out = drop_all_zero_numeric_columns(df, protected={"year"})
    assert list(out.columns) == ["year", "b"]


def test_drop_all_zero_numeric_columns_respects_protected():
    df = pd.DataFrame({"year": [0, 0], "z": [0.0, 0.0]})
    out = drop_all_zero_numeric_columns(df, protected={"year", "z"})
    assert list(out.columns) == ["year", "z"]


def test_drop_all_zero_numeric_columns_skips_non_numeric():
    df = pd.DataFrame({"year": [2020], "label": ["x"]})
    out = drop_all_zero_numeric_columns(df, protected={"year"})
    assert "label" in out.columns


def test_drop_all_zero_numeric_columns_within_tol():
    df = pd.DataFrame({"year": [2020], "tiny": [1e-12]})
    out = drop_all_zero_numeric_columns(df, protected={"year"}, tol=1e-9)
    assert "tiny" not in out.columns


def test_worksheet_age_blank_after_horizon():
    assert worksheet_age_on_dec_31_or_blank(2020, 1965, 6, 15, last_alive_calendar_year=2019) is None


def test_worksheet_age_in_horizon():
    assert worksheet_age_on_dec_31_or_blank(2020, 1965, 6, 15, last_alive_calendar_year=2020) == 55
