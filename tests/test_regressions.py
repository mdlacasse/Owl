import pytest
from datetime import date
import numpy as np

import owlplanner as owl

# solver = 'MOSEK'
solver = 'HiGHS'


def test_constructor1():
    inames = ['Joe']
    yobs = [1961]
    expectancy = [80]
    name = 'test_1'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    assert p.inames == inames
    assert np.array_equal(p.yobs, yobs)
    assert np.array_equal(p.expectancy, expectancy)
    assert p.N_i == 1
    assert p._name == name
    assert p.startDate == '1-1'


def test_constructor1_2():
    inames = ['Joe', 'Jane']
    yobs = [1961, 1962]
    expectancy = [80, 82]
    name = 'test_2'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    assert p.inames == inames
    assert np.array_equal(p.yobs, yobs)
    assert np.array_equal(p.expectancy, expectancy)
    assert p.N_i == 2
    assert p._name == name
    assert p.startDate == '1-1'


def test_date_1():
    inames = ['Joe', 'Jane']
    yobs = [1961, 1962]
    expectancy = [80, 82]
    name = 'test_3'
    p = owl.Plan(inames, yobs, expectancy, name, startDate='2025-1-1')
    assert p.inames == inames
    assert np.array_equal(p.yobs, yobs)
    assert np.array_equal(p.expectancy, expectancy)
    assert p.N_i == 2
    assert p._name == name
    assert p.startDate == '2025-1-1'


def test_date_2():
    inames = ['Joe', 'Jane']
    yobs = [1961, 1962]
    expectancy = [80, 82]
    name = 'test_3'
    startDate = date.today()
    p = owl.Plan(inames, yobs, expectancy, name, startDate=startDate)
    assert p.inames == inames
    assert np.array_equal(p.yobs, yobs)
    assert np.array_equal(p.expectancy, expectancy)
    assert p.N_i == 2
    assert p._name == name
    assert p.startDate == date.today().strftime('%Y-%m-%d')


def createPlan(ni, name, ny, topAge):
    # Make tests somehow year independent.
    assert ny >= 2
    thisyear = date.today().year
    ny -= 1
    if ni == 1:
        inames = ['Joe']
        expectancy = [topAge]
        yobs = [thisyear - topAge + ny]
    else:
        inames = ['Joe', 'Jane']
        # Make Jane pass 2 years before Joe.
        expectancy = [topAge - 2, topAge]
        yobs = [thisyear - topAge + ny, thisyear - topAge + ny]

    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    # Use a flat profile for simplicity.
    p.setSpendingProfile('flat', 100)

    return p


