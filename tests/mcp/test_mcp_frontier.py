"""
Tests for the run_spending_bequest_frontier MCP tool.

Coverage:
  - _default_bequest_grid: the probe that scales the grid when the caller gives none
  - _build_frontier_json: output shape and the today's-dollars key convention
  - run_spending_bequest_frontier (async): TOML and flat-param paths, error handling

Every error must come back as a JSON {"error": ...} string rather than an exception,
since the transport has no other way to report one.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import asyncio
import json

import pytest

from owlplanner.assistant.tools import run_spending_bequest_frontier

CASE_TOML = "examples/Case_bill.toml"
SOLVER = "HiGHS"

_SINGLE = dict(
    names=["Martin"],
    birth_dates=["1960-07-01"],
    life_expectancy=[88],
    state="TX",
    taxable=[200_000],
    tax_deferred=[800_000],
    roth=[100_000],
    ss_monthly_pias=[2_500],
    ss_ages=[67],
    rate_method="conservative",
)


def _run(coro):
    return asyncio.run(coro)


def _frontier(**kwargs):
    kwargs.setdefault("solver", SOLVER)
    return json.loads(_run(run_spending_bequest_frontier(**kwargs)))


@pytest.mark.toml
class TestFromCaseFile:
    def test_deterministic_frontier(self):
        out = _frontier(
            filename=CASE_TOML,
            bequest_grid=[0, 500_000, 1_000_000],
            scenario_method="deterministic",
        )
        assert out.get("error") is None, out.get("error")
        assert out["status"] == "ok"
        assert out["scenario_method"] == "deterministic"
        assert out["n_scenarios_run"] == 1
        assert len(out["frontier"]) == 3

        spend = [r["spending_today_dollars"] for r in out["frontier"]]
        assert all(v is not None for v in spend)
        for lo, hi in zip(spend, spend[1:]):
            assert hi <= lo + 1.0, "reserving more for the estate cannot buy more spending"

    def test_monetary_keys_are_labelled_today_dollars(self):
        """The transport contract: nominal unless the key says otherwise."""
        out = _frontier(filename=CASE_TOML, bequest_grid=[0, 500_000], scenario_method="deterministic")
        for key in ("max_feasible_bequest_today_dollars", "first_unreachable_bequest_today_dollars"):
            assert key in out
        for row in out["frontier"]:
            assert "bequest_today_dollars" in row
            assert "spending_today_dollars" in row

    def test_case_bequest_floor_does_not_pin_the_curve(self):
        """
        A case file's own bequest floor must not survive into the sweep.

        The sweep sets the floor per level; leaving the file's value in place would
        clamp every level to the same estate and flatten the curve.
        """
        out = _frontier(
            filename=CASE_TOML,
            bequest_grid=[0, 1_000_000],
            scenario_method="deterministic",
        )
        spend = [r["spending_today_dollars"] for r in out["frontier"]]
        assert spend[0] > spend[1], "the curve should slope down, not sit flat"

    def test_default_grid_is_scaled_to_the_plan(self):
        """With no grid given, the probe must produce a spread of reachable levels."""
        out = _frontier(filename=CASE_TOML, scenario_method="deterministic")
        levels = [r["bequest_today_dollars"] for r in out["frontier"]]
        assert len(levels) == 5
        assert levels[0] == 0.0
        assert levels == sorted(levels)
        assert levels[-1] > 0, "the probe should find a positive reachable estate"


@pytest.mark.toml
class TestFromFlatParams:
    def test_flat_params_frontier(self):
        out = _frontier(
            bequest_grid=[0, 200_000],
            scenario_method="deterministic",
            **_SINGLE,
        )
        assert out.get("error") is None, out.get("error")
        assert out["status"] == "ok"
        spend = [r["spending_today_dollars"] for r in out["frontier"]]
        assert spend[1] <= spend[0] + 1.0


@pytest.mark.toml
class TestErrorsAreJson:
    @pytest.mark.parametrize(
        "kwargs, fragment",
        [
            (dict(filename=CASE_TOML, scenario_method="bogus"), "scenario_method"),
            (dict(filename=CASE_TOML, success_rates_pct=[0.9]), "percentage"),
            (
                dict(
                    filename=CASE_TOML,
                    scenario_method="historical",
                    success_rates_pct=[50],
                    target_success_rate_pct=90,
                ),
                "must be one of",
            ),
            (dict(filename="does_not_exist.toml"), "Failed to load"),
            (dict(), "Provide either"),
            (dict(filename=CASE_TOML, names=["A"]), "not both"),
        ],
    )
    def test_bad_input_returns_error_json(self, kwargs, fragment):
        out = _frontier(**kwargs)
        assert "error" in out, f"expected an error for {kwargs}"
        assert fragment in out["error"]

    def test_mc_on_deterministic_rates_is_reported(self):
        """Monte Carlo needs a stochastic rate method; saying so beats an empty frontier."""
        out = _frontier(bequest_grid=[0], scenario_method="mc", n_scenarios=5, **_SINGLE)
        assert "error" in out
        assert "Monte Carlo requires a stochastic rate method" in out["error"]


@pytest.mark.toml
def test_registered_in_the_tool_list():
    from owlplanner.assistant.tools import MCP_TOOLS

    assert run_spending_bequest_frontier in MCP_TOOLS
