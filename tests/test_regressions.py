
import pytest

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
    inames = ['Joe']
    yobs = [1964]
    expectancy = [62]
    name = 'withdrawal_1'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1/1')
    p.setSpendingProfile('flat')
    p.setAccountBalances(taxable=[0], taxDeferred=[37.5], taxFree=[0])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('fixed', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'solver': solver}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*37.5/3, 0.01)

