"""
A seeded MCP stochastic tool must return the same answer twice.

These tools document a `seed` for reproducibility, but the seed has to reach
setRates(), not merely setReproducible() afterwards. A rate model that is fitted
rather than sampled -- gmm fits a mixture by EM from a random start -- consumes its
randomness while being built, and reseeding later only affects sampling: the fitted
mixture stays as it was. Four tools built their plan without passing the seed
through, so `seed=42` returned a different answer on every call, over a 3.8x range.

gmm is the point of these tests: with a purely sampled model (lognormal, historical
bootstrap) the scenario RNG reset covers it and the bug is invisible.

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

import asyncio
import json

import pytest

from owlplanner.assistant import tools as T

_PERSON = dict(
    names=["Sam"],
    birth_dates=["1962-07-01"],
    life_expectancy=[87],
    state="TX",
    taxable=[0.0],
    tax_deferred=[1_000_000.0],
    roth=[0.0],
    ss_monthly_pias=[2_300.0],
    ss_ages=[67],
    rate_method="gmm",  # fitted, not merely sampled -- see module docstring
    objective="maxSpending",
)

_SEED = 42
_N = 4

# The frontier tool sweeps a bequest floor under maxSpending by construction, so it
# takes no objective of its own.
_PERSON_NO_OBJECTIVE = {k: v for k, v in _PERSON.items() if k != "objective"}


def _twice(coro_fn):
    """Run a tool twice with the same seed and return both payloads, minus timings."""
    out = []
    for _ in range(2):
        data = json.loads(asyncio.run(coro_fn()))
        assert "error" not in data, data.get("error")
        # Wall-clock fields would differ run to run without saying anything about seeding.
        for key in ("elapsed_seconds", "timestamp"):
            data.pop(key, None)
        out.append(json.dumps(data, sort_keys=True))
    return out


@pytest.mark.toml
def test_run_stochastic_is_reproducible():
    first, second = _twice(
        lambda: T.run_stochastic(scenario_method="mc", n_scenarios=_N, seed=_SEED, **_PERSON)
    )
    assert first == second


@pytest.mark.toml
def test_run_longevity_stochastic_is_reproducible():
    first, second = _twice(
        lambda: T.run_longevity_stochastic(
            scenario_method="mc", n_scenarios=_N, seed=_SEED, sexes=["F"], **_PERSON
        )
    )
    assert first == second


@pytest.mark.toml
def test_run_year1_robustness_is_reproducible():
    first, second = _twice(
        lambda: T.run_year1_robustness(scenario_method="mc", n_scenarios=_N, seed=_SEED, **_PERSON)
    )
    assert first == second


@pytest.mark.toml
def test_run_spending_bequest_frontier_is_reproducible():
    first, second = _twice(
        lambda: T.run_spending_bequest_frontier(
            scenario_method="mc",
            n_scenarios=_N,
            seed=_SEED,
            bequest_grid=[0, 100_000],
            **_PERSON_NO_OBJECTIVE,
        )
    )
    assert first == second
