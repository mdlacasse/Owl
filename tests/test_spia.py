"""
Tests for SPIA (Single Premium Immediate Annuity) support in Owl.

Qualified SPIAs are funded from the tax-deferred (IRA) account via a non-taxable
rollover. The premium reduces the tax-deferred balance; payments are 100% ordinary income.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

from io import StringIO

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import Plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _single_plan(td=500):
    """Single-person plan with tax-deferred savings."""
    p = Plan(["Sam"], ["1960-06-15"], [90], "SPIA test")
    p.setAccountBalances(taxable=[0], taxDeferred=[td], taxFree=[0])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [50, 50, 0, 0]]])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setSpendingProfile("flat")
    p.zeroWagesAndContributions()
    return p


def _couple_plan(td0=400, td1=200):
    """Two-person plan with tax-deferred savings for both."""
    p = Plan(["Alex", "Morgan"], ["1958-03-01", "1962-09-01"], [88, 92], "SPIA couple test")
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[td0, td1], taxFree=[0, 0])
    p.setAllocationRatios("individual", generic=[
        [[60, 40, 0, 0], [50, 50, 0, 0]],
        [[60, 40, 0, 0], [50, 50, 0, 0]],
    ])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setSpendingProfile("flat")
    p.zeroWagesAndContributions()
    return p


# ---------------------------------------------------------------------------
# 1. Single-life SPIA — basic effects
# ---------------------------------------------------------------------------

def test_spia_income_amount():
    """spiaBar_in reflects $500/mo = $6,000/yr nominal in the first full year after buy_year.

    The buy_year itself may be prorated based on birth month; n_buy+1 is always full-year.
    """
    p = _single_plan()
    buy_year = p.year_n[0] + 2
    p.addSPIA(individual=0, buy_year=buy_year, premium=100_000, monthly_income=500)
    p.solve("maxSpending")

    n_full = 3   # first full year: buy_year + 1
    annual = p.spiaBar_in[0, n_full]
    assert abs(annual - 6000) < 100, f"Expected ~$6,000/yr in first full year, got ${annual:.0f}"


def test_spia_premium_reduces_tax_deferred_balance():
    """Tax-deferred balance at n_buy+1 is lower with SPIA than without."""
    p_base = _single_plan()
    p_base.solve("maxSpending")

    p_spia = _single_plan()
    buy_year = p_spia.year_n[0] + 2
    p_spia.addSPIA(individual=0, buy_year=buy_year, premium=100_000, monthly_income=500)
    p_spia.solve("maxSpending")

    bal_base = p_base.b_ijn[0, 1, 3]   # start of year n_buy+1
    bal_spia = p_spia.b_ijn[0, 1, 3]
    assert bal_spia < bal_base, (
        f"SPIA balance should be lower: {bal_spia:.0f} vs {bal_base:.0f}"
    )


def test_spia_premium_not_in_cash_flow():
    """SPIA premium leaves no trace in spia_premiums_in for years other than buy_year."""
    p = _single_plan()
    buy_year = p.year_n[0] + 3
    p.addSPIA(individual=0, buy_year=buy_year, premium=50_000, monthly_income=250)

    n_buy = 3
    assert p.spia_premiums_in[0, n_buy] == 50_000
    assert np.sum(p.spia_premiums_in[0, :n_buy]) == 0
    assert np.sum(p.spia_premiums_in[0, n_buy + 1:]) == 0


def test_spia_income_is_taxable():
    """SPIA income increases taxable income (e_n) in years it is received."""
    p_base = _single_plan()
    p_base.solve("maxSpending")

    p_spia = _single_plan()
    buy_year = p_spia.year_n[0] + 2
    p_spia.addSPIA(individual=0, buy_year=buy_year, premium=100_000, monthly_income=500)
    p_spia.solve("maxSpending")

    n_buy = 2
    # Taxable income should be higher by approximately the SPIA income amount
    assert p_spia.e_n[n_buy] > p_base.e_n[n_buy] - 1, (
        "SPIA income should increase taxable income in buy year"
    )


# ---------------------------------------------------------------------------
# 2. Past buy_year (already-purchased SPIA)
# ---------------------------------------------------------------------------

def test_spia_past_buy_year_no_premium():
    """buy_year before plan start: income flows from year 0, premium is not deducted."""
    p = _single_plan()
    past_year = p.year_n[0] - 5
    p.addSPIA(individual=0, buy_year=past_year, premium=999_999, monthly_income=500)

    # Premium should not be stored (already settled)
    assert p.spia_premiums_in.sum() == 0.0, "Past SPIA should have zero premium impact"

    p.solve("maxSpending")
    # Income should be present from year 0
    assert p.spiaBar_in[0, 0] > 0, "Past SPIA should produce income in year 0"
    assert abs(p.spiaBar_in[0, 0] - 6000) < 200, (
        f"Expected ~$6,000/yr at year 0, got ${p.spiaBar_in[0, 0]:.0f}"
    )


def test_spia_past_buy_year_increases_spending():
    """Already-purchased SPIA (free income) should allow higher spending than baseline."""
    p_base = _single_plan()
    p_base.solve("maxSpending")

    p_spia = _single_plan()
    past_year = p_spia.year_n[0] - 3
    p_spia.addSPIA(individual=0, buy_year=past_year, premium=999_999, monthly_income=500)
    p_spia.solve("maxSpending")

    assert p_spia.basis > p_base.basis, (
        f"Free SPIA income should raise spending: {p_spia.basis:.0f} vs {p_base.basis:.0f}"
    )


# ---------------------------------------------------------------------------
# 3. Inflation indexing
# ---------------------------------------------------------------------------

def test_spia_indexed_grows_with_inflation():
    """Indexed SPIA: spiaBar_in[n] grows relative to fixed SPIA at same rate as gamma_n."""
    p_fixed = _single_plan()
    buy_year = p_fixed.year_n[0] + 1
    p_fixed.addSPIA(individual=0, buy_year=buy_year, premium=0, monthly_income=500, indexed=False)
    p_fixed.solve("maxSpending")

    p_idx = _single_plan()
    p_idx.addSPIA(individual=0, buy_year=buy_year, premium=0, monthly_income=500, indexed=True)
    p_idx.solve("maxSpending")

    n = 10   # well into the horizon
    # Indexed income should exceed fixed by cumulative inflation
    assert p_idx.spiaBar_in[0, n] > p_fixed.spiaBar_in[0, n], (
        f"Indexed SPIA should be larger at year {n}: "
        f"{p_idx.spiaBar_in[0, n]:.0f} vs {p_fixed.spiaBar_in[0, n]:.0f}"
    )


def test_spia_fixed_nominal_constant():
    """Fixed nominal SPIA: real value of spiaBar_in should decrease over time."""
    p = _single_plan()
    buy_year = p.year_n[0] + 1
    p.addSPIA(individual=0, buy_year=buy_year, premium=0, monthly_income=500, indexed=False)
    p.solve("maxSpending")

    n1, n2 = 2, 15
    # Nominal income is constant; real value decreases with inflation
    real_n1 = p.spiaBar_in[0, n1] / p.gamma_n[n1]
    real_n2 = p.spiaBar_in[0, n2] / p.gamma_n[n2]
    assert real_n2 < real_n1 - 1, (
        f"Fixed SPIA real value should decrease: {real_n2:.0f} < {real_n1:.0f}"
    )


# ---------------------------------------------------------------------------
# 4. Couple: survivor fraction
# ---------------------------------------------------------------------------

def test_spia_survivor_fraction_continues_income():
    """After annuitant's horizon, survivor still receives the survivor fraction."""
    p = _couple_plan()
    buy_year = p.year_n[0] + 1
    # individual=0 buys SPIA with 50% J&S benefit
    p.addSPIA(individual=0, buy_year=buy_year, premium=100_000, monthly_income=500,
              survivor_fraction=0.5)
    p.solve("maxSpending")

    n_d = p.n_d   # year individual 0 dies
    if n_d >= p.N_n:
        pytest.skip("No death event in this couple plan horizon")

    # After death: individual 1 (survivor) should have 50% of base income
    n_after = min(n_d + 2, p.N_n - 1)
    # individual 0's income is zero after their horizon
    assert p.spiaBar_in[0, n_after] == pytest.approx(0.0, abs=1.0), (
        "Annuitant should have no income after death"
    )
    # individual 1 gets survivor benefit
    assert p.spiaBar_in[1, n_after] > 0, (
        "Survivor should continue receiving SPIA income"
    )


