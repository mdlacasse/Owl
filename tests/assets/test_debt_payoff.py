"""
Loans paid off by the sale of a property (Debts `property` column).

A loan linked to a residence or real estate in Fixed Assets is paid off in the year that property
is sold: the balance owed at the start of that year is paid that year and nothing after. Issue
#173 (Florin Mateoc): the payments otherwise ran to term after the house was gone.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import numpy as np
import pandas as pd
import pytest

import owlplanner as owl
from owlplanner import debts
from owlplanner.hfp_io import _conditionHouseTables, conditionDebtsAndFixedAssetsDF as cond

Y = 2030  # plan start year used by the unit tests
N = 30  # plan years: Y .. Y + 29


class _Log:
    def vprint(self, *a, **k):
        pass


def _debts(prop="home", active=True, year=Y, term=30):
    return cond(pd.DataFrame([dict(active=active, name="mtg", type="mortgage", year=year, term=term,
                                   amount=640000.0, rate=6.5, property=prop)]), "Debts")


def _assets(yod=Y + 10, active=True, type="residence", name="home", extra=None):
    rows = [dict(active=active, name=name, type=type, year=Y, basis=800000.0, value=800000.0, rate=0.5,
                 yod=yod, commission=6.0)]
    rows += extra or []
    return cond(pd.DataFrame(rows), "Fixed Assets")


def _payoffs(d, a):
    return debts.resolve_payoff_years(d, a, N, Y)


# ----- resolving the link --------------------------------------------------------------------

def test_linked_loan_ends_in_the_sale_year():
    assert _payoffs(_debts(), _assets()) == {0: Y + 10}


def test_relative_sale_year_follows_the_horizon():
    # yod = -8 counts back from the plan's last year (Y + N - 1).
    assert _payoffs(_debts(), _assets(yod=-8)) == {0: Y + N - 8}
    assert debts.resolve_payoff_years(_debts(), _assets(yod=-8), N - 5, Y) == {0: Y + N - 5 - 8}


def test_two_loans_on_one_property_are_both_paid_off():
    mtg = _debts().iloc[0].to_dict()
    heloc = dict(mtg, name="heloc", type="loan", year=Y + 5, term=10, amount=50000.0)
    d = cond(pd.DataFrame([mtg, heloc]), "Debts")
    assert _payoffs(d, _assets()) == {0: Y + 10, 1: Y + 10}


def test_blank_property_runs_to_term():
    assert _payoffs(_debts(prop=""), _assets()) == {}


def test_property_not_sold_in_plan_runs_to_term():
    assert _payoffs(_debts(), _assets(yod=0)) == {}  # kept to the end of the plan
    assert _payoffs(_debts(), _assets(yod=Y + N + 5)) == {}


def test_sale_after_the_term_changes_nothing():
    assert _payoffs(_debts(term=15), _assets(yod=Y + 20)) == {}


def test_real_estate_can_pay_off_a_loan():
    assert _payoffs(_debts(prop="condo"), _assets(type="real estate", name="condo")) == {0: Y + 10}


def test_inactive_loan_is_not_checked():
    assert _payoffs(_debts(prop="nowhere", active=False), _assets()) == {}


@pytest.mark.parametrize(
    "d, a, match",
    [
        (_debts(prop="cottage"), _assets(), "not a residence or real estate"),
        (_debts(prop="home"), _assets(type="stocks"), "not a residence or real estate"),
        (_debts(), _assets(extra=[dict(active=True, name="home", type="real estate", year=Y, basis=1.0,
                                       value=1.0, rate=0.0, yod=0, commission=0.0)]), "2 fixed assets"),
        (_debts(), _assets(active=False), "not active"),
        (_debts(year=Y + 12), _assets(), "after 'home' is sold"),
    ],
)
def test_a_link_that_cannot_be_honored_is_an_error(d, a, match):
    with pytest.raises(ValueError, match=match):
        _payoffs(d, a)


# ----- the payments ----------------------------------------------------------------------------

def test_payoff_pays_the_start_of_year_balance_and_stops():
    d = _debts()
    p = {0: Y + 10}
    pay = debts.get_debt_payments_array(d, N, Y, p)
    bal = debts.get_debt_balances_array(d, N, Y, p)
    regular = debts.calculate_annual_payment(640000.0, 6.5, 30)
    assert np.allclose(pay[:10], regular)
    assert pay[10] == pytest.approx(bal[10])  # the balance owed that January
    assert bal[10] == pytest.approx(debts.calculate_remaining_balance(640000.0, 6.5, 30, 10))
    assert not pay[11:].any() and not bal[11:].any()
    assert debts.get_remaining_debt_balance(d, N, Y, p) == 0.0


def test_payoff_in_the_start_year_pays_the_principal():
    pay = debts.get_debt_payments_array(_debts(), N, Y, {0: Y})
    assert pay[0] == pytest.approx(640000.0) and not pay[1:].any()


def test_no_payoffs_is_unchanged():
    d = _debts()
    assert np.array_equal(debts.get_debt_payments_array(d, N, Y), debts.get_debt_payments_array(d, N, Y, {}))
    regular = debts.calculate_annual_payment(640000.0, 6.5, 30)
    assert debts.get_debt_payments_for_year(d, Y + 12) == pytest.approx(regular)
    assert debts.get_debt_payments_for_year(d, Y + 12, {0: Y + 10}) == 0.0
    assert debts.get_debt_payments_for_year(d, Y + 10, {0: Y + 10}) == pytest.approx(
        debts.calculate_remaining_balance(640000.0, 6.5, 30, 10)
    )


# ----- workbooks -------------------------------------------------------------------------------

def test_workbook_without_the_column_loads():
    sheet = pd.DataFrame([dict(active=True, name="mtg", type="mortgage", year=Y, term=30, amount=1000.0, rate=5.0)])
    house = _conditionHouseTables({"Debts": sheet}, _Log())
    assert house["Debts"]["property"].tolist() == [""]


def test_workbook_with_the_column_keeps_it():
    sheet = pd.DataFrame([dict(active=True, name="mtg", type="mortgage", year=Y, term=30, amount=1000.0, rate=5.0,
                               property="home")])
    assert _conditionHouseTables({"Debts": sheet}, _Log())["Debts"]["property"].tolist() == ["home"]


# ----- a plan ----------------------------------------------------------------------------------

def _plan(prop):
    """Issue #173: a $640k mortgage on an $800k home sold in plan year 10."""
    p = owl.Plan(["Joe", "Jane"], ["1964-03-15", "1964-09-15"], [89, 92], "sale", verbose=False)
    y0 = int(p.year_n[0])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[600, 600], taxDeferred=[750, 750], taxFree=[75, 75])
    p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
    p.setRates("conservative")
    p.setSocialSecurity([3000, 2400], [70, 70])
    home = dict(active=True, name="home", type="residence", year=y0, basis=800000.0, value=800000.0, rate=0.5,
                yod=y0 + 10, commission=6.0)
    mtg = dict(active=True, name="mtg", type="mortgage", year=y0, term=30, amount=640000.0, rate=6.5, property=prop)
    p.houseLists["Fixed Assets"] = cond(pd.DataFrame([home]), "Fixed Assets")
    p.houseLists["Debts"] = cond(pd.DataFrame([mtg]), "Debts")
    p.solve("maxSpending", options={"bequest": 0, "withMedicare": "none", "withSSTaxability": 0.85})
    assert p.caseStatus == "solved"
    return p


def test_plan_pays_off_the_mortgage_when_the_home_is_sold():
    to_term, linked = _plan(""), _plan("home")
    owed = linked.fixed_assets_debt_balances_remaining_n[10]
    assert owed == pytest.approx(to_term.fixed_assets_debt_balances_remaining_n[10])
    assert np.count_nonzero(to_term.debt_payments_n[10:]) == 20
    assert linked.debt_payments_n[10] == pytest.approx(owed)
    assert not linked.debt_payments_n[11:].any()
    assert np.array_equal(linked.debt_payments_n[:10], to_term.debt_payments_n[:10])
    # 6.5% on the loan is above what the savings earn: paying it off raises spending.
    assert linked.g_n[0] > to_term.g_n[0]
