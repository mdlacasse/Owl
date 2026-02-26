"""
Unit tests for src/owlplanner/varmap.py (VarBlock / VarMap).
"""
import numpy as np
import pytest
from owlplanner.varmap import VarBlock, VarMap


# ---------------------------------------------------------------------------
# VarBlock tests
# ---------------------------------------------------------------------------


class TestVarBlock:
    def test_1d_idx(self):
        blk = VarBlock("e", 10, (5,))
        assert blk.idx(0) == 10
        assert blk.idx(3) == 13
        assert blk.idx(4) == 14

    def test_2d_idx(self):
        # shape (3, 4) starting at offset 0
        blk = VarBlock("f", 0, (3, 4))
        assert blk.idx(0, 0) == 0
        assert blk.idx(0, 3) == 3
        assert blk.idx(1, 0) == 4
        assert blk.idx(2, 3) == 11

    def test_3d_idx(self):
        # shape (2, 3, 4) starting at offset 5
        blk = VarBlock("b", 5, (2, 3, 4))
        assert blk.idx(0, 0, 0) == 5
        assert blk.idx(0, 0, 3) == 8
        assert blk.idx(0, 1, 0) == 9
        assert blk.idx(1, 0, 0) == 5 + 12
        assert blk.idx(1, 2, 3) == 5 + 23

    def test_end_property(self):
        blk = VarBlock("x", 7, (3, 4))
        assert blk.end == 7 + 12
        assert blk.size == 12

    def test_extract_1d(self):
        blk = VarBlock("e", 2, (4,))
        x = np.arange(10, dtype=float)
        arr = blk.extract(x)
        np.testing.assert_array_equal(arr, [2.0, 3.0, 4.0, 5.0])
        assert arr.shape == (4,)

    def test_extract_2d(self):
        blk = VarBlock("f", 0, (2, 3))
        x = np.arange(6, dtype=float)
        arr = blk.extract(x)
        np.testing.assert_array_equal(arr, [[0, 1, 2], [3, 4, 5]])
        assert arr.shape == (2, 3)

    def test_extract_3d(self):
        blk = VarBlock("b", 1, (2, 2, 3))
        x = np.arange(20, dtype=float)
        arr = blk.extract(x)
        assert arr.shape == (2, 2, 3)
        assert arr[0, 0, 0] == 1.0
        assert arr[1, 1, 2] == 1 + 2 * 2 * 3 - 1  # last element

    def test_wrong_number_of_indices_raises(self):
        blk = VarBlock("w", 0, (2, 3, 4))
        with pytest.raises(IndexError, match="expected 3 index"):
            blk.idx(0, 1)  # only 2 args for 3-dim block

    def test_repr(self):
        blk = VarBlock("g", 42, (5,))
        r = repr(blk)
        assert "g" in r
        assert "42" in r

    def test_4d_via_varmap(self):
        """VarBlock correctly handles 4-dimensional shape via VarMap.add."""
        vm = VarMap()
        vm.add("a", 2, 3, 4, 5)
        blk = vm["a"]
        assert blk.size == 2 * 3 * 4 * 5
        # Row-major: last index fastest
        assert blk.idx(0, 0, 0, 0) == 0
        assert blk.idx(0, 0, 0, 4) == 4
        assert blk.idx(0, 0, 1, 0) == 5
        assert blk.idx(1, 0, 0, 0) == 3 * 4 * 5


# ---------------------------------------------------------------------------
# VarMap tests
# ---------------------------------------------------------------------------