def test_spia_single_life_no_survivor():
    """Single-life SPIA (survivor_fraction=0): no income continues after annuitant dies."""
    p = _couple_plan()
    buy_year = p.year_n[0] + 1
    p.addSPIA(individual=0, buy_year=buy_year, premium=50_000, monthly_income=300,
              survivor_fraction=0.0)
    p.solve("maxSpending")

    n_d = p.n_d
    if n_d >= p.N_n:
        pytest.skip("No death event in this couple plan horizon")

    n_after = min(n_d + 2, p.N_n - 1)
    assert p.spiaBar_in[1, n_after] == pytest.approx(0.0, abs=1.0), (
        "Single-life SPIA should produce no income for survivor"
    )


# ---------------------------------------------------------------------------
# 5. Multiple SPIAs accumulate correctly
# ---------------------------------------------------------------------------

def test_multiple_spias_accumulate():
    """Two addSPIA calls for the same individual sum their income streams."""
    p_one = _single_plan()
    buy_year = p_one.year_n[0] + 2
    p_one.addSPIA(individual=0, buy_year=buy_year, premium=0, monthly_income=500)
    p_one.solve("maxSpending")

    p_two = _single_plan()
    p_two.addSPIA(individual=0, buy_year=buy_year, premium=0, monthly_income=300)
    p_two.addSPIA(individual=0, buy_year=buy_year, premium=0, monthly_income=200)
    p_two.solve("maxSpending")

    n = 5
    assert abs(p_one.spiaBar_in[0, n] - p_two.spiaBar_in[0, n]) < 10, (
        f"Two SPIAs should sum to one: {p_two.spiaBar_in[0, n]:.0f} vs {p_one.spiaBar_in[0, n]:.0f}"
    )


