"""
Tests for config <-> UI flat dict conversion (owlplanner.config.ui_bridge).

Copyright (C) 2025-2026 The Owlplanner Authors
"""

from io import StringIO

import owlplanner as owl
from owlplanner.config import (
    apply_config_to_plan,
    config_to_plan,
    config_to_ui,
    load_toml,
    plan_to_config,
    sanitize_config,
    ui_to_config,
)


def test_sanitize_config_start_roth_past_year():
    """sanitize_config resets startRothConversions to this year when in the past."""
    from datetime import date

    diconf = {"solver_options": {"startRothConversions": 2019}}
    log = StringIO()
    sanitize_config(diconf, log_stream=log)
    thisyear = date.today().year

    assert diconf["solver_options"]["startRothConversions"] == thisyear
    assert "Warning" in log.getvalue()
    assert "reset to" in log.getvalue()


def test_load_toml_start_roth_past_year_reset():
    """startRothConversions in the past is reset when config file is read (via sanitize_config)."""
    from datetime import date

    toml_content = open("examples/Case_joe.toml").read()
    toml_content = toml_content.replace(
        "startRothConversions = 2026",
        "startRothConversions = 2019",  # Past year
    )
    log = StringIO()
    diconf, _, _ = load_toml(StringIO(toml_content), log_stream=log)
    thisyear = date.today().year

    assert diconf["solver_options"]["startRothConversions"] == thisyear
    assert "Warning" in log.getvalue()


def test_config_to_ui_roundtrip():
    """config -> ui -> config preserves structure."""
    diconf, _, _ = load_toml(StringIO(open("examples/Case_joe.toml").read()))
    uidic = config_to_ui(diconf)

    assert uidic["name"] == "joe"
    assert uidic["status"] == "single"
    assert uidic["iname0"] == "Joe"
    assert uidic["allocType"] == "individual"

    back = ui_to_config(uidic)
    assert back["case_name"] == "joe"
    assert back["basic_info"]["names"] == ["Joe"]
    assert back["asset_allocation"]["type"] == "individual"


def test_ui_to_config_to_plan():
    """ui dict -> config -> plan produces valid plan."""
    diconf, _, _ = load_toml(StringIO(open("examples/Case_joe.toml").read()))
    uidic = config_to_ui(diconf)
    back = ui_to_config(uidic)
    plan = config_to_plan(back, verbose=False, read_contributions=False)

    assert plan._name == "joe"
    assert plan.N_i == 1
    assert plan.inames[0] == "Joe"


def test_apply_config_to_plan():
    """apply_config_to_plan syncs config to existing plan."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("default")
    if not hasattr(p, "solverOptions"):
        p.solverOptions = {}

    diconf = plan_to_config(p)
    diconf["savings_assets"]["taxable_savings_balances"] = [150.0]  # Change

    apply_config_to_plan(p, diconf)
    assert p.beta_ij[0, 0] == 150000  # 150 * 1000
