
import pytest
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
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    assert p.inames == inames
    assert p.yobs == yobs
    assert p.expectancy == expectancy
    assert p.N_i == 1
    assert p._name == name
    assert p.startDate == '1-1'


def test_constructor2():
    inames = ['Joe', 'Jane']
    yobs = [1960, 1961]
    expectancy = [80, 82]
    name = 'test_2'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    assert p.inames == inames
    assert p.yobs == yobs
    assert p.expectancy == expectancy
    assert p.N_i == 2
    assert p._name == name
    assert p.startDate == '1-1'


def test_date_1():
    inames = ['Joe', 'Jane']
    yobs = [1960, 1961]
    expectancy = [80, 82]
    name = 'test_3'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='2024-1-1')
    assert p.inames == inames
    assert p.yobs == yobs
    assert p.expectancy == expectancy
    assert p.N_i == 2
    assert p._name == name
    assert p.startDate == '2024-1-1'


def test_date_2():
    inames = ['Joe', 'Jane']
    yobs = [1960, 1961]
    expectancy = [80, 82]
    name = 'test_3'
    startDate = date.today()
    p = owl.Plan(inames, yobs, expectancy, name, startDate=startDate)
    assert p.inames == inames
    assert p.yobs == yobs
    assert p.expectancy == expectancy
    assert p.N_i == 2
    assert p._name == name


def createPlan(ni, name, ny):
    # Make tests time independent.
    thisyear = date.today().year
    ny -= 1
    if ni == 1:
        inames = ['Joe']
        yobs = [1964]
        expectancy = [thisyear - 1964 + ny]
    else:
        inames = ['Joe', 'Jane']
        yobs = [1960, 1961]
        expectancy = [thisyear - 1960 + ny, thisyear - 1961 + ny]

    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    # Use a flat profile for simplicity.
    p.setSpendingProfile('flat', 100)

    return p


def test_withdrawal1():
    n = 3
    p = createPlan(1, 'withdrawal1', n)
    amount = 37.5
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('fixed', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal2():
    n = 3
    p = createPlan(1, 'withdrawal2', n)
    # Small taxable income creates an income smaller than standard deduction. Testing e_n.
    amount = 12
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('fixed', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal3():
    n = 6
    p = createPlan(1, 'withdrawal3', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('fixed', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_taxfreegrowth1():
    n = 12
    p = createPlan(1, 'taxfreegrowth1', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('fixed', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth2():
    n = 15
    p = createPlan(1, 'taxfreegrowth2', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 50, 50, 0], [0, 50, 50, 0]]])
    rate = 4
    p.setRates('fixed', values=[0, rate, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth3():
    n = 15
    p = createPlan(1, 'taxfreegrowth3', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[50, 50, 0, 0], [50, 50, 0, 0]]])
    rate = 4
    p.setRates('fixed', values=[rate, rate, 0, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth4():
    n = 16
    p = createPlan(1, 'taxfreegrowth4', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 50, 50, 0], [0, 50, 50, 0]]])
    rate = 4
    p.setRates('fixed', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    # Only half of the amount will grow.
    assert p.bequest == pytest.approx(1000*amount*(1+rate/200)**n, abs=0.5)


def test_taxfreegrowth5():
    n = 15
    p = createPlan(1, 'taxfreegrowth5', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    # Inflation should cancel out growth, if both rates are equal.
    p.setRates('fixed', values=[0, 0, 4, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth6():
    n = 15
    p = createPlan(1, 'taxfreegrowth6', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    # Inflation should cancel out growth.
    p.setRates('fixed', values=[0, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth7():
    n = 15
    p = createPlan(1, 'taxfreegrowth7', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 100, 0, 0], [0, 100, 0, 0]]])
    # Inflation should cancel out growth.
    p.setRates('fixed', values=[0, 4, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth8():
    n = 15
    p = createPlan(1, 'taxfreegrowth8', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[100, 0, 0, 0], [100, 0, 0, 0]]])
    # Inflation should cancel out growth.
    p.setRates('fixed', values=[4, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_annuity1():
    n = 12
    p = createPlan(1, 'annuity1', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('fixed', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    rate /= 100
    # Annuity equation has to be modified to account that first withdrawal
    # happens at the start of first period:  PV = ((1 + i)/i)*(1 - (1 + i)^-n).
    annuity = 1000*amount*rate/((1 - (1 + rate)**-n)*(1 + rate))
    assert p.basis == pytest.approx(annuity, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_annuity2():
    n = 18
    p = createPlan(1, 'annuity2', n)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('fixed', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    rate /= 100
    # Annuity equation has to be modified to account that first withdrawal
    # happens before the first period:  PV = ((1 + i)/i)*(1 - (1 + i)^-n).
    annuity = 1000*amount*rate/((1 - (1 + rate)**-n)*(1 + rate))
    assert p.basis == pytest.approx(annuity, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_annuity3():
    n = 30
    p = createPlan(1, 'annuity2', n)
    amount = 100
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('fixed', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    rate /= 100
    # Annuity equation has to be modified to account that first withdrawal
    # happens before the first period:  PV = ((1 + i)/i)*(1 - (1 + i)^-n).
    annuity = 1000*amount*rate/((1 - (1 + rate)**-n)*(1 + rate))
    assert p.basis == pytest.approx(annuity, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)