class TestVarMap:
    def test_add_advances_cursor(self):
        vm = VarMap()
        vm.add("b", 2, 3, 5)   # 30 vars
        vm.add("d", 2, 4)      # 8 vars
        assert vm["b"].start == 0
        assert vm["d"].start == 30
        assert vm.nvars == 38

    def test_add_if_true(self):
        vm = VarMap()
        vm.add("a", 3)
        blk = vm.add_if(True, "h", 4, 5)
        assert blk is not None
        assert blk.start == 3
        assert vm["h"].size == 20
        assert vm.nvars == 23

    def test_add_if_false_returns_none(self):
        vm = VarMap()
        vm.add("a", 3)
        result = vm.add_if(False, "h", 4, 5)
        assert result is None
        assert "h" not in vm
        assert vm.nvars == 3

    def test_contains(self):
        vm = VarMap()
        vm.add("g", 5)
        assert "g" in vm
        assert "missing" not in vm

    def test_mark_binary_start(self):
        vm = VarMap()
        vm.add("e", 4)
        vm.add("g", 3)
        vm.mark_binary_start()
        vm.add("zx", 3, 2)
        assert vm.nconts == 7
        assert vm.nbins == 6
        assert vm.nvars == 13

    def test_nbins_before_mark_is_zero(self):
        vm = VarMap()
        vm.add("e", 4)
        # mark_binary_start not yet called → all vars counted as continuous
        assert vm.nbins == 0
        assert vm.nconts == 4

    def test_nbals(self):
        vm = VarMap()
        vm.add("b", 2, 3, 6)  # N_n+1 = 6
        assert vm.nbals == 2 * 3 * 6

    def test_getitem_missing_raises(self):
        vm = VarMap()
        with pytest.raises(KeyError, match="no block named 'x'"):
            _ = vm["x"]

    def test_add_if_false_no_cursor_advance(self):
        """add_if(False) must not advance the cursor."""
        vm = VarMap()
        vm.add("a", 5)
        vm.add_if(False, "opt", 10)
        vm.add("b", 3)
        assert vm["b"].start == 5   # cursor did not advance when cond=False
        assert vm.nvars == 8

    def test_add_if_true_cursor_advances(self):
        """add_if(True) must advance cursor by block size."""
        vm = VarMap()
        vm.add("a", 5)
        vm.add_if(True, "opt", 10)
        vm.add("b", 3)
        assert vm["b"].start == 15
        assert vm.nvars == 18

    def test_extract_correctness(self):
        """VarMap.extract produces correctly shaped arrays from x."""
        vm = VarMap()
        vm.add("b", 2, 3, 4)  # 24 vars, shape (2,3,4)
        vm.add("g", 4)         # 4 vars, shape (4,)
        x = np.arange(vm.nvars, dtype=float)
        b = vm["b"].extract(x)
        g = vm["g"].extract(x)
        assert b.shape == (2, 3, 4)
        assert g.shape == (4,)
        assert b[0, 0, 0] == 0.0
        assert g[0] == 24.0

    def test_conditional_blocks_shift_correctly(self):
        """Simulates medi=False, ss_lp=True: h absent, plo/phi/q/tss present."""
        vm = VarMap()
        vm.add("b", 1, 3, 4)    # 12
        vm.add("d", 1, 3)       # 3
        vm.add("e", 3)          # 3
        vm.add("f", 2, 3)       # 6
        vm.add("g", 3)          # 3   → cursor=27
        medi = False
        ss_lp = True
        Nmed = 2
        N_q = 5
        vm.add_if(medi, "h", Nmed, N_q)   # absent → cursor stays 27
        vm.add("m", 3)          # 3   → cursor=30
        vm.add("s", 3)          # 3   → cursor=33
        vm.add("w", 1, 3, 3)   # 9   → cursor=42
        vm.add("x", 1, 3)      # 3   → cursor=45
        vm.add_if(ss_lp, "plo", 3)  # 3 → cursor=48
        vm.add_if(ss_lp, "phi", 3)  # 3 → cursor=51
        vm.add_if(ss_lp, "q",   3)  # 3 → cursor=54
        vm.add_if(ss_lp, "tss", 3)  # 3 → cursor=57
        vm.mark_binary_start()
        vm.add("zx", 3, 2)     # 6   → cursor=63
        vm.add_if(medi,   "zm", Nmed, N_q)  # absent
        vm.add_if(ss_lp,  "zs", 3, 2)      # 6 → cursor=69

        assert "h" not in vm
        assert "tss" in vm
        assert vm["plo"].start == 45
        assert vm["tss"].start == 54
        assert vm["zx"].start == 57
        assert vm["zs"].start == 63
        assert vm.nconts == 57
        assert vm.nbins == 12
        assert vm.nvars == 69
