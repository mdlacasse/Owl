"""
Regression tests for Owl retirement planner core functionality.

Tests verify that the planner produces consistent results across
different scenarios and configurations.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import pytest
from datetime import date
import numpy as np

import owlplanner as owl

# solver = 'MOSEK'
solver = 'HiGHS'


def test_constructor1():
    inames = ['Joe']
    dobs = ["1961-01-15"]
    expectancy = [80]
    name = 'test_1'
    p = owl.Plan(inames, dobs, expectancy, name)
    assert p.inames == inames
    assert np.array_equal(p.dobs, dobs)
    assert np.array_equal(p.mobs, [1])
    assert np.array_equal(p.expectancy, expectancy)
    assert p.N_i == 1
    assert p._name == name


def test_constructor1_2():
    inames = ['Joe', 'Jane']
    dobs = ["1961-01-15", "1962-01-15"]
    expectancy = [80, 82]
    name = 'test_2'
    p = owl.Plan(inames, dobs, expectancy, name)
    assert p.inames == inames
    assert np.array_equal(p.dobs, dobs)
    assert np.array_equal(p.mobs, [1, 1])
    assert np.array_equal(p.expectancy, expectancy)
    assert p.N_i == 2
    assert p._name == name


def createPlan(ni, name, ny, topAge):
    # Make tests somehow year independent.
    assert ny >= 2
    thisyear = date.today().year
    ny -= 1
    if ni == 1:
        inames = ['Joe']
        expectancy = [topAge]
        yobs = [thisyear - topAge + ny]
        dobs = [f"{yobs[0]}-01-15"]
    else:
        inames = ['Joe', 'Jane']
        # Make Jane pass 2 years before Joe.
        expectancy = [topAge - 2, topAge]
        yobs = [thisyear - topAge + ny, thisyear - topAge + ny]
        dobs = [f"{yobs[0]}-01-15", f"{yobs[1]}-01-16"]

    p = owl.Plan(inames, dobs, expectancy, name)
    # Use a flat profile for simplicity.
    p.setSpendingProfile('flat', 100)

    return p


def test_date_1():
    inames = ['Joe', 'Jane']
    dobs = ["1961-01-15", "1962-01-16"]
    expectancy = [80, 82]
    name = 'test_3'
    p = owl.Plan(inames, dobs, expectancy, name)
    assert p.inames == inames
    assert np.array_equal(p.dobs, dobs)
    assert np.array_equal(p.mobs, [1, 1])
    assert np.array_equal(p.tobs, [15, 16])
    assert np.array_equal(p.expectancy, expectancy)
    assert p.N_i == 2
    assert p._name == name
    assert p.startDate is None


def test_date_2():
    n = 10
    p = createPlan(1, 'date_2', n, 70)
    amount = 3.0
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0], startDate="1-1")
    assert p.startDate == "1-1"


def test_date_3():
    n = 10
    p = createPlan(1, 'date_3', n, 70)
    amount = 3.0
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0])
    assert p.startDate == date.today().strftime('%Y-%m-%d')


def test_date_4():
    n = 10
    p = createPlan(1, 'date_3', n, 70)
    amount = 3.0
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0], startDate="today")
    assert p.startDate == date.today().strftime('%Y-%m-%d')


def test_withdrawal1():
    n = 10
    p = createPlan(1, 'withdrawal1', n, 70)
    amount = 3.0
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxSpending', options=options)
    assert p.caseStatus == "solved", f"Solve failed with status: {p.caseStatus}"
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal2():
    n = 10
    p = createPlan(1, 'withdrawal2', n, 70)
    # Small taxable income creates an income smaller than standard deduction. Testing e_n.
    amount = 40.0
    p.setAccountBalances(taxable=[0], taxDeferred=[amount], taxFree=[0], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxSpending', options=options)
    assert p.caseStatus == "solved", f"Solve failed with status: {p.caseStatus}"
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal2_2():
    n = 10
    p = createPlan(2, 'withdrawal2_2', n, 70)
    # Small taxable income creates an income smaller than standard deduction. Testing e_n.
    amount = 50
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[amount/2, amount/2],
                         taxFree=[0, 0], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 0, 100], [0, 0, 0, 100]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxSpending', options=options)
    assert p.caseStatus == "solved", f"Solve failed with status: {p.caseStatus}"
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal3():
    n = 6
    p = createPlan(1, 'withdrawal3', n, 70)
    amount = 60
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_withdrawal3_2():
    n = 6
    p = createPlan(2, 'withdrawal3', n, 70)
    amount = 60
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 0, 100], [0, 0, 0, 100]])
    p.setRates('user', values=[0, 0, 0, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxSpending', options=options)
    assert p.basis == pytest.approx(1000*amount/n, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)


def test_taxfreegrowth1():
    n = 12
    p = createPlan(1, 'taxfreegrowth1', n, 72)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver,
               'withSCLoop': False, 'xorConstraints': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth1_2():
    n = 12
    p = createPlan(2, 'taxfreegrowth1', n, 72)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver,
               'withSCLoop': False, 'xorConstraints': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth2():
    n = 15
    p = createPlan(1, 'taxfreegrowth2', n, 75)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 50, 50, 0], [0, 50, 50, 0]]])
    rate = 4
    p.setRates('user', values=[0, rate, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver,
               'withSCLoop': False, 'xorConstraints': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth2_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth2', n, 75)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 50, 50, 0], [0, 50, 50, 0]])
    rate = 4
    p.setRates('user', values=[0, rate, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver,
               'withSCLoop': False, 'xorConstraints': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth3():
    n = 15
    p = createPlan(1, 'taxfreegrowth3', n, 75)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[50, 50, 0, 0], [50, 50, 0, 0]]])
    rate = 4
    p.setRates('user', values=[rate, rate, 0, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver,
               'withSCLoop': False, 'xorConstraints': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth3_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth3', n, 75)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[50, 50, 0, 0], [50, 50, 0, 0]])
    rate = 4
    p.setRates('user', values=[rate, rate, 0, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver,
               'withSCLoop': False, 'xorConstraints': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount*(1+rate/100)**n, abs=0.5)


def test_taxfreegrowth4():
    n = 16
    p = createPlan(1, 'taxfreegrowth4', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 50, 50, 0], [0, 50, 50, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    # Only half of the amount will grow.
    assert p.bequest == pytest.approx(1000*amount*(1+rate/200)**n, abs=0.5)


def test_taxfreegrowth4_2():
    n = 16
    p = createPlan(2, 'taxfreegrowth4', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 50, 50, 0], [0, 50, 50, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    # Only half of the amount will grow.
    assert p.bequest == pytest.approx(1000*amount*(1+rate/200)**n, abs=0.5)


def test_taxfreegrowth5():
    n = 15
    p = createPlan(1, 'taxfreegrowth5', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    # Inflation should cancel out growth, if both rates are equal.
    p.setRates('user', values=[0, 0, 4, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth5_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth5', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    # Inflation should cancel out growth, if both rates are equal.
    p.setRates('user', values=[0, 0, 4, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth6():
    n = 15
    p = createPlan(1, 'taxfreegrowth6', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 0, 100], [0, 0, 0, 100]]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[0, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth6_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth6', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 0, 100], [0, 0, 0, 100]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[0, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth7():
    n = 15
    p = createPlan(1, 'taxfreegrowth7', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 100, 0, 0], [0, 100, 0, 0]]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[0, 4, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth7_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth7', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 100, 0, 0], [0, 100, 0, 0]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[0, 4, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver, 'withSCLoop': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth8():
    n = 15
    p = createPlan(1, 'taxfreegrowth8', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[100, 0, 0, 0], [100, 0, 0, 0]]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[4, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver,
               'withSCLoop': False, 'xorConstraints': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(1e-7, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_taxfreegrowth8_2():
    n = 15
    p = createPlan(2, 'taxfreegrowth8', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[100, 0, 0, 0], [100, 0, 0, 0]])
    # Inflation should cancel out growth.
    p.setRates('user', values=[4, 0, 0, 4])
    options = {'maxRothConversion': 0, 'netSpending': 0, 'solver': solver,
               'withSCLoop': False, 'xorConstraints': False}
    p.solve('maxBequest', options=options)
    assert p.basis == pytest.approx(0, abs=0.01)
    assert p.bequest == pytest.approx(1000*amount, abs=0.5)


def test_annuity1():
    n = 12
    p = createPlan(1, 'annuity1', n, 76)
    amount = 120
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
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
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
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
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
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
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
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
    p.setAccountBalances(taxable=[0], taxDeferred=[0], taxFree=[amount], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[0, 0, 100, 0], [0, 0, 100, 0]]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
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
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0],
                         taxFree=[amount/2, amount/2], startDate="1-1")
    p.setAllocationRatios('spouses', generic=[[0, 0, 100, 0], [0, 0, 100, 0]])
    rate = 4
    p.setRates('user', values=[0, 0, rate, 0])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
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
    dobs = ["1962-01-15"]
    expectancy = [89]
    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile('smile', 60)

    p.setAccountBalances(taxable=[90.5], taxDeferred=[600.2],
                         taxFree=[50 + 20.6], startDate="1-1")
    p.setAllocationRatios('individual', generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0], [65])
    options = {'maxRothConversion': 0, 'bequest': 0, 'solver': solver, 'withSCLoop': False}
    p.runHistoricalRange('maxSpending', options, 1928, 1958, figure=False)


def test_Historical2():
    name = 'historical2'
    inames = ['Jack', 'Jill']
    dobs = ["1962-01-15", "1965-01-16"]
    expectancy = [89, 92]
    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile('smile', 60)
    p.setAccountBalances(taxable=[90.5, 60], taxDeferred=[600.2, 150],
                         taxFree=[50 + 20.6, 40.8], startDate="1-1")
    p.setAllocationRatios('individual',
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[60, 40, 0, 0], [70, 30, 0, 0]]],)
    p.setPension([0, 10], [65, 65])
    p.setSocialSecurity([28, 25], [70, 70])
    p.setHeirsTaxRate(33)

    options = {'maxRothConversion': 100, 'noRothConversions': 'Jill', 'withSCLoop': True}
    p.runHistoricalRange('maxSpending', options, 1928, 1958, figure=False)


def test_fire_roth_ladder():
    """
    FIRE-style Roth conversion ladder verification.

    Single individual, age 45, all funds in tax-deferred, born in October
    (month > 6) to exercise the month-of-birth 59½ correction.

    Checks:
    - n595 is 1 year later for Oct-born vs Jan-born (month fix).
    - Optimizer discovers the ladder: conversions in years 0–5, Roth
      withdrawals from year 6 onward while still pre-59½.
    - P_n equals 0.1 × w_trad only — no Roth penalty leak.
    - P_n is zero for all n >= n595.
    """
    thisyear = date.today().year
    age = 45
    life = 85

    # October birth → n595 = 59 - thisyear + (thisyear - age) + 1 = 14 + 1 = 15
    dob_oct = f"{thisyear - age}-10-01"
    dob_jan = f"{thisyear - age}-01-01"

    def _make_plan(dob, name):
        p = owl.Plan(["Alex"], [dob], [life], name)
        p.setAccountBalances(taxable=[0], taxDeferred=[2000], taxFree=[0], startDate="1-1")
        p.setSpendingProfile("flat", 100)
        p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
        p.setRates("user", values=[5, 5, 5, 0])
        return p

    options = {
        "maxRothConversion": 200,
        "bequest": 0,
        "solver": solver,
        "withSCLoop": False,
        "withMedicare": False,
    }

    p_oct = _make_plan(dob_oct, "fire_ladder_oct")
    p_oct.solve("maxSpending", options=options)
    assert p_oct.caseStatus == "solved"

    p_jan = _make_plan(dob_jan, "fire_ladder_jan")
    p_jan.solve("maxSpending", options=options)
    assert p_jan.caseStatus == "solved"

    # Month-of-birth correction: Oct-born should have n595 one year later than Jan-born.
    assert p_oct.n595[0] == p_jan.n595[0] + 1

    n595 = p_oct.n595[0]
    x_in   = p_oct.x_in[0]        # Roth conversions
    w_roth = p_oct.w_ijn[0, 2, :]  # Roth withdrawals
    w_trad = p_oct.w_ijn[0, 1, :]  # Tax-deferred withdrawals
    P_n    = p_oct.P_n

    # Ladder: meaningful conversions happen in the first 5 years.
    assert np.sum(x_in[:5]) > 50, f"Expected ladder conversions in years 0-4, got {np.sum(x_in[:5]):.1f}"

    # Ladder: Roth withdrawals appear after 5 years (mature conversions).
    assert np.sum(w_roth[5:n595]) > 10, (
        f"Expected Roth withdrawals after year 5, got {np.sum(w_roth[5:n595]):.1f}"
    )

    # Penalty applies only to tax-deferred withdrawals, never to Roth.
    np.testing.assert_allclose(
        P_n[:n595], 0.1 * w_trad[:n595], atol=0.5,
        err_msg="P_n does not match 0.1*w_trad (Roth penalty leak?)",
    )

    # No penalty after 59½.
    assert np.all(P_n[n595:] == 0)
