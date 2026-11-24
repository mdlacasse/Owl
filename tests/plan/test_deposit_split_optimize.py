"""
Tests for letting the optimizer split each surplus between the spouses' taxable accounts (#236).

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

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

import io

import numpy as np
import pytest

import owlplanner as owl
from owlplanner.config import config_to_plan, plan_to_config


def _couple(eta, phi=(1, 1, 1, 1), log=None):
    """A's taxable account is mostly gain and B's is not, so where a surplus lands matters."""
    p = owl.Plan(["A", "B"], ["1962-06-15", "1964-03-10"], [68, 75], "deposit-split", verbose=False,
                 logstreams=[log or io.StringIO()])
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[1500, 30], taxDeferred=[0, 0], taxFree=[0, 0], startDate="01-01")
    p.setCostBasis([1000, 25])
    p.setBeneficiaryFractions(list(phi))
    p.setSpousalDepositFraction(eta)
    p.setAllocationRatios("individual", generic=[[[60, 0, 0, 40], [60, 0, 0, 40]]] * 2)
    p.setRates("user", values=[6, 4, 4, 2.5])
    p.setDividendRate(1.5)
    p.setSocialSecurity([2000, 1800], [67, 67])
    p.setStateTax("PA")
    p.solve("maxSpending", options={"bequest": 0})
    assert p.caseStatus == "solved"
    return p


def test_the_free_split_does_at_least_as_well_as_any_fixed_one():
    free = _couple("optimize")
    for eta in (0.0, 0.5, 1.0):
        assert free.g_n[0] >= _couple(eta).g_n[0] - 1.0, eta
    # While both live, the deposits add up to the surplus, in whatever split.
    nd = free.n_d
    np.testing.assert_allclose(free.d_in[:, :nd].sum(axis=0), free.s_n[:nd], atol=1.0)


def test_a_fixed_fraction_still_pins_the_split():
    p = _couple(0.5)
    nd = p.n_d
    np.testing.assert_allclose(p.d_in[0, :nd], p.d_in[1, :nd], atol=1.0)


def test_optimize_with_partial_beneficiaries_warns():
    log = io.StringIO()
    _couple("optimize", phi=(0.5, 1, 1, 1), log=log)
    assert "surplus deposit fraction is optimized while beneficiary fractions are below 1" in log.getvalue()


def test_setter_and_case_file():
    p = owl.Plan(["A", "B"], ["1962-06-15", "1964-03-10"], [68, 75], "deposit-split", verbose=False)
    p.setSpousalDepositFraction("Optimize")
    assert p.etaOptimize
    with pytest.raises(ValueError):
        p.setSpousalDepositFraction("best")
    p.setSpousalDepositFraction(0.25)
    assert not p.etaOptimize and p.eta == 0.25


@pytest.mark.toml
def test_optimize_round_trips_through_the_case_file():
    p = owl.readConfig("examples/Case_jack+jill.toml", verbose=False)
    p.setSpousalDepositFraction("optimize")
    diconf = plan_to_config(p)
    assert diconf["savings_assets"]["spousal_surplus_deposit_fraction"] == "optimize"
    assert config_to_plan(diconf, verbose=False).etaOptimize