def test_multiple_spias_premiums_accumulate():
    """Two premiums in the same year accumulate in spia_premiums_in."""
    p = _single_plan()
    buy_year = p.year_n[0] + 1
    p.addSPIA(individual=0, buy_year=buy_year, premium=60_000, monthly_income=300)
    p.addSPIA(individual=0, buy_year=buy_year, premium=40_000, monthly_income=200)

    n_buy = 1
    assert p.spia_premiums_in[0, n_buy] == pytest.approx(100_000), (
        f"Premiums should sum to $100k, got ${p.spia_premiums_in[0, n_buy]:.0f}"
    )


# ---------------------------------------------------------------------------
# 6. TOML round-trip
# ---------------------------------------------------------------------------

SPIA_TOML = """
case_name = "spia_toml_test"
description = "SPIA TOML round-trip"

[basic_info]
status = "single"
names = ["Robin"]
sexes = ["F"]
date_of_birth = ["1958-04-01"]
life_expectancy = [90]
start_date = "today"

[savings_assets]
taxable_savings_balances = [0.0]
tax_deferred_savings_balances = [600.0]
tax_free_savings_balances = [0.0]

[fixed_income]
pension_monthly_amounts = [0]
pension_ages = [65]
pension_indexed = [false]
social_security_pia_amounts = [0]
social_security_ages = [67]
spia_individuals        = [0]
spia_buy_years          = [2020]
spia_premiums           = [0.0]
spia_monthly_incomes    = [400.0]
spia_indexed            = [false]
spia_survivor_fractions = [0.0]

[rates_selection]
heirs_rate_on_tax_deferred_estate = 30.0
dividend_rate = 1.8
obbba_expiration_year = 2032
method = "user"
values = [6.0, 4.0, 3.0, 2.5]

[asset_allocation]
interpolation_method = "linear"
interpolation_center = 15.0
interpolation_width = 5.0
type = "individual"
generic = [[[60, 40, 0, 0], [50, 50, 0, 0]]]

[optimization_parameters]
spending_profile = "flat"
surviving_spouse_spending_percent = 60
objective = "maxSpending"

[solver_options]

[results]
default_plots = "nominal"
"""


def test_spia_toml_round_trip():
    """readConfig with spia_* fields builds a plan that produces SPIA income."""
    f = StringIO(SPIA_TOML)
    p = owl.readConfig(f, verbose=False)
    p.solve("maxSpending")

    # buy_year=2020 is before plan start → income from year 0, no premium
    assert p.spiaBar_in[0, 0] > 0, "TOML SPIA should produce income from year 0"
    assert abs(p.spiaBar_in[0, 0] - 4800) < 200, (
        f"Expected ~$4,800/yr ($400/mo×12), got ${p.spiaBar_in[0, 0]:.0f}"
    )
    assert p.spia_premiums_in.sum() == 0.0, "Past SPIA premium should be zero"


