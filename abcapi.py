'''
This file contains basic functions to build
a constraint matrix and objective function
line by line. This is used to abstract the
building of the constraint matrix in order
to be able to use various solvers for comparison.

This approach has been successful with the MOSEK and 
the HiGHS solvers.
'''
import numpy as np

class Row:
    '''
    Solver-neutral API to accomodate Mosek/HiGHS.
    '''
    def __init__(self, nvars):
        self.nvars = nvars
        self.ind = []
        self.val = []

    def addElem(self, ind, val):
        assert 0 <= ind and ind < self.nvars, 'Index %d out of range.'%ind
        self.ind.append(ind)
        self.val.append(val)

    def addElemList(self, indList, valList):
        assert len(indList) == len(valList), 'Unequal lists in addElemList.'
        self.ind += indList
        self.val += valList
        return self

    def addElemDic(self, rowDic={}):
        for key in rowDic:
            self.addElem(key, rowDic[key])
        return self


class ConstraintMatrix:
    '''
    Solver-neutral API for expressing constraints.
    '''
    def __init__(self, nvars):
        self.ncons = 0
        self.nvars = nvars
        self.Aind = []
        self.Aval = []
        self.lb = []
        self.ub = []
        self.key = []

    def newRow(self, rowDic={}):
        row = Row(self.nvars)
        row.addElemDic(rowDic)
        return row

    def addRow(self, row, lb, ub):
        self.Aind.append(row.ind)
        self.Aval.append(row.val)
        self.lb.append(lb)
        self.ub.append(ub)
        if lb == ub:
            self.key.append('fx')
        elif ub == np.inf:
            self.key.append('lo')
        else:
            self.key.append('ra')
        self.ncons += 1

    def addNewRow(self, rowDic, lb, ub):
        row = self.newRow(rowDic)
        self.addRow(row, lb, ub)

    def keys(self):
        return self.key

    def lists(self):
        '''
        Return lists for Mosek sparse representation.
        '''
        return self.Aind, self.Aval, self.lb, self.ub

    def arrays(self):
        '''
        Return dense arrays for Scipy/HiGHS.
        '''
        Alu = np.zeros((self.ncons, self.nvars))
        lb = np.array(self.lb)
        ub = np.array(self.ub)
        for ii in range(self.ncons):
            ind = self.Aind[ii]
            val = self.Aval[ii]
            for jj in range(len(ind)):
                Alu[ii, ind[jj]] = val[jj]

        return Alu, lb, ub


class Bounds:
    '''
    Solver-neutral API for bounds on variables.
    '''
    def __init__(self, nvars):
        self.nvars = nvars
        self.ind = []
        self.lb = []
        self.ub = []
        self.key = []
        self.integrality = []

    def setBinary(self, ii):
        assert 0 <= ii and ii < self.nvars, 'Index %d out of range.'%ii
        self.ind.append(ii)
        self.lb.append(0)
        self.ub.append(1)
        self.key.append('ra')
        self.integrality.append(ii)

    def set0_Ub(self, ii, ub):
        assert 0 <= ii and ii < self.nvars, 'Index %d out of range.'%ii
        self.ind.append(ii)
        self.lb.append(0)
        self.ub.append(ub)
        self.key.append('ra')

    def setLb_Inf(self, ii, lb):
        assert 0 <= ii and ii < self.nvars, 'Index %d out of range.'%ii
        self.ind.append(ii)
        self.lb.append(lb)
        self.ub.append(np.inf)
        self.key.append('lo')

    def setRange(self, ii, lb, ub):
        assert 0 <= ii and ii < self.nvars, 'Index %d out of range.'%ii
        self.ind.append(ii)
        self.lb.append(lb)
        self.ub.append(ub)
        if lb == ub:
            self.key.append('fx')
        else:
            self.key.append('ra')

    def keys(self):
        keys = ['lo']*self.nvars
        for ii in range(len(self.ind)):
            keys[self.ind[ii]] = self.key[ii]

        return keys

    def arrays(self):
        lb = np.zeros(self.nvars)
        ub = np.ones(self.nvars)*np.inf
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


class Objective:
    '''
    Solver-neutral objective function.
    '''
    def __init__(self, nvars):
        self.nvars = nvars
        self.ind = []
        self.val = []

    def setElem(self, ind, val):
        assert 0 <= ind and ind < self.nvars, 'Index %d out of range.'%ind
        self.ind.append(ind)
        self.val.append(val)

    def arrays(self):
        '''
        Return an array for scipy/HiGHS dense representation.
        '''
        c = np.zeros(self.nvars)
        for ii in range(len(self.ind)):
            c[self.ind[ii]] = self.val[ii]

        return c

    def lists(self):
        '''
        Return lists for Mosek sparse representation.
        '''
        return self.ind, self.val


