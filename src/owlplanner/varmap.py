"""
Variable block indexing and extraction for the LP solver in plan.py.

Each decision-variable family (b, d, e, f, g, h, m, s, w, x, zx, …) lives in a
contiguous slice of the flat solution vector ``x``.  ``VarBlock`` records the start
offset and shape of one such family; ``VarMap`` accumulates them in declaration order
and exposes a cursor that naturally tracks the running offset.

Usage (inside plan.py)::

    vm = VarMap()
    vm.add("b", N_i, N_j, N_n + 1)
    vm.add("d", N_i, N_n)
    ...
    vm.mark_binary_start()
    vm.add("zx", N_n, N_zx)

    # Index into constraint row:
    idx = vm["b"].idx(i, j, n)       # replaces _q3(C["b"], i, j, n, N_i, N_j, N_n+1)

    # Extract results:
    b_ijn = vm["b"].extract(x)       # shape (N_i, N_j, N_n+1)

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import numpy as np


class VarBlock:
    """
    One contiguous family of LP decision variables inside the flat solution vector.

    Parameters
    ----------
    name  : str   — human-readable label (used in error messages)
    start : int   — first index in the flat vector (replaces C["key"])
    shape : tuple — dimensions in C (row-major) order
    """

    def __init__(self, name: str, start: int, shape: tuple):
        self.name = name
        self.start = start
        self.shape = shape
        self.size = math.prod(shape)

    @property
    def end(self) -> int:
        """One past the last index (exclusive upper bound for slicing)."""
        return self.start + self.size

    def idx(self, *indices) -> int:
        """Return the flat index for the given multi-dimensional indices (row-major / C order).

        Replaces ``_q1`` / ``_q2`` / ``_q3`` / ``_q4`` — no dimension arguments
        needed at the call site because the shape is already stored in the block.
        """
        if len(indices) != len(self.shape):
            raise IndexError(
                f"VarBlock '{self.name}': expected {len(self.shape)} index/indices, "
                f"got {len(indices)}"
            )
        flat, stride = 0, 1
        for ax in range(len(self.shape) - 1, -1, -1):
            flat += indices[ax] * stride
            stride *= self.shape[ax]
        return self.start + flat

    def extract(self, x) -> np.ndarray:
        """Slice ``x[start:end]`` and reshape to ``self.shape``.

        Replaces the ``x[Ca:Cb].reshape(shape)`` pattern in ``_aggregateResults``.
        The slice boundaries are derived from the stored start/size — they are
        correct regardless of what variable blocks were added *after* this one.
        """
        return np.array(x[self.start:self.end]).reshape(self.shape)

    def __repr__(self) -> str:
        return f"VarBlock('{self.name}', start={self.start}, shape={self.shape})"


class VarMap:
    """
    Accumulates ``VarBlock`` objects in declaration order, tracking a cursor that
    advances by each block's size.

    All continuous variable blocks must be added before ``mark_binary_start()``;
    binary blocks come after.
    """

    def __init__(self):
        self._blocks: dict[str, VarBlock] = {}
        self._cursor: int = 0
        self._bin_start: int | None = None

    # ------------------------------------------------------------------
    # Building the map
    # ------------------------------------------------------------------

    def add(self, name: str, *dims: int) -> VarBlock:
        """Add a variable block with the given dimensions and return it."""
        block = VarBlock(name, self._cursor, tuple(dims))
        self._blocks[name] = block
        self._cursor += block.size
        return block

    def add_if(self, cond: bool, name: str, *dims: int):
        """Add a block only when *cond* is True; return ``None`` otherwise.

        Callers that need to guard access use ``"key" in vm`` before indexing.
        """
        return self.add(name, *dims) if cond else None

    def mark_binary_start(self):
        """Record the boundary between continuous and binary variables.

        Call this once, immediately before adding the first binary block.
        """
        self._bin_start = self._cursor

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def __getitem__(self, name: str) -> VarBlock:
        try:
            return self._blocks[name]
        except KeyError:
            raise KeyError(f"VarMap: no block named '{name}'") from None

    def __contains__(self, name: str) -> bool:
        return name in self._blocks

    # ------------------------------------------------------------------
    # Aggregate properties (mirror the old manual assignments)
    # ------------------------------------------------------------------

    @property
    def nvars(self) -> int:
        """Total number of decision variables (continuous + binary)."""
        return self._cursor

    @property
    def nconts(self) -> int:
        """Number of continuous variables (= start of first binary block)."""
        return self._bin_start if self._bin_start is not None else self._cursor

    @property
    def nbins(self) -> int:
        """Number of binary variables."""
        return self._cursor - self.nconts

    @property
    def nbals(self) -> int:
        """Size of the ``b`` block (= N_i * N_j * (N_n + 1))."""
        return self._blocks["b"].size
