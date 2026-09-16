"""
saveConfig() must refuse a half-built plan.

The cloud UI builds a Plan as soon as a case is named and only pushes values onto it at
run time, so every path that serialises a Plan can be handed one where beta_ij, the rate
method, or the profiles are still None. plan_to_config() reads those attributes directly
and used to die on a bare `TypeError: 'NoneType' object is not subscriptable`.

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

from io import StringIO

import pytest

import owlplanner as owl

CASE = "examples/Case_jack+jill.toml"


def _barePlan():
    """A Plan the way the UI creates one: named, and nothing else set."""
    log = StringIO()
    plan = owl.Plan(["Joe"], ["1960-01-01"], [90], "readiness", verbose=False, logstreams=[log, log])
    return plan, log


def test_bare_plan_is_not_configured():
    plan, _ = _barePlan()
    assert plan.isConfigured() is False


def test_is_configured_does_not_log():
    """
    The UI asks before every case-file download; asking must not fill the case log.
    """
    plan, log = _barePlan()
    mark = len(log.getvalue())
    plan.isConfigured()
    plan.isConfigured()
    assert log.getvalue()[mark:] == ""


def test_save_config_on_bare_plan_raises_instead_of_TypeError():
    plan, _ = _barePlan()
    with pytest.raises(RuntimeError, match="spending profile"):
        plan.saveConfig(StringIO())


def test_readiness_names_the_missing_balances():
    """
    The reported crash was beta_ij: with the profiles set, balances are what is left.
    """
    plan, _ = _barePlan()
    plan.setSpendingProfile("flat")
    plan.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    assert plan.beta_ij is None
    assert plan.isConfigured() is False
    with pytest.raises(RuntimeError, match="account balances"):
        plan.saveConfig(StringIO())


def test_readiness_names_the_missing_rate_method():
    """
    plan_to_config() reaches myplan.rateModel.params, so rates are a real precondition.
    """
    plan, _ = _barePlan()
    plan.setSpendingProfile("flat")
    plan.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    plan.setAccountBalances(taxable=[100], taxDeferred=[500], taxFree=[50])
    assert plan.rateMethod is None
    assert plan.isConfigured() is False
    assert plan.isConfigured(requireRates=False) is True
    with pytest.raises(RuntimeError, match="Rate method"):
        plan.saveConfig(StringIO())


@pytest.mark.toml
def test_configured_plan_still_saves():
    plan = owl.readConfig(CASE, verbose=False)
    assert plan.isConfigured() is True
    buffer = StringIO()
    plan.saveConfig(buffer)
    assert "[basic_info]" in buffer.getvalue()
