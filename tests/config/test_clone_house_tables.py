"""
Debts and fixed assets survive the UI's table sync and a clone with a new lifespan.

The UI syncs the Financial Profile by handing readHFP the per-person sheets alone. readHFP used to
treat that as a workbook without Debts or Fixed Assets: it logged them as missing, emptied the
plan's household tables until the UI restored them, and kept the per-person sheets as the plan's
raw workbook. A clone with a new life expectancy, rebuilt from that raw workbook, then had no debts
and no fixed assets, so Spending Optimization with lifespan sampling ran without them.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
from pathlib import Path

import pytest

import owlplanner as owl
from owlplanner import clone

CASE = Path(__file__).resolve().parents[2] / "examples" / "Case_jack+jill.toml"


def _counts(p):
    return {k: len(v) for k, v in p.houseLists.items()}


@pytest.fixture
def synced():
    """jack+jill (one debt, one fixed asset) after the UI's sync of the per-person tables."""
    log = io.StringIO()
    p = owl.readConfig(str(CASE), verbose=True, logstreams=[log, log])
    log.truncate(0)
    p.readHFP({n: p.timeLists[n] for n in p.inames}, houseTables=False)
    return p, log.getvalue()


@pytest.mark.toml
def test_sync_keeps_the_household_tables(synced):
    p, log = synced
    assert _counts(p) == {"Debts": 1, "Fixed Assets": 1}
    assert {"Debts", "Fixed Assets"} <= set(p.rawHFP)
    assert "not found" not in log


@pytest.mark.toml
def test_clone_with_a_new_lifespan_keeps_debts_and_assets(synced):
    p, _ = synced
    p.houseLists["Fixed Assets"].loc[0, "value"] = 123.0  # an edit made in the UI
    c = clone(p, expectancy=[int(e) + 1 for e in p.expectancy], verbose=False)
    assert _counts(c) == {"Debts": 1, "Fixed Assets": 1}
    assert float(c.houseLists["Fixed Assets"].loc[0, "value"]) == 123.0
