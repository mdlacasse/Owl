
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

def test_withdrawal1():
    thisyear = date.today().year
    inames = ['Joe']
    yobs = [1964]
    # This makes three years to fund.
    expectancy = [thisyear - 1964 + 2]
    name = 'withdrawal_1'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1/1')
    p.setSpendingProfile('flat')
    amount = 37.5
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('fixed', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'solver': solver}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/3, 0.01)

def test_withdrawal2():
    thisyear = date.today().year
    inames = ['Joe']
    yobs = [1964]
    # This makes three years to fund.
    expectancy = [thisyear - 1964 + 2]
    name = 'withdrawal_2'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1/1')
    p.setSpendingProfile('flat')
    # Small amount creates an income smaller than standard deduction.
    amount = 12
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('fixed', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'solver': solver}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/3, 0.01)

