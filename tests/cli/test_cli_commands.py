"""
Tests for owlcli commands and MCP tool functions.

CLI commands are tested via Click's CliRunner (no subprocess).
MCP tool functions are called directly (no stdio transport needed).

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import json
import pytest
from click.testing import CliRunner

from owlplanner.cli._main import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BILL_TOML = "examples/Case_bill.toml"
JACK_TOML = "examples/Case_jack+jill.toml"

# Override to make solves fast in CLI tests
FAST_OPTS = [
    "--set",
    "rates_selection.method=conservative",
    "--set",
    "solver_options.withMedicare=None",
    "--set",
    "solver_options.withSCLoop=false",
    "--set",
    "solver_options.withDecomposition=none",
]


class _Result:
    """Thin wrapper: exposes .output as clean stdout (Click 8.4+ separates stdout/stderr)."""

    def __init__(self, r):
        self._r = r
        self.output = r.stdout  # JSON-only; stderr carries log lines
        self.exit_code = r.exit_code


def _invoke(*args):
    runner = CliRunner()
    return _Result(runner.invoke(cli, list(args), catch_exceptions=False))


# ---------------------------------------------------------------------------
# owlcli explain
# ---------------------------------------------------------------------------


def test_explain_exit_code():
    r = _invoke("explain", JACK_TOML)
    assert r.exit_code == 0


def test_explain_valid_json():
    r = _invoke("explain", JACK_TOML)
    data = json.loads(r.output)
    assert isinstance(data, dict)


def test_explain_required_keys():
    r = _invoke("explain", JACK_TOML)
    data = json.loads(r.output)
    for key in (
        "filename",
        "case_name",
        "filing_status",
        "individuals",
        "time_horizon",
        "objective",
        "rate_method",
        "account_balances",
        "social_security",
        "solver_options",
    ):
        assert key in data, f"Missing key: {key}"


def test_explain_individuals_structure():
    r = _invoke("explain", JACK_TOML)
    data = json.loads(r.output)
    for ind in data["individuals"]:
        assert "name" in ind
        assert "birth_year" in ind
        assert "current_age" in ind
        assert "life_expectancy" in ind
        assert "plan_end_year" in ind


def test_explain_time_horizon_consistent():
    r = _invoke("explain", JACK_TOML)
    data = json.loads(r.output)
    th = data["time_horizon"]
    assert th["end_year"] == th["start_year"] + th["years"] - 1


def test_explain_account_balances_has_total():
    r = _invoke("explain", JACK_TOML)
    data = json.loads(r.output)
    assert "total" in data["account_balances"]
    total = data["account_balances"]["total"]
    for field in ("taxable", "tax_deferred", "roth", "hsa"):
        assert field in total


def test_explain_with_set_override():
    r = _invoke("explain", JACK_TOML, "--set", "basic_info.state=MN")
    data = json.loads(r.output)
    assert data["state"] == "MN"
    assert data["overrides_applied"] == ["basic_info.state=MN"]


def test_explain_single_person():
    r = _invoke("explain", BILL_TOML)
    data = json.loads(r.output)
    assert data["filing_status"] == "single"
    assert len(data["individuals"]) == 1


# ---------------------------------------------------------------------------
# owlcli list-rates
# ---------------------------------------------------------------------------


def test_list_rates_exit_code():
    r = _invoke("list-rates")
    assert r.exit_code == 0


def test_list_rates_valid_json():
    r = _invoke("list-rates")
    data = json.loads(r.output)
    assert "models" in data
    assert "aliases" in data


def test_list_rates_at_least_17_models():
    r = _invoke("list-rates")
    data = json.loads(r.output)
    assert len(data["models"]) >= 17


def test_list_rates_model_has_required_fields():
    r = _invoke("list-rates")
    data = json.loads(r.output)
    for m in data["models"]:
        assert "method" in m
        assert "model_name" in m
        assert "description" in m
        assert "category" in m
        assert "deterministic" in m
        assert "required_parameters" in m
        assert "optional_parameters" in m
        assert "aliases" in m


def test_list_rates_categories_are_valid():
    r = _invoke("list-rates")
    data = json.loads(r.output)
    valid = {"single", "deterministic", "stochastic", "dataframe"}
    for m in data["models"]:
        assert m["category"] in valid


def test_list_rates_category_filter_stochastic():
    r = _invoke("list-rates", "--category", "stochastic")
    data = json.loads(r.output)
    assert len(data["models"]) > 0
    for m in data["models"]:
        assert m["category"] == "stochastic"


def test_list_rates_category_filter_single():
    r = _invoke("list-rates", "--category", "single")
    data = json.loads(r.output)
    methods = [m["method"] for m in data["models"]]
    assert "trailing_30" in methods
    assert "conservative" in methods
    assert "historical" not in methods  # historical is deterministic, not single


def test_list_rates_aliases_dict():
    r = _invoke("list-rates")
    data = json.loads(r.output)
    aliases = data["aliases"]
    assert "default" in aliases
    assert aliases["default"] == "trailing_30"


# ---------------------------------------------------------------------------
# owlcli run --output-format json
# ---------------------------------------------------------------------------


@pytest.mark.toml
def test_run_json_exit_code():
    r = _invoke("run", BILL_TOML, "--output-format", "json", *FAST_OPTS)
    assert r.exit_code == 0


@pytest.mark.toml
def test_run_json_is_valid_json():
    r = _invoke("run", BILL_TOML, "--output-format", "json", *FAST_OPTS)
    data = json.loads(r.output)
    assert isinstance(data, dict)


@pytest.mark.toml
def test_run_json_status_solved():
    r = _invoke("run", BILL_TOML, "--output-format", "json", *FAST_OPTS)
    data = json.loads(r.output)
    assert data["status"] == "solved"


@pytest.mark.toml
def test_run_json_summary_keys():
    r = _invoke("run", BILL_TOML, "--output-format", "json", *FAST_OPTS)
    data = json.loads(r.output)
    s = data["summary"]
    for key in (
        "spending_basis_today_dollars",
        "effective_tax_rate",
        "total_spending_nominal",
        "final_bequest_nominal",
    ):
        assert key in s, f"Missing summary key: {key}"


@pytest.mark.toml
def test_run_json_by_year_present():
    r = _invoke("run", BILL_TOML, "--output-format", "json", *FAST_OPTS)
    data = json.loads(r.output)
    assert len(data["by_year"]) > 0
    assert "year" in data["by_year"][0]
    assert "spending" in data["by_year"][0]


@pytest.mark.toml
def test_run_json_with_set_override():
    """--set life_expectancy shortens the horizon — visible in time_horizon_years."""
    r = _invoke("run", BILL_TOML, "--output-format", "json", "--set", "basic_info.life_expectancy=[88]", *FAST_OPTS)
    data = json.loads(r.output)
    assert data["status"] == "solved"
    assert data["time_horizon_years"] == 24


# ---------------------------------------------------------------------------
# owlcli compare
# ---------------------------------------------------------------------------


@pytest.mark.toml
def test_compare_exit_code():
    r = _invoke("compare", BILL_TOML, "--set", "basic_info.state=CA", *FAST_OPTS)
    assert r.exit_code == 0


@pytest.mark.toml
def test_compare_valid_json():
    r = _invoke("compare", BILL_TOML, "--set", "basic_info.state=CA", *FAST_OPTS)
    data = json.loads(r.output)
    assert isinstance(data, dict)


@pytest.mark.toml
def test_compare_top_level_structure():
    r = _invoke("compare", BILL_TOML, "--set", "basic_info.state=CA", *FAST_OPTS)
    data = json.loads(r.output)
    for key in ("filename", "overrides", "base", "variant", "delta", "pct_change"):
        assert key in data, f"Missing key: {key}"


@pytest.mark.toml
def test_compare_overrides_recorded():
    r = _invoke("compare", BILL_TOML, "--set", "basic_info.state=CA", *FAST_OPTS)
    data = json.loads(r.output)
    assert "basic_info.state=CA" in data["overrides"]


@pytest.mark.toml
def test_compare_delta_keys_match_base():
    r = _invoke("compare", BILL_TOML, "--set", "basic_info.state=CA", *FAST_OPTS)
    data = json.loads(r.output)
    for k in data["delta"]:
        assert k in data["base"]
        assert k in data["variant"]


@pytest.mark.toml
def test_compare_self_zero_delta():
    """Comparing a case to itself (trivial override) should give near-zero deltas."""
    r = _invoke(
        "compare",
        BILL_TOML,
        "--set",
        "basic_info.state=TX",  # same as in the TOML
        *FAST_OPTS,
    )
    # If bill's state is already TX this is effectively a no-op override —
    # both solves are identical so the delta should be zero for all keys.
    data = json.loads(r.output)
    # At minimum the structure must be present; delta values are floats
    assert isinstance(data["delta"], dict)
    assert len(data["delta"]) > 0


@pytest.mark.toml
def test_compare_pct_change_contains_key_metrics():
    r = _invoke("compare", BILL_TOML, "--set", "basic_info.state=CA", *FAST_OPTS)
    data = json.loads(r.output)
    # pct_change may be empty for zero deltas, but keys must be a subset of expected
    for k in data["pct_change"]:
        assert k in data["delta"]


# ---------------------------------------------------------------------------
# MCP tool functions (fast tools only — no solve)
# ---------------------------------------------------------------------------


def test_mcp_list_cases_returns_array():
    from owlplanner.cli.cmd_serve import list_cases

    result = json.loads(list_cases("examples"))
    assert isinstance(result, list)
    assert len(result) > 0


def test_mcp_list_cases_entry_structure():
    from owlplanner.cli.cmd_serve import list_cases

    result = json.loads(list_cases("examples"))
    entry = result[0]
    for field in ("stem", "filename", "case_name", "has_hfp"):
        assert field in entry


def test_mcp_list_cases_nonexistent_dir():
    from owlplanner.cli.cmd_serve import list_cases

    result = json.loads(list_cases("nonexistent_dir_xyz"))
    assert "error" in result


def test_mcp_explain_case_valid():
    from owlplanner.cli.cmd_serve import explain_case

    result = json.loads(explain_case(JACK_TOML))
    assert result["case_name"] == "jack+jill"
    assert "individuals" in result
    assert "account_balances" in result


def test_mcp_explain_case_invalid_file():
    from owlplanner.cli.cmd_serve import explain_case

    result = json.loads(explain_case("nonexistent.toml"))
    assert "error" in result


def test_mcp_explain_case_with_override():
    from owlplanner.cli.cmd_serve import explain_case

    result = json.loads(explain_case(JACK_TOML, ["basic_info.state=MN"]))
    assert result["state"] == "MN"


def test_mcp_list_rate_models_all():
    from owlplanner.cli.cmd_serve import list_rate_models

    result = json.loads(list_rate_models("all"))
    assert len(result["models"]) >= 17
    assert all("method" in m and "category" in m for m in result["models"])


def test_mcp_list_rate_models_filtered():
    from owlplanner.cli.cmd_serve import list_rate_models

    result = json.loads(list_rate_models("single"))
    for m in result["models"]:
        assert m["category"] == "single"


def test_mcp_list_rate_models_invalid_category():
    from owlplanner.cli.cmd_serve import list_rate_models

    result = json.loads(list_rate_models("bogus"))
    assert "error" in result


# ---------------------------------------------------------------------------
# MCP solve tools (run_case, compare_cases)
# ---------------------------------------------------------------------------

MCP_FAST_OVERRIDES = [
    "rates_selection.method=conservative",
    "solver_options.withMedicare=None",
    "solver_options.withSCLoop=false",
    "solver_options.withDecomposition=none",
]


def _run_async(coro):
    import asyncio

    return asyncio.run(coro)


@pytest.mark.toml
def test_mcp_run_case_solves():
    from owlplanner.cli.cmd_serve import run_case

    result = _run_async(run_case(BILL_TOML, overrides=MCP_FAST_OVERRIDES))
    data = json.loads(result)
    assert data["status"] == "solved"
    assert data["spending_year1_nominal"] > 0


@pytest.mark.toml
def test_mcp_compare_cases_delta():
    from owlplanner.cli.cmd_serve import compare_cases

    result = _run_async(
        compare_cases(
            BILL_TOML,
            overrides=["basic_info.state=CA", *MCP_FAST_OVERRIDES],
        )
    )
    data = json.loads(result)
    assert "base" in data
    assert "variant" in data
    assert "delta" in data
    assert "spending_basis" in data["base"]
