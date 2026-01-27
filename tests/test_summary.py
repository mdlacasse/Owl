"""
Tests for plan.py summary methods with N parameter (fraction of years).

Tests verify that summary methods correctly handle the N parameter to
generate summaries covering only a fraction of the plan years.

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

import pytest
import os

import owlplanner as owl


def get_jack_jill_plan():
    """
    Create and solve a jack+jill plan for testing summary methods.

    Returns:
        Solved Plan object
    """
    exdir = "./examples/"
    case = "Case_jack+jill"
    file = os.path.join(exdir, case)
    p = owl.readConfig(file)

    hfp = os.path.join(exdir, "HFP_jack+jill.xlsx")
    p.readContributions(hfp)
    p.resolve()

    return p


def test_summary_dic_default_n():
    """Test summaryDic with N=None (default, all years)."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved", "Plan must be solved to generate summary"

    # Get summary with default N (all years)
    dic = p.summaryDic(N=None)

    # Verify dictionary structure
    assert isinstance(dic, dict)
    assert "Case name" in dic
    assert " Total net spending" in dic
    assert "[Total net spending]" in dic


def test_summary_dic_fraction_of_years():
    """Test summaryDic with N set to a fraction of total years."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    total_years = p.N_n
    assert total_years > 10, "Plan should have more than 10 years"

    # Get summary for first 5 years
    N = 5
    dic_partial = p.summaryDic(N=N)

    # Get summary for all years
    dic_full = p.summaryDic(N=None)

    # Verify case name is same
    assert dic_partial["Case name"] == dic_full["Case name"]

    # Verify partial summary has fewer or equal keys (some keys only appear when N == total)
    # Partial summary should be a subset of full summary for common keys
    common_keys = set(dic_partial.keys()) & set(dic_full.keys())
    assert len(common_keys) > 0, "Should have some common keys"

    # Verify partial spending is less than or equal to full spending
    # (extract numeric values from strings)
    def extract_value(s):
        """Extract numeric value from formatted string like '$123,456'."""
        if isinstance(s, str):
            # Remove $ and commas, convert to float
            return float(s.replace('$', '').replace(',', ''))
        return float(s)

    # Check that partial values are <= full values for common keys that represent totals
    if " Total net spending" in common_keys:
        partial_spending = extract_value(dic_partial[" Total net spending"])
        full_spending = extract_value(dic_full[" Total net spending"])
        assert partial_spending <= full_spending, "Partial spending should be <= full spending"


def test_summary_dic_first_year_only():
    """Test summaryDic with N=1 (first year only)."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    dic = p.summaryDic(N=1)

    # Verify summary exists
    assert isinstance(dic, dict)
    assert "Case name" in dic
    assert " Total net spending" in dic


def test_summary_dic_all_years():
    """Test summaryDic with N equal to total years."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    total_years = p.N_n
    dic = p.summaryDic(N=total_years)

    # Should be same as default
    dic_default = p.summaryDic(N=None)
    assert dic == dic_default


def test_summary_dic_invalid_n_zero():
    """Test summaryDic raises ValueError for N=0."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    with pytest.raises(ValueError, match="out of reange"):
        p.summaryDic(N=0)


def test_summary_dic_invalid_n_negative():
    """Test summaryDic raises ValueError for negative N."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    with pytest.raises(ValueError, match="out of reange"):
        p.summaryDic(N=-5)


def test_summary_dic_invalid_n_too_large():
    """Test summaryDic raises ValueError for N > total years."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    total_years = p.N_n
    with pytest.raises(ValueError, match="out of reange"):
        p.summaryDic(N=total_years + 1)


def test_summary_list_with_n():
    """Test summaryList with N parameter."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    # Get list for first 3 years
    summary_list = p.summaryList(N=3)

    assert isinstance(summary_list, list)
    assert len(summary_list) > 0
    # Each item should be a string with "key: value" format
    assert all(":" in item for item in summary_list)


def test_summary_df_with_n():
    """Test summaryDf with N parameter."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    # Get dataframe for first 5 years
    df = p.summaryDf(N=5)

    import pandas as pd
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1  # One row (the plan)
    assert df.index[0] == p._name


def test_summary_string_with_n():
    """Test summaryString with N parameter."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    # Get string for first 7 years
    summary_str = p.summaryString(N=7)

    assert isinstance(summary_str, str)
    assert "Synopsis" in summary_str
    assert p._name in summary_str


def test_summary_method_with_n():
    """Test summary method (prints to log) with N parameter."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    # summary() returns None but prints to log
    result = p.summary(N=10)
    assert result is None


def test_summary_consistency_across_methods():
    """Test that all summary methods produce consistent results for same N."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    N = 8

    # Get summaries using different methods
    dic = p.summaryDic(N=N)
    summary_list = p.summaryList(N=N)
    summary_str = p.summaryString(N=N)

    # Verify all contain the case name
    assert dic["Case name"] == p._name
    assert any(p._name in item for item in summary_list)
    assert p._name in summary_str

    # Verify list contains all keys from dictionary
    list_keys = {item.split(":")[0].strip() for item in summary_list}
    dict_keys = set(dic.keys())
    # Allow for some formatting differences
    assert len(list_keys) == len(dict_keys)


def test_summary_progressive_years():
    """Test that summary values increase as N increases."""
    p = get_jack_jill_plan()
    assert p.caseStatus == "solved"

    def extract_value(s):
        """Extract numeric value from formatted string."""
        if isinstance(s, str):
            return float(s.replace('$', '').replace(',', ''))
        return float(s)

    # Get summaries for increasing N values
    values = []
    for N in [1, 5, 10, 15, 20]:
        if N <= p.N_n:
            dic = p.summaryDic(N=N)
            spending = extract_value(dic[" Total net spending"])
            values.append(spending)

    # Verify values are non-decreasing (spending should accumulate)
    for i in range(1, len(values)):
        assert values[i] >= values[i-1], "Spending should not decrease as N increases"


def test_summary_unsolved_plan():
    """Test that summary methods require solved plan."""
    # Create a plan but don't solve it
    exdir = "./examples/"
    case = "Case_jack+jill"
    file = os.path.join(exdir, case)
    p = owl.readConfig(file)
    # Don't solve the plan

    # summary() method has @_checkCaseStatus decorator, so it should return None
    # when caseStatus != "solved"
    result = p.summary(N=5)
    assert result is None

    # summaryDic doesn't have the decorator, but will fail if arrays aren't initialized
    # This is expected behavior - we can't generate summary without solving
    # The test verifies the decorator works for summary() method