def test_withdrawal1():
    n = 10
    p = createPlan(1, 'withdrawal1', n, 70)
    amount = 3.0
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal2():
    n = 10
    p = createPlan(1, 'withdrawal2', n, 70)
    # Small taxable income creates an income smaller than standard deduction. Testing e_n.
    amount = 40.0
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal2_2():
    n = 10
    p = createPlan(2, 'withdrawal2_2', n, 70)
    # Small taxable income creates an income smaller than standard deduction. Testing e_n.
    amount = 50
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[amount/2, amount/2], taxFree=[0, 0])
    p.setAllocationRatios('spouses', generic=[[0, 0, 0, 100], [0, 0, 0, 100]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal3():
    n = 6
    p = createPlan(1, 'withdrawal3', n, 70)
    amount = 60
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal3_2():
    n = 6
    p = createPlan(2, 'withdrawal3', n, 70)
    amount = 60
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 0, 0, 100], [0, 0, 0, 100]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_taxfreegrowth1():
    n = 12
    p = createPlan(1, 'taxfreegrowth1', n, 72)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth1_2():
    n = 12
    p = createPlan(2, 'taxfreegrowth1', n, 72)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth2():
    n = 15
    p = createPlan(1, 'taxfreegrowth2', n, 75)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 50, 50, 0], [0, 50, 50, 0]]])
    rate = 4
    p.setRates('user', values=[0, rate, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth2_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth2', n, 75)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 50, 50, 0], [0, 50, 50, 0]])
    rate = 4
    p.setRates('user', values=[0, rate, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth3():
    n = 15
    p = createPlan(1, 'taxfreegrowth3', n, 75)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[50, 50, 0, 0], [50, 50, 0, 0]]])
    rate = 4
    p.setRates('user', values=[rate, rate, 0, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth3_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth3', n, 75)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[50, 50, 0, 0], [50, 50, 0, 0]])
    rate = 4
    p.setRates('user', values=[rate, rate, 0, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth4():
    n = 16
    p = createPlan(1, 'taxfreegrowth4', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 50, 50, 0], [0, 50, 50, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    # Only half of the amount will grow.
    assert p.bequest == pytest.approx(1000*amount*(1+rate/200)**n, abs=0.5)


def test_taxfreegrowth4_2():
    n = 16
    p = createPlan(2, 'taxfreegrowth4', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 50, 50, 0], [0, 50, 50, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    # Only half of the amount will grow.
    assert p.bequest == pytest.approx(1000*amount*(1+rate/200)**n, abs=0.5)


def test_taxfreegrowth5():
    n = 15
    p = createPlan(1, 'taxfreegrowth5', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    # Inflation should cancel out growth, if both rates are equal.
    p.setRates('user', values=[0, 0, 4, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth5_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth5', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    # Inflation should cancel out growth, if both rates are equal.
    p.setRates('user', values=[0, 0, 4, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth6():
    n = 15
    p = createPlan(1, 'taxfreegrowth6', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[0, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth6_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth6', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 0, 0, 100], [0, 0, 0, 100]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[0, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth7():
    n = 15
    p = createPlan(1, 'taxfreegrowth7', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 100, 0, 0], [0, 100, 0, 0]]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[0, 4, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth7_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth7', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 100, 0, 0], [0, 100, 0, 0]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[0, 4, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth8():
    n = 15
    p = createPlan(1, 'taxfreegrowth8', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[100, 0, 0, 0], [100, 0, 0, 0]]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[4, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth8_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth8', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[100, 0, 0, 0], [100, 0, 0, 0]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[4, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_annuity1():
    n = 12
    p = createPlan(1, 'annuity1', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    rate /= 100
    # Annuity equation has to be modified to account that first withdrawal
    # happens at the start of first period:  PV = ((1 + i)/i)*(1 - (1 + i)^-n).
    annuity = 1000*amount*rate/((1 - (1 + rate)**-n)*(1 + rate))
    assert p.basis == pytest.approx(annuity, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_annuity1_2():
    n = 12
    p = createPlan(2, 'annuity1', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
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
    p = createPlan(1, 'annuity2', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    rate /= 100
    # Annuity equation has to be modified to account that first withdrawal
    # happens before the first period:  PV = ((1 + i)/i)*(1 - (1 + i)^-n).
    annuity = 1000*amount*rate/((1 - (1 + rate)**-n)*(1 + rate))
    assert p.basis == pytest.approx(annuity, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_annuity2_2():
    n = 18
    p = createPlan(2, 'annuity2', n, 78)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
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
    p = createPlan(1, 'annuity2', n, 90)
    amount = 100
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount])
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    rate /= 100
    # Annuity equation has to be modified to account that first withdrawal
    # happens before the first period:  PV = ((1 + i)/i)*(1 - (1 + i)^-n).
    annuity = 1000*amount*rate/((1 - (1 + rate)**-n)*(1 + rate))
    assert p.basis == pytest.approx(annuity, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_annuity3_2():
    n = 30
    p = createPlan(2, 'annuity2', n, 90)
    amount = 100
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[amount/2, amount/2])
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.solve('maxSpending', options=options)
    rate /= 100
    # Annuity equation has to be modified to account that first withdrawal
    # happens before the first period:  PV = ((1 + i)/i)*(1 - (1 + i)^-n).
    annuity = 1000*amount*rate/((1 - (1 + rate)**-n)*(1 + rate))
    assert p.basis == pytest.approx(annuity, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_Historical1():
    name = 'historical1'
    inames = ['Joe']
    yobs = [1962]
    expectancy = [89]
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    p.setSpendingProfile('smile', 60)

    p.setAccountBalances(taxable=[90.5], taxDeferred=[600.2], taxFree=[50 + 20.6])
    p.setAllocationRatios('individual', generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0], [65])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withMedicare': False}
    p.runHistoricalRange('maxSpending', options, 1928, 1958, figure=False)


def test_Historical2():
    name = 'historical2'
    inames = ['Jack', 'Jill']
    yobs = [1962, 1965]
    expectancy = [89, 92]
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    p.setSpendingProfile('smile', 60)
    p.setAccountBalances(taxable=[90.5, 60], taxDeferred=[600.2, 150],
                         taxFree=[50 + 20.6, 40.8],)
    p.setAllocationRatios('individual',
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[60, 40, 0, 0], [70, 30, 0, 0]]],)
    p.setPension([0, 10], [65, 65])
    p.setSocialSecurity([28, 25], [70, 70])
    p.setHeirsTaxRate(33)
    p.setLongTermCapitalTaxRate(15)

    options = {'maxRothConversion': 100, 'noRothConversions': 'Jill', 'withMedicare': True}
    p.runHistoricalRange('maxSpending', options, 1928, 1958, figure=False)
