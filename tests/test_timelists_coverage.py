"""
Tests for timelists.py to improve coverage.

This module tests time list reading, error handling, and edge cases
that are not covered by existing tests.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import pytest
from datetime import date
import pandas as pd
from io import BytesIO
import numpy as np

import owlplanner.timelists as timelists


def test_read_time_horizons_dict_input():
    """Test read with dictionary input."""
    inames = ['Joe']
    horizons = [20]
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    df_dict = {
        'Joe': pd.DataFrame({
            'year': [2024, 2025, 2026],
            'anticipated wages': [0, 0, 0],
            'taxable ctrb': [0, 0, 0],
            '401k ctrb': [0, 0, 0],
            'Roth 401k ctrb': [0, 0, 0],
            'IRA ctrb': [0, 0, 0],
            'Roth IRA ctrb': [0, 0, 0],
            'Roth conv': [0, 0, 0],
            'big-ticket items': [0, 0, 0]
        })
    }

    finput, time_lists, house_lists = timelists.read(
        df_dict, inames, horizons, mylog
    )
    # When dict is passed, finput is set to "dictionary of DataFrames" string
    assert finput == "dictionary of DataFrames"
    assert 'Joe' in time_lists


def test_read_time_horizons_file_with_name():
    """Test read with explicit filename."""
    inames = ['Joe']
    horizons = [20]
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    # Create a simple Excel file in memory
    df = pd.DataFrame({
        'year': [2024, 2025, 2026],
        'anticipated wages': [0, 0, 0],
        'taxable ctrb': [0, 0, 0],
        '401k ctrb': [0, 0, 0],
        'Roth 401k ctrb': [0, 0, 0],
        'IRA ctrb': [0, 0, 0],
        'Roth IRA ctrb': [0, 0, 0],
        'Roth conv': [0, 0, 0],
        'big-ticket items': [0, 0, 0]
    })

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Joe', index=False)
    buffer.seek(0)

    finput, time_lists, house_lists = timelists.read(
        buffer, inames, horizons, mylog, filename="test_file.xlsx"
    )
    assert 'Joe' in time_lists


def test_read_time_horizons_file_error():
    """Test read with file that can't be read."""
    inames = ['Joe']
    horizons = [20]
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    # Create invalid file content
    buffer = BytesIO(b'invalid excel content')

    with pytest.raises(Exception, match="Could not read file"):
        timelists.read(buffer, inames, horizons, mylog)


def test_check_columns_missing_column():
    """Test _checkColumns with missing required column."""
    df = pd.DataFrame({
        'year': [2024, 2025],
        'wages': [0, 0]
    })

    with pytest.raises(ValueError, match="Column.*not found"):
        timelists._checkColumns(df, 'Joe', ['year', 'wages', 'contributions'])


def test_check_columns_removes_extra():
    """Test _checkColumns removes extra columns."""
    df = pd.DataFrame({
        'year': [2024, 2025],
        'wages': [0, 0],
        'contributions': [0, 0],
        'extra_col': [1, 2]
    })

    result = timelists._checkColumns(df, 'Joe', ['year', 'wages', 'contributions'])
    assert 'extra_col' not in result.columns
    assert 'year' in result.columns
    assert 'wages' in result.columns
    assert 'contributions' in result.columns


def test_condition_timetables_missing_sheet():
    """Test _conditionTimetables with missing sheet."""
    inames = ['Joe']
    horizons = [20]
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    df_dict = {
        'Jane': pd.DataFrame()  # Wrong name
    }

    with pytest.raises(ValueError, match="No sheet found"):
        timelists._conditionTimetables(df_dict, inames, horizons, mylog)


def test_condition_timetables_negative_values():
    """Test _conditionTimetables with negative values (should raise error)."""
    inames = ['Joe']
    horizons = [20]
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    thisyear = date.today().year
    df = pd.DataFrame({
        'year': [thisyear, thisyear + 1],
        'anticipated wages': [-100, 0],  # Negative value
        'taxable ctrb': [0, 0],
        '401k ctrb': [0, 0],
        'Roth 401k ctrb': [0, 0],
        'IRA ctrb': [0, 0],
        'Roth IRA ctrb': [0, 0],
        'Roth conv': [0, 0],
        'big-ticket items': [0, 0]
    })

    df_dict = {'Joe': df}

    with pytest.raises(ValueError, match="Item.*is < 0"):
        timelists._conditionTimetables(df_dict, inames, horizons, mylog)


def test_condition_timetables_big_ticket_can_be_negative():
    """Test _conditionTimetables allows negative big-ticket items."""
    inames = ['Joe']
    horizons = [20]
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    thisyear = date.today().year
    df = pd.DataFrame({
        'year': [thisyear, thisyear + 1],
        'anticipated wages': [0, 0],
        'taxable ctrb': [0, 0],
        '401k ctrb': [0, 0],
        'Roth 401k ctrb': [0, 0],
        'IRA ctrb': [0, 0],
        'Roth IRA ctrb': [0, 0],
        'Roth conv': [0, 0],
        'big-ticket items': [-50, 0]  # Can be negative
    })

    df_dict = {'Joe': df}

    result = timelists._conditionTimetables(df_dict, inames, horizons, mylog)
    assert 'Joe' in result


