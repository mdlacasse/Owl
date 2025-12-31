
import pytest
import os
from datetime import date
from io import StringIO

import owlplanner as owl


# solver = 'MOSEK'
solver = 'HiGHS'
thisyear = date.today().year

SPENDING1 = 87008.9
BEQUEST1 = 837617.4
SPENDING2 = 97191.5


def createJackAndJillPlan(name):
    inames = ['Jack', 'Jill']
    dobs = ["1963-01-15", "1966-01-16"]
    expectancy = [thisyear - 1963 + 20, thisyear - 1966 + 20]
    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile('flat', 60)

    p.setAccountBalances(taxable=[90, 60], taxDeferred=[600, 150],
                         taxFree=[50 + 20, 40], startDate="1-1")
    p.readContributions('./examples/HFP_jack+jill.xlsx')
    p.setInterpolationMethod('s-curve')
    p.setAllocationRatios('individual',
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]],
                                   [[50, 50, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0, 10], [65, 65])
    p.setSocialSecurity([2333, 2083], [67, 70])

    return p


def test_case1():
    p = createJackAndJillPlan('case1')
    p.setRates('historical', 1969)
    p.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 500})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(SPENDING1, abs=0.5)
    assert p.bequest == pytest.approx(500000, abs=0.5)


def test_case2():
    p = createJackAndJillPlan('case2')
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(80000, abs=0.5)
    assert p.bequest == pytest.approx(BEQUEST1, abs=0.5)


def test_config1():
    name = 'testconfig'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(80000, abs=0.5)
    assert p.bequest == pytest.approx(BEQUEST1, abs=0.5)
    p.saveConfig()
    base_filename = 'case_' + name
    full_filename = 'case_' + name + '.toml'
    assert os.path.isfile(full_filename)
    p2 = owl.readConfig(base_filename)
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p2.caseStatus == "solved"
    assert p2.basis == pytest.approx(80000, abs=0.5)
    assert p2.bequest == pytest.approx(BEQUEST1, abs=0.5)
    p3 = owl.readConfig(full_filename)
    p3.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p3.caseStatus == "solved"
    assert p3.basis == pytest.approx(80000, abs=0.5)
    assert p3.bequest == pytest.approx(BEQUEST1, abs=0.5)
    os.remove(full_filename)


def test_config2():
    name = 'testconfig'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(80000, abs=0.5)
    assert p.bequest == pytest.approx(BEQUEST1, abs=0.5)
    iostring = StringIO()
    p.saveConfig(iostring)
    # print('iostream:', iostream.getvalue())
    p2 = owl.readConfig(iostring)
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p2.caseStatus == "solved"
    assert p2.basis == pytest.approx(80000, abs=0.5)
    assert p2.bequest == pytest.approx(BEQUEST1, abs=0.5)


def test_clone1():
    name = 'testclone1.1'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(80000, abs=0.5)
    assert p.bequest == pytest.approx(BEQUEST1, abs=0.5)
    name2 = 'testclone1.2'
    p2 = owl.clone(p, name2)
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80})
    assert p2.caseStatus == "solved"
    assert p2.basis == pytest.approx(80000, abs=0.5)
    assert p2.bequest == pytest.approx(BEQUEST1, abs=0.5)


def test_clone2():
    name = 'testclone2.1'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 10})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(SPENDING2, abs=0.5)
    assert p.bequest == pytest.approx(10000, abs=0.5)
    name2 = 'testclone2.2'
    p2 = owl.clone(p, name2)
    p2.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 10})
    assert p2.caseStatus == "solved"
    assert p2.basis == pytest.approx(SPENDING2, abs=0.5)
    assert p2.bequest == pytest.approx(10000, abs=0.5)
