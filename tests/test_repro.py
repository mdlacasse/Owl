"""
Reproducibility tests for Owl retirement planner.

Tests verify that the planner produces reproducible results across
different runs and environments.

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
import os
from sys import platform
from datetime import date
from io import StringIO

import owlplanner as owl


solver = 'HiGHS'
# solver = 'MOSEK'
if platform == "darwin":
    SPENDING1 = 86_958
    BEQUEST1 = 837_286
    SPENDING2 = 97_057
    SPENDING1_FIXED = 92_628
    BEQUEST1_FIXED = 500_000
elif platform in ["win32", "linux"]:
    SPENDING1 = 86_958
    BEQUEST1 = 837_319
    SPENDING2 = 97_057
    SPENDING1_FIXED = 92_628
    BEQUEST1_FIXED = 500_000
else:
    print(f"Unknown platform {platform}")
    assert False

REL_TOL = 3e-5
ABS_TOL = 50.0  # Widened from 20 to tolerate minor HiGHS version differences across Python releases


def createJackAndJillPlan(name):
    thisyear = date.today().year
    inames = ['Jack', 'Jill']
    # Keep Jack at age 62 and Jill at age 59 so SS/Medicare timing stays constant.
    dobs = [f"{thisyear - 62}-01-15", f"{thisyear - 59}-01-16"]
    expectancy = [82, 79]
    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile('flat', 60)

    p.setAccountBalances(taxable=[90, 60], taxDeferred=[600, 150],
                         taxFree=[50 + 20, 40], startDate="1-1")
    p.readHFP('./examples/HFP_jack+jill.xlsx')
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
    p.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 500, 'solver': solver, 'withSSTaxability': 0.85})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(SPENDING1, rel=REL_TOL, abs=ABS_TOL)
    assert p.bequest == pytest.approx(500_000, rel=REL_TOL, abs=ABS_TOL)


def test_case1_fixed_rates():
    p = createJackAndJillPlan('case1_fixed')
    p.setRates('user', values=[6.0, 4.0, 3.3, 2.8])
    p.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 500, 'solver': solver, 'withSSTaxability': 0.85})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(SPENDING1_FIXED, rel=REL_TOL, abs=ABS_TOL)
    assert p.bequest == pytest.approx(BEQUEST1_FIXED, rel=REL_TOL, abs=ABS_TOL)


def test_case2():
    p = createJackAndJillPlan('case2')
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(80_000, rel=REL_TOL, abs=ABS_TOL)
    assert p.bequest == pytest.approx(BEQUEST1, rel=REL_TOL, abs=ABS_TOL)


def test_config1():
    name = 'testconfig'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(80_000, rel=REL_TOL, abs=ABS_TOL)
    assert p.bequest == pytest.approx(BEQUEST1, rel=REL_TOL, abs=ABS_TOL)
    p.saveConfig()
    base_filename = 'case_' + name
    full_filename = 'case_' + name + '.toml'
    assert os.path.isfile(full_filename)
    p2 = owl.readConfig(base_filename)
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p2.caseStatus == "solved"
    assert p2.basis == pytest.approx(80_000, rel=REL_TOL, abs=ABS_TOL)
    assert p2.bequest == pytest.approx(BEQUEST1, rel=REL_TOL, abs=ABS_TOL)
    p3 = owl.readConfig(full_filename)
    p3.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p3.caseStatus == "solved"
    assert p3.basis == pytest.approx(80_000, rel=REL_TOL, abs=ABS_TOL)
    assert p3.bequest == pytest.approx(BEQUEST1, rel=REL_TOL, abs=ABS_TOL)
    os.remove(full_filename)


def test_config2():
    name = 'testconfig'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(80_000, rel=REL_TOL, abs=ABS_TOL)
    assert p.bequest == pytest.approx(BEQUEST1, rel=REL_TOL, abs=ABS_TOL)
    iostring = StringIO()
    p.saveConfig(iostring)
    # print('iostream:', iostream.getvalue())
    p2 = owl.readConfig(iostring)
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p2.caseStatus == "solved"
    assert p2.basis == pytest.approx(80_000, rel=REL_TOL, abs=ABS_TOL)
    assert p2.bequest == pytest.approx(BEQUEST1, rel=REL_TOL, abs=ABS_TOL)


def test_clone1():
    name = 'testclone1.1'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(80_000, rel=REL_TOL, abs=ABS_TOL)
    assert p.bequest == pytest.approx(BEQUEST1, rel=REL_TOL, abs=ABS_TOL)
    name2 = 'testclone1.2'
    p2 = owl.clone(p, name2)
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p2.caseStatus == "solved"
    assert p2.basis == pytest.approx(80_000, rel=REL_TOL, abs=ABS_TOL)
    assert p2.bequest == pytest.approx(BEQUEST1, rel=REL_TOL, abs=ABS_TOL)


def test_clone2():
    name = 'testclone2.1'
    p = createJackAndJillPlan(name)
    p.setRates('historical', 1969)
    p.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 10, 'solver': solver, 'withSSTaxability': 0.85})
    assert p.caseStatus == "solved"
    assert p.basis == pytest.approx(SPENDING2, rel=REL_TOL, abs=ABS_TOL)
    assert p.bequest == pytest.approx(10_000, rel=REL_TOL, abs=ABS_TOL)
    name2 = 'testclone2.2'
    p2 = owl.clone(p, name2)
    p2.solve('maxSpending', options={'maxRothConversion': 100, 'bequest': 10, 'solver': solver, 'withSSTaxability': 0.85})
    assert p2.caseStatus == "solved"
    assert p2.basis == pytest.approx(SPENDING2, rel=REL_TOL, abs=ABS_TOL)
    assert p2.bequest == pytest.approx(10_000, rel=REL_TOL, abs=ABS_TOL)


def test_stochastic_reproducibility():
    """Test that stochastic rates are reproducible when reproducibility is enabled."""
    import numpy as np

    # Create first plan with reproducible stochastic rates
    name1 = 'test_stoch_repro_1'
    p1 = createJackAndJillPlan(name1)

    # Set up stochastic rates with reproducibility enabled and a fixed seed
    test_seed = 12345
    p1.setReproducible(True, seed=test_seed)

    # Set stochastic rates with typical values
    my_means = [8, 5, 4, 3]  # Stocks, Bonds, Fixed assets, Inflation
    my_stdev = [17, 8, 8, 2]
    offdiag_corr = [.46, .06, -.12, .68, -.27, -.21]
    p1.setRates('stochastic', values=my_means, stdev=my_stdev, corr=offdiag_corr)

    # Verify reproducibility flag and seed are set
    assert p1.reproducibleRates is True
    assert p1.rateSeed == test_seed

    # Solve the case
    p1.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p1.caseStatus == "solved", f"Solve failed with status: {p1.caseStatus}"

    # Save key results for comparison
    basis1 = p1.basis
    bequest1 = p1.bequest
    tau_kn1 = p1.tau_kn.copy()  # Rate series

    # Create second plan with the same seed and reproducibility
    name2 = 'test_stoch_repro_2'
    p2 = createJackAndJillPlan(name2)

    # Set the same reproducibility settings
    p2.setReproducible(True, seed=test_seed)

    # Set the same stochastic rates
    p2.setRates('stochastic', values=my_means, stdev=my_stdev, corr=offdiag_corr)

    # Verify reproducibility flag and seed are set
    assert p2.reproducibleRates is True
    assert p2.rateSeed == test_seed

    # Solve the case
    p2.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p2.caseStatus == "solved"

    # Verify results are identical (reproducible)
    assert p2.basis == pytest.approx(basis1, rel=REL_TOL, abs=ABS_TOL)
    assert p2.bequest == pytest.approx(bequest1, rel=REL_TOL, abs=ABS_TOL)
    np.testing.assert_allclose(p2.tau_kn, tau_kn1, rtol=REL_TOL, atol=REL_TOL)

    # Test that Monte-Carlo generates different rates even with reproducibility enabled
    # Create a third plan with reproducibility enabled
    name3 = 'test_stoch_repro_3'
    p3 = createJackAndJillPlan(name3)
    p3.setReproducible(True, seed=test_seed)
    p3.setRates('stochastic', values=my_means, stdev=my_stdev, corr=offdiag_corr)

    # Save the rate series before MC
    tau_kn_before_mc = p3.tau_kn.copy()

    # Solve once to set solverOptions and objective
    p3.solve('maxBequest', options={'maxRothConversion': 100, 'netSpending': 80, 'solver': solver, 'withSSTaxability': 0.85})
    assert p3.caseStatus == "solved"

    # Run Monte-Carlo (which should override reproducibility and regenerate rates)
    options = p3.solverOptions
    objective = p3.objective
    p3.runMC(objective, options, 2)  # Just 2 runs for testing

    # Verify that the plan's rates changed after MC (MC regenerated them)
    # The rates should be different because MC overrides reproducibility
    assert not np.allclose(p3.tau_kn, tau_kn_before_mc, atol=1e-10)

    # Verify that reproducibility flag and seed are still preserved
    assert p3.reproducibleRates is True
    assert p3.rateSeed == test_seed

    # Test that after MC, if we regenerate rates without override, we get the original reproducible rates
    # Reset rates to the original reproducible ones
    p3.setRates('stochastic', values=my_means, stdev=my_stdev, corr=offdiag_corr)
    np.testing.assert_allclose(p3.tau_kn, tau_kn_before_mc, rtol=REL_TOL, atol=REL_TOL)