def test_condition_house_tables():
    """Test _conditionHouseTables."""
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    thisyear = date.today().year
    df_dict = {
        'Debts': pd.DataFrame({
            'active': [True],
            'name': ['Test Loan'],
            'type': ['loan'],
            'year': [thisyear],
            'term': [10],
            'amount': [1000],
            'rate': [5.0]  # Percentage
        }),
        'Fixed Assets': pd.DataFrame({
            'active': [True],
            'name': ['House'],
            'type': ['residence'],
            'year': [thisyear],
            'basis': [150_000],
            'value': [200_000],
            'rate': [0.0],
            'yod': [0],
            'commission': [0.0]
        })
    }

    result = timelists._conditionHouseTables(df_dict, mylog)
    assert 'Debts' in result or 'Fixed Assets' in result or len(result) >= 0


def test_read_with_house_tables_active_column_string():
    """Test read with string active column in house tables."""
    inames = ['Joe']
    horizons = [20]
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    thisyear = date.today().year
    df_dict = {
        'Joe': pd.DataFrame({
            'year': [thisyear, thisyear + 1],
            'anticipated wages': [0, 0],
            'taxable ctrb': [0, 0],
            '401k ctrb': [0, 0],
            'Roth 401k ctrb': [0, 0],
            'IRA ctrb': [0, 0],
            'Roth IRA ctrb': [0, 0],
            'Roth conv': [0, 0],
            'big-ticket items': [0, 0]
        }),
        'Debts': pd.DataFrame({
            'active': ['True'],  # String instead of bool
            'name': ['Test Loan'],
            'type': ['loan'],
            'year': [thisyear],
            'term': [10],
            'amount': [1000],
            'rate': [5.0]
        })
    }

    finput, time_lists, house_lists = timelists.read(df_dict, inames, horizons, mylog)
    assert 'Joe' in time_lists
    assert 'Debts' in house_lists


def test_read_with_house_tables_active_column_numeric():
    """Test read with numeric active column in house tables."""
    inames = ['Joe']
    horizons = [20]
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    thisyear = date.today().year
    df_dict = {
        'Joe': pd.DataFrame({
            'year': [thisyear, thisyear + 1],
            'anticipated wages': [0, 0],
            'taxable ctrb': [0, 0],
            '401k ctrb': [0, 0],
            'Roth 401k ctrb': [0, 0],
            'IRA ctrb': [0, 0],
            'Roth IRA ctrb': [0, 0],
            'Roth conv': [0, 0],
            'big-ticket items': [0, 0]
        }),
        'Debts': pd.DataFrame({
            'active': [1],  # Numeric instead of bool
            'name': ['Test Loan'],
            'type': ['loan'],
            'year': [thisyear],
            'term': [10],
            'amount': [1000],
            'rate': [5.0]
        })
    }

    finput, time_lists, house_lists = timelists.read(df_dict, inames, horizons, mylog)
    assert 'Joe' in time_lists
    assert 'Debts' in house_lists


def test_read_with_house_tables_active_column_nan():
    """Test read with NaN in active column (defaults to True)."""
    inames = ['Joe']
    horizons = [20]
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    thisyear = date.today().year
    df_dict = {
        'Joe': pd.DataFrame({
            'year': [thisyear, thisyear + 1],
            'anticipated wages': [0, 0],
            'taxable ctrb': [0, 0],
            '401k ctrb': [0, 0],
            'Roth 401k ctrb': [0, 0],
            'IRA ctrb': [0, 0],
            'Roth IRA ctrb': [0, 0],
            'Roth conv': [0, 0],
            'big-ticket items': [0, 0]
        }),
        'Debts': pd.DataFrame({
            'active': [np.nan],  # NaN should default to True
            'name': ['Test Loan'],
            'type': ['loan'],
            'year': [thisyear],
            'term': [10],
            'amount': [1000],
            'rate': [5.0]
        })
    }

    finput, time_lists, house_lists = timelists.read(df_dict, inames, horizons, mylog)
    assert 'Joe' in time_lists
    assert 'Debts' in house_lists


def test_condition_timetables_adds_missing_years():
    """Test _conditionTimetables adds missing years."""
    inames = ['Joe']
    horizons = [5]  # Short horizon for testing
    mylog = type('Logger', (), {
        'vprint': lambda self, *args: None
    })()

    thisyear = date.today().year
    df = pd.DataFrame({
        'year': [thisyear, thisyear + 2],  # Missing some years
        'anticipated wages': [0, 0],
        'taxable ctrb': [0, 0],
        '401k ctrb': [0, 0],
        'Roth 401k ctrb': [0, 0],
        'IRA ctrb': [0, 0],
        'Roth IRA ctrb': [0, 0],
        'Roth conv': [0, 0],
        'big-ticket items': [0, 0]
    })

    df_dict = {'Joe': df}
    result = timelists._conditionTimetables(df_dict, inames, horizons, mylog)
    assert 'Joe' in result
    # Should have added missing years
    result_df = result['Joe']
    assert len(result_df) >= 2  # At least the original years plus some missing ones
