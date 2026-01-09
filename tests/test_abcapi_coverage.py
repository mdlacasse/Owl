"""
Tests for abcapi.py to improve coverage.

This module tests the abstract API for building constraint matrices,
error handling, and edge cases that are not covered by existing tests.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import pytest
import numpy as np

import owlplanner.abcapi as abc


def test_row_add_elem_out_of_range():
    """Test Row.addElem with out of range index."""
    row = abc.Row(10)
    with pytest.raises(ValueError, match="Index.*out of range"):
        row.addElem(10, 1.0)  # Index 10 is out of range for nvars=10

    with pytest.raises(ValueError, match="Index.*out of range"):
        row.addElem(-1, 1.0)


def test_row_add_elem_dic():
    """Test Row.addElemDic method."""
    row = abc.Row(10)
    row.addElemDic({0: 1.0, 5: 2.0, 9: 3.0})
    assert 0 in row.ind
    assert 5 in row.ind
    assert 9 in row.ind
    assert 1.0 in row.val
    assert 2.0 in row.val
    assert 3.0 in row.val


def test_row_add_elem_dic_none():
    """Test Row.addElemDic with None."""
    row = abc.Row(10)
    row.addElemDic(None)
    assert len(row.ind) == 0
    assert len(row.val) == 0


def test_constraint_matrix_new_row():
    """Test ConstraintMatrix.newRow method."""
    cm = abc.ConstraintMatrix(10)
    row = cm.newRow({0: 1.0, 1: 2.0})
    assert isinstance(row, abc.Row)
    assert row.nvars == 10


def test_constraint_matrix_new_row_none():
    """Test ConstraintMatrix.newRow with None."""
    cm = abc.ConstraintMatrix(10)
    row = cm.newRow(None)
    assert isinstance(row, abc.Row)
    assert len(row.ind) == 0


def test_constraint_matrix_add_row_equality():
    """Test ConstraintMatrix.addRow with equality constraint (lb == ub)."""
    cm = abc.ConstraintMatrix(10)
    row = cm.newRow({0: 1.0})
    cm.addRow(row, 5.0, 5.0)
    assert cm.ncons == 1
    assert cm.key[0] == "fx"


def test_constraint_matrix_add_row_free():
    """Test ConstraintMatrix.addRow with free constraint."""
    cm = abc.ConstraintMatrix(10)
    row = cm.newRow({0: 1.0})
    cm.addRow(row, -np.inf, np.inf)
    assert cm.ncons == 1
    assert cm.key[0] == "fr"


def test_constraint_matrix_add_row_lower_bound():
    """Test ConstraintMatrix.addRow with lower bound only."""
    cm = abc.ConstraintMatrix(10)
    row = cm.newRow({0: 1.0})
    cm.addRow(row, 0.0, np.inf)
    assert cm.ncons == 1
    assert cm.key[0] == "lo"


def test_constraint_matrix_add_row_upper_bound():
    """Test ConstraintMatrix.addRow with upper bound only."""
    cm = abc.ConstraintMatrix(10)
    row = cm.newRow({0: 1.0})
    cm.addRow(row, -np.inf, 10.0)
    assert cm.ncons == 1
    assert cm.key[0] == "up"


def test_constraint_matrix_add_row_range():
    """Test ConstraintMatrix.addRow with range constraint."""
    cm = abc.ConstraintMatrix(10)
    row = cm.newRow({0: 1.0})
    cm.addRow(row, 0.0, 10.0)
    assert cm.ncons == 1
    assert cm.key[0] == "ra"


def test_constraint_matrix_add_new_row():
    """Test ConstraintMatrix.addNewRow method."""
    cm = abc.ConstraintMatrix(10)
    cm.addNewRow({0: 1.0, 1: 2.0}, 0.0, 10.0)
    assert cm.ncons == 1
    assert len(cm.Aind[0]) == 2


def test_constraint_matrix_keys():
    """Test ConstraintMatrix.keys method."""
    cm = abc.ConstraintMatrix(10)
    row1 = cm.newRow({0: 1.0})
    row2 = cm.newRow({1: 1.0})
    cm.addRow(row1, 0.0, np.inf)
    cm.addRow(row2, -np.inf, 10.0)
    keys = cm.keys()
    assert len(keys) == 2
    assert keys[0] == "lo"
    assert keys[1] == "up"


def test_constraint_matrix_lists():
    """Test ConstraintMatrix.lists method."""
    cm = abc.ConstraintMatrix(10)
    row = cm.newRow({0: 1.0, 5: 2.0})
    cm.addRow(row, 0.0, 10.0)
    Aind, Aval, lb, ub = cm.lists()
    assert len(Aind) == 1
    assert len(Aval) == 1
    assert len(lb) == 1
    assert len(ub) == 1
    assert lb[0] == 0.0
    assert ub[0] == 10.0


def test_constraint_matrix_arrays():
    """Test ConstraintMatrix.arrays method."""
    cm = abc.ConstraintMatrix(10)
    row = cm.newRow({0: 1.0, 5: 2.0})
    cm.addRow(row, 0.0, 10.0)
    Alu, lb, ub = cm.arrays()
    assert Alu.shape == (1, 10)
    assert Alu[0, 0] == 1.0
    assert Alu[0, 5] == 2.0
    assert lb[0] == 0.0
    assert ub[0] == 10.0


def test_bounds_set_binary_out_of_range():
    """Test Bounds.setBinary with out of range index."""
    bounds = abc.Bounds(10, 2)
    with pytest.raises(ValueError, match="Index.*out of range"):
        bounds.setBinary(10)

    with pytest.raises(ValueError, match="Index.*out of range"):
        bounds.setBinary(-1)


def test_bounds_set_range_out_of_range():
    """Test Bounds.setRange with out of range index."""
    bounds = abc.Bounds(10, 2)
    with pytest.raises(ValueError, match="Index.*out of range"):
        bounds.setRange(10, 0.0, 1.0)

    with pytest.raises(ValueError, match="Index.*out of range"):
        bounds.setRange(-1, 0.0, 1.0)


def test_bounds_set_range_invalid_bounds():
    """Test Bounds.setRange with lb > ub."""
    bounds = abc.Bounds(10, 2)
    with pytest.raises(ValueError, match="Lower bound.*> upper bound"):
        bounds.setRange(0, 10.0, 5.0)


def test_bounds_set_range_equality():
    """Test Bounds.setRange with equality (lb == ub)."""
    bounds = abc.Bounds(10, 2)
    bounds.setRange(0, 5.0, 5.0)
    assert bounds.key[-1] == "fx"


def test_bounds_set_range_free():
    """Test Bounds.setRange with free bounds."""
    bounds = abc.Bounds(10, 2)
    bounds.setRange(0, -np.inf, np.inf)
    assert bounds.key[-1] == "fr"


def test_bounds_set_range_lower_bound():
    """Test Bounds.setRange with lower bound only."""
    bounds = abc.Bounds(10, 2)
    bounds.setRange(0, 0.0, np.inf)
    assert bounds.key[-1] == "lo"


def test_bounds_set_range_upper_bound():
    """Test Bounds.setRange with upper bound only."""
    bounds = abc.Bounds(10, 2)
    bounds.setRange(0, -np.inf, 10.0)
    assert bounds.key[-1] == "up"


def test_bounds_set_range_range():
    """Test Bounds.setRange with range bounds."""
    bounds = abc.Bounds(10, 2)
    bounds.setRange(0, 0.0, 10.0)
    assert bounds.key[-1] == "ra"


def test_bounds_keys():
    """Test Bounds.keys method."""
    bounds = abc.Bounds(10, 2)
    bounds.setRange(0, 0.0, 10.0)
    bounds.setRange(1, -np.inf, 5.0)
    keys = bounds.keys()
    assert len(keys) == 10
    assert keys[0] == "ra"
    assert keys[1] == "up"
    # Last 2 should be binary (ra)
    assert keys[8] == "ra"
    assert keys[9] == "ra"


def test_bounds_arrays():
    """Test Bounds.arrays method."""
    bounds = abc.Bounds(10, 2)
    bounds.setRange(0, 0.0, 10.0)
    bounds.setRange(1, 5.0, 15.0)
    lb, ub = bounds.arrays()
    assert len(lb) == 10
    assert len(ub) == 10
    assert lb[0] == 0.0
    assert ub[0] == 10.0
    assert lb[1] == 5.0
    assert ub[1] == 15.0
    # Unset bounds should have defaults
    assert ub[2] == np.inf


def test_bounds_integrality_array():
    """Test Bounds.integralityArray method."""
    bounds = abc.Bounds(10, 2)
    bounds.setBinary(3)  # Add another binary
    integrality = bounds.integralityArray()
    assert len(integrality) == 10
    assert integrality[8] == 1  # Last 2 are binary by default
    assert integrality[9] == 1
    assert integrality[3] == 1  # The one we added
    assert integrality[0] == 0  # Non-binary


def test_bounds_integrality_list():
    """Test Bounds.integralityList method."""
    bounds = abc.Bounds(10, 2)
    bounds.setBinary(3)  # Add another binary
    integrality_list = bounds.integralityList()
    assert 8 in integrality_list
    assert 9 in integrality_list
    assert 3 in integrality_list
    assert len(integrality_list) == 3


def test_objective_set_elem_out_of_range():
    """Test Objective.setElem with out of range index."""
    obj = abc.Objective(10)
    with pytest.raises(ValueError, match="Index.*out of range"):
        obj.setElem(10, 1.0)

    with pytest.raises(ValueError, match="Index.*out of range"):
        obj.setElem(-1, 1.0)


def test_objective_arrays():
    """Test Objective.arrays method."""
    obj = abc.Objective(10)
    obj.setElem(0, 1.0)
    obj.setElem(5, 2.0)
    obj.setElem(9, 3.0)
    c = obj.arrays()
    assert len(c) == 10
    assert c[0] == 1.0
    assert c[5] == 2.0
    assert c[9] == 3.0
    assert c[1] == 0.0  # Unset should be zero


def test_objective_lists():
    """Test Objective.lists method."""
    obj = abc.Objective(10)
    obj.setElem(0, 1.0)
    obj.setElem(5, 2.0)
    ind, val = obj.lists()
    assert len(ind) == 2
    assert len(val) == 2
    assert 0 in ind
    assert 5 in ind
    assert 1.0 in val
    assert 2.0 in val
