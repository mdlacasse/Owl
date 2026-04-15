"""
Regression tests for stochastic spending with longevity risk.
"""

from datetime import date
import numpy as np

import owlplanner as owl
import owlplanner.stresstests as stresstests


def _create_plan_for_stochastic_longevity():
    thisyear = date.today().year
    inames = ["Pat"]
    dobs = [f"{thisyear - 90}-01-15"]
    expectancy = [92]
    p = owl.Plan(inames, dobs, expectancy, "stochastic-longevity-regression")
    p.setSpendingProfile("flat")
    p.setAccountBalances(
        taxable=[80],
        taxDeferred=[120],
        taxFree=[30],
        startDate="1-1",
    )
    p.setAllocationRatios(
        "individual",
        generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]],
    )
    p.setPension([0], [65])
    p.setSocialSecurity([0], [70])
    p.setReproducible(True, seed=12345)
    p.setRates(
        "gaussian",
        values=[6, 3, 2, 2],
        stdev=[10, 4, 3, 1],
        corr=[0.46, 0.06, -0.12, 0.68, -0.27, -0.21],
    )
    return p


def test_stochastic_spending_mc_longevity_handles_longer_horizons(monkeypatch):
    """MC longevity should work when drawn scenario horizons exceed base plan horizon."""

    def _long_life_draw(_sex, current_age, n, rng=None, table="SSA2025"):
        assert n == 1
        _ = (rng, table)  # keep signature compatibility
        return np.array([current_age + 8], dtype=int)

    monkeypatch.setattr(stresstests, "sample_lifespans", _long_life_draw)

    p = _create_plan_for_stochastic_longevity()
    base_horizon = p.N_n
    options = {
        "maxRothConversion": 100,
        "bequest": 100,
        "solver": "HiGHS",
        "withSSTaxability": 0.85,
    }

    out1 = p.runStochasticSpending(
        "maxSpending",
        options,
        "mc",
        N=4,
        with_longevity=True,
        sexes=["M"],
        seed=2026,
    )

    current_ages = [int(p.year_n[0] - p.yobs[i]) for i in range(p.N_i)]
    horizons = [
        max(int(drawn[i] - current_ages[i] + 1) for i in range(p.N_i))
        for drawn in out1["drawn_lifespans"]
    ]
    assert max(horizons) > base_horizon
    assert len(out1["bases"]) >= 2

    p2 = _create_plan_for_stochastic_longevity()
    out2 = p2.runStochasticSpending(
        "maxSpending",
        options,
        "mc",
        N=4,
        with_longevity=True,
        sexes=["M"],
        seed=2026,
    )
    np.testing.assert_allclose(out1["bases"], out2["bases"], rtol=1e-12, atol=1e-9)


def test_stochastic_spending_mc_longevity_seed_sensitivity(monkeypatch):
    """Changing longevity seed or rate seed should change scenario outcomes."""

    def _long_life_draw(_sex, current_age, n, rng=None, table="SSA2025"):
        assert n == 1
        _ = table
        # Use RNG so longevity seed actually controls sampled lifespans.
        return np.array([current_age + int(rng.integers(3, 8))], dtype=int)

    monkeypatch.setattr(stresstests, "sample_lifespans", _long_life_draw)

    options = {
        "maxRothConversion": 100,
        "bequest": 100,
        "solver": "HiGHS",
        "withSSTaxability": 0.85,
    }

    # Baseline run
    p_base = _create_plan_for_stochastic_longevity()
    out_base = p_base.runStochasticSpending(
        "maxSpending",
        options,
        "mc",
        N=4,
        with_longevity=True,
        sexes=["M"],
        seed=1111,
    )

    # Same rate seed, different longevity seed -> different outcomes
    p_longevity_changed = _create_plan_for_stochastic_longevity()
    out_longevity_changed = p_longevity_changed.runStochasticSpending(
        "maxSpending",
        options,
        "mc",
        N=4,
        with_longevity=True,
        sexes=["M"],
        seed=2222,
    )
    assert not np.allclose(out_base["bases"], out_longevity_changed["bases"], atol=1e-9)

    # Same longevity seed, different rate seed -> different outcomes
    p_rate_changed = _create_plan_for_stochastic_longevity()
    p_rate_changed.setReproducible(True, seed=54321)
    p_rate_changed.setRates(
        "gaussian",
        values=[6, 3, 2, 2],
        stdev=[10, 4, 3, 1],
        corr=[0.46, 0.06, -0.12, 0.68, -0.27, -0.21],
    )
    out_rate_changed = p_rate_changed.runStochasticSpending(
        "maxSpending",
        options,
        "mc",
        N=4,
        with_longevity=True,
        sexes=["M"],
        seed=1111,
    )
    assert not np.allclose(out_base["bases"], out_rate_changed["bases"], atol=1e-9)
