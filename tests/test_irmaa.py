
import pytest
import numpy as np
from datetime import date

import owlplanner as owl


# solver = 'MOSEK'
solver = 'HiGHS'
thisyear = date.today().year


def createBasePlan(name):
    inames = ['Jack', 'Jill']
    ages = [70, 68]
    yobs = [thisyear - ages[0], thisyear - ages[1]]
    expectancy = [ages[0] + 20, ages[1] + 20]
    p = owl.Plan(inames, yobs, expectancy, name, startDate='1-1')
    p.setSpendingProfile('flat', 60)

    p.setAccountBalances(taxable=[90, 60],
                         taxDeferred=[600, 150], taxFree=[50 + 20, 40])
    p.readContributions('./examples/jack+jill.xlsx')
    p.setInterpolationMethod('s-curve')
    p.setAllocationRatios('individual',
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]],
                                   [[50, 50, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0, 10], [65, 65])
    p.setSocialSecurity([28, 25], [70, 70])

    return p


def test_IRMAA_brackets():
    p = createBasePlan('IRMAA_brackets')
    # p.setRates('historical', 1969)
    p.setRates('conservative')

    nm, L_nq, C_nq = owl.tax2025.mediVals(p.yobs, p.horizons, p.gamma_n, p.N_n, p.N_q)

    magis = 3*[0]
    for q in range(p.N_q):
        for n in range(2):
            magis[n] = L_nq[n, q] + 1

        kmagis = np.array(magis)/1000
        p.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 500, 'previousMAGIs': kmagis})

        for n in range(2):
            for qq in range(p.N_q):
                if L_nq[n, qq] <= magis[n] and magis[n] < L_nq[n, qq+1]:
                    assert p.zm_nq[n, qq] == 1, \
                        f"MAGI of {magis[n]} NOT found in {L_nq[n, qq]} and {L_nq[n, qq+1]}!"
                    assert p.m_n[n] == pytest.approx(C_nq[n, qq], abs=0.5)
                else:
                    assert p.zm_nq[n, qq] == 0, \
                        f"MAGI of {magis[n]} wrongly found in {L_nq[n, qq]} and {L_nq[n, qq+1]}!"
