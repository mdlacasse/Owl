
import pytest
import sys
from datetime import date

import owlplanner as owl

owl.setVerbose(False)
# solver = 'MOSEK'
solver = 'HiGHS'

def test_constructor1():
    inames = ['Joe']
    yobs = [1960]
    expectancy = [80]
    name = 'test_1'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1/1')
    assert p.inames == inames
    assert p.yobs == yobs
    assert p.expectancy == expectancy
    assert p.N_i == 1 
    assert p._name == name


def test_constructor2():
    inames = ['Joe', 'Jane']
    yobs = [1960, 1961]
    expectancy = [80, 82]
    name = 'test_2'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1/1')
    assert p.inames == inames
    assert p.yobs == yobs
    assert p.expectancy == expectancy
    assert p.N_i == 2 
    assert p._name == name


def createPlan(n, name):
    # Make it three years to fund or grow.
    thisyear = date.today().year
    if n == 1:
        inames = ['Joe']
        yobs = [1964]
        expectancy = [thisyear - 1964 + 2]
    else: 
        inames = ['Joe', 'Jane']
        yobs = [1960, 1961]
        expectancy = [thisyear - 1960 + 2, thisyear - 1961 + 2]

    p = owl.Plan(inames, yobs, expectancy, name, startDate='1/1')
    p.setSpendingProfile('flat')

    return p


def test_withdrawal1():
    p = createPlan(1, 'withdrawal1')
    amount = 37.5
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('fixed', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'solver': solver}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/3, abs=0.5)


def test_withdrawal2():
    p = createPlan(1, 'withdrawal2')
    # Small amount creates an income smaller than standard deduction.
    amount = 12
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('fixed', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'solver': solver}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/3, abs=0.5)


def test_withdrawal3():
    p = createPlan(1, 'withdrawal3')
    # Small amount creates an income smaller than standard deduction.
    amount = 12
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('fixed', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'solver': solver}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/3, abs=0.5)


def test_taxfreegrowth1():
    p = createPlan(1, 'taxfreegrowth1')
    amount = 12
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    p.setRates('fixed', values=[0, 0, 4, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*1.04**3, abs=0.5)


def test_taxfreegrowth2():
    p = createPlan(1, 'taxfreegrowth2')
    amount = 12
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    # Inflation should cancel out growth.
    p.setRates('fixed', values=[0, 0, 4, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)

def test_annuity():
    p = createPlan(1, 'annuity')
    amount = 12
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('fixed', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver}
    p.solve('maxSpending', options=options)
    rate /= 100
    # Annuity has to be modified to account that first withdrawal happens before.
    # PV = ((1 + i)/i)*(1 - (1 + i)^-n)
    annuity = 1000*amount*rate/((1 - (1 + rate)**-3)*(1 + rate))
    assert p.basis == pytest.approx(annuity, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)

