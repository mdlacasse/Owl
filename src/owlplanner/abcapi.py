"""

Owl/abcapi
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

This file contains basic functions to build a constraint matrix and
objective function line by line. This is used to abstract the
building of the constraint matrix in order to be able to use various
solvers for comparison.

This approach has been successful with the MOSEK and the HiGHS solvers.
A for matrix, B for bounds, C for constraints. Thus the name ABCAPI.

Copyright (C) 2024 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.

"""

import numpy as np


class Row(object):
    """
    Solver-neutral API to accomodate Mosek/HiGHS.
    A Row represent a row in matrix A.
    """

    def __init__(self, nvars):
        """
        Constructor requires the number of decision variables.
        """
        self.nvars = nvars
        self.ind = []
        self.val = []

    def addElem(self, ind, val):
        """
        Add an element at index ``ind`` of value ``val`` to the row.
        """
        if not (0 <= ind < self.nvars):
            raise ValueError(f"Index {ind} out of range.")
        self.ind.append(ind)
        self.val.append(val)

    def addElemDic(self, rowDic=None):
        """
        Add elements at indices provided by a dictionary.
        """
        rowDic = {} if rowDic is None else rowDic
        for key in rowDic:
            self.addElem(key, rowDic[key])
        return self


class ConstraintMatrix(object):
    """
    Solver-neutral API for expressing constraints.
    """

    def __init__(self, nvars):
        """
        Constructor only requires the number of decision variables.
        """
        self.ncons = 0
        self.nvars = nvars
        self.Aind = []
        self.Aval = []
        self.lb = []
        self.ub = []
        self.key = []

    def newRow(self, rowDic=None):
        """
        Create a new row and populate its elements using the dictionary provided.
        Return the row created.
        """
        rowDic = {} if rowDic is None else rowDic
        row = Row(self.nvars)
        row.addElemDic(rowDic)
        return row

    def addRow(self, row, lb, ub):
        """
        Add row ``row`` to the constraint matrix with the lower ``lb`` and
        upper bound ``ub`` provided.
        """
        self.Aind.append(row.ind)
        self.Aval.append(row.val)
        self.lb.append(lb)
        self.ub.append(ub)
        if lb == ub:
            self.key.append("fx")
        elif ub == np.inf and lb == -np.inf:
            self.key.append("fr")
        elif ub == np.inf:
            self.key.append("lo")
        elif lb == -np.inf:
            self.key.append("up")
        else:
            self.key.append("ra")
        self.ncons += 1

    def addNewRow(self, rowDic, lb, ub):
        """
        Create and add a new row to the constraint matrix with the lower ``lb`` and
        upper bound ``ub`` provided. Row's elements are populated from the provided
        dictionary ``rowDic``.
        """
        row = self.newRow(rowDic)
        self.addRow(row, lb, ub)

    def keys(self):
        """
        Return list of keys for each row used by MOSEK.
        """
        return self.key

    def lists(self):
        """
        Return lists of indices and values for MOSEK sparse representation.
        """
        return self.Aind, self.Aval, self.lb, self.ub

    def arrays(self):
        """
        Return full arrays for Scipy/HiGHS.
        """
        Alu = np.zeros((self.ncons, self.nvars))
        lb = np.array(self.lb)
        ub = np.array(self.ub)
        for ii in range(self.ncons):
            ind = self.Aind[ii]
            val = self.Aval[ii]
            for jj in range(len(ind)):
                Alu[ii, ind[jj]] = val[jj]

        return Alu, lb, ub


class Bounds(object):
    """
    Solver-neutral API for bounds on variables.
    """

    def __init__(self, nvars, nbins):
        self.nvars = nvars
        self.nbins = nbins
        self.ind = []
        self.lb = []
        self.ub = []
        self.key = []
        self.integrality = []
        for ii in range(nvars-nbins, nvars):
            self.setBinary(ii)

    def setBinary(self, ii):
        if not (0 <= ii < self.nvars):
            raise ValueError(f"Index {ii} out of range.")
        self.ind.append(ii)
        self.lb.append(0)
        self.ub.append(1)
        self.key.append("ra")
        self.integrality.append(ii)

    def setRange(self, ii, lb, ub):
        if not (0 <= ii < self.nvars):
            raise ValueError(f"Index {ii} out of range.")
        if lb > ub:
            raise ValueError(f"Lower bound {lb} > upper bound {ub}.")
        self.ind.append(ii)
        self.lb.append(lb)
        self.ub.append(ub)
        if lb == ub:
            self.key.append("fx")
        elif ub == np.inf and lb == -np.inf:
            self.key.append("fr")
        elif ub == np.inf:
            self.key.append("lo")
        elif lb == -np.inf:
            self.key.append("up")
        else:
            self.key.append("ra")

    def keys(self):
        keys = ["lo"] * self.nvars
        for ii in range(len(self.ind)):
            keys[self.ind[ii]] = self.key[ii]

        return keys

    def arrays(self):
        lb = np.zeros(self.nvars)
        ub = np.ones(self.nvars) * np.inf
        for ii in range(len(self.ind)):
            lb[self.ind[ii]] = self.lb[ii]
            ub[self.ind[ii]] = self.ub[ii]

        return lb, ub

    def integralityArray(self):
        integrality = np.zeros(self.nvars, dtype=int)
        for ii in range(len(self.integrality)):
            integrality[self.integrality[ii]] = 1

        return integrality

    def integralityList(self):
        return self.integrality


class Objective(object):
    """
    Solver-neutral objective function.
    """

    def __init__(self, nvars):
        self.nvars = nvars
        self.ind = []
        self.val = []

    def setElem(self, ind, val):
        if not (0 <= ind < self.nvars):
            raise ValueError(f"Index {ind} out of range.")
        self.ind.append(ind)
        self.val.append(val)

    def arrays(self):
        """
        Return an array for scipy/HiGHS dense representation.
        """
        c = np.zeros(self.nvars)
        for ii in range(len(self.ind)):
            c[self.ind[ii]] = self.val[ii]

        return c

    def lists(self):
        """
        Return lists for Mosek sparse representation.
        """
        return self.ind, self.val