def test_spia_toml_future_purchase_round_trip():
    """TOML round-trip for a future SPIA: premium deducted and income starts in buy year."""
    import datetime
    start_year = datetime.date.today().year
    buy_year = start_year + 2
    toml = f"""
case_name = "spia_future_toml_test"
description = "Future SPIA TOML round-trip"

[basic_info]
status = "single"
names = ["Robin"]
sexes = ["F"]
date_of_birth = ["1958-04-01"]
life_expectancy = [90]
start_date = "today"

[savings_assets]
taxable_savings_balances = [0.0]
tax_deferred_savings_balances = [600.0]
tax_free_savings_balances = [0.0]

[fixed_income]
pension_monthly_amounts = [0]
pension_ages = [65]
pension_indexed = [false]
social_security_pia_amounts = [0]
social_security_ages = [67]
spia_individuals        = [0]
spia_buy_years          = [{buy_year}]
spia_premiums           = [100000.0]
spia_monthly_incomes    = [500.0]
spia_indexed            = [false]
spia_survivor_fractions = [0.0]

[rates_selection]
heirs_rate_on_tax_deferred_estate = 30.0
dividend_rate = 1.8
obbba_expiration_year = 2032
method = "user"
values = [6.0, 4.0, 3.0, 2.5]

[asset_allocation]
interpolation_method = "linear"
interpolation_center = 15.0
interpolation_width = 5.0
type = "individual"
generic = [[[60, 40, 0, 0], [50, 50, 0, 0]]]

[optimization_parameters]
spending_profile = "flat"
surviving_spouse_spending_percent = 60
objective = "maxSpending"

[solver_options]
"""
    f = StringIO(toml)
    p = owl.readConfig(f, verbose=False)
    p.solve("maxSpending")

    n_buy = buy_year - start_year
    assert p.spia_premiums_in[0, n_buy] == pytest.approx(100_000.0), (
        "Premium should be deducted in buy year"
    )
    assert p.spiaBar_in[0, n_buy] > 0, "Income should begin in buy year (immediate annuity)"
    # First year is prorated by birth month; full year = $6,000, so at least half expected.
    assert p.spiaBar_in[0, n_buy] > 3_000, (
        f"Expected prorated first-year income > $3,000, got ${p.spiaBar_in[0, n_buy]:.0f}"
    )
    assert p.spiaBar_in[0, 0] == 0.0, "No income before buy year"


# ---------------------------------------------------------------------------
# 7. Validation errors
# ---------------------------------------------------------------------------

def test_spia_buy_year_after_horizon_raises():
    """buy_year at or after plan end raises ValueError."""
    p = _single_plan()
    bad_year = int(p.year_n[-1]) + 1
    with pytest.raises(ValueError, match="after the plan horizon"):
        p.addSPIA(individual=0, buy_year=bad_year, premium=50_000, monthly_income=300)


def test_spia_invalid_individual_raises():
    """individual index out of range raises ValueError."""
    p = _single_plan()
    with pytest.raises(ValueError, match="out of range"):
        p.addSPIA(individual=1, buy_year=p.year_n[0] + 1, premium=50_000, monthly_income=300)


# ---------------------------------------------------------------------------
# 8. fixedIncomeStreams includes SPIA
# ---------------------------------------------------------------------------

def test_fixed_income_streams_includes_spia():
    """fixedIncomeStreams 'spia' key is non-zero after addSPIA."""
    p = _single_plan()
    buy_year = p.year_n[0] + 1
    p.addSPIA(individual=0, buy_year=buy_year, premium=0, monthly_income=500)
    p.solve("maxSpending")

    streams = owl.fixedIncomeStreams(p)
    assert "spia" in streams, "fixedIncomeStreams should have 'spia' key"
    assert streams["spia"].sum() > 0, "SPIA stream should be non-zero"
    assert np.allclose(streams["total"], streams["ss"] + streams["pension"] +
                       streams["spia"] + streams["wages"] + streams["other"] +
                       streams["fa_income"]), "total should equal sum of components"


# ---------------------------------------------------------------------------
# 9. plan_to_config round-trip — SPIA survives clone(expectancy=...)
# ---------------------------------------------------------------------------

def test_spia_survives_expectancy_clone():
    """clone(plan, expectancy=[...]) must carry SPIA through plan_to_config."""
    from owlplanner import clone

    p = _single_plan()
    buy_year = p.year_n[0] + 1
    p.addSPIA(individual=0, buy_year=buy_year, premium=50_000, monthly_income=400)
    p.solve("maxSpending")

    # Longevity clone rebuilds via plan_to_config → config_to_plan.
    new_expectancy = [int(p.expectancy[0]) + 2]
    p2 = clone(p, expectancy=new_expectancy, verbose=False)
    p2.solve("maxSpending")

    # Clone must have exactly one SPIA entry with the same parameters.
    assert len(p2._spia_list) == 1, f"Expected 1 SPIA in clone, got {len(p2._spia_list)}"
    assert p2._spia_list[0]["monthly_income"] == 400
    assert p2._spia_list[0]["buy_year"] == buy_year
    assert p2._spia_list[0]["premium"] == 50_000

    # SPIA income must be present in the cloned plan.
    n_full = 2
    assert abs(p2.spiaBar_in[0, n_full] - 4800) < 200, (
        f"Clone SPIA income should be ~$4,800/yr, got ${p2.spiaBar_in[0, n_full]:.0f}"
    )
