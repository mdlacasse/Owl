
import pytest
import os
from datetime import date
from io import StringIO

import owlplanner as owl


# solver = 'MOSEK'
solver = 'HiGHS'
thisyear = date.today().year


def createJackAndJillPlan(name):
    inames = ['Jack', 'Jill']
    yobs = [1962, 1965]
    expectancy = [thisyear - 1962 + 20, thisyear - 1965 + 20]
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    p.setSpendingProfile('flat', 60)

    p.setAccountBalances(taxable=[90, 60], taxDeferred=[600, 150], taxFree=[50 + 20, 40])
    p.readContributions('./examples/jack+jill.xlsx')
    p.setInterpolationMethod('s-curve')
    p.setAllocationRatios('individual', generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0, 10], [65, 65])
    p.setSocialSecurity([28, 25], [70, 70])

    return p


def test_case1():
    p = createJackAndJillPlan('case1')
    p.setRates('historical', 1969)
    p.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 500})
    assert p.basis == pytest.approx(82202, abs=0.5)
    assert p.bequest == pytest.approx(500000, abs=0.5)


def test_case2():
    p = createJackAndJillPlan('case2')
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p.basis == pytest.approx(80000, abs=0.5)
    assert p.bequest == pytest.approx(606235, abs=0.5)


def test_config1():
    name = 'testconfig'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p.basis == pytest.approx(80000, abs=0.5)
    assert p.bequest == pytest.approx(606235, abs=0.5)
    p.saveConfig()
    filename = name + '.ini'
    assert os.path.isfile(filename)
    p2 = owl.readConfig(name)
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p2.basis == pytest.approx(80000, abs=0.5)
    assert p2.bequest == pytest.approx(606235, abs=0.5)
    os.remove(filename)


def test_config2():
    name = 'testconfig'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p.basis == pytest.approx(80000, abs=0.5)
    assert p.bequest == pytest.approx(606235, abs=0.5)
    iostring = StringIO()
    p.saveConfig(iostring)
    # print('iostream:', iostream.getvalue())
    p2 = owl.readConfig(iostring)
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p2.basis == pytest.approx(80000, abs=0.5)
    assert p2.bequest == pytest.approx(606235, abs=0.5)


def test_clone1():
    name = 'testclone1'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p.basis == pytest.approx(80000, abs=0.5)
    assert p.bequest == pytest.approx(606235, abs=0.5)
    name2 = 'testclone2'
    p2 = owl.clone(p, name2)
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p2.basis == pytest.approx(80000, abs=0.5)
    assert p2.bequest == pytest.approx(606235, abs=0.5)


def test_clone2():
    name = 'testclone1'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 0})
    assert p.basis == pytest.approx(92543, abs=0.5)
    assert p.bequest == pytest.approx(0, abs=0.5)
    name2 = 'testclone2'
    p2 = owl.clone(p, name2)
    p2.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 0})
    assert p2.basis == pytest.approx(92543, abs=0.5)
    assert p2.bequest == pytest.approx(0, abs=0.5)
